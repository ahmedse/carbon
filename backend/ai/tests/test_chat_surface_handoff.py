"""G2 / ADR-0046 — Chat never stages host mutations; emits Agent/My handoff."""
from __future__ import annotations

import pytest

from ai.engine.agent.chat_surface import (
    INTERNAL_REASON,
    build_chat_handoff_result,
    build_handoff_actions,
    chat_mutation_narration,
    handoff_spec_for_api,
    is_chat_surface,
    is_host_mutation_tool,
    synthesize_intent_handoff,
)
from ai.engine.agent.guardrails import (
    HookContext,
    chat_surface_hook,
    consent_hook,
)
from ai.engine.cognition.turn.execute import _narrate_tool
from ai.engine_runtime import (
    _chat_handoff_envelope,
    _chat_handoff_note,
    _extract_tool_actions,
    _should_force_action,
)
import types


def test_chat_surface_is_fail_closed():
    assert is_chat_surface("chat") is True
    assert is_chat_surface(None) is True
    assert is_chat_surface("") is True
    assert is_chat_surface("agent") is False
    assert is_chat_surface("plan") is False


def test_host_mutation_detection():
    assert is_host_mutation_tool(
        "call_host_api",
        {"api_name": "submit_my_leave", "body": {"days": 1}},
    )
    assert not is_host_mutation_tool(
        "call_host_api",
        {"api_name": "get_my_leave_balance"},
    )
    assert not is_host_mutation_tool("learn_fact", {"fact": "x"})
    assert is_host_mutation_tool("create_dq_rule", {"name": "r"})


@pytest.mark.asyncio
async def test_chat_surface_hook_cancels_leave_submit():
    ctx = HookContext(
        tool_name="call_host_api",
        tool_args={
            "api_name": "submit_my_leave",
            "body": {
                "leave_type": "annual",
                "start_date": "2026-09-23",
                "days": 1,
            },
        },
        instance_id="nibras",
        surface="chat",
        user_message="اريد اجازة غدا",
    )
    result = await chat_surface_hook(ctx)
    assert result.action == "cancel"
    assert "chat_no_host_mutation" in (result.flags or [])
    assert "ADR" not in (result.reason or "")
    assert "G2" not in (result.reason or "")
    assert isinstance(result.payload, dict)
    assert result.payload.get("action") == "chat_handoff"
    assert result.payload.get("reason") == INTERNAL_REASON
    assert result.payload.get("requires_confirmation") is False
    assert result.payload.get("caveats") == []
    env = result.payload.get("envelope") or {}
    assert env.get("caveats") == []
    assert "ADR" not in str(env)
    actions = result.payload.get("actions") or []
    assert actions[0].get("type") == "open_panel"
    routes = {a.get("route") for a in actions if a.get("type") == "navigate"}
    assert "/my/leave" in routes


@pytest.mark.asyncio
async def test_agent_surface_allows_staging_via_consent_hook():
    ctx = HookContext(
        tool_name="call_host_api",
        tool_args={"api_name": "submit_my_leave", "body": {"days": 1}},
        instance_id="nibras",
        surface="agent",
    )
    assert (await chat_surface_hook(ctx)).action == "pass"
    consent = await consent_hook(ctx)
    assert consent.action == "pass"
    assert "stages_for_confirmation" in (consent.flags or [])


@pytest.mark.asyncio
async def test_chat_allows_reads_and_memory():
    read_ctx = HookContext(
        tool_name="call_host_api",
        tool_args={"api_name": "get_my_leave_balance"},
        instance_id="nibras",
        surface="chat",
    )
    assert (await chat_surface_hook(read_ctx)).action == "pass"

    mem_ctx = HookContext(
        tool_name="learn_fact",
        tool_args={"fact": "prefers dark mode", "category": "preference"},
        instance_id="nibras",
        surface="chat",
    )
    assert (await chat_surface_hook(mem_ctx)).action == "pass"


