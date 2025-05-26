# File: accounts/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    TenantViewSet, UserViewSet, ProjectViewSet, ModuleViewSet,
    RoleViewSet, ContextViewSet, RoleAssignmentViewSet,
    MyTokenObtainPairView, my_roles
)
from rest_framework_simplejwt.views import TokenRefreshView

router = DefaultRouter()
router.register(r'tenants', TenantViewSet)
router.register(r'users', UserViewSet)
router.register(r'projects', ProjectViewSet)
router.register(r'modules', ModuleViewSet)
router.register(r'roles', RoleViewSet)
router.register(r'contexts', ContextViewSet)
router.register(r'role-assignments', RoleAssignmentViewSet)

urlpatterns = [
    path('token/', MyTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('my-roles/', my_roles, name='my_roles'),
    path('', include(router.urls)),
]