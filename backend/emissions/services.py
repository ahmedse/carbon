# File: emissions/services.py
# Business logic layer for the Carbon emissions domain.
#
# All business logic, aggregation, calculation orchestration, and
# report generation MUST live here. Views are thin — they parse
# request parameters, call services, and return responses.
#
# This enforces RULE_7 (thin views, fat services) and RULE_3
# (services import from core apps, never the reverse).

from decimal import Decimal
from collections import defaultdict
import hashlib
import json
import logging
from django.db.models import Sum, Count, Q, Window, F, Max, Exists, OuterRef
from django.db import transaction
from django.utils import timezone
from django.conf import settings

from .models import ReportingPeriod, EmissionFactor, Calculation, CalculationRule, VerificationRecord, ExportAudit
from core.models import Module
from core.services import NotificationService
from catalog.models import AssetProfile
from dataschema.models import DataRow, DataTable
from accounts.rbac_utils import get_visible_module_ids, get_visible_org_units

logger = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────

def scope_calculations(user, queryset):
    """Restrict a Calculation queryset to the modules the user may see.

    Superusers / global admins are unrestricted
    (get_visible_module_ids returns None).
    """
    allowed = get_visible_module_ids(user)
    if allowed is None:
        return queryset
    return queryset.filter(module_id__in=allowed)


SCOPE_NAMES = {
    1: 'Scope 1 - Direct',
    2: 'Scope 2 - Indirect Energy',
    3: 'Scope 3 - Value Chain',
}

MONTH_NAMES = [
    '', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
]


# ── Dashboard Service ──────────────────────────────────────────────────────

class DashboardService:
    """Compute scope breakdown, category breakdown, monthly trends, and DQ score."""

    @staticmethod
    def get_dashboard_data(user, *, period_id=None, year=None, start_date=None, end_date=None):
        base_qs = scope_calculations(user, Calculation.objects.all())
        qs = base_qs

        reporting_period = None
        if period_id:
            reporting_period = ReportingPeriod.objects.filter(id=period_id).first()
            if reporting_period:
                qs = qs.filter(reporting_period=reporting_period)
        elif start_date and end_date:
            qs = qs.filter(calculated_at__date__gte=start_date, calculated_at__date__lte=end_date)
        else:
            qs = qs.filter(reporting_year=year or timezone.now().year)

        scope_breakdown = DashboardService._build_scope_breakdown(qs)
        category_breakdown = DashboardService._build_category_breakdown(qs)
        monthly_trend = DashboardService._build_monthly_trend(qs)
        grand_total_kg = sum(s['total_kg'] for s in scope_breakdown)

        months_with_data = len([m for m in monthly_trend if m['total'] > 0])
        data_quality = min(100, int((months_with_data / 36) * 100 * 3))

        return {
            'reporting_period': reporting_period,
            'total_co2e_tonnes': round(grand_total_kg / 1000, 2),
            'scope_breakdown': [
                {**s, 'co2e_tonnes': round(s['total_kg'] / 1000, 2),
                 'percentage': round((s['total_kg'] / grand_total_kg * 100) if grand_total_kg else 0, 2)}
                for s in scope_breakdown
            ],
            'category_breakdown': [
                {**c, 'co2e_tonnes': round(c['total_kg'] / 1000, 2)}
                for c in category_breakdown
            ],
            'monthly_trend': monthly_trend,
            'data_quality_score': data_quality,
            'calculation_count': qs.count(),
            'last_updated': qs.order_by('-calculated_at').values_list('calculated_at', flat=True).first(),
        }

    @staticmethod
    def _build_scope_breakdown(qs):
        scope_data = qs.values('scope').annotate(
            total_kg=Sum('co2e_kg'), count=Count('id')
        ).order_by('scope')
        return [
            {
                'scope': s['scope'],
                'scope_name': SCOPE_NAMES.get(s['scope'], f"Scope {s['scope']}"),
                'total_kg': s['total_kg'] or Decimal('0'),
                'count': s['count'],
            }
            for s in scope_data
        ]

    @staticmethod
    def _build_category_breakdown(qs):
        category_data = qs.values('category', 'scope').annotate(
            total_kg=Sum('co2e_kg'), count=Count('id')
        ).order_by('scope', 'category')
        category_names = dict(EmissionFactor.CATEGORY_CHOICES)
        return [
            {
                'category': c['category'],
                'category_name': category_names.get(c['category'], c['category']),
                'scope': c['scope'],
                'total_kg': c['total_kg'] or Decimal('0'),
                'count': c['count'],
            }
            for c in category_data
        ]

    @staticmethod
    def _build_monthly_trend(qs):
        monthly_data = qs.values('reporting_month', 'scope').annotate(
            total_kg=Sum('co2e_kg')
        ).order_by('reporting_month', 'scope')

        monthly_dict = defaultdict(lambda: {'scope1': Decimal('0'), 'scope2': Decimal('0'), 'scope3': Decimal('0')})
        for m in monthly_data:
            month = m['reporting_month']
            if month:
                monthly_dict[month][f"scope{m['scope']}"] = m['total_kg'] or Decimal('0')

        trend = []
        for month_num in range(1, 13):
            data = monthly_dict.get(month_num, {})
            s1 = data.get('scope1', Decimal('0')) / 1000
            s2 = data.get('scope2', Decimal('0')) / 1000
            s3 = data.get('scope3', Decimal('0')) / 1000
            trend.append({
                'month': str(month_num).zfill(2),
                'month_name': MONTH_NAMES[month_num],
                'scope1': round(s1, 2),
                'scope2': round(s2, 2),
                'scope3': round(s3, 2),
                'total': round(s1 + s2 + s3, 2),
            })
        return trend


# ── Yearly Comparison Service ──────────────────────────────────────────────

