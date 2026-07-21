from django.conf import settings
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APITestCase
from rest_framework import status
from catalog.models import DataDomain
from dataschema.models import DataField, DataTable, DataRow
from core.models import Module
from mdm.models import ReferenceSet, ReferenceValue, OrgUnit
from accounts.models import ScopedRole

User = get_user_model()


class ReferenceGovernanceTests(APITestCase):
    def setUp(self):
        self.user1 = User.objects.create_user('user1', password='pass123')
        self.user2 = User.objects.create_user('user2', password='pass123')
        self.admin = User.objects.create_user('admin', password='pass123')
        self.admin.is_superuser = True
        self.admin.is_staff = True
        self.admin.save()

        self.org_unit = OrgUnit.objects.create(name='Engineering', code='ENG', org_type='college')
        self.domain = DataDomain.objects.create(name='Engineering Domain', id=self.org_unit.id)
        self.group = Group.objects.create(name='admins_group')
        ScopedRole.objects.create(user=self.user1, group=self.group, org_unit=self.org_unit, is_active=True)

    def test_date_filter_returns_valid_values(self):
        ref_set = ReferenceSet.objects.create(name='Status', slug='status', steward=self.user1, domain=self.domain, is_active=True)
        ReferenceValue.objects.create(reference_set=ref_set, code='A', label='Always active', valid_from=None, valid_to=None, is_active=True)
        ReferenceValue.objects.create(reference_set=ref_set, code='B', label='Temporal', valid_from='2025-01-01', valid_to='2025-12-31', is_active=True)
        ReferenceValue.objects.create(reference_set=ref_set, code='C', label='Future', valid_from='2026-01-01', valid_to=None, is_active=True)
        self.client.force_authenticate(user=self.user1)
        api_prefix = settings.API_PREFIX.strip('/')

        response = self.client.get(f'/{api_prefix}/mdm/reference-sets/{ref_set.id}/values/', {'date': '2025-06-15', 'active': 'true'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        codes = {item['code'] for item in response.data}
        self.assertEqual(codes, {'A', 'B'})

        response = self.client.get(f'/{api_prefix}/mdm/reference-sets/{ref_set.id}/values/', {'date': '2026-02-01', 'active': 'true'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        codes = {item['code'] for item in response.data}
        self.assertEqual(codes, {'A', 'C'})

    def test_get_current_values_defaults_to_today(self):
        today = timezone.now().date()
        ref_set = ReferenceSet.objects.create(name='Status 2', slug='status-2', steward=self.user1, domain=self.domain, is_active=True)
        ReferenceValue.objects.create(reference_set=ref_set, code='X', label='Current', valid_from=today, valid_to=None, is_active=True)
        values = ref_set.get_current_values()
        self.assertEqual(list(values.values_list('code', flat=True)), ['X'])

    def test_transition_lifecycle_states(self):
        ref_set = ReferenceSet.objects.create(name='Status 3', slug='status-3', steward=self.user1, domain=self.domain, is_active=True, lifecycle_state=ReferenceSet.LIFECYCLE_DRAFT)
        ref_set.transition_to(ReferenceSet.LIFECYCLE_ACTIVE, user=self.user1)
        self.assertEqual(ref_set.lifecycle_state, ReferenceSet.LIFECYCLE_ACTIVE)
        ref_set.transition_to(ReferenceSet.LIFECYCLE_DEPRECATED, user=self.user1)
        self.assertEqual(ref_set.lifecycle_state, ReferenceSet.LIFECYCLE_DEPRECATED)
        ref_set.transition_to(ReferenceSet.LIFECYCLE_ACTIVE, user=self.user1)
        self.assertEqual(ref_set.lifecycle_state, ReferenceSet.LIFECYCLE_ACTIVE)
        with self.assertRaises(ValueError):
            ref_set.transition_to(ReferenceSet.LIFECYCLE_ARCHIVED, user=self.user1)

    def test_transition_endpoint_validates_and_audits(self):
        ref_set = ReferenceSet.objects.create(name='Status 4', slug='status-4', steward=self.user1, domain=self.domain, is_active=True, lifecycle_state=ReferenceSet.LIFECYCLE_DRAFT)
        self.client.force_authenticate(user=self.user1)
        api_prefix = settings.API_PREFIX.strip('/')

        api_prefix = settings.API_PREFIX.strip('/')
        response = self.client.post(f'/{api_prefix}/mdm/reference-sets/{ref_set.id}/transition/', {'state': ReferenceSet.LIFECYCLE_ACTIVE}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['lifecycle_state'], ReferenceSet.LIFECYCLE_ACTIVE)

        response = self.client.post(f'/{api_prefix}/mdm/reference-sets/{ref_set.id}/transition/', {'state': 'archived'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_archive_bulk_archives_reference_sets(self):
        ref_set_1 = ReferenceSet.objects.create(name='Status 5', slug='status-5', steward=self.user1, domain=self.domain, is_active=True)
        ref_set_2 = ReferenceSet.objects.create(name='Status 6', slug='status-6', steward=self.user1, domain=self.domain, is_active=True)
        self.client.force_authenticate(user=self.admin)
        api_prefix = settings.API_PREFIX.strip('/')

        response = self.client.post(
            f'/{api_prefix}/mdm/reference-sets/archive-bulk/',
            {'ids': [ref_set_1.id, 999999]},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(ref_set_1.id, response.data['success'])
        self.assertEqual(response.data['failed'][0]['id'], 999999)
        ref_set_1.refresh_from_db()
        self.assertFalse(ref_set_1.is_active)
        self.assertEqual(ref_set_1.lifecycle_state, ReferenceSet.LIFECYCLE_ARCHIVED)
        ref_set_2.refresh_from_db()
        self.assertTrue(ref_set_2.is_active)

    def test_bind_field_bulk_and_unbind_safety(self):
        user = self.user1
        module = Module.objects.create(name='Table Module', description='demo')
        table = DataTable.objects.create(title='T', name='t', module=module, created_by=user)
        field = DataField.objects.create(data_table=table, name='status', label='Status', type='reference', created_by=user)
        ref_set = ReferenceSet.objects.create(name='Status Set', slug='status-set', steward=self.user1, domain=self.domain, is_active=True)
        self.client.force_authenticate(user=self.admin)
        api_prefix = settings.API_PREFIX.strip('/')

        api_prefix = settings.API_PREFIX.strip('/')
        response = self.client.post(f'/{api_prefix}/mdm/bind-field/', {'data_field': field.id, 'reference_set': ref_set.id}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        field.refresh_from_db()
        self.assertEqual(field.reference_set_id, ref_set.id)

        # Create a row referencing field values to make unbind unsafe.
        from dataschema.models import DataRow
        DataRow.objects.create(data_table=table, values={'status': 'PASS'})
        response = self.client.post(f'/{api_prefix}/mdm/bind-field/', {'data_field': field.id, 'reference_set': None}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Field unbind rejected', response.data['error'])

        response = self.client.post(f'/{api_prefix}/mdm/bind-field/', {'data_fields': [field.id], 'reference_set': None, 'force': True}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        field.refresh_from_db()
        self.assertIsNone(field.reference_set_id)
