"""Agent → Discuss → apply is typed state, not a phrase list (ADR-0049 P1/P9/P11).

Golden for the 2026-09-24 transcript (plan e20c2937): refine in Chat, type
"apply", then "accept" — Pulse answered with a generic plan and then
"I wasn't able to generate a response". Root causes, all removed here:

1. bare "apply" / "accept" were not in an apply allowlist;
2. the discuss context was inferred by scanning history for a marker;
3. the plan id was regex-searched out of the transcript;
4. the APPLY prompt told the model to call ``edit_plan`` in Chat, which the
   ADR-0046 guard cancels on every Chat surface (dead end even when 1–3 work).

Now: the discuss reply is a typed ``plan_revision`` question on state; the
shared affirmation module resolves the next turn; a confirmed revision is a
0-LLM handoff to Agent, where the existing replan + diff review applies it.
"""
from __future__ import annotations

import asyncio

import pytest

from ai.engine.cognition.state_store import (
    ConversationState,
    resolve_against_state,
    update_state_from_turn,
    upsert_active_plan,
)
from ai.engine.cognition.turn.plan_revision import (
    KIND,
    build_revision_handoff,
    build_revision_question,
    is_discuss_turn,
    linked_plan_ref,
    pending_revision,
)

PLAN_ID = "e20c2937-7ece-45b0-8db6-3f40e89ee35d"
SEED = (
    f'I\'d like to refine plan (plan {PLAN_ID}): "Compute payroll variance".\n\n'
    "DISCUSSION ONLY — reply in Chat with one improved brief and a short numbered step list.\n"
    "Do not change the Agent plan until I explicitly ask you to apply changes."
)
REVISION = (
    "Improved brief: compute Q3 payroll variance against Q2, validate against GOSI caps, "
    "report per department.\n1. Fetch runs\n2. Compute variance\n3. Validate\n4. Report"
)


def _state_after_discuss_reply(state: ConversationState | None = None) -> ConversationState:
    """Fold the discuss turn exactly as runner_s6 + runner._save_conversation_state do."""
    state = state or ConversationState()
    ref = linked_plan_ref(state, SEED)
    assert ref is not None
    update_state_from_turn(
        state,
        decision="answer",
        user_message=SEED,
        response_text=REVISION,
        open_question=build_revision_question(ref, REVISION),
    )
    return state


# ── Linking the plan ──────────────────────────────────────────────────────


def test_seed_links_plan_from_fe_protocol_line():
    state = ConversationState()
    assert linked_plan_ref(state, SEED) == {"plan_id": PLAN_ID, "title": ""}
    assert is_discuss_turn(SEED, state, "plan") is True


def test_active_plans_from_plans_service_win_a_title():
    state = ConversationState()
    upsert_active_plan(state, plan_id=PLAN_ID, status="pending_approval", title="Compute payroll variance")
    assert linked_plan_ref(state, SEED) == {"plan_id": PLAN_ID, "title": "Compute payroll variance"}
    # No uuid in the message → most recent revisable plan from state.
    assert linked_plan_ref(state, "refine it") == {"plan_id": PLAN_ID, "title": "Compute payroll variance"}


def test_no_plan_no_discuss():
    state = ConversationState()
    assert linked_plan_ref(state, "DISCUSSION ONLY — reply in Chat.") is None
    assert is_discuss_turn("DISCUSSION ONLY — reply in Chat.", state, "plan") is False


# ── The reply becomes typed state ──────────────────────────────────────────


def test_discuss_reply_persists_typed_question_on_answer_turn():
    state = _state_after_discuss_reply()
    q = pending_revision(state)
    assert q is not None
    assert q["kind"] == KIND
    assert q["plan_id"] == PLAN_ID
    assert q["revision"].startswith("Improved brief: compute Q3 payroll variance")
    assert q["confirm"]["plan_id"] == PLAN_ID
    assert q["asked_turn"] == 1
    # Round-trips through the durable store shape.
    assert pending_revision(ConversationState.from_dict(state.to_dict())) is not None


