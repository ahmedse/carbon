"""ADR-0052 plan contract. One finding per invariant, plus the two briefs."""
import json

from ai.engine.cognition.plan.contract import (
    apply_plan_contract,
    catalog_mutation,
    declared_call_mismatch,
    evidence_blocked,
    guard_outcome,
)
from ai.engine.cognition.plan.loop import StepResult
from ai.engine.cognition.plan.planner import PlanStep

CATALOG = [
    {"name": "list_payroll_runs", "method": "GET", "path": "/payroll-runs/"},
    {
        "name": "validate_payroll_run",
        "method": "POST",
        "path": "/payroll-runs/{id}/validate/",
        "requires_confirmation": True,
    },
    {"name": "analyze_employees", "method": "GET", "path": "/people/analytics/",
     "parameters": {"type": "object", "required": ["dimension"],
                    "properties": {"dimension": {"enum": ["org_unit"]}}}},
]
NAMES = {e["name"] for e in CATALOG}


def test_i1_invented_api_becomes_a_gap():
    steps = [PlanStep(7, "escalate", "call_host_api", {"api_name": "escalate_to_finance"})]
    findings = apply_plan_contract(steps, api_catalog=CATALOG, catalog_names=NAMES)
    assert steps[0].tool_name is None
    assert steps[0].gap
    assert any(f.code == "gap" for f in findings)


def test_i2_mutation_comes_from_the_catalog():
    assert catalog_mutation("export_document", None) is True
    assert catalog_mutation("call_host_api", CATALOG[1]) is True
    assert catalog_mutation("call_host_api", CATALOG[0]) is False
    steps = [PlanStep(
        4, "pass critic", "call_host_api",
        {"api_name": "validate_payroll_run"}, is_mutation=False,
    )]
    apply_plan_contract(steps, api_catalog=CATALOG, catalog_names=NAMES)
    assert steps[0].is_mutation is True


def test_i3_a_failed_dependency_blocks_the_export():
    export = PlanStep(5, "board pack", "export_document", {}, depends_on=[3], is_mutation=True)
    failed = StepResult(step_id=3, intent="gosi", error="missing id", failure_class="missing_binding")
    finding = evidence_blocked(export, [failed])
    assert finding is not None and finding.code == "evidence"
    ok = StepResult(step_id=3, intent="gosi", executed=True, tool_output={"result": {}})
    assert evidence_blocked(export, [ok]) is None


def test_i4_both_branches_without_a_guard_block():
    steps = [
        PlanStep(2, "decide", None, {}),
        PlanStep(6, "export", "export_document", {"title": "Board"}, depends_on=[2], is_mutation=True),
        PlanStep(7, "escalate", None, {}, depends_on=[2], gap="escalate"),
    ]
    findings = apply_plan_contract(steps, api_catalog=CATALOG, catalog_names=NAMES)
    assert any(f.code == "branch" and f.blocks for f in findings)


def test_i4_exclusive_guards_allow_both_steps():
    steps = [
        PlanStep(2, "decide", None, {}),
        PlanStep(6, "export", "export_document", {"title": "Board"}, depends_on=[2], is_mutation=True,
                 guard={"step": 2, "field": "within_band", "value": True}),
        PlanStep(7, "escalate", None, {}, depends_on=[2], gap="escalate",
                 guard={"step": 2, "field": "within_band", "value": False}),
    ]
    findings = apply_plan_contract(steps, api_catalog=CATALOG, catalog_names=NAMES)
    assert not any(f.code == "branch" and f.blocks for f in findings)
    assert guard_outcome(steps[1], {2: {"within_band": True}}) == "run"
    assert guard_outcome(steps[2], {2: {"within_band": True}}) == "skip"
    assert guard_outcome(steps[1], {2: {}}) == "pause"


def test_i5_gap_is_not_an_invented_call():
    steps = [PlanStep(7, "escalate to a team", "call_host_api", {"action": "escalate_to_finance"})]
    apply_plan_contract(steps, api_catalog=CATALOG, catalog_names=NAMES)
    assert steps[0].tool_name is None
    assert "escalate_to_finance" not in json.dumps(steps[0].tool_args)


