"""Plan dial + ESS brief → deterministic process plan; restyle follow-ups."""
from __future__ import annotations

import pytest

from ai.engine.cognition.plan.process_dial import (
    is_composite_brief,
    materialize_loan_request_plan,
)
from ai.engine.cognition.turn.arbiter import Arbiter, TurnDecision
from ai.engine.cognition.turn.plan_dial import (
    build_restyle_messages,
    is_restyle_request,
    last_assistant_answer,
    open_tasks_action,
    plan_dial_process_brief,
    render_plan_dial_answer,
    restyle_target_lang,
    restyle_wants_more_detail,
)

_AR_COMPOSITE = (
    "راجع قروضي المفتوحة ورصيد إجازتي في الوقت نفسه. إذا كان لدي قرض مفتوح، توقف. "
    "إذا لا، قدّم طلب قرض ٥٠٠ دينار لمدة ١٢ شهراً."
)
_PLAN_PREFIX = (
    "[Pulse mode: Plan. Draft a reviewable plan from this thread. "
    "Ask one missing fact at a time. Do not submit or change host records.]\n\n"
)
_ASK_PREFIX = "[Pulse mode: Ask. Answer from data; do not create tasks.]\n\n"


# ── Gate ─────────────────────────────────────────────────────────────────

def test_plan_dial_composite_loan_brief_is_process_brief():
    brief = plan_dial_process_brief(_PLAN_PREFIX + _AR_COMPOSITE)
    assert brief == _AR_COMPOSITE


def test_ask_dial_never_becomes_process_plan():
    assert plan_dial_process_brief(_ASK_PREFIX + _AR_COMPOSITE) is None
    assert plan_dial_process_brief(_AR_COMPOSITE) is None


def test_plan_dial_read_question_is_not_a_plan():
    assert plan_dial_process_brief(_PLAN_PREFIX + "كم رصيد إجازتي؟") is None
    assert plan_dial_process_brief(_PLAN_PREFIX + "What is my leave balance?") is None


def test_plan_dial_restyle_is_not_a_plan():
    assert plan_dial_process_brief(
        _PLAN_PREFIX + "in arabic and in more details please"
    ) is None


# ── Composite loan spine ─────────────────────────────────────────────────

@pytest.mark.django_db
def test_composite_loan_plan_has_guard_and_parallel_leave_read():
    assert is_composite_brief(_AR_COMPOSITE)
    plan = materialize_loan_request_plan(_AR_COMPOSITE)
    apis = [s.tool_args.get("api_name") for s in plan.steps]
    assert apis == ["list_my_loans", "get_my_leave_balance", "submit_my_loan"]
    submit = plan.steps[-1]
    assert submit.is_mutation is True
    assert submit.depends_on == [0, 1]
    guard = submit.tool_args.get("_guard") or {}
    assert guard.get("condition") == "no_open_loans"
    assert guard.get("on_fail") == "stop"
    assert "only if no open loan" in submit.intent
    assert submit.tool_args["body"].get("principal") == 500.0
    assert submit.tool_args["body"].get("term_months") == 12
    assert plan.phases[0].strategy == "parallel"
    assert "Guard" in plan.synthesis_instruction


@pytest.mark.django_db
def test_plain_loan_plan_unchanged_two_steps():
    plan = materialize_loan_request_plan("أريد قرض طوارئ ٥٠٠٠ لمدة ١٢ شهراً")
    apis = [s.tool_args.get("api_name") for s in plan.steps]
    assert apis == ["list_my_loans", "submit_my_loan"]
    assert "_guard" not in plan.steps[-1].tool_args
    assert plan.phases[0].strategy == "sequential"


# ── Answer rendering ─────────────────────────────────────────────────────

def _plan_dto() -> dict:
    plan = materialize_loan_request_plan(_AR_COMPOSITE)
    return {
        "id": "2dcf0692-dc0b-447d-be97-abe9258e56ce",
        "status": "pending_approval",
        "steps": [
            {
                "step_id": s.step_id,
                "intent": s.intent,
                "tool_name": s.tool_name,
                "tool_args": s.tool_args,
            }
            for s in plan.steps
        ],
    }


