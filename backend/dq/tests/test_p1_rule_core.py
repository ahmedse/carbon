"""
Tests for DQ Core P1 — Rule Core deliverable validation.

Covers:
 - rule_schema validation (valid/invalid definitions)
 - engine.evaluate() for dict-based rules
 - DQRule save() syncs denormalized fields
 - Archive semantics (API)
 - Per-dimension scores in DQMetricsView
 - Negative-value removal test
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from core.models import Module
from dataschema.models import DataTable, DataField, DataRow
from mdm.models import OrgUnit
from dq.models import DQRule, DQResult, RuleFieldAssignment, TableProfile, FieldProfile

User = get_user_model()


class RuleSchemaValidationTests(TestCase):
    """Test validate_definition() — D1."""

    def test_valid_range_definition(self):
        from dq.rule_schema import validate_definition
        d = {
            'schema_version': 1,
            'name': 'test range',
            'level': 'field',
            'dimension': 'validity',
            'type': 'range',
            'severity': 'error',
            'active': True,
            'bindings': [{'table': 'tbl', 'field': 'col'}],
            'params': {'min': 0, 'max': 100},
        }
        errors = validate_definition(d)
        self.assertEqual(errors, [])

    def test_valid_nl_check_definition(self):
        from dq.rule_schema import validate_definition
        d = {
            'schema_version': 1,
            'name': 'test nl',
            'level': 'business',
            'dimension': 'accuracy',
            'type': 'nl_check',
            'severity': 'warn',
            'active': True,
            'bindings': [{'table': 'tbl', 'field': 'col'}],
            'params': {'prompt': 'Check for outliers'},
        }
        errors = validate_definition(d)
        self.assertEqual(errors, [])

    def test_valid_standalone_rule_no_bindings(self):
        """ADR-0006: a rule must be valid without any bindings (standalone authoring)."""
        from dq.rule_schema import validate_definition
        d = {
            'schema_version': 1,
            'name': 'standalone range',
            'level': 'field',
            'dimension': 'validity',
            'type': 'range',
            'severity': 'error',
            'active': True,
            # no 'bindings' key at all — must validate clean
            'params': {'min': 0, 'max': 100},
        }
        errors = validate_definition(d)
        self.assertEqual(errors, [])

    def test_valid_standalone_rule_empty_bindings_list(self):
        """ADR-0006: an explicit empty bindings list is also valid (still standalone)."""
        from dq.rule_schema import validate_definition
        d = {
            'schema_version': 1,
            'name': 'standalone not_null',
            'level': 'field',
            'dimension': 'completeness',
            'type': 'not_null',
            'severity': 'warn',
            'active': True,
            'bindings': [],
        }
        errors = validate_definition(d)
        self.assertEqual(errors, [])

    def test_invalid_missing_name(self):
        from dq.rule_schema import validate_definition
        d = {
            'schema_version': 1,
            'level': 'field',
            'dimension': 'validity',
            'type': 'not_null',
            'severity': 'error',
            'active': True,
            'bindings': [{'table': 'tbl', 'field': 'col'}],
        }
        errors = validate_definition(d)
        self.assertTrue(any('name' in str(e.get('field', '')).lower() for e in errors))

    def test_invalid_unknown_type(self):
        from dq.rule_schema import validate_definition
        d = {
            'schema_version': 1,
            'name': 'bad type',
            'level': 'field',
            'dimension': 'validity',
            'type': 'bogus_type',
            'severity': 'error',
            'active': True,
            'bindings': [{'table': 'tbl', 'field': 'col'}],
        }
        errors = validate_definition(d)
        self.assertTrue(any('type' in str(e.get('field', '')).lower() for e in errors))

    def test_invalid_enforcement_on_write_for_nl_check(self):
        from dq.rule_schema import validate_definition
        d = {
            'schema_version': 1,
            'name': 'bad nl',
            'level': 'business',
            'dimension': 'accuracy',
            'type': 'nl_check',
            'severity': 'error',
            'active': True,
            'bindings': [{'table': 'tbl', 'field': 'col'}],
            'params': {'prompt': 'check'},
            'enforcement': {'on_write': True, 'on_import': 'flag'},
        }
        errors = validate_definition(d)
        self.assertTrue(any('nl_check' in str(e).lower() for e in errors))

    def test_invalid_range_no_params(self):
        from dq.rule_schema import validate_definition
        d = {
            'schema_version': 1,
            'name': 'bad range',
            'level': 'field',
            'dimension': 'validity',
            'type': 'range',
            'severity': 'error',
            'active': True,
            'bindings': [{'table': 'tbl', 'field': 'col'}],
            'params': {},
        }
        errors = validate_definition(d)
        self.assertTrue(any('min' in str(e).lower() or 'max' in str(e).lower() for e in errors))

    def test_invalid_threshold_bad_operator(self):
        from dq.rule_schema import validate_definition
        d = {
            'schema_version': 1,
            'name': 'bad threshold',
            'level': 'field',
            'dimension': 'validity',
            'type': 'threshold',
            'severity': 'error',
            'active': True,
            'bindings': [{'table': 'tbl', 'field': 'col'}],
            'params': {'operator': 'bogus_op', 'value': 10},
        }
        errors = validate_definition(d)
        self.assertTrue(any('operator' in str(e).lower() for e in errors))


class DQRuleModelSaveTests(TestCase):
    """Test DQRule.save() syncing denormalized fields — D2."""

    def setUp(self):
        self.user = User.objects.create_user(username='dq_save_tester', password='pass')
        self.org_unit = OrgUnit.objects.create(name='Save Test Org', code='SVTO', org_type='division')
        self.module = Module.objects.create(name='Save Module', org_unit=self.org_unit)
        self.table = DataTable.objects.create(title='Save Table', name='save_table', module=self.module)
        self.field = DataField.objects.create(data_table=self.table, name='col1', label='Col1', type='number')

    def test_rule_save_syncs_denormalized_from_definition(self):
        rule = DQRule.objects.create(
            name='will be overwritten',
            rule_level='business_rule',
            rule_type='nl_check',
            dimension='completeness',
            created_by=self.user,
            definition={
                'schema_version': 1,
                'name': 'Score >= 0',
                'level': 'field',
                'dimension': 'validity',
                'type': 'range',
                'severity': 'error',
                'active': True,
                'bindings': [{'table': 'save_table', 'field': 'col1'}],
                'params': {'min': 0},
            },
        )
        self.assertEqual(rule.name, 'Score >= 0')
        self.assertEqual(rule.rule_level, 'field_validation')
        self.assertEqual(rule.rule_type, 'range')
        self.assertEqual(rule.dimension, 'validity')
        self.assertTrue(rule.is_active)

    def test_rule_save_invalid_definition_raises(self):
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            DQRule.objects.create(
                name='bad',
                created_by=self.user,
                definition={
                    'schema_version': 1,
                    'name': '',  # empty name
                    'level': 'field',
                    'dimension': 'validity',
                    'type': 'not_null',
                    'severity': 'error',
                    'active': True,
                    'bindings': [{'table': 'tbl', 'field': 'col'}],
                },
            )


class EngineDictEvaluationTests(TestCase):
    """Test engine.evaluate() with dict-based rule definitions — D3."""

    def setUp(self):
        self.user = User.objects.create_user(username='engine_tester', password='pass')
        self.org_unit = OrgUnit.objects.create(name='Engine Test Org', code='ETO', org_type='division')
        self.module = Module.objects.create(name='Engine Module', org_unit=self.org_unit)
        self.table = DataTable.objects.create(title='Engine Table', name='engine_table', module=self.module)
        self.field = DataField.objects.create(data_table=self.table, name='val', label='Value', type='number')

    def _make_rows(self, values_list):
        DataRow.objects.bulk_create([
            DataRow(data_table=self.table, values={'val': v}) for v in values_list
        ])
        return list(DataRow.objects.filter(data_table=self.table, is_archived=False))

    def test_engine_range_passes_valid(self):
        from dq.engine import evaluate
        rows = self._make_rows([10, 20, 30])
        rule_def = {
            'type': 'range',
            'params': {'min': 0, 'max': 100},
        }
        passed, checked, failed, failures, score = evaluate(rule_def, rows, field=self.field)
        self.assertTrue(passed)
        self.assertEqual(checked, 3)
        self.assertEqual(failed, 0)

    def test_engine_range_fails_out_of_range(self):
        from dq.engine import evaluate
        rows = self._make_rows([-5, 50, 200])
        rule_def = {
            'type': 'range',
            'params': {'min': 0, 'max': 100},
        }
        passed, checked, failed, failures, score = evaluate(rule_def, rows, field=self.field)
        self.assertFalse(passed)
        self.assertEqual(failed, 2)

    def test_engine_not_null_on_empty_values(self):
        from dq.engine import evaluate
        rows = self._make_rows([10, None, 30])
        rule_def = {'type': 'not_null', 'params': {}}
        passed, checked, failed, failures, score = evaluate(rule_def, rows, field=self.field)
        self.assertFalse(passed)
        self.assertEqual(failed, 1)


class DQRuleArchiveAPITests(TestCase):
    """Test archive semantics on DELETE — D4."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_superuser(username='archive_admin', password='pass')
        self.client.force_authenticate(self.user)
        self.org_unit = OrgUnit.objects.create(name='Archive Org', code='ARCO', org_type='division')
        self.module = Module.objects.create(name='Archive Module', org_unit=self.org_unit)
        self.table = DataTable.objects.create(title='Archive Table', name='archive_table', module=self.module)
        self.field = DataField.objects.create(data_table=self.table, name='col', label='Col', type='number')

    def _create_rule(self, with_result=False):
        rule = DQRule.objects.create(
            name='Test Rule',
            rule_level='field_validation',
            rule_type='not_null',
            dimension='validity',
            is_active=True,
            created_by=self.user,
            definition={
                'schema_version': 1, 'name': 'Test Rule', 'level': 'field',
                'dimension': 'validity', 'type': 'not_null', 'severity': 'error',
                'active': True, 'bindings': [{'table': 'archive_table', 'field': 'col'}],
            },
        )
        RuleFieldAssignment.objects.create(rule=rule, data_table=self.table, data_field=self.field)
        if with_result:
            DQResult.objects.create(rule=rule, passed=True, checked_count=5, failed_count=0, score=100)
        return rule

    def test_archive_rule_with_results(self):
        rule = self._create_rule(with_result=True)
        r = self.client.delete(f'/carbon-api/dq/rules/{rule.id}/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(r.data['archived'])
        rule.refresh_from_db()
        self.assertTrue(rule.archived)
        self.assertFalse(rule.is_active)
        self.assertTrue(DQRule.objects.filter(id=rule.id).exists())

    def test_hard_delete_rule_no_results(self):
        rule = self._create_rule(with_result=False)
        r = self.client.delete(f'/carbon-api/dq/rules/{rule.id}/')
        self.assertEqual(r.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(DQRule.objects.filter(id=rule.id).exists())

    def test_archived_rules_excluded_from_list(self):
        rule = self._create_rule(with_result=True)
        # Archive it
        self.client.delete(f'/carbon-api/dq/rules/{rule.id}/')
        # List should exclude archived — fetch all pages
        all_ids = []
        url = '/carbon-api/dq/rules/'
        while url:
            r = self.client.get(url)
            data = r.data
            if isinstance(data, dict):
                items = data.get('results', [])
                url = data.get('next')
            else:
                items = data
                url = None
            all_ids.extend(item['id'] for item in items)
        self.assertNotIn(rule.id, all_ids)

    def test_include_archived_param_shows_archived(self):
        rule = self._create_rule(with_result=True)
        self.client.delete(f'/carbon-api/dq/rules/{rule.id}/')
        # Fetch all pages with include_archived
        all_ids = []
        url = '/carbon-api/dq/rules/?include_archived=1'
        while url:
            r = self.client.get(url)
            data = r.data
            if isinstance(data, dict):
                items = data.get('results', [])
                url = data.get('next')
            else:
                items = data
                url = None
            all_ids.extend(item['id'] for item in items)
        self.assertIn(rule.id, all_ids)


class DQMetricsDimensionTests(TestCase):
    """Test per-dimension scores in DQMetricsView — D5."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_superuser(username='metrics_admin', password='pass')
        self.client.force_authenticate(self.user)
        self.org_unit = OrgUnit.objects.create(name='Metrics Org', code='MTRO', org_type='division')
        self.module = Module.objects.create(name='Metrics Module', org_unit=self.org_unit)
        self.table = DataTable.objects.create(title='Metrics Table', name='metrics_table', module=self.module)
        self.field = DataField.objects.create(data_table=self.table, name='val', label='Value', type='number')
        TableProfile.objects.create(data_table=self.table, row_count=100, completeness_pct=95.0)
        FieldProfile.objects.create(data_field=self.field, null_count=5, completeness_pct=95.0, uniqueness_pct=98.0)

        # Create one validity rule with a result
        r1 = DQRule.objects.create(
            name='Val Rule', rule_level='field_validation', rule_type='range',
            dimension='validity', is_active=True, created_by=self.user,
            definition={'schema_version': 1, 'name': 'Val Rule', 'level': 'field',
                        'dimension': 'validity', 'type': 'range', 'severity': 'error',
                        'active': True, 'bindings': [{'table': 'metrics_table', 'field': 'val'}],
                        'params': {'min': 0}},
        )
        RuleFieldAssignment.objects.create(rule=r1, data_table=self.table, data_field=self.field)
        DQResult.objects.create(rule=r1, passed=True, checked_count=50, failed_count=0, score=100)

        # Create one completeness rule with a result
        r2 = DQRule.objects.create(
            name='Comp Rule', rule_level='field_validation', rule_type='not_null',
            dimension='completeness', is_active=True, created_by=self.user,
            definition={'schema_version': 1, 'name': 'Comp Rule', 'level': 'field',
                        'dimension': 'completeness', 'type': 'not_null', 'severity': 'error',
                        'active': True, 'bindings': [{'table': 'metrics_table', 'field': 'val'}]},
        )
        RuleFieldAssignment.objects.create(rule=r2, data_table=self.table, data_field=self.field)
        DQResult.objects.create(rule=r2, passed=False, checked_count=50, failed_count=10, score=80)

    def test_scores_by_dimension_in_metrics(self):
        r = self.client.get('/carbon-api/dq/metrics/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn('scores_by_dimension', r.data)
        sbd = r.data['scores_by_dimension']
        self.assertIn('validity', sbd)
        self.assertIn('completeness', sbd)
        self.assertEqual(sbd['validity'], 100.0)
        self.assertEqual(sbd['completeness'], 80.0)


class NegativeValueRemovedTests(TestCase):
    """Test negative values are no longer banned by platform — D6."""

    def setUp(self):
        self.user = User.objects.create_user(username='neg_tester', password='pass')
        self.org_unit = OrgUnit.objects.create(name='Neg Org', code='NEGO', org_type='division')
        self.module = Module.objects.create(name='Neg Module', org_unit=self.org_unit)
        self.table = DataTable.objects.create(title='Neg Table', name='neg_table', module=self.module)
        self.field = DataField.objects.create(data_table=self.table, name='val', label='Value', type='number')

    def test_negative_values_allowed_no_error(self):
        from dataschema.validators import validate_row
        errors = validate_row({'val': -5}, [self.field])
        # No 'negative' error code should appear
        codes = {e['code'] for e in errors}
        self.assertNotIn('negative', codes)
