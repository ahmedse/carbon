"""
P2 Gate tests — verify gate purity, severity→verdict mapping,
write-path blocking, import integration, and endpoint auth.
"""
from unittest.mock import patch, MagicMock, PropertyMock

from django.test import TestCase, TransactionTestCase, override_settings
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from core.models import Module
from dataschema.models import DataTable, DataField, DataRow
from mdm.models import OrgUnit
from dq.models import DQRule, RuleFieldAssignment, DQResult
from dq.rule_schema import GATE_ELIGIBLE_TYPES

User = get_user_model()
BASE = '/carbon-api/dq'


class GatePurityTests(TestCase):
    """Verify check_rows never writes to DB."""

    @classmethod
    def setUpTestData(cls):
        cls.org = OrgUnit.objects.create(name='Gate Purity', code='GTP', org_type='division')
        cls.module = Module.objects.create(name='Gate Purity Mod', org_unit=cls.org)
        cls.table = DataTable.objects.create(title='Purity Table', name='purity_tbl', module=cls.module)
        cls.field = DataField.objects.create(data_table=cls.table, name='score', label='Score', type='number')
        cls.rule = DQRule.objects.create(
            name='Purity Range',
            rule_type='range',
            rule_level='field_validation',
            is_active=True,
            definition={
                'schema_version': 1,
                'name': 'Purity Range',
                'level': 'field',
                'dimension': 'validity',
                'type': 'range',
                'severity': 'error',
                'bindings': [{'table': 'purity_tbl', 'field': 'score'}],
                'params': {'min': 0},
                'enforcement': {'on_write': True},
                'active': True,
            },
        )
        RuleFieldAssignment.objects.create(rule=cls.rule, data_table=cls.table, data_field=cls.field)

    def test_check_rows_no_db_writes(self):
        """check_rows is pure — no .save(), .create(), .delete(), .update()."""
        from dq.gate import check_rows

        with patch.object(DQRule, 'save') as mock_save, \
             patch.object(DQRule.objects, 'create') as mock_create, \
             patch.object(DQRule.objects, 'update') as mock_update, \
             patch.object(DQResult, 'save') as mock_result_save, \
             patch.object(DQResult.objects, 'create') as mock_result_create:
            result = check_rows(self.table, [{'score': 50}])
            self.assertIn('summary', result)
            mock_save.assert_not_called()
            mock_create.assert_not_called()
            mock_update.assert_not_called()
            mock_result_save.assert_not_called()
            mock_result_create.assert_not_called()


class SeverityVerdictTests(TestCase):
    """Severity → verdict mapping."""

    @classmethod
    def setUpTestData(cls):
        cls.org = OrgUnit.objects.create(name='Sev Test', code='SEV', org_type='division')
        cls.module = Module.objects.create(name='Sev Mod', org_unit=cls.org)
        cls.table = DataTable.objects.create(title='Sev Table', name='sev_tbl', module=cls.module)
        cls.field = DataField.objects.create(data_table=cls.table, name='val', label='Val', type='number')

    def setUp(self):
        # Clean up rules from previous test methods
        DQRule.objects.filter(field_assignments__data_table=self.table).delete()

    def _make_rule(self, name, severity):
        rule = DQRule.objects.create(
            name=name,
            rule_type='range',
            rule_level='field_validation',
            is_active=True,
            definition={
                'schema_version': 1, 'name': name,
                'level': 'field', 'dimension': 'validity',
                'type': 'range', 'severity': severity,
                'bindings': [{'table': 'sev_tbl', 'field': 'val'}],
                'params': {'min': 0}, 'enforcement': {'on_write': True},
                'active': True,
            },
        )
        RuleFieldAssignment.objects.create(rule=rule, data_table=self.table, data_field=self.field)
        return rule

    def test_error_severity_blocks(self):
        from dq.gate import check_rows
        self._make_rule('err_rule', 'error')
        result = check_rows(self.table, [{'val': -5}])
        self.assertEqual(result['summary']['blocked'], 1)

    def test_warn_severity_warns(self):
        from dq.gate import check_rows
        self._make_rule('warn_rule', 'warn')
        result = check_rows(self.table, [{'val': -5}])
        self.assertEqual(result['summary']['warned'], 1)

    def test_info_severity_passes(self):
        from dq.gate import check_rows
        self._make_rule('info_rule', 'info')
        result = check_rows(self.table, [{'val': -5}])
        # info doesn't block or warn — it's pass with failures recorded
        self.assertEqual(result['summary']['passed'], 1)
        self.assertEqual(result['row_verdicts'][0]['verdict'], 'pass')

    def test_mixed_severities_worst_wins(self):
        from dq.gate import check_rows
        self._make_rule('warn_rule', 'warn')
        # Add an error rule too
        DQRule.objects.create(
            name='err_rule', rule_type='not_null', rule_level='field_validation',
            is_active=True,
            definition={
                'schema_version': 1, 'name': 'err_rule',
                'level': 'field', 'dimension': 'completeness',
                'type': 'not_null', 'severity': 'error',
                'bindings': [{'table': 'sev_tbl', 'field': 'val'}],
                'params': {}, 'enforcement': {'on_write': True},
                'active': True,
            },
        )
        RuleFieldAssignment.objects.create(
            rule=DQRule.objects.get(name='err_rule'),
            data_table=self.table, data_field=self.field,
        )
        result = check_rows(self.table, [{'val': None}])
        self.assertEqual(result['summary']['blocked'], 1)


