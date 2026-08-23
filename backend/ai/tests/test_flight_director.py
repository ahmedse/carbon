"""
Phase 25-B — FlightDirector core: unit tests.

Covers the deterministic supervision surfaces per
``docs/DESIGN-FLIGHT-DIRECTOR.md`` §3.1–§3.3:

  - ``WorkingMemoryLedger.parse_output`` — every common created-entity shape.
  - Stale-reference validation/rewrite (125 → 129) with NO false positive on
    pre-existing ids; ambiguous / name-mismatch cases never rewrite.
  - ``contract_gate`` — artifact-noun coverage + per-step criteria templates.
  - ``prepare_step`` — corrected args (top-level AND nested in ``body``),
    extra instructions, escalation ``model_override``.
  - ``on_step_completed`` — ledger updates + worker-fidelity guard (1-of-2
    re-run; mutation never auto re-runs — RULE_21; no-op guard).

No DB is needed for the pure logic tests — a fake executor stands in for the
read-only host GETs. One ``django_db`` test proves the real
``CarbonHostExecutor`` existence check (the no-false-positive guarantee).
"""
from __future__ import annotations

import json

import pytest
from django.test import override_settings

from ai.flight_director import (
    FlightDirector,
    WorkingMemoryLedger,
    contract_gate,
)
from ai.engine.cognition.plan.planner import Plan, PlanStep
from ai.engine.cognition.turn.witnesses import DraftResult, ExecutionResult


# ── Helpers ───────────────────────────────────────────────────────────────


class _FakeExecutor:
    """Minimal executor stand-in: read-only list GETs only (no staging)."""

    def __init__(self, rules=None, tables=None):
        self.rules = rules or []
        self.tables = tables or []
        self.get_calls: list[tuple] = []

    async def _call_api(self, method, endpoint, params=None, body=None):
        self.get_calls.append((method, endpoint, params))
        if "dq/rules" in (endpoint or ""):
            return {"status_code": 200, "data": {"results": self.rules}}
        if "tables" in (endpoint or ""):
            return {"status_code": 200, "data": {"results": self.tables}}
        return {"status_code": 200, "data": {"results": []}}


def _step(step_id, intent, tool_name="call_host_api", tool_args=None,
          is_mutation=False, depends_on=None) -> PlanStep:
    return PlanStep(
        step_id=step_id,
        intent=intent,
        tool_name=tool_name,
        tool_args=tool_args or {},
        depends_on=depends_on or [],
        is_mutation=is_mutation,
    )


def _water_plan() -> Plan:
    """The Phase 25 water-consumption brief, decomposed into 3 steps."""
    return Plan(
        pattern="root_cause",
        steps=[
            _step(
                0,
                "Create a table for water consumption under module 31 "
                "with 4 fields",
                tool_args={
                    "api_name": "create_table",
                    "body": {
                        "title": "Water consumption",
                        "module": 31,
                        "fields": [
                            {"name": "period", "type": "string"},
                            {"name": "volume_m3", "type": "number"},
                        ],
                    },
                },
            ),
            _step(
                1,
                "Create a DQ rule 'Water consumption > 0' for the table",
                tool_args={
                    "api_name": "create_dq_rule",
                    "body": {"name": "Water consumption > 0", "rule_type": "threshold"},
                },
            ),
            _step(
                2,
                "Bind the water consumption rule to the water consumption table",
                tool_args={
                    "api_name": "bind_dq_rules",
                    "body": {"rule": 125, "data_table": 100},
                },
                depends_on=[0, 1],
            ),
        ],
        synthesis_instruction="Summarize what was created.",
        source="llm_decompose",
    )


# ── WorkingMemoryLedger.parse_output ──────────────────────────────────────


def test_parse_output_all_shapes():
    ledger = WorkingMemoryLedger()

    # {"id": N}
    assert ledger.parse_output({"id": 5}) == [(5, None)]
    # {"data": {"id": N, "name": X}}
    assert ledger.parse_output({"data": {"id": 6, "name": "Rule A"}}) == [(6, "Rule A")]
    # {"status_code": 201, "data": {...}}
    assert ledger.parse_output(
        {"status_code": 201, "data": {"id": 7, "title": "Table B"}}
    ) == [(7, "Table B")]
    # {"bindings": [{"id": ...}]}
    assert ledger.parse_output(
        {"bindings": [{"id": 1}, {"id": 2}]}
    ) == [(1, None), (2, None)]
    # {"table": {...}}
    assert ledger.parse_output({"table": {"id": 8, "name": "T"}}) == [(8, "T")]
    # {"artifact_id": ...}
    assert ledger.parse_output({"artifact_id": "art-1"}) == [("art-1", None)]
    # {"results": [...]} — read-only list shapes are deliberately ignored:
    # they describe pre-existing entities, not ones a prior step created.
    assert ledger.parse_output(
        {"results": [{"id": 10}, {"id": 11}]}
    ) == []


