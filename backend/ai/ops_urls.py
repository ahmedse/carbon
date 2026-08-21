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
from ai.ops_api import (
    AccessAssistAnomaliesView,
    AccessAssistCapabilitiesView,
    AccessAssistProposeGrantView,
    AccessAssistUsersWithCapabilityView,
    DomainAppManifestDetailView,
    DomainAppManifestListView,
    ImpactFieldView,
    ImpactTableView,
    LineageFieldView,
    LineageTableView,
    PulseHealthView,
    PulseModulesView,
    PulseTaskStatusView,
)
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
    # Domain app manifest API — available to all authenticated users
    path("apps/", DomainAppManifestListView.as_view(), name="ai-domain-apps"),
    path("apps/<str:app_identifier>/", DomainAppManifestDetailView.as_view(), name="ai-domain-app-detail"),
    # Access & CBAC assistance (Phase 24-H) — capability-gated, read-only
    path("access-assist/users/<int:user_id>/capabilities/", AccessAssistCapabilitiesView.as_view(), name="ai-access-assist-capabilities"),
    path("access-assist/capability/<str:capability_key>/users/", AccessAssistUsersWithCapabilityView.as_view(), name="ai-access-assist-capability-users"),
    path("access-assist/propose-grant/", AccessAssistProposeGrantView.as_view(), name="ai-access-assist-propose-grant"),
    path("access-assist/anomalies/", AccessAssistAnomaliesView.as_view(), name="ai-access-assist-anomalies"),
    # Lineage & impact (Phase 24-I) — capability-gated, read-only
    path("lineage/table/<int:table_id>/", LineageTableView.as_view(), name="ai-lineage-table"),
    path("lineage/field/<int:field_id>/", LineageFieldView.as_view(), name="ai-lineage-field"),
    path("impact/table/<int:table_id>/", ImpactTableView.as_view(), name="ai-impact-table"),
    path("impact/field/<int:field_id>/", ImpactFieldView.as_view(), name="ai-impact-field"),
]