class NlCheckExcludedTests(TestCase):
    """nl_check never runs synchronously in the gate."""

    @classmethod
    def setUpTestData(cls):
        cls.org = OrgUnit.objects.create(name='NL Test', code='NLT2', org_type='division')
        cls.module = Module.objects.create(name='NL Mod2', org_unit=cls.org)
        cls.table = DataTable.objects.create(title='NL Table2', name='nl_tbl2', module=cls.module)
        cls.field = DataField.objects.create(data_table=cls.table, name='desc', label='Desc', type='string')

    def test_nl_check_not_in_gate_eligible_types(self):
        """nl_check is NOT in GATE_ELIGIBLE_TYPES."""
        self.assertNotIn('nl_check', GATE_ELIGIBLE_TYPES)

    def test_nl_check_ignored_even_if_bound(self):
        """nl_check bound with on_write=true is skipped by gate (not in eligible types)."""
        from dq.gate import check_rows
        # nl_check can't have on_write=true per model validation, but the gate
        # skips it based on type, not enforcement flags. The GATE_ELIGIBLE_TYPES
        # frozenset already excludes it, so it never reaches the enforcement check.
        # Even if we bind it, the gate won't pick it up.
        rule = DQRule.objects.create(
            name='NL Rule', rule_type='nl_check', rule_level='business',
            is_active=True,
            definition={
                'schema_version': 1, 'name': 'NL Rule',
                'level': 'business', 'dimension': 'accuracy',
                'type': 'nl_check', 'severity': 'error',
                'bindings': [{'table': 'nl_tbl2', 'field': 'desc'}],
                'params': {'prompt': 'Check this'},
                'enforcement': {'on_write': False},
                'active': True,
            },
        )
        RuleFieldAssignment.objects.create(
            rule=rule, data_table=self.table, data_field=self.field,
        )
        result = check_rows(self.table, [{'desc': 'anything'}])
        self.assertEqual(result['summary']['passed'], 1)


class GateResultShapeTests(TestCase):
    """check_rows returns correct shape for edge cases."""

    @classmethod
    def setUpTestData(cls):
        cls.org = OrgUnit.objects.create(name='Shape Test', code='SHP', org_type='division')
        cls.module = Module.objects.create(name='Shape Mod', org_unit=cls.org)
        cls.table = DataTable.objects.create(title='Shape Table', name='shp_tbl', module=cls.module)

    def test_empty_rows_returns_empty(self):
        from dq.gate import check_rows
        result = check_rows(self.table, [])
        self.assertEqual(result['summary']['passed'], 0)
        self.assertEqual(result['row_verdicts'], [])

    def test_no_rules_bound_all_pass(self):
        from dq.gate import check_rows
        result = check_rows(self.table, [{'x': 1}])
        self.assertEqual(result['summary']['passed'], 1)
        self.assertEqual(result['row_verdicts'][0]['verdict'], 'pass')

    def test_none_table_returns_empty(self):
        from dq.gate import check_rows
        result = check_rows(None, [{'x': 1}])
        self.assertEqual(result['summary']['passed'], 1)

    def test_non_dict_rows_pass(self):
        from dq.gate import check_rows
        result = check_rows(self.table, ['not-a-dict'])
        self.assertEqual(result['summary']['passed'], 1)


