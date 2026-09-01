"""Phase 3 — DQ Jobs (TASK-DQ-CORE-P3-JOBS).

Tests:
  * lifecycle transitions for deterministic jobs (rule_run/profile/freshness/schema)
  * Pulse jobs with a mocked gateway (pending→done, unavailable streak→failed)
  * cancel (queued/running → canceled; terminal → 400)
  * POST /dq/jobs/ create+execute; GET /dq/jobs/ filters; GET /dq/jobs/{id}/ refresh
  * POST /dq/rules/{id}/run/ creates the right job type per rule type
  * nl_check absent from run_dq results (job-only)
"""
from unittest.mock import patch

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth.models import Group

from core.models import Module
from dataschema.models import DataTable, DataField, DataRow
from mdm.models import OrgUnit
from dq.models import (
    DQRule, RuleFieldAssignment, DQJob, FreshnessCheck, SchemaSnapshot,
)
from dq import jobs as jobs_module
from accounts.models import ScopedRole

User = get_user_model()
BASE = '/carbon-api/dq'


def _create_field_assignment(rule, data_field=None, data_table=None):
    return RuleFieldAssignment.objects.create(
        rule=rule, data_field=data_field,
        data_table=data_table or (data_field.data_table if data_field else None),
    )


class JobsBaseTestCase(TestCase):
    """Shared fixtures for DQ job tests (per-class DB objects)."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username='job_admin', password='pass', is_staff=True, is_superuser=True)
        cls.org_unit = OrgUnit.objects.create(
            name='Jobs Test Org', code='JBTO', org_type='division')
        cls.module = Module.objects.create(name='Jobs Module', org_unit=cls.org_unit)
        cls.table = DataTable.objects.create(
            title='Jobs Table', name='jobs_table', module=cls.module)
        cls.field = DataField.objects.create(
            data_table=cls.table, name='email', label='Email', type='string')
        DataRow.objects.bulk_create([
            DataRow(data_table=cls.table, values={'email': f'u{i}@x.com'}) for i in range(5)
        ])
        cls.rule = DQRule.objects.create(
            name='Jobs Not Null', rule_type='not_null',
            rule_level='field_validation', is_active=True)
        _create_field_assignment(cls.rule, data_field=cls.field)
        cls.nl_rule = DQRule.objects.create(
            name='Jobs NL Check', rule_type='nl_check',
            rule_level='field_validation', is_active=True,
            params={'prompt': 'Email must contain @ and a valid domain'})
        _create_field_assignment(cls.nl_rule, data_field=cls.field)

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.admin)


# ── Deterministic job lifecycle ──────────────────────────────────────────

class DeterministicJobTests(JobsBaseTestCase):
    def test_rule_run_job_lifecycle_and_counts(self):
        """queued → running → done; result has counts; DQResult rows written."""
        from dq.models import DQResult

        job = jobs_module.create_job('rule_run', rule=self.rule, user=self.admin)
        self.assertEqual(job.status, 'queued')

        jobs_module.execute(job)
        job.refresh_from_db()

        self.assertEqual(job.status, 'done')
        self.assertEqual(job.progress, 100)
        self.assertEqual(job.result['rule_id'], self.rule.id)
        self.assertIn('passed', job.result)
        self.assertIn('failed', job.result)
        self.assertGreater(job.result['fields_checked'], 0)
        # history preserved — DQResult rows written by run_single_rule
        self.assertGreater(DQResult.objects.filter(rule=self.rule).count(), 0)

    def test_rule_run_without_rule_fails(self):
        job = jobs_module.create_job('rule_run', user=self.admin)
        jobs_module.execute(job)
        job.refresh_from_db()
        self.assertEqual(job.status, 'failed')
        self.assertIn('requires a rule', job.error)

    def test_profile_job_done_with_summary(self):
        job = jobs_module.create_job('profile', table=self.table, user=self.admin)
        jobs_module.execute(job)
        job.refresh_from_db()
        self.assertEqual(job.status, 'done')
        self.assertEqual(job.result['table_id'], self.table.id)
        self.assertIn('rows_profiled', job.result)
        self.assertIn('field_profiles', job.result)

    def test_profile_job_survives_duplicate_table_profiles(self):
        """Legacy duplicate TableProfile rows must not break the profile job
        (update_or_create's internal get() raises MultipleObjectsReturned)."""
        from dq.models import TableProfile
        TableProfile.objects.create(data_table=self.table, row_count=1)
        TableProfile.objects.create(data_table=self.table, row_count=2)

        job = jobs_module.create_job('profile', table=self.table, user=self.admin)
        jobs_module.execute(job)
        job.refresh_from_db()
        self.assertEqual(job.status, 'done')
        # duplicates collapsed into a single latest row
        self.assertEqual(
            TableProfile.objects.filter(data_table=self.table).count(), 1)

    def test_freshness_job_creates_freshness_check(self):
        job = jobs_module.create_job('freshness', table=self.table, user=self.admin)
        jobs_module.execute(job)
        job.refresh_from_db()
        self.assertEqual(job.status, 'done')
        self.assertTrue(FreshnessCheck.objects.filter(data_table=self.table).exists())
        self.assertEqual(job.result['total'], 1)

    def test_schema_job_creates_schema_snapshot(self):
        job = jobs_module.create_job('schema', table=self.table, user=self.admin)
        jobs_module.execute(job)
        job.refresh_from_db()
        self.assertEqual(job.status, 'done')
        snap = SchemaSnapshot.objects.filter(data_table=self.table).order_by('-snapshot_at').first()
        self.assertIsNotNone(snap)
        self.assertIn('email', snap.column_schema)

    def test_unknown_job_type_rejected_at_creation(self):
        """create_job validates job_type (API returns 400 before this)."""
        with self.assertRaises(ValueError):
            jobs_module.create_job('bogus', user=self.admin)

    def test_runner_never_raises_on_exception(self):
        """An exception inside a handler → job failed, no exception escapes."""
        job = jobs_module.create_job('rule_run', user=self.admin)
        with patch.object(jobs_module, '_run_rule_job', side_effect=RuntimeError('boom')):
            result = jobs_module.execute(job)  # must not raise
        result.refresh_from_db()
        self.assertEqual(result.status, 'failed')
        self.assertIn('boom', result.error)


# ── Pulse job lifecycle (mocked gateway) ─────────────────────────────────

class PulseJobTests(JobsBaseTestCase):
    def test_nl_check_job_submit_then_poll_to_done(self):
        """submit → running + pulse_task_id; GET /jobs/{id} polls → done."""
        with patch('ai.intelligence.dispatch_task') as mock_post:
            mock_post.return_value = {
                'task_id': 't-111', 'status': 'pending',
            }
            r = self.client.post(
                f'{BASE}/jobs/',
                {'job_type': 'nl_check', 'rule_id': self.nl_rule.id,
                 'payload': {'prompt': 'Email must contain @'}},
                format='json',
            )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data['status'], 'running')
        self.assertEqual(r.data['pulse_task_id'], 't-111')

        with patch('ai.intelligence.get_task') as mock_get:
            mock_get.return_value = {
                'task_id': 't-111', 'status': 'completed',
                'result': {'passed': True, 'checked': 5},
            }
            r2 = self.client.get(f'{BASE}/jobs/{r.data["id"]}/')
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        self.assertEqual(r2.data['status'], 'done')
        self.assertEqual(r2.data['result']['checked'], 5)
        self.assertEqual(r2.data['progress'], 100)

    def test_pulse_pending_stays_running(self):
        job = jobs_module.create_job(
            'nl_check', rule=self.nl_rule,
            payload={'prompt': 'x'}, user=self.admin)
        job.pulse_task_id = 't-222'
        job.status = 'running'
        job.save()

        with patch('ai.intelligence.get_task') as mock_get:
            mock_get.return_value = {
                'task_id': 't-222', 'status': 'working',
            }
            jobs_module.refresh(job)
        job.refresh_from_db()
        self.assertEqual(job.status, 'running')

    def test_pulse_failed_status_fails_job(self):
        job = jobs_module.create_job(
            'nl_check', rule=self.nl_rule,
            payload={'prompt': 'x'}, user=self.admin)
        job.pulse_task_id = 't-333'
        job.status = 'running'
        job.save()

        with patch('ai.intelligence.get_task') as mock_get:
            mock_get.return_value = {
                'task_id': 't-333', 'status': 'failed',
                'error': {'code': 'model_error', 'message': 'LLM broke'},
            }
            jobs_module.refresh(job)
        job.refresh_from_db()
        self.assertEqual(job.status, 'failed')
        self.assertIn('LLM broke', job.error)

    def test_pulse_unavailable_streak_fails_after_limit(self):
        job = jobs_module.create_job(
            'nl_check', rule=self.nl_rule,
            payload={'prompt': 'x'}, user=self.admin)
        job.pulse_task_id = 't-444'
        job.status = 'running'
        job.save()

        with patch('ai.intelligence.get_task') as mock_get:
            mock_get.return_value = {'status': 'pulse_unavailable', 'error': {'code': 'not_found'}}
            # 19 polls: stays running, streak grows
            for _ in range(jobs_module.PULSE_UNAVAILABLE_LIMIT - 1):
                jobs_module.refresh(job)
            job.refresh_from_db()
            self.assertEqual(job.status, 'running')
            self.assertEqual(job.payload.get('unavailable_streak'), jobs_module.PULSE_UNAVAILABLE_LIMIT - 1)
            # 20th poll: failed
            jobs_module.refresh(job)
        job.refresh_from_db()
        self.assertEqual(job.status, 'failed')
        self.assertIn('20 consecutive', job.error)

    def test_suggest_job_submits(self):
        with patch('ai.intelligence.dispatch_task') as mock_post:
            mock_post.return_value = {
                'task_id': 't-555', 'status': 'pending',
            }
            r = self.client.post(
                f'{BASE}/jobs/',
                {'job_type': 'suggest', 'data_table_id': self.table.id},
                format='json',
            )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data['status'], 'running')
        self.assertEqual(r.data['pulse_task_id'], 't-555')

    def test_deterministic_job_refresh_is_noop(self):
        job = jobs_module.create_job('rule_run', rule=self.rule, user=self.admin)
        jobs_module.execute(job)
        job.refresh_from_db()
        before = job.status
        jobs_module.refresh(job)  # must not touch deterministic jobs
        job.refresh_from_db()
        self.assertEqual(job.status, before)

    def test_refresh_active_pulse_jobs_scoped_to_caller(self):
        """Presence-driven refresher advances only the caller's active jobs."""
        other = User.objects.create_user(username='job_other', password='pass')

        mine = jobs_module.create_job(
            'nl_check', rule=self.nl_rule,
            payload={'prompt': 'x'}, user=self.admin)
        mine.pulse_task_id = 't-mine'
        mine.status = 'running'
        mine.save()

        theirs = jobs_module.create_job(
            'nl_check', rule=self.nl_rule,
            payload={'prompt': 'x'}, user=other)
        theirs.pulse_task_id = 't-theirs'
        theirs.status = 'running'
        theirs.save()

        with patch('ai.intelligence.get_task') as mock_get:
            mock_get.return_value = {
                'task_id': 't-mine', 'status': 'completed',
                'result': {'passed': True, 'checked': 3},
            }
            jobs_module.refresh_active_pulse_jobs(self.admin)

        mine.refresh_from_db()
        theirs.refresh_from_db()
        self.assertEqual(mine.status, 'done')
        self.assertEqual(mine.progress, 100)
        self.assertEqual(theirs.status, 'running')  # untouched — not the caller's


