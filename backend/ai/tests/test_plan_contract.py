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
    {"name": "list_payroll_runs", "method": "GET", "path": "/payroll-runs/",
     "returns": ["id", "status"]},
    {
        "name": "validate_payroll_run",
        "method": "POST",
        "path": "/payroll-runs/{id}/validate/",
        "requires_confirmation": True,
    },
    {"name": "analyze_employees", "method": "GET", "path": "/people/analytics/",
     "parameters": {"type": "object", "required": ["dimension"],
                    "properties": {"dimension": {"enum": ["org_unit"]}}},
     "returns": ["headcount"]},
    {"name": "list_payslip_lines", "method": "GET", "path": "/payslip-lines/",
     "returns": ["id", "employee", "line_type", "amount", "payroll_run"]},
    {"name": "list_employees", "method": "GET", "path": "/employees/"},
    {
        "name": "analyze_committed_pay",
        "method": "GET",
        "path": "/payslip-lines/summary/",
        "returns": [
            "label", "headcount", "average", "median", "min", "max", "total",
            "period_end", "dimension", "line_type", "status",
        ],
    },
    {
        "name": "analyze_kuwaitization",
        "method": "GET",
        "path": "/people/compliance/kuwaitization/",
        "returns": [
            "label", "contract_no", "required", "actual", "deficit",
            "fill_rate_pct", "status",
        ],
    },
    {
        "name": "analyze_leave_utilization",
        "method": "GET",
        "path": "/leave-entitlements/summary/",
        "returns": [
            "label", "headcount", "entitled_days", "used_days",
            "remaining_days", "utilization_pct",
        ],
    },
    {
        "name": "analyze_loan_book",
        "method": "GET",
        "path": "/loans/summary/",
        "returns": ["label", "count", "principal_total", "remaining_total"],
    },
    {
        "name": "analyze_gosi_committed",
        "method": "GET",
        "path": "/payslip-lines/gosi-summary/",
        "returns": [
            "label", "headcount", "average", "median", "min", "max", "total",
            "period_end", "dimension", "line_type", "status",
        ],
    },
    {
        "name": "analyze_cert_expiry",
        "method": "GET",
        "path": "/certifications/summary/",
        "returns": ["label", "expired", "expiring", "current"],
    },
    {
        "name": "analyze_leave_presence",
        "method": "GET",
        "path": "/leave-records/presence/",
        "returns": ["label", "on_leave_count", "days"],
    },
    {
        "name": "list_leave_entitlements",
        "method": "GET",
        "path": "/leave-entitlements/",
        "returns": [
            "id", "employee", "employee_no", "employee_name", "leave_type",
            "entitled_days", "used_days", "carried_forward",
        ],
    },
    {
        "name": "list_loans",
        "method": "GET",
        "path": "/loans/",
        "returns": [
            "id", "employee", "employee_no", "employee_name", "loan_type",
            "principal", "interest_rate", "term_months", "start_date", "status",
        ],
    },
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
        PlanStep(6, "export", "export_document", {"title": "Board", "columns": ["id", "status"]}, depends_on=[2], is_mutation=True),
        PlanStep(7, "escalate", None, {}, depends_on=[2], gap="escalate"),
    ]
    findings = apply_plan_contract(steps, api_catalog=CATALOG, catalog_names=NAMES)
    assert any(f.code == "branch" and f.blocks for f in findings)


