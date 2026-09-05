"""
Wave C2a — Surface calibrated confidence (Faculty 7) acceptance tests.

Proves the outcome-shaped confidence signal is derived from the REAL turn and
exposed end-to-end (engine → provider → serializer), with no engine internals
leaking to the UI (RULE_23):

  1. ``_confidence_label`` maps a 0.0-1.0 score to ``high|medium|low|uncertain``.
  2. An honest-uncertainty turn surfaces ``honest_uncertainty=True`` and
     ``confidence_label="uncertain"`` through the in-process chat task.
  3. ``_serialize_message`` exposes both fields from stored metadata (and
     defaults cleanly when absent).
"""
from __future__ import annotations

import types
from unittest.mock import patch

import pytest
from django.test import override_settings

from ai.engine.core.config import get_settings
from ai.store import reset_store


# ── Fixtures (mirror test_reason_lane.py) ─────────────────────────────────


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
    """Set the reason/escalation models and clear BOTH config + router caches."""
    from ai.engine.llm import router

    monkeypatch.setenv("LLM_REASON_MODEL", reason)
    monkeypatch.setenv("LLM_ESCALATION_MODEL", escalation)
    get_settings.cache_clear()
    monkeypatch.setattr(router, "_TASK_MODEL_MAP", {})


# ── 1. Confidence label mapping (unit) ──────────────────────────────────────


def test_confidence_label_mapping():
    from ai.engine_runtime import _confidence_label

    assert _confidence_label(None) == ""
    assert _confidence_label(0.95) == "high"
    assert _confidence_label(0.8) == "high"
    assert _confidence_label(0.6) == "medium"
    assert _confidence_label(0.35) == "low"
    assert _confidence_label(0.2) == "uncertain"


# ── 1b. Conservation of confidence helpers (unit) ──────────────────────────


def test_min_input_confidence_resolved_dict():
    from ai.engine_runtime import _min_input_confidence

    assert (
        _min_input_confidence(
            [
                {
                    "tool_name": "web_research",
                    "result": {"status": "resolved", "confidence": 0.7},
                }
            ]
        )
        == 0.7
    )


def test_min_input_confidence_json_string():
    from ai.engine_runtime import _min_input_confidence

    assert (
        _min_input_confidence(
            [
                {
                    "tool_name": "web_research",
                    "result": '{"status": "resolved", "confidence": 0.5}',
                }
            ]
        )
        == 0.5
    )


def test_min_input_confidence_host_envelope():
    from ai.engine_runtime import _min_input_confidence

    assert (
        _min_input_confidence(
            [
                {
                    "tool_name": "web_research",
                    "result": {
                        "status_code": 200,
                        "data": {"status": "resolved", "confidence": 0.4},
                    },
                }
            ]
        )
        == 0.4
    )


def test_min_input_confidence_ignores_no_match_and_error():
    from ai.engine_runtime import _min_input_confidence

    results = [
        {
            "tool_name": "web_research",
            "result": {"status": "no_match", "reason": "x", "hint": "h"},
        },
        {
            "tool_name": "web_research",
            "result": {"status": "error", "cause": "boom"},
        },
        {
            "tool_name": "web_research",
            "result": {"status": "resolved", "confidence": 0.6},
        },
    ]
    assert _min_input_confidence(results) == 0.6


def test_min_input_confidence_none_when_no_resolved():
    from ai.engine_runtime import _min_input_confidence

    results = [
        {
            "tool_name": "web_research",
            "result": {"status": "no_match", "reason": "x", "hint": "h"},
        },
        {
            "tool_name": "web_research",
            "result": {"status": "error", "cause": "boom"},
        },
    ]
    assert _min_input_confidence(results) is None


def test_min_input_confidence_empty_list_none():
    from ai.engine_runtime import _min_input_confidence

    assert _min_input_confidence([]) is None