def test_parse_output_dedupes_same_id():
    ledger = WorkingMemoryLedger()
    # id appears both at top level and nested in data → one entry.
    assert ledger.parse_output(
        {"id": 9, "data": {"id": 9, "name": "X"}}, kind="rule"
    ) == [(9, "X")]


def test_parse_output_ignores_non_dicts():
    ledger = WorkingMemoryLedger()
    assert ledger.parse_output(None) == []
    assert ledger.parse_output("plain string") == []
    assert ledger.parse_output({"data": None, "id": None}) == []


# ── Stale-reference rewrite ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stale_rule_reference_rewritten_125_to_129():
    """The water incident: binding references stale rule 125, rule 129 was
    created earlier in the run → rewrite pre-staging."""
    fd = FlightDirector(executor=_FakeExecutor())  # host has NO rules
    fd.ledger.add("rule", 129, name="Water consumption > 0", step_index=1)
    fd.ledger.add("table", 100, name="Water consumption", step_index=0)

    plan = _water_plan()
    binding = plan.steps[2]
    prep = await fd.prepare_step(binding, fd.ledger, attempts=0)

    assert prep.corrected_tool_args == {
        "api_name": "bind_dq_rules",
        "body": {"rule": 129, "data_table": 100},
    }
    assert prep.repair_kind == "stale_reference"
    assert prep.repair_detail
    # Both the rewrite and the (unchanged, valid) table ref are recorded.
    repairs = json.loads(prep.repair_detail)
    assert any(
        r["kind"] == "stale_reference"
        and r["ref"] == "rule:125"
        and r["corrected_to"] == 129
        for r in repairs
    )
    # The rewrite is durable in the ledger for later acceptance checks.
    assert fd.ledger.repaired_refs[-1]["stale_id"] == 125
    assert fd.ledger.repaired_refs[-1]["corrected_id"] == 129


@pytest.mark.asyncio
async def test_pre_existing_id_is_not_rewritten():
    """No false positive: a rule that already exists on the host stays as-is."""
    fd = FlightDirector(executor=_FakeExecutor(rules=[{"id": 88, "name": "Old rule"}]))
    fd.ledger.add("table", 100, name="Water consumption", step_index=0)

    plan = _water_plan()
    binding = _step(
        2,
        "Bind the water consumption rule to the water consumption table",
        tool_args={"api_name": "bind_dq_rules",
                   "body": {"rule": 88, "data_table": 100}},
    )
    prep = await fd.prepare_step(binding, fd.ledger, attempts=0)

    # No correction, no repair, no instruction.
    assert prep.corrected_tool_args is None
    assert prep.repair_kind is None
    assert fd.ledger.repaired_refs == []


@pytest.mark.asyncio
async def test_stale_id_with_multiple_candidates_is_not_rewritten():
    """Ambiguity (two earlier rules) → never guess; instruct to re-list."""
    fd = FlightDirector(executor=_FakeExecutor())
    fd.ledger.add("rule", 129, name="Water consumption > 0", step_index=1)
    fd.ledger.add("rule", 130, name="Water consumption >= 5", step_index=1)
    fd.ledger.add("table", 100, name="Water consumption", step_index=0)

    plan = _water_plan()
    prep = await fd.prepare_step(plan.steps[2], fd.ledger, attempts=0)

    assert prep.corrected_tool_args is None  # nothing rewritten
    assert prep.repair_kind == "stale_reference_unresolved"
    assert "list current rules" in (prep.extra_instructions or "")


