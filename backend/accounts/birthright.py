# File: accounts/birthright.py
# Birthright assignment engine (ADR-0048).
#
# Access = domain duty × org scope × dates × provenance.
# This module rewrites provenance=birthright rows only. Exception grants stay.
# Domain apps pass structural facts; they do not own a second grant path.

from dataclasses import dataclass, field

from django.contrib.auth.models import Group
from django.utils import timezone

from accounts.models import DutyProfile, RoleAssignmentAuditLog, ScopedRole

# Canonical duty id → Django group name. New apps add a row here and in
# GROUP_CAPABILITIES. The manifest role key uses the canonical id.
DUTY_GROUP = {
    "platform:employee": "employee_group",
    "platform:manager": "manager_group",
    "people:lead": "people_lead",
    "people:analyst": "people_analysts_group",
    "people:data_owner": "people_data_owners_group",
    "carbon:lead": "carbon_lead",
    "carbon:data_owner": "carbon_data_owners_group",
    "carbon:analyst": "carbon_analysts_group",
    "correspondence:finance": "finance_group",
    "ai:operator": "ai_operator_group",
    "ai:auditor": "ai_auditor_group",
    "ai:publisher": "ai_publisher_group",
    "ai:process_owner": "ai_process_owner_group",
    "ai:policy_owner": "ai_policy_owner_group",
    "gradevance:lead": "gradevance_lead",
    "gradevance:marker": "gradevance_markers",
    "gradevance:student": "gradevance_students",
    "catalog:lead": "catalog_lead",
    "mdm:lead": "mdm_lead",
    "dq:lead": "dq_lead",
}

PLATFORM_EMPLOYEE = "platform:employee"
PLATFORM_MANAGER = "platform:manager"
PLATFORM_ADMIN = "platform:admin"

# Add the platform admin duty without a second alias for the bare ``admin`` group.
DUTY_GROUP.setdefault(PLATFORM_ADMIN, "admins_group")
DUTY_GROUP.setdefault("datahub:lead", "datahub_lead")
DUTY_GROUP.setdefault("turnkey:lead", "turnkey_lead")

_GROUP_DUTY = {group: duty for duty, group in DUTY_GROUP.items()}

# Live duties that cannot be held together. A grant of either side is refused
# while the other is live. Recorded on RoleAssignmentAuditLog.action=refused.
DUTY_CONFLICTS = (
    frozenset({"gradevance:marker", "gradevance:student"}),
)


def resolve_group_name(duty: str) -> str:
    """Map a domain-prefixed duty id to the Django group that grants it."""
    return DUTY_GROUP.get(duty, duty)


def group_to_duty(group_name: str) -> str:
    """Map a Django group back to its domain duty id."""
    return _GROUP_DUTY.get(group_name, group_name)


def duty_catalog():
    """Duties the engine and the admin screens share. One row per domain duty."""
    from accounts.capabilities import GROUP_CAPABILITIES

    rows = []
    for duty, group_name in sorted(DUTY_GROUP.items()):
        domain, _, name = duty.partition(":")
        rows.append({
            "duty": duty,
            "group": group_name,
            "domain": domain,
            "name": name,
            "capabilities": sorted(GROUP_CAPABILITIES.get(group_name, ())),
        })
    return rows


def duty_conflicts():
    return [sorted(pair) for pair in DUTY_CONFLICTS]


def sod_conflict(duty: str, held) -> str:
    """Return the live duty that blocks ``duty``, or '' when the grant is allowed."""
    held = set(held or ())
    for pair in DUTY_CONFLICTS:
        if duty not in pair:
            continue
        others = pair - {duty}
        blocked = others & held
        if blocked:
            return sorted(blocked)[0]
    return ""


def live_duties(user, today=None) -> set:
    if user is None:
        return set()
    names = ScopedRole.objects.filter(user=user).live(today).values_list("group__name", flat=True)
    return {group_to_duty(name) for name in names}


@dataclass
class BirthrightResult:
    granted: int = 0
    revoked: int = 0
    kept: int = 0
    refused: int = 0
    duties: list = field(default_factory=list)


def _window_ok(row, today) -> bool:
    if not row.is_active:
        return False
    if row.valid_from and row.valid_from > today:
        return False
    if row.valid_to and row.valid_to < today:
        return False
    return True


