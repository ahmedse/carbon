# File: accounts/permissions.py

from rest_framework.permissions import BasePermission
from .utils import user_has_permission

class HasRBACPermission(BasePermission):
    """
    Checks if the user has the required RBAC permission for the requested project context.
    The project context ID must be provided by the view via get_project_id_from_request(request).
    """

    def has_permission(self, request, view):
        print("[DEBUG] HasRBACPermission called")

        if not request.user.is_authenticated:
            return False
        
        print("[DEBUG] HasRBACPermission called")
        print("[DEBUG] user.is_authenticated:", getattr(request.user, 'is_authenticated', None))
        print("[DEBUG] user:", getattr(request, 'user', None))

        required_permission = getattr(view, 'required_permission', None)
        if not required_permission:
            return True  # No specific permission required

        # Extract project_id from request using mixin (view must inherit from ContextExtractorMixin)
        if hasattr(view, 'get_project_id_from_request'):
            project_id = view.get_project_id_from_request(request)
        else:
            project_id = None

        if not project_id:
            return False  # No project context provided

        return user_has_permission(request.user, required_permission, project_id)
    