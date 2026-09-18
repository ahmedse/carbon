"""Map verified LTI launch → platform User + ScopedRole capabilities."""
from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction

from gradevance.lti import LtiLaunchContext, map_lti_roles_to_capabilities

User = get_user_model()

# Capability → preferred EduOS group (created by bootstrap_platform).
_CAP_GROUP = {
    "gradevance:manage": "gradevance_lead",
    "gradevance:mark": "gradevance_markers",
    "gradevance:submit": "gradevance_students",
    "gradevance:qa": "gradevance_lead",
    "gradevance:view": "gradevance_students",
}


@dataclass
class LaunchUserResult:
    user_id: int
    username: str
    created: bool
    groups: list[str]
    capabilities: list[str]


@transaction.atomic
def provision_user_from_launch(
    ctx: LtiLaunchContext,
    *,
    email: str | None = None,
    name: str | None = None,
) -> LaunchUserResult:
    """Idempotent: username = ``lti:{iss}:{sub}`` (opaque; no PII in username)."""
    username = f"lti:{ctx.iss}:{ctx.sub}"[:150]
    caps = sorted(map_lti_roles_to_capabilities(ctx.roles))
    user, created = User.objects.get_or_create(
        username=username,
        defaults={
            "email": (email or "")[:254],
            "is_active": True,
        },
    )
    if email and user.email != email:
        user.email = email[:254]
        user.save(update_fields=["email"])
    if name and hasattr(user, "first_name") and not user.first_name:
        # Store display name hint only — not used as SoR student key.
        parts = name.strip().split(None, 1)
        user.first_name = parts[0][:30]
        if len(parts) > 1:
            user.last_name = parts[1][:150]
        user.save(update_fields=["first_name", "last_name"])

    assigned: list[str] = []
    for cap in caps:
        gname = _CAP_GROUP.get(cap)
        if not gname:
            continue
        group, _ = Group.objects.get_or_create(name=gname)
        user.groups.add(group)
        if gname not in assigned:
            assigned.append(gname)

    # Ensure ScopedRole rows for org-unscoped baseline when model exists.
    try:
        from accounts.models import ScopedRole

        for gname in assigned:
            group = Group.objects.get(name=gname)
            ScopedRole.objects.get_or_create(
                user=user,
                group=group,
                org_unit=None,
                module=None,
                defaults={"is_active": True},
            )
    except Exception:
        pass

    return LaunchUserResult(
        user_id=user.pk,
        username=user.username,
        created=created,
        groups=assigned,
        capabilities=caps,
    )
