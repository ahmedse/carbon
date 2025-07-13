# File: core/views.py

from .models import Project, Module
from .serializers import ProjectSerializer, ModuleSerializer
from accounts.permissions import HasScopedRole
from accounts.rbac_utils import get_allowed_project_ids, get_allowed_module_ids, user_has_project_role
from .models import Feedback
from .serializers import FeedbackSerializer
from rest_framework import mixins, viewsets

class ProjectViewSet(viewsets.ModelViewSet):
    """
    CRUD for projects.
    """
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [HasScopedRole]
    required_role = ("dataowner", "admins_group", "dataowners_group")

    def get_queryset(self):
        user = self.request.user
        tenant = getattr(user, "tenant", None)
        return Project.objects.filter(
            id__in=get_allowed_project_ids(user, tenant, self.required_role), tenant=tenant
        )

class ModuleViewSet(viewsets.ModelViewSet):
    """
    CRUD for modules.
    """
    queryset = Module.objects.all()
    serializer_class = ModuleSerializer
    permission_classes = [HasScopedRole]
    required_role = ("admin", "admins_group", "dataowners_group")

    def get_queryset(self):
        user = self.request.user
        tenant = getattr(user, "tenant", None)
        project_id = self.request.query_params.get("project_id")
        module_id = self.request.query_params.get("module_id")

        if not project_id:
            return Module.objects.none()

        # Admins or project-level roles: see all modules in the project
        if user_has_project_role(user, project_id, ["admin", "admins_group"]):
            return Module.objects.filter(project_id=project_id, project__tenant=tenant)

        # dataowners_group: only modules where user has module-level scoped role
        allowed_ids = get_allowed_module_ids(user, project_id, ["dataowners_group"])
        if allowed_ids:
            return Module.objects.filter(id__in=allowed_ids, project_id=project_id, project__tenant=tenant)
        return Module.objects.none()

class FeedbackViewSet(mixins.CreateModelMixin,
                      mixins.ListModelMixin,
                      viewsets.GenericViewSet):
    """
    API for submitting and listing feedback.
    Only staff can list; anyone can submit.
    """
    queryset = Feedback.objects.all()
    serializer_class = FeedbackSerializer

    def get_permissions(self):
        # Only allow listing for staff, allow create for anyone (or customize as needed)
        from rest_framework.permissions import IsAdminUser, AllowAny
        if self.action == 'list':
            return [IsAdminUser()]
        return [AllowAny()]