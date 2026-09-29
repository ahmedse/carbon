"""Locks the Pulse mode contract. A locked row fails here when the behavior breaks.

Live rows stay in the catalog. This file does not claim them.
"""
import pytest
from ai.engine.agent.chat_surface import (
    Surface,
    build_plan_mode_switch_handoff,
    is_host_mutation_tool,
)
from ai.engine.cognition.plan.export_bind import show_or_fail_read
from ai.engine.cognition.plan.loop import StepResult, downgrade_empty_completion
from ai.engine.cognition.turn.plan_proposal import (
    draft_was_cancelled,
    dropped_draft_text,
    hold_draft_text,
    is_task_plan,
    proposal_payload,
    stick_to_open_draft,
)
from ai.engine.cognition.turn.runner_util import _filter_draft_tools
from ai.eval.mode_behaviors import BEHAVIORS, by_id, counts
from ai.plans_service import apply_self_read_owner

LOCKED = {
    "ASK-01", "ASK-02", "ASK-03", "ASK-04", "ASK-10", "ASK-14", "ASK-15",
    "PLAN-01", "PLAN-02", "PLAN-03", "PLAN-05", "PLAN-06", "PLAN-07", "PLAN-08",
    "PLAN-09", "PLAN-10", "PLAN-11", "PLAN-12", "PLAN-13", "PLAN-14",
    "TASK-02", "TASK-03", "TASK-04", "TASK-05", "TASK-11", "TASK-12",
    "TASK-13", "TASK-14", "TASK-15", "TASK-16", "TASK-17",
}

_ONE_READ = {
    "steps": [{
        "step_id": 1,
        "intent": "List my direct reports",
        "tool_name": "call_host_api",
        "tool_args": {"api_name": "list_my_direct_reports"},
        "is_mutation": False,
    }],
}

_TOOLS = [
    {"function": {"name": name}}
    for name in (
        "plan_task", "edit_plan", "approve_plan", "call_host_api",
        "ask_clarification",
    )
]


def _names(mode: str) -> set[str]:
    return {
        d["function"]["name"]
        for d in _filter_draft_tools(_TOOLS, "list them", "general", mode)
    }


class _Step:
    def __init__(self, api, output):
        self.status = "completed"
        self.error = ""
        self.tool_args_json = {"api_name": api}
        self.tool_output_json = output
        self.saved = []

    def save(self, **kwargs):
        self.saved.append(kwargs.get("update_fields"))


class _Run:
    def __init__(self):
        self.status = "completed"
        self.final_response = "someone else"
        self.saved = []

    def save(self, **kwargs):
        self.saved.append(kwargs.get("update_fields"))


def test_catalog_matches_the_locks():
    ids = [row.id for row in BEHAVIORS]
    assert len(ids) == len(set(ids))
    assert counts()["all"] == 47
    assert counts()["locked"] == 31
    assert counts()["live"] == 16
    assert counts()["open"] == 0
    assert counts()["ask"] == 16
    assert counts()["plan"] == 14
    assert counts()["task"] == 17
    assert {row.id for row in BEHAVIORS if row.proof == "locked"} == LOCKED
    assert set(by_id()) == set(ids)


def test_ask_01_one_read_is_not_a_task():
    assert is_task_plan(_ONE_READ) is False
    assert proposal_payload(_ONE_READ, brief="What is my leave balance?") is None


def test_ask_02_and_15_ask_has_no_task_tools():
    assert _names("ask").isdisjoint({"plan_task", "edit_plan", "approve_plan"})
    for name in ("plan_task", "edit_plan", "approve_plan"):
        assert is_host_mutation_tool(name, {}, surface=Surface.CHAT_ASK) is True


def test_ask_03_write_handoff_does_not_say_submitted():
    env = build_plan_mode_switch_handoff(user_message="submit my leave", surface=Surface.CHAT_ASK)
    blob = " ".join([env["envelope"]["headline"], *env["envelope"]["prose"]]).lower()
    assert env["envelope"]["headline"] == "Ask mode does not create tasks"
    assert "submitted" not in blob
    assert env["pending_exec"] is False


