"""AI proactive insights read API routes (mounted at ``/carbon-api/ai/insights/``)."""

from django.urls import path

from ai.insights_api import (
    InsightDispositionView,
    InsightsListView,
    InsightsStreamView,
)

urlpatterns = [
    path("stream/", InsightsStreamView.as_view(), name="ai-insights-stream"),
    path("", InsightsListView.as_view(), name="ai-insights-list"),
    path(
        "<str:pk>/disposition/",
        InsightDispositionView.as_view(),
        name="ai-insight-disposition",
    ),
]
