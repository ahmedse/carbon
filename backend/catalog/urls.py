# catalog/urls.py
from django.urls import path
from .views import (
    DataDomainViewSet, GlossaryTermViewSet, TagViewSet,
    AssetProfileViewSet, GovernanceEventViewSet, GovernanceComplianceView,
    GovernancePolicyViewSet, CatalogSearchView,
)
from .dataset_views import (
    ApproveVersionView, ContractViolationsView, ContractView, DatasetViewSet,
    IngestERPView, IngestUploadView, RejectVersionView, VersionDetailView,
    VersionListCreateView,
)
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'domains', DataDomainViewSet, basename='datadomain')
router.register(r'glossary', GlossaryTermViewSet, basename='glossaryterm')
router.register(r'tags', TagViewSet, basename='tag')
router.register(r'assets', AssetProfileViewSet, basename='assetprofile')
router.register(r'governance-events', GovernanceEventViewSet, basename='governanceevent')
router.register(r'governance-policies', GovernancePolicyViewSet, basename='governancepolicy')
router.register(r'datasets', DatasetViewSet, basename='dataset')

urlpatterns = [
    path('search/', CatalogSearchView.as_view(), name='catalog-search'),
    path('governance/compliance/', GovernanceComplianceView.as_view(), name='governance-compliance'),
    # Nested dataset version routes — declared before router.urls so the uuid
    # converters never collide with the router's catch-all detail regex.
    path('datasets/<uuid:dataset_id>/versions/',
         VersionListCreateView.as_view(), name='dataset-versions'),
    path('datasets/<uuid:dataset_id>/versions/<uuid:version_id>/',
         VersionDetailView.as_view(), name='dataset-version-detail'),
    path('datasets/<uuid:dataset_id>/versions/<uuid:version_id>/approve/',
         ApproveVersionView.as_view(), name='dataset-version-approve'),
    path('datasets/<uuid:dataset_id>/versions/<uuid:version_id>/reject/',
         RejectVersionView.as_view(), name='dataset-version-reject'),
    # Contract
    path('datasets/<uuid:dataset_id>/contract/',
         ContractView.as_view(), name='dataset-contract'),
    path('datasets/<uuid:dataset_id>/contract/violations/',
         ContractViolationsView.as_view(), name='dataset-contract-violations'),
    # Ingest
    path('datasets/<uuid:dataset_id>/ingest/erp/',
         IngestERPView.as_view(), name='dataset-ingest-erp'),
    path('datasets/<uuid:dataset_id>/ingest/upload/',
         IngestUploadView.as_view(), name='dataset-ingest-upload'),
]
urlpatterns += router.urls
