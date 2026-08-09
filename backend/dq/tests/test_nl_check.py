"""
Tests for NL Check DQ rule type (Level 2 — Pulse integration).

Covers:
 - rule_type 'nl_check' exists and is selectable
 - requires prompt param
 - pulse_unavailable graceful degradation
 - pulse pass / fail / error / malformed response
 - Pulse partial result handling
 - Task payload construction
 - End-to-end via run_dq
"""
from unittest.mock import patch

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from core.models import Module
from dataschema.models import DataTable, DataField, DataRow
from mdm.models import OrgUnit
from dq.models import DQRule, DQResult

User = get_user_model()


# ---------------------------------------------------------------------------
# Shared mixin
# ---------------------------------------------------------------------------

class NLBaseTestCase(TestCase):
    """Creates minimal schema objects shared by all NL check tests."""

    def setUp(self):
        self.user = User.objects.create_user(username='nl_tester', password='pass')
        self.org_unit = OrgUnit.objects.create(
            name='NL Test Org', code='NLTO', org_type='division'
        )
        self.module = Module.objects.create(name='NL Module', org_unit=self.org_unit)
        self.table = DataTable.objects.create(
            title='NL Table', name='nl_table', module=self.module
        )
        self.email_field = DataField.objects.create(
            data_table=self.table, name='email', label='Email', type='string',
        )
        self.score_field = DataField.objects.create(
            data_table=self.table, name='score', label='Score', type='number',
        )

    def _make_rows(self, data_list):
        DataRow.objects.bulk_create([
            DataRow(data_table=self.table, values=d) for d in data_list
        ])
        return list(DataRow.objects.filter(data_table=self.table, is_archived=False))

    def _make_rule(self, **kwargs):
        defaults = {
            'name': 'NL Check Rule',
            'rule_type': 'nl_check',
            'scope': 'field',
            'data_field': self.email_field,
            'params': {'prompt': 'Email must contain @ and a valid domain'},
            'severity': 'error',
            'is_active': True,
        }
        defaults.update(kwargs)
        return DQRule.objects.create(**defaults)


# ---------------------------------------------------------------------------
# Test 1: rule_type exists
# ---------------------------------------------------------------------------

class NLCheckRuleTypeTests(TestCase):
    """Test that nl_check is a valid rule type."""

    def test_nl_check_in_rule_types(self):
        """nl_check is listed in RULE_TYPES choices."""
        from dq.models import RULE_TYPES
        type_codes = [t[0] for t in RULE_TYPES]
        self.assertIn('nl_check', type_codes)

    def test_client_accepts_nl_check(self):
        """REST API allows creating nl_check rules."""
        user = User.objects.create_user(username='nl_api', password='pass', is_staff=True, is_superuser=True)
        org = OrgUnit.objects.create(name='API Org', code='APIO', org_type='division')
        mod = Module.objects.create(name='API Mod', org_unit=org)
        table = DataTable.objects.create(name='api_table', module=mod)
        field = DataField.objects.create(
            data_table=table, name='val', label='Value', type='string',
        )

        client = APIClient()
        client.force_authenticate(user)
        resp = client.post('/carbon-api/dq/rules/', {
            'name': 'API NL Rule',
            'scope': 'field',
            'data_field': field.id,
            'rule_type': 'nl_check',
            'params': {'prompt': 'Value must be present'},
            'severity': 'warn',
            'is_active': True,
        }, format='json')

        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()['rule_type'], 'nl_check')


# ---------------------------------------------------------------------------
# Test 2: requires prompt
# ---------------------------------------------------------------------------

class NLCheckRequiresPromptTests(NLBaseTestCase):
    """nl_check must have a prompt param."""

    def test_missing_prompt_still_validates(self):
        """Rule without prompt still saves but validation returns passed."""
        rule = self._make_rule(params={})
        rows = self._make_rows([
            {'email': 'test@example.com'},
        ])
        from dq.services import _evaluate_rule
        passed, checked, failed, failures, score = _evaluate_rule(rule, rows)
        self.assertTrue(passed)
        self.assertEqual(checked, 0)


# ---------------------------------------------------------------------------
# Test 3: pulse_unavailable → graceful degradation
# ---------------------------------------------------------------------------

