"""Regression test for BUG-02: Phase 2 GHG Protocol fields unpopulated on legacy calculations.

Legacy Calculation rows (created before migration 0011) have NULL
`scope2_method`, `emission_factor_snapshot`, and `factor_applied_at`.
The fix is a non-destructive data migration that backfills these from the
linked EmissionFactor. This test proves:
  1. Legacy-style rows start with the fields NULL (bug reproduction)
  2. After the backfill function runs, the fields are populated correctly
     (scope2_method defaults to location_based; snapshot mirrors the factor;
     factor_applied_at uses calculated_at)
"""

import importlib
from decimal import Decimal

from django.apps import apps as global_apps
from django.test import TestCase

from accounts.models import User
from core.models import Module
from dataschema.models import DataTable, DataField, DataRow
from emissions.models import (
    EmissionFactor,
    Calculation,
    ReportingPeriod,
)
from mdm.models import OrgUnit


class Phase2BackfillTests(TestCase):
    """Regression tests for the Phase 2 backfill data migration (0012)."""

    def setUp(self):
        self.user = User.objects.create_user(username='backfilluser', password='pass123')
        self.org_unit = OrgUnit.objects.create(name='Facilities', slug='facilities')
        self.module = Module.objects.create(
            name='Electricity', scope=2, org_unit=self.org_unit,
        )
        self.table = DataTable.objects.create(
            module=self.module, name='elec_usage',
        )
        self.field = DataField.objects.create(
            data_table=self.table, name='kwh', label='kWh',
            type='number', required=True,
        )
        self.period = ReportingPeriod.objects.create(
            name='FY 2026',
            start_date='2026-01-01',
            end_date='2026-12-31',
            status='open',
        )
        self.factor = EmissionFactor.objects.create(
            code='EG_GRID_2024',
            name='Egypt Grid Average',
            category='purchased_electricity',
            scope=2,
            factor_value=Decimal('0.4584'),
            factor_unit='kg CO2e',
            activity_unit='kwh',
            source='IEA 2024',
            co2_factor=Decimal('0.4584'),
            valid_from='2024-01-01',
        )
        self.row = DataRow.objects.create(
            data_table=self.table,
            values={'kwh': '1000'},
        )

    def _create_legacy_calculation(self):
        """Create a Calculation exactly like the pre-Phase-2 code path:
        direct objects.create() without scope2_method / snapshot / applied_at."""
        return Calculation.objects.create(
            data_row=self.row,
            module=self.module,
            emission_factor=self.factor,
            activity_value=Decimal('1000'),
            activity_unit='kwh',
            co2e_kg=Decimal('458.4'),
            scope=2,
            category='purchased_electricity',
            reporting_period=self.period,
            reporting_year=2026,
        )

    def test_legacy_calculation_starts_without_phase2_fields(self):
        """Bug reproduction: legacy rows have NULL Phase 2 fields."""
        calc = self._create_legacy_calculation()
        self.assertIsNone(calc.scope2_method)
        self.assertIsNone(calc.emission_factor_snapshot)
        self.assertIsNone(calc.factor_applied_at)

    def test_backfill_populates_phase2_fields(self):
        """After backfill: scope2_method=location_based, snapshot mirrors the
        linked factor, factor_applied_at set from calculated_at."""
        calc = self._create_legacy_calculation()

        # Run the migration's backfill function against the test DB.
        backfill_migration = importlib.import_module(
            'emissions.migrations.0012_phase2_backfill')
        backfill_migration.backfill_phase2_fields(global_apps, None)

        calc.refresh_from_db()
        self.assertEqual(calc.scope2_method, 'location_based')
        self.assertIsNotNone(calc.emission_factor_snapshot)
        snap = calc.emission_factor_snapshot
        self.assertEqual(snap['factor_code'], 'EG_GRID_2024')
        # factor_value is str(Decimal) at the field's decimal_places=10 scale;
        # the live calculate_for_row path (str(ef.factor_value)) stores the
        # same trailing-zero form, so the backfill must match it exactly.
        # NB: assert against a FRESH DB read — self.factor still holds the
        # in-memory Decimal('0.4584') before DB rounding.
        db_factor = EmissionFactor.objects.get(pk=self.factor.pk)
        self.assertEqual(snap['factor_value'], str(db_factor.factor_value))
        self.assertEqual(snap['source'], 'IEA 2024')
        self.assertIsNotNone(calc.factor_applied_at)
        # factor_applied_at should not predate the calculation
        self.assertGreaterEqual(calc.factor_applied_at, calc.calculated_at)

    def test_backfill_is_idempotent(self):
        """Running the backfill twice must not change populated values."""
        calc = self._create_legacy_calculation()

        backfill_migration = importlib.import_module(
            'emissions.migrations.0012_phase2_backfill')
        backfill_migration.backfill_phase2_fields(global_apps, None)
        calc.refresh_from_db()
        first_snapshot = calc.emission_factor_snapshot
        first_applied_at = calc.factor_applied_at

        backfill_migration.backfill_phase2_fields(global_apps, None)
        calc.refresh_from_db()
        self.assertEqual(calc.emission_factor_snapshot, first_snapshot)
        self.assertEqual(calc.factor_applied_at, first_applied_at)
        self.assertEqual(calc.scope2_method, 'location_based')

    def test_scope1_legacy_calculation_gets_snapshot_but_not_method(self):
        """Scope 1 calcs get snapshot + applied_at but scope2_method stays NULL."""
        module1 = Module.objects.create(name='NG', scope=1, org_unit=self.org_unit)
        table1 = DataTable.objects.create(module=module1, name='gas_usage')
        field1 = DataField.objects.create(
            data_table=table1, name='therms', label='Therms',
            type='number', required=True,
        )
        factor1 = EmissionFactor.objects.create(
            code='NAT_GAS',
            name='Natural Gas',
            category='stationary_combustion',
            scope=1,
            factor_value=Decimal('5.3'),
            activity_unit='therms',
            source='EPA 2024',
            valid_from='2024-01-01',
        )
        row1 = DataRow.objects.create(data_table=table1, values={'therms': '100'})
        calc = Calculation.objects.create(
            data_row=row1,
            module=module1,
            emission_factor=factor1,
            activity_value=Decimal('100'),
            activity_unit='therms',
            co2e_kg=Decimal('530.0'),
            scope=1,
            category='stationary_combustion',
            reporting_period=self.period,
            reporting_year=2026,
        )

        backfill_migration = importlib.import_module(
            'emissions.migrations.0012_phase2_backfill')
        backfill_migration.backfill_phase2_fields(global_apps, None)

        calc.refresh_from_db()
        self.assertIsNone(calc.scope2_method)
        self.assertIsNotNone(calc.emission_factor_snapshot)
        self.assertEqual(calc.emission_factor_snapshot['factor_code'], 'NAT_GAS')
        self.assertIsNotNone(calc.factor_applied_at)
