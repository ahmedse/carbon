"""
Phase 25-B — FlightDirector + ReActLoop integration tests.

No LLM anywhere — the DraftWitness is scripted, the CriticWitness is the real
rules-tier reviewer, and the ExecuteWitness runs the REAL in-process
``CarbonHostExecutor`` against the test database.

  Test 1 — the water-incident scenario: create table → create rule (id 129-ish)
  → binding step whose ``body.rule`` references STALE id 125. ``prepare_step``
  rewrites it to the real rule id BEFORE the mutation is staged, so the run
  completes without the FK 500 that the raw stale body raises.

  Test 2 — additive-default proof: the same plan through the real loop with
  ``flight_director=None`` behaves identically to today (no FLIGHT DIRECTOR
  guidance, no extra rows); with a director wired, the prepare_step guidance
  reaches the draft prompt and the step still succeeds.
"""
from __future__ import annotations

import json

import pytest
from asgiref.sync import async_to_sync

from ai.engine.cognition.plan.loop import ReActLoop
from ai.engine.cognition.plan.planner import Plan, PlanStep
from ai.engine.cognition.turn.critic import CriticWitness
from ai.engine.cognition.turn.draft import DraftWitness
from ai.engine.cognition.turn.execute import ExecuteWitness
from ai.engine.cognition.turn.witnesses import DraftResult, RetrievalResult
from ai.flight_director import FlightDirector
from ai.host_executor import CarbonHostExecutor


# ── Scripted draft witness ────────────────────────────────────────────────


class _ScriptedDraftWitness(DraftWitness):
    """Deterministic DraftWitness — never touches the LLM router."""

    def __init__(self, factory):
        super().__init__()
        self.factory = factory
        self.prompts: list[str] = []

    async def draft(self, **kwargs):
        prompt = kwargs.get("user_message", "")
        self.prompts.append(prompt)
        return self.factory(prompt, **kwargs)


def _tool_call(name: str, args: dict) -> dict:
    return {
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(args)},
    }


def _make_loop(executor: CarbonHostExecutor, flight_director=None) -> ReActLoop:
    return ReActLoop(
        draft_witness=_ScriptedDraftWitness(_factory_get_rules),
        critic_witness=CriticWitness(),
        executor=ExecuteWitness(executor=executor),
        llm_client=None,
        flight_director=flight_director,
    )


def _factory_get_rules(prompt: str, **kwargs) -> DraftResult:
    """The 'LLM': always call list_dq_rules (read-only, deterministic)."""
    return DraftResult(
        text="Listing the current data quality rules.",
        tool_calls=[
            _tool_call("call_host_api", {
                "api_name": "list_dq_rules",
                "explanation": "List current DQ rules",
            }),
        ],
    )


_INSTANCE_CONFIG = {
    "api_catalog": [
        {
            "name": "list_dq_rules",
            "method": "GET",
            "path": "/carbon-api/dq/rules/",
            "requires_confirmation": False,
            "description": "List DQ rules visible to the user",
        },
    ],
}


# ── Test 1: water incident — stale-id rewrite prevents the FK 500 ─────────


@pytest.mark.django_db(transaction=True)
def test_water_incident_stale_rule_rewritten_before_binding_no_fk_500():
    from accounts.models import User
    from core.models import Module
    from dataschema.models import DataTable
    from dq.models import DQRule, RuleFieldAssignment
    from ai.engine.core.exceptions import ToolExecutionError

    user = User.objects.create_user(
        username="fd-int-water", password="secret123", is_superuser=True,
    )
    module = Module.objects.create(name="Water incident module 31")

    executor = CarbonHostExecutor(
        db=None,
        instance_config={},
        user_token=f"inproc:carbon:{user.pk}",
        host_user_id=str(user.pk),
    )
    _call = lambda *a, **k: async_to_sync(executor._call_api)(*a, **k)

    created: list = []

    try:
        # ── Step 0: create the water consumption table (real POST) ──────
        table_resp = _call(
            "POST", "/carbon-api/dataschema/tables/", {},
            {
                "title": "Water consumption",
                "module": module.pk,
                "fields": [
                    {"name": "period", "label": "Period", "type": "string"},
                    {"name": "volume_m3", "label": "Volume m3", "type": "number"},
                ],
            },
        )
        assert table_resp["status_code"] == 201
        table_id = table_resp["data"]["id"]
        created.append(("table", table_id))
        assert DataTable.objects.filter(pk=table_id).exists()

        # ── Step 1: create the DQ rule (real POST) → id 129-like ────────
        rule_resp = _call(
            "POST", "/carbon-api/dq/rules/", {},
            {
                "name": "Water consumption > 0",
                "rule_type": "threshold",
                "params": {"operator": "gt", "value": 0},
            },
        )
        assert rule_resp["status_code"] == 201
        rule_id = rule_resp["data"]["id"]
        created.append(("rule", rule_id))
        assert DQRule.objects.filter(pk=rule_id).exists()

        # ── FlightDirector ledger, exactly as the loop fills it ─────────
        fd = FlightDirector(executor=executor)
        fd.ledger.add("rule", rule_id, name="Water consumption > 0", step_index=1)
        fd.ledger.add("table", table_id, name="Water consumption", step_index=0)

        # ── Step 2: binding step references STALE rule id 125 ───────────
        binding_step = PlanStep(
            step_id=2,
            intent="Bind the water consumption rule to the water consumption table",
            tool_name="call_host_api",
            tool_args={"api_name": "bind_dq_rules",
                       "body": {"rule": 125, "data_table": table_id}},
            depends_on=[0, 1],
        )

        # prepare_step rewrites the stale id BEFORE the mutation is staged.
        prep = async_to_sync(fd.prepare_step)(binding_step, fd.ledger, attempts=0)
        assert prep.corrected_tool_args is not None
        assert prep.corrected_tool_args["body"]["rule"] == rule_id
        assert prep.corrected_tool_args["body"]["data_table"] == table_id
        assert prep.repair_kind == "stale_reference"
        assert fd.ledger.repaired_refs[-1] == {
            "step": 2, "kind": "rule", "stale_id": 125, "corrected_id": rule_id,
        }

        # ── The mutation executes with the CORRECTED body → no FK 500 ───
        bind_resp = _call(
            "POST", "/carbon-api/dq/rule-assignments/", {},
            prep.corrected_tool_args["body"],
        )
        assert bind_resp["status_code"] == 201
        assert bind_resp["data"]["count"] == 1
        assert RuleFieldAssignment.objects.filter(
            rule_id=rule_id, data_table_id=table_id,
        ).exists()

        # ── Without the director the raw stale body raises the FK 500 ───
        with pytest.raises(ToolExecutionError) as excinfo:
            _call(
                "POST", "/carbon-api/dq/rule-assignments/", {},
                {"rule": 125, "data_table": table_id},
            )
        assert "Rule binding failed" in str(excinfo.value)
        # No orphaned binding rows from the failed attempt.
        assert RuleFieldAssignment.objects.filter(
            rule_id=125, data_table_id=table_id,
        ).count() == 0

        # ── Supervisor state is serializable for working_notes.flight ───
        state = fd.state()
        assert state["repairs"][-1]["corrected_id"] == rule_id
        assert state["escalations"] == 0
    finally:
        rid, tid = locals().get("rule_id"), locals().get("table_id")
        if rid and tid:
            RuleFieldAssignment.objects.filter(
                rule_id=rid, data_table_id=tid,
            ).delete()
        if rid:
            DQRule.objects.filter(pk=rid).delete()
        if tid:
            DataTable.objects.filter(pk=tid).delete()
        Module.objects.filter(pk=module.pk).delete()
        User.objects.filter(pk=user.pk).delete()


