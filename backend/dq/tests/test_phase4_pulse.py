"""Phase 4 — Pulse suggestions + anomalies + fail-visible results
(TASK-DQ-CORE-P4-PULSE).

Tests:
  * suggest job → pending DQSuggestion rows (valid) / quarantined (invalid)
  * suggest job Pulse-down → job failed, no fabricated suggestions
  * accept → DQRule + RuleFieldAssignment, marks accepted; invalid → auto-reject
  * reject with reason; non-pending accept/reject → 400
  * GET /dq/suggestions/ filters (status, data_table) + auth
  * anomaly job: <6 profiles → done/insufficient_history, Pulse never called
  * anomaly job: stores DQAnomaly rows + dq_anomaly notifications;
    entries missing `observed` are skipped (never fabricated)
  * anomaly job Pulse-down → failed, no anomaly rows
  * GET /dq/anomalies/ filters (table, severity, date)
  * volume_anomaly_pct is actually read into the anomaly payload
  * fail-visible: skipped_unavailable results excluded from score denominators,
    honest status on DQResult, no spurious dq_violation notifications
  * anomaly_detect rules are job-only (never silently passed in run_dq)
  * legacy POST /dq/suggest/ is a thin alias that creates a suggest job
"""
from unittest.mock import patch

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from core.models import Module
from dataschema.models import DataTable, DataField
from mdm.models import OrgUnit
from dq.models import (
    DQRule, RuleFieldAssignment, DQJob, DQResult, DQSuggestion, DQAnomaly,
    DQProfileConfig, TableProfile, FieldProfile,
)
from dq import jobs as jobs_module

User = get_user_model()
BASE = '/carbon-api/dq'


def _create_field_assignment(rule, data_field=None, data_table=None):
    return RuleFieldAssignment.objects.create(
        rule=rule, data_field=data_field,
        data_table=data_table or (data_field.data_table if data_field else None),
    )


def _valid_nl_definition(table_name, field_name=None, name='Emails well-formed'):
    binding = {'table': table_name}
    if field_name:
        binding['field'] = field_name
    return {
        'schema_version': 1,
        'name': name,
        'level': 'field' if field_name else 'business',
        'dimension': 'validity',
        'type': 'nl_check',
        'severity': 'warn',
        'active': True,
        'bindings': [binding],
        'params': {'prompt': 'Email must contain @ and a valid domain'},
    }


def _make_profiles(table, field, count=6):
    """Create `count` TableProfile (+ matching FieldProfile) snapshots."""
    for i in range(count):
        TableProfile.objects.create(
            data_table=table, row_count=100 + i * 10,
            completeness_pct=99.0,
            null_counts={field.name: i}, distinct_counts={field.name: 10},
            min_values={field.name: 'a'}, max_values={field.name: 'z'},
            mean_values={field.name: 5.0 + i},
        )
        FieldProfile.objects.create(
            data_field=field, row_count=100 + i * 10, null_count=i,
            distinct_count=10, completeness_pct=99.0,
            min_value='a', max_value='z', mean_value=5.0 + i,
        )


