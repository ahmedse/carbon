from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from catalog.models import DataDomain
from core.models import Module
from dataschema.models import DataTable
from mdm.models import OrgUnit, ReferenceSet

User = get_user_model()


class APIErrorHandlingTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='api-user', password='pass123')
        cls.admin = User.objects.create_user(username='api-admin', password='pass123')
        cls.admin.is_superuser = True
        cls.admin.is_staff = True
        cls.admin.save()

    def test_invalid_transition_returns_field_details(self):
        ref_set = ReferenceSet.objects.create(name='Status Set', slug='status-set', steward=self.admin)
        self.client.force_authenticate(user=self.admin)
        api_prefix = settings.API_PREFIX.strip('/')

        response = self.client.post(
            f'/{api_prefix}/mdm/reference-sets/{ref_set.id}/transition/',
            {'state': 'invalid'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('details', response.data)
        self.assertIn('state', response.data['details'])
        self.assertIn('suggested_action', response.data)

    def test_destroy_is_rejected_with_actionable_message(self):
        domain = DataDomain.objects.create(name='Finance Domain', slug='finance-domain')
        self.client.force_authenticate(user=self.admin)
        api_prefix = settings.API_PREFIX.strip('/')

        response = self.client.delete(f'/{api_prefix}/catalog/domains/{domain.id}/')

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertIn('Hard delete not supported', response.data['detail'])

    def test_request_returns_correlation_id_header(self):
        self.client.force_authenticate(user=self.admin)
        api_prefix = settings.API_PREFIX.strip('/')

        response = self.client.get(f'/{api_prefix}/health/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('X-Correlation-ID', response.headers)
        self.assertTrue(response.headers['X-Correlation-ID'])

    def test_dq_rule_destroy_is_rejected_with_405(self):
        from dq.models import DQRule

        org_unit = OrgUnit.objects.create(name='DQ Error Test Org', code='DQET', org_type='division')
        module = Module.objects.create(name='DQ Error Module', org_unit=org_unit)
        table = DataTable.objects.create(title='DQ Error Table', name='dq_error_table', module=module)
        rule = DQRule.objects.create(
            name='Error Test Rule', rule_type='not_null',
            is_active=True, created_by=self.admin,
        )
        from dq.models import RuleFieldAssignment, DQResult
        RuleFieldAssignment.objects.create(rule=rule, data_table=table)
        # Rule with execution history → destroy is rejected
        DQResult.objects.create(rule=rule, passed=True, checked_count=1, failed_count=0, score=100)
        self.client.force_authenticate(user=self.admin)
        api_prefix = settings.API_PREFIX.strip('/')

        response = self.client.delete(f'/{api_prefix}/dq/rules/{rule.id}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['archived'])
