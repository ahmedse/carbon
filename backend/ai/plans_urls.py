"""URL routing for the Agentic Task Orchestration API (Sprint 23 W3-A).

Mounted at ``{api_prefix}/ai/plans/`` (see ``config/urls.py``), so each path
below is relative to ``/carbon-api/ai/plans/``:

    POST   /                        create (brief → pending_approval)
    GET    /                        list my plans
    GET    /{id}/                   plan detail + steps
    PATCH  /{id}/                   edit plan (replan + diff)
    PATCH  /{id}/steps/{step}/      edit a single plan step
    POST   /{id}/approve/           plan-level consent (RULE_21)
    POST   /{id}/decline/           decline a pending plan
    POST   /{id}/run/               SSE streamed run
    POST   /{id}/pause/             pause a running plan
    POST   /{id}/resume/            resume a paused plan (SSE)
    POST   /{id}/fork/              fork into a new reviewable plan
    POST   /{id}/steps/confirm/     confirm a paused consent step
    POST   /{id}/steps/decline/     decline a paused consent step
    POST   /{id}/stop/              cancel a run
    GET    /{id}/ledger/            audit ledger

Note: explicit ``as_view`` mappings instead of a router because the include
mount already carries the ``plans`` prefix — a router would double it.
"""

from django.urls import path

from ai.plans_api import PlanViewSet

urlpatterns = [
    path(
        "",
        PlanViewSet.as_view({"get": "list", "post": "create"}),
        name="ai-plan-list",
    ),
    # Template routes MUST precede the ``<str:pk>/`` detail route so the
    # literal ``templates`` segment wins over a plan id.
    path(
        "templates/",
        PlanViewSet.as_view({"get": "list_templates"}),
        name="ai-plan-template-list",
    ),
    path(
        "templates/<str:template_id>/instantiate/",
        PlanViewSet.as_view({"post": "instantiate_template"}),
        name="ai-plan-template-instantiate",
    ),
    path(
        "<str:pk>/",
        PlanViewSet.as_view({"get": "retrieve", "patch": "partial_update"}),
        name="ai-plan-detail",
    ),
    path(
        "<str:pk>/discover/",
        PlanViewSet.as_view({"post": "advance_discovery"}),
        name="ai-plan-discover",
    ),
    path(
        "<str:pk>/promote-template/",
        PlanViewSet.as_view({"post": "promote_template"}),
        name="ai-plan-promote-template",
    ),
    path(
        "<str:pk>/approve/",
        PlanViewSet.as_view({"post": "approve"}),
        name="ai-plan-approve",
    ),
    path(
        "<str:pk>/decline/",
        PlanViewSet.as_view({"post": "decline"}),
        name="ai-plan-decline",
    ),
    path(
        "<str:pk>/run/",
        PlanViewSet.as_view({"post": "run"}),
        name="ai-plan-run",
    ),
    path(
        "<str:pk>/steps/confirm/",
        PlanViewSet.as_view({"post": "confirm_step"}),
        name="ai-plan-step-confirm",
    ),
    path(
        "<str:pk>/steps/decline/",
        PlanViewSet.as_view({"post": "decline_step"}),
        name="ai-plan-step-decline",
    ),
    path(
        "<str:pk>/steps/<str:step_id>/",
        PlanViewSet.as_view({"patch": "edit_step"}),
        name="ai-plan-step-edit",
    ),
    path(
        "<str:pk>/pause/",
        PlanViewSet.as_view({"post": "pause"}),
        name="ai-plan-pause",
    ),
    path(
        "<str:pk>/resume/",
        PlanViewSet.as_view({"post": "resume"}),
        name="ai-plan-resume",
    ),
    path(
        "<str:pk>/fork/",
        PlanViewSet.as_view({"post": "fork"}),
        name="ai-plan-fork",
    ),
    path(
        "<str:pk>/stop/",
        PlanViewSet.as_view({"post": "stop"}),
        name="ai-plan-stop",
    ),
    path(
        "<str:pk>/ledger/",
        PlanViewSet.as_view({"get": "ledger"}),
        name="ai-plan-ledger",
    ),
]
