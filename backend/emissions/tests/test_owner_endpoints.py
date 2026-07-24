from decimal import Decimal

from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import ScopedRole, User
from core.models import Module
from dataschema.models import DataRow, DataTable
from emissions.models import Calculation, EmissionFactor, ReportingPeriod
from mdm.models import OrgUnit


class OwnerApiEndpointsTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='owner', password='pass123')

        self.org_unit = OrgUnit.objects.create(name='Engineering', slug='engineering')
        self.other_org_unit = OrgUnit.objects.create(name='Finance', slug='finance')

        self.module = Module.objects.create(org_unit=self.org_unit, name='Electricity - Main Campus', scope=2)
        self.other_module = Module.objects.create(org_unit=self.other_org_unit, name='Fleet - Main Campus', scope=1)

        self.table = DataTable.objects.create(module=self.module, name='electricity_usage')
        self.other_table = DataTable.objects.create(module=self.other_module, name='fleet_usage')

        self.data_row = DataRow.objects.create(data_table=self.table, values={'kwh': 1000})
        DataRow.objects.create(data_table=self.other_table, values={'liters': 200})

        self.period = ReportingPeriod.objects.create(
            name='FY 2026',
            start_date='2026-01-01',
            end_date='2026-12-31',
            status='open',
        )
        self.factor = EmissionFactor.objects.create(
            code='TEST-EF',
            name='Test Factor',
            scope=2,
            category='electricity',
            factor_value=Decimal('0.5'),
            factor_unit='kg CO2e',
            activity_unit='kWh',
            source='Test',
            valid_from='2026-01-01',
        )

        Calculation.objects.create(
            data_row=self.data_row,
            module=self.module,
            emission_factor=self.factor,
            activity_value=Decimal('1000'),
            activity_unit='kWh',
            co2e_kg=Decimal('500'),
            scope=2,
            category='electricity',
            reporting_period=self.period,
            reporting_year=2026,
            reporting_month=1,
            activity_date='2026-01-15',
        )

        self.group = Group.objects.get_or_create(name='dataowners_group')[0]
        ScopedRole.objects.create(user=self.owner, org_unit=self.org_unit, group=self.group, is_active=True)

        self.client = APIClient()

    def test_summary_endpoint_returns_scoped_summary(self):
        self.client.force_authenticate(self.owner)

        response = self.client.get(reverse('emissions:owner-summary'))

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['org_unit']['id'], self.org_unit.id)
        self.assertEqual(data['summary']['total_modules'], 1)
        self.assertEqual(data['summary']['modules_with_data'], 1)
        self.assertEqual(data['modules'][0]['name'], self.module.name)

    def test_assets_endpoint_returns_emission_sources(self):
        self.client.force_authenticate(self.owner)

        response = self.client.get(reverse('emissions:owner-assets'))

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['name'], self.module.name)
        self.assertEqual(data[0]['scope'], self.module.scope)

    def test_activity_endpoint_returns_recent_emission_activity(self):
        self.client.force_authenticate(self.owner)

        response = self.client.get(reverse('emissions:owner-activity'))

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['module_name'], self.module.name)
        self.assertEqual(data[0]['activity_type'], 'submission')

    def test_carbon_namespace_alias_serves_owner_endpoints(self):
        self.client.force_authenticate(self.owner)

        response = self.client.get('/api/v1/carbon/owner/summary/')

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['org_unit']['id'], self.org_unit.id)
        self.assertEqual(data['summary']['total_modules'], 1)
