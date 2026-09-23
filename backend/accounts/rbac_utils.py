# File: accounts/rbac_utils.py
from django.db import models
from core.models import Module
from .models import ScopedRole
from .constants import (
    ADMIN_ROLES,
    VISIBILITY_ROLES,
    ADMINS_GROUP,
)


def visible_org_ids(user, duty):
    """Org subtree for one domain duty. ``duty`` is ``people:lead`` or a group name."""
    from accounts.birthright import resolve_group_name
    return get_allowed_org_unit_ids(user, {resolve_group_name(duty)})


class CapabilityOrgScope:
    """Where a user may read data for one capability.

    ``unrestricted`` is a global grant when this deployment has no single
    root yet (the caller does not filter). Otherwise ``ids`` is the anchor
    orgs plus their children, clipped to the deployment tree when one exists.
    """

    __slots__ = ("unrestricted", "ids")

    def __init__(self, unrestricted, ids):
        self.unrestricted = unrestricted
        self.ids = frozenset(ids)


def groups_granting(capability):
    """Django group names whose expanded capabilities include ``capability``."""
    from accounts.birthright import resolve_group_name
    from accounts.capabilities import GROUP_CAPABILITIES, _expand_capabilities

    names = []
    for name, caps in GROUP_CAPABILITIES.items():
        if "*" in caps or capability in _expand_capabilities(set(caps)):
            names.append(resolve_group_name(name))
    return names


def _deployment_org_ids():
    """Deployment org ids, or None when there is no single root to clip to."""
    from mdm.services import get_deployment_org_unit_ids

    try:
        return get_deployment_org_unit_ids(include_self=True)
    except RuntimeError:
        return None


def org_scope_for_capability(user, capability):
    """Live ledger rows that grant ``capability``, expanded to child org units."""
    if not user or not getattr(user, "is_authenticated", False):
        return CapabilityOrgScope(False, ())
    granting = groups_granting(capability)
    deployment = _deployment_org_ids()
    global_grant = user_is_global_admin(user) or ScopedRole.objects.filter(
        user=user, org_unit=None, module=None, group__name__in=granting,
    ).live().exists()
    if global_grant:
        if not deployment:
            return CapabilityOrgScope(True, ())
        return CapabilityOrgScope(False, deployment)
    ids = set()
    live_names = (
        ScopedRole.objects.filter(user=user, group__name__in=granting)
        .live()
        .values_list("group__name", flat=True)
        .distinct()
    )
    for name in live_names:
        ids |= visible_org_ids(user, name)
    if deployment:
        ids &= deployment
    return CapabilityOrgScope(False, ids)


def org_units_for_capability(user, capability):
    """Active org units the user may read for ``capability``."""
    from mdm.models import OrgUnit

    scope = org_scope_for_capability(user, capability)
    qs = OrgUnit.objects.filter(is_active=True)
    if not scope.unrestricted:
        if not scope.ids:
            return []
        qs = qs.filter(id__in=scope.ids)
    return list(qs.order_by("name"))


def module_ids_for_capability(user, capability):
    """Module ids for ``capability``. None means do not filter."""
    scope = org_scope_for_capability(user, capability)
    if scope.unrestricted:
        return None
    granting = groups_granting(capability)
    module_ids = set(
        ScopedRole.objects.filter(user=user, group__name__in=granting)
        .live()
        .exclude(module=None)
        .values_list("module_id", flat=True)
    )
    if scope.ids:
        module_ids |= set(
            Module.objects.filter(org_unit_id__in=scope.ids).values_list("id", flat=True)
        )
    return module_ids


def user_has_global_role(user, roles):
    """True if the user has any of these roles globally (no org_unit, no module)."""
    if not user or not roles:
        return False
    return ScopedRole.objects.filter(
        user=user, org_unit=None, module=None, group__name__in=roles,
    ).live().exists()


def user_has_module_role(user, module_id, roles):
    if not user or not module_id or not roles:
        return False
    return ScopedRole.objects.filter(
        user=user, module_id=module_id, group__name__in=roles
    ).live().exists()


def get_allowed_org_unit_ids(user, roles):
    """Org units the user holds any of these roles on, expanded to include all descendants."""
    if not user or not roles:
        return set()
    from mdm.models import OrgUnit
    direct = set(
        ScopedRole.objects.filter(
            user=user, group__name__in=roles,
        ).live().exclude(org_unit=None).values_list('org_unit_id', flat=True)
    )
    allowed = set()
    for ou in OrgUnit.objects.filter(id__in=direct):
        allowed |= ou.get_descendant_ids(include_self=True)
    return allowed


