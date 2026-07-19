# importexport/urls.py
from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import ExportProjectViewSet, ImportJobViewSet, ExportJobViewSet

router = DefaultRouter()
router.register(r'export-projects', ExportProjectViewSet, basename='exportproject')
router.register(r'import', ImportJobViewSet, basename='importjob')
router.register(r'export', ExportJobViewSet, basename='exportjob')

urlpatterns = router.urls