def test_ask_04_confirm_is_not_a_chat_write():
    env = build_plan_mode_switch_handoff(surface=Surface.CHAT_ASK)
    assert env["requires_confirmation"] is False
    assert env["pending_exec"] is False


def test_plan_01_and_03_one_read_on_plan_is_an_unstored_card():
    shown = proposal_payload(_ONE_READ, brief="list them", single_read=True)
    assert shown["kind"] == "plan_proposal"
    assert shown["plan_id"] == ""
    assert shown["steps"][0]["effect"] is False
    assert shown["steps"][0]["args"] == [{"name": "api_name", "value": "list_my_direct_reports"}]


def test_plan_02_ask_flag_does_not_promote_the_read():
    assert is_task_plan(_ONE_READ) is False
    assert proposal_payload(_ONE_READ, single_read=False) is None


def test_plan_06_and_07_composer_sticks_change_revises():
    draft = {
        "kind": "plan_proposal",
        "steps": [{"step_id": 1, "intent": "List my direct reports"}],
        "plan_json": {"steps": [{"step_id": 1}]},
    }
    assert stick_to_open_draft(draft, change=False) is draft
    assert stick_to_open_draft(draft, change=True) is None
    assert draft_was_cancelled("why you approved it ?!") is False
    assert "nothing has been approved" in hold_draft_text("en").lower()
    assert "plans are approved" not in hold_draft_text("en").lower()


def test_plan_08_short_cancel_drops_the_draft():
    assert draft_was_cancelled("cancel")
    assert draft_was_cancelled("i said cancel")
    assert draft_was_cancelled("i saied cancel")
    assert not draft_was_cancelled(
        "Create a 1-step task that lists my direct reports then stops. Do not write."
    )
    text = dropped_draft_text("en").lower()
    assert "dropped" in text
    assert "waiting for create task" not in text


def test_plan_10_blocked_tool_does_not_claim_approval():
    env = build_plan_mode_switch_handoff(user_message="list them", surface=Surface.CHAT_PLAN)
    blob = " ".join([env["envelope"]["headline"], *env["envelope"]["prose"]])
    assert env["envelope"]["headline"] == "Nothing is approved yet"
    assert "Plans are approved" not in blob
    assert env["pending_exec"] is False


def test_plan_11_plan_withholds_approval_and_host_reads():
    assert _names("plan") == {"ask_clarification"}
    assert is_host_mutation_tool("edit_plan", {}, surface=Surface.CHAT_PLAN) is True
    assert is_host_mutation_tool("approve_plan", {}, surface=Surface.CHAT_PLAN) is True


def test_plan_12_card_shows_read_versus_change_and_a_block():
    plan = {
        "steps": [
            _ONE_READ["steps"][0],
            {
                "step_id": 2,
                "intent": "Export the workbook",
                "tool_name": "export_document",
                "tool_args": {},
                "is_mutation": False,
            },
        ],
    }
    shown = proposal_payload(
        plan,
        findings=[{
            "step_id": 2,
            "code": "output_fit",
            "detail": "no fields",
            "blocks": True,
        }],
    )
    assert shown["steps"][0]["effect"] is False
    export = shown["steps"][1]
    assert export["blocked"] is True
    assert export["effect"] is True
    assert shown["blocks_create"] is True


def test_plan_14_one_write_is_a_proposal_and_still_unstored():
    write = {
        "steps": [{
            "step_id": 1,
            "intent": "Submit the request",
            "tool_name": "call_host_api",
            "tool_args": {"api_name": "submit_my_leave", "method": "POST"},
            "is_mutation": True,
        }],
    }
    assert is_task_plan(write) is True
    shown = proposal_payload(write, brief="submit it")
    assert shown["kind"] == "plan_proposal"
    assert shown["plan_id"] == ""
    assert shown["steps"][0]["effect"] is True


