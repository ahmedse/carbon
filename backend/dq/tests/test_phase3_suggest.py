"""
Tests for Phase 3 — AI-suggested DQ rules via Pulse (dq.suggest).

POST /dq/suggest/ is now a THIN ALIAS over the suggest job (Phase 4):
it creates a DQJob and returns 201 + job (X-Deprecated: true).
Covers:
 - Missing param → 400
 - Table not found → 404
 - Auto-profile when no profile exists
 - Pulse unavailable/timeout → job failed honestly (fail-visible)
 - Pulse returns suggestions → pending DQSuggestion rows persisted
 - Pulse returns empty suggestions → done, zero rows
 - Payload matches PULSE_CONTRACT_SPEC.md §3.2
 - Field stats in payload (min/max/mean/stddev)
 - Connection error → job failed honestly
"""
from unittest.mock import patch

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from core.models import Module
from dataschema.models import DataTable, DataField, DataRow
from mdm.models import OrgUnit, ReferenceSet, ReferenceValue
from dq.models import TableProfile, FieldProfile, DQSuggestion, DQJob

User = get_user_model()


# ---------------------------------------------------------------------------
# Shared mixin
# ---------------------------------------------------------------------------

class SuggestBaseTestCase(TestCase):
    """Create minimal schema objects shared by all suggest tests."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='suggest_tester', password='pass',
            is_staff=True, is_superuser=True,
        )
        self.org_unit = OrgUnit.objects.create(
            name='Suggest Test Org', code='STO', org_type='division'
        )
        self.module = Module.objects.create(
            name='Suggest Module', org_unit=self.org_unit
        )
        self.table = DataTable.objects.create(
            title='Suggest Table', name='suggest_table', module=self.module
        )
        self.text_field = DataField.objects.create(
            data_table=self.table, name='email', label='Email', type='string',
        )
        self.num_field = DataField.objects.create(
            data_table=self.table, name='score', label='Score', type='number',
        )

    def _create_profile(self):
        """Create a TableProfile + FieldProfiles to satisfy suggest."""
        tp = TableProfile.objects.create(
            data_table=self.table,
            row_count=100,
            completeness_pct=95.0,
            null_counts={'email': 5, 'score': 3},
            distinct_counts={'email': 90, 'score': 50},
        )
        FieldProfile.objects.create(
            data_field=self.text_field,
            row_count=100, null_count=5, distinct_count=90,
            completeness_pct=95.0, uniqueness_pct=90.0,
        )
        FieldProfile.objects.create(
            data_field=self.num_field,
            row_count=100, null_count=3, distinct_count=50,
            completeness_pct=97.0, uniqueness_pct=50.0,
            min_value='0', max_value='100', mean_value=55.4,
        )
        return tp


# ---------------------------------------------------------------------------
# Test 1: missing param → 400
# ---------------------------------------------------------------------------

class SuggestMissingParamTests(SuggestBaseTestCase):
    """Endpoint requires data_table_id."""

    def test_suggest_endpoint_requires_table_id(self):
        client = APIClient()
        client.force_authenticate(self.user)
        resp = client.post('/carbon-api/dq/suggest/', {}, format='json')
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertIn('error', data)
        self.assertEqual(data['error'], 'data_table_id is required')


# ---------------------------------------------------------------------------
# Test 2: table not found → 404
# ---------------------------------------------------------------------------

class SuggestTableNotFoundTests(SuggestBaseTestCase):
    """Endpoint returns 404 for nonexistent table."""

    def test_suggest_endpoint_table_not_found(self):
        client = APIClient()
        client.force_authenticate(self.user)
        resp = client.post('/carbon-api/dq/suggest/', {
            'data_table_id': 99999,
        }, format='json')
        self.assertEqual(resp.status_code, 404)
        self.assertIn('not found', resp.json()['error'])


# ---------------------------------------------------------------------------
# Test 3: auto-profile when no profile exists
# ---------------------------------------------------------------------------

class SuggestNeedsProfileTests(SuggestBaseTestCase):
    """Thin alias: if no TableProfile exists, one is created; job runs async."""

    @patch('ai.providers._http.requests.post')
    def test_suggest_needs_profile(self, mock_post):
        """Table has data but no profile → auto-profile then suggest job."""
        # Add some data so profiling succeeds
        DataRow.objects.create(data_table=self.table, values={
            'email': 'a@b.com', 'score': 50,
        })

        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            'task_id': 't-1',
            'status': 'completed',
            'result': {
                'suggestions': [],
            },
        }

        client = APIClient()
        client.force_authenticate(self.user)
        resp = client.post('/carbon-api/dq/suggest/', {
            'data_table_id': self.table.id,
        }, format='json')

        # Thin alias: 201 + a job object, marked deprecated
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp['X-Deprecated'], 'true')
        data = resp.json()
        self.assertEqual(data['job_type'], 'suggest')
        self.assertEqual(data['status'], 'done')

        # A profile should now exist (auto-profiled before the job ran)
        self.assertTrue(
            TableProfile.objects.filter(data_table=self.table).exists()
        )
        self.assertEqual(
            DQJob.objects.filter(
                job_type='suggest', data_table=self.table).count(), 1)
        self.assertFalse(DQSuggestion.objects.filter(data_table=self.table).exists())


# ---------------------------------------------------------------------------
# Test 4: pulse unavailable → graceful degradation
# ---------------------------------------------------------------------------

class SuggestPulseUnavailableTests(SuggestBaseTestCase):
    """Pulse timeout → job fails honestly (fail-visible, never fabricated)."""

    @patch('ai.providers._http.requests.post')
    def test_suggest_pulse_unavailable(self, mock_post):
        from requests import Timeout
        mock_post.side_effect = Timeout('Request timed out')

        self._create_profile()

        client = APIClient()
        client.force_authenticate(self.user)
        resp = client.post('/carbon-api/dq/suggest/', {
            'data_table_id': self.table.id,
        }, format='json')

        # Fail-visible: Pulse unreachable → job failed, no suggestion rows.
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data['status'], 'failed')
        self.assertIn('timed out', data['error'])
        self.assertFalse(DQSuggestion.objects.filter(data_table=self.table).exists())

        job = DQJob.objects.filter(
            job_type='suggest', data_table=self.table).first()
        self.assertIsNotNone(job)
        self.assertEqual(job.status, 'failed')


# ---------------------------------------------------------------------------
# Test 5: pulse returns suggestions
# ---------------------------------------------------------------------------

class SuggestReturnsSuggestionsTests(SuggestBaseTestCase):
    """Pulse returns 2 suggestions → persisted as pending DQSuggestion rows."""

    @patch('ai.providers._http.requests.post')
    def test_suggest_pulse_returns_suggestions(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            'task_id': 't-2',
            'status': 'completed',
            'result': {
                'suggestions': [
                    {
                        'prompt': 'Score must be between 0 and 100',
                        'rationale': 'Field ranges from 0 to 100.',
                        'suggested_severity': 'error',
                        'confidence': 0.95,
                    },
                    {
                        'prompt': 'Email must contain @',
                        'rationale': 'Email field appears to hold email addresses.',
                        'suggested_severity': 'warning',
                        'confidence': 0.88,
                    },
                ],
            },
        }

        self._create_profile()

        client = APIClient()
        client.force_authenticate(self.user)
        resp = client.post('/carbon-api/dq/suggest/', {
            'data_table_id': self.table.id,
        }, format='json')

        # Thin alias: 201 + job; suggestions persisted as pending rows.
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data['job_type'], 'suggest')
        self.assertEqual(data['status'], 'done')
        self.assertEqual(data['result']['suggestions_stored'], 2)
        self.assertEqual(data['result']['suggestions_invalid'], 0)

        rows = DQSuggestion.objects.filter(data_table=self.table)
        self.assertEqual(rows.count(), 2)
        self.assertTrue(all(s.status == 'pending' for s in rows))
        score_sug = rows.get(rationale='Field ranges from 0 to 100.')
        self.assertEqual(score_sug.confidence, 0.95)
        self.assertEqual(score_sug.payload['type'], 'nl_check')
        self.assertEqual(score_sug.created_by, self.user)
        self.assertIsNotNone(score_sug.job)
        self.assertFalse(rows.filter(payload__isnull=True).exists())


# ---------------------------------------------------------------------------
# Test 6: pulse returns empty suggestions
# ---------------------------------------------------------------------------

class SuggestEmptySuggestionsTests(SuggestBaseTestCase):
    """Pulse returns [] → job done with zero suggestion rows persisted."""

    @patch('ai.providers._http.requests.post')
    def test_suggest_pulse_empty_suggestions(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            'task_id': 't-3',
            'status': 'completed',
            'result': {
                'suggestions': [],
            },
        }

        self._create_profile()

        client = APIClient()
        client.force_authenticate(self.user)
        resp = client.post('/carbon-api/dq/suggest/', {
            'data_table_id': self.table.id,
        }, format='json')

        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data['status'], 'done')
        # empty suggestion list → nothing stored, no counter added
        self.assertEqual(data['result'], {'suggestions': []})
        self.assertFalse(DQSuggestion.objects.filter(data_table=self.table).exists())


# ---------------------------------------------------------------------------
# Test 7: field stats in payload (min/max/mean/stddev)
# ---------------------------------------------------------------------------

class SuggestFieldStatsTests(SuggestBaseTestCase):
    """Payload includes min/max/mean/stddev for numeric fields."""

    @patch('ai.providers._http.requests.post')
    def test_suggest_field_stats_in_payload(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            'task_id': 't-stats',
            'status': 'completed',
            'result': {'suggestions': []},
        }

        self._create_profile()

        from dq.services import suggest_rules_for_table
        # Patch the AI provider call that's _inside_ suggest_rules_for_table
        # (AI Wave A: suggest now routes via ai.intelligence.CarbonIntelligence).
        with patch('ai.intelligence.CarbonIntelligence.submit_dq_suggest') as mock_suggest:
            mock_suggest.return_value = {
                'task_id': 't-stats',
                'status': 'completed',
                'result': {'suggestions': []},
            }
            suggest_rules_for_table(self.table.id)

            # Check the table_profile passed to the provider
            call_args = mock_suggest.call_args[0]
            table_payload = call_args[0]
            self.assertEqual(table_payload['name'], 'suggest_table')
            self.assertEqual(table_payload['row_count'], 100)

            score_field = next(
                f for f in table_payload['fields'] if f['name'] == 'score'
            )
            self.assertIn('min', score_field)
            self.assertEqual(score_field['min'], '0')
            self.assertIn('max', score_field)
            self.assertEqual(score_field['max'], '100')
            self.assertIn('mean', score_field)
            self.assertEqual(score_field['mean'], 55.4)
            # stddev should have been estimated from range
            self.assertIn('stddev', score_field)


# ---------------------------------------------------------------------------
# Test 9: connection error → graceful degradation
# ---------------------------------------------------------------------------

class SuggestConnectionErrorTests(SuggestBaseTestCase):
    """ConnectionError → job fails honestly (fail-visible, no fabricated data)."""

    @patch('ai.providers._http.requests.post')
    def test_suggest_pulse_connection_error(self, mock_post):
        from requests import ConnectionError as ReqConnError
        mock_post.side_effect = ReqConnError('Connection refused')

        self._create_profile()

        client = APIClient()
        client.force_authenticate(self.user)
        resp = client.post('/carbon-api/dq/suggest/', {
            'data_table_id': self.table.id,
        }, format='json')

        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data['status'], 'failed')
        self.assertIn('unreachable', data['error'])
        self.assertFalse(DQSuggestion.objects.filter(data_table=self.table).exists())
