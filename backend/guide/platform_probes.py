"""Probes every pack may use. No domain word here."""
from __future__ import annotations

from guide.registry import PLATFORM, probe


@probe(PLATFORM, "live", "identity")
def live_identity(ctx, lesson):
    """The caller's own capabilities for this app and the org units they hold a role on."""
    from accounts.models import ScopedRole

    prefix = f"{ctx.app_id}:"
    caps = ["*"] if "*" in ctx.caps else sorted(key for key in ctx.caps if key.startswith(prefix))
    names = (
        ScopedRole.objects.filter(user=ctx.user).live()
        .exclude(org_unit=None).values_list("org_unit__name", flat=True).distinct()
    )
    return {"kind": "identity", "capabilities": caps, "org_units": sorted(set(names))[:20]}
