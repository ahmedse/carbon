"""Tests for Inventory Coverage models, service, and API (ADR-0020)."""
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import Group
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User, ScopedRole
from emissions.models import (
    InventorySource,
    InventorySourceStatus,
    CoverageGoal,
    CoverageAction,
    ReportingPeriod,
)
from emissions.services import InventoryCoverageService
from mdm.models import OrgUnit


class InventorySourceModelTests(TestCase):
    def setUp(self):
        self.org = OrgUnit.objects.create(name='Facilities', slug='facilities')

    def test_str_method(self):
        source = InventorySource(
            org_unit=self.org, scope=3, scope3_category=1, source_name='Business Travel'
        )
        s = str(source)
        self.assertIn('Business Travel', s)
        self.assertIn('Scope 3', s)
        self.assertIn('Cat 1', s)

    def test_unique_binding_constraint(self):
        InventorySource.objects.create(
            org_unit=self.org, scope=3, scope3_category=1, source_name='Flights'
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                InventorySource.objects.create(
                    org_unit=self.org, scope=3, scope3_category=1, source_name='Flights'
                )

    def test_status_defaults(self):
        source = InventorySource.objects.create(
            org_unit=self.org, scope=1, source_name='Natural Gas Boilers'
        )
        status = InventorySourceStatus.objects.create(
            source=source,
            reporting_period=ReportingPeriod.objects.create(
                name='FY2024', start_date=date(2024, 1, 1), end_date=date(2024, 12, 31)
            ),
        )
        self.assertEqual(status.status, 'declared')
        self.assertIsNone(status.data_quality_tier)

    def test_source_period_unique_constraint(self):
        source = InventorySource.objects.create(
            org_unit=self.org, scope=1, source_name='Generators'
        )
        period = ReportingPeriod.objects.create(
            name='FY2024', start_date=date(2024, 1, 1), end_date=date(2024, 12, 31)
        )
        InventorySourceStatus.objects.create(source=source, reporting_period=period)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                InventorySourceStatus.objects.create(source=source, reporting_period=period)

    def test_coverage_goal_and_action_str(self):
        source = InventorySource.objects.create(
            org_unit=self.org, scope=1, source_name='Boilers'
        )
        goal = CoverageGoal.objects.create(
            org_unit=self.org, name='Scope 1 Goal', scope='1',
            target_coverage_pct=Decimal('90.00'), target_year=2030,
        )
        self.assertIn('Scope 1 Goal', str(goal))

        action = CoverageAction.objects.create(
            source=source, action_type='collect_data'
        )
        self.assertIn('Collect Data', str(action))
        self.assertEqual(action.status, 'open')


class InventoryCoverageServiceTests(TestCase):
    def setUp(self):
        self.org = OrgUnit.objects.create(name='Facilities', slug='facilities-cov')
        self.period = ReportingPeriod.objects.create(
            name='FY2024', start_date=date(2024, 1, 1), end_date=date(2024, 12, 31)
        )

    def _make_source(self, name, scope=1, category=None):
        return InventorySource.objects.create(
            org_unit=self.org, scope=scope, scope3_category=category, source_name=name
        )

    def test_compute_coverage_all_branches(self):
        not_assessed = self._make_source('Not Assessed Source')
        covered_t1 = self._make_source('Covered Tier 1 Source')
        covered_t2 = self._make_source('Covered Tier 2 Source')
        excluded = self._make_source('Excluded Source')
        declared = self._make_source('Declared Source')

        InventorySourceStatus.objects.create(
            source=covered_t1, reporting_period=self.period,
            status='covered', data_quality_tier=1,
        )
        InventorySourceStatus.objects.create(
            source=covered_t2, reporting_period=self.period,
            status='covered', data_quality_tier=2,
        )
        InventorySourceStatus.objects.create(
            source=excluded, reporting_period=self.period,
            status='excluded', exclusion_reason='not_material',
        )
        InventorySourceStatus.objects.create(
            source=declared, reporting_period=self.period, status='declared',
        )

        result = InventoryCoverageService.compute_coverage(self.period.id)

        self.assertEqual(result['total'], 5)
        self.assertEqual(result['covered'], 2)
        self.assertEqual(result['gaps_count'], 2)
        self.assertEqual(result['material_exclusions_count'], 1)
        self.assertEqual(result['avg_quality_tier'], 1.5)

        reasons = {g['reason'] for g in result['gaps']}
        self.assertIn('not_assessed', reasons)
        self.assertIn('declared', reasons)

        excluded_reasons = {e['reason'] for e in result['material_exclusions']}
        self.assertIn('Not Material', excluded_reasons)

        # No goal → absolute definition, denominator = total
        self.assertEqual(result['completeness_definition'], 'absolute')
        self.assertEqual(result['pct'], round((2 / 5) * 100, 2))

    def test_materiality_bounded_denominator(self):
        covered = self._make_source('Covered Source')
        excluded = self._make_source('Excluded Source')
        not_assessed = self._make_source('Not Assessed Source')

        InventorySourceStatus.objects.create(
            source=covered, reporting_period=self.period,
            status='covered', data_quality_tier=2,
        )
        InventorySourceStatus.objects.create(
            source=excluded, reporting_period=self.period,
            status='excluded', exclusion_reason='out_of_boundary',
        )

        CoverageGoal.objects.create(
            org_unit=self.org, name='Scope 1 Coverage', scope='1',
            target_coverage_pct=Decimal('100.00'), target_year=2030,
            completeness_definition='materiality_bounded', status='active',
        )

        result = InventoryCoverageService.compute_coverage(
            self.period.id, org_unit_id=self.org.id
        )

        self.assertEqual(result['total'], 3)
        self.assertEqual(result['covered'], 1)
        self.assertEqual(result['material_exclusions_count'], 1)
        self.assertEqual(result['completeness_definition'], 'materiality_bounded')
        # denominator = total - exclusions = 2
        self.assertEqual(result['pct'], 50.0)
        self.assertEqual(result['target_coverage_pct'], 100.0)

    def test_org_unit_filter(self):
        other_org = OrgUnit.objects.create(name='Other', slug='other-org')
        self._make_source('Mine')
        InventorySource.objects.create(
            org_unit=other_org, scope=1, source_name='Theirs'
        )

        result = InventoryCoverageService.compute_coverage(
            self.period.id, org_unit_id=self.org.id
        )
        self.assertEqual(result['total'], 1)


class InventoryCoverageAPITests(TestCase):
    def setUp(self):
        self.org = OrgUnit.objects.create(name='Facilities', slug='facilities-api')
        self.period = ReportingPeriod.objects.create(
            name='FY2024', start_date=date(2024, 1, 1), end_date=date(2024, 12, 31)
        )
        InventorySource.objects.create(
            org_unit=self.org, scope=1, source_name='Natural Gas'
        )
        self.client = APIClient()

    def test_get_coverage_ok(self):
        self.client.force_authenticate(
            User.objects.create_user(username='viewer', password='pass')
        )
        resp = self.client.get(
            reverse('carbon:inventory-coverage'),
            {'reporting_period': self.period.id},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['total'], 1)
        self.assertEqual(data['covered'], 0)
        self.assertIn('pct', data)

    def test_get_coverage_missing_period_400(self):
        self.client.force_authenticate(
            User.objects.create_user(username='viewer2', password='pass')
        )
        resp = self.client.get(reverse('carbon:inventory-coverage'))
        self.assertEqual(resp.status_code, 400)

    def test_non_admin_post_403(self):
        self.client.force_authenticate(
            User.objects.create_user(username='pleb', password='pass')
        )
        resp = self.client.post(
            reverse('carbon:inventory-source-list'),
            {'org_unit': self.org.id, 'scope': 1, 'source_name': 'Nope'},
            format='json',
        )
        self.assertEqual(resp.status_code, 403)

    def test_admin_list_sources(self):
        user = User.objects.create_user(username='lead', password='pass')
        admins_group, _ = Group.objects.get_or_create(name='admins_group')
        ScopedRole.objects.create(user=user, group=admins_group, is_active=True)
        self.client.force_authenticate(user)

        resp = self.client.get(reverse('carbon:inventory-source-list'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)
