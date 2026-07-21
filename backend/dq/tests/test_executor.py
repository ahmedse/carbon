"""
Tests for DQ rule executor and services (A1 / A3 deliverables).

Covers:
 - All rule types: not_null, unique, allowed_values, range, regex, reference_integrity
 - Edge cases: empty table, all-null, duplicates, invalid regex
 - Catalog write-back (AssetProfile quality_status / quality_score)
 - GovernanceEvent creation
"""
import time
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

from core.models import Module
from dataschema.models import DataTable, DataField, DataRow
from mdm.models import OrgUnit, ReferenceSet, ReferenceValue
from catalog.models import AssetProfile, GovernanceEvent
from dq.models import DQRule, DQResult
from dq.services import (
    _evaluate_rule, _is_empty, profile_table, run_dq,
    run_single_rule, bulk_profile, _compute_quality,
)

User = get_user_model()


# ---------------------------------------------------------------------------
# Shared test fixture mixin
# ---------------------------------------------------------------------------

class DQBaseTestCase(TestCase):
    """Create minimal schema objects shared by all executor tests."""

    def setUp(self):
        self.user = User.objects.create_user(username='dq_tester', password='pass')
        self.org_unit = OrgUnit.objects.create(
            name='DQ Test Org', code='DQTO', org_type='division'
        )
        self.module = Module.objects.create(name='DQ Module', org_unit=self.org_unit)
        self.table = DataTable.objects.create(
            title='DQ Table', name='dq_table', module=self.module
        )
        self.text_field = DataField.objects.create(
            data_table=self.table, name='email', label='Email', type='string',
        )
        self.num_field = DataField.objects.create(
            data_table=self.table, name='score', label='Score', type='number',
        )
        # Reference data
        self.ref_set = ReferenceSet.objects.create(name='Status Codes')
        ReferenceValue.objects.bulk_create([
            ReferenceValue(reference_set=self.ref_set, code='PASS', label='Pass', is_active=True),
            ReferenceValue(reference_set=self.ref_set, code='FAIL', label='Fail', is_active=True),
            ReferenceValue(reference_set=self.ref_set, code='WARN', label='Warn', is_active=True),
        ])
        self.ref_field = DataField.objects.create(
            data_table=self.table, name='status', label='Status', type='select',
            reference_set=self.ref_set,
        )

    def _make_rows(self, data_list):
        """Bulk-create DataRows from a list of dicts."""
        DataRow.objects.bulk_create([
            DataRow(data_table=self.table, values=d) for d in data_list
        ])
        return list(DataRow.objects.filter(data_table=self.table, is_archived=False))

    def _make_rule(self, rule_type, field=None, params=None, **kwargs):
        return DQRule.objects.create(
            name=f'{rule_type} rule',
            rule_type=rule_type,
            data_table=self.table if field is None else None,
            data_field=field,
            params=params or {},
            is_active=True,
            **kwargs,
        )


# ---------------------------------------------------------------------------
# Helper / utility tests
# ---------------------------------------------------------------------------

class IsEmptyTests(TestCase):
    def test_none_is_empty(self):
        self.assertTrue(_is_empty(None))

    def test_empty_string_is_empty(self):
        self.assertTrue(_is_empty(''))

    def test_zero_is_not_empty(self):
        self.assertFalse(_is_empty(0))

    def test_false_is_not_empty(self):
        self.assertFalse(_is_empty(False))

    def test_list_empty_is_empty(self):
        self.assertTrue(_is_empty([]))

    def test_nonempty_list_is_not_empty(self):
        self.assertFalse(_is_empty([1]))


# ---------------------------------------------------------------------------
# Rule type tests
# ---------------------------------------------------------------------------

