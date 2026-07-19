# connections/urls.py
from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import DataSourceViewSet, ConsumingConnectionViewSet

router = DefaultRouter()
router.register(r'sources', DataSourceViewSet, basename='datasource')
router.register(r'consuming', ConsumingConnectionViewSet, basename='consumingconnection')

urlpatterns = router.urls
