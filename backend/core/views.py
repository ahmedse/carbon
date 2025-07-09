# File: core/views.py

from rest_framework import viewsets
from .models import Project, Module
from .serializers import ProjectSerializer, ModuleSerializer
from accounts.permissions import HasScopedRole

class ProjectViewSet(viewsets.ModelViewSet):
    """
    CRUD for projects.
    """
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [HasScopedRole]
    required_role = ("dataowner", "admins_group", "dataowners_group")

    def get_permissions(self):
        project_id = self.request.query_params.get("project_id")
        print("[DEBUG] get_permissions called")
        print("[DEBUG] Query params in get_permissions:", self.request.query_params)
        print("[DEBUG] project_id from query params:", project_id)
        if project_id:
            try:
                self.project = Project.objects.get(pk=project_id)
                print("[DEBUG] Set self.project in get_permissions:", self.project)
            except Project.DoesNotExist:
                print("[DEBUG] Project.DoesNotExist in get_permissions for id", project_id)
                self.project = None
        else:
            print("[DEBUG] No project_id in query params in get_permissions!")
            self.project = None
        return super().get_permissions()
    
    def get_queryset(self):
        user = self.request.user
        from accounts.models import ScopedRole

        # Only within the user's tenant
        tenant = user.tenant

        # Projects where user has a ScopedRole (project or module scope)
        # Get IDs from project-scoped or module-scoped roles
        project_ids = set(
            ScopedRole.objects.filter(
                user=user,
                tenant=tenant,
                is_active=True,
            )
            .exclude(project=None)
            .values_list('project_id', flat=True)
        )
        # Add projects from module-scoped roles
        module_projects = Module.objects.filter(
            id__in=ScopedRole.objects.filter(
                user=user,
                tenant=tenant,
                is_active=True,
            ).exclude(module=None).values_list('module_id', flat=True)
        ).values_list('project_id', flat=True)
        project_ids.update(module_projects)

        # Return only projects the user can access in their tenant
        return Project.objects.filter(id__in=project_ids, tenant=tenant)

class ModuleViewSet(viewsets.ModelViewSet):
    """
    CRUD for modules.
    """
    queryset = Module.objects.all()
    serializer_class = ModuleSerializer
    permission_classes = [HasScopedRole]
    required_role = ("admin", "admins_group", "dataowners_group")

    def get_permissions(self):
        # Set project context before checking permissions
        project_id = self.request.query_params.get("project_id")
        if project_id:
            try:
                self.project = Project.objects.get(pk=project_id)
            except Project.DoesNotExist:
                self.project = None
        else:
            self.project = None
        return super().get_permissions()

    def get_queryset(self):
        user = self.request.user
        from accounts.models import ScopedRole

        tenant = user.tenant
        project_id = self.request.query_params.get("project_id")

        # Only module-level ScopedRoles
        module_ids = list(
            ScopedRole.objects.filter(
                user=user,
                tenant=tenant,
                is_active=True,
            ).exclude(module=None).values_list('module_id', flat=True)
        )
        print("[DEBUG] module_ids:", module_ids)

        # Only project-level ScopedRoles (module__isnull=True)
        project_ids = list(
            ScopedRole.objects.filter(
                user=user,
                tenant=tenant,
                is_active=True,
                module__isnull=True
            ).exclude(project=None).values_list('project_id', flat=True)
        )
        print("[DEBUG] project_ids:", project_ids)

        if project_id:
            project_id = int(project_id)
            print("[DEBUG] Filtering with project_id:", project_id)
            if project_id in project_ids:
                print("[DEBUG] User has project-level role for this project")
                return Module.objects.filter(project_id=project_id, project__tenant=tenant)
            else:
                print("[DEBUG] User does NOT have project-level role, only module-level")
                return Module.objects.filter(id__in=module_ids, project_id=project_id, project__tenant=tenant)

        modules_by_project = Module.objects.filter(project_id__in=project_ids, project__tenant=tenant)
        modules_by_module = Module.objects.filter(id__in=module_ids, project__tenant=tenant)
        print("[DEBUG] modules_by_project:", list(modules_by_project.values_list('id', flat=True)))
        print("[DEBUG] modules_by_module:", list(modules_by_module.values_list('id', flat=True)))
        return (modules_by_project | modules_by_module).distinct()
