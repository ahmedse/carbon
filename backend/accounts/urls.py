# File: accounts/urls.py

from rest_framework.routers import DefaultRouter
from django.urls import path
from .views import (
    UserViewSet, GroupViewSet,
    ScopedRoleViewSet, RoleAssignmentAuditLogViewSet,
    LogoutView, my_roles, me_context,
)

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'roles', GroupViewSet, basename='role')
router.register(r'scoped-roles', ScopedRoleViewSet, basename='scopedrole')
router.register(r'role-audit-logs', RoleAssignmentAuditLogViewSet, basename='roleassignmentauditlog')

urlpatterns = [
    path('my-roles/', my_roles, name='my-roles'),
    path('me/context/', me_context, name='me-context'),
    path('logout/', LogoutView.as_view(), name='logout'),
]

urlpatterns += router.urls