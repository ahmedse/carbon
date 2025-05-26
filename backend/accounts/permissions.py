# File: accounts/permissions.py

from rest_framework.permissions import BasePermission
from .utils import user_has_permission

class HasRBACPermission(BasePermission):
    """
    Checks if the user has the required RBAC permission for the requested context.
    The context must be provided by the view via get_context_from_request(request).
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        required_permission = getattr(view, 'required_permission', None)
        if not required_permission:
            return True

        # Context extraction
        if hasattr(view, 'get_context_from_request'):
            context = view.get_context_from_request(request)
        else:
            context = None

        if not context:
            return False

        has_perm = user_has_permission(request.user, required_permission, context)
        return has_perm