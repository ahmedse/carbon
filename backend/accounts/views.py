# File: accounts/views.py
# DRF views for tenants, users, scoped roles, and audit logs.

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import ScopedRole
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

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_roles(request):
    """
    Return all active roles (group names) for the current user,
    with context (tenant/project/module).
    """
    roles = []
    for r in ScopedRole.objects.filter(user=request.user, is_active=True).select_related('group', 'tenant', 'project', 'module'):
        roles.append({
            "id": r.id,
            "role": r.group.name,            # The role name (group name)
            "tenant_id": r.tenant_id,
            "tenant": str(r.tenant),
            "project_id": r.project_id,
            "project": str(r.project) if r.project else None,
            "module_id": r.module_id,
            "module": str(r.module) if r.module else None,
            "context_type": (
                "module" if r.module_id else
                "project" if r.project_id else
                "tenant"
            ),
            "active": r.is_active,
        })
    return Response({"roles": roles})