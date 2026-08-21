"""Access & CBAC assistance — read-only proposals for admin/ops (Phase 24-H).

DESIGN-ADAPTIVE-LEARNING-DQ-CORE.md §5B Phase H: Pulse assists admins with
*explanation and proposal*, never mutation:

  * ``effective_capabilities`` — what is this user's effective capability set
    across their org subtree?
  * ``users_with_capability``  — which users can reach capability X?
  * ``propose_grant``          — least-privilege grant proposal (never executes)
  * ``flag_access_anomalies``  — over-granted users + dormant grants

HARD RULES
  * READ-ONLY by construction — no model is ever created/updated here.
  * ``propose_grant`` returns a ``requires_confirmation`` payload only
    (RULE_21: AI suggests, Carbon executes — and even Carbon only executes
    through the existing ScopedRole admin flow with human action).
  * Capability gates: callers must require ``platform:view_audit`` (read) or
    ``platform:manage_access`` (proposal). Results are filtered by
    ``scope.org_unit_ids`` — a caller may never see capability data for org
    units outside their own subtree.
  * Downward-only imports (accounts, mdm) — this module must never be
    imported by those domain apps (RULE_20).
"""

from __future__ import annotations

import logging
from typing import Any, Iterable

logger = logging.getLogger("carbon.ai.access_assist")


# ── Org subtree helpers ────────────────────────────────────────────────────


def _subtree_org_ids(org_unit_ids: Iterable[int] | None) -> set[int] | None:
    """Expand ``org_unit_ids`` to include all descendant org units.

    ``None`` means "no org filter" (the caller is a global admin). An empty
    set means "only these units" (no expansion needed — but we still expand).
    """
    if org_unit_ids is None:
        return None
    from mdm.models import OrgUnit

    expanded: set[int] = set()
    for ou_id in org_unit_ids:
        ou = OrgUnit.objects.filter(pk=ou_id).first()
        if ou is None:
            continue
        expanded.add(ou.id)
        expanded.update(ou.get_descendant_ids(include_self=False))
    return expanded


def _roles_in_scope(user, subtree: set[int] | None):
    """Active ScopedRoles for ``user``, optionally restricted to an org subtree.

    A role is in scope when it is global (org_unit=None AND module=None) or
    its org_unit (or its module's org_unit) falls inside ``subtree``.
    """
    roles = user.scoped_roles.filter(is_active=True).select_related("group", "module")
    if subtree is None:
        return roles
    return [
        r for r in roles
        if r.org_unit_id is None and r.module_id is None
        or (r.org_unit_id is not None and r.org_unit_id in subtree)
        or (r.module_id is not None and r.module.org_unit_id in subtree)
    ]


def _caps_for_roles(roles) -> frozenset[str]:
    """Resolve capability keys from a list of ScopedRole objects.

    Mirrors ``accounts.capabilities.get_user_capabilities`` resolution
    (incl. DD-1: scoped wildcard groups grant READ-ONLY view capabilities),
    but over an already-filtered role subset so subtree-scoped answers are
    possible without mutating the shared resolution engine.
    """
    from accounts.capabilities import (
        ALL_CAPABILITIES,
        GROUP_CAPABILITIES,
        _expand_capabilities,
    )

    caps: set[str] = set()
    global_roles = [r for r in roles if r.org_unit_id is None and r.module_id is None]
    scoped_roles = [r for r in roles if r.org_unit_id is not None or r.module_id is not None]

    for r in global_roles:
        group_caps = GROUP_CAPABILITIES.get(r.group.name, set())
        if "*" in group_caps:
            caps = set(ALL_CAPABILITIES.keys())
            break
        caps.update(group_caps)

    if "*" not in caps:
        for r in scoped_roles:
            group_caps = GROUP_CAPABILITIES.get(r.group.name, set())
            if "*" in group_caps:
                caps.update(
                    cap.key for cap in ALL_CAPABILITIES.values()
                    if cap.action == "view" or cap.action.startswith("view_")
                )
                continue
            caps.update(group_caps)

    return _expand_capabilities(caps)


def _groups_granting(capability_key: str, subtree: set[int] | None, roles) -> list[dict]:
    """Which in-scope role assignments actually grant ``capability_key``.

    Returns one entry per contributing ScopedRole: {group, scope, scope_label}.
    """
    from accounts.capabilities import GROUP_CAPABILITIES

    result: list[dict[str, Any]] = []
    for r in roles:
        group_caps = GROUP_CAPABILITIES.get(r.group.name, set())
        grants = "*" in group_caps or capability_key in group_caps
        if not grants:
            continue
        if r.org_unit_id is not None:
            scope_label = f"org:{r.org_unit_id}"
        elif r.module_id is not None:
            scope_label = f"module:{r.module_id}"
        else:
            scope_label = "global"
        result.append({"group": r.group.name, "scope": scope_label})
    return result


