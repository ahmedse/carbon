# File: core/views.py

from rest_framework import viewsets
from .models import Project, Cycle, Module
from .serializers import ProjectSerializer, CycleSerializer, ModuleSerializer
from accounts.permissions import HasRBACPermission
from accounts.context_mixin import ContextExtractorMixin

class ProjectViewSet(ContextExtractorMixin, viewsets.ModelViewSet):
    queryset = Project.objects.none()  # For DRF router introspection
    serializer_class = ProjectSerializer
    permission_classes = [HasRBACPermission]
    required_permission = 'view_project'

    def get_queryset(self):
        # Tenant enforcement: users only see their own tenant's projects
        return Project.objects.filter(tenant=self.request.user.tenant)

    def get_context(self, request):
        return self.get_context_from_request(request)

class CycleViewSet(ContextExtractorMixin, viewsets.ModelViewSet):
    queryset = Cycle.objects.none()  # For DRF router introspection
    serializer_class = CycleSerializer
    permission_classes = [HasRBACPermission]
    required_permission = 'view_project'

    def get_queryset(self):
        # Only cycles in projects belonging to this user's tenant
        return Cycle.objects.filter(project__tenant=self.request.user.tenant)

    def get_context(self, request):
        return self.get_context_from_request(request)

class ModuleViewSet(ContextExtractorMixin, viewsets.ModelViewSet):
    queryset = Module.objects.none()  # For DRF router introspection
    serializer_class = ModuleSerializer
    permission_classes = [HasRBACPermission]
    required_permission = 'view_project'

    def get_queryset(self):
        # Only modules in projects belonging to this user's tenant
        return Module.objects.filter(project__tenant=self.request.user.tenant)

    def get_context(self, request):
        return self.get_context_from_request(request)