"""Tests for core emission services: CalculationEngineService, TargetService, DashboardService, OwnerService."""
from django.test import TestCase
from decimal import Decimal

from accounts.models import User
from emissions.models import (
    EmissionFactor, CalculationRule, Calculation, ReportingPeriod, GWP
)
from emissions.services import (
    DashboardService, YearlyComparisonService, ReportService,
    CalculationEngineService, OwnerService, TargetService,
)
from dataschema.models import DataTable, DataField, DataRow
from mdm.models import OrgUnit
from core.models import Module


class CalculationEngineServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='engine', password='pass')
        self.org_unit = OrgUnit.objects.create(name='Eng', slug='eng')
        self.module = Module.objects.create(name='Electricity', scope=2, org_unit=self.org_unit)
        self.table = DataTable.objects.create(module=self.module, name='electricity')
        self.field = DataField.objects.create(
            data_table=self.table, name='kwh', label='kWh', type='number', required=True
        )
        self.factor = EmissionFactor.objects.create(
            code='GRID', name='Grid', category='electricity', scope=2,
            factor_value=Decimal('0.5'), activity_unit='kWh',
            source='EPA', valid_from='2024-01-01'
        )
        self.rule = CalculationRule.objects.create(
            data_table=self.table, activity_field=self.field,
            emission_factor=self.factor, name='Elec→CO2',
            is_active=True, auto_calculate=True
        )
        self.period = ReportingPeriod.objects.create(
            name='FY26', start_date='2026-01-01', end_date='2026-12-31', status='open'
        )

    def test_validate_returns_errors_for_missing_rule_id(self):
        rule, period, errors = CalculationEngineService.validate_calculation_request(None)
        self.assertIn('rule_id', errors)

    def test_validate_returns_rule_not_found(self):
        rule, period, errors = CalculationEngineService.validate_calculation_request(9999)
        self.assertIn('rule_id', errors)

    def test_validate_rejects_inactive_rule(self):
        self.rule.is_active = False
        self.rule.save()
        rule, period, errors = CalculationEngineService.validate_calculation_request(self.rule.id)
        self.assertIn('rule_id', errors)

    def test_validate_rejects_closed_period(self):
        self.period.status = 'closed'
        self.period.save()
        rule, period, errors = CalculationEngineService.validate_calculation_request(
            self.rule.id, period_id=self.period.id
        )
        self.assertIn('reporting_period_id', errors)

    def test_validate_reports_incomplete_rows(self):
        DataRow.objects.create(data_table=self.table, values={})
        DataRow.objects.create(data_table=self.table, values={'kwh': '100'})
        rule, period, errors = CalculationEngineService.validate_calculation_request(
            self.rule.id, period_id=self.period.id
        )
        self.assertIn('incomplete_rows', errors)
        self.assertEqual(len(errors['incomplete_rows']), 1)


class TargetServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='targets', password='pass')
        self.org_unit = OrgUnit.objects.create(name='TargetOrg', slug='target-org')
        from emissions.models import SBTiTarget
        self.target = SBTiTarget.objects.create(
            org_unit=self.org_unit, name='2030 Goal', base_year=2023,
            target_year=2030, target_type='absolute', scope='1+2',
            reduction_pct=Decimal('50.00')
        )

    def test_get_progress_returns_structure(self):
        result = TargetService.get_progress(self.target.id, 2025)
        self.assertEqual(result['target_id'], self.target.id)
        self.assertEqual(result['name'], '2030 Goal')
        self.assertIn('actual_tco2e', result)
        self.assertIn('status', result)


class DashboardServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='dash', password='pass')
        self.superuser = User.objects.create_user(
            username='dashadmin', password='pass', is_superuser=True
        )

    def test_get_dashboard_returns_structure(self):
        # Use superuser to avoid scope restriction issues
        result = DashboardService.get_dashboard_data(self.superuser)
        self.assertIn('total_co2e_tonnes', result)
        self.assertIn('scope_breakdown', result)
        self.assertIn('calculation_count', result)
        self.assertIn('last_updated', result)

    def test_get_dashboard_with_period(self):
        period = ReportingPeriod.objects.create(
            name='FY26', start_date='2026-01-01', end_date='2026-12-31'
        )
        result = DashboardService.get_dashboard_data(self.superuser, period_id=period.id)
        self.assertIn('total_co2e_tonnes', result)
        self.assertEqual(result['total_co2e_tonnes'], 0.0)


class OwnerServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='owner', password='pass')
        self.superuser = User.objects.create_user(
            username='superowner', password='pass', is_superuser=True
        )

    def test_get_org_units_returns_list_for_non_staff(self):
        result = OwnerService.get_org_units(self.user)
        self.assertIsInstance(result, list)

    def test_get_org_units_returns_none_for_superuser(self):
        result = OwnerService.get_org_units(self.superuser)
        self.assertIsNone(result)