# ── Test 2: additive default — fd=None behaves identically to today ───────


def _read_plan() -> Plan:
    """A read-only step that carries a stale ``rule`` reference arg — the
    reference validator has something to supervise without any mutation."""
    return Plan(
        pattern="custom",
        steps=[
            PlanStep(
                step_id=0,
                intent="List current data quality rules",
                tool_name="call_host_api",
                tool_args={"api_name": "list_dq_rules",
                           "query_params": {"rule": 125}},
            ),
        ],
        synthesis_instruction="Summarize the rule list.",
        source="llm_decompose",
    )


def _run_loop(loop: ReActLoop, flight_director, instance_id: str):
    return async_to_sync(loop.run)(
        plan=_read_plan(),
        instance_id=instance_id,
        conversation_id=f"conv-{instance_id}",
        user_message="List the current data quality rules.",
        system_prompt="You are the Carbon Data Trust Platform copilot.",
        conversation_history=None,
        instance_config=_INSTANCE_CONFIG,
        user_info={},
        retrieval=RetrievalResult(),
        host_user_id=None,
        flight_director=flight_director,
    )


@pytest.mark.django_db(transaction=True)
def test_loop_default_matches_today_and_director_is_additive():
    from accounts.models import User
    from ai.models.core import Run

    user = User.objects.create_user(
        username="fd-int-loop", password="secret123", is_superuser=True,
    )

    def _new_executor() -> CarbonHostExecutor:
        return CarbonHostExecutor(
            db=None,
            instance_config=_INSTANCE_CONFIG,
            user_token=f"inproc:carbon:{user.pk}",
            host_user_id=str(user.pk),
        )

    run_count_before = Run.objects.count()

    try:
        # ── Run 1: flight_director=None → today's behavior ──────────────
        loop_bare = _make_loop(_new_executor(), flight_director=None)
        result_bare = _run_loop(loop_bare, None, "bare")

        assert result_bare.succeeded
        assert len(result_bare.step_results) == 1
        assert result_bare.step_results[0].error is None
        assert result_bare.step_results[0].executed
        # No FLIGHT DIRECTOR guidance reached the draft — additive default.
        assert all(
            "FLIGHT DIRECTOR:" not in p for p in loop_bare.draft_witness.prompts
        )

        # ── Run 2: same plan, director wired → still succeeds, PLUS the
        #    prepare_step guidance is visible to the draft. ──────────────
        fd = FlightDirector(executor=_new_executor())
        loop_fd = _make_loop(_new_executor(), flight_director=fd)
        result_fd = _run_loop(loop_fd, fd, "fd")

        assert result_fd.succeeded
        assert len(result_fd.step_results) == 1
        assert result_fd.step_results[0].error is None
        assert result_fd.step_results[0].executed
        # Same outcome as today — nothing about the loop changed.
        assert (
            result_bare.step_results[0].critic_verdict
            == result_fd.step_results[0].critic_verdict
        )
        # The supervisor flagged the stale reference in the draft prompt.
        fd_prompt = loop_fd.draft_witness.prompts[0]
        assert "FLIGHT DIRECTOR:" in fd_prompt
        assert "the referenced rule id 125 is invalid" in fd_prompt
        # The read-only step neither repaired nor escalated anything.
        assert fd.ledger.repaired_refs == []
        assert fd.state()["escalations"] == 0

        # ── Additive default: neither run writes any Run row ────────────
        assert Run.objects.count() == run_count_before
    finally:
        User.objects.filter(pk=user.pk).delete()
