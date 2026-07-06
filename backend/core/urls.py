from rest_framework.routers import DefaultRouter
from .views import ModuleViewSet, FeedbackViewSet

router = DefaultRouter()
router.register(r'modules', ModuleViewSet)
router.register(r'feedback', FeedbackViewSet, basename='feedback')

urlpatterns = router.urls