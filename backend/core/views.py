from rest_framework import viewsets
from .models import Project, Cycle, Module
from .serializers import ProjectSerializer, CycleSerializer, ModuleSerializer
from rest_framework.permissions import IsAuthenticated
from accounts.context_mixin import ContextExtractorMixin

class ProjectViewSet(ContextExtractorMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Project.objects.none()
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Project.objects.all()
        return Project.objects.filter(tenant=self.request.user.tenant)

class CycleViewSet(ContextExtractorMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Cycle.objects.none()
    serializer_class = CycleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Cycle.objects.all()
        return Cycle.objects.filter(project__tenant=self.request.user.tenant)

class ModuleViewSet(ContextExtractorMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Module.objects.none()
    serializer_class = ModuleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Module.objects.all()
        return Module.objects.filter(project__tenant=self.request.user.tenant)