def _user_summary(user) -> dict[str, Any]:
    return {
        "user_id": user.id,
        "username": user.username,
        "is_active": user.is_active,
        "is_superuser": user.is_superuser,
    }


# ── Public queries (all read-only) ─────────────────────────────────────────


def effective_capabilities(
    user_id: int, org_unit_ids: Iterable[int] | None = None
) -> dict[str, Any]:
    """Effective capability set for ``user_id`` across an org subtree.

    ``org_unit_ids=None`` → global effective set (all active roles).
    Otherwise the set is computed from global roles + roles scoped inside the
    expanded subtree.
    """
    from accounts.models import User

    user = User.objects.filter(pk=user_id).only(
        "id", "username", "is_active", "is_superuser"
    ).first()
    if user is None:
        return {"error": {"code": "not_found", "detail": f"User {user_id} not found."}}

    subtree = _subtree_org_ids(org_unit_ids)
    roles = _roles_in_scope(user, subtree)

    if user.is_superuser:
        caps = frozenset({"*"})
    else:
        caps = _caps_for_roles(roles)

    return {
        "user": _user_summary(user),
        "org_unit_ids": sorted(subtree) if subtree is not None else None,
        "capability_count": len(caps) if "*" not in caps else None,
        "capabilities": sorted(caps),
        "role_count": len(roles),
    }


def users_with_capability(
    capability_key: str, org_unit_ids: Iterable[int] | None = None
) -> dict[str, Any]:
    """Users whose effective capabilities include ``capability_key``.

    Unknown capability keys return an empty list (never leak suggestions).
    Scoped by the caller's ``org_unit_ids`` subtree when provided.
    """
    from accounts.capabilities import ALL_CAPABILITIES
    from accounts.models import User

    if capability_key not in ALL_CAPABILITIES:
        return {
            "capability": capability_key,
            "known": False,
            "users": [],
            "count": 0,
        }

    subtree = _subtree_org_ids(org_unit_ids)
    users = list(User.objects.all().only("id", "username", "is_active", "is_superuser"))
    matches: list[dict[str, Any]] = []
    for user in users:
        roles = _roles_in_scope(user, subtree)
        if user.is_superuser:
            matches.append({**_user_summary(user), "granted_via": ["*"]})
            continue
        caps = _caps_for_roles(roles)
        if "*" in caps or capability_key in caps:
            matches.append({
                **_user_summary(user),
                "granted_via": _groups_granting(capability_key, subtree, roles),
            })

    matches.sort(key=lambda m: m["username"].lower())
    return {
        "capability": capability_key,
        "known": True,
        "users": matches,
        "count": len(matches),
    }