def recalculate_birthright(
    *,
    user,
    is_active: bool,
    home_org_id,
    managed_org_ids,
    position_code: str = "",
    trigger: str = "",
    actor=None,
) -> BirthrightResult:
    """Diff birthright rows for ``user`` against structural facts.

    ``managed_org_ids`` is the set of org units this person runs.
    ``position_code`` selects DutyProfile rows. Inactive people lose
    every birthright row. Exception rows are not deleted.
    """
    result = BirthrightResult()
    if user is None:
        return result

    today = timezone.localdate()
    desired = {}  # (group_name, org_id or None) -> duty id
    if is_active:
        desired[(resolve_group_name(PLATFORM_EMPLOYEE), None)] = PLATFORM_EMPLOYEE
        if home_org_id:
            desired[(resolve_group_name(PLATFORM_EMPLOYEE), home_org_id)] = PLATFORM_EMPLOYEE
        for org_id in managed_org_ids or ():
            desired[(resolve_group_name(PLATFORM_MANAGER), org_id)] = PLATFORM_MANAGER
        if position_code:
            for profile in DutyProfile.objects.filter(position_code=position_code):
                group_name = resolve_group_name(profile.duty)
                if profile.scope == DutyProfile.SCOPE_GLOBAL:
                    desired[(group_name, None)] = profile.duty
                elif profile.scope == DutyProfile.SCOPE_HOME and home_org_id:
                    desired[(group_name, home_org_id)] = profile.duty
                elif profile.scope == DutyProfile.SCOPE_MANAGED:
                    for org_id in managed_org_ids or ():
                        desired[(group_name, org_id)] = profile.duty

    held = set()
    for row in ScopedRole.objects.filter(user=user, module=None).select_related("group"):
        if row.provenance == ScopedRole.PROVENANCE_EXCEPTION and _window_ok(row, today):
            held.add(group_to_duty(row.group.name))
    for key, duty in list(desired.items()):
        conflict = sod_conflict(duty, held)
        if not conflict:
            held.add(duty)
            continue
        desired.pop(key, None)
        group, _created = Group.objects.get_or_create(name=key[0])
        _audit(
            user, actor, group, key[1], "refused", trigger, duty,
            extra={"sod_conflict": conflict},
        )
        result.refused += 1

    groups = {
        name: Group.objects.get_or_create(name=name)[0]
        for name, _org in desired
    }

    existing = {
        (row.group_id, row.org_unit_id): row
        for row in ScopedRole.objects.filter(user=user, module=None).select_related("group")
    }
    group_by_id = {g.id: g for g in groups.values()}

    for (group_name, org_id), duty in desired.items():
        group = groups[group_name]
        group_by_id[group.id] = group
        row = existing.get((group.id, org_id))
        if row is not None and row.provenance == ScopedRole.PROVENANCE_EXCEPTION and _window_ok(row, today):
            result.kept += 1
            continue
        if row is None:
            ScopedRole.objects.create(
                user=user,
                group=group,
                org_unit_id=org_id,
                module=None,
                provenance=ScopedRole.PROVENANCE_BIRTHRIGHT,
                is_active=True,
                valid_from=today,
                valid_to=None,
            )
            _audit(user, actor, group, org_id, "assigned", trigger, duty)
            result.granted += 1
            continue
        changed = (
            not row.is_active
            or row.provenance != ScopedRole.PROVENANCE_BIRTHRIGHT
            or row.valid_to is not None
        )
        row.provenance = ScopedRole.PROVENANCE_BIRTHRIGHT
        row.is_active = True
        row.valid_from = row.valid_from or today
        row.valid_to = None
        row.save(update_fields=["provenance", "is_active", "valid_from", "valid_to"])
        if changed:
            _audit(user, actor, group, org_id, "assigned", trigger, duty)
            result.granted += 1
        else:
            result.kept += 1

    desired_pairs = set()
    for group_name, org_id in desired:
        desired_pairs.add((groups[group_name].id, org_id))

    for (group_id, org_id), row in existing.items():
        if row.provenance != ScopedRole.PROVENANCE_BIRTHRIGHT:
            continue
        if (group_id, org_id) in desired_pairs:
            continue
        if not row.is_active:
            continue
        row.is_active = False
        row.valid_to = today
        row.save(update_fields=["is_active", "valid_to"])
        group = row.group
        group_by_id[group.id] = group
        _audit(user, actor, group, org_id, "removed", trigger, "")
        result.revoked += 1

    _sync_group_membership(user, group_by_id, today)
    result.duties = sorted({duty for duty in desired.values()})
    return result


def _sync_group_membership(user, group_by_id, today):
    for group in group_by_id.values():
        live = ScopedRole.objects.filter(user=user, group=group).live(today).exists()
        if live:
            user.groups.add(group)
        else:
            user.groups.remove(group)


def _audit(user, actor, group, org_id, action, trigger, duty, extra=None):
    payload = {"provenance": "birthright", "trigger": trigger, "duty": duty}
    if extra:
        payload.update(extra)
    RoleAssignmentAuditLog.objects.create(
        user=user,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        group=group,
        org_unit_id=org_id,
        module=None,
        action=action,
        extra=payload,
    )
