# File: core/urls.py

from rest_framework.routers import DefaultRouter
from .views import ProjectViewSet, ModuleViewSet
from .views import FeedbackViewSet

router = DefaultRouter()
router.register(r'projects', ProjectViewSet)
router.register(r'modules', ModuleViewSet)
router.register(r'feedback', FeedbackViewSet, basename='feedback')

urlpatterns = router.urls