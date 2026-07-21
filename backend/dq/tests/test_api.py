"""
API endpoint tests for DQ execution (A2 / A4 deliverables).

Covers:
 - POST /dq/profile/ — profile a table
 - POST /dq/profile/bulk/ — bulk profile
 - POST /dq/run/ — single rule and table-wide runs
 - GET /dq/results/ — filtering, limit
 - GET /dq/rules/{id}/history/ — trend computation
 - GET /dq/results/{id}/failures/ — failure detail
 - RBAC: non-owner gets 403; no org_unit gets empty set
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth.models import Group

from core.models import Module
from dataschema.models import DataTable, DataField, DataRow
from mdm.models import OrgUnit, ReferenceSet, ReferenceValue
from catalog.models import AssetProfile
from dq.models import DQRule, DQResult
from accounts.models import ScopedRole

User = get_user_model()

BASE = '/carbon-api/dq'


class APIBaseTestCase(TestCase):
    """Shared fixtures for API tests."""

    def setUp(self):
        self.client = APIClient()

        # Admin user (staff/superuser)
        self.admin = User.objects.create_user(
            username='dq_admin', password='pass', is_staff=True, is_superuser=True
        )

        # Owner: user with ScopedRole for the org_unit
        self.owner = User.objects.create_user(username='dq_owner', password='pass')

        # Outsider: no ScopedRole
        self.outsider = User.objects.create_user(username='dq_outsider', password='pass')

        self.org_unit = OrgUnit.objects.create(
            name='API Test Org', code='APTO', org_type='division'
        )
        self.module = Module.objects.create(name='API DQ Module', org_unit=self.org_unit)
        self.table = DataTable.objects.create(
            title='API DQ Table', name='api_dq_table', module=self.module
        )
        self.field = DataField.objects.create(
            data_table=self.table, name='email', label='Email', type='string',
        )
        self.ref_set = ReferenceSet.objects.create(name='API Status')
        ReferenceValue.objects.bulk_create([
            ReferenceValue(reference_set=self.ref_set, code='OK', label='OK', is_active=True),
        ])

        # Grant owner access
        steward_group, _ = Group.objects.get_or_create(name='data_steward')
        ScopedRole.objects.create(
            user=self.owner, org_unit=self.org_unit,
            group=steward_group, is_active=True
        )

        # Seed some rows
        DataRow.objects.bulk_create([
            DataRow(data_table=self.table, values={'email': f'u{i}@x.com'})
            for i in range(5)
        ])

        # Create a rule
        self.rule = DQRule.objects.create(
            name='API Not Null', rule_type='not_null',
            data_field=self.field, is_active=True,
        )


# ---------------------------------------------------------------------------
# POST /dq/profile/ — A2.1
# ---------------------------------------------------------------------------

class ProfileEndpointTests(APIBaseTestCase):
    def test_admin_can_profile(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post(f'{BASE}/profile/', {'data_table_id': self.table.id}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn('table_id', r.data)
        self.assertIn('rows_profiled', r.data)
        self.assertIn('field_profiles', r.data)

    def test_owner_can_profile(self):
        self.client.force_authenticate(self.owner)
        r = self.client.post(f'{BASE}/profile/', {'data_table_id': self.table.id}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_outsider_gets_403(self):
        self.client.force_authenticate(self.outsider)
        r = self.client.post(f'{BASE}/profile/', {'data_table_id': self.table.id}, format='json')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_gets_401(self):
        r = self.client.post(f'{BASE}/profile/', {'data_table_id': self.table.id}, format='json')
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_missing_table_id_gets_400(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post(f'{BASE}/profile/', {}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_nonexistent_table_gets_404(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post(f'{BASE}/profile/', {'data_table_id': 99999}, format='json')
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_legacy_data_table_param_works(self):
        """data_table (legacy) should also be accepted."""
        self.client.force_authenticate(self.admin)
        r = self.client.post(f'{BASE}/profile/', {'data_table': self.table.id}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# POST /dq/profile/bulk/ — A2.3
# ---------------------------------------------------------------------------

class BulkProfileEndpointTests(APIBaseTestCase):
    def test_bulk_profile_success(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post(
            f'{BASE}/profile/bulk/',
            {'data_table_ids': [self.table.id]},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['total'], 1)
        self.assertEqual(r.data['success'], 1)

    def test_bulk_profile_mixed(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post(
            f'{BASE}/profile/bulk/',
            {'data_table_ids': [self.table.id, 99999]},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['total'], 2)
        self.assertEqual(r.data['success'], 1)
        self.assertEqual(r.data['failed'], 1)

    def test_bulk_profile_invalid_body_400(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post(f'{BASE}/profile/bulk/', {'data_table_ids': []}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# POST /dq/run/ — A2.2
# ---------------------------------------------------------------------------

class DQRunEndpointTests(APIBaseTestCase):
    def test_run_by_rule_id(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post(f'{BASE}/run/', {'rule_id': self.rule.id}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn('passed', r.data)
        self.assertIn('score', r.data)

    def test_run_by_table_id(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post(f'{BASE}/run/', {'data_table_id': self.table.id}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn('rules_run', r.data)

    def test_run_outsider_gets_403(self):
        self.client.force_authenticate(self.outsider)
        r = self.client.post(f'{BASE}/run/', {'rule_id': self.rule.id}, format='json')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_run_missing_params_400(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post(f'{BASE}/run/', {}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_run_nonexistent_rule_404(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post(f'{BASE}/run/', {'rule_id': 99999}, format='json')
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_run_updates_asset_profile(self):
        self.client.force_authenticate(self.admin)
        self.client.post(f'{BASE}/run/', {'data_table_id': self.table.id}, format='json')
        ap = AssetProfile.objects.filter(data_table=self.table).first()
        self.assertIsNotNone(ap)
        self.assertIn(ap.quality_status, ['passing', 'warning', 'failing'])


# ---------------------------------------------------------------------------
# GET /dq/results/ — A4.1
# ---------------------------------------------------------------------------

class DQResultsListTests(APIBaseTestCase):
    def setUp(self):
        super().setUp()
        # Create some results
        for i in range(5):
            DQResult.objects.create(
                rule=self.rule,
                passed=(i % 2 == 0),
                checked_count=10,
                failed_count=5 if i % 2 != 0 else 0,
                score=100 if i % 2 == 0 else 50,
            )

    def test_admin_can_list_results(self):
        self.client.force_authenticate(self.admin)
        r = self.client.get(f'{BASE}/results/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_filter_by_rule_id(self):
        self.client.force_authenticate(self.admin)
        r = self.client.get(f'{BASE}/results/?rule_id={self.rule.id}')
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_filter_by_passed_true(self):
        self.client.force_authenticate(self.admin)
        r = self.client.get(f'{BASE}/results/?passed=true')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        for item in r.data:
            self.assertTrue(item['passed'])

    def test_filter_by_passed_false(self):
        self.client.force_authenticate(self.admin)
        r = self.client.get(f'{BASE}/results/?passed=false')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        for item in r.data:
            self.assertFalse(item['passed'])

    def test_outsider_sees_no_results(self):
        self.client.force_authenticate(self.outsider)
        r = self.client.get(f'{BASE}/results/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(len(r.data), 0)

    def test_owner_can_see_results(self):
        self.client.force_authenticate(self.owner)
        r = self.client.get(f'{BASE}/results/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertGreater(len(r.data), 0)


# ---------------------------------------------------------------------------
# GET /dq/rules/{id}/history/ — A4.2
# ---------------------------------------------------------------------------

class RuleHistoryTests(APIBaseTestCase):
    def setUp(self):
        super().setUp()
        # Seed 6 historical results with varying scores
        scores = [100, 95, 90, 85, 80, 75]
        for s in scores:
            DQResult.objects.create(
                rule=self.rule, passed=(s >= 90),
                checked_count=10, failed_count=0 if s >= 90 else 1, score=s,
            )

    def test_history_returns_correct_shape(self):
        self.client.force_authenticate(self.admin)
        r = self.client.get(f'{BASE}/rules/{self.rule.id}/history/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn('rule_id', r.data)
        self.assertIn('runs', r.data)
        self.assertIn('trend', r.data)

    def test_history_trend_is_valid(self):
        self.client.force_authenticate(self.admin)
        r = self.client.get(f'{BASE}/rules/{self.rule.id}/history/')
        self.assertIn(r.data['trend'], ['improving', 'degrading', 'stable'])

    def test_history_max_10_runs(self):
        # Create 15 more results
        for _ in range(15):
            DQResult.objects.create(
                rule=self.rule, passed=True, checked_count=10, failed_count=0, score=100
            )
        self.client.force_authenticate(self.admin)
        r = self.client.get(f'{BASE}/rules/{self.rule.id}/history/')
        self.assertLessEqual(len(r.data['runs']), 10)

    def test_outsider_gets_403_on_history(self):
        # Outsider has no org_unit access → rule not in their queryset → 404 (object not found)
        self.client.force_authenticate(self.outsider)
        r = self.client.get(f'{BASE}/rules/{self.rule.id}/history/')
        self.assertIn(r.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])


# ---------------------------------------------------------------------------
# GET /dq/results/{id}/failures/ — A4.3
# ---------------------------------------------------------------------------

class ResultFailuresTests(APIBaseTestCase):
    def setUp(self):
        super().setUp()
        self.result = DQResult.objects.create(
            rule=self.rule, passed=False,
            checked_count=10, failed_count=3,
            score=70,
            sample_failures=[
                {'row': 1, 'value': 'bad1'},
                {'row': 2, 'value': 'bad2'},
                {'row': 3, 'value': ''},
            ],
        )

    def test_failures_returns_correct_shape(self):
        self.client.force_authenticate(self.admin)
        r = self.client.get(f'{BASE}/results/{self.result.id}/failures/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn('result_id', r.data)
        self.assertIn('failures', r.data)
        self.assertIn('failed_count', r.data)

    def test_failures_contains_field_name(self):
        self.client.force_authenticate(self.admin)
        r = self.client.get(f'{BASE}/results/{self.result.id}/failures/')
        for f in r.data['failures']:
            self.assertEqual(f['field_name'], 'email')

    def test_failures_outsider_gets_403(self):
        # Outsider has no org_unit access → result not in their queryset → 404 (object not found)
        self.client.force_authenticate(self.outsider)
        r = self.client.get(f'{BASE}/results/{self.result.id}/failures/')
        self.assertIn(r.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])


# ---------------------------------------------------------------------------
# POST /dq/rules/{id}/execute/ — DQRuleViewSet @action
# ---------------------------------------------------------------------------

class RuleExecuteActionTests(APIBaseTestCase):
    def test_admin_can_execute_rule(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post(f'{BASE}/rules/{self.rule.id}/execute/')
        # Returns 200 or 201 with result data
        self.assertIn(r.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])

    def test_execute_returns_result_fields(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post(f'{BASE}/rules/{self.rule.id}/execute/')
        self.assertIn(r.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])
        self.assertIn('passed', r.data)

    def test_outsider_cannot_execute_rule(self):
        self.client.force_authenticate(self.outsider)
        r = self.client.post(f'{BASE}/rules/{self.rule.id}/execute/')
        self.assertIn(r.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])


# ---------------------------------------------------------------------------
# GET /dq/metrics/ — DQMetricsView
# ---------------------------------------------------------------------------

class DQMetricsViewTests(APIBaseTestCase):
    def test_admin_can_get_metrics(self):
        self.client.force_authenticate(self.admin)
        r = self.client.get(f'{BASE}/metrics/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn('table_count', r.data)
        self.assertIn('total_rows', r.data)
        self.assertIn('completeness_pct', r.data)

    def test_owner_can_get_metrics(self):
        self.client.force_authenticate(self.owner)
        r = self.client.get(f'{BASE}/metrics/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_unauthenticated_gets_401(self):
        r = self.client.get(f'{BASE}/metrics/')
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)


# ---------------------------------------------------------------------------
# POST /dq/run-validation/ — RunDQValidationView
# ---------------------------------------------------------------------------

class RunDQValidationViewTests(APIBaseTestCase):
    def test_admin_can_run_validation(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post(
            f'{BASE}/run-validation/',
            {'data_table': self.table.id},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn('status', r.data)

    def test_missing_table_returns_400(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post(f'{BASE}/run-validation/', {}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_nonexistent_table_returns_404(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post(f'{BASE}/run-validation/', {'data_table': 99999}, format='json')
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_outsider_gets_403(self):
        self.client.force_authenticate(self.outsider)
        r = self.client.post(f'{BASE}/run-validation/', {'data_table': self.table.id}, format='json')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