def propose_grant(
    user_id: int, capability_key: str, org_unit_ids: Iterable[int] | None = None
) -> dict[str, Any]:
    """Least-privilege grant proposal for ``capability_key`` to ``user_id``.

    READ-ONLY: returns a ``requires_confirmation`` payload. Nothing is ever
    written — the caller (or a later confirmation flow with a human) applies
    the proposal through the existing ScopedRole admin surface.
    """
    from accounts.capabilities import ALL_CAPABILITIES, GROUP_CAPABILITIES
    from accounts.models import User

    if capability_key not in ALL_CAPABILITIES:
        return {"error": {"code": "unknown_capability", "detail": capability_key}}

    user = User.objects.filter(pk=user_id).only(
        "id", "username", "is_active", "is_superuser"
    ).first()
    if user is None:
        return {"error": {"code": "not_found", "detail": f"User {user_id} not found."}}

    subtree = _subtree_org_ids(org_unit_ids)

    # Already holds it? Proposal says "no change needed".
    roles = _roles_in_scope(user, subtree)
    if user.is_superuser:
        already = True
    else:
        caps = _caps_for_roles(roles)
        already = "*" in caps or capability_key in caps
    if already:
        return {
            "type": "access_grant_proposal",
            "requires_confirmation": False,
            "summary": (
                f"{user.username} already has {capability_key} "
                "in the requested scope — no change needed."
            ),
            "proposal": None,
            "rationale": ["No grant required: capability already effective."],
            "never_executes": True,
        }

    # Least-privilege group: smallest declared set that includes the key.
    # Wildcard ("*") groups are the MOST privileged — only considered when
    # no specific (non-wildcard) group grants the capability.
    from accounts.capabilities import GROUP_CAPABILITIES as _GC
    specific: list[tuple[str, int]] = []
    wildcard: list[str] = []
    for group_name, group_caps in _GC.items():
        if "*" in group_caps:
            wildcard.append(group_name)
        elif capability_key in group_caps:
            specific.append((group_name, len(group_caps)))
    specific.sort(key=lambda pair: (pair[1], pair[0]))
    if specific:
        group_name, group_size = specific[0]
    elif wildcard:
        group_name = sorted(wildcard)[0]
        group_size = None  # wildcard — capability set is open-ended
    else:
        return {
            "type": "access_grant_proposal",
            "requires_confirmation": True,
            "summary": f"No standard role grants {capability_key}.",
            "proposal": None,
            "rationale": ["No group in the role catalog grants this capability."],
            "never_executes": True,
        }

    cap = ALL_CAPABILITIES[capability_key]
    scope = {"org_unit_ids": sorted(subtree)} if subtree is not None else {"scope": "global"}
    grant_note = (
        f"({group_size} declared capabilities, least-privilege)"
        if group_size is not None
        else "(wildcard group — most privileged; confirm this is truly needed)"
    )
    return {
        "type": "access_grant_proposal",
        "requires_confirmation": True,
        "summary": (
            f"Propose adding {user.username} to role '{group_name}' {grant_note} "
            f"for {capability_key} ({cap.label})."
        ),
        "proposal": {
            "user_id": user.id,
            "username": user.username,
            "capability": capability_key,
            "capability_label": cap.label,
            "group": group_name,
            "group_capability_count": group_size,
            "scope": scope,
        },
        "rationale": [
            f"{capability_key} is granted by {len(specific) + len(wildcard)} role(s).",
            (
                f"'{group_name}' is the smallest non-wildcard role ({group_size} capabilities)."
                if group_size is not None
                else f"No specific role grants {capability_key}; only wildcard '{group_name}' does."
            ),
            "Apply only via the human-confirmed access flow — this assistant never writes.",
        ],
        "never_executes": True,
    }


def flag_access_anomalies(
    org_unit_ids: Iterable[int] | None = None,
    dormant_days: int = 180,
) -> dict[str, Any]:
    """Over-granted users + dormant grants in the given org subtree.

    Flags (both advisory, severity-tagged):
      * ``over_grant``  — user holds a GLOBAL wildcard admin role
                          (``admin``/``admins_group`` with ``*``).
      * ``dormant_grant`` — active ScopedRole whose user is inactive or has
                            not logged in for ``dormant_days``.
    """
    from accounts.models import ScopedRole, User

    subtree = _subtree_org_ids(org_unit_ids)
    flags: list[dict[str, Any]] = []

    roles = ScopedRole.objects.filter(is_active=True).select_related("user", "group")
    if subtree is not None:
        from django.db.models import Q

        roles = roles.filter(
            Q(org_unit_id__isnull=True, module_id__isnull=True)
            | Q(org_unit_id__in=subtree)
            | Q(module__org_unit_id__in=subtree)
        )

    for r in roles.select_related("user", "group", "org_unit", "module").iterator():
        if r.org_unit_id is None and r.module_id is None and r.group.name in ("admin", "admins_group"):
            flags.append({
                "type": "over_grant",
                "severity": "high",
                "user_id": r.user_id,
                "username": r.user.username,
                "group": r.group.name,
                "scope": "global",
                "detail": "Global wildcard admin role — review whether this user needs full platform administration.",
                "action": "review",
            })
            continue

        dormant = not r.user.is_active
        if not dormant and r.user.last_login is not None:
            from django.utils import timezone
            from datetime import timedelta

            dormant = timezone.now() - r.user.last_login > timedelta(days=dormant_days)
        if dormant:
            flags.append({
                "type": "dormant_grant",
                "severity": "low",
                "user_id": r.user_id,
                "username": r.user.username,
                "group": r.group.name,
                "scope": (
                    f"org:{r.org_unit_id}" if r.org_unit_id else
                    f"module:{r.module_id}" if r.module_id else "global"
                ),
                "detail": (
                    "Inactive user" if not r.user.is_active
                    else f"No login for {dormant_days}+ days"
                ),
                "action": "review",
            })

    flags.sort(key=lambda f: (f["severity"], f["username"]))
    return {"flags": flags, "count": len(flags)}
