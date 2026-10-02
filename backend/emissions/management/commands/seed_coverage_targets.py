"""Seed a small, realistic set of CoverageTargets for local development.

Local dev only. Idempotent: re-running never duplicates a target or a task.

HONESTY RULES (do not relax):
  * Real campuses / org units only, resolved from ``mdm.OrgUnit`` by name.
  * Real owners only, resolved from ``accounts.User`` by username *within*
    ``emissions.views.eligible_owner_queryset``; a username the eligibility rule
    rejects (probe / shell / schema / bare fixture) and a missing username both
    leave the owner null and are reported, never invented. An existing seeded
    row owned by an ineligible account is REPAIRED in place (owner FK updated),
    never duplicated.
  * No ``Calculation`` is created, no kilogram is written, no
    ``InventorySourceStatus`` is written. Coverage streams stay the sole
    Missing / Entered / Excluded reporter, so progress legitimately reads
    empty / absent until a real row exists on the period.
  * Periods 15 / 16 (and every period status) are never touched.
  * Targets are guarded by (reporting_period, org_unit, scope,
    scope3_category, name) — the model's unique binding.

Progress is DERIVED (``emissions.coverage_targets.target_progress``); this
command never stores a percent or a state on the target.
"""
from __future__ import annotations

from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from emissions.models import CoverageTarget, CoverageTask, EmissionFactor, InventorySource
from emissions.services import single_open_period
from mdm.models import OrgUnit