def test_i6_executed_api_must_match_the_declaration():
    declared = {"api_name": "validate_payroll_run"}
    other = {"function": {"name": "call_host_api", "arguments": json.dumps({"api_name": "list_payroll_runs"})}}
    same = {"function": {"name": "call_host_api", "arguments": json.dumps(declared)}}
    assert declared_call_mismatch("call_host_api", declared, other) == "list_payroll_runs"
    assert declared_call_mismatch("call_host_api", declared, same) == ""


def test_workforce_briefing_shape_has_one_effect():
    """0bd5072d shape: reads, then one export. No second branch."""
    steps = [
        PlanStep(0, "headcount by org unit", "call_host_api",
                 {"api_name": "analyze_employees", "dimension": "org_unit"}),
        PlanStep(1, "list runs", "call_host_api", {"api_name": "list_payroll_runs"}),
        PlanStep(2, "summarize", None, {}, depends_on=[0, 1]),
        PlanStep(3, "export the report", "export_document", {"title": "Weekly"}, depends_on=[2]),
    ]
    findings = apply_plan_contract(steps, api_catalog=CATALOG, catalog_names=NAMES)
    assert not any(f.blocks for f in findings)
    assert steps[3].is_mutation is True
    assert steps[0].is_mutation is False


def test_conditional_brief_keeps_one_branch():
    """aec8f39a expected shape: a guard, and the other branch is a gap with no export beside it."""
    within = [
        PlanStep(0, "variance read", "call_host_api", {"api_name": "list_payroll_runs"}),
        PlanStep(1, "band", None, {}, depends_on=[0]),
        PlanStep(2, "read lines", "call_host_api", {"api_name": "list_payroll_runs"}, depends_on=[1]),
        PlanStep(3, "board pack", "export_document", {"title": "Board"}, depends_on=[2],
                 guard={"step": 1, "field": "within_band", "value": True}),
    ]
    over = [
        PlanStep(0, "variance read", "call_host_api", {"api_name": "list_payroll_runs"}),
        PlanStep(1, "band", None, {}, depends_on=[0]),
        PlanStep(2, "escalate", None, {}, depends_on=[1], gap="hand off to a person",
                 guard={"step": 1, "field": "within_band", "value": False}),
    ]
    assert not any(f.blocks for f in apply_plan_contract(within, api_catalog=CATALOG, catalog_names=NAMES))
    assert over[2].tool_name is None
    assert not any(
        s.tool_name == "export_document" for s in over
    )
    assert not any(f.blocks for f in apply_plan_contract(over, api_catalog=CATALOG, catalog_names=NAMES))


def test_i1_invented_api_blocks_resume():
    steps = [PlanStep(7, "escalate", "call_host_api", {"api_name": "escalate_to_finance"})]
    findings = apply_plan_contract(steps, api_catalog=CATALOG, catalog_names=NAMES)
    blocked = [f for f in findings if f.blocks]
    assert blocked and blocked[0].code == "gap"
    assert steps[0].tool_name is None
    assert "not a host API" not in blocked[0].detail


def test_i3_card_lists_dependency_status():
    from ai.engine.cognition.plan.contract import evidence_rows

    green = evidence_rows([3], {3: {"status": "completed", "failure_class": ""}})
    assert green[0]["ok"] is True
    red = evidence_rows([3], {3: {"status": "failed", "failure_class": "missing_binding"}})
    assert red[0]["ok"] is False


def test_output_check_fails_an_error_inside_a_success_envelope():
    from ai.engine.cognition.plan.loop import _output_check

    step = PlanStep(3, "gosi read", "call_host_api", {"api_name": "list_payroll_runs"})
    result = StepResult(step_id=3, intent="gosi read", executed=True,
                        tool_output={"result": json.dumps({"status": 404, "detail": "no id"})})
    _output_check(step, result)
    assert result.error and result.failure_class == "permanent"
    bad = StepResult(step_id=3, intent="x", executed=True, tool_output={"result": {"status": 422}})
    _output_check(step, bad)
    assert bad.failure_class == "invalid_args"
    ok = StepResult(step_id=3, intent="x", executed=True,
                    tool_output={"result": {"status": "COMPUTED", "rows": []}})
    _output_check(step, ok)
    assert not ok.error


