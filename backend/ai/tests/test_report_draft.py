"""
Phase 10-A — Report Draft typed route + provider wiring.

Proves the intelligence-layer typed handler (``_send_report_draft_message``)
bridges the frontend entry-point payload (``{module_id, period_id}``) to the
engine's ``{report_type, period_start, period_end}`` shape and serializes the
frozen metadata contract the 10-B frontend depends on:

    {"type": "report", "title", "summary", "report_type",
     "period_start", "period_end", "generated_at",
     "sections": [{"title", "content", "sql", "data", "caveat"}, ...]}

The engine (``_run_report_draft``), protocol dataclasses, and provider
(``pulse.draft_report``) are already built and tested — this file covers only
the intelligence-layer handler, never re-implementing them.
"""

from __future__ import annotations

import types
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings

from accounts.models import User
from ai.engine.core.config import get_settings
from ai.intelligence import CarbonIntelligence
from ai.models import AIConversation
from ai.store import reset_store
from backend.ai.protocol import ReportDraftRequest, ReportDraftResponse, ReportSection, Scope
from core.models import Module
from emissions.models import ReportingPeriod
from mdm.models import OrgUnit


# ── Fixtures (mirror test_investigate.py) ────────────────────────────────


def _fake_completion(content: str) -> types.SimpleNamespace:
    """Return an OpenAI-shaped completion whose content is *content*."""

    async def _create(**kw):
        return types.SimpleNamespace(
            choices=[
                types.SimpleNamespace(
                    message=types.SimpleNamespace(content=content, tool_calls=None),
                    finish_reason="stop",
                )
            ],
            usage=types.SimpleNamespace(
                prompt_tokens=10, completion_tokens=4, total_tokens=14
            ),
        )

    return types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=_create))
    )


@pytest.fixture
def django_store():
    """Use the Django backend so durable writes land in the test DB."""
    with override_settings(AI_STORE_BACKEND="django"):
        reset_store()
        yield
        reset_store()


@pytest.fixture
def cfg():
    """Clear the settings cache around each test."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="report-worker", password="secret123")


@pytest.fixture
def module_graph(db, user):
    org = OrgUnit.objects.create(name="Report Org", slug="report-org")
    module = Module.objects.create(name="Report Module", scope=1, org_unit=org)
    return {"org": org, "module": module}


def _scope_for(user, module_id: int, *, app_identifier: str | None = None) -> Scope:
    return Scope(
        user_identifier=str(user.pk),
        org_unit_ids=["1"],
        module_ids=[str(module_id)],
        app_identifier=app_identifier,
    )


# ── Helpers ───────────────────────────────────────────────────────────────


def _draft_response(request: ReportDraftRequest) -> ReportDraftResponse:
    """Canned provider response that echoes the request's report params."""
    return ReportDraftResponse(
        status="completed",
        title="GHG Summary Report",
        summary="Figures below should be verified against source systems.",
        report_type=request.report_type,
        period_start=request.period_start,
        period_end=request.period_end,
        generated_at="2026-08-16T12:00:00+00:00",
        sections=[
            ReportSection(title="Summary", content="**Overview** — deterministic."),
            ReportSection(
                title="Data Volume (Live)",
                content="Live metrics.",
                data=[{"metric": "rows", "value": 42}],
                caveat="Live figures may drift.",
            ),
        ],
    )


def _conversation(user, module_graph, *, task_payload: dict) -> AIConversation:
    return AIConversation.objects.create(
        user=user,
        title="report draft",
        conversation_type="report_draft",
        task_payload_json=task_payload,
        scope_json={},
    )


def _run_handler(user, module_graph, conversation, *, response=None):
    """Patch build_scope, mock the provider, and drive send_message."""
    provider = MagicMock()
    provider.provider_name = "dummy"
    provider.draft_report = MagicMock(side_effect=response or _draft_response)

    ci = CarbonIntelligence()
    ci._provider = provider

    with patch(
        "ai.intelligence.build_scope",
        return_value=_scope_for(user, module_graph["module"].id),
    ):
        result = ci.send_message(user, str(conversation.id), "draft the report")

    return provider, result


# ── Routing: report_draft conversation → _send_report_draft_message ──────


