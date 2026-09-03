"""Phase H3-B — anomaly watch routes (mounted at ``/carbon-api/ai/watches/``)."""

from django.urls import path

from ai.watches_api import WatchesListView, WatchDetailView

urlpatterns = [
    path("", WatchesListView.as_view(), name="ai-watches-list"),
    path("<str:pk>/", WatchDetailView.as_view(), name="ai-watch-detail"),
]