class NLCheckPulseUnavailableTests(NLBaseTestCase):
    """When Pulse is unreachable, NL check returns passed."""

    @patch('pulse_gateway.requests.post')
    def test_pulse_unreachable_degradation(self, mock_post):
        """ConnectionError → passed, no failures."""
        from requests import ConnectionError as ReqConnError
        mock_post.side_effect = ReqConnError('Connection refused')

        rule = self._make_rule()
        rows = self._make_rows([
            {'email': 'good@example.com'},
            {'email': 'bad'},
        ])

        from dq.services import _evaluate_rule
        passed, checked, failed, failures, score = _evaluate_rule(rule, rows)
        self.assertTrue(passed)
        self.assertEqual(score, 100)

    @patch('pulse_gateway.requests.post')
    def test_pulse_timeout_degradation(self, mock_post):
        """Timeout → passed, no failures."""
        from requests import Timeout
        mock_post.side_effect = Timeout('Request timed out')

        rule = self._make_rule()
        rows = self._make_rows([
            {'email': 'good@example.com'},
            {'email': 'bad'},
        ])

        from dq.services import _evaluate_rule
        passed, checked, failed, failures, score = _evaluate_rule(rule, rows)
        self.assertTrue(passed)
        self.assertEqual(score, 100)


# ---------------------------------------------------------------------------
# Test 4: pulse pass
# ---------------------------------------------------------------------------

class NLCheckPulsePassTests(NLBaseTestCase):
    """When Pulse returns pass, NL check passes."""

    @patch('pulse_gateway.requests.post')
    def test_pulse_pass(self, mock_post):
        """200 OK, status=completed, result pass → passed=True."""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            'task_id': 'test-task-id',
            'status': 'completed',
            'result': {
                'results': [{
                    'rule_id': '1',
                    'status': 'pass',
                    'failing_rows': [],
                    'explanation': 'All emails are valid.',
                    'confidence': 0.97,
                }],
            },
        }

        rule = self._make_rule()
        rows = self._make_rows([
            {'email': 'a@b.com'},
            {'email': 'c@d.com'},
        ])

        from dq.services import _evaluate_rule
        passed, checked, failed, failures, score = _evaluate_rule(rule, rows)
        self.assertTrue(passed)
        self.assertEqual(failed, 0)
        self.assertEqual(score, 100)


# ---------------------------------------------------------------------------
# Test 5: pulse fail
# ---------------------------------------------------------------------------

class NLCheckPulseFailTests(NLBaseTestCase):
    """When Pulse returns fail, NL check fails with details."""

    @patch('pulse_gateway.requests.post')
    def test_pulse_fail(self, mock_post):
        """200 OK, status=completed, result fail → passed=False."""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            'task_id': 'test-task-id',
            'status': 'completed',
            'result': {
                'results': [{
                    'rule_id': '1',
                    'status': 'fail',
                    'failing_rows': [0, 2],
                    'explanation': 'Rows 0 and 2 have invalid emails.',
                    'confidence': 0.93,
                }],
            },
        }

        rule = self._make_rule()
        rows = self._make_rows([
            {'email': 'bad'},
            {'email': 'good@example.com'},
            {'email': 'also-bad'},
            {'email': 'fine@test.com'},
        ])

        from dq.services import _evaluate_rule
        passed, checked, failed, failures, score = _evaluate_rule(rule, rows)
        self.assertFalse(passed)
        self.assertEqual(failed, 2)
        self.assertEqual(len(failures), 2)
        self.assertEqual(score, 50)


# ---------------------------------------------------------------------------
# Test 6: pulse error status
# ---------------------------------------------------------------------------

class NLCheckPulseErrorTests(NLBaseTestCase):
    """When Pulse returns error, NL check degrades to passed."""

    @patch('pulse_gateway.requests.post')
    def test_pulse_error(self, mock_post):
        """status=error → passed=True (graceful)."""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            'task_id': 'test-task-id',
            'status': 'completed',
            'result': {
                'results': [{
                    'rule_id': '1',
                    'status': 'error',
                    'failing_rows': None,
                    'explanation': 'Insufficient data for evaluation.',
                    'confidence': None,
                }],
            },
        }

        rule = self._make_rule()
        rows = self._make_rows([{'email': 'x@y.com'}])

        from dq.services import _evaluate_rule
        passed, checked, failed, failures, score = _evaluate_rule(rule, rows)
        self.assertTrue(passed)


# ---------------------------------------------------------------------------
# Test 7: pulse malformed response
# ---------------------------------------------------------------------------