def test_sibling_exports_are_one_file_write():
    """xlsx + pdf from the same reads is one effect (format set), not I4."""
    from ai.engine.cognition.plan.contract import blocks_create
    from ai.engine.cognition.turn.plan_proposal import proposal_payload

    steps = [
        PlanStep(0, "latest run", "call_host_api",
                 {"api_name": "list_payroll_runs", "status": "committed"}),
        PlanStep(1, "pay by org", "call_host_api",
                 {"api_name": "analyze_committed_pay", "dimension": "org_unit"},
                 depends_on=[0]),
        PlanStep(2, "pay by nationality", "call_host_api",
                 {"api_name": "analyze_committed_pay", "dimension": "nationality"},
                 depends_on=[0]),
        PlanStep(3, "workbook", "export_document",
                 {"title": "Salary Distribution Report", "format": "xlsx"},
                 depends_on=[1, 2], is_mutation=True),
        PlanStep(4, "executive brief", "export_document",
                 {"title": "Executive Summary", "format": "pdf"},
                 depends_on=[1, 2], is_mutation=True),
    ]
    findings = apply_plan_contract(steps, api_catalog=CATALOG, catalog_names=NAMES)
    exports = [s for s in steps if s.tool_name == "export_document"]
    assert len(exports) == 1
    assert exports[0].tool_args.get("format") == "pack"
    assert "average" in (exports[0].tool_args or {}).get("columns", [])
    assert not any(f.code == "branch" and f.blocks for f in findings)
    assert blocks_create(findings, steps, CATALOG) is None
    payload = proposal_payload(
        {"steps": [
            {"step_id": s.step_id, "intent": s.intent, "tool_name": s.tool_name,
             "gap": s.gap, "tool_args": s.tool_args}
            for s in steps
        ]},
        findings=findings,
    )
    assert payload["blocks_create"] is False


def test_i4_unrepaired_host_writes_refuse_create():
    from ai.engine.cognition.plan.contract import blocks_create

    steps = [
        PlanStep(0, "validate first", "call_host_api",
                 {"api_name": "validate_payroll_run"}),
        PlanStep(1, "validate second", "call_host_api",
                 {"api_name": "validate_payroll_run"}),
    ]
    findings = apply_plan_contract(steps, api_catalog=CATALOG, catalog_names=NAMES)
    assert any(f.code == "branch" and f.blocks for f in findings)
    assert blocks_create(findings, steps, CATALOG) is not None