@pytest.mark.asyncio
async def test_stale_id_without_name_overlap_is_not_rewritten():
    """Single candidate but no name overlap with the step intent → instruct,
    never rewrite (avoids rewiring an unrelated entity)."""
    fd = FlightDirector(executor=_FakeExecutor())
    fd.ledger.add("rule", 129, name="Scope 2 invoice rule", step_index=1)
    fd.ledger.add("table", 100, name="Water consumption", step_index=0)

    plan = _water_plan()
    prep = await fd.prepare_step(plan.steps[2], fd.ledger, attempts=0)

    assert prep.corrected_tool_args is None
    assert prep.repair_kind == "stale_reference_unresolved"


@pytest.mark.asyncio
async def test_in_ledger_id_is_valid_noop():
    """An id the ledger already knows (created earlier) needs no host round-trip."""
    fd = FlightDirector(executor=_FakeExecutor())
    fd.ledger.add("rule", 129, name="Water consumption > 0", step_index=1)
    fd.ledger.add("table", 100, name="Water consumption", step_index=0)

    binding = _step(
        2,
        "Bind the water consumption rule to the water consumption table",
        tool_args={"api_name": "bind_dq_rules",
                   "body": {"rule": 129, "data_table": 100}},
    )
    prep = await fd.prepare_step(binding, fd.ledger, attempts=0)

    assert prep.corrected_tool_args is None
    assert prep.repair_kind is None
    # No host round-trips were needed for in-ledger ids.
    assert fd.executor.get_calls == []


@pytest.mark.asyncio
async def test_nested_list_refs_are_validated():
    """Alternative binding shape ``{"table_id": T, "dq_rule_ids": [125]}`` is
    walked and corrected too (spec §3.2 lists ``dq_rule_ids``)."""
    fd = FlightDirector(executor=_FakeExecutor())
    fd.ledger.add("rule", 129, name="Water consumption > 0", step_index=1)
    fd.ledger.add("table", 100, name="Water consumption", step_index=0)

    binding = _step(
        2,
        "Bind the water consumption rule to the water consumption table",
        tool_args={"api_name": "bind_dq_rules",
                   "body": {"table_id": 100, "dq_rule_ids": [125]}},
    )
    prep = await fd.prepare_step(binding, fd.ledger, attempts=0)

    assert prep.corrected_tool_args["body"]["dq_rule_ids"] == [129]
    assert prep.corrected_tool_args["body"]["table_id"] == 100
    assert prep.repair_kind == "stale_reference"


# ── prepare_step: escalation model override ───────────────────────────────


@override_settings(AI_FLIGHT_DIRECTOR_ESCALATION_MODEL="escalation-probe")
@pytest.mark.asyncio
async def test_prepare_step_model_override_on_escalation_attempt():
    fd = FlightDirector(executor=_FakeExecutor())
    step = _step(0, "Create a DQ rule",
                 tool_args={"api_name": "create_dq_rule", "body": {"name": "R"}})

    first = await fd.prepare_step(step, fd.ledger, attempts=0)
    assert first.model_override is None

    escalated = await fd.prepare_step(step, fd.ledger, attempts=1)
    assert escalated.model_override == "escalation-probe"


@override_settings(AI_FLIGHT_DIRECTOR_ESCALATION_MODEL="escalation-probe")
def test_escalation_model_setting_default():
    fd = FlightDirector()
    assert fd.escalation_model() == "escalation-probe"


def test_escalation_model_default_when_unset():
    fd = FlightDirector()
    # No override_settings → the getattr default applies.
    assert fd.escalation_model() == "gpt-4o"


# ── contract_gate ─────────────────────────────────────────────────────────


def test_contract_gate_finds_no_missing_artifacts_but_suggests_criteria():
    plan = _water_plan()
    brief = (
        "Create a table for water consumption under data product 31 with 4 "
        "fields, reuse or create required DQ rules, and bind them to the table."
    )
    result = contract_gate(plan, brief)

    # table, rule, field, binding all covered by a step.
    assert result["findings"] == []
    criteria = result["suggested_criteria"]
    # create_table step → table_fields criterion from its fields args.
    assert criteria["0"]["type"] == "table_fields"
    assert criteria["0"]["fields"] == ["period", "volume_m3"]
    # create rule step (call_host_api POST) → created_entity/host/201.
    assert criteria["1"] == {"type": "created_entity", "kind": "host",
                             "expect_status": 201}
    # binding step (call_host_api POST) → created_entity/host/201.
    assert criteria["2"]["type"] == "created_entity"


