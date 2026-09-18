"""Seed specialized Pulse agents + multi-step templates with file deliverables.

Creates domain agents (payroll / compliance / workforce / finance packager),
wires handoffs from the orchestrator, promotes three PlanTemplates that end in
``export_document`` (docx / xlsx / pdf / png pack), and optionally materializes
a completed demo Run with real downloadable artifacts for the given user.

Usage:
    python manage.py seed_complex_agent_demos
    python manage.py seed_complex_agent_demos --user admin
    python manage.py seed_complex_agent_demos --user admin --with-demo-run
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
    set_current_plan_run,
)
from ai.plugins.export_document import ExportDocument

logger = logging.getLogger("carbon.ai.seed_complex_agent_demos")

# Stable template names — upsert by name+user.
TEMPLATE_SPECS = [
    {
        "name": "Payroll variance board pack",
        "description": (
            "Multi-agent payroll controller workflow: headcount → variance → "
            "GOSI exposure → export Word/Excel/PDF/PNG pack."
        ),
        "brief": (
            "Run October payroll variance for GOFSCO. Summarize headcount, "
            "GOSI exposure, and outstanding loans. Export a board pack "
            "(Word + Excel + PDF + PNG chart)."
        ),
        "plan_json": {
            "pattern": "payroll_board_pack",
            "brief": "October payroll variance board pack",
            "steps": [
                {
                    "step_id": 0,
                    "intent": "Fetch headcount and payroll totals for the period",
                    "tool_name": "call_host_api",
                    "tool_args": {"path": "/api/analyze_employees", "method": "GET"},
                    "depends_on": [],
                    "agent_role": "domain_specialist",
                },
                {
                    "step_id": 1,
                    "intent": "Compute payroll variance vs prior month",
                    "tool_name": "call_host_api",
                    "tool_args": {"path": "/api/payroll/variance", "method": "GET"},
                    "depends_on": [0],
                    "agent_role": "domain_specialist",
                },
                {
                    "step_id": 2,
                    "intent": "Summarize GOSI exposure and outstanding loans",
                    "tool_name": None,
                    "tool_args": {},
                    "depends_on": [0, 1],
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
                    "tool_args": {
                        "format": "pack",
                        "title": "October Payroll Variance Board Pack",
                        "content": (
                            "## Executive summary\n"
                            "October payroll closed within tolerance after variance review.\n\n"
                            "### GOSI Exposure\n"
                            "- **Total GOSI Exposure**: KWD 184,220\n"
                            "- Employer share within policy band\n\n"
                            "### Outstanding Loans\n"
                            "- 42 active loans · KWD 312,400 outstanding\n\n"
                            "### Compliance Risk Flags\n"
                            "- 2 late enrollment cases — HR to close by month-end\n"
                        ),
                        "table": {
                            "headers": ["Metric", "Value"],
                            "rows": [
                                ["Headcount", "529"],
                                ["Payroll total (KWD)", "1,204,550"],
                                ["Variance vs prior (%)", "1.8"],
                                ["GOSI exposure (KWD)", "184220"],
                                ["Outstanding loans (KWD)", "312400"],
                            ],
                        },
                    },
                    "depends_on": [2, 3],
                    "agent_role": "orchestrator",
                    "is_mutation": True,
                },
            ],
        },
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
                    "tool_args": {"path": "/api/leave/balances", "method": "GET"},
                    "depends_on": [],
                    "agent_role": "researcher",
                },
                {
                    "step_id": 1,
                    "intent": "Flag attendance anomalies and policy breaches",
                    "tool_name": None,
                    "tool_args": {},
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
                    "tool_args": {"path": "/api/analyze_employees", "method": "GET"},
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
    ("orchestrator", "compliance_auditor", 1, "compliance critique before export"),
    ("orchestrator", "workforce_researcher", 2, "workforce trend research"),
    ("orchestrator", "finance_packager", 1, "assemble file deliverable packs"),
    ("payroll_controller", "orchestrator", 1, "return payroll findings"),
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
            },
            final_response=(
                "### Demo board pack ready\n\n"
                "Specialized agents prepared the payroll variance pack. "
                "Download Word, Excel, PDF, and the PNG chart from **Artifacts**.\n\n"
                "Use **Discuss in Chat** to challenge the findings or refine the workflow."
            ),
        )
        export_step_index = 0
        for step in steps:
            idx = int(step.get("step_id", 0))
            RunStep.objects.create(
                run_id=run_id,
                step_index=idx,
                intent=step.get("intent", ""),
                tool_name=step.get("tool_name"),
                tool_args_json=step.get("tool_args") or {},
                depends_on_json=step.get("depends_on") or [],
                status=STEP_COMPLETED,
                step_id=str(idx),
                step_state="succeeded",
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
            f"ids={result.get('artifact_ids')}"
        )
        return run_id
