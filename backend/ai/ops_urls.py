"""AI Pulse ops read API routes (mounted at ``/carbon-api/ai/pulse/``)."""

from django.urls import path

from ai.ops_api import PulseHealthView, PulseModulesView, PulseTaskStatusView

urlpatterns = [
    path("health/", PulseHealthView.as_view(), name="ai-pulse-health"),
    path("modules/", PulseModulesView.as_view(), name="ai-pulse-modules"),
    path("tasks/<str:task_id>/", PulseTaskStatusView.as_view(), name="ai-pulse-task-status"),
]
