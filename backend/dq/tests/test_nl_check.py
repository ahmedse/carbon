"""Tests for NL Check DQ rule type (Level 2 — Pulse integration, M2M model)."""
from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from core.models import Module
from dataschema.models import DataTable, DataField, DataRow
from mdm.models import OrgUnit
from dq.models import DQRule, DQResult, RuleFieldAssignment

User = get_user_model()


def _create_field_assignment(rule, data_field=None, data_table=None):
    return RuleFieldAssignment.objects.create(
        rule=rule, data_field=data_field,
        data_table=data_table or (data_field.data_table if data_field else None),
    )


class NLBaseTestCase(TestCase):
    """Creates minimal schema objects shared by all NL check tests."""

    def setUp(self):
        self.user = User.objects.create_user(username='nl_tester', password='pass')
        self.org_unit = OrgUnit.objects.create(name='NL Test Org', code='NLTO', org_type='division')
        self.module = Module.objects.create(name='NL Module', org_unit=self.org_unit)
        self.table = DataTable.objects.create(title='NL Table', name='nl_table', module=self.module)
        self.email_field = DataField.objects.create(
            data_table=self.table, name='email', label='Email', type='string')
        self.score_field = DataField.objects.create(
            data_table=self.table, name='score', label='Score', type='number')

    def _make_rows(self, data_list):
        DataRow.objects.bulk_create([DataRow(data_table=self.table, values=d) for d in data_list])
        return list(DataRow.objects.filter(data_table=self.table, is_archived=False))

    def _make_rule(self, **kwargs):
        defaults = {
            'name': 'NL Check Rule',
            'rule_type': 'nl_check',
            'rule_level': 'field_validation',
            'params': {'prompt': 'Email must contain @ and a valid domain'},
            'severity': 'error',
            'is_active': True,
        }
        defaults.update(kwargs)
        rule = DQRule.objects.create(**defaults)
        _create_field_assignment(rule, data_field=self.email_field)
        return rule


# ── Test 1: rule_type exists ──

