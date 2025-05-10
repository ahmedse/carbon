# core/views.py

from rest_framework import viewsets
from .models import Project
from .serializers import ProjectSerializer
from accounts.permissions import HasRBACPermission

class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    # Add RBAC protection
    permission_classes = [HasRBACPermission]
    required_permission = 'view_project'

    def get_context(self, request):
        # Find the project context for RBAC check
        project_id = self.kwargs.get('pk')
        from accounts.models import Context
        if project_id:
            return Context.objects.filter(type='project', project_id=project_id).first()
        return None  # If no context, permission will fail