def test_conserved_confidence_no_constraint():
    from ai.engine_runtime import _conserved_confidence

    assert _conserved_confidence(0.9, None) == (0.9, False)


def test_conserved_confidence_caps_amplification():
    from ai.engine_runtime import _conserved_confidence

    assert _conserved_confidence(0.9, 0.6) == (0.6, True)


def test_conserved_confidence_no_violation():
    from ai.engine_runtime import _conserved_confidence

    assert _conserved_confidence(0.5, 0.6) == (0.5, False)


def test_conserved_confidence_none_answer():
    from ai.engine_runtime import _conserved_confidence

    assert _conserved_confidence(None, 0.6) == (0.6, False)


# ── 2. Honest-uncertainty turn → flag + label (integration) ────────────────


@pytest.mark.django_db(transaction=True)
def test_honest_uncertainty_surfaces_flag_and_uncertain_label(
    monkeypatch, django_store, single_pass, stub_llm
):
    """A critic knowledge_gap with no reason model surfaces the honest flag."""
    _set_reason_model(monkeypatch, reason="", escalation="")

    class _FakeDraft:
        def __init__(self, *args, **kwargs):
            pass

        async def draft(self, **kwargs):
            from ai.engine.cognition.turn.witnesses import DraftResult

            return DraftResult(
                text=(
                    "I'm not sure about that specific metric, I don't have "
                    "the information."
                ),
                confidence=0.3,
                model_used=kwargs.get("model") or "",
                tokens_used=5,
                prompt_tokens=3,
                completion_tokens=2,
            )

    # Use the REAL critic so knowledge_gap detection actually fires.
    from ai.engine_runtime import dispatch_task

    monkeypatch.setattr(
        "ai.engine.cognition.turn.draft.DraftWitness", _FakeDraft
    )

    data = dispatch_task(
        "chat",
        {"message": "Can you give me the exact emission factor for our main boiler unit?"},
        instance_id="carbon",
    )

    assert data.get("status") == "completed", data
    result = data["result"]
    assert result["honest_uncertainty"] is True
    assert result["confidence_label"] == "uncertain"