class YearlyComparisonService:
    """Year-over-year comparison, baseline calculation, and SBTi trajectory."""

    @staticmethod
    def get_comparison(user, years):
        qs = scope_calculations(user, Calculation.objects.all())

        yearly_data = qs.filter(reporting_year__in=years).values('reporting_year').annotate(
            total_kg=Sum('co2e_kg'), count=Count('id')
        ).order_by('reporting_year')

        baseline_period = ReportingPeriod.objects.filter(is_baseline=True).first()
        baseline_year = baseline_period.start_date.year if baseline_period else 2020

        comparison = YearlyComparisonService._build_yearly_comparison(yearly_data, baseline_year)
        YearlyComparisonService._attach_scope_breakdown(qs, years, comparison)

        targets = YearlyComparisonService._build_sbti_trajectory(
            baseline_year, baseline_total=comparison[0]['baseline_total'] if comparison else None, years=years
        )

        return {
            'baseline_year': baseline_year,
            'baseline_total_tonnes': comparison[0]['baseline_total'] if comparison else None,
            'current_year': max(years) if years else None,
            'yearly_comparison': comparison,
            'targets': targets,
        }

    @staticmethod
    def _build_yearly_comparison(yearly_data, baseline_year):
        comparison = []
        baseline_total = None
        previous_total = None

        for y in yearly_data:
            year = y['reporting_year']
            total_tonnes = round((y['total_kg'] or Decimal('0')) / 1000, 2)

            if year == baseline_year:
                baseline_total = total_tonnes

            reduction = 0.0
            if baseline_total and baseline_total > 0:
                reduction = round(((baseline_total - total_tonnes) / baseline_total) * 100, 1)

            yoy = 0.0
            if previous_total and previous_total > 0:
                yoy = round(((total_tonnes - previous_total) / previous_total) * 100, 1)

            comparison.append({
                'year': year,
                'total_co2e_tonnes': total_tonnes,
                'calculation_count': y['count'],
                'reduction_from_baseline': reduction,
                'yoy_change': yoy,
                'is_baseline': year == baseline_year,
                'baseline_total': baseline_total,
            })
            previous_total = total_tonnes

        return comparison

    @staticmethod
    def _attach_scope_breakdown(qs, years, comparison):
        scope_by_year = qs.filter(reporting_year__in=years).values(
            'reporting_year', 'scope'
        ).annotate(total_kg=Sum('co2e_kg')).order_by('reporting_year', 'scope')

        scope_data = defaultdict(lambda: {'scope1': 0, 'scope2': 0, 'scope3': 0})
        for s in scope_by_year:
            scope_data[s['reporting_year']][f"scope{s['scope']}"] = round(
                (s['total_kg'] or Decimal('0')) / 1000, 2
            )

        for item in comparison:
            scopes = scope_data.get(item['year'], {})
            item['scope1'] = scopes.get('scope1', 0)
            item['scope2'] = scopes.get('scope2', 0)
            item['scope3'] = scopes.get('scope3', 0)

    @staticmethod
    def _build_sbti_trajectory(baseline_year, baseline_total, years):
        """Build SBTi-aligned trajectory from committed SBTiTarget records.

        Reads the SBTiTarget table (E3-2). Falls back to 50%-by-2030 linear
        interpolation only when no targets are found for the baseline year.
        Baseline year comes from ReportingPeriod.is_baseline (no hardcoded 2020).
        """
        from .models import SBTiTarget

        targets = []
        sbti_targets = SBTiTarget.objects.filter(
            base_year=baseline_year, status__in=['committed', 'approved']
        ).order_by('target_year')

        if sbti_targets.exists():
            # Build trajectory from committed SBTi targets
            reduction_by_year = {}
            for st in sbti_targets:
                reduction_by_year[st.target_year] = float(st.reduction_pct)

            # Sort target years
            target_years = sorted(reduction_by_year.keys())
            if not target_years:
                return targets

            for year in years:
                if year <= baseline_year:
                    pct = 0.0
                elif year >= target_years[-1]:
                    pct = reduction_by_year[target_years[-1]]
                else:
                    # Linear interpolation between nearest target years
                    prev_year = baseline_year
                    prev_pct = 0.0
                    next_year = target_years[-1]
                    next_pct = reduction_by_year[target_years[-1]]
                    for ty in target_years:
                        if ty <= year:
                            prev_year = ty
                            prev_pct = reduction_by_year[ty]
                        if ty >= year and ty < next_year:
                            next_year = ty
                            next_pct = reduction_by_year[ty]

                    if next_year == prev_year:
                        pct = prev_pct
                    else:
                        pct = prev_pct + (next_pct - prev_pct) * (year - prev_year) / (next_year - prev_year)

                target_value = round(float(baseline_total) * (1 - pct / 100), 2) if baseline_total else 0
                targets.append({
                    'year': year,
                    'target_co2e_tonnes': target_value,
                    'target_reduction_pct': round(pct, 1),
                })
        else:
            # Fallback: linear 50%-by-2030 (legacy behavior)
            target_reduction_by_2030 = 0.50
            years_to_2030 = 2030 - baseline_year if baseline_year else 10
            annual_reduction = target_reduction_by_2030 / years_to_2030

            for year in years:
                years_from_baseline = year - baseline_year if baseline_year else 0
                target_reduction = min(target_reduction_by_2030, annual_reduction * years_from_baseline)
                target_value = round(float(baseline_total) * (1 - target_reduction), 2) if baseline_total else 0
                targets.append({
                    'year': year,
                    'target_co2e_tonnes': target_value,
                    'target_reduction_pct': round(target_reduction * 100, 1),
                })

        return targets


# ── Report Service ─────────────────────────────────────────────────────────