def test_task_04_foreign_profile_fails_owner_and_leave_not_reports():
    run = _Run()
    profile = _Step("get_my_profile", {"result": {"status_code": 200, "data": {"employee_no": "2378"}}})
    leave = _Step("get_my_leave_balance", {"result": {"status_code": 200, "data": []}})
    reports = _Step("list_my_direct_reports", {"result": {"status_code": 200, "data": []}})
    assert apply_self_read_owner(run, [profile, leave, reports], "1067") is True
    assert run.status == "failed"
    assert profile.status == "failed"
    assert leave.status == "failed"
    assert reports.status == "completed"
    assert "1067" in run.final_response and "2378" in run.final_response


def test_task_05_and_11_empty_completion_is_not_finished():
    status, ok = downgrade_empty_completion(
        "completed",
        "I wasn't able to complete the requested plan",
        [StepResult(step_id=1, intent="read", draft_text="")],
        True,
    )
    assert status == "failed" and ok is False
    held, held_ok = downgrade_empty_completion(
        "completed",
        "Finished. Here's what I found.",
        [StepResult(step_id=1, intent="read", draft_text="1067")],
        True,
    )
    assert held == "completed" and held_ok is True


def test_task_05_unshown_body_fails_the_step():
    result = StepResult(step_id=1, intent="read", tool_output={"result": {"status_code": 200, "data": {"x": 1}}})
    show_or_fail_read(result, {"api_name": "not_a_catalog_read"}, language="en", catalog=[], is_mutation=False)
    assert result.error == "host result was not shown"
    assert result.critic_verdict == "veto"


def test_task_12_a_failed_step_is_not_completed():
    status, ok = downgrade_empty_completion("failed", "blocked", [], False)
    assert status == "failed" and ok is False


def test_ask_10_a_refused_lookup_is_repeated_not_invented():
    from ai.engine.cognition.turn.zero_llm import last_directory_deny, render_directory_deny

    deny = last_directory_deny([{
        "tool": "resolve_entity",
        "digest": "not authorized (people:view required)",
    }])
    text = render_directory_deny({
        "message": "Not authorized to look up other employees (people:view required).",
    })
    assert deny is not None
    assert "people:view" in text
    assert "1067" not in text


@pytest.mark.asyncio
async def test_ask_14_memory_is_a_proposal_until_confirm():
    from ai.engine.agent.tools import execute_learn_fact
    from ai.engine.cognition.dialogue.pending_action import PendingActionStore

    class _Exec:
        def __init__(self):
            self.stored = []

        async def cancel_pending_learn_facts(self, conversation_id):
            return None

        async def create_pending_execution(self, **kwargs):
            self.stored.append(kwargs)
            return type("Row", (), {"id": "mem-1"})()

    executor = _Exec()
    result = await execute_learn_fact(
        fact="project code ALPHA-7",
        category="observation",
        instance_id="nibras",
        executor=executor,
        conversation_id="conv-1",
    )
    assert result["requires_confirmation"] is True
    assert executor.stored[0]["tool_name"] == "learn_fact"
    store = PendingActionStore()
    assert store.check_confirmation("conv-1", "what is my leave balance") is None


def test_plan_05_card_has_create_change_cancel_not_approve_or_run():
    from pathlib import Path

    text = Path(
        "/home/ahmed/ws/carbon/carbon-frontend/src/shell/PlanProposalForm.jsx",
    ).read_text(encoding="utf-8")
    assert "t('plan.create')" in text
    assert "t('plan.change')" in text
    assert "t('plan.cancel')" in text
    assert "Approve" not in text
    assert "Run" not in text


def test_plan_09_composer_cancel_does_not_delete_a_task():
    import inspect

    from ai.engine.cognition.turn.runner_surfaces import SoftSurfacesMixin

    source = inspect.getsource(SoftSurfacesMixin._try_plan_dial_process_plan)
    assert "dropped_draft_text" in source
    assert "delete_plan" not in source
    assert "cancel_plan" not in source


