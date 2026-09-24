"""Seed specialized Pulse agents + multi-step templates with file deliverables.

Creates domain agents (payroll / GOSI / compliance / workforce / finance packager),
wires handoffs from the orchestrator, promotes PlanTemplates for Nibras/GOFSCO
(board pack, leave coverage, loan risk, attendance backlog, Field Ops slice)
that end in ``export_document`` (docx / xlsx / pdf / png pack), and optionally
materializes a completed demo Run with real downloadable artifacts.

Host steps use ``call_host_api(api_name=…)`` from the Nibras catalog — not
path hardcoding and not intent-from-text.

Usage:
    python manage.py seed_complex_agent_demos
    python manage.py seed_complex_agent_demos --user ahmed
    python manage.py seed_complex_agent_demos --user ahmed --with-demo-run
    python manage.py seed_complex_agent_demos --reset-templates
"""

from __future__ import annotations

import json
import logging

from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils.timezone import now

from ai.catalog_service import CatalogService
from ai.engine.agent.registry import AgentRegistry
from ai.engine.core.database import get_session_factory
from ai.instance_registry import resolve_instance_id
from ai.models.core import PlanTemplate, Run, RunStep, generate_uuid
from ai.plans_service import (
    PLAN_INSTANCE_ID,
    PlansService,
    STATUS_COMPLETED,
    STEP_COMPLETED,
    STEP_SKIPPED,
    set_current_plan_run,
)
from ai.plugins.export_document import ExportDocument

logger = logging.getLogger("carbon.ai.seed_complex_agent_demos")

# Host-call resilience (W-4) — demos declare retry; driver enforces when live.
_HOST_RETRY = {"max_attempts": 3, "backoff_ms": 400, "on": ["timeout", "transient"]}