class ReportService:
    """GHG Protocol report generation: JSON, CSV, and Excel (xlsx).

    Excel workbook (E3-1):
      - Summary sheet: scope → category breakdown
      - By-Gas sheet: CO2/CH4/N2O totals from Calculation gas fields
      - Detail Rows sheet: per-calculation rows
      - Org-Unit Rollup sheet: per org-unit totals
    """

    @staticmethod
    def generate_report(user, *, period_id=None, org_unit_id=None, year=None,
                        report_format='json', grouping='scope'):
        qs = scope_calculations(
            user,
            Calculation.objects.select_related(
                'module', 'module__org_unit', 'emission_factor',
                'data_row', 'data_row__data_table'
            ),
        )

        if org_unit_id:
            from mdm.models import OrgUnit
            try:
                ou = OrgUnit.objects.get(pk=org_unit_id)
                qs = qs.filter(module__org_unit_id__in=ou.get_descendant_ids(include_self=True))
            except OrgUnit.DoesNotExist:
                pass

        reporting_period = None
        if period_id:
            reporting_period = ReportingPeriod.objects.filter(id=period_id).first()
            if reporting_period:
                qs = qs.filter(reporting_period=reporting_period)
        else:
            qs = qs.filter(reporting_year=year or timezone.now().year)

        summary = ReportService._build_summary(qs)
        scope_details = ReportService._build_scope_details(qs)
        rows = ReportService._build_detail_rows(qs)

        # By-gas totals (E3-1)
        by_gas = ReportService._build_by_gas(qs)

        # Org-unit rollup (E3-1)
        org_unit_rollup = ReportService._build_org_unit_rollup(qs)

        # Grouping (month|category) applied to detail rows
        if grouping == 'month':
            rows = ReportService._group_by_month(rows, qs)
        elif grouping == 'category':
            rows = ReportService._group_by_category(rows)

        return {
            'title': f"Carbon Emissions Report - {reporting_period.name if reporting_period else year}",
            'reporting_period': reporting_period,
            'generated_at': timezone.now(),
            'summary': summary,
            'scope_details': scope_details,
            'by_gas': by_gas,
            'org_unit_rollup': org_unit_rollup,
            'rows': rows,
            'format': report_format,
            'grouping': grouping,
        }

    @staticmethod
    def generate_report_xlsx(data, user=None):
        """Generate an Excel workbook from report data.

        Returns bytes of the .xlsx file. Also writes an ExportAudit record.
        """
        import io
        import xlsxwriter

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})

        # Formats
        header_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#1a365d', 'font_color': 'white',
            'border': 1, 'text_wrap': True,
        })
        number_fmt = workbook.add_format({'num_format': '#,##0.00', 'border': 1})
        int_fmt = workbook.add_format({'num_format': '#,##0', 'border': 1})
        pct_fmt = workbook.add_format({'num_format': '0.0%', 'border': 1})
        cell_fmt = workbook.add_format({'border': 1})

        # ── Sheet 1: Summary ──
        ws_summary = workbook.add_worksheet('Summary')
        ws_summary.write(0, 0, 'Scope', header_fmt)
        ws_summary.write(0, 1, 'Category', header_fmt)
        ws_summary.write(0, 2, 'Emissions (tonnes CO2e)', header_fmt)
        ws_summary.write(0, 3, 'Calculation Count', header_fmt)
        ws_summary.set_column(0, 0, 20)
        ws_summary.set_column(1, 1, 30)
        ws_summary.set_column(2, 2, 22)
        ws_summary.set_column(3, 3, 18)

        row_idx = 1
        for sd in data.get('scope_details', []):
            for cat in sd.get('categories', []):
                ws_summary.write(row_idx, 0, sd['name'], cell_fmt)
                ws_summary.write(row_idx, 1, cat['name'], cell_fmt)
                ws_summary.write(row_idx, 2, cat['emissions_tonnes'], number_fmt)
                ws_summary.write(row_idx, 3, cat['count'], int_fmt)
                row_idx += 1

        # ── Sheet 2: By-Gas ──
        by_gas = data.get('by_gas', {})
        ws_gas = workbook.add_worksheet('By-Gas')
        ws_gas.write(0, 0, 'Scope', header_fmt)
        ws_gas.write(0, 1, 'CO2 (t)', header_fmt)
        ws_gas.write(0, 2, 'CH4 (t CO2e)', header_fmt)
        ws_gas.write(0, 3, 'N2O (t CO2e)', header_fmt)
        ws_gas.write(0, 4, 'Total CO2e (t)', header_fmt)
        ws_gas.set_column(0, 4, 20)

        gas_row = 1
        for scope_name, gas_data in by_gas.items():
            ws_gas.write(gas_row, 0, scope_name, cell_fmt)
            ws_gas.write(gas_row, 1, gas_data.get('co2_tonnes', 0), number_fmt)
            ws_gas.write(gas_row, 2, gas_data.get('ch4_tonnes', 0), number_fmt)
            ws_gas.write(gas_row, 3, gas_data.get('n2o_tonnes', 0), number_fmt)
            ws_gas.write(gas_row, 4, gas_data.get('total_co2e_tonnes', 0), number_fmt)
            gas_row += 1

        # ── Sheet 3: Detail Rows ──
        rows = data.get('rows', [])
        ws_detail = workbook.add_worksheet('Detail Rows')
        detail_headers = ['Module', 'Table', 'Category', 'Scope', 'Activity',
                          'Value', 'Unit', 'Factor', 'CO2e kg', 'CO2e t']
        for col, h in enumerate(detail_headers):
            ws_detail.write(0, col, h, header_fmt)
        ws_detail.set_column(0, 9, 18)

        for i, r in enumerate(rows[:5000], 1):
            ws_detail.write(i, 0, r.get('module', ''), cell_fmt)
            ws_detail.write(i, 1, r.get('table', ''), cell_fmt)
            ws_detail.write(i, 2, r.get('category', ''), cell_fmt)
            ws_detail.write(i, 3, r.get('scope', ''), int_fmt)
            ws_detail.write(i, 4, r.get('activity_description', ''), cell_fmt)
            ws_detail.write(i, 5, float(r.get('activity_value', 0)), number_fmt)
            ws_detail.write(i, 6, r.get('activity_unit', ''), cell_fmt)
            ws_detail.write(i, 7, r.get('emission_factor', ''), cell_fmt)
            ws_detail.write(i, 8, float(r.get('co2e_kg', 0)), number_fmt)
            ws_detail.write(i, 9, float(r.get('co2e_tonnes', 0)), number_fmt)

        # ── Sheet 4: Org-Unit Rollup ──
        ou_rollup = data.get('org_unit_rollup', [])
        ws_ou = workbook.add_worksheet('Org-Unit Rollup')
        ws_ou.write(0, 0, 'Org Unit', header_fmt)
        ws_ou.write(0, 1, 'Scope 1 (t)', header_fmt)
        ws_ou.write(0, 2, 'Scope 2 (t)', header_fmt)
        ws_ou.write(0, 3, 'Scope 3 (t)', header_fmt)
        ws_ou.write(0, 4, 'Total (t)', header_fmt)
        ws_ou.write(0, 5, 'Count', header_fmt)
        ws_ou.set_column(0, 5, 20)

        for i, ou in enumerate(ou_rollup, 1):
            ws_ou.write(i, 0, ou.get('org_unit_name', ''), cell_fmt)
            ws_ou.write(i, 1, ou.get('scope1_tonnes', 0), number_fmt)
            ws_ou.write(i, 2, ou.get('scope2_tonnes', 0), number_fmt)
            ws_ou.write(i, 3, ou.get('scope3_tonnes', 0), number_fmt)
            ws_ou.write(i, 4, ou.get('total_tonnes', 0), number_fmt)
            ws_ou.write(i, 5, ou.get('count', 0), int_fmt)

        workbook.close()
        file_bytes = output.getvalue()
        output.close()

        # Write ExportAudit
        if user and user.is_authenticated:
            config_dict = {
                'period_id': data.get('reporting_period', {}).get('id') if isinstance(data.get('reporting_period'), dict) else None,
                'org_unit_id': data.get('org_unit_id'),
                'format': 'xlsx',
                'grouping': data.get('grouping', 'scope'),
            }
            config_json = json.dumps(config_dict, sort_keys=True, default=str)
            config_hash = hashlib.sha256(config_json.encode()).hexdigest()
            ExportAudit.objects.create(
                exported_by=user,
                report_format='xlsx',
                config_hash=config_hash,
                row_count=len(rows),
                file_size_bytes=len(file_bytes),
                grouping=data.get('grouping', 'scope'),
            )

        return file_bytes

    @staticmethod
    def _build_by_gas(qs):
        """Aggregate CO2, CH4, N2O totals by scope from Calculation gas fields."""
        by_scope = {}
        for scope in [1, 2, 3]:
            scope_qs = qs.filter(scope=scope)
            agg = scope_qs.aggregate(
                co2=Sum('co2_kg'),
                ch4=Sum('ch4_kg'),
                n2o=Sum('n2o_kg'),
                total=Sum('co2e_kg'),
            )
            by_scope[SCOPE_NAMES.get(scope, f"Scope {scope}")] = {
                'co2_tonnes': round(float(agg['co2'] or 0) / 1000, 2),
                'ch4_tonnes': round(float(agg['ch4'] or 0) / 1000, 2),
                'n2o_tonnes': round(float(agg['n2o'] or 0) / 1000, 2),
                'total_co2e_tonnes': round(float(agg['total'] or 0) / 1000, 2),
            }
        return by_scope

    @staticmethod
    def _build_org_unit_rollup(qs):
        """Per-org-unit scope breakdown."""
        ou_data = qs.values(
            'module__org_unit_id', 'module__org_unit__name'
        ).annotate(
            scope1=Sum('co2e_kg', filter=Q(scope=1)),
            scope2=Sum('co2e_kg', filter=Q(scope=2)),
            scope3=Sum('co2e_kg', filter=Q(scope=3)),
            total=Sum('co2e_kg'),
            count=Count('id'),
        ).order_by('module__org_unit__name')

        return [
            {
                'org_unit_id': ou['module__org_unit_id'],
                'org_unit_name': ou['module__org_unit__name'] or 'Unknown',
                'scope1_tonnes': round(float(ou['scope1'] or 0) / 1000, 2),
                'scope2_tonnes': round(float(ou['scope2'] or 0) / 1000, 2),
                'scope3_tonnes': round(float(ou['scope3'] or 0) / 1000, 2),
                'total_tonnes': round(float(ou['total'] or 0) / 1000, 2),
                'count': ou['count'],
            }
            for ou in ou_data
        ]

    @staticmethod
    def _group_by_month(rows, qs):
        """Group detail rows by month."""
        monthly = qs.values('reporting_month').annotate(
            total_kg=Sum('co2e_kg'), count=Count('id')
        ).order_by('reporting_month')
        return [
            {
                'month': m['reporting_month'] or 0,
                'month_name': MONTH_NAMES[m['reporting_month']] if m['reporting_month'] and 1 <= m['reporting_month'] <= 12 else 'Unknown',
                'co2e_tonnes': round(float(m['total_kg'] or 0) / 1000, 2),
                'count': m['count'],
            }
            for m in monthly
        ]

    @staticmethod
    def _group_by_category(rows):
        """Group detail rows by category."""
        from collections import defaultdict
        grouped = defaultdict(lambda: {'co2e_tonnes': 0.0, 'count': 0})
        for r in rows:
            cat = r.get('category', 'Unknown')
            grouped[cat]['co2e_tonnes'] += float(r.get('co2e_tonnes', 0))
            grouped[cat]['count'] += 1
        return [
            {'category': k, 'co2e_tonnes': round(v['co2e_tonnes'], 2), 'count': v['count']}
            for k, v in sorted(grouped.items())
        ]

    @staticmethod
    def _build_summary(qs):
        scope_totals = qs.values('scope').annotate(
            total_kg=Sum('co2e_kg'), count=Count('id')
        ).order_by('scope')

        total_tonnes = Decimal('0')
        breakdown = []
        for s in scope_totals:
            t = s['total_kg'] or Decimal('0')
            tonnes = t / 1000
            total_tonnes += tonnes
            breakdown.append({
                'scope': s['scope'],
                'name': SCOPE_NAMES.get(s['scope'], f"Scope {s['scope']}"),
                'emissions_tonnes': round(tonnes, 2),
                'calculation_count': s['count'],
            })

        return {
            'total_emissions_tonnes': round(total_tonnes, 2),
            'scope_breakdown': breakdown,
        }

    @staticmethod
    def _build_scope_details(qs):
        scope_details = []
        for scope in [1, 2, 3]:
            scope_qs = qs.filter(scope=scope)
            categories = scope_qs.values('category').annotate(
                total_kg=Sum('co2e_kg'), count=Count('id')
            ).order_by('category')

            category_names = dict(EmissionFactor.CATEGORY_CHOICES)
            scope_total = sum(c['total_kg'] or 0 for c in categories)

            scope_details.append({
                'scope': scope,
                'name': SCOPE_NAMES.get(scope, f"Scope {scope}"),
                'total_tonnes': round(scope_total / 1000, 2),
                'categories': [
                    {
                        'name': category_names.get(c['category'], c['category']),
                        'code': c['category'],
                        'emissions_tonnes': round((c['total_kg'] or 0) / 1000, 2),
                        'count': c['count'],
                    }
                    for c in categories
                ],
            })
        return scope_details

    @staticmethod
    def _build_detail_rows(qs, limit=1000):
        rows = []
        for calc in qs[:limit]:
            rows.append({
                'module': calc.module.name if calc.module else '',
                'table': calc.data_row.data_table.title if calc.data_row and calc.data_row.data_table else '',
                'category': calc.category,
                'scope': calc.scope,
                'activity_description': calc.emission_factor.name if calc.emission_factor else '',
                'activity_value': calc.activity_value,
                'activity_unit': calc.activity_unit,
                'emission_factor': (
                    f"{calc.emission_factor.factor_value} "
                    f"{calc.emission_factor.factor_unit}/"
                    f"{calc.emission_factor.activity_unit}"
                ) if calc.emission_factor else '',
                'co2e_kg': calc.co2e_kg,
                'co2e_tonnes': round(calc.co2e_kg / 1000, 4),
            })
        return rows


