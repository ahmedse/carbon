# File: accounts/views.py
# DRF views for users, scoped roles, and audit logs.

from rest_framework import status, viewsets
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from django.contrib.auth.models import Group
from .models import User, ScopedRole, RoleAssignmentAuditLog
from .serializers import (
    UserSerializer, GroupSerializer,
    ScopedRoleSerializer, ScopedRoleCreateSerializer,
    RoleAssignmentAuditLogSerializer
)
from .permissions import HasScopedRole
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.exceptions import TokenError


class LoginRateThrottle(AnonRateThrottle):
    """Limit login attempts per IP to reduce brute-force attacks."""

    scope = 'login'


class ThrottledTokenObtainPairView(TokenObtainPairView):
    """JWT obtain view with request throttling."""

    throttle_classes = [LoginRateThrottle]

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_roles(request):
    """
    Returns the current user's scoped roles in a flat format for the frontend.
    """
    user = request.user
    scoped_roles = user.scoped_roles.filter(is_active=True).select_related(
        'org_unit', 'module', 'group'
    )

    roles = []
    for sr in scoped_roles:
        roles.append({
            "role": sr.group.name,
            "context_type": "module" if sr.module_id else ("org_unit" if sr.org_unit_id else "global"),
            "org_unit": str(sr.org_unit) if sr.org_unit else None,
            "org_unit_id": sr.org_unit_id,
            "module": str(sr.module) if sr.module else None,
            "module_id": sr.module_id,
            "active": sr.is_active,
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


class LogoutView(APIView):
    """Blacklist refresh tokens on logout to prevent reuse."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response(
                {'detail': 'refresh token required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError:
            return Response(
                {'detail': 'invalid or expired refresh token'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({'detail': 'Logout successful'}, status=status.HTTP_200_OK)

    