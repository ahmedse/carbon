"""Agent run failure classes (run 0bd5072d, 2026-09-24).

One test per root cause: argument shape, typed data between steps, follow-ups
through the surface, hollow success, typed failures, and the task title
(frontend, see taskWorkspace.test.js).
"""
import json
from types import SimpleNamespace

import pytest

from ai.engine.cognition.plan.bindings import declare_bindings, resolve_bindings
from ai.engine.cognition.plan.catalog_args import (
    WRITE_HELD,
    apply_repaired_params,
    canonical_host_calls,
    catalog_arg_violations,
)
from ai.engine.cognition.plan.failures import (
    BLOCKED_DEPENDENCY,
    INVALID_ARGS,
    MISSING_BINDING,
    NO_EFFECT,
    TRANSIENT,
    classify_step_failure,
    is_replannable,
    is_retryable,
)
from ai.engine.cognition.plan.loop import ReActLoop, StepResult
from ai.engine.cognition.plan.planner import (
    PlanStep,
    _canonicalize_host_steps,
    skill_has_effect,
)
from ai.engine.cognition.turn.capability import CapabilitySurface

CATALOG = [
    {
        "name": "analyze_employees",
        "method": "GET",
        "path": "/people/analytics/",
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["dimension"],
            "properties": {
                "dimension": {"type": "string", "enum": ["org_unit", "employment_type_code"]},
                "group_by": {"type": "array"},
            },
        },
    },
    {"name": "list_payroll_runs", "method": "GET", "path": "/payroll-runs/", "latest_by": "period_end"},
    {
        "name": "get_payroll_run",
        "label": "Payroll run details",
        "method": "GET",
        "path": "/payroll-runs/{id}/",
        "parameters": {"type": "object", "required": ["id"], "properties": {"id": {}}},
    },
    {"name": "commit_payroll_run", "method": "POST", "path": "/payroll-runs/{id}/commit/"},
]
CFG = {"api_catalog": CATALOG}
SURFACE = CapabilitySurface(entries=tuple(CATALOG))

RUNS = {
    "result": json.dumps({
        "count": 3,
        "results": [
            {"id": 21, "period_end": "2026-06-30", "status": "committed"},
            {"id": 30, "period_end": "2026-09-30", "status": "draft"},
            {"id": 28, "period_end": "2026-08-31", "status": "computed"},
        ],
    }),
}


# ── 1. One argument, one place ────────────────────────────────────────────


def test_top_level_dimension_moves_to_query_params_at_plan_save():
    steps = [PlanStep(0, "headcount by org unit", "call_host_api", {
        "api_name": "analyze_employees", "dimension": "org_unit", "group_by": ["org_unit"],
    })]
    _canonicalize_host_steps(steps, CATALOG)
    assert steps[0].tool_args == {
        "api_name": "analyze_employees",
        "query_params": {"dimension": "org_unit", "group_by": ["org_unit"]},
    }
    assert catalog_arg_violations(CATALOG, "call_host_api", steps[0].tool_args) == []


def test_top_level_value_is_not_counted_as_sent():
    """The executor never sends a top-level key, so validation must not accept one."""
    args = {"api_name": "analyze_employees", "dimension": "org_unit"}
    assert catalog_arg_violations(CATALOG, "call_host_api", args)


def test_repair_writes_where_the_executor_reads():
    repaired = apply_repaired_params(
        {"api_name": "analyze_employees", "dimension": ""}, {"dimension": "org_unit"}, CATALOG,
    )
    assert repaired == {"api_name": "analyze_employees", "query_params": {"dimension": "org_unit"}}


def test_plan_save_fills_an_enum_the_step_names_once():
    steps = [PlanStep(0, "headcount by employment type code", "call_host_api", {
        "api_name": "analyze_employees",
    })]
    _canonicalize_host_steps(steps, CATALOG)
    assert steps[0].tool_args["query_params"] == {"dimension": "employment_type_code"}


def test_executed_calls_drop_transport_keys_and_bind():
    calls = [{"id": "c", "function": {"name": "call_host_api", "arguments": json.dumps({
        "api_name": "get_payroll_run", "method": "GET", "endpoint": "/x",
        "path_params": {"id": 30}, "bind": {"id": {"step": 2}},
    })}}]
    sent = json.loads(canonical_host_calls(calls, CATALOG)[0]["function"]["arguments"])
    assert sent == {"api_name": "get_payroll_run", "path_params": {"id": 30}}


# ── 2. Typed data between steps ───────────────────────────────────────────