# ── Calculation Engine Service ─────────────────────────────────────────────

class CalculationEngineService:
    """Orchestrate calculation rule execution with validation."""

    @staticmethod
    def execute_rule(rule, *, reporting_period=None, user=None, recalculate=False):
        """Execute a CalculationRule and return (created, skipped, errors)."""
        return rule.calculate_for_table(
            reporting_period=reporting_period,
            user=user,
            recalculate=recalculate,
        )

    @staticmethod
    def validate_calculation_request(rule_id, period_id=None):
        """Validate preconditions for a calculation request.

        Returns (rule, period, errors_dict).
        If errors_dict is non-empty, the request should be rejected.
        """
        errors = {}

        if not rule_id:
            errors['rule_id'] = 'Missing required parameter: rule_id'
            return None, None, errors

        rule = CalculationRule.objects.filter(id=rule_id).first()
        if not rule:
            errors['rule_id'] = 'Rule not found'
            return None, None, errors

        if not rule.is_active:
            errors['rule_id'] = 'Cannot execute an inactive calculation rule.'
            return None, None, errors

        period = None
        if period_id:
            period = ReportingPeriod.objects.filter(id=period_id).first()
            if not period:
                errors['reporting_period_id'] = 'Reporting period not found'
                return rule, None, errors
            if period.status in {'locked', 'verified', 'closed'}:
                errors['reporting_period_id'] = (
                    f'Reporting period is {period.status} and cannot be used for new calculations.'
                )
                return rule, period, errors

        rows = DataRow.objects.filter(data_table=rule.data_table, is_archived=False)
        if not rows.exists():
            errors['rows'] = 'No active rows found for the selected calculation rule.'
            return rule, period, errors

        incomplete = []
        for row in rows:
            raw_value = row.values.get(rule.activity_field.name)
            if raw_value is None or raw_value == '':
                incomplete.append(row.id)
                continue
            if rule.date_field and not row.values.get(rule.date_field.name):
                incomplete.append(row.id)

        if incomplete:
            errors['incomplete_rows'] = incomplete

        return rule, period, errors

    @staticmethod
    def batch_calculate(table_ids, period_id, user=None):
        """Run calculation rules across multiple tables.

        Args:
            table_ids: list of DataTable IDs
            period_id: ReportingPeriod ID
            user: request user (optional, passed to execute_rule)

        Returns:
            dict: {total_created, total_updated, total_skipped, total_errors,
                   per_table: {table_id: {created, updated, skipped, errors}}}
        """
        period = None
        if period_id:
            period = ReportingPeriod.objects.filter(id=period_id).first()
            if not period:
                return {
                    'total_created': 0, 'total_updated': 0,
                    'total_skipped': 0, 'total_errors': 1,
                    'per_table': {}, 'detail': 'Reporting period not found',
                }
            if period.status in {'locked', 'verified', 'closed'}:
                return {
                    'total_created': 0, 'total_updated': 0,
                    'total_skipped': 0, 'total_errors': 1,
                    'per_table': {}, 'detail': f'Reporting period is {period.status} and cannot be used for calculations.',
                }

        result = {
            'total_created': 0,
            'total_updated': 0,
            'total_skipped': 0,
            'total_errors': 0,
            'per_table': {},
        }
        for table_id in table_ids:
            rules = CalculationRule.objects.filter(
                data_table_id=table_id, is_active=True
            )
            if not rules.exists():
                result['per_table'][str(table_id)] = {
                    'created': 0, 'updated': 0, 'skipped': 0, 'errors': 0,
                    'note': 'no active rules',
                }
                continue

            t = {'created': 0, 'updated': 0, 'skipped': 0, 'errors': 0}
            for rule in rules:
                created, skipped, err_count = CalculationEngineService.execute_rule(
                    rule, reporting_period=period, user=user,
                )
                t['created'] += created
                t['skipped'] += skipped
                t['errors'] += err_count

            result['per_table'][str(table_id)] = t
            result['total_created'] += t['created']
            result['total_skipped'] += t['skipped']
            result['total_errors'] += t['errors']

        # Notify requesting user on batch completion
        if user is not None:
            count = result['total_created']
            _notify_user(user, 'batch_complete',
                         f"Batch calculation complete: {count} calculations")

        return result

    @staticmethod
    def recalculate(calculation):
        """Re-run a single Calculation with its existing parameters.

        Supersede pattern (E3-3): creates a NEW Calculation row, marks the
        old one with superseded_by pointing to the successor.  This preserves
        full audit history — nothing is ever deleted.
        """
        from datetime import date

        ef = calculation.emission_factor
        activity = calculation.activity_value

        # Check factor validity (E3-3)
        activity_date = calculation.activity_date or calculation.calculated_at.date()

        # Guard: Django .create() with string input may leave valid_from/valid_to
        # as strings rather than datetime.date objects.
        def _as_date(val):
            if val is None:
                return None
            if isinstance(val, str):
                return date.fromisoformat(val)
            if isinstance(val, date):
                return val
            return None

        valid_from = _as_date(ef.valid_from)
        valid_to = _as_date(ef.valid_to)

        if valid_to and valid_to < activity_date:
            raise ValueError(
                f"Emission factor '{ef.code}' expired on {valid_to} — "
                f"cannot calculate for activity date {activity_date}"
            )
        if valid_from and valid_from > activity_date:
            raise ValueError(
                f"Emission factor '{ef.code}' not yet valid (from {valid_from}) — "
                f"cannot calculate for activity date {activity_date}"
            )

        # Create successor
        successor = Calculation.objects.create(
            data_row=calculation.data_row,
            module=calculation.module,
            emission_factor=ef,
            activity_value=activity,
            activity_unit=calculation.activity_unit,
            co2e_kg=activity * ef.factor_value,
            co2_kg=(activity * ef.co2_factor) if ef.co2_factor else None,
            ch4_kg=(activity * ef.ch4_factor) if ef.ch4_factor else None,
            n2o_kg=(activity * ef.n2o_factor) if ef.n2o_factor else None,
            scope=calculation.scope,
            category=calculation.category,
            reporting_period=calculation.reporting_period,
            reporting_year=calculation.reporting_year,
            reporting_month=calculation.reporting_month,
            activity_date=calculation.activity_date,
            calculation_method='recalculated',
            is_stale=False,
        )

        # Mark old as superseded
        calculation.superseded_by = successor
        calculation.is_stale = False
        calculation.save(update_fields=['superseded_by', 'is_stale'])

        return successor

    @staticmethod
    def batch_recalculate(*, period_id=None, module_id=None, calculation_ids=None):
        """Re-run multiple calculations and return counts.

        Accepts filters (period_id, module_id) or an explicit list of
        calculation IDs.  Returns ``{total, recalculated, failed}``.
        """
        qs = Calculation.objects.select_related('emission_factor', 'reporting_period')

        if calculation_ids:
            qs = qs.filter(id__in=calculation_ids)
        else:
            if period_id:
                qs = qs.filter(reporting_period_id=period_id)
            if module_id:
                qs = qs.filter(module_id=module_id)
            if not period_id and not module_id:
                return {'total': 0, 'recalculated': 0, 'failed': 0}

        total = qs.count()
        recalculated = 0
        failed = 0
        for calc in qs.iterator():
            try:
                CalculationEngineService.recalculate(calc)
                recalculated += 1
            except Exception:
                failed += 1

        return {'total': total, 'recalculated': recalculated, 'failed': failed}


