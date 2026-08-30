"""
Wave C1 — Adaptive reasoning lane (backend) acceptance tests.

Proves the "reason" task lane:

  1. ``get_model_for_task("reason")`` resolves ``LLM_REASON_MODEL`` when set
     and falls back cleanly (through the legacy escalation model to
     ``LLM_MODEL``) when unset.
  2. S1 salience classifies genuinely hard queries ("why"/"explain"/"root
     cause") as ``route="deep"``.
  3. A ``deep`` turn selects the reason model when configured, and falls
     back cleanly when unset.
  4. A critic ``knowledge_gap`` escalates to the reason lane and records the
     escalation (critic verdict before/after) in the turn ledger (L7).

The LLM is stubbed (``get_llm_client``) because the dev environment has no
``LLM_API_KEY``; DraftWitness/CriticWitness are swapped for deterministic
fakes exactly like ``test_artifact_e2e.py``.
"""
from __future__ import annotations

import asyncio
import json
import types
from unittest.mock import patch

import pytest
from django.test import override_settings

from ai.engine.core.config import get_settings
from ai.store import reset_store


# ── Fixtures (mirror test_chat_wiring.py) ─────────────────────────────────


def _fake_completion(*args, **kwargs) -> types.SimpleNamespace:
    """Deterministic OpenAI-shaped chat completion (for the intent resolver)."""

    async def _create(**kw):
        return types.SimpleNamespace(
            choices=[
                types.SimpleNamespace(
                    message=types.SimpleNamespace(
                        content="This is a stubbed chat reply.",
                        tool_calls=None,
                    ),
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
    """Use the Django backend and force the single-pass chat path."""
    with override_settings(AI_STORE_BACKEND="django"):
        reset_store()
        yield
        reset_store()


@pytest.fixture
def single_pass(monkeypatch):
    """Disable fan-out / multi-step so the six-witness spine runs alone."""
    monkeypatch.setenv("AGENT_ORCHESTRATOR_ENABLED", "false")
    monkeypatch.setenv("KG_MULTI_STEP_ENABLED", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def stub_llm():
    """Stub the OpenAI client (no API key in dev)."""
    with patch("ai.engine.llm.provider.get_llm_client") as mock:
        mock.return_value = _fake_completion()
        yield mock


def _set_reason_model(monkeypatch, reason: str = "", escalation: str = ""):
    """Set the reason/escalation models and clear BOTH config + router caches.

    ``_TASK_MODEL_MAP`` is module-level-cached, so it must be reset alongside
    ``get_settings`` or a prior test's value leaks through.
    """
    from ai.engine.llm import router

    monkeypatch.setenv("LLM_REASON_MODEL", reason)
    monkeypatch.setenv("LLM_ESCALATION_MODEL", escalation)
    get_settings.cache_clear()
    monkeypatch.setattr(router, "_TASK_MODEL_MAP", {})


# ── 1. Router lane resolution ───────────────────────────────────────────────


def test_reason_lane_resolves_and_falls_back(monkeypatch):
    from ai.engine.llm.router import get_model_for_task

    # Unset → reason lane falls back to the deep/fallback model.
    _set_reason_model(monkeypatch, reason="", escalation="")
    assert get_model_for_task("reason") == get_model_for_task("deep")

    # Set → reason lane resolves to LLM_REASON_MODEL.
    _set_reason_model(monkeypatch, reason="reason-pro", escalation="")
    assert get_model_for_task("reason") == "reason-pro"

    # Legacy escalation model is honored as a fallback when reason is unset.
    _set_reason_model(monkeypatch, reason="", escalation="legacy-escalation")
    assert get_model_for_task("reason") == "legacy-escalation"


# ── 2. Salience deep detection ──────────────────────────────────────────────


def test_salience_routes_deep_for_reasoning_queries():
    from ai.engine.cognition.turn.salience import SalienceWitness

    async def _route(msg: str) -> str:
        return (await SalienceWitness().assess(msg)).route

    assert asyncio.run(_route("Why did our emissions rise last quarter?")) == "deep"
    assert asyncio.run(_route("explain the GHG protocol")) == "deep"
    assert asyncio.run(_route("root cause of the accuracy drop")) == "deep"
    # Conversational / identity / plain data lookups stay fast/full.
    assert asyncio.run(_route("hello")) == "fast"
    assert asyncio.run(_route("how many datasets do we have")) == "full"


# ── 3. Deep turn → reason model (integration) ───────────────────────────────


@pytest.mark.django_db(transaction=True)
def test_deep_turn_selects_reason_model(
    monkeypatch, django_store, single_pass, stub_llm
):
    """A deep salience turn selects LLM_REASON_MODEL when configured."""
    _set_reason_model(monkeypatch, reason="reason-pro", escalation="")

    captured: dict = {}

    class _FakeDraft:
        def __init__(self, *args, **kwargs):
            pass

        async def draft(self, **kwargs):
            captured["model"] = kwargs.get("model")
            return types.SimpleNamespace(
                text="Deep answer.",
                tool_calls=[],
                claimed_citations=[],
                confidence=0.9,
                model_used=kwargs.get("model") or "",
                tokens_used=5,
                prompt_tokens=3,
                completion_tokens=2,
            )

    class _FakeCritic:
        def __init__(self, *args, **kwargs):
            pass

        async def review(self, draft, retrieval, **kwargs):
            return types.SimpleNamespace(
                verdict="pass", flags=[], rewritten_text="", veto_reason="",
                partial_knowledge="",
            )

    monkeypatch.setattr(
        "ai.engine.cognition.turn.draft.DraftWitness", _FakeDraft
    )
    monkeypatch.setattr(
        "ai.engine.cognition.turn.critic.CriticWitness", _FakeCritic
    )

    from ai.engine_runtime import dispatch_task

    data = dispatch_task(
        "chat",
        {"message": "Why did our emissions rise last quarter?"},
        instance_id="carbon",
    )

    assert data.get("status") == "completed", data
    assert captured.get("model") == "reason-pro"


@pytest.mark.django_db(transaction=True)
def test_deep_turn_falls_back_when_reason_unset(
    monkeypatch, django_store, single_pass, stub_llm
):
    """A deep salience turn falls back cleanly (LLM_MODEL) when unset."""
    _set_reason_model(monkeypatch, reason="", escalation="")

    captured: dict = {}

    class _FakeDraft:
        def __init__(self, *args, **kwargs):
            pass

        async def draft(self, **kwargs):
            captured["model"] = kwargs.get("model")
            return types.SimpleNamespace(
                text="Deep answer.",
                tool_calls=[],
                claimed_citations=[],
                confidence=0.9,
                model_used=kwargs.get("model") or "",
                tokens_used=5,
                prompt_tokens=3,
                completion_tokens=2,
            )

    class _FakeCritic:
        def __init__(self, *args, **kwargs):
            pass

        async def review(self, draft, retrieval, **kwargs):
            return types.SimpleNamespace(
                verdict="pass", flags=[], rewritten_text="", veto_reason="",
                partial_knowledge="",
            )

    monkeypatch.setattr(
        "ai.engine.cognition.turn.draft.DraftWitness", _FakeDraft
    )
    monkeypatch.setattr(
        "ai.engine.cognition.turn.critic.CriticWitness", _FakeCritic
    )

    from ai.engine.llm.router import get_model_for_task
    from ai.engine_runtime import dispatch_task

    data = dispatch_task(
        "chat",
        {"message": "Why did our emissions rise last quarter?"},
        instance_id="carbon",
    )

    assert data.get("status") == "completed", data
    # Unset reason lane resolves to the deep/fallback model (LLM_MODEL).
    assert captured.get("model") == get_model_for_task("deep")


# ── 4. knowledge_gap → reason lane + ledger record (integration) ────────────


@pytest.mark.django_db(transaction=True)
def test_knowledge_gap_escalates_to_reason_lane_and_records_ledger(
    monkeypatch, django_store, single_pass, stub_llm
):
    """A critic knowledge_gap escalates to the reason lane and is recorded."""
    _set_reason_model(monkeypatch, reason="reason-pro", escalation="")

    captured: dict = {"models": []}

    class _FakeDraft:
        def __init__(self, *args, **kwargs):
            pass

        async def draft(self, **kwargs):
            model = kwargs.get("model")
            captured["models"].append(model)
            first = len(captured["models"]) == 1
            return types.SimpleNamespace(
                # First draft hedges → critic flags knowledge_gap.
                text=(
                    "I'm not sure about that specific metric, I don't have "
                    "the information."
                )
                if first
                else "Here is the detailed breakdown with the real figures.",
                tool_calls=[],
                claimed_citations=[],
                confidence=0.3 if first else 0.9,
                model_used=model or "",
                tokens_used=5,
                prompt_tokens=3,
                completion_tokens=2,
            )

    # Use the REAL critic so knowledge_gap detection actually fires.
    from ai.engine_runtime import dispatch_task

    monkeypatch.setattr(
        "ai.engine.cognition.turn.draft.DraftWitness", _FakeDraft
    )

    conv_id = "conv-reason-kg"
    data = dispatch_task(
        "chat",
        {
            "message": "Can you give me the exact emission factor for our main boiler unit?",
            "conversation_history": {"conversation_id": conv_id},
        },
        instance_id="carbon",
    )

    assert data.get("status") == "completed", data
    # First draft = default model (None → provider default); escalation = reason.
    assert captured["models"] == [None, "reason-pro"]

    # Ledger records the escalation with before/after critic verdicts.
    from ai.models.core import TurnLedgerRow

    row = TurnLedgerRow.objects.get(stage="escalation", conversation_id=conv_id)
    assert row.model_used == "reason-pro"
    payload = row.payload_json
    if isinstance(payload, str):
        payload = json.loads(payload)
    assert payload["trigger"] == "knowledge_gap"
    assert payload["to_model"] == "reason-pro"
    assert payload["verdict_before"] == "knowledge_gap"
    assert "verdict_after" in payload
