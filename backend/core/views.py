# File: core/views.py

from rest_framework import viewsets
from .models import Project, Cycle, Module
from .serializers import ProjectSerializer, CycleSerializer, ModuleSerializer
from rest_framework.permissions import IsAuthenticated
from accounts.context_mixin import ContextExtractorMixin

class ProjectViewSet(ContextExtractorMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Project.objects.all()
        return Project.objects.filter(tenant=self.request.user.tenant)

class CycleViewSet(ContextExtractorMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Cycle.objects.all()
    serializer_class = CycleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Cycle.objects.all()
        return Cycle.objects.filter(project__tenant=self.request.user.tenant)

class ModuleViewSet(ContextExtractorMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Module.objects.all()
    serializer_class = ModuleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        project_id, _ = self.get_project_and_module_id_from_request(self.request)
        if self.request.user.is_superuser:
            return Module.objects.all()
        qs = Module.objects.filter(project__tenant=self.request.user.tenant)
        if project_id:
            qs = qs.filter(project_id=project_id)
        return qs