class NotNullRuleTests(DQBaseTestCase):
    def test_all_present_passes(self):
        rows = self._make_rows([{'email': 'a@b.com'}, {'email': 'x@y.com'}])
        rule = self._make_rule('not_null', field=self.text_field)
        passed, checked, failed, sample, score = _evaluate_rule(rule, rows)
        self.assertTrue(passed)
        self.assertEqual(failed, 0)
        self.assertEqual(score, 100)

    def test_some_null_fails(self):
        rows = self._make_rows([{'email': 'a@b.com'}, {'email': None}, {'email': ''}])
        rule = self._make_rule('not_null', field=self.text_field)
        passed, checked, failed, sample, score = _evaluate_rule(rule, rows)
        self.assertFalse(passed)
        self.assertEqual(failed, 2)
        self.assertLess(score, 100)

    def test_all_null_fails_completely(self):
        rows = self._make_rows([{'email': None}, {'email': None}])
        rule = self._make_rule('not_null', field=self.text_field)
        passed, checked, failed, sample, score = _evaluate_rule(rule, rows)
        self.assertFalse(passed)
        self.assertEqual(failed, 2)
        self.assertEqual(score, 0)

    def test_empty_table_passes(self):
        rows = []
        rule = self._make_rule('not_null', field=self.text_field)
        passed, checked, failed, sample, score = _evaluate_rule(rule, rows)
        self.assertTrue(passed)
        self.assertEqual(score, 100)


class UniqueRuleTests(DQBaseTestCase):
    def test_all_unique_passes(self):
        rows = self._make_rows([{'email': 'a@a.com'}, {'email': 'b@b.com'}])
        rule = self._make_rule('unique', field=self.text_field)
        passed, checked, failed, sample, score = _evaluate_rule(rule, rows)
        self.assertTrue(passed)

    def test_duplicates_detected(self):
        rows = self._make_rows([
            {'email': 'dup@x.com'}, {'email': 'dup@x.com'}, {'email': 'ok@x.com'}
        ])
        rule = self._make_rule('unique', field=self.text_field)
        passed, checked, failed, sample, score = _evaluate_rule(rule, rows)
        self.assertFalse(passed)
        self.assertGreaterEqual(failed, 2)  # both dup rows flagged

    def test_nulls_ignored_for_uniqueness(self):
        rows = self._make_rows([{'email': None}, {'email': None}, {'email': 'ok@x.com'}])
        rule = self._make_rule('unique', field=self.text_field)
        passed, checked, failed, sample, score = _evaluate_rule(rule, rows)
        # nulls are skipped; only 'ok@x.com' checked — passes
        self.assertTrue(passed)


class AllowedValuesRuleTests(DQBaseTestCase):
    def test_values_in_list_passes(self):
        rows = self._make_rows([{'status': 'PASS'}, {'status': 'FAIL'}])
        rule = self._make_rule('allowed_values', field=self.ref_field,
                               params={'values': ['PASS', 'FAIL', 'WARN']})
        passed, checked, failed, sample, score = _evaluate_rule(rule, rows)
        self.assertTrue(passed)

    def test_invalid_value_fails(self):
        rows = self._make_rows([{'status': 'PASS'}, {'status': 'INVALID'}])
        rule = self._make_rule('allowed_values', field=self.ref_field,
                               params={'values': ['PASS', 'FAIL']})
        passed, checked, failed, sample, score = _evaluate_rule(rule, rows)
        self.assertFalse(passed)
        self.assertEqual(failed, 1)

    def test_via_reference_set(self):
        rows = self._make_rows([{'status': 'PASS'}, {'status': 'BADCODE'}])
        rule = self._make_rule('allowed_values', field=self.ref_field,
                               params={'reference_set': self.ref_set.id})
        passed, checked, failed, sample, score = _evaluate_rule(rule, rows)
        self.assertFalse(passed)
        self.assertEqual(failed, 1)


class RangeRuleTests(DQBaseTestCase):
    def test_in_range_passes(self):
        rows = self._make_rows([{'score': '50'}, {'score': '99'}])
        rule = self._make_rule('range', field=self.num_field, params={'min': 0, 'max': 100})
        passed, *_ = _evaluate_rule(rule, rows)
        self.assertTrue(passed)

    def test_below_min_fails(self):
        rows = self._make_rows([{'score': '-1'}, {'score': '50'}])
        rule = self._make_rule('range', field=self.num_field, params={'min': 0, 'max': 100})
        passed, checked, failed, sample, score = _evaluate_rule(rule, rows)
        self.assertFalse(passed)
        self.assertEqual(failed, 1)

    def test_non_numeric_fails(self):
        rows = self._make_rows([{'score': 'abc'}])
        rule = self._make_rule('range', field=self.num_field, params={'min': 0, 'max': 100})
        passed, checked, failed, sample, score_val = _evaluate_rule(rule, rows)
        self.assertFalse(passed)
        self.assertEqual(failed, 1)


