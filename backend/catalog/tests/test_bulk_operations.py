from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from catalog.models import AssetProfile, DataDomain
from dataschema.models import DataField, DataTable
from core.models import Module
from mdm.models import ReferenceSet, ReferenceValue

User = get_user_model()


class BulkOperationsTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='bulk-user', password='pass123')
        self.admin = User.objects.create_user(username='bulk-admin', password='pass123')
        self.admin.is_superuser = True
        self.admin.is_staff = True
        self.admin.save()
        self.domain = DataDomain.objects.create(name='Ops Domain', slug='ops-domain')
        self.module = Module.objects.create(name='Ops Module', description='demo')
        self.table = DataTable.objects.create(title='Ops Table', name='ops_table', module=self.module)
        self.field = DataField.objects.create(data_table=self.table, name='status', label='Status', type='string')

    def test_archive_bulk_reports_partial_failures(self):
        profile_1 = AssetProfile.objects.create(data_table=self.table, domain=self.domain)
        profile_2 = AssetProfile.objects.create(data_field=self.field, domain=self.domain)
        self.client.force_authenticate(user=self.admin)
        api_prefix = settings.API_PREFIX.strip('/')

        response = self.client.post(
            f'/{api_prefix}/catalog/assets/archive-bulk/',
            {'ids': [profile_1.id, 999999]},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(profile_1.id, response.data['success'])
        self.assertEqual(response.data['failed'][0]['id'], 999999)
        profile_1.refresh_from_db()
        self.assertFalse(profile_1.is_active)

    def test_reference_value_bulk_create_is_atomic(self):
        ref_set = ReferenceSet.objects.create(name='Value Set', slug='value-set', steward=self.admin)
        self.client.force_authenticate(user=self.admin)
        api_prefix = settings.API_PREFIX.strip('/')

        response = self.client.post(
            f'/{api_prefix}/mdm/reference-values/bulk-create/',
            [{'code': 'A', 'label': 'Alpha'}, {'code': 'A', 'label': 'Duplicate'}],
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ReferenceValue.objects.count(), 0)
