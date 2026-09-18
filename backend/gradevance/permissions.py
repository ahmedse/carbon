"""CBAC permission helpers for GradeVance API views."""
from rest_framework.permissions import BasePermission

from accounts.capabilities import has_capability


def _can(user, capability: str) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    from accounts.models import ScopedRole

    if ScopedRole.objects.filter(
        user=user,
        is_active=True,
        group__name__in=["admin", "admins_group"],
        org_unit__isnull=True,
        module__isnull=True,
    ).exists():
        return True
    return has_capability(user, capability)


class GradevanceViewAccess(BasePermission):
    def has_permission(self, request, view):
        return _can(request.user, "gradevance:view")


class GradevanceManageAccess(BasePermission):
    def has_permission(self, request, view):
        return _can(request.user, "gradevance:manage")


class GradevanceMarkAccess(BasePermission):
    def has_permission(self, request, view):
        return _can(request.user, "gradevance:mark") or _can(request.user, "gradevance:manage")


class GradevanceSubmitAccess(BasePermission):
    def has_permission(self, request, view):
        return (
            _can(request.user, "gradevance:submit")
            or _can(request.user, "gradevance:manage")
            or _can(request.user, "gradevance:view")
        )


class GradevanceReadOrSubmit(BasePermission):
    """GET → view; POST submit path → submit/manage."""

    def has_permission(self, request, view):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return _can(request.user, "gradevance:view") or _can(
                request.user, "gradevance:submit"
            )
        return (
            _can(request.user, "gradevance:submit")
            or _can(request.user, "gradevance:manage")
        )
