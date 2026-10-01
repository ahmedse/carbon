"""Domain-app product contracts P-13–P-20 / CR-S2-01, CR-OFF-01, CR-REST-01, CR-OWN-01."""
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import Group
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.capabilities import get_user_capabilities
from accounts.models import ScopedRole, User
from accounts.rbac_utils import org_scope_for_capability
from core.models import Module
from dataschema.models import DataField, DataRow, DataTable
from emissions.inventory_math import (
    LOCATION_BASED,
    inventory_kg,
    is_offset_field,
    offset_keys_in,
)
from emissions.models import Calculation, CalculationRule, EmissionFactor, InventorySource
from emissions.onboarding_o1 import evaluate_o1
from mdm.models import OrgUnit


def _factor(**kwargs):
    defaults = {
        'code': 'EG-GRID-TEST',
        'name': 'EG grid test',
        'category': 'electricity',
        'scope': 2,
        'factor_value': Decimal('0.4584'),
        'activity_unit': 'kWh',
        'source': 'Test EG grid',
        'valid_from': date(2020, 1, 1),
        'is_active': True,
    }
    defaults.update(kwargs)
    return EmissionFactor.objects.create(**defaults)


class InventoryMathTests(TestCase):
    def test_offset_keys_are_ignored_not_subtracted(self):
        values = {'kwh': 100, 'offset_kg': 40, 'rec': 10, 'eac': 5}
        self.assertEqual(offset_keys_in(values), ('offset_kg', 'rec', 'eac'))
        self.assertEqual(inventory_kg(100, '0.5', values=values), Decimal('50.0'))

    def test_offset_field_name(self):
        self.assertTrue(is_offset_field('offset_kg'))
        self.assertTrue(is_offset_field('I-REC'))
        self.assertFalse(is_offset_field('kwh'))


class Scope2MethodTests(TestCase):
    def setUp(self):
        self.org = OrgUnit.objects.create(name='Smart Village', slug='sv-s2')
        self.module = Module.objects.create(name='SV electricity', scope=2, org_unit=self.org)
        self.table = DataTable.objects.create(name='sv_kwh', title='SV kWh', module=self.module)
        self.field = DataField.objects.create(
            data_table=self.table, name='kwh', label='kWh', type='number',
        )

    def test_scope2_source_persists_location_based(self):
        source = InventorySource.objects.create(
            org_unit=self.org, scope=2, source_name='Smart Village electricity',
        )
        source.refresh_from_db()
        self.assertEqual(source.scope2_method, LOCATION_BASED)

    def test_scope1_source_has_blank_method(self):
        source = InventorySource.objects.create(
            org_unit=self.org, scope=1, source_name='Smart Village diesel',
        )
        source.refresh_from_db()
        self.assertEqual(source.scope2_method, '')

    def test_calculation_labels_location_based(self):
        factor = _factor()
        row = DataRow.objects.create(data_table=self.table, values={'kwh': 10, 'offset_kg': 999})
        calc = Calculation.create_from_data_row(
            data_row=row,
            emission_factor=factor,
            activity_value=10,
            activity_unit='kWh',
            reporting_year=2023,
        )
        self.assertEqual(calc.scope2_method, LOCATION_BASED)
        self.assertEqual(calc.co2e_kg, Decimal('10') * Decimal('0.4584'))

    def test_market_based_without_distinct_factor_is_not_invented(self):
        factor = _factor(code='EG-GRID-ONLY')
        row = DataRow.objects.create(data_table=self.table, values={'kwh': 10})
        rule = CalculationRule.objects.create(
            name='SV electricity',
            data_table=self.table,
            activity_field=self.field,
            emission_factor=factor,
            rule_type='direct',
            is_active=True,
            scope2_calculation_method='market_based',
        )
        result = rule.calculate_for_row(row)
        self.assertIsNone(result)
        self.assertFalse(Calculation.objects.filter(scope2_method='market_based').exists())

    def test_evaluate_o1_names_location_based(self):
        result = evaluate_o1(
            periods=[{
                'id': 7, 'name': 'AY 2026', 'status': 'open',
                'start_date': '2026-01-01', 'end_date': '2026-12-31',
                'period_type': 'annual', 'organizational_boundary': 3,
            }],
            boundaries=[{
                'id': 3, 'name': 'AASTMT operational',
                'consolidation_approach': 'operational_control',
            }],
            sources=[
                {
                    'id': 1, 'source_name': 'Smart Village electricity',
                    'scope': 2, 'description': '', 'scope2_method': 'location_based',
                },
                {
                    'id': 2, 'source_name': 'Smart Village diesel',
                    'scope': 1, 'description': 'Campus generators',
                },
            ],
            statuses=[],
            summary={'total_calculations': 1, 'by_scope': {
                '2': {'total_co2e_kg': '1239599.320800', 'scope2_method': 'location-based'},
            }},
        )
        method = next(row for row in result['checks'] if row['code'] == 'scope2_method')
        self.assertTrue(method['met'])
        self.assertEqual(method['method'], 'location-based')
        kg = next(row for row in result['checks'] if row['code'] == 'summary_kg')
        self.assertEqual(kg['method'], 'location-based')
        self.assertEqual(kg['kg'], '1239599.320800')


