# File: accounts/urls.py

from rest_framework.routers import DefaultRouter
from django.urls import path
from .views import (
    UserViewSet, GroupViewSet,
    ScopedRoleViewSet, RoleAssignmentAuditLogViewSet,
    LogoutView, my_roles, me_context, change_password, role_registry,
    platform_apps, capability_matrix,
)
from .pulse_auth import pulse_auth_view, pulse_provision_view

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'roles', GroupViewSet, basename='role')
router.register(r'groups', GroupViewSet, basename='group')
router.register(r'scoped-roles', ScopedRoleViewSet, basename='scopedrole')
router.register(r'role-audit-logs', RoleAssignmentAuditLogViewSet, basename='roleassignmentauditlog')

urlpatterns = [
    path('my-roles/', my_roles, name='my-roles'),
    path('me/context/', me_context, name='me-context'),
    path('role-registry/', role_registry, name='role-registry'),
    path('change-password/', change_password, name='change-password'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('platform-apps/', platform_apps, name='platform-apps'),
    path('platform-apps/<str:app_id>/', platform_apps, name='platform-apps-detail'),
    # Pulse AI Copilot integration endpoints
    path('pulse-auth/', pulse_auth_view, name='pulse-auth'),
    path('pulse-provision/', pulse_provision_view, name='pulse-provision'),
    # URL aliases for frontend discoverability (P11 hardening)
    path('audit-log/', RoleAssignmentAuditLogViewSet.as_view({'get': 'list'}), name='audit-log-list'),
    path('audit-log/<int:pk>/', RoleAssignmentAuditLogViewSet.as_view({'get': 'retrieve'}), name='audit-log-detail'),
    path('access-control/', ScopedRoleViewSet.as_view({'get': 'list', 'post': 'create'}), name='access-control-list'),
    path('access-control/<int:pk>/', ScopedRoleViewSet.as_view({'get': 'retrieve', 'patch': 'partial_update', 'delete': 'destroy'}), name='access-control-detail'),
    path('capability-matrix/', capability_matrix, name='capability-matrix'),
]

urlpatterns += router.urls