def test_i4_exclusive_guards_allow_both_steps():
    steps = [
        PlanStep(2, "decide", None, {}),
        PlanStep(6, "export", "export_document", {"title": "Board", "columns": ["id", "status"]}, depends_on=[2], is_mutation=True,
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
        PlanStep(2, "summarize", None, {"produces": ["headcount"]}, depends_on=[0, 1]),
        PlanStep(3, "export the report", "export_document", {"title": "Weekly", "columns": ["headcount"]}, depends_on=[2]),
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
        PlanStep(3, "board pack", "export_document", {"title": "Board", "columns": ["id", "status"]}, depends_on=[2],
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
        PlanStep(1, "board pack", "export_document", {"title": "Board", "columns": ["headcount"]}, depends_on=[0]),
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


def test_contract_does_not_invent_an_export_from_wording():
    steps = [PlanStep(0, "headcount", "call_host_api", {"api_name": "analyze_employees", "dimension": "org_unit"})]
    apply_plan_contract(
        steps, api_catalog=CATALOG, catalog_names=NAMES,
        utterance="Export the salary distribution as Excel",
    )
    assert all(s.tool_name != "export_document" for s in steps)


def test_unnamed_export_after_a_read_is_still_a_gap():
    """Live hole: payslip lines return amount, so an unnamed xlsx looked covered."""
    steps = [
        PlanStep(0, "runs", "call_host_api", {"api_name": "list_payroll_runs"}),
        PlanStep(1, "lines", "call_host_api", {"api_name": "list_payslip_lines"}, depends_on=[0]),
        PlanStep(2, "compute", None, {}, depends_on=[1]),
        PlanStep(3, "export", "export_document", {"title": "Report", "format": "xlsx"}, depends_on=[2]),
    ]
    findings = apply_plan_contract(steps, api_catalog=CATALOG, catalog_names=NAMES)
    assert any(f.code == "output_fit" and f.blocks for f in findings)
    assert steps[3].tool_name is None


def test_unnamed_export_binds_closed_aggregate_already_on_the_plan():
    """The live 10-step draft: GET is present, export omitted columns, contract
    must name them from returns — not invent a correspondence request."""
    from ai.engine.cognition.plan.contract import blocks_create
    from ai.engine.cognition.turn.plan_proposal import proposal_payload

    catalog = CATALOG + [{
        "name": "file_a_request",
        "method": "POST",
        "path": "/requests/",
        "kind": "request",
        "label": "File a request",
        "default_body": {"corr_type": "internal_memo"},
        "requires_confirmation": True,
    }]
    names = {e["name"] for e in catalog}
    steps = [
        PlanStep(0, "latest run", "call_host_api",
                 {"api_name": "list_payroll_runs", "status": "committed"}),
        PlanStep(1, "roster", "call_host_api",
                 {"api_name": "list_employees"}, depends_on=[0]),
        PlanStep(2, "pay by org", "call_host_api",
                 {"api_name": "analyze_committed_pay", "dimension": "org_unit"},
                 depends_on=[0]),
        PlanStep(3, "pay by nationality", "call_host_api",
                 {"api_name": "analyze_committed_pay", "dimension": "nationality"},
                 depends_on=[0]),
        PlanStep(4, "pay by position", "call_host_api",
                 {"api_name": "analyze_committed_pay", "dimension": "position"},
                 depends_on=[0]),
        PlanStep(5, "pay by status", "call_host_api",
                 {"api_name": "analyze_committed_pay", "dimension": "is_active"},
                 depends_on=[0]),
        PlanStep(6, "headcount", "call_host_api",
                 {"api_name": "analyze_employees", "dimension": "org_unit"},
                 depends_on=[1]),
        PlanStep(7, "synthesize", None, {}, depends_on=[2, 3, 4, 5, 6]),
        PlanStep(8, "export", "export_document",
                 {"title": "Salary Distribution Report", "format": "xlsx"},
                 depends_on=[7]),
    ]
    findings = apply_plan_contract(
        steps, api_catalog=catalog, catalog_names=names,
        utterance="salary distribution report",
    )
    export = next(s for s in steps if s.tool_name == "export_document")
    assert "average" in (export.tool_args or {}).get("columns", [])
    assert "median" in (export.tool_args or {}).get("columns", [])
    assert set(export.depends_on) <= {2, 3, 4, 5, 6}
    assert 7 not in {s.step_id for s in steps}
    assert not any((s.tool_args or {}).get("fills_gap") for s in steps)
    assert not any(f.code == "output_fit" and f.blocks for f in findings)
    assert blocks_create(findings, steps, catalog) is None
    payload = proposal_payload(
        {"steps": [
            {"step_id": s.step_id, "intent": s.intent, "tool_name": s.tool_name,
             "gap": s.gap, "tool_args": s.tool_args}
            for s in steps
        ]},
        findings=findings,
    )
    assert payload["blocks_create"] is False
    assert not any(s["blocked"] and s["tool"] == "export_document" for s in payload["steps"])


def test_unnamed_export_is_a_gap_when_nothing_declares_fields():
    steps = [
        PlanStep(0, "validate", "call_host_api", {"api_name": "validate_payroll_run"}),
        PlanStep(1, "export", "export_document", {"title": "Board"}, depends_on=[0]),
    ]
    findings = apply_plan_contract(steps, api_catalog=CATALOG, catalog_names=NAMES)
    assert any(f.code == "output_fit" and f.blocks for f in findings)
    assert steps[1].tool_name is None


def test_output_fit_drops_an_export_the_catalog_cannot_produce():
    steps = [
        PlanStep(0, "headcount", "call_host_api",
                 {"api_name": "analyze_employees", "dimension": "org_unit"}),
        PlanStep(1, "export", "export_document",
                 {"title": "Report", "columns": ["average", "median"]}, depends_on=[0]),
    ]
    findings = apply_plan_contract(steps, api_catalog=CATALOG, catalog_names=NAMES)
    assert any(f.code == "output_fit" and f.blocks for f in findings)
    assert steps[1].tool_name is None
    assert steps[1].gap


def test_output_fit_keeps_an_export_whose_columns_are_declared():
    steps = [
        PlanStep(0, "headcount", "call_host_api",
                 {"api_name": "analyze_employees", "dimension": "org_unit"}),
        PlanStep(1, "export", "export_document",
                 {"title": "Report", "columns": ["headcount"]}, depends_on=[0]),
    ]
    findings = apply_plan_contract(steps, api_catalog=CATALOG, catalog_names=NAMES)
    assert not any(f.code == "output_fit" for f in findings)
    assert steps[1].tool_name == "export_document"


def test_output_fit_covers_declared_pay_structure_columns():
    steps = [
        PlanStep(0, "pay structure", "call_host_api",
                 {"api_name": "analyze_committed_pay", "dimension": "org_unit"}),
        PlanStep(1, "export", "export_document",
                 {"title": "Report", "columns": ["average", "median"]}, depends_on=[0]),
    ]
    findings = apply_plan_contract(steps, api_catalog=CATALOG, catalog_names=NAMES)
    assert not any(f.code == "output_fit" for f in findings)
    assert steps[1].tool_name == "export_document"
    missing = [
        PlanStep(0, "pay structure", "call_host_api",
                 {"api_name": "analyze_committed_pay", "dimension": "org_unit"}),
        PlanStep(1, "export", "export_document",
                 {"title": "Report", "columns": ["p90"]}, depends_on=[0]),
    ]
    blocked = apply_plan_contract(missing, api_catalog=CATALOG, catalog_names=NAMES)
    assert any(f.code == "output_fit" and f.blocks for f in blocked)
    assert missing[1].tool_name is None


def test_output_fit_covers_declared_kuwaitization_columns():
    steps = [
        PlanStep(0, "quota", "call_host_api",
                 {"api_name": "analyze_kuwaitization"}),
        PlanStep(1, "export", "export_document",
                 {"title": "Report", "columns": ["required", "actual"]}, depends_on=[0]),
    ]
    findings = apply_plan_contract(steps, api_catalog=CATALOG, catalog_names=NAMES)
    assert not any(f.code == "output_fit" for f in findings)
    missing = [
        PlanStep(0, "quota", "call_host_api",
                 {"api_name": "analyze_kuwaitization"}),
        PlanStep(1, "export", "export_document",
                 {"title": "Report", "columns": ["p90"]}, depends_on=[0]),
    ]
    blocked = apply_plan_contract(missing, api_catalog=CATALOG, catalog_names=NAMES)
    assert any(f.code == "output_fit" and f.blocks for f in blocked)


def test_output_fit_blocks_hop_columns_lists_do_not_declare():
    hops = [
        ("list_leave_entitlements", ["utilization_pct"]),
        ("list_loans", ["remaining_balance"]),
    ]
    for api, cols in hops:
        steps = [
            PlanStep(0, api, "call_host_api", {"api_name": api}),
            PlanStep(1, "export", "export_document",
                     {"title": "Report", "columns": cols}, depends_on=[0]),
        ]
        findings = apply_plan_contract(steps, api_catalog=CATALOG, catalog_names=NAMES)
        assert any(f.code == "output_fit" and f.blocks for f in findings), api


def test_output_fit_covers_items_3_to_7_columns():
    declared = [
        ("analyze_leave_utilization", ["entitled_days", "used_days"]),
        ("analyze_loan_book", ["principal_total", "remaining_total"]),
        ("analyze_gosi_committed", ["average", "total"]),
        ("analyze_cert_expiry", ["expired", "expiring"]),
        ("analyze_leave_presence", ["on_leave_count", "days"]),
    ]
    for api, cols in declared:
        steps = [
            PlanStep(0, api, "call_host_api", {"api_name": api}),
            PlanStep(1, "export", "export_document",
                     {"title": "Report", "columns": cols}, depends_on=[0]),
        ]
        findings = apply_plan_contract(steps, api_catalog=CATALOG, catalog_names=NAMES)
        assert not any(f.code == "output_fit" for f in findings), api
        missing = [
            PlanStep(0, api, "call_host_api", {"api_name": api}),
            PlanStep(1, "export", "export_document",
                     {"title": "Report", "columns": ["p90"]}, depends_on=[0]),
        ]
        blocked = apply_plan_contract(missing, api_catalog=CATALOG, catalog_names=NAMES)
        assert any(f.code == "output_fit" and f.blocks for f in blocked), api


def test_proposal_shows_the_output_fit_block():
    from ai.engine.cognition.turn.plan_proposal import proposal_payload

    steps = [
        PlanStep(0, "headcount", "call_host_api", {"api_name": "analyze_employees"}),
        PlanStep(1, "export", "export_document",
                 {"title": "Report", "columns": ["average"]}, depends_on=[0]),
    ]
    findings = apply_plan_contract(steps, api_catalog=CATALOG, catalog_names=NAMES)
    payload = proposal_payload(
        {"steps": [
            {"step_id": 0, "intent": "headcount", "tool_name": "call_host_api"},
            {"step_id": 1, "intent": "export", "tool_name": None, "gap": "declared output"},
        ], "source": "llm_decompose"},
        findings=findings,
    )
    blocked = [s for s in payload["steps"] if s["blocked"]]
    assert blocked and blocked[-1]["findings"][0]["code"] == "output_fit"
    assert payload["blocks_create"] is True
    assert "declares" in blocked[-1]["reason"]


def test_tool_less_hop_that_feeds_an_export_is_a_gap():
    steps = [
        PlanStep(0, "lines", "call_host_api", {"api_name": "list_payslip_lines"}),
        PlanStep(1, "compute groups", None, {}, depends_on=[0]),
        PlanStep(2, "export", "export_document",
                 {"title": "Report", "columns": ["amount"]}, depends_on=[1]),
    ]
    findings = apply_plan_contract(steps, api_catalog=CATALOG, catalog_names=NAMES)
    assert any(f.code == "output_fit" and f.step_id == 1 for f in findings)


def test_blocks_create_is_output_fit_not_a_handoff_gap():
    from ai.engine.cognition.plan.contract import Finding, blocks_create

    assert blocks_create([Finding("gap", 7, "hand off", blocks=False)]) is None
    hit = blocks_create([Finding("output_fit", 8, "This export does not name the fields it will contain.")])
    assert hit is not None and hit.code == "output_fit"


def test_request_write_unblocks_create():
    """A catalog request write is the remaining effect when output-fit fails."""
    from ai.engine.cognition.plan.contract import blocks_create
    from ai.engine.cognition.turn.plan_proposal import proposal_payload

    catalog = CATALOG + [{
        "name": "file_a_request",
        "method": "POST",
        "path": "/requests/",
        "kind": "request",
        "label": "File a request",
        "default_body": {"corr_type": "internal_memo"},
        "requires_confirmation": True,
    }]
    names = {e["name"] for e in catalog}
    steps = [
        PlanStep(0, "headcount", "call_host_api",
                 {"api_name": "analyze_employees", "dimension": "org_unit"}),
        PlanStep(1, "export", "export_document",
                 {"title": "Report", "columns": ["average", "median"]}, depends_on=[0]),
    ]
    findings = apply_plan_contract(
        steps, api_catalog=catalog, catalog_names=names,
        utterance="Board pack with average and median",
    )
    assert steps[1].tool_name is None
    assert steps[-1].tool_name == "call_host_api"
    assert steps[-1].tool_args["api_name"] == "file_a_request"
    assert steps[-1].tool_args["fills_gap"] is True
    assert steps[-1].tool_args["payload"]["brief"]
    assert blocks_create(findings, steps, catalog) is None
    assert not any(f.code == "branch" and f.blocks for f in findings)
    payload = proposal_payload(
        {"steps": [
            {"step_id": s.step_id, "intent": s.intent, "tool_name": s.tool_name,
             "gap": s.gap, "tool_args": s.tool_args}
            for s in steps
        ]},
        findings=findings,
    )
    assert payload["blocks_create"] is False
    again = apply_plan_contract(
        steps, api_catalog=catalog, catalog_names=names,
        utterance="Board pack with average and median",
    )
    assert sum(1 for s in steps if (s.tool_args or {}).get("api_name") == "file_a_request") == 1
    assert steps[-1].tool_args.get("fills_gap") is True
    assert (steps[-1].tool_args.get("body") or {}).get("title")
    assert "fills_gap" not in (steps[-1].tool_args.get("body") or {})
    assert blocks_create(again, steps, catalog) is None


def test_host_args_keeps_fills_gap_off_the_body():
    from ai.engine.cognition.turn.capability import CapabilitySurface

    surface = CapabilitySurface(entries=[{
        "name": "file_a_request",
        "method": "POST",
        "path": "/requests/",
        "kind": "request",
        "parameters": {"type": "object", "properties": {
            "title": {"type": "string"},
        }},
    }])
    args = surface.host_args("file_a_request", {
        "title": "Need a field", "fills_gap": True,
    })
    assert args["fills_gap"] is True
    assert args["body"]["title"] == "Need a field"
    assert "fills_gap" not in args["body"]


def test_output_fit_still_blocks_when_no_request_entry():
    steps = [
        PlanStep(0, "headcount", "call_host_api",
                 {"api_name": "analyze_employees", "dimension": "org_unit"}),
        PlanStep(1, "export", "export_document",
                 {"title": "Report", "columns": ["average"]}, depends_on=[0]),
    ]
    findings = apply_plan_contract(steps, api_catalog=CATALOG, catalog_names=NAMES)
    assert any(s.tool_name == "call_host_api" and (s.tool_args or {}).get("fills_gap") for s in steps) is False
    from ai.engine.cognition.plan.contract import blocks_create
    assert blocks_create(findings, steps, CATALOG) is not None


def test_eight_step_propose_refuses_create():
    from ai.engine.cognition.turn.plan_proposal import proposal_payload

    steps = [
        PlanStep(1, "run", "call_host_api", {"api_name": "list_payroll_runs"}),
        PlanStep(2, "people", "call_host_api", {"api_name": "list_employees"}, depends_on=[1]),
        PlanStep(3, "lines", "call_host_api", {"api_name": "list_payslip_lines"}, depends_on=[1]),
        PlanStep(4, "by org", None, {}, depends_on=[2, 3]),
        PlanStep(5, "by nationality", None, {}, depends_on=[2, 3]),
        PlanStep(6, "by position", None, {}, depends_on=[2, 3]),
        PlanStep(7, "by status", None, {}, depends_on=[2, 3]),
        PlanStep(8, "export", "export_document",
                 {"title": "Salary Distribution Report", "format": "xlsx"},
                 depends_on=[4, 5, 6, 7]),
    ]
    findings = apply_plan_contract(steps, api_catalog=CATALOG, catalog_names=NAMES)
    payload = proposal_payload(
        {"steps": [
            {"step_id": s.step_id, "intent": s.intent, "tool_name": s.tool_name, "gap": s.gap}
            for s in steps
        ]},
        findings=findings,
    )
    assert payload["blocks_create"] is True
    blocked = [s for s in payload["steps"] if s["blocked"]]
    assert {s["step_id"] for s in blocked} == {4, 5, 6, 7, 8}
    assert all(s["reason"] and s["reason"] != "declared output" for s in blocked)


def test_query_bind_uses_the_same_dialect_as_path():
    from ai.engine.cognition.plan.bindings import resolve_bindings
    from ai.engine.cognition.turn.capability import CapabilitySurface

    surface = CapabilitySurface(entries=[{
        "name": "list_lines",
        "method": "GET",
        "path": "/lines/",
        "parameters": {"type": "object", "properties": {"run_id": {"type": "string"}}},
    }])
    args = surface.host_args("list_lines", {
        "run_id": {"step": 0, "field": "id", "select": "latest"},
    })
    assert args["bind"]["run_id"]["step"] == 0
    assert "run_id" not in (args.get("query_params") or {})
    bound = resolve_bindings(args, surface, {0: [{"id": 9}]}, {0: "list_runs"})
    assert bound.status == "bound"
    assert bound.tool_args["query_params"]["run_id"] == 9
