from rest_framework.routers import DefaultRouter
from .views import (
    ReadingItemDefinitionViewSet,
    ReadingTemplateViewSet,
    ReadingTemplateFieldViewSet,
    ReadingEntryViewSet,
    EvidenceFileViewSet,
)

router = DefaultRouter()
router.register(r'item-definitions', ReadingItemDefinitionViewSet)
router.register(r'templates', ReadingTemplateViewSet)
router.register(r'template-fields', ReadingTemplateFieldViewSet)
router.register(r'entries', ReadingEntryViewSet)
router.register(r'evidence-files', EvidenceFileViewSet)

urlpatterns = router.urls