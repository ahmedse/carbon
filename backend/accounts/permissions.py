# File: accounts/permissions.py
# Purpose: Custom permission class for RBAC enforcement in DRF views.

from rest_framework.permissions import BasePermission
from .utils import user_has_permission
from .models import Context

class HasRBACPermission(BasePermission):
    """
    Checks if the user has a required RBAC permission for a given context.
    The view must set 'required_permission' and implement 'get_context(request)'.
    """
    def has_permission(self, request, view):
        """
        Returns True if the user has the required permission in the context.
        """
        if not request.user.is_authenticated:
            return False

        required_permission = getattr(view, 'required_permission', None)
        if not required_permission:
            return True  # No RBAC specified

        context = view.get_context(request)
        if not context:
            return False
        return user_has_permission(request.user, required_permission, context)