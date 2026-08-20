"""
datahub/services.py — Dataset Hub business logic.

Thin views call these services. Responsibilities:
  * contract evaluation → DataContractViolation records
  * version approve / reject lifecycle (approve sets dataset.current_version)
  * health mirror to catalog.AssetProfile
  * access-policy resolution (explicit policy > module ScopedRole > deny)
"""
import logging

from django.db.models import Q
from django.utils import timezone

from catalog.models import AssetProfile
from dq.gate import check_rows

from .models import DataContractViolation, DatasetAccessPolicy

logger = logging.getLogger(__name__)

# Health → AssetProfile quality mirror (same thresholds as dq services).
PASSING_THRESHOLD = 0.9
WARNING_THRESHOLD = 0.7


# ── Access resolution ────────────────────────────────────────────────────────

def get_dataset_access(user, dataset) -> dict:
    """Resolve what an authenticated user may do with a dataset.

    Resolution order: explicit DatasetAccessPolicy > module-level ScopedRole > deny.

    Returns {"can_view": bool, "can_ingest": bool, "can_approve": bool}.
    """
    can_view = False
    can_ingest = False
    can_approve = False

    # Explicit policies take precedence (deny-all is expressed by no policy).
    policies = list(
        DatasetAccessPolicy.objects.filter(
            dataset=dataset,
        ).filter(
            Q(user=user) | Q(group__in=user.groups.all())
        )
    )
    if policies:
        for policy in policies:
            can_view = can_view or policy.can_view
            can_ingest = can_ingest or policy.can_ingest
            can_approve = can_approve or policy.can_approve
        return {
            'can_view': can_view,
            'can_ingest': can_ingest,
            'can_approve': can_approve,
        }

    # Module-level ScopedRole — resolved by the viewset queryset; here we
    # conservatively answer with the user's visibility on the module.
    from accounts.rbac_utils import get_visible_module_ids
    visible = get_visible_module_ids(user)
    if visible is None or dataset.module_id in visible:
        can_view = True
        can_ingest = True  # ingest is capability-gated separately; policy is per-dataset
        can_approve = True
    return {
        'can_view': can_view,
        'can_ingest': can_ingest,
        'can_approve': can_approve,
    }


# ── Contract evaluation ──────────────────────────────────────────────────────

def check_contract(version, contract=None) -> list:
    """Evaluate a DatasetVersion against its Dataset's active contract.

    Creates a DataContractViolation for every breach. Returns the list of
    violations created (empty when the dataset has no active contract).
    """
    from .models import DataContract

    if contract is None:
        contract = DataContract.objects.filter(
            dataset=version.dataset, is_active=True,
        ).first()
    if contract is None:
        return []

    violations = []

    # 1) Schema — missing required fields (union across all member tables)
    schema = dict(version.schema_snapshot or {})
    for member in version.members.all():
        for name, spec in (member.schema_snapshot or {}).items():
            schema.setdefault(name, spec)
    for field_name in contract.required_fields or []:
        if field_name not in schema:
            violations.append(DataContractViolation.objects.create(
                contract=contract,
                dataset_version=version,
                violation_type='schema',
                detail={'field': field_name, 'expected': 'present', 'actual': 'missing'},
            ))

    # 2) Quality — score below minimum SLA
    health = version.health_detail or {}
    checks = [
        ('min_completeness', 'completeness', contract.min_completeness),
        ('min_validity', 'validity', contract.min_validity),
        ('min_health_score', 'health_score', contract.min_health_score),
    ]
    for field, dimension, minimum in checks:
        if minimum is None:
            continue
        actual = version.health_score if dimension == 'health_score' else health.get(dimension)
        if actual is None or actual < minimum:
            violations.append(DataContractViolation.objects.create(
                contract=contract,
                dataset_version=version,
                violation_type='quality',
                detail={
                    'dimension': dimension,
                    'expected': f'>={minimum}',
                    'actual': actual,
                },
            ))

    # 3) Freshness — version older than the SLA (live age, not ingest snapshot)
    if contract.freshness_hours:
        age_hours = (timezone.now() - version.created_at).total_seconds() / 3600.0
        if age_hours > contract.freshness_hours:
            violations.append(DataContractViolation.objects.create(
                contract=contract,
                dataset_version=version,
                violation_type='freshness',
                detail={
                    'expected': f'<= {contract.freshness_hours} hours',
                    'actual': f'{age_hours:.2f} hours',
                },
            ))

    return violations


