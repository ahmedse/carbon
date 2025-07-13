# File: accounts/permissions.py

from rest_framework import permissions
from .rbac_utils import (
    user_has_project_role, user_has_module_role, get_allowed_module_ids
)

class HasScopedRole(permissions.BasePermission):
    """
    Centralized, robust RBAC for project/module roles.
    """
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        required_roles = getattr(view, 'required_role', None)
        if not required_roles:
            return False

        project_id = request.query_params.get("project_id")
        module_id = request.query_params.get("module_id")

        # Admins: allow all in project
        if user_has_project_role(user, project_id, ["admin", "admins_group"]):
            return True

        # dataowners_group logic
        if "dataowners_group" in required_roles:
            if view.__class__.__name__ == "ModuleViewSet" and getattr(view, "action", None) == "list":
                allowed = get_allowed_module_ids(user, project_id, ["dataowners_group"])
                return bool(allowed)
            if not module_id:
                return False
            return user_has_module_role(user, project_id, module_id, ["dataowners_group"])

        # Other roles (e.g., audit, dataowner)
        return user_has_project_role(user, project_id, required_roles)