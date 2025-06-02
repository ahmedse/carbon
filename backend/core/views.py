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
        qs = Module.objects.all() if self.request.user.is_superuser else Module.objects.filter(project__tenant=self.request.user.tenant)
        project_id = self.get_project_id_from_request(self.request)
        print(f"[DEBUG] project_id {project_id}")
        if project_id:
            qs = qs.filter(project_id=project_id)
            print(f"[DEBUG] Modules list for project {project_id} : {qs}")
        return qs

    # def get_queryset(self):
    #     if self.request.user.is_superuser:
    #         return Module.objects.all()
    #     return Module.objects.filter(project__tenant=self.request.user.tenant)

    