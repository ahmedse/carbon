# File: people/leave_policy_service.py
# Leave-policy propagation service (LPR-2A).
#
# DRF-free service (no rest_framework, no Response, no serializers — RULE_3).
# Views and the management command both call into here so the eligibility
# filter and create logic live in exactly one place. Propagation is idempotent:
# an existing entitlement is never overwritten (neither its ``entitled_days``
# nor its ``policy`` provenance).

from datetime import timedelta

from django.db.models import Max
from django.utils import timezone

from .models import Employee, LeaveEntitlement, LeavePolicy, LeavePolicyVersion


def _eligible_queryset(policy):
    """Return the queryset of employees eligible for ``policy``.

    Mirrors the LPR-1A eligibility filter:
      - active employees only;
      - gender restriction (male/female → ``gender__iexact``);
      - minimum service days (``join_date`` before the threshold date);
      - org-unit scope (``applies_to_org_units``; empty = all);
      - contract-type scope (``applies_to_contract_types``; empty = all);
      - Kuwaitization scope (``applies_to_kuwaitization``: Kuwaiti / non-Kuwaiti
        / any — GOFSCO 42-day vs 30-day leave);
      - rotation-pattern scope (``applies_to_rotations``; empty = all).
    """
    employees = Employee.objects.filter(is_active=True)

    if policy.gender_restriction in (LeavePolicy.GENDER_MALE, LeavePolicy.GENDER_FEMALE):
        employees = employees.filter(gender__iexact=policy.gender_restriction)
    if policy.min_service_days:
        min_join = timezone.localdate() - timedelta(days=policy.min_service_days)
        employees = employees.filter(join_date__lte=min_join)
    if policy.applies_to_org_units.exists():
        employees = employees.filter(
            org_unit_id__in=policy.applies_to_org_units.values_list('id', flat=True),
        )
    if policy.applies_to_contract_types:
        employees = employees.filter(
            contract_type_code__in=policy.applies_to_contract_types,
        )
    if policy.applies_to_kuwaitization == LeavePolicy.KUWAIT_ONLY:
        employees = employees.filter(kuwaitization=True)
    elif policy.applies_to_kuwaitization == LeavePolicy.KUWAIT_NON:
        employees = employees.filter(kuwaitization=False)
    if policy.applies_to_rotations:
        employees = employees.filter(
            rotation__in=policy.applies_to_rotations,
        )

    return employees


def propagate_policy(policy, year=None, *, dry_run=False):
    """Propagate ``policy``'s default entitlement to eligible employees.

    Args:
        policy: a ``LeavePolicy`` instance.
        year: target leave year (defaults to the current year).
        dry_run: when True, compute counts without writing anything.

    Returns:
        dict with keys ``eligible``, ``will_create``, ``will_update``,
        ``skipped``, ``year``; plus ``created``/``updated`` when not dry-run.

    Raises:
        ValueError: when ``policy`` is not active (draft/deprecated and not a
            legacy ``is_active`` row) and therefore cannot be propagated.
    """
    if year is None:
        year = timezone.now().year

    propagatable = policy.status == LeavePolicy.STATUS_ACTIVE or (
        not policy.status and policy.is_active
    )
    if not propagatable:
        raise ValueError('Only active policies can be propagated')

    total_active = Employee.objects.filter(is_active=True).count()
    employees = _eligible_queryset(policy)

    eligible_ids = list(employees.values_list('id', flat=True))
    eligible_count = len(eligible_ids)
    skipped = total_active - eligible_count

    existing_ids = set(
        LeaveEntitlement.objects.filter(
            year=year,
            leave_type=policy.leave_type,
            employee_id__in=eligible_ids,
        ).values_list('employee_id', flat=True)
    )
    will_create = sum(1 for eid in eligible_ids if eid not in existing_ids)
    will_update = len(existing_ids)

    result = {
        'eligible': eligible_count,
        'will_create': will_create,
        'will_update': will_update,
        'skipped': skipped,
        'year': year,
    }

    if dry_run:
        return result

    created = 0
    for eid in eligible_ids:
        if eid in existing_ids:
            continue
        _, was_created = LeaveEntitlement.objects.get_or_create(
            employee_id=eid,
            year=year,
            leave_type=policy.leave_type,
            defaults={
                'entitled_days': policy.default_entitled_days,
                'policy': policy,
            },
        )
        if was_created:
            created += 1

    result['created'] = created
    # Pre-existing entitlements are recognized but never overwritten.
    result['updated'] = will_update
    return result


