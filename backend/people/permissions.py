# File: people/permissions.py
# CBAC permission class for the People & Payroll domain (NIR-1C).
#
# Mirrors the canonical hosted-app pattern in ``backend/healthy/views.py``:
#   * reads  → ``people:view``
#   * writes → ``people:manage``
# Superusers and global admins (admin/admins_group with org_unit=None and
# module=None) bypass capability checks and get full access.

from rest_framework.permissions import BasePermission

from accounts.capabilities import has_capability


def is_global_admin(user) -> bool:
    """Superuser or holder of a GLOBAL admin role (org_unit=None, module=None)."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    from accounts.models import ScopedRole
    return ScopedRole.objects.filter(
        user=user, is_active=True,
        group__name__in=['admin', 'admins_group'],
        org_unit__isnull=True, module__isnull=True,
    ).exists()


def _can(user, capability: str) -> bool:
    """Superuser/global-admin bypass, else CBAC capability check."""
    if not user or not user.is_authenticated:
        return False
    if is_global_admin(user):
        return True
    return has_capability(user, capability)


class PeopleAccess(BasePermission):
    """``people:view`` for reads, ``people:manage`` for writes."""

    def has_permission(self, request, view):
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return _can(request.user, 'people:view')
        return _can(request.user, 'people:manage')
