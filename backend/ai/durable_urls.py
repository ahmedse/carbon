"""URL routing for the durable execution API (Phase W3-E).

Mounted at ``{api_prefix}/ai/runs/`` (see ``config/urls.py``), so each path
below is relative to ``/carbon-api/ai/runs/``:

    GET  /{run_id}/timeline/   ordered event log for a run
    POST /{run_id}/resume/     crash-safe resume (reconcile + re-enter)
    POST /{run_id}/replay/     consent-gated replay staging (RULE_21)

Explicit ``as_view`` mappings (same convention as ``ai.plans_urls`` — the
include mount already carries the ``runs`` prefix; a router would double it).
"""

from django.urls import path

from ai.durable_api import RunViewSet

urlpatterns = [
    path(
        "<str:pk>/timeline/",
        RunViewSet.as_view({"get": "timeline"}),
        name="ai-run-timeline",
    ),
    path(
        "<str:pk>/resume/",
        RunViewSet.as_view({"post": "resume"}),
        name="ai-run-resume",
    ),
    path(
        "<str:pk>/replay/",
        RunViewSet.as_view({"post": "replay"}),
        name="ai-run-replay",
    ),
]