def build_payroll_board_pack_plan_json() -> dict:
    """Branched + resilient payroll board-pack plan (ADR-0034 workflow_graph).

    Flow::

        fetch → variance → {choice}
            ├─ guard: variance_pct <= 2.0 → summarize → critic → export
            └─ default: escalate Finance (human) → block export

        critic.catch → observe_repair → export | fail (no silent pack)

    Linear ``steps`` remain for RunStep materialization; ``workflow_graph``
    drives the DAG (choice / catch / retry) on the Run surface.
    """
    export_args = {
        "format": "pack",
        "title": "October Payroll Variance Board Pack",
        "content": (
            "## Executive summary\n"
            "October payroll closed within tolerance after variance review.\n\n"
            "### Branch taken\n"
            "- Variance **1.8%** ≤ 2.0% band → continue (escalate path skipped)\n\n"
            "### GOSI Exposure\n"
            "- **Total GOSI Exposure**: KWD 184,220\n"
            "- Employer share within policy band\n\n"
            "### Outstanding Loans\n"
            "- 42 active loans · KWD 312,400 outstanding\n\n"
            "### Compliance Risk Flags\n"
            "- 2 late enrollment cases — HR to close by month-end\n"
            "- Critic passed; export allowed only after review\n"
        ),
        "table": {
            "headers": ["Metric", "Value"],
            "rows": [
                ["Headcount", "529"],
                ["Payroll total (KWD)", "1,204,550"],
                ["Variance vs prior (%)", "1.8"],
                ["Variance band", "<= 2.0"],
                ["Branch", "within_band"],
                ["GOSI exposure (KWD)", "184220"],
                ["Outstanding loans (KWD)", "312400"],
            ],
        },
    }
    steps = [
        {
            "step_id": 0,
            "intent": "Fetch headcount and payroll totals for the period",
            "tool_name": "call_host_api",
            "tool_args": {"api_name": "analyze_employees"},
            "depends_on": [],
            "agent_role": "domain_specialist",
        },
        {
            "step_id": 1,
            "intent": "Compute payroll variance vs prior month",
            "tool_name": "call_host_api",
            "tool_args": {"api_name": "list_payroll_runs"},
            "depends_on": [0],
            "agent_role": "domain_specialist",
        },
        {
            "step_id": 2,
            "intent": "Summarize GOSI exposure and outstanding loans",
            "tool_name": None,
            "tool_args": {},
            "depends_on": [1],
            "agent_role": "researcher",
        },
        {
            "step_id": 3,
            "intent": "Critic review: flag compliance risks before export",
            "tool_name": None,
            "tool_args": {},
            "depends_on": [2],
            "agent_role": "critic",
        },
        {
            "step_id": 4,
            "intent": "Export board pack as Word, Excel, PDF, and PNG chart",
            "tool_name": "export_document",
            "tool_args": export_args,
            "depends_on": [3],
            "agent_role": "orchestrator",
            "is_mutation": True,
        },
        {
            "step_id": 5,
            "intent": "Escalate variance to Finance (human gate) — block silent export",
            "tool_name": None,
            "tool_args": {},
            "depends_on": [1],
            "agent_role": "orchestrator",
            "branch": "escalate",
        },
    ]
    workflow_graph = {
        "version": "1",
        "entry": "t0",
        "nodes": [
            {
                "id": "t0",
                "node_type": "task",
                "intent": steps[0]["intent"],
                "tool_name": "call_host_api",
                "tool_args": {"api_name": "analyze_employees"},
                "retry": dict(_HOST_RETRY),
                "timeout_ms": 15_000,
                "meta": {"step_id": 0, "agent_role": "domain_specialist"},
            },
            {
                "id": "t1",
                "node_type": "task",
                "intent": steps[1]["intent"],
                "tool_name": "call_host_api",
                "tool_args": {"api_name": "list_payroll_runs"},
                "retry": dict(_HOST_RETRY),
                "timeout_ms": 15_000,
                "meta": {"step_id": 1, "agent_role": "domain_specialist"},
            },
            {
                "id": "choice_variance",
                "node_type": "choice",
                "intent": "Variance within policy band?",
                "meta": {"agent_role": "orchestrator"},
            },
            {
                "id": "t2",
                "node_type": "task",
                "intent": steps[2]["intent"],
                "meta": {"step_id": 2, "agent_role": "researcher"},
            },
            {
                "id": "t5",
                "node_type": "human",
                "intent": steps[5]["intent"],
                "meta": {"step_id": 5, "agent_role": "orchestrator"},
            },
            {
                "id": "t3",
                "node_type": "task",
                "intent": steps[3]["intent"],
                "catch": [
                    {
                        "on": ["timeout", "permanent", "tool_error", "veto"],
                        "next": "observe_repair",
                    }
                ],
                "timeout_ms": 30_000,
                "meta": {"step_id": 3, "agent_role": "critic"},
            },
            {
                "id": "observe_repair",
                "node_type": "observe",
                "intent": "Repair critic findings before export (no silent pack)",
                "meta": {"agent_role": "critic"},
            },
            {
                "id": "t4",
                "node_type": "task",
                "intent": steps[4]["intent"],
                "tool_name": "export_document",
                "tool_args": export_args,
                "is_mutation": True,
                "meta": {"step_id": 4, "agent_role": "orchestrator"},
            },
            {
                "id": "fail_block_export",
                "node_type": "fail",
                "intent": "Block export — unresolved critic or Finance escalation",
            },
        ],
        "edges": [
            {"source": "t0", "target": "t1", "label": "next"},
            {"source": "t1", "target": "choice_variance", "label": "next"},
            {
                "source": "choice_variance",
                "target": "t2",
                "guard": "variance_pct <= 2.0",
                "label": "within band",
            },
            {
                "source": "choice_variance",
                "target": "t5",
                "is_default": True,
                "label": "escalate",
            },
            {"source": "t2", "target": "t3", "label": "next"},
            {"source": "t3", "target": "t4", "label": "critic ok"},
            {
                "source": "observe_repair",
                "target": "t4",
                "guard": "critic_healed == true",
                "label": "healed",
            },
            {
                "source": "observe_repair",
                "target": "fail_block_export",
                "is_default": True,
                "label": "unresolved",
            },
            {
                "source": "t5",
                "target": "fail_block_export",
                "label": "await Finance",
            },
        ],
    }
    return {
        "pattern": "payroll_board_pack",
        "brief": "October payroll variance board pack",
        "steps": steps,
        "workflow_graph": workflow_graph,
        "demo_branch": {
            "choice_id": "choice_variance",
            "taken": "within_band",
            "skipped_step_ids": [5],
            "variance_pct": 1.8,
        },
    }


