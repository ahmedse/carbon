# File: accounts/views.py
# DRF views for users, scoped roles, and audit logs.

from rest_framework import status, viewsets
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from django.contrib.auth.models import Group
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from .models import User, ScopedRole, RoleAssignmentAuditLog, PlatformAppConfig
from .serializers import (
    UserSerializer, GroupSerializer,
    ScopedRoleSerializer, ScopedRoleCreateSerializer,
    RoleAssignmentAuditLogSerializer, PlatformAppConfigSerializer
)
from .permissions import HasScopedRole, CanManageScopedRoles
from .rbac_utils import user_is_global_admin, get_steward_org_unit_ids
from .services import RoleResolutionService, AppManifestService
from .constants import PROTECTED_GROUPS
from rest_framework.exceptions import PermissionDenied
from django.db.models import Q
from rest_framework.decorators import action, api_view, permission_classes
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
        user_is_global_admin, get_visible_module_ids,
        get_visible_org_units, VISIBILITY_ROLES
    )
    from core.models import Module

    user = request.user

    scoped_roles = user.scoped_roles.filter(is_active=True).select_related('group', 'org_unit')
    role_names = [r.group.name for r in scoped_roles]
    is_global = user_is_global_admin(user)

    perspectives = []
    scoped_roles_data = []
    for role in scoped_roles:
        group_name = role.group.name
        perspective = RoleResolutionService.perspective_from_group_name(group_name)
        if perspective and perspective not in perspectives:
            perspectives.append(perspective)

        scoped_roles_data.append({
            'role': group_name,
            'org_unit': role.org_unit.name if role.org_unit else 'Global',
            'module': role.module.name if role.module else None,
            'is_active': role.is_active,
        })

    # Superusers and global admins should always receive the platform admin perspective.
    if is_global and 'admin' not in perspectives:
        perspectives.append('admin')

    perspective_order = {'admin': 0, 'carbon-admin': 1, 'catalog-admin': 2, 'data-owner': 3, 'analyst': 4, 'viewer': 5, 'steward': 6}
    perspectives = sorted(set(perspectives), key=lambda value: (perspective_order.get(value, 99), value))

    org_units = [org_unit.id for org_unit in get_visible_org_units(user)]

    visible_module_ids = get_visible_module_ids(user)
    if visible_module_ids is None:
        module_count = Module.objects.count()
        user_modules = list(Module.objects.values('id', 'name'))
    else:
        module_count = len(visible_module_ids)
        user_modules = list(Module.objects.filter(id__in=visible_module_ids).values('id', 'name'))

    # Capability-based access control — single source of truth for frontend
    from accounts.capabilities import get_capabilities_for_frontend
    capabilities = get_capabilities_for_frontend(user)

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
        'capabilities': capabilities,  # NEW: capability-based access control
        'org_units': org_units,
        'modules': user_modules,
        'scoped_roles': scoped_roles_data,
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

