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

def test_review_only_loan_brief_does_not_submit():
    brief = "راجع قروضي المفتوحة ورصيد إجازتي في الوقت نفسه."
    assert is_composite_brief(brief)
    plan = materialize_loan_request_plan(brief)
    apis = [s.tool_args.get("api_name") for s in plan.steps]
    assert apis == ["list_my_loans", "get_my_leave_balance"]
    assert all(not s.is_mutation for s in plan.steps)
    text = render_plan_dial_answer(
        brief=brief,
        plan={"id": "f0e88412-0000", "steps": [
            {"intent": s.intent, "tool_args": s.tool_args} for s in plan.steps
        ]},
        lang="ar",
    )
    assert "قراءة فقط" in text
    assert text.count("\n- **") == 2
    assert "submit_my_loan" not in text


def test_plan_dial_composite_loan_brief_is_process_brief():
    brief = plan_dial_process_brief(_PLAN_PREFIX + _AR_COMPOSITE)
    assert brief == _AR_COMPOSITE


def test_ask_dial_never_becomes_process_plan():
    assert plan_dial_process_brief(_ASK_PREFIX + _AR_COMPOSITE) is None
    assert plan_dial_process_brief(_AR_COMPOSITE) is None


def test_plan_dial_read_question_is_not_a_plan():
    """The planner decides, not the wording: one bound read is a question."""
    from ai.engine.cognition.turn.plan_proposal import is_task_plan, proposal_payload

    one_read = {
        "id": "run-1",
        "steps": [{
            "step_id": 1,
            "intent": "Read my leave balance",
            "tool_name": "call_host_api",
            "tool_args": {"api_name": "get_my_leave_balance"},
            "is_mutation": False,
        }],
    }
    assert is_task_plan(one_read) is False
    assert proposal_payload(one_read, brief="What is my leave balance?") is None


def test_a_read_that_takes_two_steps_is_a_task():
    two_reads = {
        "id": "run-2",
        "status": "pending_approval",
        "steps": [
            {
                "step_id": 1,
                "intent": "Read the 20 lowest salaries",
                "tool_name": "call_host_api",
                "tool_args": {"api_name": "list_compensation", "body": {"limit": 20}},
                "is_mutation": False,
            },
            {
                "step_id": 2,
                "intent": "Read their positions",
                "tool_name": "call_host_api",
                "tool_args": {"api_name": "list_positions"},
                "is_mutation": False,
                "gap": "",
            },
        ],
    }
    from ai.engine.cognition.turn.plan_proposal import proposal_payload

    proposal = proposal_payload(two_reads, brief="lowest 20 salaries and their jobs")
    assert proposal["kind"] == "plan_proposal"
    assert proposal["plan_id"] == "run-2"
    assert [s["step_id"] for s in proposal["steps"]] == [1, 2]
    assert {"name": "limit", "value": "20"} in proposal["steps"][0]["args"]
    assert proposal["blocked_count"] == 0


def test_a_step_with_no_capability_is_blocked_in_the_proposal():
    from ai.engine.cognition.turn.plan_proposal import proposal_payload

    plan = {
        "id": "run-3",
        "steps": [
            {"step_id": 1, "intent": "Read salaries", "tool_name": "call_host_api"},
            {"step_id": 2, "intent": "Mail the board", "gap": "no capability"},
        ],
    }
    proposal = proposal_payload(plan, brief="send the board a salary note")
    assert proposal["blocked_count"] == 1
    assert proposal["steps"][1]["blocked"] is True
    assert proposal["steps"][1]["gap"] == "no capability"


def test_plan_dial_still_owns_a_substantive_brief():
    assert plan_dial_process_brief(
        _PLAN_PREFIX + "full report about the lowest 20 salaries and their jobs"
    ) == "full report about the lowest 20 salaries and their jobs"


@pytest.mark.asyncio
async def test_v21_plan_route_returns_the_planner_not_the_draft(monkeypatch):
    """The superseded soft exit must not drop the plan. The planner owns the turn."""
    from types import SimpleNamespace

    from ai.engine.cognition.turn.exit_policy import may_stage
    from ai.engine.cognition.turn.router import ProcessMode, RouteDecision, RouteKind
    from ai.engine.cognition.turn.runner_metered_state import MeteredTurnState
    from ai.engine.cognition.turn.runner_pre_s1 import run_pre_s1_gates

    monkeypatch.setenv("PULSE_UNDERSTAND", "v21")
    assert may_stage("plan_dial_process") is False

    proposal = object()
    ledger = SimpleNamespace(decision_signals=[])
    runner = SimpleNamespace()

    async def _plan(**kwargs):
        return proposal, ledger

    async def _understand(**kwargs):
        raise AssertionError("understanding must not run once a proposal exists")

    runner._try_plan_dial_process_plan = _plan
    runner._try_v21_understand = _understand
    route = RouteDecision(
        kind=RouteKind.PLAN_PROCESS,
        mode=ProcessMode.PLAN,
        message="lowest 20 salaries and their jobs",
        committed=True,
        reason="governed_process_dial",
    )
    out = await run_pre_s1_gates(
        runner,
        MeteredTurnState(user_message=route.message),
        instance_id="nibras",
        conversation_id="c",
        host_user_id="2",
        process_mode="plan",
        surface=None,
        page_context="",
        conversation_history=[],
        instance_config={},
        user_info={},
        progress_callback=None,
        stream_callback=None,
        model=None,
        temperature=None,
        knowledge_items=None,
        scope=None,
        process_state=None,
        meter=None,
        state_ctx=None,
        budget=None,
        turn_id="t" * 8,
        t0=0.0,
        ledger=ledger,
        staged=[],
        settings=SimpleNamespace(NAVIGATION_RESOLVER_ENABLED=False),
        turn_route=route,
        original_user_message=route.message,
        state=None,
        _broadcast_run=None,
    )
    assert out[0] is proposal


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
