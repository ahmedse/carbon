# File: accounts/permissions.py

from rest_framework import permissions
from .models import ScopedRole

class HasScopedRole(permissions.BasePermission):
    """
    Permission class to check if the user has a given role within a specific scope.
    - Always requires project_id.
    - If user has admin/admins_group, allow with project_id only.
    - If user ONLY has dataowners_group, require module_id as well and check module-level role.
    """

    def has_permission(self, request, view):
        user = request.user
        # print("[DEBUG][HasScopedRole] has_permission called for user:", user)

        if not user or not user.is_authenticated:
            print("[ERROR][HasScopedRole] User not authenticated")
            return False

        required_roles = getattr(view, 'required_role', None)
        if not required_roles:
            print("[ERROR][HasScopedRole] No required_role configured on view")
            return False

        # Always require project_id
        project_id = request.query_params.get("project_id")
        if not project_id:
            print("[ERROR][HasScopedRole] Missing project_id in request")
            return False

        # Get all relevant ScopedRoles for this user and project
        from core.models import Project, Module
        try:
            project = Project.objects.get(pk=project_id)
        except Project.DoesNotExist:
            print(f"[ERROR][HasScopedRole] Project id={project_id} does not exist")
            return False

        # Compose group filter
        if isinstance(required_roles, (list, tuple)):
            group_filter = {'group__name__in': required_roles}
        else:
            group_filter = {'group__name': required_roles}

        qs = ScopedRole.objects.filter(user=user, is_active=True, project=project, **group_filter)
        user_roles = set(qs.values_list('group__name', flat=True))
        # print("[DEBUG][HasScopedRole] User roles for project:", user_roles)

        # Admin/admins_group logic
        if "admin" in user_roles or "admins_group" in user_roles:
            # print("[DEBUG][HasScopedRole] User is admin/admins_group for project, access granted")
            return True

        # dataowners_group logic
        if "dataowners_group" in user_roles:
            module_id = request.query_params.get("module_id")
            if not module_id:
                print("[ERROR][HasScopedRole] dataowners_group must provide module_id")
                return False
            try:
                module = Module.objects.get(pk=module_id, project=project)
            except Module.DoesNotExist:
                print(f"[ERROR][HasScopedRole] Module id={module_id} for project={project_id} does not exist")
                return False
            has_module_role = ScopedRole.objects.filter(
                user=user, is_active=True, project=project, module=module, group__name="dataowners_group"
            ).exists()
            # print(f"[DEBUG][HasScopedRole] dataowners_group for module: {has_module_role}")
            return has_module_role

        print("[ERROR][HasScopedRole] User does not have any allowed roles for this project")
        return False