# catalog/urls.py
from django.urls import path
from .views import (
    DataDomainViewSet, GlossaryTermViewSet, TagViewSet,
    AssetProfileViewSet, GovernanceEventViewSet, GovernanceComplianceView,
    GovernancePolicyViewSet, CatalogSearchView,
)
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'domains', DataDomainViewSet, basename='datadomain')
router.register(r'glossary', GlossaryTermViewSet, basename='glossaryterm')
router.register(r'tags', TagViewSet, basename='tag')
router.register(r'assets', AssetProfileViewSet, basename='assetprofile')
router.register(r'governance-events', GovernanceEventViewSet, basename='governanceevent')
router.register(r'governance-policies', GovernancePolicyViewSet, basename='governancepolicy')

urlpatterns = [
    path('search/', CatalogSearchView.as_view(), name='catalog-search'),
    path('governance/compliance/', GovernanceComplianceView.as_view(), name='governance-compliance'),
]
urlpatterns += router.urls
