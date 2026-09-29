from rest_framework.routers import DefaultRouter

from .views import InboundBatchViewSet, InboundCartridgeViewSet, InboundTemplateViewSet

router = DefaultRouter()
router.register(r'batches', InboundBatchViewSet, basename='inbound-batch')
router.register(r'cartridges', InboundCartridgeViewSet, basename='inbound-cartridge')
router.register(r'templates', InboundTemplateViewSet, basename='inbound-template')

urlpatterns = router.urls