# ── Cancel ───────────────────────────────────────────────────────────────

class CancelJobTests(JobsBaseTestCase):
    def test_cancel_queued_job(self):
        job = jobs_module.create_job('rule_run', rule=self.rule, user=self.admin)
        jobs_module.cancel(job)
        job.refresh_from_db()
        self.assertEqual(job.status, 'canceled')

    def test_cancel_running_job_via_api(self):
        job = jobs_module.create_job('rule_run', rule=self.rule, user=self.admin)
        job.status = 'running'
        job.save()
        r = self.client.post(f'{BASE}/jobs/{job.id}/cancel/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['status'], 'canceled')

    def test_cancel_done_job_returns_400(self):
        job = jobs_module.create_job('rule_run', rule=self.rule, user=self.admin)
        jobs_module.execute(job)
        job.refresh_from_db()
        self.assertEqual(job.status, 'done')
        r = self.client.post(f'{BASE}/jobs/{job.id}/cancel/')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)


# ── API surface ──────────────────────────────────────────────────────────

class JobsApiTests(JobsBaseTestCase):
    def test_create_rule_run_job_via_api(self):
        """POST /dq/jobs/ rule_run → 201, done, result non-empty; list filters."""
        r = self.client.post(
            f'{BASE}/jobs/',
            {'job_type': 'rule_run', 'rule_id': self.rule.id},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data['status'], 'done')
        self.assertTrue(r.data['result'])

        listed = self.client.get(f'{BASE}/jobs/?status=done&job_type=rule_run')
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        ids = [j['id'] for j in listed.data]
        self.assertIn(r.data['id'], ids)

    def test_create_job_invalid_job_type_400(self):
        r = self.client.post(
            f'{BASE}/jobs/', {'job_type': 'nope'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rule_run_job_requires_rule_400(self):
        r = self.client.post(
            f'{BASE}/jobs/', {'job_type': 'rule_run'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_gets_401(self):
        self.client.force_authenticate(user=None)
        r = self.client.get(f'{BASE}/jobs/')
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_rules_run_creates_rule_run_job(self):
        r = self.client.post(f'{BASE}/rules/{self.rule.id}/run/')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data['job_type'], 'rule_run')
        self.assertEqual(r.data['status'], 'done')

    def test_rules_run_creates_nl_check_job_for_nl_rule(self):
        with patch('ai.intelligence.dispatch_task') as mock_post:
            mock_post.return_value = {
                'task_id': 't-666', 'status': 'completed',
                'result': {'passed': True},
            }
            r = self.client.post(f'{BASE}/rules/{self.nl_rule.id}/run/')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data['job_type'], 'nl_check')
        self.assertEqual(r.data['status'], 'done')
        self.assertEqual(r.data['pulse_task_id'], 't-666')


# ── nl_check job-only (deliverable 5) ────────────────────────────────────

class NLCheckJobOnlyTests(JobsBaseTestCase):
    def test_run_dq_skips_nl_check_rules(self):
        from dq.services import run_dq

        result = run_dq(self.table.id, user=self.admin)
        summary = result['summary']
        # only the deterministic rule ran — nl_check rule excluded
        self.assertTrue(all(s['rule_id'] != self.nl_rule.id for s in summary))
        self.assertEqual(len(summary), 1)
        self.assertEqual(summary[0]['rule_id'], self.rule.id)

    def test_run_dq_still_evaluates_deterministic_rules(self):
        from dq.services import run_dq

        result = run_dq(self.table.id, user=self.admin)
        self.assertGreater(result['rules_run'], 0)
