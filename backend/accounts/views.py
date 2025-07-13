# File: accounts/views.py
# DRF views for tenants, users, scoped roles, and audit logs.

from rest_framework import viewsets
from rest_framework.permissions import BasePermission
from django.contrib.auth.models import Group
from .models import Tenant, User, ScopedRole, RoleAssignmentAuditLog
from .serializers import (
    TenantSerializer, UserSerializer, GroupSerializer,
    ScopedRoleSerializer, ScopedRoleCreateSerializer,
    RoleAssignmentAuditLogSerializer
)
from .permissions import HasScopedRole
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_roles(request):
    """
    Returns the current user's scoped roles in a flat format for the frontend.
    """
    user = request.user
    scoped_roles = user.scoped_roles.filter(is_active=True).select_related('tenant', 'project', 'module', 'group')

    roles = []
    for sr in scoped_roles:
        # Determine context type
        if sr.module:
            context_type = "module"
            module_id = sr.module.id
            module_name = str(sr.module)
            project_id = sr.project.id if sr.project else sr.module.project.id if sr.module.project else None
            project_name = str(sr.project) if sr.project else str(sr.module.project) if sr.module.project else None
        elif sr.project:
            context_type = "project"
            module_id = None
            module_name = None
            project_id = sr.project.id
            project_name = str(sr.project)
        else:
            context_type = "tenant"
            project_id = None
            project_name = None
            module_id = None
            module_name = None

        roles.append({
            "role": sr.group.name,
            "tenant": str(sr.tenant),
            "tenant_id": sr.tenant.id,
            "context_type": context_type,
            "project": project_name,
            "project_id": project_id,
            "module": module_name,
            "module_id": module_id,
            "active": sr.is_active,  # <-- add this line
        })

    return Response({
        "username": user.username,
        "roles": roles,   # <<--- this is what your frontend expects
    })

class IsSuperuser(BasePermission):
    """
    Allows access only to Django superusers.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_superuser)

class TenantViewSet(viewsets.ModelViewSet):
    """
    CRUD for tenants. Only Django superuser can manage tenants.
    """
    queryset = Tenant.objects.all()
    serializer_class = TenantSerializer
    permission_classes = [IsSuperuser]

class UserViewSet(viewsets.ModelViewSet):
    """
    CRUD for users.
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [HasScopedRole]
    required_role = "admin"  # Only users with 'admin' ScopedRole can manage users

class GroupViewSet(viewsets.ReadOnlyModelViewSet):
    """
    List/read roles (Django groups).
    """
    queryset = Group.objects.all()
    serializer_class = GroupSerializer
    permission_classes = [HasScopedRole]
    required_role = "admin"  # Only users with 'admin' ScopedRole can list groups

class ScopedRoleViewSet(viewsets.ModelViewSet):
    """
    CRUD for scoped role assignments.
    """
    queryset = ScopedRole.objects.all()
    permission_classes = [HasScopedRole]
    required_role = "admin"  # Only users with 'admin' ScopedRole can manage scoped roles

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ScopedRoleCreateSerializer
        return ScopedRoleSerializer

class RoleAssignmentAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only view for role assignment audit logs.
    """
    queryset = RoleAssignmentAuditLog.objects.all().order_by('-timestamp')
    serializer_class = RoleAssignmentAuditLogSerializer
    permission_classes = [HasScopedRole]
    required_role = "audit"  # Only users with 'audit' ScopedRole can view audit logs

    