# Each spec is anchored on a REAL campus and a REAL org unit. ``unit`` defaults
# to the campus itself (campus-level target: progress keys on the campus, where
# the InventorySource rows live). A narrower ``unit`` is a real descendant.
TARGET_SPECS = [
    {
        'campus': 'Smart Village',
        'unit': 'Smart Village',
        'scope': '1+2',
        'scope3_category': None,
        'name': 'Scope 1+2 coverage — Smart Village',
        'goal_kind': 'percent',
        'goal_value': '90.0000',
        'goal_unit': '',
        'min_quality_tier': 3,
        'due_date': date(2026, 12, 31),
        'owner': 'data.smartvillage',
        'notes': 'Campus-level coverage goal across Scope 1 and 2.',
        'tasks': [
            {
                'task_type': 'fill_gap',
                'title': 'Close Smart Village Scope 1 diesel stream',
                'detail': 'Bind the on-site generator diesel row on the open period.',
                'source_name': 'Diesel generators (on-site power)',
            },
            {
                'task_type': 'bind_data_product',
                'title': 'Bind Smart Village electricity contract',
                'detail': 'Bind the monthly electricity contract already in the catalogue.',
                'table_name': 'monthly_electricity',
            },
            {
                'task_type': 'complete_rows',
                'title': 'Complete Smart Village electricity rows through June 2026',
                'detail': 'Rows must reach June 2026 before the stream can settle.',
                'table_name': 'monthly_electricity',
                'through_month': date(2026, 6, 1),
            },
        ],
    },
    {
        'campus': 'Smart Village',
        'unit': 'Smart Village',
        'scope': '2',
        'scope3_category': None,
        'name': 'Scope 2 electricity (location-based) — Smart Village',
        'goal_kind': 'absolute',
        'goal_value': '500000.0000',
        'goal_unit': 'kgCO2e',
        'min_quality_tier': 2,
        'due_date': date(2026, 9, 30),
        'owner': 'data.smartvillage',
        'notes': 'Absolute target. Measured kilograms come only from real calculations.',
        'tasks': [
            {
                'task_type': 'secure_factor',
                'title': 'Secure the Egypt grid emission factor',
                'detail': 'The active grid factor must stay in force for the year.',
                'factor_code': 'EG_GRID_2024',
            },
            {
                'task_type': 'fill_gap',
                'title': 'Close Smart Village purchased electricity stream',
                'detail': 'Enter the purchased electricity row on the open period.',
                'source_name': 'Purchased electricity',
            },
        ],
    },
    {
        'campus': 'Smart Village',
        'unit': 'Smart Village',
        'scope': '3',
        'scope3_category': 5,
        'name': 'Scope 3 Cat 5 waste coverage — Smart Village',
        'goal_kind': 'percent',
        'goal_value': '80.0000',
        'goal_unit': '',
        'min_quality_tier': 4,
        'due_date': date(2026, 11, 30),
        # A seeded owner must itself satisfy ``eligible_owner_queryset`` — the
        # bare fixture account this used to name (carbon_lead_user) is exactly
        # what the owner picker now rejects. Use the real org-scoped data-owner
        # account for the campus, the same one the other Smart Village targets use.
        'owner': 'data.smartvillage',
        'notes': 'Scope 3 category 5 (waste generated in operations).',
        'tasks': [
            {
                'task_type': 'fill_gap',
                'title': 'Close Smart Village waste disposal stream',
                'detail': 'Enter the waste disposal tonnage on the open period.',
                'source_name': 'Waste disposal',
            },
            {
                'task_type': 'other',
                'title': 'Confirm waste treatment route',
                'detail': 'Verify the treatment route before the factor is applied.',
            },
        ],
    },
    {
        'campus': 'Smart Village',
        'unit': 'Facilities & Utilities',
        'scope': '1+2',
        'scope3_category': None,
        'name': 'Scope 1+2 coverage — Facilities & Utilities',
        'goal_kind': 'percent',
        'goal_value': '85.0000',
        'goal_unit': '',
        'min_quality_tier': 4,
        'due_date': date(2026, 12, 31),
        'owner': 'data.smartvillage',
        'notes': (
            'Optional narrower unit inside the campus. Progress still keys on '
            'org_unit and stays empty until this unit has its own streams.'
        ),
        'tasks': [
            {
                'task_type': 'bind_data_product',
                'title': 'Bind the Smart Village generator diesel log',
                'detail': 'Bind the real generator diesel contract table.',
                'table_name': 'sv_generator_diesel',
            },
            {
                'task_type': 'other',
                'title': 'Review sub-unit scope split',
                'detail': 'Decide which campus streams sub-divide into this unit.',
            },
        ],
    },
    {
        'campus': 'Abu Qir',
        'unit': 'Abu Qir',
        'scope': '1+2',
        'scope3_category': None,
        'name': 'Scope 1+2 coverage — Abu Qir',
        'goal_kind': 'percent',
        'goal_value': '90.0000',
        'goal_unit': '',
        'min_quality_tier': 3,
        'due_date': date(2026, 12, 31),
        'owner': 'data.abuqir',
        'notes': 'Campus-level coverage goal across Scope 1 and 2.',
        'tasks': [
            {
                'task_type': 'fill_gap',
                'title': 'Close Abu Qir diesel stream',
                'detail': 'Enter the stationary + mobile diesel row on the open period.',
                'source_name': 'Diesel (stationary + mobile)',
            },
            {
                'task_type': 'bind_data_product',
                'title': 'Bind the Abu Qir monthly fuel contract',
                'detail': 'Bind the real monthly fuel contract table.',
                'table_name': 'monthly_fuel',
            },
        ],
    },
    {
        'campus': 'Aswan South Valley',
        'unit': 'Aswan South Valley',
        'scope': '1+2+3',
        'scope3_category': None,
        'name': 'Scope 1+2+3 coverage — Aswan South Valley',
        'goal_kind': 'percent',
        'goal_value': '75.0000',
        'goal_unit': '',
        'min_quality_tier': 4,
        'due_date': date(2026, 12, 31),
        'owner': 'data.southvalley',
        'notes': 'Full-inventory coverage goal.',
        'tasks': [
            {
                'task_type': 'fill_gap',
                'title': 'Close South Valley purchased electricity stream',
                'detail': 'Enter the purchased electricity row on the open period.',
                'source_name': 'Purchased electricity',
            },
            {
                'task_type': 'complete_rows',
                'title': 'Complete South Valley activity rows through June 2026',
                'detail': 'Rows must reach June 2026 before the stream can settle.',
                'table_name': 'scope12_activity',
                'through_month': date(2026, 6, 1),
            },
        ],
    },
    {
        'campus': 'New Alamein',
        'unit': 'New Alamein',
        'scope': '2',
        'scope3_category': None,
        'name': 'Scope 2 electricity coverage — New Alamein',
        'goal_kind': 'percent',
        'goal_value': '100.0000',
        'goal_unit': '',
        'min_quality_tier': 3,
        'due_date': date(2026, 10, 31),
        'owner': 'data.alamein',
        'notes': 'Campus-level Scope 2 completeness goal.',
        'tasks': [
            {
                'task_type': 'fill_gap',
                'title': 'Close New Alamein electricity stream',
                'detail': 'Enter the New Alamein electricity row on the open period.',
                'source_name': 'Alamein',
            },
            {
                'task_type': 'other',
                'title': 'Confirm New Alamein meter coverage',
                'detail': 'Confirm every metered supply is represented.',
            },
        ],
    },
    {
        'campus': 'فرع العلمين — Alamein Campus',
        'unit': 'فرع العلمين — Alamein Campus',
        'scope': '1+2',
        'scope3_category': None,
        'name': 'Scope 1+2 coverage — Alamein Campus',
        'goal_kind': 'percent',
        'goal_value': '85.0000',
        'goal_unit': '',
        'min_quality_tier': 3,
        'due_date': date(2026, 12, 31),
        'owner': 'alamein.finance',
        'notes': 'Campus-level coverage goal across Scope 1 and 2.',
        'tasks': [
            {
                'task_type': 'bind_data_product',
                'title': 'Bind the Alamein medical generator log',
                'detail': 'Bind the real generator contract table for the campus.',
                'table_name': 'med_gen_log',
            },
            {
                'task_type': 'other',
                'title': 'Confirm Alamein campus boundary',
                'detail': 'Confirm the campus boundary before stream declaration.',
            },
        ],
    },
]


