# File: accounts/permissions.py
# Custom DRF permissions for scoped RBAC.

from rest_framework import permissions
from .models import ScopedRole

class HasScopedRole(permissions.BasePermission):
    """
    Permission class to check if the user has a given role within a specific scope.
    Usage:
        - Set `required_role`, `project`, `module` attributes in the view.
    """
    def has_permission(self, request, view):
        user = request.user
        print("[DEBUG] has_permission called")
        print(f"[HasScopedRole] User: {user} ({user.pk}), is_authenticated={user.is_authenticated}")

        if not user.is_authenticated:
            return False

        required_role = getattr(view, 'required_role', None)
        project = getattr(view, 'project', None)
        module = getattr(view, 'module', None)

        # extract from query params if missing
        if not project:
            project_id = request.query_params.get("project_id")
            if project_id:
                from core.models import Project
                try:
                    project = Project.objects.get(pk=project_id)
                except Project.DoesNotExist:
                    project = None
        if not module:
            module_id = request.query_params.get("module_id")
            if module_id:
                from core.models import Module
                try:
                    module = Module.objects.get(pk=module_id)
                except Module.DoesNotExist:
                    module = None

        print(f"[HasScopedRole] required_role={required_role}, project={project}, module={module}")

        if not required_role:
            return False

        # Support both string and list for required_role
        if isinstance(required_role, (list, tuple)):
            group_filter = {'group__name__in': required_role}
        else:
            group_filter = {'group__name': required_role}

        # Try matching most-specific to least-specific scope
        qs = ScopedRole.objects.filter(user=user, is_active=True, **group_filter)

        # 1. If module is set, allow:
        #    - A role scoped directly to the module
        #    - Or a role scoped to the whole project (module__isnull=True)
        if module:
            return qs.filter(module=module).exists() or qs.filter(project=project, module__isnull=True).exists()
        # 2. If project is set, allow:
        #    - A role scoped to the project with module__isnull=True
        elif project:
            return qs.filter(project=project).exists()
        # 3. Otherwise, allow global role:
        else:
            return qs.filter(project__isnull=True, module__isnull=True).exists()