class OffsetInventoryTests(TestCase):
    def setUp(self):
        self.org = OrgUnit.objects.create(name='Offset Org', slug='off-org')
        self.module = Module.objects.create(name='Offset mod', scope=2, org_unit=self.org)
        self.table = DataTable.objects.create(name='off_kwh', title='kWh', module=self.module)
        self.kwh = DataField.objects.create(
            data_table=self.table, name='kwh', label='kWh', type='number',
        )
        self.offset = DataField.objects.create(
            data_table=self.table, name='offset_kg', label='Offset', type='number',
        )
        self.factor = _factor(code='OFF-GRID')

    def test_offset_activity_field_produces_no_calculation(self):
        rule = CalculationRule.objects.create(
            name='offset rule',
            data_table=self.table,
            activity_field=self.offset,
            emission_factor=self.factor,
            rule_type='direct',
            is_active=True,
        )
        row = DataRow.objects.create(data_table=self.table, values={'offset_kg': 40, 'kwh': 100})
        self.assertIsNone(rule.calculate_for_row(row))

    def test_kwh_rule_ignores_offset_column(self):
        rule = CalculationRule.objects.create(
            name='kwh rule',
            data_table=self.table,
            activity_field=self.kwh,
            emission_factor=self.factor,
            rule_type='direct',
            is_active=True,
        )
        row = DataRow.objects.create(
            data_table=self.table, values={'kwh': 100, 'offset_kg': 999, 'rec': 12},
        )
        calc = rule.calculate_for_row(row)
        self.assertIsNotNone(calc)
        self.assertEqual(calc.co2e_kg, Decimal('100') * Decimal('0.4584'))


class RestatementTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(username='restate_admin', password='AdminPa_132')
        self.module = Module.objects.create(name='Restate mod')
        self.table = DataTable.objects.create(name='restate_t', title='T', module=self.module)
        self.row = DataRow.objects.create(data_table=self.table, values={'kwh': 100})
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_queryset_update_cannot_write_values(self):
        with self.assertRaises(IntegrityError):
            DataRow.objects.filter(pk=self.row.pk).update(values={'kwh': 1})
        self.row.refresh_from_db()
        self.assertEqual(self.row.values['kwh'], 100)

    def test_restate_archives_and_appends(self):
        url = reverse('dataschema-row-restate', args=[self.row.pk])
        resp = self.client.post(url, {'values': {'kwh': 120}}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.row.refresh_from_db()
        self.assertTrue(self.row.is_archived)
        self.assertEqual(self.row.values['kwh'], 100)
        new_id = resp.data['id']
        self.assertNotEqual(new_id, self.row.pk)
        successor = DataRow.objects.get(pk=new_id)
        self.assertFalse(successor.is_archived)
        self.assertEqual(successor.values['kwh'], 120)
        self.assertEqual(successor.version, 2)


class CampusOwnerTests(TestCase):
    def test_campus_dataowner_enter_data_is_org_scoped(self):
        root = OrgUnit.objects.create(name='AASTMT', slug='own-root', org_type='company')
        campus_a = OrgUnit.objects.create(
            name='Smart Village', slug='own-sv', parent=root, org_type='department',
        )
        campus_b = OrgUnit.objects.create(
            name='Abu Qir', slug='own-aq', parent=root, org_type='department',
        )
        group, _ = Group.objects.get_or_create(name='dataowners_group')
        user = User.objects.create_user(username='data.smartvillage', password='AASTcarbonPa_132')
        ScopedRole.objects.create(
            user=user, group=group, org_unit=campus_a, module=None, is_active=True,
        )
        scope = org_scope_for_capability(user, 'carbon:enter_data')
        self.assertFalse(scope.unrestricted)
        self.assertIn(campus_a.id, scope.ids)
        self.assertNotIn(campus_b.id, scope.ids)

    def test_emp_1067_is_not_granted_people_view(self):
        user = User.objects.create_user(username='emp_1067', password='x')
        self.assertNotIn('people:view', get_user_capabilities(user))


class DualScope2AndDisclosureTests(TestCase):
    def setUp(self):
        from emissions.models import ReportingPeriod
        from emissions.services import CalculationSummaryService

        self.Summary = CalculationSummaryService
        self.user = User.objects.create_superuser(username='s2_admin', password='AdminPa_132')
        self.org = OrgUnit.objects.create(name='Smart Village', slug='s2-sv')
        self.module = Module.objects.create(name='SV electricity', scope=2, org_unit=self.org)
        self.table = DataTable.objects.create(name='sv_kwh_dual', title='SV kWh', module=self.module)
        self.field = DataField.objects.create(
            data_table=self.table, name='kwh', label='kWh', type='number',
        )
        self.period = ReportingPeriod.objects.create(
            name='FY 2023-24', start_date=date(2023, 7, 1), end_date=date(2024, 6, 30),
            status='open', period_type='annual',
        )
        self.grid = _factor(code='EG-GRID-202')
        self.row = DataRow.objects.create(data_table=self.table, values={'kwh': 10})

    def test_market_based_absent_is_not_zero(self):
        Calculation.create_from_data_row(
            data_row=self.row,
            emission_factor=self.grid,
            activity_value=10,
            activity_unit='kWh',
            reporting_year=2023,
            reporting_period=self.period,
        )
        summary = self.Summary.get_summary(self.user, self.period.id)
        market = summary['by_scope2_method']['market_based']
        self.assertFalse(market['present'])
        self.assertEqual(market['reason'], 'no_distinct_contractual_factor')
        self.assertNotIn('total_co2e_kg', market)
        loc = summary['by_scope2_method']['location_based']
        self.assertTrue(loc['present'])
        self.assertEqual(loc['scope2_method'], 'location-based')

    def test_market_based_with_distinct_factor_is_labelled(self):
        ppa = _factor(code='PPA-CONTRACT', name='Contractual PPA', factor_value=Decimal('0.1'))
        rule = CalculationRule.objects.create(
            name='dual electricity',
            data_table=self.table,
            activity_field=self.field,
            emission_factor=self.grid,
            rule_type='direct',
            is_active=True,
            scope2_calculation_method='dual',
            factor_selector_mapping={'__market__': 'PPA-CONTRACT'},
        )
        result = rule.calculate_for_row(self.row)
        self.assertIsNotNone(result)
        market = Calculation.objects.get(scope2_method='market_based')
        self.assertEqual(market.co2e_kg, Decimal('10') * Decimal('0.1'))
        self.assertEqual(market.emission_factor_id, ppa.id)
        summary = self.Summary.get_summary(self.user, None)
        self.assertTrue(summary['by_scope2_method']['market_based']['present'])

    def test_grid_code_as_market_is_not_a_distinct_factor(self):
        rule = CalculationRule.objects.create(
            name='copy grid',
            data_table=self.table,
            activity_field=self.field,
            emission_factor=self.grid,
            rule_type='direct',
            is_active=True,
            scope2_calculation_method='dual',
            factor_selector_mapping={'__market__': 'EG-GRID-202'},
        )
        rule.calculate_for_row(self.row)
        self.assertFalse(Calculation.objects.filter(scope2_method='market_based').exists())

    def test_disclosure_shape_maps_ledger_and_keeps_market_absent(self):
        from emissions.services import DisclosureService
        Calculation.create_from_data_row(
            data_row=self.row,
            emission_factor=self.grid,
            activity_value=10,
            activity_unit='kWh',
            reporting_year=2023,
            reporting_period=self.period,
        )
        payload = DisclosureService.export(
            self.user, framework='esrs_e1', period_id=self.period.id,
        )
        self.assertEqual(payload['status'], 'shape_only')
        self.assertFalse(payload['new_kilogram'])
        self.assertFalse(payload['assurance']['met'])
        self.assertEqual(payload['fields']['E1-6_scope_2_market_based_status'], 'absent')
        self.assertIsNone(payload['fields']['E1-6_scope_2_market_based_kg'])
        self.assertIsNone(payload['fields']['E1-6_scope_3_kg'])
        self.assertEqual(
            Decimal(payload['fields']['E1-6_scope_2_location_based_kg']),
            Decimal('10') * Decimal('0.4584'),
        )
        client = APIClient()
        client.force_authenticate(user=self.user)
        resp = client.get(
            '/carbon-api/carbon/disclosure/',
            {'framework': 'cdp', 'reporting_period_id': self.period.id},
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['framework'], 'cdp')
        self.assertIsNone(resp.data['fields']['C6.3_scope_2_market_based_kg'])
        self.assertFalse(resp.data['market_based']['present'])

    def test_saved_report_headline_excludes_absent_market(self):
        from emissions.models import ReportConfig
        from emissions.services import ReportConfigService

        Calculation.create_from_data_row(
            data_row=self.row,
            emission_factor=self.grid,
            activity_value=10,
            activity_unit='kWh',
            reporting_year=2023,
            reporting_period=self.period,
        )
        config = ReportConfig.objects.create(
            name='dual-s2-hold', created_by=self.user, reporting_period=self.period,
        )
        result = ReportConfigService.generate_from_config(config, self.user)
        self.assertFalse(result['by_scope2_method']['market_based']['present'])
        self.assertNotIn('total_co2e_kg', result['by_scope2_method']['market_based'])
        s2 = next(row for row in result['scope_breakdown'] if row['scope'] == 2)
        self.assertEqual(s2['scope2_method'], 'location-based')

    def test_disclosure_rejects_unknown_framework(self):
        from emissions.services import DisclosureService
        with self.assertRaises(ValueError):
            DisclosureService.export(self.user, framework='made_up', period_id=self.period.id)

    def test_console_activity_labels_scope2_and_does_not_invent_a_method(self):
        from types import SimpleNamespace
        from emissions.services import _activity_detail

        labelled = _activity_detail(SimpleNamespace(
            activity_value=10, activity_unit='kWh', co2e_kg=4.5,
            scope=2, scope2_method='location_based',
        ))
        self.assertIn('kg CO2e', labelled)
        self.assertIn('location-based', labelled)
        scope1 = _activity_detail(SimpleNamespace(
            activity_value=3000, activity_unit='litre', co2e_kg=8040,
            scope=1, scope2_method=None,
        ))
        self.assertIn('kg CO2e', scope1)
        self.assertNotIn('location-based', scope1)
        self.assertNotIn('market-based', scope1)
        blank = _activity_detail(SimpleNamespace(
            activity_value=1, activity_unit='kWh', co2e_kg=1,
            scope=2, scope2_method='',
        ))
        self.assertIn('unlabelled', blank)
        self.assertNotIn('market-based', blank)
