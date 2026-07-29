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
from django.db.models import Sum, Count, Q, Window, F, Max, Exists, OuterRef
from django.utils import timezone

from .models import ReportingPeriod, EmissionFactor, Calculation, CalculationRule
from core.models import Module
from catalog.models import AssetProfile
from dataschema.models import DataRow, DataTable
from accounts.rbac_utils import get_visible_module_ids, get_visible_org_units


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
    def get_dashboard_data(user, *, period_id=None, year=None):
        base_qs = scope_calculations(user, Calculation.objects.all())
        qs = base_qs

        reporting_period = None
        if period_id:
            reporting_period = ReportingPeriod.objects.filter(id=period_id).first()
            if reporting_period:
                qs = qs.filter(reporting_period=reporting_period)
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
            'calculation_count': base_qs.count(),
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
        """SBTi 1.5°C aligned: 50% reduction by 2030."""
        target_reduction_by_2030 = 0.50
        years_to_2030 = 2030 - baseline_year if baseline_year else 10
        annual_reduction = target_reduction_by_2030 / years_to_2030

        targets = []
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
    """GHG Protocol report generation with scope details and optional CSV."""

    @staticmethod
    def generate_report(user, *, period_id=None, org_unit_id=None, year=None, report_format='json'):
        qs = scope_calculations(
            user,
            Calculation.objects.select_related(
                'module', 'emission_factor', 'data_row', 'data_row__data_table'
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

        return {
            'title': f"Carbon Emissions Report - {reporting_period.name if reporting_period else year}",
            'reporting_period': reporting_period,
            'generated_at': timezone.now(),
            'summary': summary,
            'scope_details': scope_details,
            'rows': rows,
            'format': report_format,
        }

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
            if period.status == 'closed':
                errors['reporting_period_id'] = (
                    'Reporting period is closed and cannot be used for new calculations.'
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

        return result


# ── Owner Service ──────────────────────────────────────────────────────────

class OwnerService:
    """Data-owner-scoped dashboard, summary, assets, and activity."""

    @staticmethod
    def get_org_units(user):
        """Return org units the user may access for owner pages."""
        from accounts.models import ScopedRole
        if user.is_superuser or user.is_staff:
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
        from .models import SBTiTarget, Calculation
        from decimal import Decimal

        target = SBTiTarget.objects.get(pk=target_id)
        scopes = target.scope.replace('+', ',').split(',')

        actual = Calculation.objects.filter(
            module__org_unit_id=target.org_unit_id,
            reporting_year=year,
            scope__in=scopes,
        ).aggregate(total=Sum('co2e_kg'))['total'] or Decimal('0')

        # Progress = how much of the reduction achieved (simplified baseline model)
        return {
            'target_id': target.id,
            'name': target.name,
            'base_year': target.base_year,
            'target_year': target.target_year,
            'target_type': target.target_type,
            'reduction_pct': float(target.reduction_pct),
            'actual_tco2e': float(actual),
            'status': target.status,
        }


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
