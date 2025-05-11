from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RoleViewSet, ContextViewSet, RoleAssignmentViewSet, MyTokenObtainPairView
from rest_framework_simplejwt.views import TokenRefreshView
from .views import my_roles


router = DefaultRouter()
router.register(r'roles', RoleViewSet)
router.register(r'contexts', ContextViewSet)
router.register(r'role-assignments', RoleAssignmentViewSet)

urlpatterns = [
    path('token/', MyTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('/', include(router.urls)),
    path('my-roles/', my_roles),
]