def test_extract_tool_actions_promotes_chat_handoff_ctas():
    handoff = build_chat_handoff_result(
        "call_host_api",
        {"api_name": "submit_my_leave", "body": {"leave_type": "annual"}},
    )
    actions, pending = _extract_tool_actions([
        {
            "tool_name": "call_host_api",
            "tool_args": {"api_name": "submit_my_leave"},
            "result": handoff,
            "error": None,
            "guardrail_flags": ["chat_no_host_mutation"],
        },
    ])
    assert pending == []
    assert any(a.get("type") == "open_panel" for a in actions)
    assert any(
        a.get("type") == "navigate" and a.get("route") == "/my/leave"
        for a in actions
    )


def test_chat_handoff_note_owns_copy_no_adr():
    handoff = build_chat_handoff_result(
        "call_host_api",
        {"api_name": "submit_my_leave", "body": {"days": 1}},
        user_message="I want leave tomorrow",
    )
    note = _chat_handoff_note([{
        "tool_name": "call_host_api",
        "result": handoff,
        "guardrail_flags": ["chat_no_host_mutation"],
    }])
    assert "Chat does not submit" in note
    assert "Agent" in note
    assert "ADR" not in note
    assert "G2" not in note
    env = _chat_handoff_envelope([{
        "tool_name": "call_host_api",
        "result": handoff,
    }])
    assert env is not None
    assert env.get("caveats") == []


def test_intent_handoff_for_arabic_leave():
    text, actions, envelope = synthesize_intent_handoff(
        "اريد اجازة, ليوم واحد غدا, عادي."
    )
    assert "الدردشة" in text or "إجازة" in text
    assert "ADR" not in text
    assert any(a.get("type") == "open_panel" for a in actions)
    assert any(a.get("route") == "/my/leave" for a in actions)
    assert envelope.get("caveats") == []
    assert "ADR" not in str(envelope)


def test_chat_ess_write_intent_detects_leave_not_balance():
    from ai.engine.agent.chat_surface import is_ess_write_intent

    assert is_ess_write_intent("اريد اجازة، ليوم واحد غدا، عادي")
    assert is_ess_write_intent("I want to request annual leave tomorrow")
    assert not is_ess_write_intent("what is my leave balance")
    assert not is_ess_write_intent("hello")


def test_leave_handoff_spec():
    spec = handoff_spec_for_api("submit_my_leave")
    assert spec["process"] == "leave.request.lifecycle"
    assert spec["my_route"] == "/my/leave"
    acts = build_handoff_actions(spec)
    assert acts[0]["type"] == "open_panel"
    assert len(acts) >= 2


def test_manager_review_intent_hands_off_to_team():
    from ai.engine.agent.chat_surface import (
        build_handoff_actions,
        handoff_copy,
        handoff_spec_for_intent,
    )

    spec = handoff_spec_for_intent("Please approve the leave request in my inbox")
    assert spec["my_route"] == "/team"
    assert spec.get("manager_only")
    acts = build_handoff_actions(spec)
    assert len(acts) == 1
    assert acts[0]["route"] == "/team"
    copy = handoff_copy(spec)
    assert "Team" in copy
    assert "Agent" in copy  # says not in Agent
    assert "Open" in copy or "inbox" in copy.lower()


def test_chat_narration_never_says_submitting():
    msg = _narrate_tool(
        "call_host_api",
        {"api_name": "submit_my_leave", "body": {"days": 1}},
        surface="chat",
    )
    assert "Submitting" not in msg
    assert "Preparing" in msg or "next steps" in msg.lower()
    # Agent surface may still say Submitting
    agent_msg = _narrate_tool(
        "call_host_api",
        {"api_name": "submit_my_leave", "body": {"days": 1}},
        surface="agent",
    )
    assert "Submitting" in agent_msg


def test_shall_i_submit_prose_triggers_handoff_backstop():
    """F3 — Chat asking for submit confirm is bait, not a valid ending."""
    ledger = types.SimpleNamespace(
        execution=types.SimpleNamespace(completed_tools=[])
    )
    assert _should_force_action(
        "اريد اجازة, ليوم واحد غدا, عادي.",
        types.SimpleNamespace(
            text="للتقدم بطلب إجازة سأحتاج إلى تأكيد منك. هل تريدني أن أتابع تقديم الطلب؟"
        ),
        ledger,
    ) is True


def test_chat_mutation_narration_copy():
    assert "leave" in chat_mutation_narration("submit_my_leave").lower()
