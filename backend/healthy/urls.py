"""Healthy Foods Factory API routes (DESIGN-PLATFORM.md §8.5)."""
from django.urls import path

from .views import (
    DashboardARQueueView, DashboardSlowMoversView, DashboardSummaryView,
    LoadoutActualsView, LoadoutListView, LoadoutRepView, LoadoutWeekView,
    RepHealthDetailView, RepHealthListView, SnapshotListCreateView,
)

urlpatterns = [
    path('snapshots/', SnapshotListCreateView.as_view(), name='healthy-snapshots'),
    path('loadout/', LoadoutListView.as_view(), name='healthy-loadout-list'),
    path('loadout/<str:week>/', LoadoutWeekView.as_view(), name='healthy-loadout-week'),
    path('loadout/<str:week>/<str:rep>/', LoadoutRepView.as_view(), name='healthy-loadout-rep'),
    path('loadout/<str:week>/<str:rep>/actuals/', LoadoutActualsView.as_view(),
         name='healthy-loadout-actuals'),
    path('rep-health/', RepHealthListView.as_view(), name='healthy-rep-health-list'),
    path('rep-health/<str:week>/<str:rep>/', RepHealthDetailView.as_view(),
         name='healthy-rep-health-detail'),
    path('dashboards/summary/', DashboardSummaryView.as_view(),
         name='healthy-dashboard-summary'),
    path('dashboards/ar-queue/', DashboardARQueueView.as_view(),
         name='healthy-dashboard-ar-queue'),
    path('dashboards/slow-movers/', DashboardSlowMoversView.as_view(),
         name='healthy-dashboard-slow-movers'),
]