def test_plan_13_footer_says_nothing_runs_until_approve():
    import json
    from pathlib import Path

    doc = json.loads(Path(
        "/home/ahmed/ws/carbon/carbon-frontend/src/i18n/locales/en/ai.json",
    ).read_text(encoding="utf-8"))
    hint = doc["composerPlanHint"]
    assert "drafts a plan" in hint
    assert "Ask is a separate session" in hint
    assert "Nothing runs until you Approve" in hint
    assert "already running" not in hint.lower()


def test_task_02_run_stays_off_until_approved():
    from pathlib import Path

    text = Path(
        "/home/ahmed/ws/carbon/carbon-frontend/src/shell/AgentRunToolbar.jsx",
    ).read_text(encoding="utf-8")
    assert "effectiveStatus === 'approved' || effectiveStatus === 'paused'" in text
    assert "pending_approval" not in text.split("const runnable", 1)[1].split("const paused", 1)[0]


@pytest.mark.asyncio
async def test_task_03_a_write_pauses_and_a_read_does_not():
    from ai.tests.test_pv2_deterministic_steps import (
        _loan_args,
        _run_bound_read_step,
        _run_bound_step,
    )

    write, _, _ = await _run_bound_step(
        tool_args=_loan_args(),
        confirmation_token=None,
        language="en",
        expect_draft_called=False,
    )
    assert write.paused is True
    assert write.executed is False
    assert "mutation_not_confirmed" in write.critic_flags

    read, _, _ = await _run_bound_read_step(
        api_name="get_my_leave_balance",
        payload=[{"leave_type": "annual", "entitled": 30, "remaining": 18}],
        language="en",
    )
    assert read.paused is False
    assert read.executed is True


def test_task_15_retry_keeps_the_mutation_flag():
    from ai.engine.cognition.plan.loop import ReActLoop
    from ai.engine.cognition.plan.planner import PlanStep

    loop = ReActLoop.__new__(ReActLoop)
    failed = PlanStep(
        step_id=1,
        intent="Submit the request",
        tool_name="call_host_api",
        tool_args={"api_name": "submit_my_leave"},
        is_mutation=True,
    )
    retried = loop._replan_step(failed, StepResult(step_id=1, intent="submit", error="no token"))
    assert retried[0].is_mutation is True


def test_task_16_a_later_pass_does_not_clear_the_night():
    from ai.eval.agent_deep_bench import score_agent_bench

    report = score_agent_bench(
        plan_bank={"passed": 12, "n": 12},
        soak={"soak_complete": True},
        retests=[],
    )
    assert report["night_2026_09_23"] == "FAIL stays"


def test_task_17_go_live_stays_shut_while_a_row_is_open():
    from ai.eval.tasks_prod_bench import score_kpis

    reached = {"honest": "reached", "note": "ok"}
    kpis = score_kpis({
        "grounded": reached, "bind": reached, "first_turn": reached,
        "cockpit": reached, "stability": reached, "arabic": reached,
        "latency": reached, "chat": reached,
    })
    by_id = {row["id"]: row for row in kpis}
    assert by_id["R7"]["honest"] == "missing"
    assert by_id["R8"]["honest"] == "fail"
    assert by_id["R12"]["honest"] == "fail"
    assert "Lab" in by_id["R12"]["note"]


def test_task_13_and_14_chat_surfaces_cannot_approve():
    for surface in (Surface.CHAT_ASK, Surface.CHAT_PLAN):
        assert is_host_mutation_tool("approve_plan", {}, surface=surface) is True
        assert is_host_mutation_tool("edit_plan", {}, surface=surface) is True
        env = build_plan_mode_switch_handoff(surface=surface)
        assert env["pending_exec"] is False
        assert "submitted" not in env["message"].lower()
