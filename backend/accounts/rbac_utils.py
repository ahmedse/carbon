# File: accounts/rbac_utils.py
from django.db import models
from core.models import Module
from .models import ScopedRole


def user_has_global_role(user, roles):
    """True if the user has any of these roles globally (no org_unit, no module)."""
    if not user or not roles:
        return False
    return ScopedRole.objects.filter(
        user=user, is_active=True, org_unit=None, module=None, group__name__in=roles
    ).exists()


def user_has_module_role(user, module_id, roles):
    if not user or not module_id or not roles:
        return False
    return ScopedRole.objects.filter(
        user=user, is_active=True, module_id=module_id, group__name__in=roles
    ).exists()


def get_allowed_org_unit_ids(user, roles):
    """Org units the user holds any of these roles on, expanded to include all descendants."""
    if not user or not roles:
        return set()
    from mdm.models import OrgUnit
    direct = set(
        ScopedRole.objects.filter(
            user=user, is_active=True, group__name__in=roles
        ).exclude(org_unit=None).values_list('org_unit_id', flat=True)
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
            user=user, is_active=True, group__name__in=roles
        ).exclude(module=None).values_list('module_id', flat=True)
    )
    org_ids = get_allowed_org_unit_ids(user, roles)
    if org_ids:
        module_ids |= set(
            Module.objects.filter(org_unit_id__in=org_ids).values_list('id', flat=True)
        )
    return module_ids