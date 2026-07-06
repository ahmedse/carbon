# File: accounts/permissions.py

# File: accounts/permissions.py
from rest_framework import permissions
from .rbac_utils import (
    user_has_global_role, user_has_module_role, get_allowed_org_unit_ids,
)


class HasScopedRole(permissions.BasePermission):
    """
    RBAC: superusers and global admins pass everything. Otherwise access is granted at
    module level OR when the target module's org_unit is within the user's allowed org subtree.
    """
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        required_roles = getattr(view, 'required_role', None)
        if not required_roles:
            return False
        if isinstance(required_roles, str):
            required_roles = (required_roles,)

        if user.is_superuser:
            return True
        if user_has_global_role(user, ["admin", "admins_group"]):
            return True

        module_id = request.query_params.get("module_id") or request.data.get("module_id")
        if module_id:
            if user_has_module_role(user, module_id, ["admin", "admins_group"]):
                return True
            if user_has_module_role(user, module_id, required_roles):
                return True
            from core.models import Module
            try:
                mod = Module.objects.get(pk=module_id)
            except Module.DoesNotExist:
                mod = None
            if mod and mod.org_unit_id:
                allowed_orgs = get_allowed_org_unit_ids(
                    user, list(required_roles) + ["admin", "admins_group"]
                )
                if mod.org_unit_id in allowed_orgs:
                    return True

        if user_has_global_role(user, required_roles):
            return True

        return False