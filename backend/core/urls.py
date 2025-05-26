# File: core/urls.py

from rest_framework.routers import DefaultRouter
from .views import ProjectViewSet, CycleViewSet, ModuleViewSet

router = DefaultRouter()
router.register(r'projects', ProjectViewSet)
router.register(r'cycles', CycleViewSet)
router.register(r'modules', ModuleViewSet)

urlpatterns = router.urls