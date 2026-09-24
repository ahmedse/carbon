"""Typed pre-draft router: mode, open questions, committed decisions."""
from types import SimpleNamespace

from ai.engine.cognition.state_store import ConversationState, update_state_from_turn
from ai.engine.cognition.turn.router import (
    ProcessMode,
    RouteKind,
    TurnRouter,
)
from ai.engine.cognition.turn.witnesses import TurnLedger
from ai.engine_runtime import _should_force_action


PLAN = (
    "راجع قروضي المفتوحة ورصيد إجازتي في الوقت نفسه. "
    "إذا كان لدي قرض مفتوح، توقف. إذا لا، قدّم طلب قرض ٥٠٠ دينار لمدة ١٢ شهراً."
)


def test_structured_mode_not_prompt_prefix_owns_plan_route():
    decision = TurnRouter().decide(
        message=PLAN,
        process_mode="plan",
        state=ConversationState(),
    )
    assert decision.mode is ProcessMode.PLAN
    assert decision.kind is RouteKind.PLAN_PROCESS
    assert decision.committed is True
    assert decision.message == PLAN


def test_ask_mode_same_brief_does_not_create_plan():
    decision = TurnRouter().decide(
        message=PLAN,
        process_mode="ask",
        state=ConversationState(),
    )
    assert decision.mode is ProcessMode.ASK
    assert decision.kind is RouteKind.NORMAL
    assert decision.committed is False


def test_report_clarify_is_typed_open_question():
    decision = TurnRouter().decide(
        message="I need a full report about salaries in the company",
        process_mode="ask",
        state=ConversationState(),
    )
    assert decision.kind is RouteKind.REPORT_CLARIFY
    assert decision.committed
    assert decision.open_question is not None
    payload = decision.open_question.to_dict()
    assert payload["kind"] == "report_focus"
    assert payload["slot"] == "report_focus"
    assert [row["id"] for row in payload["options"]] == ["1", "2", "3", "4"]


def test_numbered_followup_resolves_from_state_not_assistant_prose():
    state = ConversationState(open_question={
        "kind": "report_focus",
        "slot": "report_focus",
        "prompt": "this wording can change freely",
        "options": [
            {"id": "1", "label": "Distribution", "value": "salary bands with charts"},
            {"id": "2", "label": "Run health", "value": "payroll run health"},
        ],
    })
    decision = TurnRouter().decide(
        message="1",
        process_mode="ask",
        state=state,
        history=[{"role": "assistant", "content": "completely unrelated wording"}],
    )
    assert decision.kind is RouteKind.FOLLOWUP
    assert decision.message == "salary bands with charts"
    assert decision.committed is False


def test_typed_question_roundtrips_through_conversation_state():
    state = ConversationState()
    state = update_state_from_turn(
        state,
        decision="clarify",
        response_text="Choose a report focus",
        open_question={
            "kind": "report_focus",
            "prompt": "Choose a report focus",
            "slot": "report_focus",
            "options": [{"id": "1", "label": "Bands", "value": "salary bands"}],
        },
    )
    restored = ConversationState.from_dict(state.to_dict())
    assert restored.open_question["kind"] == "report_focus"
    assert restored.open_question["options"][0]["value"] == "salary bands"


def test_committed_route_cannot_be_overwritten_by_runtime_fallback():
    ledger = TurnLedger(
        turn_id="t",
        instance_id="nibras",
        decision_committed=True,
        route_kind="plan_process",
        process_mode="plan",
    )
    response = SimpleNamespace(text="تمت صياغة الخطة")
    assert _should_force_action(PLAN, response, ledger) is False


def test_restyle_is_committed_route():
    decision = TurnRouter().decide(
        message="in arabic and in more details please",
        process_mode="plan",
        state=ConversationState(),
        history=[{"role": "assistant", "content": "Plan drafted."}],
    )
    assert decision.kind is RouteKind.RESTYLE
    assert decision.committed
