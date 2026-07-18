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
from .permissions import HasScopedRole, CanManageScopedRoles
from .rbac_utils import user_is_global_admin, get_steward_org_unit_ids
from rest_framework.exceptions import PermissionDenied
from django.db.models import Q
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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me_context(request):
    """
    Returns the current user's context card for frontend perspective resolution.
    Includes: user info, roles, perspectives available, org units, module count.
    
    Frontend uses this to decide which perspective tabs to show and auto-set default perspective.
    """
    from .rbac_utils import (
        user_is_global_admin, get_allowed_org_unit_ids, get_allowed_module_ids,
        VISIBILITY_ROLES
    )
    from mdm.models import OrgUnit
    from core.models import Module
    
    user = request.user
    
    # Get all active scoped roles
    scoped_roles = user.scoped_roles.filter(is_active=True).select_related('group', 'org_unit')
    role_names = list(set(r.group.name for r in scoped_roles))
    is_global = user_is_global_admin(user)
    
    # Determine available perspectives for this user
    perspectives = ['dashboards']  # all users see dashboards
    has_data_role = any(r in role_names for r in ['dataowners_group', 'auditors_group'])
    has_admin_role = 'admins_group' in role_names
    
    if has_data_role or has_admin_role:
        perspectives.append('data_entry')
    if has_admin_role:
        perspectives.append('admin')
    
    # Org units the user can see
    if is_global:
        org_units = list(OrgUnit.objects.values('id', 'name', 'org_type')[:100])
    else:
        allowed_ids = get_allowed_org_unit_ids(user, VISIBILITY_ROLES)
        org_units = list(OrgUnit.objects.filter(id__in=allowed_ids).values('id', 'name', 'org_type'))
    
    # Module count
    if is_global:
        module_count = Module.objects.count()
    else:
        module_count = len(get_allowed_module_ids(user, VISIBILITY_ROLES))
    
    return Response({
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'full_name': f"{user.first_name} {user.last_name}".strip() or user.username,
        },
        'roles': role_names,
        'is_global_admin': is_global,
        'perspectives': perspectives,
        'org_units': org_units,
        'module_count': module_count,
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

    - Superusers / global admins: full access.
    - Org-scoped stewards (admins_group on an org unit): may list/create/delete role
      assignments ONLY within their own org subtree, and NEVER global roles.
    """
    queryset = ScopedRole.objects.all()
    permission_classes = [CanManageScopedRoles]

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ScopedRoleCreateSerializer
        return ScopedRoleSerializer

    def get_queryset(self):
        user = self.request.user
        if user_is_global_admin(user):
            return ScopedRole.objects.all()
        allowed = get_steward_org_unit_ids(user)
        # Only assignments whose target org (directly or via module) is in the steward's subtree.
        return ScopedRole.objects.filter(
            Q(org_unit_id__in=allowed) | Q(module__org_unit_id__in=allowed)
        )

    def _assert_within_subtree(self, org_unit, module):
        """Anti-escalation guard: a steward may only target an org unit inside their subtree,
        never a global role (org_unit=None AND module=None) and never a foreign subtree."""
        user = self.request.user
        if user_is_global_admin(user):
            return
        allowed = get_steward_org_unit_ids(user)
        target_org_id = None
        if org_unit is not None:
            target_org_id = org_unit.id if hasattr(org_unit, 'id') else org_unit
        elif module is not None:
            target_org_id = getattr(module, 'org_unit_id', None)
        if not target_org_id or target_org_id not in allowed:
            raise PermissionDenied(
                "You can only manage role assignments within your own organization units."
            )

    def perform_create(self, serializer):
        self._assert_within_subtree(
            serializer.validated_data.get('org_unit'),
            serializer.validated_data.get('module'),
        )
        serializer.save()

    def perform_update(self, serializer):
        self._assert_within_subtree(
            serializer.validated_data.get('org_unit'),
            serializer.validated_data.get('module'),
        )
        serializer.save()

    def perform_destroy(self, instance):
        self._assert_within_subtree(instance.org_unit, instance.module)
        instance.delete()
class RoleAssignmentAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only view for role assignment audit logs.
    """
    queryset = RoleAssignmentAuditLog.objects.all().order_by('-timestamp')
    serializer_class = RoleAssignmentAuditLogSerializer
    permission_classes = [HasScopedRole]
    required_role = "audit"  # Only users with 'audit' ScopedRole can view audit logs


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """
    Change the authenticated user's password.
    
    Request body: {
        "current_password": "string",
        "new_password": "string"
    }
    """
    user = request.user
    current_password = request.data.get('current_password')
    new_password = request.data.get('new_password')

    # Validation
    if not current_password:
        return Response(
            {'current_password': ['Current password is required.']},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not new_password:
        return Response(
            {'new_password': ['New password is required.']},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Check if current password is correct
    if not user.check_password(current_password):
        return Response(
            {'current_password': ['Current password is incorrect.']},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    # Validate new password length
    if len(new_password) < 8:
        return Response(
            {'new_password': ['Password must be at least 8 characters long.']},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Prevent using the same password
    if user.check_password(new_password):
        return Response(
            {'new_password': ['New password cannot be the same as the current password.']},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Set the new password
    user.set_password(new_password)
    user.save()

    return Response(
        {'detail': 'Password changed successfully.'},
        status=status.HTTP_200_OK,
    )


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

    