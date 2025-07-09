# File: core/urls.py

from rest_framework.routers import DefaultRouter
from .views import ProjectViewSet, ModuleViewSet

router = DefaultRouter()
router.register(r'projects', ProjectViewSet)
router.register(r'modules', ModuleViewSet)

urlpatterns = router.urls