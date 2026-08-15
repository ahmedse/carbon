"""AI Pulse ops read API routes (mounted at ``/carbon-api/ai/pulse/``)."""

from django.urls import path

from ai.activation_api import PulseSettingsView, PulseUsageView
from ai.graph_api import GraphDataView
from ai.learning_api import LearningRunView, LearningStatusView
from ai.observability_api import (
    PulseArchetypesView,
    PulseDataView,
    PulseInventoryView,
)
from ai.ops_api import PulseHealthView, PulseModulesView, PulseTaskStatusView
from ai.sweeps_api import SweepsStatusView

urlpatterns = [
    path("health/", PulseHealthView.as_view(), name="ai-pulse-health"),
    path("modules/", PulseModulesView.as_view(), name="ai-pulse-modules"),
    path("tasks/<str:task_id>/", PulseTaskStatusView.as_view(), name="ai-pulse-task-status"),
    path("inventory/", PulseInventoryView.as_view(), name="ai-pulse-inventory"),
    path("data/<str:key>/", PulseDataView.as_view(), name="ai-pulse-data"),
    path("archetypes/", PulseArchetypesView.as_view(), name="ai-pulse-archetypes"),
    path("graph/", GraphDataView.as_view(), name="ai-pulse-graph"),
    path("usage/", PulseUsageView.as_view(), name="ai-pulse-usage"),
    path("settings/", PulseSettingsView.as_view(), name="ai-pulse-settings"),
    path("sweeps/", SweepsStatusView.as_view(), name="ai-pulse-sweeps"),
    path("learning-status/", LearningStatusView.as_view(), name="ai-pulse-learning-status"),
    path("learning-status/run/", LearningRunView.as_view(), name="ai-pulse-learning-status-run"),
]