def test_contract_gate_flags_missing_artifact():
    plan = Plan(
        pattern="custom",
        steps=[
            _step(0, "Reuse an existing rule", tool_args={"api_name": "list_dq_rules"}),
        ],
        synthesis_instruction="",
        source="custom",
    )
    brief = "Create a monthly water consumption report and export it."
    result = contract_gate(plan, brief)

    nouns = {f["noun"] for f in result["findings"]}
    assert "report" in nouns  # no step covers the report artifact
    assert "export" in nouns
    assert "table" not in nouns  # not mentioned in the brief


def test_contract_gate_never_blocks():
    plan = _water_plan()
    brief = "Do something entirely unrelated with no artifacts."
    result = contract_gate(plan, brief)
    # The gate records; it never raises or signals a hard block.
    assert isinstance(result["findings"], list)
    assert isinstance(result["suggested_criteria"], dict)


# ── on_step_completed: ledger + fidelity ──────────────────────────────────


def _tool_call(name: str, args: dict) -> dict:
    return {
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(args)},
    }


def test_on_step_completed_updates_ledger_from_all_tools():
    fd = FlightDirector()
    step = _step(1, "Create a DQ rule",
                 tool_args={"api_name": "create_dq_rule", "body": {"name": "R"}})
    draft = DraftResult(
        text="creating",
        tool_calls=[_tool_call("call_host_api", {"api_name": "create_dq_rule"})],
    )
    execution = ExecutionResult(completed_tools=[
        {
            "tool_name": "call_host_api",
            "result": json.dumps({"status_code": 201, "data": {"id": 129, "name": "R"}}),
        },
    ])

    verdict = fd.on_step_completed(step, draft, execution, None, fd.ledger)

    assert not verdict.fidelity_failure
    entities = fd.ledger.by_kind("rule")
    assert len(entities) == 1
    assert entities[0].id == 129
    assert entities[0].name == "R"
    assert entities[0].step_index == 1


def test_fidelity_1_of_2_requests_rerun():
    fd = FlightDirector()
    step = _step(1, "Create a DQ rule", is_mutation=False)
    draft = DraftResult(
        text="creating",
        tool_calls=[
            _tool_call("call_host_api", {"api_name": "create_dq_rule"}),
            _tool_call("call_host_api", {"api_name": "bind_dq_rules"}),
        ],
    )
    execution = ExecutionResult(completed_tools=[
        {"tool_name": "call_host_api",
         "result": json.dumps({"status_code": 201, "data": {"id": 129}})},
    ])

    verdict = fd.on_step_completed(step, draft, execution, None, fd.ledger,
                                   attempts=0)

    assert verdict.fidelity_failure
    assert verdict.declared == 2
    assert verdict.executed == 1
    assert verdict.requests_rerun
    assert verdict.repair_kind == "fidelity"
    assert "1 declared action(s) did not run" in (verdict.extra_instructions or "")
    assert not verdict.escalated


def test_fidelity_mutation_escalates_never_reruns():
    """RULE_21: a mutation step that dropped declared calls is NEVER auto
    re-run — it escalates for human review."""
    fd = FlightDirector()
    step = _step(1, "Create a DQ rule", is_mutation=True)
    draft = DraftResult(text="x", tool_calls=[_tool_call("call_host_api", {"a": 1})])
    execution = ExecutionResult(completed_tools=[])

    verdict = fd.on_step_completed(step, draft, execution, None, fd.ledger,
                                   attempts=0)

    assert verdict.fidelity_failure
    assert verdict.escalated
    assert not verdict.requests_rerun
    assert fd.escalations == 1
    assert fd.escalated_steps == [1]


def test_fidelity_persists_after_rerun_escalates():
    fd = FlightDirector()
    step = _step(1, "Create a DQ rule", is_mutation=False)
    draft = DraftResult(text="x", tool_calls=[_tool_call("call_host_api", {"a": 1})])
    execution = ExecutionResult(completed_tools=[])

    verdict = fd.on_step_completed(step, draft, execution, None, fd.ledger,
                                   attempts=1)

    assert verdict.fidelity_failure
    assert verdict.escalated
    assert not verdict.requests_rerun
    assert "fidelity persisted after re-run" in (verdict.repair_detail or "")