class GroupViewSet(viewsets.ModelViewSet):
    """
    CRUD for Django Groups (roles).

    Platform admins can create, update, list, and delete role definitions.
    Protected groups such as admin and carbon_data_owners_group cannot be deleted.
    """
    queryset = Group.objects.all().order_by('name')
    serializer_class = GroupSerializer
    permission_classes = [HasScopedRole]
    required_role = "admin"

    def destroy(self, request, *args, **kwargs):
        group = self.get_object()
        if group.name in PROTECTED_GROUPS:
            return Response(
                {'error': f'Cannot delete protected group: {group.name}'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['get'])
    def members(self, request, pk=None):
        """List users with global assignments to this role."""
        group = self.get_object()
        scoped_roles = ScopedRole.objects.filter(
            group=group,
            org_unit__isnull=True,
            module__isnull=True,
            is_active=True,
        ).select_related('user')
        members = [
            {
                'id': role.user.id,
                'user_id': role.user.id,
                'username': role.user.username,
                'email': role.user.email or '',
                'assigned_at': role.created_at,
                'scoped_role_id': role.id,
                'group_id': group.id,
                'org_unit_id': None,
                'module_id': None,
            }
            for role in scoped_roles
        ]
        return Response(members)

    @action(detail=True, methods=['get'])
    def scoped_assignments(self, request, pk=None):
        """List scoped role assignments for this role."""
        group = self.get_object()
        scoped_roles = ScopedRole.objects.filter(group=group).select_related(
            'user', 'org_unit', 'module'
        )
        assignments = [
            {
                'id': role.id,
                'user_id': role.user.id,
                'group_id': group.id,
                'user': str(role.user),
                'org_unit': str(role.org_unit) if role.org_unit else None,
                'module': str(role.module) if role.module else None,
                'org_unit_id': role.org_unit_id,
                'module_id': role.module_id,
                'is_active': role.is_active,
                'created_at': role.created_at,
            }
            for role in scoped_roles
        ]
        return Response(assignments)

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
        if getattr(self, 'swagger_fake_view', False):
            return ScopedRole.objects.none()
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


@swagger_auto_schema(
    method='get',
    operation_description='Return app role definitions from the platform manifest registry.',
    responses={200: openapi.Response('OK', schema=openapi.Schema(type=openapi.TYPE_OBJECT))},
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def role_registry(request):
    """
    Return app roles declared in the platform manifest registry.
    """
    if not user_is_global_admin(request.user) and not request.user.is_superuser:
        return Response({'detail': 'You do not have permission to access this endpoint.'}, status=403)

    role_data = []
    for app_manifest in AppManifestService.load_manifests():
        role_data.append({
            'id': app_manifest.get('id'),
            'name': app_manifest.get('name', app_manifest.get('id')),
            'version': app_manifest.get('version', '1.0.0'),
            'roles': app_manifest.get('roles', []),
        })

    return Response({'apps': role_data})


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


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def platform_apps(request, app_id=None):
    """
    GET  /accounts/platform-apps/         — list all registered apps with enabled status
    PUT  /accounts/platform-apps/{app_id}/ — toggle is_enabled (admin only)
    """
    from .rbac_utils import user_is_global_admin

    if request.method == 'PUT':
        if not user_is_global_admin(request.user):
            raise PermissionDenied('Only platform admins can manage app configuration.')
        try:
            config = PlatformAppConfig.objects.get(app_id=app_id)
        except PlatformAppConfig.DoesNotExist:
            return Response({'error': f'App {app_id} not found'}, status=404)
        serializer = PlatformAppConfigSerializer(config, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save(updated_by=request.user)
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    # GET: return all apps merged with DB config (auto-creates missing records)
    manifests = AppManifestService.load_manifests()
    configs = {c.app_id: c for c in PlatformAppConfig.objects.all()}

    result = []
    for manifest in manifests:
        app_id = manifest['id']
        config = configs.get(app_id)
        if not config:
            config = PlatformAppConfig.objects.create(app_id=app_id, is_enabled=True)
        result.append({
            'app_id': app_id,
            'name': manifest.get('name', app_id),
            'version': manifest.get('version', '1.0.0'),
            'is_enabled': config.is_enabled,
            'display_order': config.display_order,
            'roles': manifest.get('roles', []),
            'updated_at': config.updated_at,
        })

    return Response(result)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def capability_matrix(request):
    """
    GET /accounts/capability-matrix/

    Returns the full capability inheritance matrix for admin UI.
    Accessible to any authenticated admin user.

    Response:
    {
        matrix: [{group, is_wildcard, capabilities: [{key, label, domain, category, inherited}]}],
        inheritance: [{from, to}],
        domains: [{domain, label, capabilities: [{key, label, category}]}]
    }
    """
    from accounts.capabilities import get_capability_matrix, IMPLIES, ALL_CAPABILITIES
    from accounts.rbac_utils import user_is_global_admin

    # Only admins can see the matrix
    if not user_is_global_admin(request.user):
        from accounts.capabilities import has_capability
        if not has_capability(request.user, 'platform:manage_access'):
            raise PermissionDenied('Only platform admins can view the capability matrix.')

    matrix = get_capability_matrix()

    # Inheritance edges for visualization
    inheritance = []
    for from_cap, to_set in sorted(IMPLIES.items()):
        for to_cap in sorted(to_set):
            inheritance.append({"from": from_cap, "to": to_cap})

    # Domains for grouping
    domains_dict = {}
    for key, c in sorted(ALL_CAPABILITIES.items()):
        if c.domain not in domains_dict:
            domains_dict[c.domain] = {"domain": c.domain, "label": c.domain.title(), "capabilities": []}
        domains_dict[c.domain]["capabilities"].append({
            "key": key, "label": c.label, "category": c.category, "action": c.action,
        })

    return Response({
        "matrix": matrix,
        "inheritance": inheritance,
        "domains": sorted(domains_dict.values(), key=lambda d: d["domain"]),
    })

    