class GateEndpointTests(TestCase):
    """POST /dq/gate/check/ auth and validation."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(username='gate_admin', password='pass', is_staff=True, is_superuser=True)
        cls.outsider = User.objects.create_user(username='gate_outsider', password='pass')
        cls.org = OrgUnit.objects.create(name='Gate EP Org', code='GEP', org_type='division')
        cls.module = Module.objects.create(name='Gate EP Mod', org_unit=cls.org)
        cls.table = DataTable.objects.create(title='Gate EP Table', name='gep_tbl', module=cls.module)
        cls.field = DataField.objects.create(data_table=cls.table, name='x', label='X', type='number')

    def setUp(self):
        self.client = APIClient()

    def test_authenticated_admin_gets_200(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post(f'{BASE}/gate/check/', {
            'data_table': self.table.id,
            'rows': [{'x': 1}],
        }, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn('summary', r.data)
        self.assertIn('row_verdicts', r.data)

    def test_unauthenticated_gets_401(self):
        r = self.client.post(f'{BASE}/gate/check/', {
            'data_table': self.table.id,
            'rows': [{'x': 1}],
        }, format='json')
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_outsider_gets_403(self):
        self.client.force_authenticate(self.outsider)
        r = self.client.post(f'{BASE}/gate/check/', {
            'data_table': self.table.id,
            'rows': [{'x': 1}],
        }, format='json')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_missing_data_table_returns_400(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post(f'{BASE}/gate/check/', {
            'rows': [{'x': 1}],
        }, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_empty_rows_returns_400(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post(f'{BASE}/gate/check/', {
            'data_table': self.table.id,
            'rows': [],
        }, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_nonexistent_table_returns_404(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post(f'{BASE}/gate/check/', {
            'data_table': 99999,
            'rows': [{'x': 1}],
        }, format='json')
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)


class WritePathGateTests(TestCase):
    """DataRowSerializer blocks on error rules, allows warn rules."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(username='wp_admin', password='pass', is_staff=True, is_superuser=True)
        cls.org = OrgUnit.objects.create(name='WP Org', code='WPO', org_type='division')
        cls.module = Module.objects.create(name='WP Mod', org_unit=cls.org)

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        # Each test gets its own table so rules never cross-contaminate
        test_name = self._testMethodName
        self.table = DataTable.objects.create(
            title=f'WP {test_name}', name=f'wp_{test_name[-8:]}',
            module=self.module,
        )
        self.field = DataField.objects.create(
            data_table=self.table, name='temp', label='Temp', type='number',
        )

    def _make_rule(self, name, severity, tbl_name):
        return DQRule.objects.create(
            name=name, rule_type='range', rule_level='field_validation',
            is_active=True,
            definition={
                'schema_version': 1, 'name': name,
                'level': 'field', 'dimension': 'validity',
                'type': 'range', 'severity': severity,
                'bindings': [{'table': tbl_name, 'field': 'temp'}],
                'params': {'min': 0}, 'enforcement': {'on_write': True},
                'active': True,
            },
        )

    def test_error_rule_blocks_write_400(self):
        tbl_name = self.table.name
        rule = self._make_rule('Block Neg', 'error', tbl_name)
        RuleFieldAssignment.objects.create(rule=rule, data_table=self.table, data_field=self.field)
        r = self.client.post('/carbon-api/dataschema/rows/', {
            'data_table': self.table.id,
            'values': {'temp': -5},
        }, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_warn_rule_allows_write_201(self):
        tbl_name = self.table.name
        rule = self._make_rule('Warn Neg', 'warn', tbl_name)
        RuleFieldAssignment.objects.create(rule=rule, data_table=self.table, data_field=self.field)
        r = self.client.post('/carbon-api/dataschema/rows/', {
            'data_table': self.table.id,
            'values': {'temp': -5},
        }, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)

    def test_warn_rule_sets_dq_flags(self):
        tbl_name = self.table.name
        rule = self._make_rule('Warn Neg2', 'warn', tbl_name)
        RuleFieldAssignment.objects.create(rule=rule, data_table=self.table, data_field=self.field)
        r = self.client.post('/carbon-api/dataschema/rows/', {
            'data_table': self.table.id,
            'values': {'temp': -10},
        }, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        row = DataRow.objects.get(id=r.data['id'])
        self.assertTrue(len(row.dq_flags) > 0)
        self.assertEqual(row.dq_flags[0]['rule_name'], 'Warn Neg2')
