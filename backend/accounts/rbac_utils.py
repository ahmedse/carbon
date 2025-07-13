# File: accounts/rbac_utils.py

from core.models import Project, Module
from .models import ScopedRole

def user_has_project_role(user, project_id, roles):
    if not user or not project_id or not roles:
        return False
    return ScopedRole.objects.filter(
        user=user, is_active=True, project_id=project_id, group__name__in=roles
    ).exists()

def user_has_module_role(user, project_id, module_id, roles):
    if not user or not project_id or not module_id or not roles:
        return False
    return ScopedRole.objects.filter(
        user=user, is_active=True, project_id=project_id, module_id=module_id, group__name__in=roles
    ).exists()

def get_allowed_module_ids(user, project_id, roles):
    if not user or not project_id or not roles:
        return set()
    return set(
        ScopedRole.objects.filter(
            user=user, is_active=True, project_id=project_id, group__name__in=roles
        ).exclude(module=None).values_list('module_id', flat=True)
    )

def get_allowed_project_ids(user, tenant, roles):
    if not user or not tenant or not roles:
        return set()
    project_ids = set(
        ScopedRole.objects.filter(
            user=user, tenant=tenant, is_active=True, group__name__in=roles
        ).exclude(project=None).values_list('project_id', flat=True)
    )
    module_project_ids = set(
        Module.objects.filter(
            id__in=ScopedRole.objects.filter(
                user=user, tenant=tenant, is_active=True, group__name__in=roles
            ).exclude(module=None).values_list('module_id', flat=True)
        ).values_list('project_id', flat=True)
    )
    return project_ids | module_project_ids