def propagate_all_active(year=None, *, dry_run=False):
    """Propagate every active policy and aggregate the results.

    Active = ``status == 'active'`` plus legacy rows (``status == ''`` with
    ``is_active=True``). Each policy is propagated independently; totals are
    summed across policies.

    Returns:
        dict with keys ``eligible``, ``will_create``, ``will_update``,
        ``skipped``, ``created``, ``updated``, ``year`` and ``per_policy``
        (a list of ``{policy_id, name, ...per-policy counts}``).
    """
    if year is None:
        year = timezone.now().year

    policies = list(
        LeavePolicy.objects.filter(status=LeavePolicy.STATUS_ACTIVE)
        | LeavePolicy.objects.filter(status='', is_active=True)
    )
    # Deterministic ordering for stable output/aggregation.
    policies.sort(key=lambda p: p.id)

    totals = {
        'eligible': 0,
        'will_create': 0,
        'will_update': 0,
        'skipped': 0,
        'created': 0,
        'updated': 0,
        'year': year,
        'per_policy': [],
    }

    for policy in policies:
        result = propagate_policy(policy, year=year, dry_run=dry_run)
        totals['eligible'] += result['eligible']
        totals['will_create'] += result['will_create']
        totals['will_update'] += result['will_update']
        totals['skipped'] += result['skipped']
        totals['created'] += result.get('created', 0)
        totals['updated'] += result.get('updated', 0)
        totals['per_policy'].append({
            'policy_id': policy.id,
            'name': policy.name,
            **result,
        })

    return totals


# ── LPR-3A — policy versioning (snapshot + fork semantics) ────────────────


def snapshot_policy(policy):
    """Serialize ``policy``'s configurable fields into a JSON-safe dict.

    Decimal and date-adjacent values are coerced via ``str()`` so the result is
    directly JSON-serializable. The live policy row is not mutated.
    """
    return {
        'leave_type': policy.leave_type.code if policy.leave_type_id else None,
        'default_entitled_days': str(policy.default_entitled_days),
        'max_carryover_days': str(policy.max_carryover_days),
        'is_carryover_allowed': policy.is_carryover_allowed,
        'accrual_method': policy.accrual_method,
        'gender_restriction': policy.gender_restriction,
        'requires_approval': policy.requires_approval,
        'min_service_days': policy.min_service_days,
        'name': policy.name,
        'description': policy.description,
        'status': policy.status,
        'applies_to_contract_types': list(policy.applies_to_contract_types or []),
        'applies_to_org_units': list(
            policy.applies_to_org_units.values_list('id', flat=True),
        ),
        'applies_to_kuwaitization': policy.applies_to_kuwaitization,
        'applies_to_rotations': list(policy.applies_to_rotations or []),
    }


def fork_policy(policy, *, effective_from=None, change_summary='', user=None):
    """Create a new ``LeavePolicyVersion`` snapshot of ``policy``.

    Fork semantics:
      1. ``next_version`` = max(existing ``version_number``) + 1 (or 1).
      2. ``effective_from`` defaults to ``timezone.localdate()``.
      3. The prior open-ended version (``effective_to IS NULL``) is closed at
         ``effective_from - 1 day``.
      4. A new version is recorded with ``snapshot_policy(policy)``.

    The live ``LeavePolicy`` configurable fields are NOT mutated — versioning
    records the snapshot; the live row remains the current config.

    Returns:
        The newly created ``LeavePolicyVersion``.
    """
    max_number = LeavePolicyVersion.objects.filter(policy=policy).aggregate(
        max_version=Max('version_number'),
    )['max_version']
    next_version = (max_number or 0) + 1

    if effective_from is None:
        effective_from = timezone.localdate()

    # Close the prior open version (highest number, still open-ended).
    LeavePolicyVersion.objects.filter(
        policy=policy, effective_to__isnull=True,
    ).update(effective_to=effective_from - timedelta(days=1))

    return LeavePolicyVersion.objects.create(
        policy=policy,
        version_number=next_version,
        effective_from=effective_from,
        snapshot=snapshot_policy(policy),
        change_summary=change_summary,
        created_by=user,
    )


def get_version_history(policy):
    """Return the policy's versions in ascending ``version_number`` order."""
    return list(
        LeavePolicyVersion.objects.filter(policy=policy).order_by('version_number'),
    )


def latest_version(policy):
    """Return the newest ``LeavePolicyVersion`` for ``policy``, or None."""
    return (
        LeavePolicyVersion.objects.filter(policy=policy)
        .order_by('-version_number')
        .first()
    )
