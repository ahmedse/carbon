# File: emissions/urls.py
# URL patterns for the Emissions API

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    ReportingPeriodViewSet,
    EmissionFactorViewSet,
    GWPViewSet,
    CalculationViewSet,
    CalculationRuleViewSet,
    ReportConfigViewSet,
    DashboardAPIView,
    YearlyComparisonAPIView,
    ReportAPIView,
    CalculateAPIView,
    OwnerDashboardAPIView,
    OwnerSummaryAPIView,
    OwnerAssetsAPIView,
    OwnerActivityAPIView,
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

urlpatterns = [
    # ViewSet routes
    path('', include(router.urls)),
    
    # Dashboard API
    path('dashboard/', DashboardAPIView.as_view(), name='dashboard'),
    
    # Owner dashboard (org-unit scoped)
    path('owner-dashboard/', OwnerDashboardAPIView.as_view(), name='owner-dashboard'),
    path('owner/summary/', OwnerSummaryAPIView.as_view(), name='owner-summary'),
    path('owner/assets/', OwnerAssetsAPIView.as_view(), name='owner-assets'),
    path('owner/activity/', OwnerActivityAPIView.as_view(), name='owner-activity'),
    
    # Yearly Comparison API
    path('yearly-comparison/', YearlyComparisonAPIView.as_view(), name='yearly-comparison'),
    
    # Report API
    path('report/', ReportAPIView.as_view(), name='report'),
    
    # Calculate API (trigger calculations)
    path('calculate/', CalculateAPIView.as_view(), name='calculate'),
]
