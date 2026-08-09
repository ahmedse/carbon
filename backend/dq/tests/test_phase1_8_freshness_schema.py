"""Phase 1.8: Freshness & Schema Monitoring — tests."""
import pytest
from datetime import timedelta, datetime
from django.utils import timezone

from dq.models import (
    FreshnessCheck, SchemaSnapshot, SchemaChange,
)
from dataschema.models import DataTable, DataField, DataRow, Module

from django.core.management import call_command


@pytest.fixture
def module_obj(db):
    return Module.objects.create(name="test_module")


@pytest.fixture
def data_table(db, module_obj):
    return DataTable.objects.create(
        title="Freshness Table", name="freshness_table", module=module_obj
    )


class TestFreshnessCheck:
    """1.8a-1.8b: FreshnessCheck model + check_freshness command."""

    def test_model_create(self, data_table):
        now = timezone.now()
        fc = FreshnessCheck.objects.create(
            data_table=data_table,
            expected_max_age_hours=24,
            last_data_timestamp=now - timedelta(hours=10),
            is_fresh=True,
        )
        assert fc.is_fresh is True
        assert 'fresh' in str(fc)

    def test_model_str_stale(self, data_table):
        fc = FreshnessCheck.objects.create(
            data_table=data_table,
            expected_max_age_hours=24,
            is_fresh=False,
        )
        assert 'stale' in str(fc)

    def test_command_no_data(self, data_table):
        """Check freshness on an empty table — should be fresh."""
        call_command('check_freshness', table_id=data_table.id)
        check = FreshnessCheck.objects.filter(data_table=data_table).latest('checked_at')
        assert check.is_fresh is True

    def test_command_fresh_data(self, data_table):
        """Recently inserted row — should be fresh."""
        DataField.objects.create(data_table=data_table, name='val', type='string', is_active=True)
        DataRow.objects.create(data_table=data_table, values={'val': 'hello'})
        call_command('check_freshness', table_id=data_table.id)
        check = FreshnessCheck.objects.filter(data_table=data_table).latest('checked_at')
        assert check.is_fresh is True

    def test_command_stale_data(self, data_table):
        """Old row — should be stale with low threshold (override via DQProfileConfig)."""
        from dq.models import DQProfileConfig
        DQProfileConfig.objects.create(freshness_threshold_hours=0)

        DataField.objects.create(data_table=data_table, name='val', type='string', is_active=True)
        DataRow.objects.create(data_table=data_table, values={'val': 'old'})
        call_command('check_freshness', table_id=data_table.id)
        check = FreshnessCheck.objects.filter(data_table=data_table).latest('checked_at')
        assert check.is_fresh is False
        assert check.expected_max_age_hours == 0

    def test_command_notify_stale(self, data_table):
        """With --notify, a stale check fires a notification if rules exist."""
        from dq.models import DQProfileConfig
        from accounts.models import NotificationRule, UserAlert
        from django.contrib.auth import get_user_model

        User = get_user_model()
        User.objects.create_user("testuser", password="pass")  # active user needed

        DQProfileConfig.objects.create(freshness_threshold_hours=0)
        NotificationRule.objects.create(
            event_type=NotificationRule.EventType.FRESHNESS_VIOLATION,
            min_severity=NotificationRule.Severity.WARNING,
            enabled=True,
        )

        DataField.objects.create(data_table=data_table, name='val', type='string', is_active=True)
        DataRow.objects.create(data_table=data_table, values={'val': 'stale'})
        call_command('check_freshness', table_id=data_table.id, notify=True)

        assert UserAlert.objects.filter(category='dq_violation').count() == 1


class TestSchemaMonitoring:
    """1.8c-1.8d: SchemaSnapshot + SchemaChange models + schema_snapshot command."""

    def test_snapshot_create(self, data_table):
        DataField.objects.create(data_table=data_table, name='col_a', type='string', is_active=True)
        ss = SchemaSnapshot.objects.create(
            data_table=data_table,
            column_schema={'col_a': {'type': 'string', 'is_nullable': True, 'position': 1}},
            row_count=0,
        )
        assert ss.column_schema['col_a']['type'] == 'string'
        assert 'freshness_table' in str(ss)  # table name in __str__

    def test_schema_change_model(self, data_table):
        sc = SchemaChange.objects.create(
            data_table=data_table,
            change_type='added',
            field_name='new_col',
            old_definition=None,
            new_definition={'type': 'number'},
        )
        assert sc.change_type == 'added'
        assert 'added' in str(sc).lower()

    def test_command_initial_snapshot(self, data_table):
        """First run — no previous snapshot, so no changes detected."""
        DataField.objects.create(data_table=data_table, name='col_a', type='string', is_active=True)
        call_command('schema_snapshot', table_id=data_table.id)

        snapshots = SchemaSnapshot.objects.filter(data_table=data_table)
        assert snapshots.count() == 1
        assert SchemaChange.objects.filter(data_table=data_table).count() == 0

    def test_command_detect_added_column(self, data_table):
        """Second run after adding a column — added change detected."""
        f1 = DataField.objects.create(
            data_table=data_table, name='col_a', type='string', is_active=True
        )
        call_command('schema_snapshot', table_id=data_table.id)

        # Add a new column
        DataField.objects.create(
            data_table=data_table, name='col_b', type='number', is_active=True
        )
        call_command('schema_snapshot', table_id=data_table.id)

        assert SchemaSnapshot.objects.filter(data_table=data_table).count() == 2
        changes = SchemaChange.objects.filter(data_table=data_table, change_type='added')
        assert changes.filter(field_name='col_b').exists()

    def test_command_detect_dropped_column(self, data_table):
        """Second run after removing a column — dropped change detected."""
        f1 = DataField.objects.create(
            data_table=data_table, name='col_a', type='string', is_active=True
        )
        DataField.objects.create(
            data_table=data_table, name='col_b', type='number', is_active=True
        )
        call_command('schema_snapshot', table_id=data_table.id)

        # Archive col_b (simulating drop)
        DataField.objects.filter(name='col_b').update(is_active=False)
        call_command('schema_snapshot', table_id=data_table.id)

        changes = SchemaChange.objects.filter(data_table=data_table, change_type='dropped')
        assert changes.filter(field_name='col_b').exists()

    def test_command_detect_modified_column(self, data_table):
        """Second run after modifying column type — modified change detected."""
        DataField.objects.create(
            data_table=data_table, name='col_a', type='string', is_active=True
        )
        call_command('schema_snapshot', table_id=data_table.id)

        DataField.objects.filter(name='col_a').update(type='number')
        call_command('schema_snapshot', table_id=data_table.id)

        changes = SchemaChange.objects.filter(data_table=data_table, change_type='modified')
        assert changes.filter(field_name='col_a').exists()

    def test_command_notify_schema_change(self, data_table):
        """With --notify, schema changes fire notifications."""
        from accounts.models import NotificationRule, UserAlert
        from django.contrib.auth import get_user_model

        User = get_user_model()
        User.objects.create_user("testuser2", password="pass")

        NotificationRule.objects.create(
            event_type=NotificationRule.EventType.SCHEMA_CHANGE,
            min_severity=NotificationRule.Severity.INFO,
            enabled=True,
        )

        DataField.objects.create(
            data_table=data_table, name='col_a', type='string', is_active=True
        )
        call_command('schema_snapshot', table_id=data_table.id)
        DataField.objects.create(
            data_table=data_table, name='col_b', type='number', is_active=True
        )
        call_command('schema_snapshot', table_id=data_table.id, notify=True)

        assert UserAlert.objects.filter(category='system').count() == 1