# ── Owner Service ──────────────────────────────────────────────────────────

class OwnerService:
    """Data-owner-scoped dashboard, summary, assets, and activity."""

    @staticmethod
    def get_org_units(user):
        """Return org units the user may access for owner pages.
        Returns None for unrestricted (superuser/staff/global visibility role)."""
        from accounts.models import ScopedRole
        from accounts.rbac_utils import VISIBILITY_ROLES
        if user.is_superuser or user.is_staff:
            return None  # unrestricted
        # Users with a global visibility role (org_unit=None, module=None) can see all org units
        if ScopedRole.objects.filter(
            user=user, is_active=True, org_unit=None, module=None,
            group__name__in=VISIBILITY_ROLES,
        ).exists():
            return None  # unrestricted
        return list(
            ScopedRole.objects.filter(user=user, is_active=True)
            .values_list('org_unit_id', flat=True).distinct()
        )

    @staticmethod
    def get_owner_dashboard(user, period_id=None):
        org_unit_ids = OwnerService.get_org_units(user)
        if org_unit_ids is not None and not org_unit_ids:
            return None  # no access

        # Reporting period
        reporting_period = None
        if period_id:
            reporting_period = ReportingPeriod.objects.filter(id=period_id).first()
        else:
            today = timezone.now().date()
            reporting_period = ReportingPeriod.objects.filter(
                start_date__lte=today, end_date__gte=today,
                status__in=['open', 'locked'],
            ).first()

        # Scoped calculations
        calc_qs = Calculation.objects.all()
        if org_unit_ids is not None:
            calc_qs = calc_qs.filter(module__org_unit_id__in=org_unit_ids)
        if reporting_period:
            calc_qs = calc_qs.filter(reporting_period=reporting_period)

        scope_breakdown = DashboardService._build_scope_breakdown(calc_qs)
        grand_total_kg = sum(s['total_kg'] for s in scope_breakdown)

        dq_summary = OwnerService._build_dq_summary(org_unit_ids)

        return {
            'reporting_period': reporting_period,
            'total_co2e_tonnes': round(grand_total_kg / 1000, 2),
            'scope_breakdown': [
                {
                    **s,
                    'co2e_tonnes': round(s['total_kg'] / 1000, 2),
                    'percentage': round(
                        (s['total_kg'] / grand_total_kg * 100) if grand_total_kg else 0, 2
                    ),
                }
                for s in scope_breakdown
            ],
            'category_breakdown': [],
            'monthly_trend': [],
            'data_quality_summary': dq_summary,
            'calculation_count': calc_qs.count(),
            'submission_status': (
                'pending'
                if reporting_period and reporting_period.status == 'open'
                else 'submitted'
            ),
        }

    @staticmethod
    def _build_dq_summary(org_unit_ids):
        """Build DQ metrics from AssetProfile for given org units."""
        if org_unit_ids is not None:
            asset_qs = AssetProfile.objects.filter(
                Q(data_table__module__org_unit_id__in=org_unit_ids)
                | Q(data_field__data_table__module__org_unit_id__in=org_unit_ids)
            )
        else:
            asset_qs = AssetProfile.objects.all()

        total = asset_qs.count()
        passing = asset_qs.filter(quality_status='passing').count()
        warning = asset_qs.filter(quality_status='warning').count()
        failing = asset_qs.filter(quality_status='failing').count()

        return {
            'quality_score': round((passing / total * 100), 1) if total > 0 else 0.0,
            'passing_count': passing,
            'warning_count': warning,
            'failing_count': failing,
            'unknown_count': total - passing - warning - failing,
            'total_assets': total,
        }

    @staticmethod
    def get_owner_summary(user):
        org_units = get_visible_org_units(user)
        if not org_units:
            return None

        org_unit = org_units[0]
        modules = Module.objects.filter(org_unit=org_unit).select_related('org_unit').order_by('name')
        module_ids = list(modules.values_list('id', flat=True))

        row_counts = dict(
            DataTable.objects.filter(module_id__in=module_ids)
            .annotate(row_count=Count('rows'))
            .values_list('module_id', 'row_count')
        )
        modules_with_data = sum(1 for mid in module_ids if row_counts.get(mid, 0) > 0)
        latest_row = DataRow.objects.filter(data_table__module__org_unit=org_unit).order_by('-created_at').first()

        return {
            'org_unit': {
                'id': org_unit.id,
                'name': org_unit.name,
                'code': getattr(org_unit, 'code', ''),
            },
            'modules': [
                {
                    'id': m.id,
                    'name': m.name,
                    'scope': m.scope,
                    'table_name': m.name.lower().replace(' ', '_'),
                }
                for m in modules
            ],
            'summary': {
                'total_modules': len(module_ids),
                'modules_with_data': modules_with_data,
                'latest_submission': latest_row.created_at.isoformat() if latest_row else None,
                'data_quality': {'passing': 0, 'warning': 0, 'failing': 0},
            },
        }

    @staticmethod
    def get_owner_assets(user, search=None, scope=None):
        org_units = get_visible_org_units(user)
        if not org_units:
            return None

        modules = Module.objects.filter(
            org_unit__in=org_units
        ).select_related('org_unit').order_by('name')

        if search:
            modules = modules.filter(name__icontains=search)
        if scope:
            modules = modules.filter(scope=scope)

        module_ids = list(modules.values_list('id', flat=True))
        table_row_counts = dict(
            DataTable.objects.filter(module_id__in=module_ids)
            .annotate(row_count=Count('rows'))
            .values_list('module_id', 'row_count')
        )
        last_entry_map = dict(
            DataRow.objects.filter(data_table__module_id__in=module_ids)
            .values('data_table__module_id')
            .annotate(last_created_at=Max('created_at'))
            .values_list('data_table__module_id', 'last_created_at')
        )

        return [
            {
                'id': m.id,
                'name': m.name,
                'scope': m.scope,
                'category': m.name.lower().replace(' ', '_'),
                'table_name': m.name.lower().replace(' ', '_'),
                'row_count': table_row_counts.get(m.id, 0),
                'last_entry': last_entry_map.get(m.id).isoformat() if last_entry_map.get(m.id) else None,
                'data_quality_status': 'passing' if table_row_counts.get(m.id, 0) else 'warning',
            }
            for m in modules
        ]

    @staticmethod
    def get_owner_activity(user):
        org_units = get_visible_org_units(user)
        if not org_units:
            return None

        calcs = Calculation.objects.filter(
            module__org_unit__in=org_units
        ).select_related('module', 'reporting_period').order_by('-calculated_at')[:10]

        return [
            {
                'id': c.id,
                'activity_type': 'submission',
                'module_id': c.module_id,
                'module_name': c.module.name,
                'scope': c.scope,
                'category': c.category,
                'co2e_tonnes': round((c.co2e_kg or Decimal('0')) / Decimal('1000'), 2),
                'reported_at': c.calculated_at.isoformat(),
                'period_name': c.reporting_period.name if c.reporting_period else None,
            }
            for c in calcs
        ]