def _payroll_plan():
    return {
        2: PlanStep(2, "list runs", "call_host_api", {"api_name": "list_payroll_runs"}),
        3: PlanStep(3, "latest run", "call_host_api", {"api_name": "get_payroll_run"}, depends_on=[2]),
    }


def test_path_id_is_declared_from_the_listing_dependency():
    by_id = _payroll_plan()
    declare_bindings(by_id[3], by_id, SURFACE)
    assert by_id[3].tool_args["bind"] == {"id": {"step": 2, "field": "id"}}


def test_a_binding_written_into_the_path_slot_is_a_declaration():
    """Seen live: the planner nested the bind spec under path_params.id."""
    steps = list(_payroll_plan().values())
    steps[1].tool_args = {
        "api_name": "get_payroll_run",
        "path_params": {"id": {"step": 2, "field": "id", "select": "latest"}},
    }
    _canonicalize_host_steps(steps, CATALOG)
    assert steps[1].tool_args == {
        "api_name": "get_payroll_run",
        "bind": {"id": {"step": 2, "field": "id", "select": "latest"}},
    }
    b = resolve_bindings(steps[1].tool_args, SURFACE, {2: RUNS}, {2: "list_payroll_runs"})
    assert b.status == "bound" and b.tool_args["path_params"] == {"id": 30}


def test_many_candidates_without_select_is_a_typed_choice():
    by_id = _payroll_plan()
    declare_bindings(by_id[3], by_id, SURFACE)
    b = resolve_bindings(by_id[3].tool_args, SURFACE, {2: RUNS}, {2: "list_payroll_runs"})
    assert b.status == "choice"
    assert b.key == "id" and b.from_step == 2
    assert [o["value"] for o in b.options] == [21, 30, 28]


def test_select_latest_uses_the_catalog_order_field():
    args = {"api_name": "get_payroll_run", "bind": {"id": {"step": 2, "field": "id", "select": "latest"}}}
    b = resolve_bindings(args, SURFACE, {2: RUNS}, {2: "list_payroll_runs"})
    assert b.status == "bound"
    assert b.tool_args["path_params"] == {"id": 30}


def test_one_candidate_binds_without_select():
    one = {"result": json.dumps({"results": [{"id": 30, "period_end": "2026-09-30"}]})}
    args = {"api_name": "get_payroll_run", "bind": {"id": {"step": 2, "field": "id"}}}
    b = resolve_bindings(args, SURFACE, {2: one}, {2: "list_payroll_runs"})
    assert b.status == "bound" and b.tool_args["path_params"] == {"id": 30}


def _loop_call(loop, step, prior_results=()):
    return loop._execute_step(
        step=step, dw=None, cw=None, ex=None, instance_id="t", conversation_id="c",
        user_message="", system_prompt="", conversation_history=None,
        instance_config=CFG, user_info=None, retrieval=None,
        progress_callback=None, stream_callback=None, dry_run=False,
        confirmation_token=None, step_contexts={}, prior_results=list(prior_results),
    )


@pytest.mark.asyncio
async def test_unbound_path_id_stops_as_missing_binding_before_the_host():
    loop = ReActLoop()
    loop._step_api_names = {2: "list_payroll_runs"}
    by_id = _payroll_plan()
    declare_bindings(by_id[3], by_id, SURFACE)
    prior = StepResult(step_id=2, intent="", executed=True, tool_output=RUNS)
    result = await _loop_call(loop, by_id[3], [prior])
    assert result.failure_class == MISSING_BINDING
    assert result.executed is False and result.paused is True
    assert result.confirmation_token
    assert result.choice["key"] == "id" and len(result.choice["options"]) == 3
    assert "get_payroll_run" not in (result.error or "")


# ── 3. Follow-ups go through the surface ──────────────────────────────────


def test_invented_followup_without_api_name_is_dropped():
    parent = PlanStep(4, "variance", None, {})
    args, _ = ReActLoop._admit_followup(
        "call_host_api", {"method": "GET", "endpoint": "/payroll/runs/latest"}, parent, CFG, [parent],
    )
    assert args is None


def test_followup_write_is_dropped():
    parent = PlanStep(2, "runs", "call_host_api", {"api_name": "list_payroll_runs"})
    args, _ = ReActLoop._admit_followup(
        "call_host_api", {"api_name": "commit_payroll_run"}, parent, CFG, [parent],
    )
    assert args is None