# ── Version lifecycle ────────────────────────────────────────────────────────

def approve_version(version, user) -> None:
    """Approve a pending version and set it as the dataset's current version."""
    from .models import DatasetVersion
    if version.status == 'approved':
        return
    if version.status != 'pending':
        raise ValueError(f"Cannot approve a version in status '{version.status}'.")

    now = timezone.now()
    version.status = 'approved'
    version.approved_by = user
    version.approved_at = now
    version.save(update_fields=['status', 'approved_by', 'approved_at'])

    dataset = version.dataset
    dataset.current_version = version
    if dataset.status == 'draft':
        dataset.status = 'active'
    dataset.save(update_fields=['current_version', 'status'])
    logger.info('Approved %s v%s (user=%s)', dataset.slug, version.version_number, user.pk)


def reject_version(version, user, reason: str = '') -> None:
    """Reject a pending version with a reason. Does NOT touch current_version."""
    if version.status == 'rejected':
        return
    if version.status != 'pending':
        raise ValueError(f"Cannot reject a version in status '{version.status}'.")

    version.status = 'rejected'
    version.approved_by = user  # recorded as the deciding user
    version.approved_at = timezone.now()
    version.rejection_reason = reason or ''
    version.save(update_fields=[
        'status', 'approved_by', 'approved_at', 'rejection_reason',
    ])
    logger.info('Rejected %s v%s (user=%s, reason=%r)',
                version.dataset.slug, version.version_number, user.pk, reason)


# ── Health mirror ────────────────────────────────────────────────────────────

def mirror_health_to_catalog(version, user=None) -> None:
    """Mirror a version's health to catalog.AssetProfile.quality_status/score.

    Mirrors per member table when the version has composition members (each
    member carries its own health_score); falls back to the version's
    single-table behavior for legacy versions without members.

    Thresholds mirror dq conventions: passing ≥ 0.9, warning ≥ 0.7, failing < 0.7.
    """
    members = list(version.members.all())
    if members:
        for member in members:
            score = member.health_score if member.health_score is not None else version.health_score
            if score is None:
                continue
            _mirror_score(version.data_table_id, score, member.data_table, user)
        return
    if version.health_score is None:
        return
    _mirror_score(version.data_table_id, version.health_score, version.data_table, user)


def _mirror_score(version_table_id, health_score, data_table, user=None) -> None:
    """Apply one health score to a table's AssetProfile (shared by both paths)."""
    ap, _ = AssetProfile.objects.get_or_create(data_table=data_table)
    old_status = ap.quality_status
    old_score = ap.quality_score
    score = round(health_score * 100)
    if health_score >= PASSING_THRESHOLD:
        ap.quality_status = 'passing'
    elif health_score >= WARNING_THRESHOLD:
        ap.quality_status = 'warning'
    else:
        ap.quality_status = 'failing'
    ap.quality_score = score
    if user:
        ap.updated_by = user
    ap.save(update_fields=['quality_status', 'quality_score', 'updated_at']
            + (['updated_by'] if user else []))
    if ap.quality_status != old_status or ap.quality_score != old_score:
        logger.info('Mirrored health for table %s: %s (%s -> %s)',
                    version_table_id, score, old_status, ap.quality_status)


def gate_validity(table, rows) -> float:
    """DQ gate pass rate (validity dimension) for a set of raw rows.

    Stateless — calls existing dq.gate.check_rows (mode='import'); no forking.
    """
    if not rows:
        return 1.0
    verdict = check_rows(table, rows, mode='import')
    summary = verdict.get('summary') or {}
    passed = summary.get('passed', 0)
    blocked = summary.get('blocked', 0)
    warned = summary.get('warned', 0)
    total = passed + blocked + warned
    if total == 0:
        return 1.0
    return round(passed / total, 4)