def test_plain_answer_turn_still_clears_open_question():
    state = _state_after_discuss_reply()
    update_state_from_turn(state, decision="answer", user_message="what is GOSI?", response_text="GOSI is …")
    assert pending_revision(state) is None
    assert state.open_question == {}


# ── Resolving the user's reply against state (no allowlist) ────────────────


@pytest.mark.parametrize("utterance", [
    "apply", "Apply.", "accept", "yes", "ok apply", "go", "proceed", "do it",
    "نعم", "اعتمدها", "طبق", "تمام طبقها",
])
def test_commit_affirmations_resolve_against_pending_revision(utterance):
    state = _state_after_discuss_reply()
    confirm = resolve_against_state(utterance, state)
    assert confirm is not None
    assert confirm["kind"] == KIND
    assert confirm["plan_id"] == PLAN_ID


@pytest.mark.parametrize("utterance", [
    "why in single step?!",
    "do not apply yet",
    "apply for three days leave",
    "think deeper, compare to latest online numbers and make doc file report",
    "accept? are you sure",
    "what's my leave balance",
])
def test_non_commit_turns_stay_in_discuss(utterance):
    state = _state_after_discuss_reply()
    assert resolve_against_state(utterance, state) is None
    assert is_discuss_turn(utterance, state, "plan") is True


def test_dial_off_plan_is_not_discuss():
    state = _state_after_discuss_reply()
    assert is_discuss_turn("why in single step?!", state, "ask") is False


def test_commit_words_are_not_a_global_affirmation():
    """"apply" only commits a pending *plan revision*; an ESS confirm question
    keeps the stricter starts-with-yes bar so "apply for leave" cannot fire a read."""
    state = ConversationState()
    state.open_question = {
        "kind": "confirm_api", "confirm": {"api": "get_my_leave_balance"}, "text": "Show your balance?",
    }
    assert resolve_against_state("apply for leave", state) is None
    assert resolve_against_state("yes", state) == {"api": "get_my_leave_balance"}


# ── Confirm → 0-LLM handoff to Agent ───────────────────────────────────────


def test_confirmed_revision_is_an_agent_handoff_carrying_the_revision():
    state = _state_after_discuss_reply()
    confirm = resolve_against_state("apply", state)
    response = build_revision_handoff(confirm, "apply")
    assert response.llm_calls == 0 and response.tools_used == []
    assert "Apply in Agent" in response.text or "Agent" in response.text
    assert len(response.actions) == 1
    action = response.actions[0]
    assert action["type"] == "open_panel" and action["panel"] == "tasks"
    assert action["plan_id"] == PLAN_ID
    assert action["revision"] == confirm["revision"]
    assert "I wasn't able" not in response.text


def test_arabic_reply_gets_arabic_handoff_copy():
    state = _state_after_discuss_reply()
    response = build_revision_handoff(resolve_against_state("اعتمدها", state), "اعتمدها")
    assert "الوكيل" in response.text
    assert response.actions[0]["label"] == "تطبيق في الوكيل"


# ── Why Chat must hand off: the guard cancels edit_plan on every Chat surface ─


def test_edit_plan_in_chat_plan_is_cancelled_by_adr_0046_guard():
    """Documents the contradiction the old APPLY prompt ran into. Any future
    design that asks Chat to call edit_plan must first change this contract."""
    from ai.engine.agent.guardrails import HookContext, chat_surface_hook

    ctx = HookContext(
        tool_name="edit_plan",
        tool_args={"plan_id": PLAN_ID, "step_deltas": [{"action": "remove", "step_id": 3}]},
        instance_id="x", host_user_id=1, surface="chat", process_mode="plan", user_message="apply",
    )
    result = asyncio.run(chat_surface_hook(ctx))
    assert result.action == "cancel"
    assert "chat_no_host_mutation" in (result.flags or [])