@pytest.mark.django_db(transaction=True)
def test_confident_turn_surfaces_high_label(
    monkeypatch, django_store, single_pass, stub_llm
):
    """A confident, clean turn surfaces honest_uncertainty=False + high label."""
    _set_reason_model(monkeypatch, reason="", escalation="")

    class _FakeDraft:
        def __init__(self, *args, **kwargs):
            pass

        async def draft(self, **kwargs):
            from ai.engine.cognition.turn.witnesses import DraftResult

            return DraftResult(
                text="Scope 1 emissions rose 4% because of increased fuel use.",
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
    result = data["result"]
    assert result["honest_uncertainty"] is False
    assert result["confidence_label"] == "high"


@pytest.mark.django_db(transaction=True)
def test_clarify_shortcircuit_surfaces_label_and_honest_flag(
    monkeypatch, django_store, single_pass, stub_llm
):
    """Regression: the intent-resolver clarify short-circuit returns BEFORE any
    draft/critic witness, so there is no ``ledger.draft`` to derive from. The
    label must come from the runner's own ``AgentResponse.confidence_label``
    (``medium``) and the clarification must surface as honest uncertainty —
    never silently drop to ``""``/``False``."""
    _set_reason_model(monkeypatch, reason="", escalation="")

    from ai.engine.cognition.turn.intent import IntentResolution, IntentResolver

    async def _fake_resolve(self, **kwargs):
        return IntentResolution(
            action="clarify",
            delivery="explain",
            intent="",
            candidates=[],
            confidence=0.0,
            clarification="Are you asking about carbon emissions or something else?",
            options=[],
            input_tokens=5,
            output_tokens=3,
            model_used="gpt-4o",
        )

    monkeypatch.setattr(IntentResolver, "resolve", _fake_resolve)

    from ai.engine_runtime import dispatch_task

    data = dispatch_task(
        "chat",
        {
            "message": (
                "What is the exact lifetime in kg of every fluorescent tube "
                "in building C?"
            ),
        },
        instance_id="carbon",
    )

    assert data.get("status") == "completed", data
    result = data["result"]
    assert result["honest_uncertainty"] is True
    assert result["confidence_label"] == "medium"
    assert "Are you asking" in (result.get("content") or "")


@pytest.mark.django_db(transaction=True)
def test_weather_clarify_stores_pending_weather_focus(
    monkeypatch, django_store, single_pass, stub_llm
):
    """WEATHER-FT turn 1: a weather query that the intent resolver clarifies
    must seed ``pending_weather`` in working memory so the next turn (a bare
    location confirmation) can re-route into the weather tool."""
    _set_reason_model(monkeypatch, reason="", escalation="")

    from ai.engine.cognition.turn.intent import IntentResolution, IntentResolver
    from ai.engine.memory.working import get_working_memory

    async def _fake_resolve(self, **kwargs):
        return IntentResolution(
            action="clarify",
            delivery="explain",
            intent="",
            candidates=[],
            confidence=0.0,
            clarification="Which location in North Coast Egypt do you mean?",
            options=[],
            input_tokens=5,
            output_tokens=3,
            model_used="gpt-4o",
        )

    monkeypatch.setattr(IntentResolver, "resolve", _fake_resolve)

    conv_id = "conv-weather-ft-1"
    _wm = get_working_memory()
    _wm.clear(conv_id)

    from ai.engine_runtime import dispatch_task

    data = dispatch_task(
        "chat",
        {
            "message": "tell me abt the todays weather in northcost egypt?",
            "conversation_history": {"conversation_id": conv_id, "messages": []},
        },
        instance_id="carbon",
    )

    assert data.get("status") == "completed", data
    focus = _wm.get_focus(conv_id)
    assert focus is not None, "expected pending_weather focus to be stored"
    assert focus.entity_type == "pending_weather"
    assert "weather" in focus.entity.lower()
    _wm.clear(conv_id)


@pytest.mark.django_db(transaction=True)
def test_weather_followthrough_suppresses_second_clarification(
    monkeypatch, django_store, single_pass, stub_llm
):
    """WEATHER-FT turn 2: with a ``pending_weather`` focus already set, a bare
    location reply is rewritten to a weather query and the intent-resolver
    clarify/disambiguate short-circuit is SUPPRESSED — never a second
    'which one did you mean?' clarification."""
    _set_reason_model(monkeypatch, reason="", escalation="")

    from ai.engine.cognition.turn.intent import IntentResolution, IntentResolver
    from ai.engine.memory.working import get_working_memory

    async def _fake_resolve(self, **kwargs):
        # The resolver WOULD disambiguate — the rewrite-turn guard must skip it.
        return IntentResolution(
            action="disambiguate",
            delivery="explain",
            intent="",
            candidates=[],
            confidence=0.4,
            clarification="",
            options=["El Alamein, Egypt", "El Alamein, Libya"],
            input_tokens=5,
            output_tokens=3,
            model_used="gpt-4o",
        )

    monkeypatch.setattr(IntentResolver, "resolve", _fake_resolve)

    conv_id = "conv-weather-ft-2"
    _wm = get_working_memory()
    _wm.set_focus(conv_id, "weather in northcost egypt", "pending_weather")

    from ai.engine_runtime import dispatch_task

    data = dispatch_task(
        "chat",
        {
            "message": "El Alamein",
            "conversation_history": {"conversation_id": conv_id, "messages": []},
        },
        instance_id="carbon",
    )

    assert data.get("status") == "completed", data
    content = (data["result"].get("content") or "").lower()
    # The disambiguation short-circuit text must NOT appear — suppression worked.
    assert "which do you mean" not in content
    assert "el alamein, libya" not in content
    _wm.clear(conv_id)


@pytest.mark.django_db(transaction=True)
def test_critic_veto_caps_confidence_to_uncertain(
    monkeypatch, django_store, single_pass, stub_llm
):
    """Regression: a critic VETO verdict means the answer was REJECTED as
    unsupported — it must surface as "uncertain" + honest, never a
    high-confidence bluff, even when the draft's self-reported confidence is
    high (live E2E caught this: an unanswerable question routed through a
    failed tool call and was still labeled "high")."""
    _set_reason_model(monkeypatch, reason="", escalation="")

    class _FakeDraft:
        def __init__(self, *args, **kwargs):
            pass

        async def draft(self, **kwargs):
            from ai.engine.cognition.turn.witnesses import DraftResult

            return DraftResult(
                text="Our boiler emitted 9,999 tCO2e last quarter.",
                confidence=0.92,
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
                verdict="veto",
                flags=["ungrounded_claim"],
                rewritten_text="",
                veto_reason="no knowledge or memory context to support the claim",
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
        {"message": "What is our exact boiler emission last quarter?"},
        instance_id="carbon",
    )

    assert data.get("status") == "completed", data
    result = data["result"]
    assert result["confidence_label"] == "uncertain", result
    assert result["honest_uncertainty"] is True, result


@pytest.mark.django_db(transaction=True)
def test_pass_with_ungrounded_claim_flag_stays_confident(
    monkeypatch, django_store, single_pass, stub_llm
):
    """Regression (calibration subtlety): the critic attaches the ADVISORY
    ``ungrounded_claim`` flag even to ``pass`` verdicts for general-knowledge
    answers it cannot ground against retrieval. That flag must NOT downgrade a
    confident answer — only a ``veto`` verdict is a rejection."""
    _set_reason_model(monkeypatch, reason="", escalation="")

    class _FakeDraft:
        def __init__(self, *args, **kwargs):
            pass

        async def draft(self, **kwargs):
            from ai.engine.cognition.turn.witnesses import DraftResult

            return DraftResult(
                text="Scope 1 covers direct emissions; Scope 2 covers purchased energy.",
                confidence=0.91,
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
                verdict="pass",
                flags=["ungrounded_claim"],
                rewritten_text="",
                veto_reason="",
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
        {"message": "What is the difference between Scope 1 and Scope 2?"},
        instance_id="carbon",
    )

    assert data.get("status") == "completed", data
    result = data["result"]
    assert result["confidence_label"] == "high", result
    assert result["honest_uncertainty"] is False, result


# ── 3. Serializer exposes both fields (unit) ────────────────────────────────


def test_serialize_message_exposes_confidence_fields():
    from ai.intelligence import _serialize_message

    class _Msg:
        id = "m-1"
        conversation_id = "c-1"
        role = "assistant"
        content = "hi"
        metadata_json = {
            "confidence_label": "low",
            "honest_uncertainty": True,
        }
        token_usage_json = {}
        parent_message_id = None
        parent_id = None
        is_deleted = False
        context_signature = ""
        status = "completed"
        provider_model = ""
        outcome = None
        correction_text = ""
        created_at = types.SimpleNamespace(isoformat=lambda: "2026-08-30T00:00:00")

    out = _serialize_message(_Msg())
    assert out["confidence_label"] == "low"
    assert out["honest_uncertainty"] is True


def test_serialize_message_defaults_cleanly():
    from ai.intelligence import _serialize_message

    class _Msg:
        id = "m-2"
        conversation_id = "c-2"
        role = "assistant"
        content = "hi"
        metadata_json = {}
        token_usage_json = {}
        parent_message_id = None
        parent_id = None
        is_deleted = False
        context_signature = ""
        status = "completed"
        provider_model = ""
        outcome = None
        correction_text = ""
        created_at = types.SimpleNamespace(isoformat=lambda: "2026-08-30T00:00:00")

    out = _serialize_message(_Msg())
    assert out["confidence_label"] == ""
    assert out["honest_uncertainty"] is False
