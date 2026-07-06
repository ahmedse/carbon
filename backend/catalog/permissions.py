# catalog/permissions.py
from rest_framework.permissions import BasePermission, SAFE_METHODS
from accounts.models import ScopedRole


class ReadAnyWriteAdmin(BasePermission):
    """Any authenticated user can read; only superusers or members of the
    `admins_group` scoped role can write."""
    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        if user.is_superuser:
            return True
        return ScopedRole.objects.filter(user=user, is_active=True, group__name='admins_group').exists()
