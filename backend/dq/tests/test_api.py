"""API endpoint tests for DQ execution (M2M decoupled model)."""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth.models import Group

from core.models import Module
from dataschema.models import DataTable, DataField, DataRow
from mdm.models import OrgUnit, ReferenceSet, ReferenceValue
from catalog.models import AssetProfile
from dq.models import DQRule, DQResult, RuleFieldAssignment
from accounts.models import ScopedRole

User = get_user_model()
BASE = '/carbon-api/dq'


def _create_field_assignment(rule, data_field=None, data_table=None):
    return RuleFieldAssignment.objects.create(
        rule=rule, data_field=data_field,
        data_table=data_table or (data_field.data_table if data_field else None),
    )


class APIBaseTestCase(TestCase):
    """Shared fixtures for API tests."""

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username='dq_admin', password='pass', is_staff=True, is_superuser=True)
        self.owner = User.objects.create_user(username='dq_owner', password='pass')
        self.outsider = User.objects.create_user(username='dq_outsider', password='pass')
        self.org_unit = OrgUnit.objects.create(
            name='API Test Org', code='APTO', org_type='division')
        self.module = Module.objects.create(name='API DQ Module', org_unit=self.org_unit)
        self.table = DataTable.objects.create(
            title='API DQ Table', name='api_dq_table', module=self.module)
        self.field = DataField.objects.create(
            data_table=self.table, name='email', label='Email', type='string')
        self.ref_set = ReferenceSet.objects.create(name='API Status')
        ReferenceValue.objects.bulk_create([
            ReferenceValue(reference_set=self.ref_set, code='OK', label='OK', is_active=True),
        ])
        steward_group, _ = Group.objects.get_or_create(name='data_steward')
        ScopedRole.objects.create(
            user=self.owner, org_unit=self.org_unit, group=steward_group, is_active=True)
        DataRow.objects.bulk_create([
            DataRow(data_table=self.table, values={'email': f'u{i}@x.com'}) for i in range(5)
        ])
        self.rule = DQRule.objects.create(
            name='API Not Null', rule_type='not_null', rule_level='field_validation', is_active=True)
        _create_field_assignment(self.rule, data_field=self.field)


# ── POST /dq/profile/ ──

class ProfileEndpointTests(APIBaseTestCase):
    def test_admin_can_profile(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post(f'{BASE}/profile/', {'data_table_id': self.table.id}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn('table_id', r.data)

    def test_owner_can_profile(self):
        self.client.force_authenticate(self.owner)
        r = self.client.post(f'{BASE}/profile/', {'data_table_id': self.table.id}, format='json')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

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


# ── POST /dq/profile/bulk/ ──

class BulkProfileEndpointTests(APIBaseTestCase):
    def test_bulk_profile_success(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post(f'{BASE}/profile/bulk/', {'data_table_ids': [self.table.id]}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_bulk_profile_invalid_body_400(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post(f'{BASE}/profile/bulk/', {'data_table_ids': []}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)


# ── POST /dq/run/ ──

class DQRunEndpointTests(APIBaseTestCase):
    def test_run_by_rule_id(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post(f'{BASE}/run/', {'rule_id': self.rule.id}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_run_by_table_id(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post(f'{BASE}/run/', {'data_table_id': self.table.id}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)

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


# ── GET /dq/results/ ──

class DQResultsListTests(APIBaseTestCase):
    def setUp(self):
        super().setUp()
        for i in range(5):
            DQResult.objects.create(
                rule=self.rule, data_field=self.field,
                passed=(i % 2 == 0), checked_count=10,
                failed_count=5 if i % 2 != 0 else 0,
                score=100 if i % 2 == 0 else 50)

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

    def test_outsider_sees_no_results(self):
        self.client.force_authenticate(self.outsider)
        r = self.client.get(f'{BASE}/results/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(len(r.data) if isinstance(r.data, list) else r.data.get('count', 0), 0)


# ── GET /dq/rules/{id}/history/ ──

class RuleHistoryTests(APIBaseTestCase):
    def setUp(self):
        super().setUp()
        for s in [100, 95, 90, 85, 80, 75]:
            DQResult.objects.create(
                rule=self.rule, data_field=self.field,
                passed=(s >= 90), checked_count=10,
                failed_count=0 if s >= 90 else 1, score=s)

    def test_history_returns_correct_shape(self):
        self.client.force_authenticate(self.admin)
        r = self.client.get(f'{BASE}/rules/{self.rule.id}/history/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn('runs', r.data)
        self.assertIn('trend', r.data)

    def test_history_trend_is_valid(self):
        self.client.force_authenticate(self.admin)
        r = self.client.get(f'{BASE}/rules/{self.rule.id}/history/')
        self.assertIn(r.data['trend'], ['improving', 'degrading', 'stable'])

    def test_history_max_10_runs(self):
        for _ in range(15):
            DQResult.objects.create(
                rule=self.rule, data_field=self.field,
                passed=True, checked_count=10, failed_count=0, score=100)
        self.client.force_authenticate(self.admin)
        r = self.client.get(f'{BASE}/rules/{self.rule.id}/history/')
        self.assertLessEqual(len(r.data['runs']), 10)

    def test_outsider_gets_403_on_history(self):
        self.client.force_authenticate(self.outsider)
        r = self.client.get(f'{BASE}/rules/{self.rule.id}/history/')
        self.assertIn(r.status_code, [403, 404])


# ── GET /dq/results/{id}/failures/ ──

class ResultFailuresTests(APIBaseTestCase):
    def setUp(self):
        super().setUp()
        self.result = DQResult.objects.create(
            rule=self.rule, data_field=self.field, passed=False,
            checked_count=10, failed_count=3, score=70,
            sample_failures=[{'row': 1, 'value': 'bad1'}, {'row': 2, 'value': 'bad2'}])

    def test_failures_returns_correct_shape(self):
        self.client.force_authenticate(self.admin)
        r = self.client.get(f'{BASE}/results/{self.result.id}/failures/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn('failures', r.data)

    def test_failures_outsider_gets_403(self):
        self.client.force_authenticate(self.outsider)
        r = self.client.get(f'{BASE}/results/{self.result.id}/failures/')
        self.assertIn(r.status_code, [403, 404])


# ── POST /dq/rules/{id}/execute/ ──

class RuleExecuteActionTests(APIBaseTestCase):
    def test_admin_can_execute_rule(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post(f'{BASE}/rules/{self.rule.id}/execute/')
        self.assertIn(r.status_code, [200, 201])

    def test_execute_returns_result_fields(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post(f'{BASE}/rules/{self.rule.id}/execute/')
        self.assertIn('passed', r.data)

    def test_outsider_cannot_execute_rule(self):
        self.client.force_authenticate(self.outsider)
        r = self.client.post(f'{BASE}/rules/{self.rule.id}/execute/')
        self.assertIn(r.status_code, [403, 404])


# ── GET /dq/metrics/ ──

class DQMetricsViewTests(APIBaseTestCase):
    def test_admin_can_get_metrics(self):
        self.client.force_authenticate(self.admin)
        r = self.client.get(f'{BASE}/metrics/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_unauthenticated_gets_401(self):
        r = self.client.get(f'{BASE}/metrics/')
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)


# ── POST /dq/run-validation/ ──

class RunDQValidationViewTests(APIBaseTestCase):
    def test_admin_can_run_validation(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post(f'{BASE}/run-validation/', {'data_table': self.table.id}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)

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