# ── My Data Service ────────────────────────────────────────────────────────

class MyDataService:
    """Consolidated My Data endpoint logic for the data owner workspace."""

    @staticmethod
    def get_my_data(user):
        org_units = get_visible_org_units(user)
        if not org_units:
            return None

        org_unit = org_units[0]
        modules = Module.objects.filter(
            org_unit__in=org_units
        ).select_related('org_unit').order_by('name')

        module_ids = list(modules.values_list('id', flat=True))

        table_counts = dict(
            DataTable.objects.filter(module_id__in=module_ids, is_archived=False)
            .values('module_id').annotate(count=Count('id'))
            .values_list('module_id', 'count')
        )
        row_counts = dict(
            DataRow.objects.filter(data_table__module_id__in=module_ids, is_archived=False)
            .values('data_table__module_id').annotate(count=Count('id'))
            .values_list('data_table__module_id', 'count')
        )
        last_entry_map = dict(
            DataRow.objects.filter(data_table__module_id__in=module_ids)
            .values('data_table__module_id')
            .annotate(last_created_at=Max('created_at'))
            .values_list('data_table__module_id', 'last_created_at')
        )

        # Quality from AssetProfile
        quality_qs = AssetProfile.objects.filter(
            Q(data_table__module_id__in=module_ids)
            | Q(data_field__data_table__module_id__in=module_ids)
        )
        statuses = list(quality_qs.values_list('quality_status', flat=True))
        passing = statuses.count('passing')
        warning = statuses.count('warning')
        failing = statuses.count('failing')
        total_assets = len(statuses)

        module_quality = {}
        for asset in quality_qs.select_related(
            'data_table__module', 'data_field__data_table__module'
        ):
            mid = None
            if asset.data_table and asset.data_table.module_id:
                mid = asset.data_table.module_id
            elif (
                asset.data_field
                and asset.data_field.data_table
                and asset.data_field.data_table.module_id
            ):
                mid = asset.data_field.data_table.module_id
            if mid:
                module_quality.setdefault(mid, []).append(asset.quality_status)

        modules_data = []
        for m in modules:
            mid = m.id
            statuses_m = module_quality.get(mid, [])
            if 'failing' in statuses_m:
                qs = 'failing'
            elif 'warning' in statuses_m:
                qs = 'warning'
            elif 'passing' in statuses_m:
                qs = 'passing'
            else:
                qs = 'unknown'
            pc = statuses_m.count('passing')
            qscore = round(pc / len(statuses_m) * 100, 1) if statuses_m else None

            modules_data.append({
                'id': mid,
                'name': m.name,
                'scope': m.scope,
                'table_count': table_counts.get(mid, 0),
                'row_count': row_counts.get(mid, 0),
                'quality_status': qs,
                'quality_score': qscore,
                'last_entry': last_entry_map.get(mid).isoformat() if last_entry_map.get(mid) else None,
            })

        total_rows = sum(row_counts.values())
        latest_submission = max(last_entry_map.values()).isoformat() if last_entry_map else None

        recent_rows = DataRow.objects.filter(
            data_table__module_id__in=module_ids, is_archived=False
        ).select_related('data_table__module', 'created_by').order_by('-created_at')[:10]

        return {
            'org_unit': {
                'id': org_unit.id,
                'name': org_unit.name,
                'code': getattr(org_unit, 'code', ''),
            },
            'stats': {
                'total_modules': len(module_ids),
                'modules_with_data': sum(1 for mid in module_ids if row_counts.get(mid, 0) > 0),
                'total_rows': total_rows,
                'latest_submission': latest_submission,
                'data_quality': {
                    'passing': passing,
                    'warning': warning,
                    'failing': failing,
                    'unknown': total_assets - passing - warning - failing,
                    'total_assets': total_assets,
                },
            },
            'modules': modules_data,
            'recent_activity': [
                {
                    'module_name': r.data_table.module.name if r.data_table.module else None,
                    'action': 'data_entered',
                    'timestamp': r.created_at.isoformat(),
                    'rows': 1,
                    'user': r.created_by.username if r.created_by else None,
                }
                for r in recent_rows
            ],
        }


# ── Console Service ────────────────────────────────────────────────────────

