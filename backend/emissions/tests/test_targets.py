"""Tests for SBTiTarget model, API, and TargetService."""
from django.urls import reverse
from rest_framework.test import APIClient
from django.test import TestCase
from decimal import Decimal
from django.contrib.auth.models import Group

from accounts.models import User, ScopedRole
from emissions.models import SBTiTarget, Calculation, EmissionFactor, ReportingPeriod
from mdm.models import OrgUnit
from core.models import Module
from dataschema.models import DataTable, DataField, DataRow


class SBTiTargetModelTests(TestCase):
    def test_str_method(self):
        target = SBTiTarget(
            name='Test Target', base_year=2023, target_year=2030,
            target_type='absolute', scope='1+2', reduction_pct=Decimal('50.00')
        )
        s = str(target)
        self.assertIn('Test Target', s)
        self.assertIn('2023', s)
        self.assertIn('50', s)

    def test_default_status_is_draft(self):
        org = OrgUnit.objects.create(name='Test Org', slug='test-org')
        target = SBTiTarget.objects.create(
            org_unit=org, name='T1', base_year=2020, target_year=2030,
            target_type='absolute', scope='1', reduction_pct=Decimal('30.00')
        )
        self.assertEqual(target.status, 'draft')

    def test_ordering_by_base_year_desc(self):
        org = OrgUnit.objects.create(name='Test Org', slug='test-org-2')
        SBTiTarget.objects.create(org_unit=org, name='Old', base_year=2020,
                                   target_year=2030, target_type='absolute',
                                   scope='1', reduction_pct=Decimal('30'))
        SBTiTarget.objects.create(org_unit=org, name='New', base_year=2024,
                                   target_year=2030, target_type='absolute',
                                   scope='1', reduction_pct=Decimal('30'))
        targets = list(SBTiTarget.objects.all())
        self.assertGreaterEqual(targets[0].base_year, targets[1].base_year)


class SBTiTargetAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='targetuser', password='pass')
        self.org_unit = OrgUnit.objects.create(name='Facilities', slug='facilities')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        admins_group, _ = Group.objects.get_or_create(name='admins_group')
        ScopedRole.objects.create(user=self.user, group=admins_group, is_active=True)

    def test_create_target(self):
        resp = self.client.post(reverse('carbon:sbti-target-list'), {
            'org_unit': self.org_unit.id, 'name': '2030 Goal',
            'base_year': 2023, 'target_year': 2030,
            'target_type': 'absolute', 'scope': '1+2',
            'reduction_pct': '50.00', 'status': 'draft',
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data['name'], '2030 Goal')
        self.assertEqual(data['org_unit_name'], 'Facilities')

    def test_list_targets(self):
        SBTiTarget.objects.create(
            org_unit=self.org_unit, name='T1', base_year=2020, target_year=2030,
            target_type='absolute', scope='1', reduction_pct=Decimal('30')
        )
        resp = self.client.get(reverse('carbon:sbti-target-list'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)

    def test_update_target(self):
        target = SBTiTarget.objects.create(
            org_unit=self.org_unit, name='T1', base_year=2020, target_year=2030,
            target_type='absolute', scope='1', reduction_pct=Decimal('30')
        )
        resp = self.client.patch(
            reverse('carbon:sbti-target-detail', args=[target.id]),
            {'status': 'committed'}, format='json'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['status'], 'committed')

    def test_delete_target(self):
        target = SBTiTarget.objects.create(
            org_unit=self.org_unit, name='T1', base_year=2020, target_year=2030,
            target_type='absolute', scope='1', reduction_pct=Decimal('30')
        )
        resp = self.client.delete(reverse('carbon:sbti-target-detail', args=[target.id]))
        self.assertEqual(resp.status_code, 204)