class Command(BaseCommand):
    help = (
        'Idempotently seed realistic CoverageTargets + tasks on the open period. '
        'Local dev only; writes no kilogram, no Calculation, no stream state.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--period',
            type=int,
            default=None,
            help='ReportingPeriod id (default: the single open period).',
        )

    def handle(self, *args, **options):
        from emissions.models import ReportingPeriod

        period = None
        if options.get('period'):
            period = ReportingPeriod.objects.filter(pk=options['period']).first()
            if period is None:
                raise CommandError(f"ReportingPeriod {options['period']} not found")
        else:
            period = single_open_period()
        if period is None:
            raise CommandError('No single open period; refusing to seed.')

        # The eligibility rule the owner picker uses is the single source of
        # truth for who may own a target. Resolve against it and repair any
        # seeded row that a previous seed bound to an ineligible fixture.
        from emissions.views import eligible_owner_queryset

        eligible_ids = set(eligible_owner_queryset().values_list('id', flat=True))

        created_targets = 0
        existing_targets = 0
        created_tasks = 0
        repaired_owners = 0
        missing_owners = []
        missing_units = []

        with transaction.atomic():
            for spec in TARGET_SPECS:
                campus = OrgUnit.objects.filter(
                    org_type='campus', name=spec['campus'], is_active=True
                ).first()
                if campus is None:
                    missing_units.append(spec['campus'])
                    continue

                org_unit = self._resolve_unit(campus, spec['unit'])
                if org_unit is None:
                    missing_units.append(f"{spec['unit']} ({spec['campus']})")
                    continue

                owner = self._resolve_owner(spec.get('owner'))
                if spec.get('owner') and owner is None:
                    missing_owners.append(spec['owner'])

                defaults = {
                    'campus': campus,
                    'goal_kind': spec['goal_kind'],
                    'goal_value': spec['goal_value'],
                    'goal_unit': spec['goal_unit'],
                    'min_quality_tier': spec['min_quality_tier'],
                    'due_date': spec['due_date'],
                    'owner': owner,
                    'status': 'active',
                    'notes': spec['notes'],
                }
                target, created = CoverageTarget.objects.get_or_create(
                    reporting_period=period,
                    org_unit=org_unit,
                    scope=spec['scope'],
                    scope3_category=spec['scope3_category'],
                    name=spec['name'],
                    defaults=defaults,
                )
                if created:
                    created_targets += 1
                else:
                    existing_targets += 1
                    repair_fields = []
                    # Keep the campus link honest if an older row lacks it.
                    if target.campus_id != campus.id:
                        target.campus = campus
                        repair_fields.append('campus')
                    # Repair — never duplicate — a seeded row whose owner the
                    # eligibility rule rejects (e.g. an old bare fixture
                    # account). A legitimately-set eligible owner is untouched.
                    if target.owner_id is None or target.owner_id not in eligible_ids:
                        if owner is not None:
                            target.owner = owner
                            repair_fields.append('owner')
                            repaired_owners += 1
                    if repair_fields:
                        target.save(update_fields=repair_fields)

                for task_spec in spec.get('tasks', []):
                    if self._upsert_task(target, task_spec, campus, eligible_ids):
                        created_tasks += 1

        self.stdout.write(self.style.SUCCESS(
            f"seed_coverage_targets: period={period.id} ({period.name!r}) "
            f"targets created={created_targets} existing={existing_targets} "
            f"owners repaired={repaired_owners} "
            f"tasks created={created_tasks}"
        ))
        if missing_units:
            self.stdout.write(self.style.WARNING(
                f"missing org units (skipped): {', '.join(missing_units)}"
            ))
        if missing_owners:
            self.stdout.write(self.style.WARNING(
                f"missing owners (left null): {', '.join(missing_owners)}"
            ))

    @staticmethod
    def _resolve_unit(campus, name):
        if name == campus.name:
            return campus
        ids = campus.get_descendant_ids(include_self=False)
        if not ids:
            return None
        return OrgUnit.objects.filter(id__in=ids, name=name, is_active=True).first()

    @staticmethod
    def _resolve_owner(username):
        """Resolve an owner only if the eligibility rule itself accepts them.

        A reserved automation / test username, a user with no real signal, or a
        missing username all resolve to ``None`` — the caller reports it and
        the target keeps (or gets) a null owner rather than an ineligible one.
        """
        if not username:
            return None
        from emissions.views import eligible_owner_queryset

        return eligible_owner_queryset().filter(username=username).first()

    def _upsert_task(self, target, spec, campus, eligible_ids=None):
        """Create the task when absent; return True when a row was created.

        An existing task whose owner is ineligible (a fixture inherited from an
        older seed) is repaired in place to the target's eligible owner.
        """
        source = None
        if spec.get('source_name'):
            source = InventorySource.objects.filter(
                org_unit=campus, source_name=spec['source_name'], is_active=True
            ).order_by('id').first()

        table = None
        if spec.get('table_name'):
            from dataschema.models import DataTable

            table = (
                DataTable.objects.filter(name=spec['table_name'], is_archived=False)
                .order_by('id')
                .first()
            )

        factor = None
        if spec.get('factor_code'):
            factor = EmissionFactor.objects.filter(
                code=spec['factor_code'], is_active=True
            ).order_by('id').first()

        owner = self._resolve_owner(spec.get('owner'))
        default_owner = target.owner

        task, created = CoverageTask.objects.get_or_create(
            target=target,
            task_type=spec['task_type'],
            title=spec['title'],
            defaults={
                'detail': spec.get('detail', ''),
                'status': 'open',
                'due_date': spec.get('due_date') or target.due_date,
                'owner': owner or default_owner,
                'stream_source': source,
                'data_table': table,
                'factor': factor,
                'through_month': spec.get('through_month'),
            },
        )
        if not created and eligible_ids is not None and target.owner_id is not None:
            if task.owner_id is None or task.owner_id not in eligible_ids:
                task.owner = target.owner
                task.save(update_fields=['owner'])
        return created
