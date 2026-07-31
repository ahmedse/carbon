# File: accounts/permissions.py

# File: accounts/permissions.py
from rest_framework import permissions
from .rbac_utils import (
    user_has_global_role, user_has_module_role, get_allowed_org_unit_ids,
    ADMIN_ROLES, get_steward_org_unit_ids, VISIBILITY_ROLES,
)

# Read-only roles: can view but NOT create/update/delete
READ_ONLY_ROLES = {"viewers_group", "analysts_group"}


class HasScopedRole(permissions.BasePermission):
    """
    RBAC: superusers and global admins pass everything. Otherwise access is granted at
    module level OR when the target module's org_unit is within the user's allowed org subtree.
    
    Enhanced to resolve module_id from data_table when data_table is provided but module_id is not.
    
    Write operations (POST/PUT/PATCH/DELETE) are blocked for read-only roles
    (viewers_group, analysts_group).
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

        # For write operations, check the user isn't limited to read-only roles
        if request.method not in permissions.SAFE_METHODS:
            # Determine which of the required_roles the user actually has (globally or scoped)
            user_roles = set(required_roles) & READ_ONLY_ROLES
            # If ALL the user's qualifying roles are read-only, deny write
            if user_roles:
                # Check if user has any write-capable roles (not in READ_ONLY_ROLES)
                write_roles = set(required_roles) - READ_ONLY_ROLES
                if not write_roles or not user_has_global_role(user, list(write_roles)):
                    # Check scoped write roles
                    has_write_role = False
                    if write_roles:
                        from .models import ScopedRole
                        has_write_role = ScopedRole.objects.filter(
                            user=user, is_active=True,
                            group__name__in=list(write_roles),
                        ).exists()
                    if not has_write_role:
                        return False

        module_id = request.query_params.get("module_id") or request.data.get("module_id")
        
        # FIX: Resolve module_id from data_table if not provided
        if not module_id:
            data_table_id = request.query_params.get("data_table") or request.data.get("data_table")
            if data_table_id:
                try:
                    from dataschema.models import DataTable
                    table = DataTable.objects.select_related('module').get(pk=data_table_id)
                    module_id = table.module_id
                except (DataTable.DoesNotExist, ValueError, TypeError):
                    pass
        
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


class ReadAnyWriteGlobalAdmin(permissions.BasePermission):
    """Any authenticated user can read governance resources.
    Only GLOBAL admins can write:
    - superusers, OR
    - admins_group with org_unit=None (global scope)

    Org-scoped admins are read-only.
    """
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        if user.is_superuser:
            return True
        return bool(user_has_global_role(user, ['admins_group']))


class ReadScopedWriteAdmin(permissions.BasePermission):
    """Schema resource permission for DataTable and DataField.
    
    Read access: org-scoped users (data-owners, auditors, admins) within their scope
    Write access: ONLY global admins (schema management is admin-only)
    
    Uses HasScopedRole for read permission checking (org-scoped filtering).
    Uses ReadAnyWriteGlobalAdmin logic for write protection.
    """
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        
        # Write operations: only global admins
        if request.method not in permissions.SAFE_METHODS:
            if user.is_superuser:
                return True
            return bool(user_has_global_role(user, ['admins_group']))
        
        # Read operations: use HasScopedRole logic
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
        
        # Resolve module_id from data_table if not provided
        if not module_id:
            data_table_id = request.query_params.get("data_table") or request.data.get("data_table")
            if data_table_id:
                try:
                    from dataschema.models import DataTable
                    table = DataTable.objects.select_related('module').get(pk=data_table_id)
                    module_id = table.module_id
                except (DataTable.DoesNotExist, ValueError, TypeError):
                    pass
        
        # For DataTable detail views, resolve module_id from pk
        if not module_id and hasattr(view, 'kwargs') and 'pk' in view.kwargs:
            try:
                from dataschema.models import DataTable
                table_id = view.kwargs['pk']
                table = DataTable.objects.select_related('module').get(pk=table_id)
                module_id = table.module_id
            except (DataTable.DoesNotExist, ValueError, TypeError, AttributeError):
                pass
        
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


class CanManageScopedRoles(permissions.BasePermission):
    """Allows superusers, global admins, and org-scoped stewards (admins_group on any org unit).
    Subtree enforcement + anti-escalation is done in the viewset (get_queryset / perform_*)."""

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        if user_has_global_role(user, ADMIN_ROLES):
            return True
        return bool(get_steward_org_unit_ids(user))