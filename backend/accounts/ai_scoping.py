"""CBAC tenancy scoping for the AI read layer (Phase F).

Applies the ``AppScopeMixin`` partition (app + visibility + org subtree) to a
read-layer queryset. Lives in ``accounts`` so the ``ai`` models/store/engine
stay pure; the ``ai`` read-layer views import it at the query boundary.
"""
from django.db.models import Q

from .constants import ADMIN_ROLES
from .rbac_utils import get_allowed_org_unit_ids, user_is_global_admin


def scope_ai_queryset(qs, user):
    """Filter an AI read queryset by app + visibility + org scope.

    Superusers and global admins see everything (bypass — matches
    ``_check_write_capability`` steps 1-2).  Everyone else sees:
      - ``visibility`` in (global, shared) rows, plus their own ``private`` rows
      - rows in their allowed org subtree (or null-org rows if they hold no org role)
    """
    qs = qs.filter(app_identifier="carbon")
    if user.is_superuser or user_is_global_admin(user):
        return qs
    uid = str(user.id)
    vis = (
        Q(visibility__in=["global", "shared"])
        | Q(visibility="private", host_user_id=uid)
    )
    qs = qs.filter(vis)
    allowed = get_allowed_org_unit_ids(user, ADMIN_ROLES)
    if allowed:
        qs = qs.filter(Q(org_unit_id__in=allowed) | Q(org_unit_id__isnull=True))
    else:
        qs = qs.filter(org_unit_id__isnull=True)
    return qs
