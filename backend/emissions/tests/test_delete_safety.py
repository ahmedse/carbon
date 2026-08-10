"""Tests for enterprise-grade deletion safety across all emission ViewSets.

Covers:
- ReportingPeriod: status gates, calculation blocks, force delete
- EmissionFactor: dependency check on calculation rules, soft-delete
- GWP: soft-delete
- Calculation: hard-delete with audit
- CalculationRule: archive vs hard-delete based on audit count
- SBTiTarget: hard-delete with audit
- OrganizationalBoundary: dependency check on reporting periods
- BaseYear: dependency check on recalculation triggers
"""

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient, APITestCase

from emissions.models import (
    ReportingPeriod, EmissionFactor, GWP, Calculation, CalculationRule,
    SBTiTarget, CalculationAudit, OrganizationalBoundary, BaseYear,
    RecalculationTrigger,
)
from catalog.models import GovernanceEvent
from dataschema.models import DataTable, DataField, DataRow
from core.models import Module
from mdm.models import OrgUnit

User = get_user_model()


class ReportingPeriodDeleteTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username='del_admin', password='Admin_123'
        )
        self.regular = User.objects.create_user(
            username='del_regular', password='User_123'
        )
        self.org = OrgUnit.objects.create(name='Test Org', slug='test-org')
        self.module = Module.objects.create(name='Test Module', scope=1, org_unit=self.org)

    def _make_calculation(self, period, data_row_id, code='TEST_DEL'):
        table = DataTable.objects.create(module=self.module, name=f'tbl_{data_row_id}')
        DataRow.objects.create(
            id=data_row_id, data_table=table, values={'fuel': 100},
            created_by=self.admin,
        )
        factor = EmissionFactor.objects.create(
            code=code, name='Test Factor', category='fuel',
            scope=1, factor_value=2.0, activity_unit='litres',
            source='DEFRA', valid_from='2024-01-01',
        )
        return Calculation.objects.create(
            module=self.module, data_row_id=data_row_id,
            emission_factor=factor, reporting_period=period,
            activity_value=100, activity_unit='litres',
            co2e_kg=200, scope=1, category='fuel',
            reporting_year=2026,
        )

    def test_delete_draft_period_succeeds(self):
        period = ReportingPeriod.objects.create(
            name='Draft FY26', start_date='2026-01-01',
            end_date='2026-12-31', status='draft',
        )
        self.client.force_authenticate(user=self.admin)
        url = reverse('carbon:reporting-period-detail', kwargs={'pk': period.pk})
        resp = self.client.delete(url)
        self.assertEqual(resp.status_code, 204)
        period.refresh_from_db()
        self.assertEqual(period.status, 'closed')

    def test_delete_open_period_blocked(self):
        period = ReportingPeriod.objects.create(
            name='Open FY26', start_date='2026-01-01',
            end_date='2026-12-31', status='open',
        )
        self.client.force_authenticate(user=self.admin)
        url = reverse('carbon:reporting-period-detail', kwargs={'pk': period.pk})
        resp = self.client.delete(url)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['code'], 'period_not_deletable')

    def test_delete_locked_period_blocked(self):
        period = ReportingPeriod.objects.create(
            name='Locked FY26', start_date='2026-01-01',
            end_date='2026-12-31', status='locked',
        )
        self.client.force_authenticate(user=self.admin)
        url = reverse('carbon:reporting-period-detail', kwargs={'pk': period.pk})
        resp = self.client.delete(url)
        self.assertEqual(resp.status_code, 400)

    def test_delete_with_calculations_blocked(self):
        period = ReportingPeriod.objects.create(
            name='Has Calcs', start_date='2026-01-01',
            end_date='2026-12-31', status='draft',
        )
        self._make_calculation(period, data_row_id=101, code='TEST_CALC1')
        self.client.force_authenticate(user=self.admin)
        url = reverse('carbon:reporting-period-detail', kwargs={'pk': period.pk})
        resp = self.client.delete(url)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['code'], 'period_has_calculations')

    def test_force_delete_with_calculations_as_superuser(self):
        period = ReportingPeriod.objects.create(
            name='Force Del', start_date='2026-01-01',
            end_date='2026-12-31', status='draft',
        )
        self._make_calculation(period, data_row_id=102, code='TEST_FORCE')
        self.client.force_authenticate(user=self.admin)
        url = reverse('carbon:reporting-period-detail', kwargs={'pk': period.pk})
        resp = self.client.delete(f'{url}?force=true')
        self.assertEqual(resp.status_code, 204)

    def test_force_delete_with_calculations_as_regular_user_blocked(self):
        period = ReportingPeriod.objects.create(
            name='Regular Force', start_date='2026-01-01',
            end_date='2026-12-31', status='draft',
        )
        self._make_calculation(period, data_row_id=103, code='TEST_REGF')
        self.client.force_authenticate(user=self.regular)
        url = reverse('carbon:reporting-period-detail', kwargs={'pk': period.pk})
        resp = self.client.delete(f'{url}?force=true')
        self.assertEqual(resp.status_code, 403)

    def test_delete_emits_governance_event(self):
        period = ReportingPeriod.objects.create(
            name='Audit Test', start_date='2026-01-01',
            end_date='2026-12-31', status='draft',
        )
        self.client.force_authenticate(user=self.admin)
        url = reverse('carbon:reporting-period-detail', kwargs={'pk': period.pk})
        self.client.delete(url)
        event = GovernanceEvent.objects.filter(
            entity_type='ReportingPeriod', entity_id=period.id, action='delete'
        ).first()
        self.assertIsNotNone(event)
        self.assertEqual(event.user, self.admin)


class EmissionFactorDeleteTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username='ef_admin', password='Admin_123'
        )
        self.org = OrgUnit.objects.create(name='EF Test Org', slug='ef-test-org')
        self.module = Module.objects.create(name='EF Module', scope=1, org_unit=self.org)

    def test_delete_unused_factor_succeeds(self):
        factor = EmissionFactor.objects.create(
            code='UNUSED', name='Unused Factor', category='fuel',
            scope=1, factor_value=1.5, activity_unit='litres',
            source='DEFRA', valid_from='2024-01-01',
        )
        self.client.force_authenticate(user=self.admin)
        url = reverse('carbon:emission-factor-detail', kwargs={'pk': factor.pk})
        resp = self.client.delete(url)
        self.assertEqual(resp.status_code, 204)
        factor.refresh_from_db()
        self.assertFalse(factor.is_active)

    def test_delete_factor_with_rules_blocked(self):
        factor = EmissionFactor.objects.create(
            code='INUSE', name='In Use Factor', category='fuel',
            scope=1, factor_value=1.5, activity_unit='litres',
            source='DEFRA', valid_from='2024-01-01',
        )
        table = DataTable.objects.create(module=self.module, name='ef_table')
        field = DataField.objects.create(
            data_table=table, name='ef_field', label='EF Field', type='number'
        )
        CalculationRule.objects.create(
            name='Test Rule', data_table=table, activity_field=field,
            emission_factor=factor, rule_type='direct',
        )
        self.client.force_authenticate(user=self.admin)
        url = reverse('carbon:emission-factor-detail', kwargs={'pk': factor.pk})
        resp = self.client.delete(url)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['code'], 'factor_in_use')


class GWPDeleteTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username='gwp_admin', password='Admin_123'
        )

    def test_delete_gwp_hard_deletes_with_audit(self):
        gwp = GWP.objects.create(
            gas_name='Carbon Dioxide', gas_formula='CO2',
            gwp_ar5_100yr=1, gwp_ar6_100yr=1,
        )
        self.client.force_authenticate(user=self.admin)
        url = reverse('carbon:gwp-detail', kwargs={'pk': gwp.pk})
        resp = self.client.delete(url)
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(GWP.objects.filter(pk=gwp.pk).exists())
        event = GovernanceEvent.objects.filter(
            entity_type='GWP', entity_id=gwp.id, action='delete'
        ).first()
        self.assertIsNotNone(event)


class CalculationDeleteTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username='calc_admin', password='Admin_123'
        )
        self.org = OrgUnit.objects.create(name='Calc Test Org', slug='calc-test-org')
        self.module = Module.objects.create(name='Calc Module', scope=1, org_unit=self.org)

    def _make_calculation(self, data_row_id, code='CALC_TEST'):
        table = DataTable.objects.create(module=self.module, name=f'calc_tbl_{data_row_id}')
        DataRow.objects.create(
            id=data_row_id, data_table=table, values={'fuel': 100},
            created_by=self.admin,
        )
        factor = EmissionFactor.objects.create(
            code=code, name='Calc Factor', category='fuel',
            scope=1, factor_value=2.0, activity_unit='litres',
            source='DEFRA', valid_from='2024-01-01',
        )
        return Calculation.objects.create(
            module=self.module, data_row_id=data_row_id,
            emission_factor=factor, activity_value=100,
            activity_unit='litres', co2e_kg=200, scope=1,
            category='fuel', reporting_year=2026,
        )

    def test_delete_calculation_hard_deletes(self):
        calc = self._make_calculation(data_row_id=201)
        self.client.force_authenticate(user=self.admin)
        url = reverse('carbon:calculation-detail', kwargs={'pk': calc.pk})
        resp = self.client.delete(url)
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Calculation.objects.filter(pk=calc.pk).exists())

    def test_delete_calculation_emits_audit(self):
        calc = self._make_calculation(data_row_id=202, code='CALC_AUDIT')
        self.client.force_authenticate(user=self.admin)
        url = reverse('carbon:calculation-detail', kwargs={'pk': calc.pk})
        self.client.delete(url)
        event = GovernanceEvent.objects.filter(
            entity_type='Calculation', entity_id=calc.id, action='delete'
        ).first()
        self.assertIsNotNone(event)


class CalculationRuleDeleteTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username='rule_admin', password='Admin_123'
        )
        self.org = OrgUnit.objects.create(name='Rule Test Org', slug='rule-test-org')
        self.module = Module.objects.create(name='Rule Module', scope=1, org_unit=self.org)

    def _make_rule(self, name='Test Rule', code='RULE_TEST'):
        table = DataTable.objects.create(module=self.module, name=f'{name}_table')
        field = DataField.objects.create(
            data_table=table, name=f'{name}_field', label=name, type='number'
        )
        factor = EmissionFactor.objects.create(
            code=code, name=name, category='fuel',
            scope=1, factor_value=2.0, activity_unit='litres',
            source='DEFRA', valid_from='2024-01-01',
        )
        return CalculationRule.objects.create(
            name=name, data_table=table, activity_field=field,
            emission_factor=factor, rule_type='direct',
        )

    def test_delete_rule_without_audits_hard_deletes(self):
        rule = self._make_rule(name='NoAuditRule', code='NOAUDIT')
        self.client.force_authenticate(user=self.admin)
        url = reverse('carbon:calculation-rule-detail', kwargs={'pk': rule.pk})
        resp = self.client.delete(url)
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(CalculationRule.objects.filter(pk=rule.pk).exists())

    def test_delete_rule_with_audits_archives(self):
        rule = self._make_rule(name='AuditRule', code='AUDITRULE')
        CalculationAudit.objects.create(
            calculation_rule=rule, trigger_type='single',
            created_count=5, triggered_by=self.admin,
        )
        self.client.force_authenticate(user=self.admin)
        url = reverse('carbon:calculation-rule-detail', kwargs={'pk': rule.pk})
        resp = self.client.delete(url)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['archived'])
        rule.refresh_from_db()
        self.assertFalse(rule.is_active)


class SBTiTargetDeleteTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username='sbt_admin', password='Admin_123'
        )
        self.org = OrgUnit.objects.create(name='SBT Test Org', slug='sbt-test-org')

    def test_delete_target_hard_deletes(self):
        target = SBTiTarget.objects.create(
            org_unit=self.org, name='Test Target',
            base_year=2023, target_year=2030,
            target_type='absolute', scope='1+2',
            reduction_pct=30, status='draft',
        )
        self.client.force_authenticate(user=self.admin)
        url = reverse('carbon:sbti-target-detail', kwargs={'pk': target.pk})
        resp = self.client.delete(url)
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(SBTiTarget.objects.filter(pk=target.pk).exists())


class OrganizationalBoundaryDeleteTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username='bound_admin', password='Admin_123'
        )

    def test_delete_boundary_with_periods_blocked(self):
        boundary = OrganizationalBoundary.objects.create(
            name='Test Boundary', consolidation_approach='operational_control',
        )
        ReportingPeriod.objects.create(
            name='Bound Period', start_date='2026-01-01',
            end_date='2026-12-31', status='draft',
            organizational_boundary=boundary,
        )
        self.client.force_authenticate(user=self.admin)
        url = reverse('carbon:organizational-boundary-detail', kwargs={'pk': boundary.pk})
        resp = self.client.delete(url)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['code'], 'boundary_in_use')

    def test_delete_unused_boundary_succeeds(self):
        boundary = OrganizationalBoundary.objects.create(
            name='Free Boundary', consolidation_approach='equity_share',
        )
        self.client.force_authenticate(user=self.admin)
        url = reverse('carbon:organizational-boundary-detail', kwargs={'pk': boundary.pk})
        resp = self.client.delete(url)
        self.assertEqual(resp.status_code, 204)
        boundary.refresh_from_db()
        self.assertFalse(boundary.is_active)


class BaseYearDeleteTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username='by_admin', password='Admin_123'
        )

    def test_delete_base_year_with_triggers_blocked(self):
        period = ReportingPeriod.objects.create(
            name='BY Period', start_date='2026-01-01',
            end_date='2026-12-31', status='draft',
        )
        base_year = BaseYear.objects.create(
            year=2020, reporting_period=period,
        )
        RecalculationTrigger.objects.create(
            base_year=base_year, trigger_type='threshold_exceeded',
            description='Test trigger', triggered_by=self.admin,
        )
        self.client.force_authenticate(user=self.admin)
        url = reverse('carbon:base-year-detail', kwargs={'pk': base_year.pk})
        resp = self.client.delete(url)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['code'], 'base_year_in_use')

    def test_delete_base_year_without_triggers_succeeds(self):
        period = ReportingPeriod.objects.create(
            name='BY Clean', start_date='2026-01-01',
            end_date='2026-12-31', status='draft',
        )
        base_year = BaseYear.objects.create(
            year=2021, reporting_period=period,
        )
        self.client.force_authenticate(user=self.admin)
        url = reverse('carbon:base-year-detail', kwargs={'pk': base_year.pk})
        resp = self.client.delete(url)
        self.assertEqual(resp.status_code, 204)


class DataFieldDeleteTests(APITestCase):
    """Tests for DataFieldViewSet.perform_destroy dependency guards."""
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username='df_admin', password='Admin_123'
        )
        self.org = OrgUnit.objects.create(name='DF Test Org', slug='df-test-org')
        self.module = Module.objects.create(name='DF Module', scope=1, org_unit=self.org)

    def _create_field(self, name='test_field'):
        table = DataTable.objects.create(module=self.module, name=f'{name}_table')
        return DataField.objects.create(
            data_table=table, name=name, label=name, type='number'
        )


class DataRowDeleteTests(APITestCase):
    """Tests for DataRowViewSet.destroy soft-delete."""
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username='dr_admin', password='Admin_123'
        )
        self.org = OrgUnit.objects.create(name='DR Test Org', slug='dr-test-org')
        self.module = Module.objects.create(name='DR Module', scope=1, org_unit=self.org)

    def test_delete_row_soft_deletes(self):
        table = DataTable.objects.create(module=self.module, name='dr_table')
        row = DataRow.objects.create(
            data_table=table, values={'fuel': 100},
            created_by=self.admin,
        )
        self.client.force_authenticate(user=self.admin)
        url = reverse('dataschema-row-detail', kwargs={'pk': row.pk})
        resp = self.client.delete(f'{url}?data_table={table.pk}')
        self.assertEqual(resp.status_code, 204)
        row.refresh_from_db()
        self.assertTrue(row.is_archived)