class RegexRuleTests(DQBaseTestCase):
    EMAIL_PATTERN = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'

    def test_valid_emails_pass(self):
        rows = self._make_rows([{'email': 'user@example.com'}, {'email': 'a.b+c@x.io'}])
        rule = self._make_rule('regex', field=self.text_field,
                               params={'pattern': self.EMAIL_PATTERN})
        passed, checked, failed, sample, score = _evaluate_rule(rule, rows)
        self.assertTrue(passed)
        self.assertEqual(failed, 0)

    def test_invalid_emails_fail(self):
        rows = self._make_rows([{'email': 'not-an-email'}, {'email': 'user@'}, {'email': 'a@b.com'}])
        rule = self._make_rule('regex', field=self.text_field,
                               params={'pattern': self.EMAIL_PATTERN})
        passed, checked, failed, sample, score = _evaluate_rule(rule, rows)
        self.assertFalse(passed)
        self.assertEqual(failed, 2)

    def test_invalid_pattern_skips_gracefully(self):
        rows = self._make_rows([{'email': 'user@example.com'}])
        rule = self._make_rule('regex', field=self.text_field,
                               params={'pattern': '[invalid_regex'})
        # Should not raise; either score 100 (no match attempt) or all fail
        passed, checked, failed, sample, score = _evaluate_rule(rule, rows)
        # Rule executed without exception
        self.assertIsNotNone(score)

    def test_empty_values_skipped(self):
        rows = self._make_rows([{'email': None}, {'email': ''}, {'email': 'ok@x.com'}])
        rule = self._make_rule('regex', field=self.text_field,
                               params={'pattern': self.EMAIL_PATTERN})
        passed, checked, failed, sample, score = _evaluate_rule(rule, rows)
        self.assertEqual(checked, 1)  # only the non-empty row is checked
        self.assertTrue(passed)


