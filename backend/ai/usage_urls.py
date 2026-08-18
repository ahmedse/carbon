"""AI usage + quota routes (mounted at ``/carbon-api/ai/usage/``)."""

from django.urls import path

from ai.usage_views import UsageByConversationView, UsageSummaryView

urlpatterns = [
    path("summary/", UsageSummaryView.as_view(), name="ai-usage-summary"),
    path(
        "by-conversation/",
        UsageByConversationView.as_view(),
        name="ai-usage-by-conversation",
    ),
]