@pytest.mark.django_db
def test_render_arabic_answer_mirrors_language_and_guard():
    text = render_plan_dial_answer(brief=_AR_COMPOSITE, plan=_plan_dto(), lang="ar")
    assert "2dcf0692" in text
    assert "الشرط" in text
    assert "قروضي" in text
    assert "رصيد إجازتي" in text
    assert "٥٠٠" in text and "١٢" in text
    # Never the invented salary clarify, never English body.
    assert "salary" not in text.lower()
    assert "monthly" not in text.lower()
    assert "Submit loan request" not in text


@pytest.mark.django_db
def test_render_english_answer():
    text = render_plan_dial_answer(
        brief="If I have an open loan, stop. Otherwise apply for a 500 loan over 12 months.",
        plan=_plan_dto(),
        lang="en",
    )
    assert "Plan 2dcf0692 drafted" in text
    assert "Guard" in text
    assert "Tasks" in text
    assert "500" in text


def test_open_tasks_action_bilingual():
    en = open_tasks_action("abc", "en")
    ar = open_tasks_action("abc", "ar")
    assert en["type"] == ar["type"] == "open_panel"
    assert en["panel"] == "tasks"
    assert en["label"] == "Open in Tasks"
    assert ar["label"] == "افتح في المهام"


# ── Restyle ──────────────────────────────────────────────────────────────

def test_restyle_detection():
    assert is_restyle_request("in arabic and in more details please")
    assert is_restyle_request(_PLAN_PREFIX + "in arabic and in more details please")
    assert is_restyle_request("بالعربي وبالتفصيل")
    assert is_restyle_request("more details")
    assert is_restyle_request("can you elaborate")
    # New content is a new ask, not a restyle.
    assert not is_restyle_request("in arabic: I want a 500 loan for 12 months")
    assert not is_restyle_request("give me the salary report in arabic")
    assert not is_restyle_request("ما هي الخطوات؟")
    assert not is_restyle_request("")


def test_restyle_target_lang_and_detail():
    assert restyle_target_lang("in arabic and in more details please") == "ar"
    assert restyle_target_lang("in english please") == "en"
    assert restyle_target_lang("بالتفصيل") == "ar"
    assert restyle_target_lang("more details") == "en"
    assert restyle_wants_more_detail("in arabic and in more details please")
    assert not restyle_wants_more_detail("in arabic please")


def test_restyle_messages_keep_facts_no_new_questions():
    history = [
        {"role": "user", "content": "x"},
        {"role": "assistant", "content": "Plan 2dcf0692 drafted — 3 steps."},
        {"role": "user", "content": "in arabic and in more details please"},
    ]
    prev = last_assistant_answer(history)
    assert prev.startswith("Plan 2dcf0692")
    msgs = build_restyle_messages(
        previous_answer=prev,
        request="in arabic and in more details please",
        target_lang="ar",
        more_detail=True,
    )
    system = msgs[0]["content"]
    assert "Arabic" in system
    assert "Do NOT add new facts" in system
    assert "Do NOT ask what the topic is" in system
    assert "Plan 2dcf0692" in msgs[1]["content"]


def test_last_assistant_answer_empty_history():
    assert last_assistant_answer([]) == ""
    assert last_assistant_answer(None) == ""


# ── Arbiter ──────────────────────────────────────────────────────────────

def test_arbiter_plan_dial_process_is_tool_answer():
    signals = [
        {"gate": "plan_dial_process", "fired": True},
        {"gate": "chat_handoff", "fired": False},
    ]
    assert Arbiter().decide(signals) == TurnDecision.TOOL_ANSWER
    # A Chat handoff that also fired still outranks it (ADR-0046).
    signals.append({"gate": "chat_handoff", "fired": True})
    assert Arbiter().decide(signals) == TurnDecision.HANDOFF_AGENT