class ReferenceIntegrityRuleTests(DQBaseTestCase):
    def test_valid_codes_pass(self):
        rows = self._make_rows([{'status': 'PASS'}, {'status': 'WARN'}])
        rule = self._make_rule('reference_integrity', field=self.ref_field,
                               params={'reference_set_id': self.ref_set.id})
        passed, checked, failed, sample, score = _evaluate_rule(rule, rows)
        self.assertTrue(passed)
        self.assertEqual(failed, 0)

    def test_invalid_code_fails(self):
        rows = self._make_rows([{'status': 'PASS'}, {'status': 'UNKNOWN_CODE'}])
        rule = self._make_rule('reference_integrity', field=self.ref_field,
                               params={'reference_set_id': self.ref_set.id})
        passed, checked, failed, sample, score = _evaluate_rule(rule, rows)
        self.assertFalse(passed)
        self.assertEqual(failed, 1)
        self.assertEqual(sample[0]['value'], 'UNKNOWN_CODE')

    def test_inactive_values_not_allowed(self):
        ReferenceValue.objects.create(
            reference_set=self.ref_set, code='DEPR', label='Deprecated', is_active=False
        )
        rows = self._make_rows([{'status': 'DEPR'}])
        rule = self._make_rule('reference_integrity', field=self.ref_field,
                               params={'reference_set_id': self.ref_set.id})
        passed, checked, failed, sample, score = _evaluate_rule(rule, rows)
        self.assertFalse(passed)

    def test_temporal_validity_uses_current_values_only(self):
        yesterday = timezone.now().date() - timezone.timedelta(days=1)
        tomorrow = timezone.now().date() + timezone.timedelta(days=1)
        ReferenceValue.objects.create(
            reference_set=self.ref_set, code='CURRENT', label='Current', valid_from=None, valid_to=None, is_active=True
        )
        ReferenceValue.objects.create(
            reference_set=self.ref_set, code='EXPIRED', label='Expired', valid_from=None, valid_to=yesterday, is_active=True
        )
        ReferenceValue.objects.create(
            reference_set=self.ref_set, code='FUTURE', label='Future', valid_from=tomorrow, valid_to=None, is_active=True
        )
        rows = self._make_rows([{'status': 'CURRENT'}, {'status': 'EXPIRED'}, {'status': 'FUTURE'}])
        rule = self._make_rule('reference_integrity', field=self.ref_field,
                               params={'reference_set_id': self.ref_set.id})
        passed, checked, failed, sample, score = _evaluate_rule(rule, rows)
        self.assertFalse(passed)
        self.assertEqual(failed, 2)
        self.assertEqual({item['value'] for item in sample}, {'EXPIRED', 'FUTURE'})

    def test_uses_field_reference_set_if_no_param(self):
        """Rule without explicit reference_set_id should fall back to field.reference_set."""
        rows = self._make_rows([{'status': 'PASS'}, {'status': 'BADCODE'}])
        rule = self._make_rule('reference_integrity', field=self.ref_field, params={})
        passed, checked, failed, sample, score = _evaluate_rule(rule, rows)
        self.assertFalse(passed)
        self.assertEqual(failed, 1)

    def test_no_reference_set_returns_all_failed(self):
        """Field without reference_set and no param → all non-empty values fail."""
        field_no_ref = DataField.objects.create(
            data_table=self.table, name='category', label='Category', type='string'
        )
        rows = self._make_rows([{'category': 'X'}, {'category': 'Y'}])
        rule = self._make_rule('reference_integrity', field=field_no_ref, params={})
        passed, checked, failed, sample, score = _evaluate_rule(rule, rows)
        self.assertFalse(passed)
        self.assertEqual(failed, 2)


# ---------------------------------------------------------------------------
# profile_table service
# ---------------------------------------------------------------------------

class ProfileTableTests(DQBaseTestCase):
    def test_profile_returns_correct_fields(self):
        self._make_rows([
            {'email': 'a@b.com', 'score': '10'},
            {'email': 'c@d.com', 'score': '20'},
        ])
        result = profile_table(self.table.id)
        self.assertEqual(result['table_id'], self.table.id)
        self.assertEqual(result['rows_profiled'], 2)
        self.assertIn('fields_profiled', result)
        self.assertIn('field_profiles', result)
        self.assertIn('completeness_pct', result)

    def test_profile_empty_table(self):
        result = profile_table(self.table.id)
        self.assertEqual(result['rows_profiled'], 0)
        self.assertEqual(result['completeness_pct'], 0.0)

    def test_completeness_computed_correctly(self):
        self._make_rows([
            {'email': 'a@b.com'},
            {'email': None},
            {'email': 'c@d.com'},
            {'email': None},
        ])
        result = profile_table(self.table.id)
        # email field: 2/4 = 50%; other fields also missing → avg < 100
        self.assertLessEqual(result['completeness_pct'], 60.0)


# ---------------------------------------------------------------------------
# run_dq + catalog write-back
# ---------------------------------------------------------------------------

