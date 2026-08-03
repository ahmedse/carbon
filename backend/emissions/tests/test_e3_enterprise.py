# File: emissions/tests/test_e3_enterprise.py
# E3 Enterprise Features — Excel reporting, SBTi progress, calculation integrity,
# auto-calculate signal, export audit.

from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from core.models import Module
from mdm.models import OrgUnit
from dataschema.models import DataTable, DataRow, DataField
from emissions.models import (
    ReportingPeriod, EmissionFactor, Calculation, CalculationRule,
    SBTiTarget, ExportAudit,
)
from emissions.services import (
    ReportService, CalculationEngineService, TargetService,
)


def _make_ef(**kwargs):
    """Create an EmissionFactor with required defaults."""
    defaults = {
        'source': 'Test source',
        'category': 'combustion',
        'activity_unit': 'unit',
    }
    defaults.update(kwargs)
    return EmissionFactor.objects.create(**defaults)


def _make_dt(cls, name, title):
    """Create a DataTable with module."""
    return DataTable.objects.create(
        name=name, title=title, module=cls.module,
    )


def _make_dr(cls, dt):
    """Create a DataRow."""
    return DataRow.objects.create(data_table=dt, values={})


class E3ReportingTests(TestCase):
    """E3-1: Excel reporting, by-gas, export audit."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='e3_reporter', password='test1234',
            is_superuser=True, is_staff=True,
        )
        cls.org_unit = OrgUnit.objects.create(name='E3 Report OU', code='E3R')
        cls.period = ReportingPeriod.objects.create(
            name='FY2026', start_date='2026-01-01', end_date='2026-12-31',
        )
        cls.module = Module.objects.create(name='E3 Module', org_unit=cls.org_unit)

        cls.ef_co2 = _make_ef(
            code='E3-CO2', name='CO2 Only', factor_value=2.5,
            co2_factor=2.5, ch4_factor=0, n2o_factor=0, scope=1, is_active=True,
            valid_from=date(2020, 1, 1),
        )
        cls.ef_ch4 = _make_ef(
            code='E3-CH4', name='CH4 Heavy', factor_value=0.1,
            co2_factor=0.0, ch4_factor=0.1, n2o_factor=0, scope=1, is_active=True,
            valid_from=date(2020, 1, 1),
        )
        cls.ef_n2o = _make_ef(
            code='E3-N2O', name='N2O Heavy', factor_value=0.05,
            co2_factor=0.0, ch4_factor=0.0, n2o_factor=0.05, scope=2, is_active=True,
            valid_from=date(2020, 1, 1),
        )

        dt = _make_dt(cls, 'e3_report_table', 'E3 Report Table')
        cls.dr1 = _make_dr(cls, dt)
        cls.dr2 = _make_dr(cls, dt)
        cls.dr3 = _make_dr(cls, dt)

        cls.calc_co2 = Calculation.objects.create(
            data_row=cls.dr1, module=cls.module, emission_factor=cls.ef_co2,
            activity_value=100, activity_unit='km',
            co2e_kg=250, co2_kg=250, ch4_kg=0, n2o_kg=0,
            scope=1, category='transport', reporting_year=2026,
            reporting_period=cls.period,
        )
        cls.calc_ch4 = Calculation.objects.create(
            data_row=cls.dr2, module=cls.module, emission_factor=cls.ef_ch4,
            activity_value=500, activity_unit='L',
            co2e_kg=50, co2_kg=0, ch4_kg=50, n2o_kg=0,
            scope=1, category='fuel', reporting_year=2026,
            reporting_period=cls.period,
        )
        cls.calc_n2o = Calculation.objects.create(
            data_row=cls.dr3, module=cls.module, emission_factor=cls.ef_n2o,
            activity_value=200, activity_unit='kg',
            co2e_kg=10, co2_kg=0, ch4_kg=0, n2o_kg=10,
            scope=2, category='fertilizer', reporting_year=2026,
            reporting_period=cls.period,
        )

    # ── By-gas totals ──────────────────────────────────────────────

    def test_by_gas_multiplies_gas_amounts(self):
        data = ReportService.generate_report(
            self.user, period_id=self.period.id, year=2026,
        )
        by_gas = data['by_gas']
        # _build_by_gas keys by scope name, not gas name
        self.assertIn('Scope 1 - Direct', by_gas)
        self.assertIn('Scope 2 - Indirect Energy', by_gas)
        self.assertAlmostEqual(by_gas['Scope 1 - Direct']['total_co2e_tonnes'], 0.3, places=1)
        self.assertAlmostEqual(by_gas['Scope 1 - Direct']['co2_tonnes'], 0.25, places=1)

    def test_by_gas_totals_match_calculation_sums(self):
        data = ReportService.generate_report(
            self.user, period_id=self.period.id, year=2026,
        )
        by_gas = data['by_gas']
        # Scope 1: 250 kg CO2 = 0.25 t, 50 kg CH4 totals 300 kg co2e = 0.3 t
        self.assertAlmostEqual(by_gas['Scope 1 - Direct']['total_co2e_tonnes'], 0.3, places=1)
        self.assertAlmostEqual(by_gas['Scope 2 - Indirect Energy']['total_co2e_tonnes'], 0.01, places=2)

    def test_by_gas_tonnes_conversion(self):
        data = ReportService.generate_report(
            self.user, period_id=self.period.id, year=2026,
        )
        by_gas = data['by_gas']
        # CO2 in scope 1: 250 kg → 0.25 tonnes
        self.assertAlmostEqual(by_gas['Scope 1 - Direct']['co2_tonnes'], 0.25, places=4)

    # ── Org-unit rollup ────────────────────────────────────────────

    def test_org_unit_rollup_present(self):
        data = ReportService.generate_report(
            self.user, period_id=self.period.id, year=2026,
        )
        self.assertIn('org_unit_rollup', data)

    # ── Excel generation ───────────────────────────────────────────

    def test_generate_xlsx_returns_nonzero_bytes(self):
        data = ReportService.generate_report(
            self.user, period_id=self.period.id, year=2026,
        )
        xlsx_bytes = ReportService.generate_report_xlsx(data, user=self.user)
        self.assertGreater(len(xlsx_bytes), 0)

    def test_generate_xlsx_writes_export_audit(self):
        data = ReportService.generate_report(
            self.user, period_id=self.period.id, year=2026,
        )
        count_before = ExportAudit.objects.count()
        ReportService.generate_report_xlsx(data, user=self.user)
        self.assertEqual(ExportAudit.objects.count(), count_before + 1)

        audit = ExportAudit.objects.latest('exported_at')
        self.assertEqual(audit.report_format, 'xlsx')
        self.assertEqual(audit.exported_by, self.user)
        self.assertGreater(audit.file_size_bytes, 0)

    def test_generate_report_csv_format(self):
        data = ReportService.generate_report(
            self.user, period_id=self.period.id, year=2026,
            report_format='csv',
        )
        self.assertEqual(data['format'], 'csv')

    def test_grouping_by_category(self):
        data = ReportService.generate_report(
            self.user, period_id=self.period.id, year=2026,
            grouping='category',
        )
        self.assertEqual(data['grouping'], 'category')
        self.assertIsInstance(data['rows'], list)

    def test_grouping_by_month(self):
        data = ReportService.generate_report(
            self.user, period_id=self.period.id, year=2026,
            grouping='month',
        )
        self.assertEqual(data['grouping'], 'month')


class E3SBTiProgressTests(TestCase):
    """E3-2: SBTi real progress tracking."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='e3_sbti', password='test1234',
            is_superuser=True, is_staff=True,
        )
        cls.org_unit = OrgUnit.objects.create(name='E3 SBTI OU', code='E3S')
        cls.module = Module.objects.create(name='SBTi Module', org_unit=cls.org_unit)

        cls.target = SBTiTarget.objects.create(
            name='E3 SBTi Target', org_unit=cls.org_unit,
            base_year=2020, target_year=2030, reduction_pct=50,
            target_type='absolute', status='approved', scope='1',
            created_by=cls.user,
        )

        cls.ef = _make_ef(
            code='SBTI-EF', name='SBTI Test EF', factor_value=1.0,
            scope=1, is_active=True, valid_from=date(2020, 1, 1),
        )

        dt = _make_dt(cls, 'e3_sbti_table', 'E3 SBTI Table')
        dr1 = _make_dr(cls, dt)
        dr2 = _make_dr(cls, dt)

        cls.baseline = Calculation.objects.create(
            data_row=dr1, module=cls.module, emission_factor=cls.ef,
            activity_value=1000, activity_unit='unit',
            co2e_kg=1000, scope=1, reporting_year=2020,
        )
        cls.current = Calculation.objects.create(
            data_row=dr2, module=cls.module, emission_factor=cls.ef,
            activity_value=750, activity_unit='unit',
            co2e_kg=750, scope=1, reporting_year=2024,
        )

    def test_progress_baseline_detected(self):
        progress = TargetService.get_progress(self.target.id, 2024)
        self.assertAlmostEqual(progress['baseline_tco2e'], 1.0, places=2)

    def test_progress_actual_detected(self):
        progress = TargetService.get_progress(self.target.id, 2024)
        self.assertAlmostEqual(progress['actual_tco2e'], 0.75, places=2)

    def test_progress_pct_is_reasonable(self):
        progress = TargetService.get_progress(self.target.id, 2024)
        self.assertIsNotNone(progress['progress_pct'])
        self.assertGreaterEqual(progress['progress_pct'], 0)
        self.assertLessEqual(progress['progress_pct'], 100)

    def test_progress_on_track_field(self):
        progress = TargetService.get_progress(self.target.id, 2024)
        self.assertIn('on_track', progress)
        self.assertIsInstance(progress['on_track'], bool)

    def test_progress_trajectory_present(self):
        progress = TargetService.get_progress(self.target.id, 2024)
        self.assertIsNotNone(progress['trajectory_tco2e'])
        self.assertGreaterEqual(progress['trajectory_tco2e'], 0.5)
        self.assertLessEqual(progress['trajectory_tco2e'], 1.0)

    def test_progress_no_baseline_no_crash(self):
        empty_target = SBTiTarget.objects.create(
            name='Empty Target', org_unit=self.org_unit,
            base_year=2010, target_year=2030, reduction_pct=30,
            target_type='absolute', status='committed', scope='2',
            created_by=self.user,
        )
        progress = TargetService.get_progress(empty_target.id, 2025)
        self.assertIsNotNone(progress)
        self.assertEqual(progress['baseline_tco2e'], 0)
        self.assertEqual(progress['progress_pct'], None)