@pytest.mark.django_db
def test_report_draft_conversation_routes_to_handler(user, module_graph, django_store, cfg):
    """A report_draft conversation runs the typed handler, not the staged placeholder."""
    conversation = _conversation(
        user,
        module_graph,
        task_payload={
            "module_id": module_graph["module"].id,
            "module_name": module_graph["module"].name,
            "report_type": "ghg_summary",
            "period_start": "2026-01-01",
            "period_end": "2026-12-31",
        },
    )

    provider, result = _run_handler(user, module_graph, conversation)

    # The provider was actually invoked (typed route is live).
    provider.draft_report.assert_called_once()

    meta = result["assistant_message"]["metadata_json"]
    assert meta["type"] == "report", result
    assert meta["title"] == "GHG Summary Report", result
    assert result["conversation"]["status"] == "needs_input", result


# ── Parameter resolution ──────────────────────────────────────────────────


@pytest.mark.django_db
def test_report_draft_period_id_resolution(user, module_graph, django_store, cfg):
    """A period_id resolves to start/end dates and a period-type→report_type map."""
    period = ReportingPeriod.objects.create(
        name="FY 2026",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        period_type="annual",
    )
    conversation = _conversation(
        user,
        module_graph,
        task_payload={
            "module_id": module_graph["module"].id,
            "period_id": period.id,
        },
    )

    provider, result = _run_handler(user, module_graph, conversation)

    request = provider.draft_report.call_args.args[0]
    assert isinstance(request, ReportDraftRequest)
    assert request.report_type == "annual_summary"
    assert request.period_start == "2026-01-01"
    assert request.period_end == "2026-12-31"

    meta = result["assistant_message"]["metadata_json"]
    assert meta["report_type"] == "annual_summary", result
    assert meta["period_start"] == "2026-01-01", result
    assert meta["period_end"] == "2026-12-31", result


@pytest.mark.django_db
def test_report_draft_direct_params(user, module_graph, django_store, cfg):
    """Without period_id, report_type/period_start/period_end pass through."""
    conversation = _conversation(
        user,
        module_graph,
        task_payload={
            "module_id": module_graph["module"].id,
            "report_type": "custom_summary",
            "period_start": "2026-03-01",
            "period_end": "2026-06-30",
        },
    )

    provider, result = _run_handler(user, module_graph, conversation)

    request = provider.draft_report.call_args.args[0]
    assert request.report_type == "custom_summary"
    assert request.period_start == "2026-03-01"
    assert request.period_end == "2026-06-30"

    meta = result["assistant_message"]["metadata_json"]
    assert meta["report_type"] == "custom_summary", result


# ── Frozen metadata contract ──────────────────────────────────────────────


@pytest.mark.django_db
def test_report_draft_metadata_shape(user, module_graph, django_store, cfg):
    """Serialized metadata matches the frozen 10-B contract (title/sections/needs_input)."""
    conversation = _conversation(
        user,
        module_graph,
        task_payload={
            "module_id": module_graph["module"].id,
            "report_type": "ghg_summary",
            "period_start": "2026-01-01",
            "period_end": "2026-12-31",
        },
    )

    _, result = _run_handler(user, module_graph, conversation)

    meta = result["assistant_message"]["metadata_json"]
    assert meta["type"] == "report", result
    assert meta["title"] == "GHG Summary Report", result
    assert meta["summary"], result
    assert meta["generated_at"], result

    sections = meta["sections"]
    assert isinstance(sections, list) and len(sections) == 2, result
    assert sections[0]["title"] == "Summary", result
    assert sections[0]["content"], result
    assert sections[1]["title"] == "Data Volume (Live)", result
    assert sections[1]["data"] == [{"metric": "rows", "value": 42}], result
    assert sections[1]["caveat"] == "Live figures may drift.", result
    assert result["conversation"]["status"] == "needs_input", result


# ── Deterministic fallback (engine-level) ─────────────────────────────────


@pytest.mark.django_db
def test_report_draft_deterministic_fallback(django_store, cfg):
    """LLM outage → still 'completed' with a deterministic, non-empty summary."""
    from ai.engine_runtime import dispatch_task

    payload = {
        "report_type": "ghg_summary",
        "period_start": "2026-01-01",
        "period_end": "2026-12-31",
    }

    with patch("ai.engine.llm.router.route_chat", side_effect=RuntimeError("no key")):
        data = dispatch_task("carbon.report.draft", payload, instance_id="carbon")

    assert data.get("status") == "completed", data  # NOT pulse_unavailable
    result = data.get("result") or {}
    summary = result.get("summary", "")
    assert summary, data
    assert "Ghg Summary" in summary, data
    assert "verified" in summary, data
