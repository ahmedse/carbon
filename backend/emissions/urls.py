# File: emissions/urls.py
# URL patterns for the Emissions API

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    ReportingPeriodViewSet,
    EmissionFactorViewSet,
    GWPViewSet,
    CalculationViewSet,
    CalculationSummaryAPIView,
    CalculationRuleViewSet,
    ReportConfigViewSet,
    DashboardAPIView,
    YearlyComparisonAPIView,
    ReportAPIView,
    CalculateAPIView,
    BatchCalculateAPIView,
    OwnerDashboardAPIView,
    OwnerSummaryAPIView,
    OwnerAssetsAPIView,
    OwnerActivityAPIView,
    MyDataAPIView,
    ConsoleAPIView,
    VerificationRecordViewSet,
    CalculationAuditViewSet,
    SBTiTargetViewSet,
    ExportAuditViewSet,
    OrganizationalBoundaryViewSet,
    BaseYearViewSet,
    RecalculationTriggerViewSet,
    InventorySourceViewSet,
    InventorySourceStatusViewSet,
    CoverageGoalViewSet,
    CoverageActionViewSet,
    InventoryCoverageAPIView,
    ChairmanAPIView,
)

app_name = 'emissions'

# Create router for ViewSets
router = DefaultRouter()
router.register(r'periods', ReportingPeriodViewSet, basename='reporting-period')
router.register(r'factors', EmissionFactorViewSet, basename='emission-factor')
router.register(r'gwp', GWPViewSet, basename='gwp')
router.register(r'calculations', CalculationViewSet, basename='calculation')
router.register(r'rules', CalculationRuleViewSet, basename='calculation-rule')
router.register(r'report-configs', ReportConfigViewSet, basename='report-config')

verification_router = DefaultRouter()
verification_router.register(r'verifications', VerificationRecordViewSet, basename='verification')

audit_router = DefaultRouter()
audit_router.register(r'calculation-audits', CalculationAuditViewSet, basename='calculation-audit')

targets_router = DefaultRouter()
targets_router.register(r'targets', SBTiTargetViewSet, basename='sbti-target')

export_audit_router = DefaultRouter()
export_audit_router.register(r'export-audits', ExportAuditViewSet, basename='export-audit')

# GHG Protocol Phase 2 routers
boundary_router = DefaultRouter()
boundary_router.register(r'boundaries', OrganizationalBoundaryViewSet, basename='organizational-boundary')

base_year_router = DefaultRouter()
base_year_router.register(r'base-years', BaseYearViewSet, basename='base-year')

recalc_router = DefaultRouter()
recalc_router.register(r'recalculation-triggers', RecalculationTriggerViewSet, basename='recalculation-trigger')

# Inventory Coverage routers (ADR-0020)
inventory_source_router = DefaultRouter()
inventory_source_router.register(r'inventory-sources', InventorySourceViewSet, basename='inventory-source')

inventory_source_status_router = DefaultRouter()
inventory_source_status_router.register(
    r'inventory-source-statuses', InventorySourceStatusViewSet, basename='inventory-source-status'
)

coverage_goal_router = DefaultRouter()
coverage_goal_router.register(r'coverage-goals', CoverageGoalViewSet, basename='coverage-goal')

coverage_action_router = DefaultRouter()
coverage_action_router.register(r'coverage-actions', CoverageActionViewSet, basename='coverage-action')

urlpatterns = [
    # Calculation summary — MUST come before router include to avoid path collision
    path('calculations/summary/', CalculationSummaryAPIView.as_view(), name='calculation-summary'),

    # ViewSet routes
    path('', include(router.urls)),
    
    # Verification routes
    path('', include(verification_router.urls)),
    
    # Audit trail routes
    path('', include(audit_router.urls)),
    
    # SBTi target routes
    path('', include(targets_router.urls)),
    
    # Export audit routes (E3-1)
    path('', include(export_audit_router.urls)),

    # GHG Protocol Phase 2 routes
    path('', include(boundary_router.urls)),
    path('', include(base_year_router.urls)),
    path('', include(recalc_router.urls)),

    # Inventory Coverage routes (ADR-0020)
    path('', include(inventory_source_router.urls)),
    path('', include(inventory_source_status_router.urls)),
    path('', include(coverage_goal_router.urls)),
    path('', include(coverage_action_router.urls)),
    path('coverage/', InventoryCoverageAPIView.as_view(), name='inventory-coverage'),
    
    # Dashboard API
    path('dashboard/', DashboardAPIView.as_view(), name='dashboard'),

    # Chairman overview API (Tier 1 single-call payload)
    path('chairman/', ChairmanAPIView.as_view(), name='chairman'),
    
    # Owner APIs (org-unit scoped)
    path('owner-dashboard/', OwnerDashboardAPIView.as_view(), name='owner-dashboard'),
    path('owner/summary/', OwnerSummaryAPIView.as_view(), name='owner-summary'),
    path('owner/assets/', OwnerAssetsAPIView.as_view(), name='owner-assets'),
    path('owner/activity/', OwnerActivityAPIView.as_view(), name='owner-activity'),

    # My Data API (consolidated owner workspace)
    path('my-data/', MyDataAPIView.as_view(), name='my-data'),
    
    # Yearly Comparison API
    path('yearly-comparison/', YearlyComparisonAPIView.as_view(), name='yearly-comparison'),
    
    # Report API
    path('report/', ReportAPIView.as_view(), name='report'),
    
    # Calculate API (trigger calculations)
    path('calculate/', CalculateAPIView.as_view(), name='calculate'),
    path('batch-calculate/', BatchCalculateAPIView.as_view(), name='batch-calculate'),
    
    # Console API (aggregated landing page data)
    path('console/', ConsoleAPIView.as_view(), name='console'),
]
