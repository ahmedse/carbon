from django.urls import reverse
from rest_framework.test import APIClient
from django.test import TestCase
from django.contrib.auth.models import Group
from decimal import Decimal

from accounts.models import User, ScopedRole
from emissions.models import EmissionFactor, CalculationRule, ReportingPeriod
from dataschema.models import DataTable, DataField, DataRow
from mdm.models import OrgUnit
from core.models import Module


class CalculationValidationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='calcuser', password='pass123')
        self.org_unit = OrgUnit.objects.create(name='Engineering', slug='engineering')
        self.module = Module.objects.create(name='Electricity Source', scope=2, org_unit=self.org_unit)
        self.table = DataTable.objects.create(module=self.module, name='electricity_usage')
        self.field = DataField.objects.create(data_table=self.table, name='kwh', label='kWh', type='number', required=True)
        self.period = ReportingPeriod.objects.create(
            name='FY 2026',
            start_date='2026-01-01',
            end_date='2026-12-31',
            status='open',
        )
        self.factor = EmissionFactor.objects.create(
            code='GRID_ELECTRICITY',
            name='Grid Electricity',
            category='electricity',
            scope=2,
            factor_value=Decimal('0.417'),
            activity_unit='kWh',
            source='EPA 2024',
            valid_from='2024-01-01',
        )
        self.rule = CalculationRule.objects.create(
            data_table=self.table,
            activity_field=self.field,
            emission_factor=self.factor,
            name='Electricity → CO2e',
            is_active=True,
            auto_calculate=True,
        )
        Group.objects.get_or_create(name='admins_group')
        ScopedRole.objects.create(user=self.user, group=Group.objects.get(name='admins_group'), is_active=True)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_calculate_returns_400_when_rule_missing(self):
        response = self.client.post(reverse('emissions:calculate'), {})
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json())

    def test_calculate_returns_422_when_period_closed(self):
        self.period.status = 'closed'
        self.period.save()

        response = self.client.post(reverse('emissions:calculate'), {
            'rule_id': self.rule.id,
            'reporting_period_id': self.period.id,
        })

        self.assertEqual(response.status_code, 422)
        self.assertIn('error', response.json())

    def test_calculate_returns_422_when_incomplete_activity_data(self):
        DataRow.objects.create(data_table=self.table, values={})

        response = self.client.post(reverse('emissions:calculate'), {
            'rule_id': self.rule.id,
            'reporting_period_id': self.period.id,
        })

        self.assertEqual(response.status_code, 422)
        self.assertIn('error', response.json())
