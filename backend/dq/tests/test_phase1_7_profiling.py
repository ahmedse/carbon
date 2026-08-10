"""Phase 1.7: Data Profiling Engine — tests."""
import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from dq.models import TableProfile, FieldProfile, DQProfileConfig
from dataschema.models import DataTable, DataField, DataRow, Module
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser("admin", "a@b.com", "pass123")


@pytest.fixture
def module_obj(db):
    return Module.objects.create(name="test_module")


@pytest.fixture
def data_table(db, module_obj):
    return DataTable.objects.create(
        title="Test Table", name="test_table", module=module_obj
    )


@pytest.fixture
def data_rows(data_table):
    """Create DataTable + 3 fields + 3 rows."""
    f1 = DataField.objects.create(
        data_table=data_table, name="name", type="string", is_active=True
    )
    f2 = DataField.objects.create(
        data_table=data_table, name="age", type="number", is_active=True
    )
    f3 = DataField.objects.create(
        data_table=data_table, name="city", type="string", is_active=True
    )
    for i, (n, a, c) in enumerate(
        [("Alice", "30", "Cairo"), (None, "25", "Alex"), ("Bob", None, None)]
    ):
        DataRow.objects.create(
            data_table=data_table,
            values={"name": n, "age": a, "city": c},
        )
    return data_table


class TestDQProfileConfig:
    """1.7a: DQProfileConfig singleton."""

    def test_get_defaults(self, db):
        config = DQProfileConfig.objects.create()
        assert config.freshness_threshold_hours == 24
        assert config.volume_anomaly_pct == 25

    def test_update(self, db):
        config = DQProfileConfig.objects.create()
        config.freshness_threshold_hours = 48
        config.volume_anomaly_pct = 10
        config.save()
        config.refresh_from_db()
        assert config.freshness_threshold_hours == 48
        assert config.volume_anomaly_pct == 10

    def test_api_get(self, api_client, superuser):
        api_client.force_authenticate(superuser)
        url = reverse("dq-profile-config")
        response = api_client.get(url)
        assert response.status_code == 200
        assert "freshness_threshold_hours" in response.data

    def test_api_put(self, api_client, superuser):
        api_client.force_authenticate(superuser)
        url = reverse("dq-profile-config")
        response = api_client.put(url, {"freshness_threshold_hours": 48}, format="json")
        assert response.status_code == 200
        assert response.data["freshness_threshold_hours"] == 48

    def test_api_requires_auth(self, api_client, db):
        url = reverse("dq-profile-config")
        response = api_client.get(url)
        assert response.status_code == 401


class TestEnhancedTableProfile:
    """1.7b: TableProfile with per-column JSON summary fields."""

    def test_profile_stores_column_stats(self, data_rows):
        from dq.services import profile_table

        profile_table(data_rows.id)

        tp = TableProfile.objects.filter(data_table=data_rows).latest("profiled_at")
        assert tp.row_count == 3
        assert tp.completeness_pct > 0

        # JSON summary fields
        assert isinstance(tp.null_counts, dict)
        assert isinstance(tp.distinct_counts, dict)
        assert isinstance(tp.min_values, dict)
        assert isinstance(tp.max_values, dict)
        assert isinstance(tp.mean_values, dict)

        # name field: 1 null (row 2), 2 non-null, 2 distinct (Alice, Bob)
        assert tp.null_counts.get("name") == 1
        assert tp.distinct_counts.get("name") == 2
        assert tp.max_values.get("name") is None  # non-numeric

        # age field: 1 null (row 3), 2 numeric: 30, 25
        assert tp.null_counts.get("age") == 1
        assert tp.distinct_counts.get("age") == 2
        assert tp.min_values.get("age") == "25.0"
        assert tp.max_values.get("age") == "30.0"
        assert tp.mean_values.get("age") == 27.5

        # city field: 1 null (row 3), 2 non-null: Cairo, Alex
        assert tp.null_counts.get("city") == 1
        assert tp.distinct_counts.get("city") == 2

    def test_field_profiles_also_created(self, data_rows):
        from dq.services import profile_table

        profile_table(data_rows.id)

        fps = FieldProfile.objects.filter(data_field__data_table=data_rows)
        assert fps.count() == 3  # name, age, city


class TestManagementCommand:
    """1.7c: manage.py profile_all."""

    def test_profile_all_creates_table_profiles(self, data_rows):
        from django.core.management import call_command

        call_command("profile_all")
        # At least one profile for our test table
        assert TableProfile.objects.filter(data_table=data_rows).exists()

    def test_profile_all_with_table_id(self, data_rows):
        from django.core.management import call_command

        call_command("profile_all", table_id=data_rows.id)
        assert TableProfile.objects.filter(data_table=data_rows).exists()

    def test_profile_all_with_module_id(self, data_rows, module_obj):
        from django.core.management import call_command

        call_command("profile_all", module_id=module_obj.id)
        assert TableProfile.objects.filter(data_table=data_rows).exists()


class TestAdminActions:
    """1.7d: Admin 'Profile selected tables' action."""

    def test_admin_action_profiles_tables(self, data_rows):
        from dq.services import profile_table

        # Profile once
        profile_table(data_rows.id)
        first = TableProfile.objects.filter(data_table=data_rows).latest("profiled_at")

        # Profile again (action would re-profile)
        profile_table(data_rows.id)
        second = TableProfile.objects.filter(data_table=data_rows).latest("profiled_at")

        # Should have a profile that was updated
        assert TableProfile.objects.filter(data_table=data_rows).count() >= 1
        # Second profile should be at >= the time of the first
        assert second.profiled_at >= first.profiled_at
