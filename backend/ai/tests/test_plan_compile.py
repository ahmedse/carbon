"""Catalog-first plan author. The DAG comes from returns, not from a model."""
from pathlib import Path

import yaml

from ai.engine.cognition.plan.compile import compile_catalog_plan
from ai.engine.cognition.plan.contract import apply_plan_contract, blocks_create

CATALOG = [
    {
        "name": "list_payroll_runs",
        "method": "GET",
        "path": "/payroll-runs/",
        "returns": ["id", "org_unit", "period_start", "period_end", "status"],
        "latest_by": "period_end",
        "parameters": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["draft", "computed", "validated", "committed", "failed"],
                },
            },
        },
    },
    {
        "name": "list_payslip_lines",
        "method": "GET",
        "path": "/payslip-lines/",
        "returns": ["id", "employee", "line_type", "amount", "payroll_run"],
    },
    {
        "name": "list_employees",
        "method": "GET",
        "path": "/employees/",
        "returns": ["id", "org_unit", "nationality", "position"],
    },
    {
        "name": "analyze_employees",
        "method": "GET",
        "path": "/people/analytics/",
        "label": "Headcount",
        "description": "Headcount and count by dimension. Not average or median.",
        "returns": ["label", "count", "pct", "total"],
        "parameters": {
            "type": "object",
            "required": ["dimension"],
            "properties": {
                "dimension": {
                    "type": "string",
                    "enum": ["org_unit", "nationality", "position", "is_active"],
                },
            },
        },
    },
    {
        "name": "analyze_committed_pay",
        "method": "GET",
        "path": "/payslip-lines/summary/",
        "label": "Committed pay structure",
        "description": "Committed-pay aggregate. Host computes label, headcount, "
                       "average, median, min, max, total.",
        "returns": [
            "label", "headcount", "average", "median", "min", "max", "total",
            "period_end", "dimension", "line_type", "status",
        ],
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["period_end", "dimension"],
            "properties": {
                "period_end": {"type": "string"},
                "dimension": {
                    "type": "string",
                    "enum": ["org_unit", "nationality", "position", "is_active"],
                },
                "line_type": {"type": "string", "enum": ["net", "gross"]},
            },
        },
    },
    {
        "name": "analyze_gosi_committed",
        "method": "GET",
        "path": "/payslip-lines/gosi-summary/",
        "label": "Committed GOSI",
        "description": "Committed GOSI totals. Host computes label, headcount, "
                       "average, median, min, max, total. Not a line_type on pay.",
        "returns": [
            "label", "headcount", "average", "median", "min", "max", "total",
            "period_end", "dimension", "line_type", "status",
        ],
        "parameters": {
            "type": "object",
            "required": ["period_end", "dimension"],
            "properties": {
                "period_end": {"type": "string"},
                "dimension": {
                    "type": "string",
                    "enum": ["org_unit", "nationality", "position", "is_active"],
                },
            },
        },
    },
]

BRIEF = (
    "Create a task to generate a salary distribution report with the following "
    "specifications: Dimensions: Salary distribution by organizational unit "
    "Salary distribution by nationality Salary distribution by job title / position "
    "Salary distribution by employment status. Metrics: Average salary per group "
    "Median salary per group Salary range (minimum and maximum) per group "
    "Headcount per group Total payroll cost per group. Output format: Excel "
    "workbook with separate sheets per dimension."
)


def _apis(plan) -> list[str]:
    return [
        str((s.tool_args or {}).get("api_name") or "")
        for s in plan.steps if s.tool_name == "call_host_api"
    ]


def test_compile_covers_measures_from_the_closed_aggregate():
    plan = compile_catalog_plan(BRIEF, CATALOG)
    assert plan is not None
    assert plan.source == "catalog_compile"
    apis = _apis(plan)
    assert apis.count("analyze_committed_pay") == 4
    assert "list_payroll_runs" in apis
    assert "list_payslip_lines" not in apis
    assert "list_employees" not in apis
    assert "analyze_employees" not in apis
    dims = {
        (s.tool_args or {}).get("dimension")
        or ((s.tool_args or {}).get("query_params") or {}).get("dimension")
        for s in plan.steps
        if (s.tool_args or {}).get("api_name") == "analyze_committed_pay"
    }
    assert dims == {"org_unit", "nationality", "position", "is_active"}
    export = next(s for s in plan.steps if s.tool_name == "export_document")
    columns = export.tool_args["columns"]
    assert {"average", "median", "min", "max", "headcount", "total"} <= set(columns)
    assert "label" in columns
    assert not {"dimension", "period_end", "status", "line_type"} & set(columns)
    assert export.tool_args["format"] == "xlsx"
    assert len([s for s in plan.steps if s.tool_name == "export_document"]) == 1


