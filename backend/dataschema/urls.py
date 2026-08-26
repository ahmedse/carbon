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
from .policy_views import FieldAccessPolicyView, FieldAccessPolicyDetailView

router = DefaultRouter()
router.register(r'tables', DataTableViewSet, basename='dataschema-table')
router.register(r'fields', DataFieldViewSet, basename='dataschema-field')
router.register(r'rows', DataRowViewSet, basename='dataschema-row')
router.register(r'schema-logs', SchemaChangeLogViewSet, basename='dataschema-schemalog')
router.register(r'relations', TableRelationViewSet, basename='dataschema-relation')

urlpatterns = [
    path('fields/<int:field_id>/policies/', FieldAccessPolicyView.as_view(), name='field-policies'),
    path('fields/<int:field_id>/policies/<int:pk>/', FieldAccessPolicyDetailView.as_view(), name='field-policy-detail'),
    path('', include(router.urls)),
]