class ConsoleService:
    """Aggregated console data for the Carbon landing page."""

    @staticmethod
    def get_console_data(user):
        today = timezone.now().date()

        # Active reporting period
        active_period = ReportingPeriod.objects.filter(
            status__in=['open', 'locked', 'submitted']
        ).order_by('-start_date').first()

        active_period_data = None
        if active_period:
            active_period_data = {
                'id': active_period.id,
                'name': active_period.name,
                'start_date': active_period.start_date.isoformat(),
                'end_date': active_period.end_date.isoformat(),
                'status': active_period.status,
                'days_remaining': (active_period.end_date - today).days,
            }

        visible_module_ids = get_visible_module_ids(user)
        module_filter = {} if visible_module_ids is None else {'id__in': visible_module_ids}

        module_agg = Module.objects.filter(**module_filter).aggregate(
            module_count=Count('id'),
            table_count=Count('data_tables', filter=Q(data_tables__is_archived=False)),
        )

        calc_qs = scope_calculations(
            user,
            Calculation.objects.select_related('module', 'reporting_period'),
        )
        recent_calcs = list(
            calc_qs.annotate(
                total_count=Window(Count('id')),
                total_kg_sum=Window(Sum('co2e_kg')),
            ).order_by('-calculated_at')[:10]
        )

        if recent_calcs:
            total_calculations = recent_calcs[0].total_count
            total_emissions_tonnes = round(float(recent_calcs[0].total_kg_sum or 0) / 1000, 2)
        else:
            total_calculations = 0
            total_emissions_tonnes = 0.0

        recent_activity = [
            {
                'id': c.id,
                'action': 'calculation_completed',
                'module_name': c.module.name if c.module else None,
                'timestamp': c.calculated_at.isoformat() if c.calculated_at else None,
                'detail': (
                    f"{c.activity_value} {c.activity_unit} \u2192 "
                    f"{round(c.co2e_kg, 1)} kg CO2e"
                ),
            }
            for c in recent_calcs
        ]

        # Asset quality
        asset_filter = {}
        if visible_module_ids is not None:
            asset_filter = {
                'data_table__module_id__in': visible_module_ids,
                'data_field__data_table__module_id__in': visible_module_ids,
            }
            asset_qs = AssetProfile.objects.filter(
                Q(**{k: v for k, v in asset_filter.items() if k.startswith('data_table')})
                | Q(**{k: v for k, v in asset_filter.items() if k.startswith('data_field')}),
                quality_score__isnull=False,
            )
        else:
            asset_qs = AssetProfile.objects.filter(quality_score__isnull=False)

        all_assets = list(
            asset_qs.select_related('data_table__module', 'data_field__data_table__module')
            .only('quality_score', 'data_table__module__name', 'data_field__data_table__module__name')
        )
        scores = [a.quality_score for a in all_assets if a.quality_score is not None]
        avg_quality_score = round(sum(scores) / len(scores), 1) if scores else 0.0

        dq_alerts = []
        for asset in all_assets:
            if asset.quality_score and asset.quality_score < 70:
                module_name = None
                if asset.data_table and asset.data_table.module:
                    module_name = asset.data_table.module.name
                elif asset.data_field and asset.data_field.data_table and asset.data_field.data_table.module:
                    module_name = asset.data_field.data_table.module.name
                dq_alerts.append({
                    'type': 'dq',
                    'module_name': module_name,
                    'score': asset.quality_score,
                    'threshold': 70,
                    'message': 'Data quality below 70% threshold',
                })
                if len(dq_alerts) >= 5:
                    break

        # Pending submissions
        pending_alerts = []
        if active_period:
            if visible_module_ids is not None:
                data_table_qs = DataTable.objects.filter(
                    module_id__in=visible_module_ids, is_archived=False,
                )
            else:
                data_table_qs = DataTable.objects.filter(is_archived=False)

            has_calc = Calculation.objects.filter(
                data_row=OuterRef('pk'), reporting_period=active_period,
            )
            pending_rows = (
                DataRow.objects
                .filter(data_table__in=data_table_qs, is_archived=False)
                .annotate(has_calc=Exists(has_calc))
                .filter(has_calc=False)
                .values('data_table__module_id', 'data_table__module__name')
                .annotate(pending_count=Count('id'))
                .order_by('-pending_count')[:5]
            )
            for pr in pending_rows:
                pending_alerts.append({
                    'type': 'pending_submission',
                    'module_id': pr['data_table__module_id'],
                    'module_name': pr['data_table__module__name'],
                    'pending_rows': pr['pending_count'],
                    'message': f"{pr['pending_count']} rows pending submission",
                })

        return {
            'active_period': active_period_data,
            'stats': {
                'total_modules': module_agg['module_count'] or 0,
                'total_tables': module_agg['table_count'] or 0,
                'total_calculations': total_calculations,
                'avg_quality_score': avg_quality_score,
                'total_emissions_tonnes': total_emissions_tonnes,
            },
            'alerts': dq_alerts + pending_alerts,
            'recent_activity': recent_activity,
        }


# ── Report Config Service ──────────────────────────────────────────────────

class ReportConfigService:
    """Generate report data from a saved ReportConfig."""

class TargetService:
    """Progress tracking for SBTi targets."""

    @staticmethod
    def get_progress(target_id, year):
        """Return % progress and trajectory vs actual for an SBTi target."""
        from .models import SBTiTarget, Calculation
        from decimal import Decimal

        target = SBTiTarget.objects.get(pk=target_id)
        scope_list = [s.strip() for s in target.scope.replace('+', ',').split(',') if s.strip()]

        # Actual emissions for the requested year
        actual = Calculation.objects.filter(
            module__org_unit_id=target.org_unit_id,
            reporting_year=year,
            scope__in=scope_list,
        ).aggregate(total=Sum('co2e_kg'))['total'] or Decimal('0')
        actual_tco2e = float(actual) / 1000.0

        # Baseline cohort (for base_year reduction math)
        base_qs = Calculation.objects.filter(
            module__org_unit_id=target.org_unit_id,
            reporting_year=target.base_year,
            scope__in=scope_list,
        )

        # Also try activity_date year if reporting_year rows don't exist yet
        if not base_qs.exists():
            base_qs = Calculation.objects.filter(
                module__org_unit_id=target.org_unit_id,
                activity_date__year=target.base_year,
                scope__in=scope_list,
            )
        base_total = base_qs.aggregate(total=Sum('co2e_kg'))['total'] or Decimal('0')
        base_tco2e = float(base_total) / 1000.0

        # Trajectory: linear interpolation from baseline to target
        trajectory = None
        span_years = float(target.target_year - target.base_year)
        if span_years > 0 and base_tco2e > 0:
            target_multiplier = 1.0 - (float(target.reduction_pct) / 100.0)
            target_tco2e = base_tco2e * target_multiplier
            # Linear: tco2e_at_year = base_tco2e - (year - base_year) * annual_reduction
            annual_reduction = (base_tco2e - target_tco2e) / span_years
            trajectory_tco2e = base_tco2e - (year - target.base_year) * annual_reduction
            if trajectory_tco2e < target_tco2e:
                trajectory_tco2e = target_tco2e  # don't overshoot target
            trajectory = round(trajectory_tco2e, 2)

        # Progress: (baseline - actual) / (baseline - target) * 100
        progress_pct = None
        if base_tco2e > 0 and span_years > 0:
            target_tco2e = base_tco2e * (1.0 - float(target.reduction_pct) / 100.0)
            reduction_needed = base_tco2e - target_tco2e
            reduction_achieved = base_tco2e - actual_tco2e
            if reduction_needed > 0:
                progress_pct = round((reduction_achieved / reduction_needed) * 100, 1)

        return {
            'target_id': target.id,
            'name': target.name,
            'base_year': target.base_year,
            'target_year': target.target_year,
            'target_type': target.target_type,
            'reduction_pct': float(target.reduction_pct),
            'baseline_tco2e': round(base_tco2e, 2),
            'actual_tco2e': round(actual_tco2e, 2),
            'trajectory_tco2e': trajectory,
            'progress_pct': progress_pct,
            'status': target.status,
            'year': year,
            'on_track': actual_tco2e <= trajectory if trajectory else None,
        }

    @staticmethod
    def mark_stale_for_factor(emission_factor, exclude_pk=None):
        """E3-3: Mark all non-superseded Calculations for a factor as stale.

        Returns the number of Calculations marked stale.
        """
        qs = Calculation.objects.filter(
            emission_factor=emission_factor,
            superseded_by__isnull=True,
            is_stale=False,
        )
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
        return qs.update(is_stale=True)