def test_compile_binds_period_from_the_listing_that_declares_it():
    plan = compile_catalog_plan(BRIEF, CATALOG)
    pay = next(
        s for s in plan.steps
        if (s.tool_args or {}).get("api_name") == "analyze_committed_pay"
    )
    bind = (pay.tool_args or {}).get("bind") or {}
    assert bind["period_end"]["field"] == "period_end"
    assert bind["period_end"]["select"] == "latest"
    listing = next(
        s for s in plan.steps
        if (s.tool_args or {}).get("api_name") == "list_payroll_runs"
    )
    assert (listing.tool_args or {}).get("status") == "committed"
    assert bind["period_end"]["step"] == listing.step_id


def test_compile_plan_passes_the_contract():
    plan = compile_catalog_plan(BRIEF, CATALOG)
    names = {e["name"] for e in CATALOG}
    findings = apply_plan_contract(
        plan.steps, api_catalog=CATALOG, catalog_names=names, utterance=BRIEF,
    )
    assert not any(f.blocks for f in findings)
    assert blocks_create(findings, plan.steps, CATALOG) is None
    assert not any((s.tool_args or {}).get("fills_gap") for s in plan.steps)


def test_compile_prefers_the_entry_whose_description_matches():
    brief = (
        "Committed GOSI totals by nationality. Include average, median, "
        "headcount, and total."
    )
    plan = compile_catalog_plan(brief, CATALOG)
    assert plan is not None
    apis = set(_apis(plan))
    assert "analyze_gosi_committed" in apis
    assert "analyze_committed_pay" not in apis


def test_compile_headcount_uses_the_count_aggregate():
    brief = "Headcount by organizational unit as an Excel workbook."
    plan = compile_catalog_plan(brief, CATALOG)
    assert plan is not None
    apis = _apis(plan)
    assert "analyze_employees" in apis
    assert "analyze_committed_pay" not in apis
    export = next(s for s in plan.steps if s.tool_name == "export_document")
    assert "count" in export.tool_args["columns"] or "total" in export.tool_args["columns"]


def test_compile_refuses_when_no_measure_is_named():
    assert compile_catalog_plan("escalate this to a person", CATALOG) is None
    assert compile_catalog_plan("export a board pack of p90", CATALOG) is None


def test_compile_widens_format_when_the_brief_names_two_files():
    plan = compile_catalog_plan(BRIEF + " Also a PDF executive report.", CATALOG)
    export = next(s for s in plan.steps if s.tool_name == "export_document")
    assert export.tool_args["format"] == "pack"


def test_compile_uses_the_nibras_catalog_on_the_live_brief():
    path = (
        Path(__file__).resolve().parents[1]
        / "engine" / "instances" / "nibras" / "instance.yaml"
    )
    catalog = list(yaml.safe_load(path.read_text(encoding="utf-8")).get("api_catalog") or [])
    plan = compile_catalog_plan(BRIEF, catalog)
    assert plan is not None
    apis = _apis(plan)
    assert apis.count("analyze_committed_pay") == 4
    assert "analyze_employees" not in apis
    assert "list_payslip_lines" not in apis
    export = next(s for s in plan.steps if s.tool_name == "export_document")
    cols = set(export.tool_args["columns"])
    assert {"average", "median", "min", "max", "headcount", "total"} <= cols
    assert not {"dimension", "period_end", "status", "line_type"} & cols
    findings = apply_plan_contract(
        plan.steps,
        api_catalog=catalog,
        catalog_names={str(e.get("name") or "") for e in catalog},
        utterance=BRIEF,
    )
    assert not any(f.blocks for f in findings)
