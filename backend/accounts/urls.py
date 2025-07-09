# File: accounts/urls.py

from rest_framework.routers import DefaultRouter
from django.urls import path
from .views import (
    TenantViewSet, UserViewSet, GroupViewSet,
    ScopedRoleViewSet, RoleAssignmentAuditLogViewSet
)
from .views import my_roles

router = DefaultRouter()
router.register(r'tenants', TenantViewSet)
router.register(r'users', UserViewSet)
router.register(r'roles', GroupViewSet, basename='role')
router.register(r'scoped-roles', ScopedRoleViewSet, basename='scopedrole')
router.register(r'role-audit-logs', RoleAssignmentAuditLogViewSet, basename='roleassignmentauditlog')

urlpatterns = [
    path('my-roles/', my_roles, name='my-roles'),
]

urlpatterns += router.urls