# File: accounts/permissions.py

from rest_framework.permissions import BasePermission
from .utils import user_has_permission

class HasRBACPermission(BasePermission):
    """
    Checks if the user has the required RBAC permission for the requested project/module context.
    The project_id and module_id must be provided by the view via get_project_and_module_id_from_request(request).
    """
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        required_permission = getattr(view, 'required_permission', None)
        if not required_permission:
            return True  # No specific permission required

        if hasattr(view, 'get_project_and_module_id_from_request'):
            project_id, module_id = view.get_project_and_module_id_from_request(request)
        else:
            project_id = module_id = None

        if not project_id and not module_id:
            return False  # No context provided

        return user_has_permission(request.user, required_permission, project_id, module_id)