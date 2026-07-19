# File: dataschema/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DataTableViewSet,
    DataFieldViewSet,
    DataRowViewSet,
    SchemaChangeLogViewSet,
    TableRelationViewSet,
)

router = DefaultRouter()
router.register(r'tables', DataTableViewSet, basename='dataschema-table')
router.register(r'fields', DataFieldViewSet, basename='dataschema-field')
router.register(r'rows', DataRowViewSet, basename='dataschema-row')
router.register(r'schema-logs', SchemaChangeLogViewSet, basename='dataschema-schemalog')
router.register(r'relations', TableRelationViewSet, basename='dataschema-relation')

urlpatterns = [
    path('', include(router.urls)),
]