def test_review_step_needs_a_typed_verdict():
    from ai.engine.cognition.plan.loop import _output_check

    step = PlanStep(4, "pass critic", None, {}, depends_on=[3], agent_role="critic")
    silent = StepResult(step_id=4, intent="review", executed=True, draft_text="Looks fine.")
    _output_check(step, silent)
    assert silent.failure_class == "no_effect"
    fail = StepResult(step_id=4, intent="review", executed=True, draft_text=(
        'Checked.\n{"verdict": "fail", "findings": [{"code": "empty", "detail": "step 3 has no rows"}]}'
    ))
    _output_check(step, fail)
    assert fail.failure_class == "permanent" and "step 3 has no rows" in fail.error
    ok = StepResult(step_id=4, intent="review", executed=True,
                    draft_text='Fine.\n{"verdict": "pass", "findings": []}')
    _output_check(step, ok)
    assert not ok.error


def test_review_step_cannot_call_a_tool():
    steps = [
        PlanStep(3, "read", "call_host_api", {"api_name": "list_payroll_runs"}),
        PlanStep(4, "pass critic", "call_host_api", {"api_name": "validate_payroll_run"},
                 depends_on=[3], agent_role="critic"),
    ]
    findings = apply_plan_contract(steps, api_catalog=CATALOG, catalog_names=NAMES)
    assert any(f.code == "review" and f.blocks for f in findings)


def test_unresolved_guard_asks_a_typed_choice():
    from ai.engine.cognition.plan.contract import guard_choice

    step = PlanStep(6, "export", "export_document", {"title": "B"},
                    guard={"step": 1, "field": "within_band", "value": True})
    choice = guard_choice(step)
    assert choice["kind"] == "guard" and choice["step"] == 1
    assert [o["value"] for o in choice["options"]] == [True, False]
    assert guard_outcome(step, {1: {"guard_values": {"within_band": False}}}) == "skip"


def test_coverage_counts_what_a_step_does_not_only_its_words():
    from types import SimpleNamespace

    from ai.flight_director import contract_gate

    plan = SimpleNamespace(steps=[
        PlanStep(0, "headcount", "call_host_api", {"api_name": "analyze_employees"}),
        PlanStep(1, "board pack", "export_document", {"title": "Board"}, depends_on=[0]),
    ])
    brief = "Build the monthly report and export it for the board."
    assert not [f for f in contract_gate(plan, brief)["findings"] if f["blocks"]]
    summary = SimpleNamespace(steps=[
        PlanStep(0, "headcount", "call_host_api", {"api_name": "analyze_employees"}),
        PlanStep(1, "summarize", None, {}, depends_on=[0]),
    ])
    assert not [f for f in contract_gate(summary, "Give me a short report.")["findings"] if f["blocks"]]
    reads_only = SimpleNamespace(steps=[
        PlanStep(0, "headcount", "call_host_api", {"api_name": "analyze_employees"}),
    ])
    missing = contract_gate(reads_only, "Export the headcount.")["findings"]
    assert [f["noun"] for f in missing if f["blocks"]] == ["export"]
    quoted = contract_gate(plan, "Build the 'Q3_pack' report.")["findings"]
    assert all(not f["blocks"] for f in quoted)


def test_golden_bank_both_briefs():
    import yaml
    from pathlib import Path

    bank = yaml.safe_load(
        (Path(__file__).resolve().parents[1] / "eval" / "plan_contract_bank.yaml").read_text()
    )
    for case in bank["cases"]:
        steps = [
            PlanStep(
                s["step_id"], s["intent"], s.get("tool_name"), s.get("tool_args") or {},
                depends_on=s.get("depends_on") or [],
                is_mutation=s.get("is_mutation", False),
                gap=s.get("gap"),
                guard=s.get("guard"),
            )
            for s in case["steps"]
        ]
        findings = apply_plan_contract(steps, api_catalog=CATALOG, catalog_names=NAMES)
        blocked = [f.code for f in findings if f.blocks]
        assert blocked == case["blocking"], case["id"]