def user_has_org_role(user, org_unit_id, roles):
    """True if the user has any of these roles on this org unit or any ancestor of it."""
    if not user or not org_unit_id or not roles:
        return False
    return org_unit_id in get_allowed_org_unit_ids(user, roles)


def get_allowed_module_ids(user, roles):
    """Modules the user can access: module-scoped roles OR modules whose org_unit is
    within the user's allowed org subtree."""
    if not user or not roles:
        return set()
    module_ids = set(
        ScopedRole.objects.filter(
            user=user, group__name__in=roles
        ).live().exclude(module=None).values_list('module_id', flat=True)
    )
    org_ids = get_allowed_org_unit_ids(user, roles)
    if org_ids:
        module_ids |= set(
            Module.objects.filter(org_unit_id__in=org_ids).values_list('id', flat=True)
        )
    return module_ids


def get_visible_org_units(user):
    """Return org units the user may view for emissions owner pages.

    ADR-0028: when a deployment root exists, results are limited to that
    root's subtree even for global admins / global visibility roles.
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return []
    from mdm.models import OrgUnit
    from mdm.services import get_deployment_org_unit_ids

    def _scope(qs):
        try:
            deployment_ids = get_deployment_org_unit_ids(include_self=True)
        except RuntimeError:
            return OrgUnit.objects.none()
        if deployment_ids:
            qs = qs.filter(id__in=deployment_ids)
        return qs

    if user_is_global_admin(user):
        return list(_scope(OrgUnit.objects.filter(is_active=True)).order_by('name'))

    # Users with a global visibility role (org_unit=None, module=None) can see
    # all org units within the deployment root subtree.
    if ScopedRole.objects.filter(
        user=user, org_unit=None, module=None,
        group__name__in=VISIBILITY_ROLES,
    ).live().exists():
        return list(_scope(OrgUnit.objects.filter(is_active=True)).order_by('name'))

    allowed_ids = get_allowed_org_unit_ids(user, VISIBILITY_ROLES)
    if not allowed_ids:
        return []
    try:
        deployment_ids = get_deployment_org_unit_ids(include_self=True)
    except RuntimeError:
        return []
    if deployment_ids:
        allowed_ids &= deployment_ids
    if not allowed_ids:
        return []
    return list(OrgUnit.objects.filter(id__in=allowed_ids, is_active=True).order_by('name'))


# --- Visibility helpers (org-scoped READ access) -------------------------------
# ADMIN_ROLES, VISIBILITY_ROLES imported from .constants


def user_is_global_admin(user):
    """True for superusers or holders of a GLOBAL admins_group role (org_unit=None, module=None)."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    return user_has_global_role(user, ADMIN_ROLES)


def user_is_domain_lead(user, app_name=None):
    """True if the user holds an active {app_name}_lead ScopedRole (any scope).

    If app_name is None, returns True for ANY domain lead group.
    Domain Leads manage their app's data/config within their org scope.
    They are NOT platform admins.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False
    from .constants import DOMAIN_LEAD_GROUPS
    qs = ScopedRole.objects.filter(
        user=user,
    ).live()
    if app_name:
        lead_group = f"{app_name}_lead"
        # Only check if this is a known domain lead group
        if lead_group in DOMAIN_LEAD_GROUPS:
            return qs.filter(group__name=lead_group).exists()
        return False
    return qs.filter(group__name__in=DOMAIN_LEAD_GROUPS).exists()


def get_visible_module_ids(user):
    """Module ids the user may see across the platform.

    Returns None to mean 'unrestricted' (superuser / global admin or any global visibility role).
    Otherwise returns the set of module ids within the user's allowed org subtree
    (or granted directly at module scope) for any visibility role.
    """
    if user_is_global_admin(user):
        return None
    # Users with a global visibility role (org_unit=None, module=None) can see all modules
    if ScopedRole.objects.filter(
        user=user, org_unit=None, module=None,
        group__name__in=VISIBILITY_ROLES,
    ).live().exists():
        return None
    return get_allowed_module_ids(user, VISIBILITY_ROLES)


def get_steward_org_unit_ids(user):
    """Org units (incl. all descendants) where the user holds an admins_group role.
    Empty set => the user is not a steward anywhere."""
    if not user or not getattr(user, "is_authenticated", False):
        return set()
    return get_allowed_org_unit_ids(user, ADMIN_ROLES)


def user_is_steward(user):
    """True if the user administers at least one org subtree (but is not necessarily global)."""
    return bool(get_steward_org_unit_ids(user))