def test_followup_path_id_must_be_bindable_from_its_parent():
    lonely = PlanStep(4, "variance", None, {})
    assert ReActLoop._admit_followup(
        "call_host_api", {"api_name": "get_payroll_run"}, lonely, CFG, [lonely],
    )[0] is None
    parent = PlanStep(2, "runs", "call_host_api", {"api_name": "list_payroll_runs"})
    args, label = ReActLoop._admit_followup(
        "call_host_api", {"api_name": "get_payroll_run"}, parent, CFG, [parent],
    )
    assert args["bind"] == {"id": {"step": 2, "field": "id"}}
    assert label == "Payroll run details"


# ── 4. Hollow success ─────────────────────────────────────────────────────


def test_a_procedure_without_executable_steps_is_not_plannable():
    stub = SimpleNamespace(kind="procedure", body=json.dumps({"steps": [{"tool_name": None}]}))
    assert skill_has_effect(stub) is False
    plan = SimpleNamespace(kind="multi_step_plan", body=json.dumps({"steps": [{"tool_name": "call_host_api"}]}))
    assert skill_has_effect(plan) is True
    governed = SimpleNamespace(kind="procedure", body=json.dumps({"process_ref": "p.v1"}))
    assert skill_has_effect(governed) is True


def test_a_recipe_return_is_no_effect_not_completed():
    step = PlanStep(4, "variance", "invoke_skill", {"skill_name": "x"})
    result = StepResult(
        step_id=4, intent="", critic_verdict="pass", executed=True,
        tool_output={"executed": False, "result": {"kind": "procedure"}},
    )
    assert classify_step_failure(step, result, plan_source="llm_decompose") == NO_EFFECT
    assert result.error and result.critic_verdict == "veto"


# ── 5. Typed failures ─────────────────────────────────────────────────────


@pytest.mark.parametrize("error,expected", [
    (WRITE_HELD, BLOCKED_DEPENDENCY),
    ("Host API returned 400: Unknown dimension(s) ''", INVALID_ARGS),
    ("[timeout] exceeded timeout_ms=30000", TRANSIENT),
    ("Host API returned 503", TRANSIENT),
])
def test_failure_class(error, expected):
    step = PlanStep(0, "", "call_host_api", {})
    result = StepResult(step_id=0, intent="", critic_verdict="veto", error=error)
    assert classify_step_failure(step, result) == expected


def test_only_transient_is_retried_and_deterministic_is_not_replanned():
    assert is_retryable(TRANSIENT)
    for cls in (INVALID_ARGS, MISSING_BINDING, BLOCKED_DEPENDENCY, NO_EFFECT):
        assert not is_retryable(cls)
        assert not is_replannable(cls)


@pytest.mark.asyncio
async def test_a_failed_dependency_never_runs_its_dependent():
    loop = ReActLoop()
    loop._failed_read_ids = {0}
    step = PlanStep(5, "synthesize", None, {}, depends_on=[0, 2])
    result = await _loop_call(loop, step)
    assert result.executed is False
    assert result.failure_class == BLOCKED_DEPENDENCY


def test_confirm_writes_the_picked_path_value():
    from ai.plans_service import PlansService, PlanStepError

    saved = {}

    class _Step:
        def __init__(self):
            self.run_id = "run"
            self.step_index = 3
            self.confirmation_token = ""
            self.tool_args_json = {"api_name": "get_payroll_run", "bind": {"id": {"step": 2}}}
            self.critic_flags_json = {
                "failure_class": "missing_binding",
                "choice": {"key": "id", "options": [{"value": 30, "label": "30"}, {"value": 21, "label": "21"}]},
            }
            self.error = "pick"

        def save(self, update_fields=None):
            saved["args"] = self.tool_args_json
            saved["flags"] = self.critic_flags_json

    out = PlansService._apply_binding_choice(None, _Step(), {"id": 30})
    assert out["choice"] == {"id": 30}
    assert saved["args"]["path_params"] == {"id": 30}
    assert "bind" not in saved["args"]
    assert "failure_class" not in saved["flags"]
    with pytest.raises(PlanStepError):
        PlansService._apply_binding_choice(None, _Step(), {"id": 99})


def test_run_retry_reads_the_recorded_class():
    from ai.plans_service import RUN_RETRY_MAX, _step_failure_class

    assert RUN_RETRY_MAX == 1
    assert _step_failure_class(SimpleNamespace(critic_flags_json={"failure_class": "transient"})) == TRANSIENT
    assert _step_failure_class(SimpleNamespace(critic_flags_json=["legacy"])) == ""