class RunDQTests(DQBaseTestCase):
    def setUp(self):
        super().setUp()
        self._make_rows([
            {'email': 'a@b.com', 'score': '50', 'status': 'PASS'},
            {'email': 'b@c.com', 'score': '80', 'status': 'FAIL'},
            {'email': None, 'score': '5', 'status': 'BADCODE'},
        ])

    def test_run_dq_creates_results(self):
        rule = self._make_rule('not_null', field=self.text_field)
        result = run_dq(self.table.id)
        self.assertEqual(result['rules_run'], 1)
        self.assertEqual(DQResult.objects.count(), 1)

    def test_run_dq_updates_asset_profile_status(self):
        self._make_rule('not_null', field=self.text_field)
        run_dq(self.table.id, user=self.user)
        ap = AssetProfile.objects.filter(data_table=self.table).first()
        self.assertIsNotNone(ap)
        self.assertIn(ap.quality_status, ['passing', 'warning', 'failing'])
        self.assertIsNotNone(ap.quality_score)

    def test_run_dq_creates_governance_event(self):
        self._make_rule('not_null', field=self.text_field)
        run_dq(self.table.id, user=self.user)
        self.assertTrue(GovernanceEvent.objects.filter(entity_type='AssetProfile').exists())

    def test_passing_score_sets_passing_status(self):
        # All rows have valid emails → not_null passes → 100% → 'passing'
        self._make_rule('not_null', field=self.text_field)
        # Remove the null row
        DataRow.objects.filter(data_table=self.table).delete()
        DataRow.objects.create(data_table=self.table, values={'email': 'a@b.com'})
        run_dq(self.table.id, user=self.user)
        ap = AssetProfile.objects.filter(data_table=self.table).first()
        self.assertEqual(ap.quality_status, 'passing')
        self.assertEqual(ap.quality_score, 100)

    def test_all_fail_sets_failing_status(self):
        # not_null will fail for all rows (all null email)
        DataRow.objects.filter(data_table=self.table).delete()
        DataRow.objects.bulk_create([
            DataRow(data_table=self.table, values={'email': None}),
            DataRow(data_table=self.table, values={'email': None}),
        ])
        self._make_rule('not_null', field=self.text_field)
        run_dq(self.table.id, user=self.user)
        ap = AssetProfile.objects.filter(data_table=self.table).first()
        self.assertEqual(ap.quality_status, 'failing')


class RunSingleRuleTests(DQBaseTestCase):
    def setUp(self):
        super().setUp()
        DataRow.objects.bulk_create([
            DataRow(data_table=self.table, values={'email': 'a@b.com', 'score': '50'}),
            DataRow(data_table=self.table, values={'email': 'c@d.com', 'score': '80'}),
        ])

    def test_run_single_rule_returns_correct_shape(self):
        rule = self._make_rule('not_null', field=self.text_field)
        result = run_single_rule(rule.id, user=self.user)
        self.assertIn('rule_id', result)
        self.assertIn('passed', result)
        self.assertIn('score', result)
        self.assertIn('result_id', result)

    def test_run_single_rule_creates_dqresult(self):
        rule = self._make_rule('not_null', field=self.text_field)
        before_count = DQResult.objects.count()
        run_single_rule(rule.id)
        self.assertEqual(DQResult.objects.count(), before_count + 1)


class BulkProfileTests(DQBaseTestCase):
    def test_bulk_profile_success(self):
        result = bulk_profile([self.table.id])
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['success'], 1)
        self.assertEqual(result['failed'], 0)

    def test_bulk_profile_missing_table_handled(self):
        result = bulk_profile([99999])
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['failed'], 1)
        self.assertEqual(result['results'][0]['status'], 'error')

    def test_bulk_profile_mixed_results(self):
        result = bulk_profile([self.table.id, 99999])
        self.assertEqual(result['total'], 2)
        self.assertEqual(result['success'], 1)
        self.assertEqual(result['failed'], 1)


# ---------------------------------------------------------------------------
# Performance smoke test: 1000 rows, 3 rules
# ---------------------------------------------------------------------------

class PerformanceTests(DQBaseTestCase):
    def test_1000_rows_completes_under_5_seconds(self):
        DataRow.objects.bulk_create([
            DataRow(data_table=self.table, values={
                'email': f'user{i}@example.com' if i % 10 != 0 else None,
                'score': str(i % 100),
                'status': 'PASS' if i % 3 != 0 else 'INVALID',
            })
            for i in range(1000)
        ])
        rules = [
            self._make_rule('not_null', field=self.text_field),
            self._make_rule('regex', field=self.text_field,
                            params={'pattern': r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'}),
            self._make_rule('reference_integrity', field=self.ref_field,
                            params={'reference_set_id': self.ref_set.id}),
        ]
        start = time.time()
        run_dq(self.table.id)
        elapsed = time.time() - start
        self.assertLess(elapsed, 5.0, f"1000 rows / 3 rules took {elapsed:.2f}s (>5s limit)")
        self.assertEqual(DQResult.objects.count(), 3)