# Stable template names — upsert by name+user.
TEMPLATE_SPECS = [
    {
        "name": "Payroll variance board pack",
        "description": (
            "Multi-agent branched payroll pack: headcount → variance → "
            "choice (within band vs Finance escalate) → GOSI summarize → "
            "critic (catch→observe repair) → export Word/Excel/PDF/PNG. "
            "Host fetches declare retry/timeout."
        ),
        "brief": (
            "Run October payroll variance for GOFSCO. If variance is within "
            "band, summarize GOSI/loans, pass critic, then export a board pack "
            "(Word + Excel + PDF + PNG). If over band, escalate to Finance and "
            "do not export silently."
        ),
        "plan_json": build_payroll_board_pack_plan_json(),
    },
    {
        "name": "Leave & attendance compliance brief",
        "description": (
            "Compliance auditor path: leave balances, attendance anomalies, "
            "Word+PDF brief for HR leadership."
        ),
        "brief": (
            "Audit leave and attendance compliance for this month. Produce a "
            "Word report and PDF for HR leadership."
        ),
        "plan_json": {
            "pattern": "leave_compliance_brief",
            "brief": "Leave & attendance compliance brief",
            "steps": [
                {
                    "step_id": 0,
                    "intent": "Pull leave balances and pending requests",
                    "tool_name": "call_host_api",
                    "tool_args": {"api_name": "list_leave_entitlements"},
                    "depends_on": [],
                    "agent_role": "researcher",
                },
                {
                    "step_id": 1,
                    "intent": "Flag attendance anomalies and policy breaches",
                    "tool_name": "call_host_api",
                    "tool_args": {"api_name": "list_attendance"},
                    "depends_on": [0],
                    "agent_role": "critic",
                },
                {
                    "step_id": 2,
                    "intent": "Export Word + PDF compliance brief",
                    "tool_name": "export_document",
                    "tool_args": {
                        "format": "pack",
                        "title": "Leave & Attendance Compliance Brief",
                        "content": (
                            "## Scope\n"
                            "Month-to-date leave and attendance review.\n\n"
                            "### Findings\n"
                            "- 11 employees over policy threshold for unplanned leave\n"
                            "- 3 departments with rising late-clock patterns\n\n"
                            "### Recommended actions\n"
                            "1. Manager coaching for flagged departments\n"
                            "2. Close open leave approvals older than 5 days\n"
                        ),
                        "table": {
                            "headers": ["Department", "Flags"],
                            "rows": [
                                ["Field Ops", "7"],
                                ["Finance", "2"],
                                ["HR", "1"],
                                ["Projects", "4"],
                            ],
                        },
                    },
                    "depends_on": [1],
                    "agent_role": "orchestrator",
                    "is_mutation": True,
                },
            ],
        },
    },
    {
        "name": "Workforce briefing with chart pack",
        "description": (
            "Workforce researcher + finance packager: headcount trends, "
            "Excel workbook + PNG chart for the weekly standup."
        ),
        "brief": (
            "Prepare the weekly workforce briefing with headcount trends. "
            "Export Excel and a PNG chart for standup."
        ),
        "plan_json": {
            "pattern": "workforce_chart_pack",
            "brief": "Weekly workforce briefing",
            "steps": [
                {
                    "step_id": 0,
                    "intent": "Analyze employee headcount trends",
                    "tool_name": "call_host_api",
                    "tool_args": {"api_name": "analyze_employees"},
                    "depends_on": [],
                    "agent_role": "researcher",
                },
                {
                    "step_id": 1,
                    "intent": "Draft standup narrative from trends",
                    "tool_name": None,
                    "tool_args": {},
                    "depends_on": [0],
                    "agent_role": "planner",
                },
                {
                    "step_id": 2,
                    "intent": "Export Excel workbook and PNG chart",
                    "tool_name": "export_document",
                    "tool_args": {
                        "format": "pack",
                        "title": "Weekly Workforce Briefing",
                        "content": (
                            "## This week\n"
                            "- Net headcount +4 vs last week\n"
                            "- Attrition stable at 0.6%\n"
                            "- Two open critical roles in Field Ops\n"
                        ),
                        "table": {
                            "headers": ["Week", "Headcount"],
                            "rows": [
                                ["W1", "521"],
                                ["W2", "523"],
                                ["W3", "525"],
                                ["W4", "529"],
                            ],
                        },
                    },
                    "depends_on": [1],
                    "agent_role": "orchestrator",
                    "is_mutation": True,
                },
            ],
        },
    },
    {
        "name": "GOFSCO GOSI WPS prep pack",
        "description": (
            "Nibras/GOFSCO: generate → validate GOSI WPS SIF, critic gates "
            "submit, then export HR action pack. Submit stays human-gated."
        ),
        "brief": (
            "Prepare the GOFSCO GOSI WPS SIF for this payroll period: generate, "
            "validate, pass critic, then package findings. Do not submit until "
            "Finance/HR approves the run."
        ),
        "plan_json": {
            "pattern": "gofsco_gosi_wps_prep",
            "brief": "GOFSCO GOSI WPS prep pack",
            "persona": "emp_2400",
            "steps": [
                {
                    "step_id": 0,
                    "intent": "Generate GOSI WPS SIF for the locked payroll run",
                    "tool_name": "call_host_api",
                    "tool_args": {"api_name": "generate_gosi_wps_sif"},
                    "depends_on": [],
                    "agent_role": "domain_specialist",
                    "is_mutation": True,
                },
                {
                    "step_id": 1,
                    "intent": "Validate GOSI WPS SIF against Kuwait rules",
                    "tool_name": "call_host_api",
                    "tool_args": {"api_name": "validate_gosi_wps_sif"},
                    "depends_on": [0],
                    "agent_role": "domain_specialist",
                },
                {
                    "step_id": 2,
                    "intent": "Critic: block silent submit on validation flags",
                    "tool_name": None,
                    "tool_args": {},
                    "depends_on": [1],
                    "agent_role": "critic",
                },
                {
                    "step_id": 3,
                    "intent": "Human gate — Finance/HR approve before bank submit",
                    "tool_name": None,
                    "tool_args": {},
                    "depends_on": [2],
                    "agent_role": "orchestrator",
                    "branch": "await_human",
                },
                {
                    "step_id": 4,
                    "intent": "Export GOSI prep brief (Word + Excel + PDF)",
                    "tool_name": "export_document",
                    "tool_args": {
                        "format": "pack",
                        "title": "GOFSCO GOSI WPS Prep Pack",
                        "content": (
                            "## GOFSCO · GOSI WPS\n"
                            "SIF generated and validated. Submit held for human approval.\n\n"
                            "### Validation\n"
                            "- Schema OK\n"
                            "- 2 late-enrollment flags for HR follow-up\n\n"
                            "### Next\n"
                            "Approve step → `submit_gosi_wps_sif` (Agent + RULE_21).\n"
                        ),
                        "table": {
                            "headers": ["Check", "Result"],
                            "rows": [
                                ["Generate", "ok"],
                                ["Validate", "ok · 2 flags"],
                                ["Submit", "held"],
                            ],
                        },
                    },
                    "depends_on": [3],
                    "agent_role": "orchestrator",
                    "is_mutation": True,
                },
            ],
        },
    },
    {
        "name": "Team leave coverage — Coiled Tubing",
        "description": (
            "Nibras Team (emp_1712): who is out on the CT crew this week, "
            "coverage plan, critic conflict check, manager brief."
        ),
        "brief": (
            "For Mohammad Bolto Ali's Coiled Tubing team: list leave this week, "
            "draft coverage, flag conflicts, export a manager brief."
        ),
        "plan_json": {
            "pattern": "team_leave_coverage_ct",
            "brief": "Team leave coverage — Coiled Tubing",
            "persona": "emp_1712",
            "steps": [
                {
                    "step_id": 0,
                    "intent": "List leave records for the manager's crew this week",
                    "tool_name": "call_host_api",
                    "tool_args": {"api_name": "list_leave_records"},
                    "depends_on": [],
                    "agent_role": "researcher",
                },
                {
                    "step_id": 1,
                    "intent": "Resolve crew roster (incl. emp_1067 Bilagot)",
                    "tool_name": "call_host_api",
                    "tool_args": {"api_name": "list_employees"},
                    "depends_on": [],
                    "agent_role": "researcher",
                },
                {
                    "step_id": 2,
                    "intent": "Draft day-by-day coverage for Field Ops / CT",
                    "tool_name": None,
                    "tool_args": {},
                    "depends_on": [0, 1],
                    "agent_role": "planner",
                },
                {
                    "step_id": 3,
                    "intent": "Critic: overlapping absences and understaffed shifts",
                    "tool_name": None,
                    "tool_args": {},
                    "depends_on": [2],
                    "agent_role": "critic",
                },
                {
                    "step_id": 4,
                    "intent": "Export manager coverage brief",
                    "tool_name": "export_document",
                    "tool_args": {
                        "format": "pack",
                        "title": "CT Crew Leave Coverage — This Week",
                        "content": (
                            "## Coiled Tubing · Team coverage\n"
                            "Manager: Mohammad Bolto Ali (`emp_1712`)\n\n"
                            "### Out this week\n"
                            "- Review leave_records + roster before approving swaps\n\n"
                            "### Critic\n"
                            "- Flag any day with < minimum CT staffing\n"
                        ),
                        "table": {
                            "headers": ["Day", "Out", "Coverage"],
                            "rows": [
                                ["Sun", "1", "OK"],
                                ["Mon", "2", "Watch"],
                                ["Tue", "0", "OK"],
                            ],
                        },
                    },
                    "depends_on": [3],
                    "agent_role": "orchestrator",
                    "is_mutation": True,
                },
            ],
        },
    },
    {
        "name": "GOFSCO loan portfolio risk brief",
        "description": (
            "Nibras People/Finance: company loan book → concentration → "
            "critic policy band → board-ready pack."
        ),
        "brief": (
            "Pull GOFSCO company loans and installments, assess concentration "
            "risk, pass critic, export a risk brief for HR leadership."
        ),
        "plan_json": {
            "pattern": "gofsco_loan_portfolio_risk",
            "brief": "GOFSCO loan portfolio risk brief",
            "persona": "emp_2400",
            "steps": [
                {
                    "step_id": 0,
                    "intent": "List company loans",
                    "tool_name": "call_host_api",
                    "tool_args": {"api_name": "list_loans"},
                    "depends_on": [],
                    "agent_role": "researcher",
                },
                {
                    "step_id": 1,
                    "intent": "List installments / outstanding schedule",
                    "tool_name": "call_host_api",
                    "tool_args": {"api_name": "list_loan_installments"},
                    "depends_on": [0],
                    "agent_role": "domain_specialist",
                },
                {
                    "step_id": 2,
                    "intent": "Critic: policy band, high balance, arrears",
                    "tool_name": None,
                    "tool_args": {},
                    "depends_on": [1],
                    "agent_role": "critic",
                },
                {
                    "step_id": 3,
                    "intent": "Export loan risk pack",
                    "tool_name": "export_document",
                    "tool_args": {
                        "format": "pack",
                        "title": "GOFSCO Loan Portfolio Risk Brief",
                        "content": (
                            "## Loan book\n"
                            "Company-wide outstanding loans for GOFSCO.\n\n"
                            "### Critic focus\n"
                            "- Concentration by department\n"
                            "- Arrears and near-limit balances\n"
                        ),
                        "table": {
                            "headers": ["Metric", "Value"],
                            "rows": [
                                ["Active loans", "42"],
                                ["Outstanding (KWD)", "312400"],
                                ["Arrears flags", "3"],
                            ],
                        },
                    },
                    "depends_on": [2],
                    "agent_role": "orchestrator",
                    "is_mutation": True,
                },
            ],
        },
    },
    {
        "name": "Attendance permission backlog — HR",
        "description": (
            "Nibras People lead (emp_2400): open attendance permissions, "
            "SLA critic, action pack — Approve stays Agent/host UI."
        ),
        "brief": (
            "List open attendance permissions across GOFSCO, flag SLA breaches, "
            "export an HR triage pack. Do not auto-approve."
        ),
        "plan_json": {
            "pattern": "attendance_permission_backlog",
            "brief": "Attendance permission backlog — HR",
            "persona": "emp_2400",
            "steps": [
                {
                    "step_id": 0,
                    "intent": "List attendance permissions awaiting action",
                    "tool_name": "call_host_api",
                    "tool_args": {"api_name": "list_attendance_permissions"},
                    "depends_on": [],
                    "agent_role": "researcher",
                },
                {
                    "step_id": 1,
                    "intent": "Cross-check attendance rows for the same window",
                    "tool_name": "call_host_api",
                    "tool_args": {"api_name": "list_attendance"},
                    "depends_on": [0],
                    "agent_role": "researcher",
                },
                {
                    "step_id": 2,
                    "intent": "Critic: age > 5 days, missing manager, duplicates",
                    "tool_name": None,
                    "tool_args": {},
                    "depends_on": [1],
                    "agent_role": "critic",
                },
                {
                    "step_id": 3,
                    "intent": "Plan triage order for Abdullah (People lead)",
                    "tool_name": None,
                    "tool_args": {},
                    "depends_on": [2],
                    "agent_role": "planner",
                },
                {
                    "step_id": 4,
                    "intent": "Export HR triage pack",
                    "tool_name": "export_document",
                    "tool_args": {
                        "format": "pack",
                        "title": "Attendance Permission Backlog — GOFSCO",
                        "content": (
                            "## HR triage\n"
                            "Owner: Abdullah Mubarak Rashed AlHajri (`emp_2400`)\n\n"
                            "Approvals stay on Agent Run / People UI (ADR-0046).\n"
                        ),
                        "table": {
                            "headers": ["Priority", "Count"],
                            "rows": [
                                ["SLA breach", "4"],
                                ["Normal", "11"],
                                ["Duplicate suspect", "1"],
                            ],
                        },
                    },
                    "depends_on": [3],
                    "agent_role": "orchestrator",
                    "is_mutation": True,
                },
            ],
        },
    },
    {
        "name": "Field Ops headcount slice",
        "description": (
            "Nibras analytics: analyze_employees by department/position, "
            "planner narrative, chart pack for weekly ops standup."
        ),
        "brief": (
            "Break down GOFSCO headcount for Field Ops / Coiled Tubing. "
            "Export Excel + PNG for the ops standup."
        ),
        "plan_json": {
            "pattern": "field_ops_headcount_slice",
            "brief": "Field Ops headcount slice",
            "persona": "ahmed",
            "steps": [
                {
                    "step_id": 0,
                    "intent": "Analyze employees by department / position",
                    "tool_name": "call_host_api",
                    "tool_args": {
                        "api_name": "analyze_employees",
                        "dimension": "department",
                    },
                    "depends_on": [],
                    "agent_role": "researcher",
                },
                {
                    "step_id": 1,
                    "intent": "List positions to map CT / Field Ops titles",
                    "tool_name": "call_host_api",
                    "tool_args": {"api_name": "list_positions"},
                    "depends_on": [],
                    "agent_role": "researcher",
                },
                {
                    "step_id": 2,
                    "intent": "Draft Field Ops standup narrative",
                    "tool_name": None,
                    "tool_args": {},
                    "depends_on": [0, 1],
                    "agent_role": "planner",
                },
                {
                    "step_id": 3,
                    "intent": "Export Field Ops chart pack",
                    "tool_name": "export_document",
                    "tool_args": {
                        "format": "pack",
                        "title": "GOFSCO Field Ops Headcount Slice",
                        "content": (
                            "## Field Ops\n"
                            "Department and position cut for weekly ops standup.\n"
                        ),
                        "table": {
                            "headers": ["Slice", "Headcount"],
                            "rows": [
                                ["Field Ops", "186"],
                                ["Coiled Tubing", "42"],
                                ["Projects", "61"],
                            ],
                        },
                    },
                    "depends_on": [2],
                    "agent_role": "orchestrator",
                    "is_mutation": True,
                },
            ],
        },
    },
]