class NLCheckPulseMalformedTests(NLBaseTestCase):
    """When Pulse returns malformed/invalid JSON, NL check degrades gracefully."""

    @patch('pulse_gateway.requests.post')
    def test_pulse_malformed_no_results(self, mock_post):
        """Response missing 'results' key → passed=True."""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            'task_id': 'test-task-id',
            'status': 'completed',
            'result': {},
        }

        rule = self._make_rule()
        rows = self._make_rows([{'email': 'a@b.com'}])

        from dq.services import _evaluate_rule
        passed, checked, failed, failures, score = _evaluate_rule(rule, rows)
        self.assertTrue(passed)

    @patch('pulse_gateway.requests.post')
    def test_pulse_wrong_status_field(self, mock_post):
        """Response with unexpected top-level status → passed=True."""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            'task_id': 'test-task-id',
            'status': 'failed',
            'error': {'code': 'model_error', 'message': 'LLM failed'},
        }

        rule = self._make_rule()
        rows = self._make_rows([{'email': 'a@b.com'}])

        from dq.services import _evaluate_rule
        passed, checked, failed, failures, score = _evaluate_rule(rule, rows)
        self.assertTrue(passed)


# ---------------------------------------------------------------------------
# Test 8: pulse partial result
# ---------------------------------------------------------------------------

class NLCheckPulsePartialTests(NLBaseTestCase):
    """Can handle Pulse partial completion gracefully."""

    @patch('pulse_gateway.requests.post')
    def test_pulse_partial(self, mock_post):
        """status=partial with mixed results."""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            'task_id': 'test-task-id',
            'status': 'partial',
            'result': {
                'results': [{
                    'rule_id': '1',
                    'status': 'pass',
                    'failing_rows': [],
                    'explanation': 'OK.',
                    'confidence': 0.9,
                }],
            },
            'error': {
                'code': 'partial_failure',
                'message': 'Some rules failed',
            },
        }

        rule = self._make_rule()
        rows = self._make_rows([{'email': 'a@b.com'}])

        from dq.services import _evaluate_rule
        passed, checked, failed, failures, score = _evaluate_rule(rule, rows)
        # partial → still degrades gracefully
        self.assertTrue(passed)


# ---------------------------------------------------------------------------
# Test 9: task payload construction
# ---------------------------------------------------------------------------

class NLCheckPayloadTests(TestCase):
    """Test that payload matches PULSE_CONTRACT_SPEC.md §3.1."""

    def test_payload_construction(self):
        """_build_dq_validate_payload produces correct envelope."""
        from pulse_gateway import PulseGateway
        g = PulseGateway()
        rules = [{
            'id': 'r-1',
            'prompt': 'Check emails',
            'fields': ['email'],
            'severity': 'warn',
        }]
        rows = [{'email': 'a@b.com'}]
        context = {'table_name': 'test', 'row_count_hint': 1}

        payload = g._build_dq_validate_payload('t-1', rules, rows, context)

        # Envelope
        self.assertIn('auth', payload)
        self.assertIn('task', payload)
        self.assertEqual(payload['auth']['instance_id'], 'carbon')

        # Task
        task = payload['task']
        self.assertEqual(task['id'], 't-1')
        self.assertEqual(task['type'], 'dq.validate')

        # Task payload
        task_payload = task['payload']
        self.assertIn('rules', task_payload)
        self.assertIn('rows', task_payload)
        self.assertIn('context', task_payload)
        self.assertEqual(task_payload['rules'][0]['prompt'], 'Check emails')
        self.assertEqual(task_payload['rows'][0]['email'], 'a@b.com')
        self.assertIn('meta', task)


# ---------------------------------------------------------------------------
# Test 10: via run_dq (end-to-end)
# ---------------------------------------------------------------------------

class NLCheckViaRunDQTests(NLBaseTestCase):
    """End-to-end: NL check rule exercised through run_dq."""

    @patch('pulse_gateway.requests.post')
    def test_nl_check_via_run_dq(self, mock_post):
        """run_dq calls Pulse for nl_check rules."""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            'task_id': 'e2e-task',
            'status': 'completed',
            'result': {
                'results': [{
                    'rule_id': str(self._make_rule().id),
                    'status': 'fail',
                    'failing_rows': [1],
                    'explanation': 'Row 1 has bad email.',
                    'confidence': 0.91,
                }],
            },
        }

        rule = self._make_rule()
        self._make_rows([
            {'email': 'good@example.com'},
            {'email': 'bad-email'},
            {'email': 'also-good@test.com'},
        ])

        from dq.services import run_dq
        result = run_dq(self.table.id, user=self.user)

        self.assertIn('table', result)
        self.assertGreaterEqual(result['rules_run'], 1)
        # A DQResult should have been created
        self.assertTrue(DQResult.objects.filter(rule=rule).exists())
        dq_result = DQResult.objects.get(rule=rule)
        self.assertFalse(dq_result.passed)
        self.assertEqual(dq_result.failed_count, 1)
