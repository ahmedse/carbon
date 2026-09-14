from rest_framework.routers import DefaultRouter
from .views import (
    ModuleViewSet, FeedbackViewSet, NotificationViewSet, RequestAuditLogViewSet,
)

router = DefaultRouter()
router.register(r'modules', ModuleViewSet)
router.register(r'feedback', FeedbackViewSet, basename='feedback')
router.register(r'notifications', NotificationViewSet, basename='notification')
router.register(r'audit-logs', RequestAuditLogViewSet, basename='requestauditlog')

urlpatterns = router.urls