# Specialized agents — names are stable; roles stay within AGENT_ROLES.
AGENT_SPECS = [
    {
        "name": "payroll_controller",
        "role": "domain_specialist",
        "tool_set": [
            "search_knowledge",
            "get_entity_details",
            "call_host_api",
            "export_document",
        ],
        "playbook_blocks": [
            "Own payroll variance, GOSI, and loan exposure analyses.",
            "Always finish board asks with export_document format=pack.",
        ],
        "max_turns": 5,
    },
    {
        "name": "compliance_auditor",
        "role": "critic",
        "tool_set": [
            "search_knowledge",
            "get_entity_details",
            "call_host_api",
            "export_document",
        ],
        "playbook_blocks": [
            "Challenge leave/attendance and policy breaches before export.",
            "Prefer Word+PDF briefs for HR leadership.",
        ],
        "max_turns": 3,
    },
    {
        "name": "workforce_researcher",
        "role": "researcher",
        "tool_set": [
            "search_knowledge",
            "get_entity_details",
            "call_host_api",
            "export_document",
            "web_research",
        ],
        "playbook_blocks": [
            "Produce workforce trends and standup-ready narratives.",
            "Pair Excel with a PNG chart when the brief asks for visuals.",
        ],
        "max_turns": 4,
    },
    {
        "name": "gosi_controller",
        "role": "domain_specialist",
        "tool_set": [
            "search_knowledge",
            "get_entity_details",
            "call_host_api",
            "export_document",
        ],
        "playbook_blocks": [
            "Own generate/validate GOSI WPS SIF for GOFSCO payroll periods.",
            "Never submit_gosi_wps_sif without critic pass + human gate.",
        ],
        "max_turns": 5,
    },
    {
        "name": "finance_packager",
        "role": "planner",
        "tool_set": [
            "search_knowledge",
            "get_entity_details",
            "export_document",
        ],
        "playbook_blocks": [
            "Assemble multi-format deliverable packs from prior step findings.",
            "Never leave a board brief as prose-only when files were requested.",
        ],
        "max_turns": 3,
    },
]