class P4BaseTestCase(TestCase):
    """Shared fixtures for Phase 4 tests (per-class DB objects)."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username='p4_admin', password='pass', is_staff=True, is_superuser=True)
        cls.org_unit = OrgUnit.objects.create(
            name='P4 Test Org', code='P4TO', org_type='division')
        cls.module = Module.objects.create(name='P4 Module', org_unit=cls.org_unit)
        cls.table = DataTable.objects.create(
            title='P4 Table', name='p4_table', module=cls.module)
        cls.field = DataField.objects.create(
            data_table=cls.table, name='email', label='Email', type='string')
        cls.rule = DQRule.objects.create(
            name='P4 Not Null', rule_type='not_null',
            rule_level='field_validation', is_active=True)
        _create_field_assignment(cls.rule, data_field=cls.field)
        cls.nl_rule = DQRule.objects.create(
            name='P4 NL Check', rule_type='nl_check',
            rule_level='field_validation', is_active=True,
            params={'prompt': 'Email must contain @ and a valid domain'})
        _create_field_assignment(cls.nl_rule, data_field=cls.field)

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.admin)


# ── Suggest job → DQSuggestion persistence ───────────────────────────────

class P4SuggestJobTests(P4BaseTestCase):
    def test_suggest_job_persists_pending_suggestions(self):
        """Submit (pending) → poll (completed) → pending DQSuggestion rows."""
        with patch('ai.intelligence.dispatch_task') as mock_post:
            mock_post.return_value = {
                'task_id': 't-sug-1', 'status': 'pending',
            }
            r = self.client.post(
                f'{BASE}/jobs/',
                {'job_type': 'suggest', 'data_table_id': self.table.id},
                format='json',
            )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data['status'], 'running')
        self.assertEqual(r.data['pulse_task_id'], 't-sug-1')

        # Pulse answers asynchronously with two suggestions:
        #  one with a full valid definition, one without (converted to a
        #  business nl_check definition from prompt).
        with patch('ai.intelligence.get_task') as mock_get:
            mock_get.return_value = {
                'task_id': 't-sug-1', 'status': 'completed',
                'result': {
                    'suggestions': [
                        {
                            'definition': _valid_nl_definition(self.table.name, self.field.name),
                            'rationale': 'Emails should look like emails',
                            'confidence': 0.9,
                        },
                        {
                            'prompt': 'Values must not be null',
                            'suggested_severity': 'error',
                            'rationale': 'Nulls are bad',
                            'confidence': 0.7,
                        },
                    ],
                },
            }
            r2 = self.client.get(f'{BASE}/jobs/{r.data["id"]}/')

        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        self.assertEqual(r2.data['status'], 'done')
        self.assertEqual(r2.data['result']['suggestions_stored'], 2)
        self.assertEqual(r2.data['result']['suggestions_invalid'], 0)

        stored = list(DQSuggestion.objects.filter(data_table=self.table).order_by('id'))
        self.assertEqual(len(stored), 2)
        self.assertTrue(all(s.status == 'pending' for s in stored))
        self.assertEqual(stored[0].payload.get('type'), 'nl_check')
        self.assertEqual(stored[0].confidence, 0.9)
        self.assertIsNotNone(stored[0].job)
        self.assertEqual(stored[0].job.job_type, 'suggest')
        # converted suggestion (no definition) is a business-level nl_check
        self.assertEqual(stored[1].payload.get('level'), 'business')
        self.assertEqual(stored[1].payload['params']['prompt'], 'Values must not be null')

    def test_suggest_job_quarantines_invalid_suggestions(self):
        """Invalid definitions → quarantined in job.result.invalid, no rows."""
        with patch('ai.intelligence.dispatch_task') as mock_post:
            mock_post.return_value = {
                'task_id': 't-sug-2', 'status': 'completed',
                'result': {
                    'suggestions': [
                        # missing name, level, severity, active, bindings, prompt
                        {'definition': {'schema_version': 1, 'type': 'nl_check'}},
                        'not-a-dict',
                    ],
                },
            }
            r = self.client.post(
                f'{BASE}/jobs/',
                {'job_type': 'suggest', 'data_table_id': self.table.id},
                format='json',
            )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data['status'], 'done')
        self.assertEqual(r.data['result']['suggestions_stored'], 0)
        self.assertEqual(r.data['result']['suggestions_invalid'], 2)
        self.assertTrue(r.data['result']['invalid'])
        # nothing fabricated into suggestion rows
        self.assertFalse(DQSuggestion.objects.filter(data_table=self.table).exists())

    def test_suggest_job_pulse_unavailable_fails(self):
        """Pulse unreachable → job failed, no suggestions fabricated."""
        with patch('ai.intelligence.dispatch_task') as mock_post:
            mock_post.return_value = {
                'status': 'pulse_unavailable',
                'error': {'code': 'connection_error', 'message': 'Pulse unreachable: connection refused'},
            }
            r = self.client.post(
                f'{BASE}/jobs/',
                {'job_type': 'suggest', 'data_table_id': self.table.id},
                format='json',
            )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data['status'], 'failed')
        self.assertIn('unreachable', r.data['error'])
        self.assertFalse(DQSuggestion.objects.filter(data_table=self.table).exists())


# ── Suggestion accept/reject API ─────────────────────────────────────────

class P4SuggestionApiTests(P4BaseTestCase):
    def _make_suggestion(self, definition=None, status_='pending'):
        return DQSuggestion.objects.create(
            data_table=self.table,
            payload=definition or _valid_nl_definition(self.table.name, self.field.name),
            rationale='Because emails matter',
            confidence=0.9,
            status=status_,
            created_by=self.admin,
        )

    def test_accept_suggestion_creates_rule_with_assignment(self):
        s = self._make_suggestion()
        r = self.client.post(f'{BASE}/suggestions/{s.id}/accept/')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        rule_id = r.data['id']
        rule = DQRule.objects.get(id=rule_id)
        self.assertEqual(rule.rule_type, 'nl_check')
        self.assertEqual(rule.name, 'Emails well-formed')
        self.assertEqual(rule.created_by, self.admin)
        self.assertEqual(rule.definition, s.payload)
        # assignment bound to table + field
        assn = RuleFieldAssignment.objects.filter(rule=rule).first()
        self.assertIsNotNone(assn)
        self.assertEqual(assn.data_table, self.table)
        self.assertEqual(assn.data_field, self.field)
        # suggestion marked accepted
        s.refresh_from_db()
        self.assertEqual(s.status, 'accepted')

    def test_accept_suggestion_invalid_payload_autorejects(self):
        s = self._make_suggestion(definition={'schema_version': 1, 'type': 'nl_check'})
        r = self.client.post(f'{BASE}/suggestions/{s.id}/accept/')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        s.refresh_from_db()
        self.assertEqual(s.status, 'rejected')
        self.assertIn('Auto-rejected on accept', s.reject_reason)
        self.assertFalse(DQRule.objects.filter(definition=s.payload).exists())

    def test_accept_non_pending_returns_400(self):
        s = self._make_suggestion(status_='accepted')
        r = self.client.post(f'{BASE}/suggestions/{s.id}/accept/')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reject_suggestion_with_reason(self):
        s = self._make_suggestion()
        r = self.client.post(
            f'{BASE}/suggestions/{s.id}/reject/',
            {'reason': 'Duplicate of existing rule'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['status'], 'rejected')
        s.refresh_from_db()
        self.assertEqual(s.status, 'rejected')
        self.assertEqual(s.reject_reason, 'Duplicate of existing rule')

    def test_reject_non_pending_returns_400(self):
        s = self._make_suggestion(status_='rejected')
        r = self.client.post(f'{BASE}/suggestions/{s.id}/reject/', {}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_suggestions_list_filters_by_status_and_table(self):
        self._make_suggestion()
        self._make_suggestion(status_='accepted')
        self._make_suggestion(status_='rejected')

        pending = self.client.get(f'{BASE}/suggestions/?status=pending')
        self.assertEqual(pending.status_code, status.HTTP_200_OK)
        self.assertEqual(len(pending.data), 1)
        self.assertEqual(pending.data[0]['status'], 'pending')

        by_table = self.client.get(f'{BASE}/suggestions/?data_table={self.table.id}')
        self.assertEqual(by_table.status_code, status.HTTP_200_OK)
        self.assertEqual(len(by_table.data), 3)

    def test_suggestions_require_auth(self):
        self.client.force_authenticate(user=None)
        r = self.client.get(f'{BASE}/suggestions/')
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_accept_requires_dq_manage_rules(self):
        """G4 — accept/reject are write actions gated on dq:manage_rules;
        a plain authenticated user without the capability is forbidden."""
        s = self._make_suggestion()
        plain = User.objects.create_user(username='p4_plain', password='pass')
        self.client.force_authenticate(user=plain)
        r = self.client.post(f'{BASE}/suggestions/{s.id}/accept/')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        s.refresh_from_db()
        self.assertEqual(s.status, 'pending')  # no promotion happened

    def test_reject_requires_dq_manage_rules(self):
        """G4 — reject is also a write action; plain user is forbidden."""
        s = self._make_suggestion()
        plain = User.objects.create_user(username='p4_plain2', password='pass')
        self.client.force_authenticate(user=plain)
        r = self.client.post(f'{BASE}/suggestions/{s.id}/reject/',
                             {'reason': 'nope'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        s.refresh_from_db()
        self.assertEqual(s.status, 'pending')  # not rejected


# ── Anomaly job ──────────────────────────────────────────────────────────

class P4AnomalyJobTests(P4BaseTestCase):
    def test_anomaly_job_insufficient_history_done_without_pulse(self):
        """< MIN_ANOMALY_PROFILES profiles → done/insufficient_history,
        Pulse never called (fail-visible: nothing fabricated)."""
        _make_profiles(self.table, self.field, count=2)
        with patch('ai.intelligence.dispatch_task') as mock_post:
            r = self.client.post(
                f'{BASE}/jobs/',
                {'job_type': 'anomaly', 'data_table_id': self.table.id},
                format='json',
            )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data['status'], 'done')
        self.assertEqual(r.data['result']['state'], 'insufficient_history')
        self.assertEqual(r.data['result']['anomalies'], [])
        mock_post.assert_not_called()  # Pulse never contacted
        self.assertFalse(DQAnomaly.objects.filter(data_table=self.table).exists())

    def test_anomaly_job_stores_anomalies(self):
        _make_profiles(self.table, self.field, count=6)
        anomalies = [
            {'metric': 'row_count', 'observed': 120,
             'expected_low': 80, 'expected_high': 100,
             'score': 3.2, 'explanation': 'Row count jumped', 'severity': 'error'},
            {'field': 'email', 'group_key': {'building': 'alamein'},
             'observed': 0.3, 'expected_range': {'low': 0.0, 'high': 0.1},
             'score': 2.1, 'explanation': 'Null pct rose', 'severity': 'warn'},
        ]
        with patch('ai.intelligence.dispatch_task') as mock_post, \
             patch('accounts.models.notify_event') as mock_notify:
            mock_post.return_value = {
                'task_id': 't-anom-1', 'status': 'completed',
                'result': {'anomalies': anomalies},
            }
            r = self.client.post(
                f'{BASE}/jobs/',
                {'job_type': 'anomaly', 'data_table_id': self.table.id},
                format='json',
            )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data['status'], 'done')
        self.assertEqual(r.data['result']['anomalies_stored'], 2)

        rows = list(DQAnomaly.objects.filter(data_table=self.table).order_by('id'))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].metric, 'row_count')
        self.assertEqual(rows[0].observed, 120.0)
        self.assertEqual(rows[0].expected_range, {'low': 80, 'high': 100})
        self.assertEqual(rows[0].score, 3.2)
        self.assertEqual(rows[0].severity, 'error')
        self.assertEqual(rows[0].job.job_type, 'anomaly')
        self.assertEqual(rows[1].metric, 'email')
        self.assertEqual(rows[1].group_key, {'building': 'alamein'})
        # dq_anomaly notification emitted per stored anomaly
        self.assertEqual(mock_notify.call_count, 2)
        event_types = [c.kwargs.get('event_type') or c.args[0] for c in mock_notify.call_args_list]
        self.assertTrue(all(et == 'dq_anomaly' for et in event_types))

    def test_anomaly_job_skips_entries_missing_observed(self):
        _make_profiles(self.table, self.field, count=6)
        anomalies = [
            {'metric': 'row_count', 'observed': 120,
             'expected_range': {'low': 80, 'high': 100},
             'score': 3.0, 'explanation': 'Jump', 'severity': 'warn'},
            {'metric': 'sum(kwh)', 'expected_range': {'low': 1, 'high': 2}},
        ]
        with patch('ai.intelligence.dispatch_task') as mock_post:
            mock_post.return_value = {
                'task_id': 't-anom-2', 'status': 'completed',
                'result': {'anomalies': anomalies},
            }
            r = self.client.post(
                f'{BASE}/jobs/',
                {'job_type': 'anomaly', 'data_table_id': self.table.id},
                format='json',
            )
        self.assertEqual(r.data['result']['anomalies_stored'], 1)
        # the observed-less entry was dropped — no fabricated row
        self.assertEqual(DQAnomaly.objects.filter(data_table=self.table).count(), 1)
        self.assertFalse(
            DQAnomaly.objects.filter(metric='sum(kwh)').exists())

    def test_anomaly_job_pulse_unavailable_fails(self):
        _make_profiles(self.table, self.field, count=6)
        with patch('ai.intelligence.dispatch_task') as mock_post:
            mock_post.return_value = {
                'status': 'pulse_unavailable',
                'error': {'code': 'connection_error', 'message': 'Pulse unreachable: connection refused'},
            }
            r = self.client.post(
                f'{BASE}/jobs/',
                {'job_type': 'anomaly', 'data_table_id': self.table.id},
                format='json',
            )
        self.assertEqual(r.data['status'], 'failed')
        self.assertIn('unreachable', r.data['error'])
        self.assertFalse(DQAnomaly.objects.filter(data_table=self.table).exists())

    def test_anomalies_list_filters(self):
        _make_profiles(self.table, self.field, count=6)
        anomalies = [
            {'metric': 'row_count', 'observed': 120,
             'expected_range': {'low': 80, 'high': 100}, 'severity': 'error'},
            {'metric': 'email_nulls', 'observed': 0.3,
             'expected_range': {'low': 0.0, 'high': 0.1}, 'severity': 'warn'},
        ]
        with patch('ai.intelligence.dispatch_task') as mock_post:
            mock_post.return_value = {
                'task_id': 't-anom-3', 'status': 'completed',
                'result': {'anomalies': anomalies},
            }
            self.client.post(
                f'{BASE}/jobs/',
                {'job_type': 'anomaly', 'data_table_id': self.table.id},
                format='json')

        by_severity = self.client.get(f'{BASE}/anomalies/?severity=error')
        self.assertEqual(by_severity.status_code, status.HTTP_200_OK)
        self.assertEqual(len(by_severity.data), 1)
        self.assertEqual(by_severity.data[0]['severity'], 'error')

        by_table = self.client.get(f'{BASE}/anomalies/?data_table={self.table.id}')
        self.assertEqual(len(by_table.data), 2)

        today = timezone.localdate().isoformat()
        by_date = self.client.get(f'{BASE}/anomalies/?date={today}')
        self.assertEqual(len(by_date.data), 2)


# ── Fail-visible behavior (design decision #1) ───────────────────────────

class P4FailVisibleTests(P4BaseTestCase):
    def test_volume_anomaly_pct_wired_into_payload(self):
        """DQProfileConfig.volume_anomaly_pct is actually read (was inert)."""
        from dq import services
        cfg = DQProfileConfig.objects.first()
        if cfg is None:
            cfg = DQProfileConfig.objects.create()
        cfg.volume_anomaly_pct = 40
        cfg.save()

        _make_profiles(self.table, self.field, count=6)
        payload, err = services.build_anomaly_payload(self.table.id)
        self.assertIsNone(err)
        self.assertEqual(payload['volume_anomaly_pct'], 40)
        self.assertEqual(payload['sensitivity'], 40)
        self.assertEqual(len(payload['history']), 6)
        self.assertIn(self.field.name, payload['fields'])

    def test_metrics_skipped_rules_excluded_from_score(self):
        """GET /dq/metrics/ counts skipped_rules and excludes them from the
        pass-rate denominator."""
        for name, rtype, passed, status_ in [
            ('Passing', 'not_null', True, 'passed'),
            ('Failing', 'not_null', False, 'failed'),
            ('Skipped', 'not_null', None, 'skipped_unavailable'),
        ]:
            rule = DQRule.objects.create(
                name=name, rule_type=rtype,
                rule_level='field_validation', is_active=True)
            _create_field_assignment(rule, data_field=self.field)
            DQResult.objects.create(
                rule=rule, data_field=self.field,
                status=status_, passed=passed,
                checked_count=5, failed_count=0 if passed else 2,
                score=100 if passed else 60,
            )

        r = self.client.get(f'{BASE}/metrics/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        data = r.json()
        self.assertEqual(data['passing_rules'], 1)
        self.assertEqual(data['failing_rules'], 1)
        self.assertEqual(data['skipped_rules'], 1)
        self.assertEqual(data['overall_score'], 50.0)  # 1/2 — skipped excluded

    def test_nl_check_skipped_unavailable_result_status(self):
        """Pulse-down nl_check job → honest DQResult(status='skipped_unavailable',
        passed=None, score=0)."""
        job = jobs_module.create_job(
            'nl_check', rule=self.nl_rule,
            payload={'prompt': 'Email must contain @'}, user=self.admin)
        with patch('ai.intelligence.dispatch_task') as mock_post:
            mock_post.return_value = {
                'status': 'pulse_unavailable',
                'error': {'code': 'not_found', 'message': 'engine offline'},
            }
            jobs_module.execute(job)
        job.refresh_from_db()
        self.assertEqual(job.status, 'failed')
        result = DQResult.objects.filter(rule=self.nl_rule).order_by('-run_at').first()
        self.assertIsNotNone(result)
        self.assertEqual(result.status, 'skipped_unavailable')
        self.assertIsNone(result.passed)
        self.assertEqual(result.score, 0)
        self.assertEqual(result.checked_count, 0)

    def test_skipped_result_does_not_fire_violation_notification(self):
        """passed=None (skipped) is NOT a violation — no dq_violation alert.
        Only a real failure (passed=False) fires one."""
        # dq.apps.ready() already wires dq.signals at startup — the receiver
        # below fires on post_save for every DQResult we create.
        with patch('accounts.models.notify_event') as mock_notify:
            DQResult.objects.create(
                rule=self.rule, data_field=self.field,
                status='failed', passed=False, failed_count=2, score=40)
            DQResult.objects.create(
                rule=self.rule, data_field=self.field,
                status='passed', passed=True, score=100)
            DQResult.objects.create(
                rule=self.rule, data_field=self.field,
                status='skipped_unavailable', passed=None, score=0)

        called_for = [c.kwargs.get('event_type') for c in mock_notify.call_args_list]
        # only the real failure notified
        self.assertEqual(len(called_for), 1)
        self.assertEqual(called_for[0], 'dq_violation')

    def test_anomaly_detect_rule_not_silently_passed_in_run_dq(self):
        """anomaly_detect rules are job-only: run_dq skips them and the engine
        never fabricates a verdict."""
        anomaly_rule = DQRule.objects.create(
            name='Volume anomaly', rule_type='anomaly_detect',
            rule_level='business_rule', is_active=True,
            definition={
                'schema_version': 1,
                'name': 'Volume anomaly',
                'level': 'business',
                'dimension': 'reasonability',
                'type': 'anomaly_detect',
                'severity': 'warn',
                'active': True,
                'bindings': [{'table': self.table.name}],
                'params': {'prompt': 'Detect unusual row-count changes'},
            })
        _create_field_assignment(anomaly_rule, data_field=None, data_table=self.table)

        from dq.services import run_dq
        result = run_dq(self.table.id, user=self.admin)
        # only the plain not_null rule ran; nl_check + anomaly_detect are job-only
        self.assertEqual(result['rules_run'], 1)
        self.assertFalse(DQResult.objects.filter(rule=anomaly_rule).exists())

        # engine: anomaly_detect → skipped sentinel, never (True, ...)
        from dq.engine import evaluate
        passed, checked, failed, failures, score = evaluate(
            anomaly_rule.definition, rows=[], field=None)
        self.assertIsNone(passed)
        self.assertEqual(checked, 0)
        self.assertEqual(score, 0)

    def test_legacy_suggest_alias_creates_job(self):
        """POST /dq/suggest/ is a thin alias: creates+submits a suggest job,
        answers 201 with the job and X-Deprecated: true."""
        with patch('ai.intelligence.dispatch_task') as mock_post:
            mock_post.return_value = {
                'task_id': 't-legacy-1', 'status': 'completed',
                'result': {'suggestions': [
                    {'prompt': 'Never null', 'rationale': 'Nulls are bad',
                     'confidence': 0.8},
                ]},
            }
            r = self.client.post(
                f'{BASE}/suggest/',
                {'data_table_id': self.table.id}, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.headers.get('X-Deprecated'), 'true')
        self.assertEqual(r.data['job_type'], 'suggest')
        self.assertEqual(r.data['status'], 'done')
        # suggestion persisted by the job it created
        self.assertTrue(DQSuggestion.objects.filter(
            data_table=self.table, job_id=r.data['id']).exists())

    def test_legacy_suggest_alias_missing_table_400(self):
        r = self.client.post(f'{BASE}/suggest/', {}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
