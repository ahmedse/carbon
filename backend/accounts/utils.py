# accounts/utils.py

from .models import RoleAssignment
from core.models import Module
import logging

# RBAC Matrix (Explicit)
# | Role      | context   | view_data | manage_data | view_schema | manage_schema | manage_module | manage_project |
# |-----------|-----------|-----------|-------------|-------------|---------------|--------------|---------------|
# | admin     | project   |    YES    |    YES      |    YES      |     YES       |     YES      |     YES       |
# | admin     | module    |    YES    |    YES      |    YES      |     YES       |     YES      |     YES       |
# | audit     | project   |    NO     |    NO       |    NO       |     NO        |     NO       |     NO        |
# | audit     | module    |    YES    |    YES      |    NO       |     NO        |     YES      |     NO        |
# | dataowner | project   |    NO     |    NO       |    NO       |     NO        |     NO       |     NO        |
# | dataowner | module    |    YES    |    YES      |    NO       |     NO        |     NO       |     NO        |

ADMIN_ROLE = 'admin_role'
AUDIT_ROLE = 'audit_role'
DATAOWNER_ROLE = 'dataowner_role'

# Permission codes (must match your Permission model codes)
VIEW_DATA = "view_data"
MANAGE_DATA = "manage_data"
VIEW_SCHEMA = "view_schema"
MANAGE_SCHEMA = "manage_schema"
MANAGE_MODULE = "manage_module"
MANAGE_PROJECT = "manage_project"

# Explicit permissions per role and context, no implication
ROLE_PERMISSION_MAP = {
    # admin_role: all permissions at both project and module context
    ADMIN_ROLE: {VIEW_DATA, MANAGE_DATA, VIEW_SCHEMA, MANAGE_SCHEMA, MANAGE_MODULE, MANAGE_PROJECT},
    # audit_role: only explicit permissions at module context
    AUDIT_ROLE: {VIEW_DATA, MANAGE_DATA, MANAGE_MODULE},
    # dataowner_role: only explicit permissions at module context
    DATAOWNER_ROLE: {VIEW_DATA, MANAGE_DATA},
}

DEBUG = True  # Set to True to enable debug prints

def debug(msg):
    if DEBUG:
        print("[RBAC DEBUG]", msg)
        logging.getLogger('accounts.rbac').debug(msg)

def get_role_for_permission(permission_code):
    """Returns set of roles that explicitly grant this permission."""
    allowed = {role for role, perms in ROLE_PERMISSION_MAP.items() if permission_code in perms}
    debug(f"get_role_for_permission({permission_code}) = {allowed}")
    return allowed

def user_has_permission(user, permission_code, project_id, module_id=None):
    """
    Explicit RBAC check: user must have a RoleAssignment for the given context (module or project)
    that grants the exact permission_code (no implication).
    """
    if user.is_superuser:
        debug(f"user {user} is superuser -> ALLOW")
        return True

    allowed_roles = get_role_for_permission(permission_code)

    if module_id is not None:
        # Context is module
        try:
            module = Module.objects.get(id=module_id, project_id=project_id)
            debug(f"Module {module_id} found for project {project_id}")
        except Module.DoesNotExist:
            debug(f"Module {module_id} does not exist for project {project_id}")
            return False

        # Module-level: check for explicit RoleAssignment on this module
        for role_name in allowed_roles:
            if RoleAssignment.objects.filter(
                user=user, is_active=True,
                context__type='module',
                context__module_id=module_id,
                role__name=role_name,
                role__permissions__code=permission_code,
            ).exists():
                debug(f"User {user} has {role_name} on module {module_id} for permission {permission_code}")
                return True

        # admin_role can grant module-level perms via project-level assignment, if and only if admin_role has that permission
        if ADMIN_ROLE in allowed_roles:
            if RoleAssignment.objects.filter(
                user=user, is_active=True,
                context__type='project',
                context__project_id=project_id,
                role__name=ADMIN_ROLE,
                role__permissions__code=permission_code,
            ).exists():
                debug(f"User {user} has admin_role on project {project_id} for permission {permission_code} (module context)")
                return True

        debug(f"User {user} does NOT have permission {permission_code} on module {module_id}")
        return False

    # Context is project (no module)
    # Only admin_role grants at project level in this explicit model
    if project_id is not None:
        if ADMIN_ROLE in allowed_roles:
            if RoleAssignment.objects.filter(
                user=user, is_active=True,
                context__type='project',
                context__project_id=project_id,
                role__name=ADMIN_ROLE,
                role__permissions__code=permission_code,
            ).exists():
                debug(f"User {user} has admin_role on project {project_id} for permission {permission_code} (project context)")
                return True

        debug(f"User {user} does NOT have permission {permission_code} on project {project_id}")
        return False

    debug(f"User {user} denied {permission_code}: no context")
    return False