class ReportConfigService:
    """Generate report data from a saved ReportConfig."""

    @staticmethod
    def generate_from_config(config, user):
        from django.utils import timezone
        from mdm.models import OrgUnit

        qs = Calculation.objects.select_related(
            'reporting_period', 'module', 'module__org_unit'
        ).all()
        qs = scope_calculations(user, qs)

        if config.org_unit_id:
            try:
                ou = OrgUnit.objects.get(pk=config.org_unit_id)
                qs = qs.filter(module__org_unit_id__in=ou.get_descendant_ids(include_self=True))
            except OrgUnit.DoesNotExist:
                pass

        if config.reporting_period_id:
            qs = qs.filter(reporting_period_id=config.reporting_period_id)
        elif config.custom_start and config.custom_end:
            qs = qs.filter(
                activity_date__gte=config.custom_start,
                activity_date__lte=config.custom_end,
            )

        if config.ghg_scopes:
            qs = qs.filter(scope__in=config.ghg_scopes)

        if config.categories:
            qs = qs.filter(category__in=config.categories)

        scope_data = qs.values('scope').annotate(
            total_kg=Sum('co2e_kg'), count=Count('id')
        ).order_by('scope')
        category_data = qs.values('category').annotate(
            total_kg=Sum('co2e_kg'), count=Count('id')
        ).order_by('category')

        grand_total_kg = sum(s['total_kg'] or 0 for s in scope_data)

        scope_breakdown = []
        for s in scope_data:
            total_kg = s['total_kg'] or Decimal('0')
            scope_breakdown.append({
                'scope': s['scope'],
                'scope_name': SCOPE_NAMES.get(s['scope'], f"Scope {s['scope']}"),
                'co2e_tonnes': round(total_kg / 1000, 2),
                'percentage': round(
                    (total_kg / grand_total_kg * 100) if grand_total_kg else 0, 2
                ),
            })

        category_breakdown = []
        for c in category_data:
            category_breakdown.append({
                'category': c['category'],
                'co2e_tonnes': round((c['total_kg'] or 0) / 1000, 2),
                'calculation_count': c['count'],
            })

        module_breakdown = []
        if config.grouping == 'module':
            module_data = qs.values('module__name').annotate(
                total_kg=Sum('co2e_kg'), count=Count('id')
            ).order_by('module__name')
            for m in module_data:
                module_breakdown.append({
                    'module': m['module__name'],
                    'co2e_tonnes': round((m['total_kg'] or 0) / 1000, 2),
                    'calculation_count': m['count'],
                })

        return {
            'config_id': config.id,
            'config_name': config.name,
            'reporting_period_id': config.reporting_period_id,
            'date_range': {
                'start': config.custom_start.isoformat() if config.custom_start else None,
                'end': config.custom_end.isoformat() if config.custom_end else None,
            },
            'org_unit_id': config.org_unit_id,
            'total_co2e_tonnes': round(grand_total_kg / 1000, 2),
            'calculation_count': qs.count(),
            'scope_breakdown': scope_breakdown,
            'category_breakdown': category_breakdown,
            'module_breakdown': module_breakdown,
            'generated_at': timezone.now().isoformat(),
        }


# ── Notification helpers (module-level — not exported) ────────────────────

def _notify_user(user, verb, message, link=''):
    """Notify a single user. No-op if user is None."""
    NotificationService.notify(user, verb, message, link)


def _notify_period_event(period, verb, message):
    """Notify all data-owner users about a period lifecycle event."""
    from accounts.models import ScopedRole
    from django.contrib.auth import get_user_model
    User = get_user_model()
    # Find all active users with dataowners_group membership
    dataowner_ids = ScopedRole.objects.filter(
        group__name='dataowners_group', is_active=True,
    ).values_list('user_id', flat=True).distinct()
    for user in User.objects.filter(id__in=dataowner_ids):
        NotificationService.notify(user, verb, message)


# ── Verification Service ──────────────────────────────────────────────────

class VerificationService:
    """Orchestrates the reporting period verification workflow.

    Views delegate here — never contain business logic directly.
    """

    @staticmethod
    def submit(period, user):
        """Transition a draft period to submitted and create a pending VerificationRecord."""
        period.transition_to('submitted', user)
        VerificationRecord.objects.update_or_create(
            reporting_period=period,
            verifier=user,
            defaults={'status': 'pending', 'notes': ''},
        )
        # Notify data owners
        _notify_period_event(period, 'submitted',
                             f"Period \"{period.name}\" submitted for verification")
        return period

    @staticmethod
    def verify(period, user):
        """Verify a submitted period (admin only). Uses update_or_create so
        re-verification by the same admin updates instead of raising IntegrityError."""
        from accounts.rbac_utils import user_is_global_admin
        from django.core.exceptions import PermissionDenied

        if not user_is_global_admin(user):
            raise PermissionDenied("Only admins can verify reporting periods.")

        period.transition_to('verified', user)
        VerificationRecord.objects.update_or_create(
            reporting_period=period,
            verifier=user,
            defaults={'status': 'verified', 'verified_at': timezone.now()},
        )
        # Notify period creator
        _notify_user(period.created_by, 'verified',
                     f"Period \"{period.name}\" has been verified")
        return period

    @staticmethod
    def reject(period, user, notes=''):
        """Reject a submitted period with notes (admin only)."""
        from accounts.rbac_utils import user_is_global_admin
        from django.core.exceptions import PermissionDenied

        if not user_is_global_admin(user):
            raise PermissionDenied("Only admins can reject reporting periods.")

        period.transition_to('rejected', user)
        VerificationRecord.objects.update_or_create(
            reporting_period=period,
            verifier=user,
            defaults={
                'status': 'rejected',
                'notes': notes,
                'verified_at': timezone.now(),
            },
        )
        # Notify period creator
        msg = f"Period \"{period.name}\" has been rejected"
        if notes:
            msg += f": {notes}"
        _notify_user(period.created_by, 'rejected', msg)
        return period


# ── Period Lock Service ──────────────────────────────────────────────────

class PeriodLockService:
    """Orchestrates period lock/unlock and table-level lock propagation.

    When a period is locked, all DataTables linked via CalculationRule
    have their is_locked flag set to True, blocking data writes.
    Unlocking the period flips them back.
    """

    @staticmethod
    def open_period(period, user):
        """Transition a period to 'open' and unlock its tables."""
        period.transition_to('open', user)
        PeriodLockService.set_period_tables_locked(period, locked=False)
        return period

    @staticmethod
    def lock_period(period, user):
        """Transition a period to 'locked' and lock its tables."""
        period.transition_to('locked', user)
        PeriodLockService.set_period_tables_locked(period, locked=True)
        return period

    @staticmethod
    def close_period(period, user):
        """Transition a period to 'closed'."""
        period.transition_to('closed', user)
        return period

    @staticmethod
    def set_period_tables_locked(period, locked):
        """Find all DataTables linked via CalculationRule and toggle is_locked.

        Since CalculationRule has a data_table FK but no period FK,
        we lock all tables that have any active CalculationRule.
        Row-date-level enforcement is an ADR candidate — not built here.
        """
        table_ids = CalculationRule.objects.filter(
            is_active=True,
        ).values_list('data_table_id', flat=True).distinct()
        DataTable.objects.filter(id__in=table_ids).update(is_locked=locked)