class NLCheckRuleTypeTests(TestCase):
    def test_nl_check_in_rule_types(self):
        from dq.models import RULE_TYPES
        type_codes = [t[0] for t in RULE_TYPES]
        self.assertIn('nl_check', type_codes)

    def test_client_accepts_nl_check(self):
        user = User.objects.create_user(username='nl_api', password='pass', is_staff=True, is_superuser=True)
        org = OrgUnit.objects.create(name='API Org', code='APIO', org_type='division')
        mod = Module.objects.create(name='API Mod', org_unit=org)
        table = DataTable.objects.create(name='api_table', module=mod)
        field = DataField.objects.create(data_table=table, name='val', label='Value', type='string')
        client = APIClient()
        client.force_authenticate(user)
        resp = client.post('/carbon-api/dq/rules/', {
            'name': 'API NL Rule',
            'rule_level': 'field_validation',
            'rule_type': 'nl_check',
            'params': {'prompt': 'Value must be present'},
            'severity': 'warn',
            'is_active': True,
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()['rule_type'], 'nl_check')


# ── Test 2: requires prompt ──

class NLCheckRequiresPromptTests(NLBaseTestCase):
    def test_missing_prompt_still_validates(self):
        rule = self._make_rule(params={})
        rows = self._make_rows([{'email': 'test@example.com'}])
        from dq.services import _evaluate_rule
        passed, checked, failed, failures, score = _evaluate_rule(rule, rows, field=self.email_field)
        self.assertTrue(passed)
        self.assertEqual(checked, 0)


# ── Test 3: pulse_unavailable → graceful ──

class NLCheckPulseUnavailableTests(NLBaseTestCase):
    @patch('ai.providers._http.requests.post')
    def test_pulse_unreachable_degradation(self, mock_post):
        from requests import ConnectionError as ReqConnError
        mock_post.side_effect = ReqConnError('Connection refused')
        rule = self._make_rule()
        rows = self._make_rows([{'email': 'good@example.com'}, {'email': 'bad'}])
        from dq.services import _evaluate_rule
        # Phase 4 fail-visible (TASK-DQ-CORE-P4-PULSE, design decision #1):
        # Pulse unreachable is NO LONGER a silent auto-pass. Result is
        # SKIPPED_UNAVAILABLE — passed=None, score 0, checked 0.
        passed, checked, failed, failures, score = _evaluate_rule(rule, rows, field=self.email_field)
        self.assertIsNone(passed)
        self.assertEqual(checked, 0)
        self.assertEqual(score, 0)

    @patch('ai.providers._http.requests.post')
    def test_pulse_timeout_degradation(self, mock_post):
        from requests import Timeout
        mock_post.side_effect = Timeout('Request timed out')
        rule = self._make_rule()
        rows = self._make_rows([{'email': 'good@example.com'}, {'email': 'bad'}])
        from dq.services import _evaluate_rule
        # Phase 4 fail-visible: timeout -> skipped (passed=None), score 0.
        passed, checked, failed, failures, score = _evaluate_rule(rule, rows, field=self.email_field)
        self.assertIsNone(passed)
        self.assertEqual(checked, 0)
        self.assertEqual(score, 0)


# ── Test 4: pulse pass ──

class NLCheckPulsePassTests(NLBaseTestCase):
    @patch('ai.providers._http.requests.post')
    def test_pulse_pass(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            'task_id': 'test-task-id', 'status': 'completed',
            'result': {'results': [{'rule_id': '1', 'status': 'pass',
                'details': [{'passed': True}, {'passed': True}], 'confidence': 0.97}]}}
        rule = self._make_rule()
        rows = self._make_rows([{'email': 'a@b.com'}, {'email': 'c@d.com'}])
        from dq.services import _evaluate_rule
        passed, checked, failed, failures, score = _evaluate_rule(rule, rows, field=self.email_field)
        self.assertTrue(passed)
        self.assertEqual(failed, 0)
        self.assertEqual(score, 100)


# ── Test 5: pulse fail ──

class NLCheckPulseFailTests(NLBaseTestCase):
    @patch('ai.providers._http.requests.post')
    def test_pulse_fail(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            'task_id': 'test-task-id', 'status': 'completed',
            'result': {'results': [{'rule_id': '1', 'status': 'fail',
                'details': [
                    {'passed': False, 'explanation': 'Row 0 has invalid email.'},
                    {'passed': True},
                    {'passed': False, 'explanation': 'Row 2 has invalid email.'},
                    {'passed': True},
                ], 'confidence': 0.93}]}}
        rule = self._make_rule()
        rows = self._make_rows([
            {'email': 'bad'}, {'email': 'good@example.com'},
            {'email': 'also-bad'}, {'email': 'fine@test.com'}])
        from dq.services import _evaluate_rule
        passed, checked, failed, failures, score = _evaluate_rule(rule, rows, field=self.email_field)
        self.assertFalse(passed)
        self.assertEqual(failed, 2)
        self.assertEqual(len(failures), 2)
        self.assertEqual(score, 50)


# ── Test 6: pulse error status ──

class NLCheckPulseErrorTests(NLBaseTestCase):
    @patch('ai.providers._http.requests.post')
    def test_pulse_error(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            'task_id': 'test-task-id', 'status': 'completed',
            'result': {'results': [{'rule_id': '1', 'status': 'error',
                'details': [], 'confidence': None}]}}
        rule = self._make_rule()
        rows = self._make_rows([{'email': 'x@y.com'}])
        from dq.services import _evaluate_rule
        # Phase 4 fail-visible: a Pulse 'error' verdict is skipped, not auto-passed.
        passed, checked, failed, failures, score = _evaluate_rule(rule, rows, field=self.email_field)
        self.assertIsNone(passed)
        self.assertEqual(checked, 0)
        self.assertEqual(score, 0)


# ── Test 7: malformed response ──

class NLCheckPulseMalformedTests(NLBaseTestCase):
    @patch('ai.providers._http.requests.post')
    def test_pulse_malformed_no_results(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {'task_id': 'test-task-id', 'status': 'completed', 'result': {}}
        rule = self._make_rule()
        rows = self._make_rows([{'email': 'a@b.com'}])
        from dq.services import _evaluate_rule
        # Phase 4 fail-visible: completed-but-malformed (no results) is skipped.
        passed, checked, failed, failures, score = _evaluate_rule(rule, rows, field=self.email_field)
        self.assertIsNone(passed)
        self.assertEqual(checked, 0)
        self.assertEqual(score, 0)

    @patch('ai.providers._http.requests.post')
    def test_pulse_wrong_status_field(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            'task_id': 'test-task-id', 'status': 'failed',
            'error': {'code': 'model_error', 'message': 'LLM failed'}}
        rule = self._make_rule()
        rows = self._make_rows([{'email': 'a@b.com'}])
        from dq.services import _evaluate_rule
        # Phase 4 fail-visible: a task-level 'failed' status is skipped, not passed.
        passed, checked, failed, failures, score = _evaluate_rule(rule, rows, field=self.email_field)
        self.assertIsNone(passed)
        self.assertEqual(checked, 0)
        self.assertEqual(score, 0)


# ── Test 8: partial result ──

class NLCheckPulsePartialTests(NLBaseTestCase):
    @patch('ai.providers._http.requests.post')
    def test_pulse_partial(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            'task_id': 'test-task-id', 'status': 'partial',
            'result': {'results': [{'rule_id': '1', 'status': 'pass',
                'details': [{'passed': True}], 'confidence': 0.9}]},
            'error': {'code': 'partial_failure', 'message': 'Some rules failed'}}
        rule = self._make_rule()
        rows = self._make_rows([{'email': 'a@b.com'}])
        from dq.services import _evaluate_rule
        # Phase 4 fail-visible: a 'partial' task status carries error context
        # and is skipped, not auto-passed.
        passed, checked, failed, failures, score = _evaluate_rule(rule, rows, field=self.email_field)
        self.assertIsNone(passed)
        self.assertEqual(checked, 0)
        self.assertEqual(score, 0)


# ── Test 9: via run_dq (job-only since TASK-DQ-CORE-P3-JOBS) ──

class NLCheckViaRunDQTests(NLBaseTestCase):
    @patch('ai.providers._http.requests.post')
    def test_nl_check_via_run_dq(self, mock_post):
        """nl_check rules are job-only: run_dq skips them, no DQResult is written.

        Phase 3 (TASK-DQ-CORE-P3-JOBS, deliverable 5) moved nl_check out of
        run_dq — nothing AI runs synchronously in a request. They execute only
        via the `nl_check` DQJob type.
        """
        rule = self._make_rule()
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            'task_id': 'e2e-task', 'status': 'completed',
            'result': {'results': [{'rule_id': str(rule.id), 'status': 'fail',
                'details': [
                    {'passed': True},
                    {'passed': False, 'explanation': 'Row 1 has bad email.'},
                    {'passed': True},
                ], 'confidence': 0.91}]}}
        self._make_rows([
            {'email': 'good@example.com'}, {'email': 'bad-email'}, {'email': 'also-good@test.com'}])
        from dq.services import run_dq
        result = run_dq(self.table.id, user=self.user)
        self.assertIn('table', result)
        # nl_check rule excluded from the run — no DQResult rows for it
        self.assertEqual(result['rules_run'], 0)
        self.assertFalse(DQResult.objects.filter(rule=rule).exists())

        # The nl_check job path still works end-to-end (submit + poll).
        from dq.jobs import create_job, execute, refresh
        job = create_job('nl_check', rule=rule, table=self.table,
                         payload={'prompt': 'Check emails'}, user=self.user)
        execute(job)
        job.refresh_from_db()
        self.assertEqual(job.status, 'done')
        self.assertEqual(job.result['results'][0]['status'], 'fail')
        self.assertTrue(DQResult.objects.filter(rule=rule).exists())