HANDOFF_SPECS = [
    ("orchestrator", "payroll_controller", 2, "payroll variance and GOSI packs"),
    ("orchestrator", "gosi_controller", 1, "GOSI WPS generate/validate"),
    ("orchestrator", "compliance_auditor", 1, "compliance critique before export"),
    ("orchestrator", "workforce_researcher", 2, "workforce trend research"),
    ("orchestrator", "finance_packager", 1, "assemble file deliverable packs"),
    ("payroll_controller", "orchestrator", 1, "return payroll findings"),
    ("gosi_controller", "orchestrator", 1, "return GOSI SIF findings"),
    ("compliance_auditor", "orchestrator", 1, "return compliance verdict"),
    ("workforce_researcher", "orchestrator", 1, "return workforce findings"),
    ("finance_packager", "orchestrator", 1, "return packaged deliverables"),
]


class Command(BaseCommand):
    help = "Seed specialized agents + PlanTemplates with file deliverables."

    def add_arguments(self, parser):
        parser.add_argument(
            "--user",
            type=str,
            default=None,
            help="Username that owns templates / demo run (default: first superuser).",
        )
        parser.add_argument(
            "--instance",
            type=str,
            default=None,
            help="Instance id (default: resolve_instance_id / PLAN_INSTANCE_ID).",
        )
        parser.add_argument(
            "--with-demo-run",
            action="store_true",
            help="Materialize a completed Run with real downloadable artifacts.",
        )
        parser.add_argument(
            "--reset-templates",
            action="store_true",
            help="Delete existing templates with the same names for this user.",
        )

    def handle(self, *args, **options):
        instance_id = options.get("instance") or PLAN_INSTANCE_ID or resolve_instance_id()
        user = self._resolve_user(options.get("user"))
        catalog = CatalogService(instance_id=instance_id)

        self.stdout.write(f"instance={instance_id} user={user.username} ({user.pk})")

        # Ensure default topology exists, then layer specialized agents.
        async_to_sync(self._seed_defaults)(instance_id)
        agents = self._seed_agents(catalog)
        async_to_sync(self._seed_handoffs)(instance_id, agents)
        self.stdout.write(self.style.SUCCESS(f"agents ready: {', '.join(sorted(agents))}"))

        if options.get("reset_templates"):
            deleted, _ = PlanTemplate.objects.filter(
                host_user_id=str(user.pk),
                name__in=[t["name"] for t in TEMPLATE_SPECS],
            ).delete()
            self.stdout.write(f"reset templates deleted={deleted}")

        templates = self._seed_templates(user)
        self.stdout.write(
            self.style.SUCCESS(f"templates ready: {len(templates)} ({', '.join(t.name for t in templates)})")
        )

        if options.get("with_demo_run"):
            run_id = self._materialize_demo_run(user, templates[0])
            self.stdout.write(self.style.SUCCESS(f"demo run completed id={run_id}"))

        self.stdout.write(self.style.SUCCESS("seed_complex_agent_demos done"))

    def _resolve_user(self, username: str | None):
        User = get_user_model()
        if username:
            try:
                return User.objects.get(username=username)
            except User.DoesNotExist as exc:
                raise CommandError(f"User {username!r} not found.") from exc
        user = User.objects.filter(is_superuser=True).order_by("pk").first()
        if user is None:
            user = User.objects.order_by("pk").first()
        if user is None:
            raise CommandError("No users in the database — create one first.")
        return user

    async def _seed_defaults(self, instance_id: str) -> None:
        factory = get_session_factory(instance_id)
        async with factory() as db:
            registry = AgentRegistry(db)
            await registry.seed_defaults(instance_id)

    def _seed_agents(self, catalog: CatalogService) -> dict[str, str]:
        by_name: dict[str, str] = {}
        for spec in AGENT_SPECS:
            row = catalog.register_agent(
                name=spec["name"],
                role=spec["role"],
                tool_set=spec["tool_set"],
                playbook_blocks=spec["playbook_blocks"],
                max_turns=spec["max_turns"],
            )
            by_name[spec["name"]] = row["id"]
            self.stdout.write(f"  agent {spec['name']} ({spec['role']}) id={row['id']}")
        # Also capture orchestrator for handoffs.
        for agent in catalog.list_agents():
            by_name.setdefault(agent["name"], agent["id"])
        return by_name

    async def _seed_handoffs(self, instance_id: str, agents: dict[str, str]) -> None:
        factory = get_session_factory(instance_id)
        async with factory() as db:
            registry = AgentRegistry(db)
            for from_name, to_name, max_parallel, desc in HANDOFF_SPECS:
                if from_name not in agents or to_name not in agents:
                    continue
                await registry.add_handoff(
                    from_agent_id=agents[from_name],
                    to_agent_id=agents[to_name],
                    description=desc,
                    max_parallel=max_parallel,
                )

    def _seed_templates(self, user) -> list[PlanTemplate]:
        out: list[PlanTemplate] = []
        for spec in TEMPLATE_SPECS:
            existing = PlanTemplate.objects.filter(
                host_user_id=str(user.pk), name=spec["name"]
            ).first()
            plan_json = json.loads(json.dumps(spec["plan_json"]))
            plan_json["brief"] = spec["brief"]
            if existing:
                existing.description = spec["description"]
                existing.plan_json = plan_json
                existing.save(update_fields=["description", "plan_json", "updated_at"])
                out.append(existing)
                self.stdout.write(f"  template upsert {existing.name} id={existing.id}")
            else:
                tpl = PlanTemplate(
                    id=generate_uuid(),
                    host_user_id=str(user.pk),
                    name=spec["name"],
                    description=spec["description"],
                    plan_json=plan_json,
                )
                tpl.save()
                out.append(tpl)
                self.stdout.write(f"  template create {tpl.name} id={tpl.id}")
        return out

    def _materialize_demo_run(self, user, template: PlanTemplate) -> str:
        """Create a completed Run + run export_document pack → real artifacts."""
        plan_json = json.loads(json.dumps(template.plan_json or {}))
        steps = [s for s in plan_json.get("steps", []) if isinstance(s, dict)]
        demo_branch = plan_json.get("demo_branch") or {}
        skipped_ids = {
            int(x) for x in (demo_branch.get("skipped_step_ids") or [])
        }
        # Happy-path demo: mark escalate branch as skipped so the choice
        # gateway annotates "within band" as chosen on the Run graph.
        for step in steps:
            sid = int(step.get("step_id", -1))
            if sid in skipped_ids:
                step["status"] = STEP_SKIPPED
            else:
                step["status"] = STEP_COMPLETED
        run_id = generate_uuid()
        Run.objects.create(
            id=run_id,
            instance_id=PLAN_INSTANCE_ID,
            conversation_id="",
            host_user_id=str(user.pk),
            user_message=template.name,
            status=STATUS_COMPLETED,
            plan_json=plan_json,
            working_notes={
                "from_template": template.id,
                "demo_seed": True,
                "seeded_at": now().isoformat(),
                "demo_branch": demo_branch,
            },
            final_response=(
                "### Demo board pack ready\n\n"
                "Specialized agents ran a **branched** payroll variance workflow "
                "(within-band path taken; Finance escalate skipped). "
                "Critic passed with catch→observe repair declared for failures. "
                "Download Word, Excel, PDF, and the PNG chart from **Artifacts**.\n\n"
                "Use **Discuss in Chat** to challenge the findings or refine the workflow."
            ),
        )
        export_step_index = 0
        for step in steps:
            idx = int(step.get("step_id", 0))
            step_status = STEP_SKIPPED if idx in skipped_ids else STEP_COMPLETED
            step_state = "skipped" if idx in skipped_ids else "succeeded"
            RunStep.objects.create(
                run_id=run_id,
                step_index=idx,
                intent=step.get("intent", ""),
                tool_name=step.get("tool_name"),
                tool_args_json=step.get("tool_args") or {},
                depends_on_json=step.get("depends_on") or [],
                status=step_status,
                step_id=str(idx),
                step_state=step_state,
            )
            if step.get("tool_name") == "export_document":
                export_step_index = idx

        export_args = None
        for step in steps:
            if step.get("tool_name") == "export_document":
                export_args = dict(step.get("tool_args") or {})
                break
        if not export_args:
            export_args = {
                "format": "pack",
                "title": template.name,
                "content": "## Demo\nSeeded deliverable pack.",
                "table": {
                    "headers": ["Metric", "Value"],
                    "rows": [["Headcount", "529"], ["Variance %", "1.8"]],
                },
            }
        export_args.setdefault("format", "pack")

        set_current_plan_run(run_id)
        try:
            plugin = ExportDocument()
            result = async_to_sync(plugin.execute)(export_args, ctx=None)
        finally:
            set_current_plan_run(None)

        if result.get("error"):
            raise CommandError(f"export_document failed: {result['error']}")

        arts = PlansService().list_artifacts(user, run_id)
        self.stdout.write(
            f"  artifacts={arts.get('count', 0)} export_step={export_step_index} "
            f"ids={result.get('artifact_ids')} skipped={sorted(skipped_ids)}"
        )
        return run_id
