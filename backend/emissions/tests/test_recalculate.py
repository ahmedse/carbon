"""Tests for Calculation recalculate and batch-recalculate endpoints (E2-B6)."""

from django.urls import reverse
from rest_framework.test import APIClient
from django.test import TestCase
from django.contrib.auth.models import Group
from decimal import Decimal

from accounts.models import User, ScopedRole
from emissions.models import (
    EmissionFactor,
    Calculation,
    CalculationRule,
    ReportingPeriod,
)
from dataschema.models import DataTable, DataField, DataRow
from mdm.models import OrgUnit
from core.models import Module


class CalculationRecalculateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='recalcuser', password='pass123')
        self.org_unit = OrgUnit.objects.create(name='Facilities', slug='facilities')
        self.module = Module.objects.create(
            name='Natural Gas', scope=1, org_unit=self.org_unit,
        )
        self.table = DataTable.objects.create(
            module=self.module, name='gas_usage',
        )
        self.field = DataField.objects.create(
            data_table=self.table, name='therms', label='Therms',
            type='number', required=True,
        )
        self.period = ReportingPeriod.objects.create(
            name='FY 2026',
            start_date='2026-01-01',
            end_date='2026-12-31',
            status='open',
        )
        self.factor = EmissionFactor.objects.create(
            code='NAT_GAS',
            name='Natural Gas',
            category='stationary_combustion',
            scope=1,
            factor_value=Decimal('5.3'),
            activity_unit='therms',
            source='EPA 2024',
            valid_from='2024-01-01',
        )
        self.row = DataRow.objects.create(
            data_table=self.table,
            values={'therms': '100'},
        )
        self.calculation = Calculation.objects.create(
            data_row=self.row,
            module=self.module,
            emission_factor=self.factor,
            activity_value=Decimal('100'),
            activity_unit='therms',
            co2e_kg=Decimal('530.0'),
            scope=1,
            category='stationary_combustion',
            reporting_period=self.period,
            reporting_year=2026,
        )

        Group.objects.get_or_create(name='admins_group')
        ScopedRole.objects.create(
            user=self.user,
            group=Group.objects.get(name='admins_group'),
            is_active=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    # ── Single recalculate ────────────────────────────────────────────────

    def test_recalculate_single_returns_200(self):
        """POST /calculations/{id}/recalculate/ updates values and returns 200."""
        url = reverse('emissions:calculation-recalculate', args=[self.calculation.id])
        response = self.client.post(url)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        # 100 therms * 5.3 = 530
        self.assertEqual(Decimal(str(data['co2e_kg'])), Decimal('530.0'))
        self.assertEqual(Decimal(str(data['activity_value'])), Decimal('100'))
        self.assertEqual(data['emission_factor'], self.factor.id)

        # E3-3: old calc marked superseded, new calc has updated values
        self.calculation.refresh_from_db()
        self.assertIsNotNone(self.calculation.superseded_by_id)
        successor = Calculation.objects.get(id=self.calculation.superseded_by_id)
        self.assertEqual(successor.co2e_kg, Decimal('530.0'))

    def test_recalculate_404_when_not_found(self):
        url = reverse('emissions:calculation-recalculate', args=[99999])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)

    def test_recalculate_409_when_period_locked(self):
        self.period.status = 'locked'
        self.period.save()

        url = reverse('emissions:calculation-recalculate', args=[self.calculation.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 409)
        self.assertIn('locked', response.json()['detail'])

    def test_recalculate_409_when_period_verified(self):
        self.period.status = 'verified'
        self.period.save()

        url = reverse('emissions:calculation-recalculate', args=[self.calculation.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 409)
        self.assertIn('verified', response.json()['detail'])

    def test_recalculate_409_when_period_closed(self):
        self.period.status = 'closed'
        self.period.save()

        url = reverse('emissions:calculation-recalculate', args=[self.calculation.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 409)
        self.assertIn('closed', response.json()['detail'])

    # ── Batch recalculate ─────────────────────────────────────────────────

    def test_batch_recalculate_returns_200_with_counts(self):
        """POST /calculations/batch-recalculate/ with period_id returns counts."""
        # Create a second calculation so we have N > 1
        row2 = DataRow.objects.create(
            data_table=self.table,
            values={'therms': '200'},
        )
        Calculation.objects.create(
            data_row=row2,
            module=self.module,
            emission_factor=self.factor,
            activity_value=Decimal('200'),
            activity_unit='therms',
            co2e_kg=Decimal('9999'),  # will be overwritten to 1060
            scope=1,
            category='stationary_combustion',
            reporting_period=self.period,
            reporting_year=2026,
        )

        url = reverse('emissions:calculation-batch-recalculate')
        response = self.client.post(url, {
            'period_id': self.period.id,
        }, format='json')

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['total'], 2)
        self.assertEqual(data['recalculated'], 2)
        self.assertEqual(data['failed'], 0)

        # E3-3: supersede creates new rows; verify successor for row2
        row2_calc = Calculation.objects.filter(data_row=row2, superseded_by__isnull=True).first()
        self.assertIsNotNone(row2_calc)
        self.assertEqual(row2_calc.co2e_kg, Decimal('1060.0'))

    def test_batch_recalculate_by_module_id(self):
        url = reverse('emissions:calculation-batch-recalculate')
        response = self.client.post(url, {
            'module_id': self.module.id,
        }, format='json')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['total'], 1)
        self.assertEqual(data['recalculated'], 1)
        self.assertEqual(data['failed'], 0)

    def test_batch_recalculate_by_calculation_ids(self):
        url = reverse('emissions:calculation-batch-recalculate')
        response = self.client.post(url, {
            'calculation_ids': [self.calculation.id],
        }, format='json')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['total'], 1)
        self.assertEqual(data['recalculated'], 1)
        self.assertEqual(data['failed'], 0)

    def test_batch_recalculate_400_no_params(self):
        url = reverse('emissions:calculation-batch-recalculate')
        response = self.client.post(url, {}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('period_id', response.json()['detail'])

    def test_batch_recalculate_409_when_period_locked(self):
        self.period.status = 'locked'
        self.period.save()

        url = reverse('emissions:calculation-batch-recalculate')
        response = self.client.post(url, {
            'period_id': self.period.id,
        }, format='json')
        self.assertEqual(response.status_code, 409)
        self.assertIn('locked', response.json()['detail'])
