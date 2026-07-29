from django.test import TestCase
from rest_framework.test import APIClient, APITestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from emissions.models import (
    CalculationRule, ReportingPeriod, SBTiTarget, EmissionFactor,
)
from dataschema.models import DataTable, DataField
from core.models import Module
from mdm.models import OrgUnit

User = get_user_model()


class RBACHardeningTests(APITestCase):
    def setUp(self):
        self.client = APIClient()

        # Create org and module for test data
        self.org = OrgUnit.objects.create(name='RBAC Test Org', slug='rbac-test-org')
        self.module = Module.objects.create(name='RBAC Test Mod', scope=1, org_unit=self.org)

        # Create admin (superuser) and dataowner (regular user)
        self.admin = User.objects.create_superuser(
            username='rbac_admin', password='AdminPa_123'
        )
        self.dataowner = User.objects.create_user(
            username='rbac_owner', password='Owner_123'
        )

        # Create supporting objects
        self.table = DataTable.objects.create(
            module=self.module, name='rbac_test_table'
        )
        self.field = DataField.objects.create(
            data_table=self.table, name='fuel_l', label='Fuel L',
            type='number', required=True
        )
        self.factor = EmissionFactor.objects.create(
            code='RBAC_DIESEL', name='RBAC Diesel', category='fuel',
            scope=1, factor_value=2.68, activity_unit='litres',
            source='DEFRA', valid_from='2024-01-01'
        )
        self.rule = CalculationRule.objects.create(
            name='RBAC Test Rule', data_table=self.table,
            activity_field=self.field, emission_factor=self.factor,
            rule_type='direct', is_active=True,
        )
        self.period = ReportingPeriod.objects.create(
            name='RBAC FY26', start_date='2026-01-01',
            end_date='2026-12-31', status='open',
        )
        self.target = SBTiTarget.objects.create(
            org_unit=self.org, name='RBAC Target',
            base_year=2023, target_year=2030,
            target_type='absolute', scope='1+2',
            reduction_pct=30, status='draft',
        )

    def test_dataowner_cannot_create_rule(self):
        self.client.force_authenticate(user=self.dataowner)
        resp = self.client.post(reverse('emissions:calculation-rule-list'), {
            'name': 'test', 'data_table': self.table.pk,
            'activity_field': self.field.pk, 'rule_type': 'direct',
        }, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_dataowner_cannot_trigger_calculate(self):
        self.client.force_authenticate(user=self.dataowner)
        resp = self.client.post(reverse('emissions:calculate'), {
            'rule_id': self.rule.pk,
        }, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_admin_can_still_access_rules(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(reverse('emissions:calculation-rule-list'))
        self.assertEqual(resp.status_code, 200)