def test_no_op_guard_forces_rerun_with_tool_instruction():
    """declared == 0 AND executed == 0 on a tool step → orchestrator no-op
    guard: force one re-draft to actually call the tool."""
    fd = FlightDirector()
    step = _step(1, "Create a DQ rule", tool_name="call_host_api", is_mutation=False)
    draft = DraftResult(text="I cannot run that.")  # no tool calls
    execution = ExecutionResult(completed_tools=[])

    verdict = fd.on_step_completed(step, draft, execution, None, fd.ledger,
                                   attempts=0)

    assert verdict.fidelity_failure
    assert verdict.requests_rerun
    assert verdict.repair_kind == "no_op"
    assert "call call_host_api — do not answer in prose" in (
        verdict.extra_instructions or ""
    )


def test_reasoning_step_has_no_fidelity_contract():
    fd = FlightDirector()
    step = _step(1, "Summarize the results", tool_name=None)
    draft = DraftResult(text="summary")
    execution = ExecutionResult(completed_tools=[])

    verdict = fd.on_step_completed(step, draft, execution, None, fd.ledger)

    assert not verdict.fidelity_failure
    assert not verdict.requests_rerun


# ── state() serialization ─────────────────────────────────────────────────


def test_state_serialization():
    fd = FlightDirector(executor=_FakeExecutor())
    fd.ledger.add("rule", 129, name="Water consumption > 0", step_index=1)
    fd.ledger.add("table", 100, name="Water consumption", step_index=0)
    fd.contract = {"ok": True, "findings": [], "suggested_criteria": {}}

    state = fd.state()

    assert [e["kind"] for e in state["ledger"]] == ["rule", "table"]
    assert state["repairs"] == []
    assert state["escalations"] == 0
    assert state["fidelity"] == {"failures": 0, "escalated_steps": []}
    assert state["contract"] == {"ok": True, "findings": [], "suggested_criteria": {}}


# ── Real host existence check (django_db) ─────────────────────────────────


@pytest.mark.django_db(transaction=True)
def test_real_executor_existence_check_no_false_positive():
    """With the REAL CarbonHostExecutor, a genuinely existing rule passes the
    existence check (no rewrite), a nonexistent one fails it, and the stale
    125 → 129 rewrite still holds against the live list."""
    from asgiref.sync import async_to_sync

    from accounts.models import User
    from dq.models import DQRule
    from ai.host_executor import CarbonHostExecutor

    user = User.objects.create_user(username="fd-executor", password="secret123")
    user.is_staff = True
    user.save(update_fields=["is_staff"])

    existing = DQRule.objects.create(
        name="Pre-existing completeness rule",
        rule_type="not_null",
        rule_level="field_validation",
    )

    executor = CarbonHostExecutor(
        db=None,
        instance_config={},
        user_token=f"inproc:carbon:{user.pk}",
        host_user_id=str(user.pk),
    )

    listed = async_to_sync(executor._call_api)("GET", "/carbon-api/dq/rules/", {})
    assert listed == {
        "status_code": 200,
        "data": {"results": [{
            "id": existing.pk,
            "name": existing.name,
            "rule_type": existing.rule_type,
            "rule_level": existing.rule_level,
            "severity": existing.severity,
            "dimension": existing.dimension,
            "is_active": existing.is_active,
        }]},
    }

    fd = FlightDirector(executor=executor)
    # The table referenced by the binding is known to have been created earlier
    # in the run, so its ref validates against the ledger and does not surface
    # as an unrelated unresolved-reference repair.
    fd.ledger.add("table", 100, name="Water consumption", step_index=0)

    # Pre-existing id → valid (no rewrite, no false positive).
    step = _step(
        2,
        "Bind the completeness rule to the water consumption table",
        tool_args={"api_name": "bind_dq_rules",
                   "body": {"rule": existing.pk, "data_table": 100}},
    )
    prep = async_to_sync(fd.prepare_step)(step, fd.ledger, attempts=0)
    assert prep.corrected_tool_args is None
    assert prep.repair_kind is None

    # Nonexistent + single ledger candidate with name overlap → rewrite.
    fd.ledger.add("rule", 129, name="Water consumption > 0", step_index=1)
    stale = _step(
        2,
        "Bind the water consumption rule to the water consumption table",
        tool_args={"api_name": "bind_dq_rules",
                   "body": {"rule": 125, "data_table": 100}},
    )
    prep2 = async_to_sync(fd.prepare_step)(stale, fd.ledger, attempts=0)
    assert prep2.corrected_tool_args["body"]["rule"] == 129
    assert prep2.repair_kind == "stale_reference"
