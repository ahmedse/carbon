# core/views.py

from rest_framework import viewsets
from .models import Project
from .serializers import ProjectSerializer
from accounts.permissions import HasRBACPermission
from accounts.context_mixin import ContextExtractorMixin  # Import the mixin

class ProjectViewSet(ContextExtractorMixin, viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    # Add RBAC protection
    permission_classes = [HasRBACPermission]
    required_permission = 'view_project'

    def get_context(self, request):
        # Use the unified context extraction method from the mixin
        return self.get_context_from_request(request)