class E3CalculationIntegrityTests(TestCase):
    """E3-3: Supersede pattern, factor validity, stale markers."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='e3_integrity', password='test1234',
            is_superuser=True, is_staff=True,
        )
        cls.org_unit = OrgUnit.objects.create(name='E3 Integrity OU', code='E3I')
        cls.module = Module.objects.create(name='Integrity Module', org_unit=cls.org_unit)

        cls.ef = _make_ef(
            code='INT-EF', name='Integrity EF', factor_value=3.0,
            scope=1, is_active=True, valid_from=date(2020, 1, 1),
        )

        dt = _make_dt(cls, 'e3_int_table', 'E3 Int Table')
        dr = _make_dr(cls, dt)
        cls.calc = Calculation.objects.create(
            data_row=dr, module=cls.module, emission_factor=cls.ef,
            activity_value=50, activity_unit='L',
            co2e_kg=50 * 3.0,
            scope=1, reporting_year=2026,
        )

    def test_recalculate_creates_successor(self):
        count_before = Calculation.objects.count()
        successor = CalculationEngineService.recalculate(self.calc)
        self.assertEqual(Calculation.objects.count(), count_before + 1)
        self.assertNotEqual(successor.pk, self.calc.pk)

    def test_recalculate_sets_superseded_by(self):
        successor = CalculationEngineService.recalculate(self.calc)
        self.calc.refresh_from_db()
        self.assertEqual(self.calc.superseded_by, successor)

    def test_recalculate_preserves_history(self):
        old_co2e = self.calc.co2e_kg
        successor = CalculationEngineService.recalculate(self.calc)
        self.calc.refresh_from_db()
        self.assertEqual(self.calc.co2e_kg, old_co2e)
        self.assertEqual(float(successor.co2e_kg), 150.0)

    def test_recalculate_rejects_expired_factor(self):
        self.ef.valid_to = timezone.now().date() - timedelta(days=1)
        self.ef.save()
        with self.assertRaises(ValueError):
            CalculationEngineService.recalculate(self.calc)

    def test_recalculate_rejects_future_factor(self):
        self.ef.valid_from = timezone.now().date() + timedelta(days=30)
        self.ef.save()
        with self.assertRaises(ValueError):
            CalculationEngineService.recalculate(self.calc)

    def test_successor_not_stale(self):
        successor = CalculationEngineService.recalculate(self.calc)
        self.assertFalse(successor.is_stale)

    def test_factor_edit_marks_calculations_stale(self):
        dt2 = _make_dt(self, 'e3_stale_table', 'E3 Stale Table')
        dr = _make_dr(self, dt2)
        calc = Calculation.objects.create(
            data_row=dr, module=self.module, emission_factor=self.ef,
            activity_value=10, co2e_kg=30,
            scope=1, reporting_year=2026,
        )
        self.assertFalse(calc.is_stale)

        self.ef.factor_value = 5.0
        self.ef.save()

        calc.refresh_from_db()
        self.assertTrue(calc.is_stale)


class E3AutoCalculateTests(TestCase):
    """E3-4: Auto-calculate on DataRow save (direct rule invocation)."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='e3_autocalc', password='test1234',
            is_superuser=True, is_staff=True,
        )
        cls.org_unit = OrgUnit.objects.create(name='E3 Auto OU', code='E3A')
        cls.module = Module.objects.create(name='AutoCalc Module', org_unit=cls.org_unit)
        cls.table = _make_dt(cls, 'autocalc_table', 'AutoCalc Table')
        cls.ef = _make_ef(
            code='AUTO-EF', name='AutoCalc EF', factor_value=2.0,
            scope=1, is_active=True, valid_from=date(2020, 1, 1),
        )

    def test_rule_calculate_for_row_creates_calculation(self):
        """E3-4: CalculationRule.calculate_for_row() produces a Calculation."""
        activity_field = DataField.objects.create(
            name='activity', label='Activity', type='number',
            data_table=self.table,
        )
        rule = CalculationRule.objects.create(
            name='Auto Rule', data_table=self.table,
            activity_field=activity_field,
            emission_factor=self.ef,
            auto_calculate=True,
            is_active=True,
        )

        row = DataRow.objects.create(
            data_table=self.table,
            values={'activity': '40'},
        )

        count_before = Calculation.objects.count()
        calc = rule.calculate_for_row(row)
        count_after = Calculation.objects.count()

        self.assertIsNotNone(calc)
        self.assertGreater(count_after, count_before)
        self.assertEqual(float(calc.co2e_kg), 80.0)  # 40 × 2.0

    def test_auto_calculate_flag_ignored_without_setting(self):
        """E3-4: auto_calculate=True on rule does not auto-fire without setting."""
        activity_field = DataField.objects.create(
            name='activity', label='Activity', type='number',
            data_table=self.table,
        )
        CalculationRule.objects.create(
            name='Manual Rule', data_table=self.table,
            activity_field=activity_field,
            emission_factor=self.ef,
            auto_calculate=True,
            is_active=True,
        )

        count_before = Calculation.objects.count()
        DataRow.objects.create(
            data_table=self.table,
            values={'activity': '100'},
        )
        # No auto-fire without EMISSIONS_AUTO_CALC setting
        self.assertEqual(Calculation.objects.count(), count_before)
