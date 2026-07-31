"""Tests for core emission services: all 9 service classes."""
from django.test import TestCase
from decimal import Decimal

from accounts.models import User
from emissions.models import (
    EmissionFactor, CalculationRule, Calculation, ReportingPeriod,
    GWP, ReportConfig, SBTiTarget,
)
from emissions.services import (
    DashboardService, YearlyComparisonService, ReportService,
    CalculationEngineService, OwnerService, TargetService,
    MyDataService, ConsoleService, ReportConfigService,
)
from dataschema.models import DataTable, DataField, DataRow
from mdm.models import OrgUnit
from core.models import Module
from catalog.models import AssetProfile


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


# ── YearlyComparisonService ─────────────────────────────────────────────────

class YearlyComparisonServiceTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_user(
            username='ycadmin', password='pass', is_superuser=True
        )

    def test_comparison_returns_structure(self):
        result = YearlyComparisonService.get_comparison(self.superuser, [2024, 2025])
        self.assertIn('baseline_year', result)
        self.assertIn('yearly_comparison', result)
        self.assertIn('targets', result)

    def test_empty_years_returns_structure(self):
        result = YearlyComparisonService.get_comparison(self.superuser, [])
        self.assertIn('baseline_year', result)
        self.assertEqual(result['current_year'], None)

    def test_baseline_year_from_period(self):
        ReportingPeriod.objects.create(
            name='Baseline FY20', start_date='2020-01-01', end_date='2020-12-31',
            is_baseline=True
        )
        result = YearlyComparisonService.get_comparison(self.superuser, [2020])
        self.assertEqual(result['baseline_year'], 2020)


# ── ReportService ───────────────────────────────────────────────────────────

class ReportServiceTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_user(
            username='rptadmin', password='pass', is_superuser=True
        )
        self.org_unit = OrgUnit.objects.create(name='RptOrg', slug='rpt-org')
        self.module = Module.objects.create(
            name='RptModule', scope=1, org_unit=self.org_unit
        )
        self.table = DataTable.objects.create(module=self.module, name='rpt_table')
        self.field = DataField.objects.create(
            data_table=self.table, name='litres', label='Litres', type='number', required=True
        )
        self.factor = EmissionFactor.objects.create(
            code='FUEL', name='Diesel', category='transport', scope=1,
            factor_value=Decimal('2.68'), activity_unit='litres',
            source='DEFRA', valid_from='2024-01-01'
        )
        self.period = ReportingPeriod.objects.create(
            name='FY26', start_date='2026-01-01', end_date='2026-12-31', status='open'
        )

    def test_report_returns_structure(self):
        result = ReportService.generate_report(self.superuser)
        self.assertIn('title', result)
        self.assertIn('summary', result)
        self.assertIn('scope_details', result)
        self.assertIn('format', result)

    def test_report_with_period(self):
        result = ReportService.generate_report(self.superuser, period_id=self.period.id)
        self.assertEqual(result['title'], 'Carbon Emissions Report - FY26')

    def test_report_with_org_unit(self):
        result = ReportService.generate_report(
            self.superuser, org_unit_id=self.org_unit.id
        )
        self.assertIn('title', result)

    def test_empty_report_returns_valid_structure(self):
        result = ReportService.generate_report(self.superuser)
        self.assertEqual(result['summary']['total_emissions_tonnes'], 0.0)
        self.assertEqual(len(result['rows']), 0)


# ── CalculationEngineService Extended ───────────────────────────────────────

class CalculationEngineServiceExtendedTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_user(
            username='calcadmin', password='pass', is_superuser=True
        )
        self.org_unit = OrgUnit.objects.create(name='CalcOrg', slug='calc-org')
        self.module = Module.objects.create(
            name='CalcModule', scope=2, org_unit=self.org_unit
        )
        self.table = DataTable.objects.create(module=self.module, name='calc_table')
        self.field = DataField.objects.create(
            data_table=self.table, name='kwh', label='kWh', type='number', required=True
        )
        self.factor = EmissionFactor.objects.create(
            code='SOLAR', name='Solar', category='electricity', scope=2,
            factor_value=Decimal('0.02'), activity_unit='kWh',
            source='EPA', valid_from='2024-01-01'
        )
        self.period = ReportingPeriod.objects.create(
            name='FY26', start_date='2026-01-01', end_date='2026-12-31', status='open'
        )

    def test_batch_calculate_active_rules(self):
        rule = CalculationRule.objects.create(
            data_table=self.table, activity_field=self.field,
            emission_factor=self.factor, name='Solar→CO2',
            is_active=True, auto_calculate=True
        )
        DataRow.objects.create(data_table=self.table, values={'kwh': '1000'})
        result = CalculationEngineService.batch_calculate(
            [self.table.id], self.period.id, user=self.superuser
        )
        self.assertIn('total_created', result)
        self.assertIn('per_table', result)
        self.assertIn(str(self.table.id), result['per_table'])

    def test_batch_calculate_empty_table_ids(self):
        result = CalculationEngineService.batch_calculate([], self.period.id)
        self.assertEqual(result['total_created'], 0)


# ── OwnerService Extended ───────────────────────────────────────────────────

class OwnerServiceExtendedTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='ownsrv', password='pass')
        self.superuser = User.objects.create_user(
            username='ownsrvadmin', password='pass', is_superuser=True
        )
        self.org_unit = OrgUnit.objects.create(name='OwnerOrg', slug='owner-org')
        self.module = Module.objects.create(
            name='OwnerModule', scope=1, org_unit=self.org_unit
        )
        self.table = DataTable.objects.create(module=self.module, name='owner_table')

    def test_get_owner_dashboard_returns_structure(self):
        result = OwnerService.get_owner_dashboard(self.superuser)
        self.assertIn('total_co2e_tonnes', result)
        self.assertIn('scope_breakdown', result)
        self.assertIn('data_quality_summary', result)

    def test_get_owner_summary_returns_structure(self):
        result = OwnerService.get_owner_summary(self.superuser)
        self.assertIn('summary', result)
        self.assertIn('total_modules', result['summary'])
        self.assertIn('org_unit', result)

    def test_get_owner_assets_returns_list(self):
        result = OwnerService.get_owner_assets(self.superuser)
        self.assertIsInstance(result, list)


# ── MyDataService ───────────────────────────────────────────────────────────

class MyDataServiceTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_user(
            username='mydataadmin', password='pass', is_superuser=True
        )
        self.org_unit = OrgUnit.objects.create(name='MyDataOrg', slug='mydata-org')
        self.module = Module.objects.create(
            name='MyDataModule', scope=1, org_unit=self.org_unit
        )
        self.table = DataTable.objects.create(module=self.module, name='mydata_table')

    def test_get_my_data_returns_structure(self):
        result = MyDataService.get_my_data(self.superuser)
        self.assertIn('org_unit', result)
        self.assertIn('stats', result)
        self.assertIn('modules', result)
        self.assertIn('recent_activity', result)

    def test_get_my_data_stats_total_rows(self):
        DataRow.objects.create(data_table=self.table, values={'val': '1'})
        result = MyDataService.get_my_data(self.superuser)
        self.assertEqual(result['stats']['total_rows'], 1)

    def test_get_my_data_quality_status(self):
        AssetProfile.objects.create(
            data_table=self.table, quality_status='passing', quality_score=100
        )
        result = MyDataService.get_my_data(self.superuser)
        self.assertEqual(result['stats']['data_quality']['passing'], 1)


# ── ConsoleService ──────────────────────────────────────────────────────────

class ConsoleServiceTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_user(
            username='consoleadmin', password='pass', is_superuser=True
        )

    def test_console_returns_structure(self):
        result = ConsoleService.get_console_data(self.superuser)
        self.assertIn('active_period', result)
        self.assertIn('stats', result)
        self.assertIn('alerts', result)
        self.assertIn('recent_activity', result)

    def test_console_no_active_period_graceful(self):
        result = ConsoleService.get_console_data(self.superuser)
        self.assertIsNone(result['active_period'])

    def test_console_with_period_returns_days_remaining(self):
        ReportingPeriod.objects.create(
            name='FY26', start_date='2026-01-01', end_date='2026-12-31', status='open'
        )
        result = ConsoleService.get_console_data(self.superuser)
        self.assertIsNotNone(result['active_period'])
        self.assertIn('days_remaining', result['active_period'])


# ── ReportConfigService ─────────────────────────────────────────────────────

class ReportConfigServiceTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_user(
            username='cfgadmin', password='pass', is_superuser=True
        )
        self.org_unit = OrgUnit.objects.create(name='CfgOrg', slug='cfg-org')
        self.module = Module.objects.create(
            name='CfgModule', scope=1, org_unit=self.org_unit
        )
        self.config = ReportConfig.objects.create(
            name='Test Config', ghg_scopes=[1], categories=[],
            org_unit=None, grouping='scope',
        )

    def test_generate_from_config_returns_structure(self):
        result = ReportConfigService.generate_from_config(self.config, self.superuser)
        self.assertIn('config_id', result)
        self.assertIn('config_name', result)
        self.assertIn('scope_breakdown', result)
        self.assertIn('total_co2e_tonnes', result)

    def test_generate_from_config_empty_data(self):
        result = ReportConfigService.generate_from_config(self.config, self.superuser)
        self.assertEqual(result['total_co2e_tonnes'], 0.0)
        self.assertEqual(result['calculation_count'], 0)


# ── TargetService Extended ──────────────────────────────────────────────────

class TargetServiceExtendedTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_user(
            username='tgtextadmin', password='pass', is_superuser=True
        )
        self.org_unit = OrgUnit.objects.create(name='TgtExtOrg', slug='tgt-ext-org')
        self.target = SBTiTarget.objects.create(
            org_unit=self.org_unit, name='2040 Net Zero', base_year=2020,
            target_year=2040, target_type='absolute', scope='1+2',
            reduction_pct=Decimal('90.00')
        )

    def test_get_progress_zero_data(self):
        result = TargetService.get_progress(self.target.id, 2025)
        self.assertEqual(result['actual_tco2e'], 0.0)
        self.assertEqual(result['name'], '2040 Net Zero')
