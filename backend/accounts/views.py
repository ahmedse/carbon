from rest_framework import viewsets
from .models import Tenant, Role, Context, RoleAssignment, User
from core.models import Project, Module
from .serializers import (
    TenantSerializer, RoleSerializer, ContextSerializer,
    RoleAssignmentSerializer, UserSerializer, ProjectSerializer, ModuleSerializer
)
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.db import models
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

class TenantViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Tenant.objects.none()
    serializer_class = TenantSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Only allow users to see their own tenant
        if self.request.user.is_superuser:
            return Tenant.objects.all()
        return Tenant.objects.filter(id=self.request.user.tenant_id)

class UserViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.none()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_superuser:
            return User.objects.all()
        return User.objects.filter(tenant=self.request.user.tenant)

class ProjectViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Project.objects.none()
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Project.objects.all()
        return Project.objects.filter(tenant=self.request.user.tenant)

class ModuleViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Module.objects.none()
    serializer_class = ModuleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Module.objects.all()
        return Module.objects.filter(project__tenant=self.request.user.tenant)

class RoleViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Role.objects.none()
    serializer_class = RoleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Role.objects.all()

class ContextViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Context.objects.none()
    serializer_class = ContextSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Context.objects.all()
        return Context.objects.filter(
            models.Q(project__tenant=self.request.user.tenant) |
            models.Q(module__project__tenant=self.request.user.tenant)
        )

class RoleAssignmentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = RoleAssignment.objects.none()
    serializer_class = RoleAssignmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_superuser:
            return RoleAssignment.objects.all()
        return RoleAssignment.objects.filter(user__tenant=self.request.user.tenant)

class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['username'] = user.username
        token['tenant'] = user.tenant.name if user.tenant else None
        return token

class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        import logging
        logger = logging.getLogger('django')
        logger.debug(f"Token request data: {request.data}")
        return super().post(request, *args, **kwargs)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_roles(request):
    user = request.user
    print("DEBUG: user =", user)
    assignments = user.role_assignments.select_related('role', 'context', 'context__project', 'context__module').filter(is_active=True)
    print("DEBUG: assignments =", assignments)
    for a in assignments:
        print("DEBUG: a =", a, "role:", a.role.name, "context:", a.context)
    roles = [
        {
            "role": a.role.name,
            "context_id": a.context.id,
            "context_type": a.context.type,
            "project": a.context.project.name if a.context.project else None,
            "project_id": a.context.project.id if a.context.project else None,
            "module": a.context.module.name if a.context.module else None,
            "module_id": a.context.module.id if a.context.module else None,
            "permissions": [p.code for p in a.role.permissions.all()],
            "active": a.is_active,
        }
        for a in assignments
    ]
    return Response({"roles": roles})