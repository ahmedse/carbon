"""Seed Agent tasks + sophisticated Job Maps (visible on Agent tab).

Agent UI lists ``Run`` plans — not Artifacts alone. This command:
  1. Wipes prior showcase Job Maps + showcase Runs for the user
  2. Creates a conversation + real Agent plans (with steps)
  3. Attaches rich Ops Canvas Job Maps keyed by ``plan_id``

Usage:
    python manage.py seed_ops_canvas_examples --user ahmed --reset
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils.timezone import now

from ai.models import AIArtifact, AIConversation
from ai.models.core import Run, RunStep, generate_uuid
from ai.ops_canvas import ARTIFACT_TYPE, MODE_AGENT, build_payload
from ai.plans_service import (
    PLAN_INSTANCE_ID,
    STATUS_COMPLETED,
    STATUS_PAUSED,
    STEP_AWAITING_APPROVAL,
    STEP_COMPLETED,
    STEP_PENDING,
    STEP_RUNNING,
    STEP_SKIPPED,
)

DEMO_CONV_TITLE = "Ops Canvas · agentic showcase"
SHOWCASE_NOTE = "ops_canvas_showcase"


def _showcases() -> list[dict]:
    """Each item: Agent Run (task list) + Job Map layers (canvas under DAG)."""
    return [
        {
            "brief": (
                "Close October payroll: parallel GOSI/loans/leave fan-out, "
                "XOR branch on MoM variance >2%, critic gate, export board pack"
            ),
            "run_status": STATUS_COMPLETED,
            "title": "Month-end payroll saga — parallel · branch · critic · pack",
            "plan_id_hint": None,  # generated
            "steps": [
                {
                    "step_id": 0,
                    "intent": "Resolve PayrollRun PR-2026-10 + lock period",
                    "tool_name": "resolve_entity",
                    "depends_on": [],
                    "status": STEP_COMPLETED,
                },
                {
                    "step_id": 1,
                    "intent": "∥ Fan-out: GOSI exposure ledger",
                    "tool_name": "aggregate_entity",
                    "depends_on": [0],
                    "status": STEP_COMPLETED,
                },
                {
                    "step_id": 2,
                    "intent": "∥ Fan-out: active loans outstanding",
                    "tool_name": "aggregate_entity",
                    "depends_on": [0],
                    "status": STEP_COMPLETED,
                },
                {
                    "step_id": 3,
                    "intent": "∥ Fan-out: leave accrual delta MoM",
                    "tool_name": "list_leave_entitlements",
                    "depends_on": [0],
                    "status": STEP_COMPLETED,
                },
                {
                    "step_id": 4,
                    "intent": "Join fan-out → compute MoM variance %",
                    "tool_name": "cross_synthesize",
                    "depends_on": [1, 2, 3],
                    "status": STEP_COMPLETED,
                },
                {
                    "step_id": 5,
                    "intent": "Choice XOR: variance ≤ 2% → continue else escalate",
                    "tool_name": "plan_task",
                    "depends_on": [4],
                    "status": STEP_COMPLETED,
                },
                {
                    "step_id": 6,
                    "intent": "Escalate Finance human grant",
                    "tool_name": "plan_task",
                    "depends_on": [5],
                    "status": STEP_SKIPPED,
                },
                {
                    "step_id": 7,
                    "intent": "Draft board narrative + risk flags",
                    "tool_name": "cross_synthesize",
                    "depends_on": [5],
                    "status": STEP_COMPLETED,
                    "agent_role": "finance_packager",
                },
                {
                    "step_id": 8,
                    "intent": "Critic agent: veto / pass board pack",
                    "tool_name": "cross_synthesize",
                    "depends_on": [7],
                    "status": STEP_COMPLETED,
                    "agent_role": "critic",
                },
                {
                    "step_id": 9,
                    "intent": "Export board pack (docx + xlsx + png)",
                    "tool_name": "export_document",
                    "depends_on": [8],
                    "status": STEP_COMPLETED,
                    "tool_args": {"format": "pack", "title": "Oct Payroll Board"},
                },
                {
                    "step_id": 10,
                    "intent": "FlightDirector acceptance close + learn",
                    "tool_name": "flight_acceptance",
                    "depends_on": [9],
                    "status": STEP_COMPLETED,
                },
            ],
            "phases": [
                {"phase_id": 0, "name": "Fan-out", "strategy": "parallel", "step_ids": [1, 2, 3]},
                {"phase_id": 1, "name": "Branch + critic", "strategy": "sequential", "step_ids": [4, 5, 6, 7, 8]},
                {"phase_id": 2, "name": "Export + accept", "strategy": "sequential", "step_ids": [9, 10]},
            ],
            "related_object": {
                "type": "people.PayrollRun",
                "id": "PR-2026-10",
                "label": "October 2026 payroll close",
            },
            "layers": {
                "intent": {
                    "ask": "Close October payroll with resilient parallel→choice→critic→export workflow",
                    "success_criteria": "Pack exported after critic pass; escalate only if variance>2%",
                    "contract": "agent",
                },
                "job_map": {
                    "steps": [],  # filled from RunSteps at seed time
                    "tools": [
                        "resolve_entity",
                        "aggregate_entity",
                        "list_leave_entitlements",
                        "cross_synthesize",
                        "export_document",
                    ],
                    "capabilities": ["people:view", "people:view_payroll", "ai:run_agent", "ai:export"],
                    "entities": [{"type": "people.PayrollRun", "id": "PR-2026-10"}],
                    "workflow_graph": {
                        "pattern": "parallel→join→choice→critic→export",
                        "resilience": {"retry": {"max_attempts": 3}, "compensate_on": "critic_veto"},
                    },
                },
                "live_run": {
                    "progress_pct": 100,
                    "status": "completed",
                    "qos": {
                        "acceptance_status": "met",
                        "requirements_total": 7,
                        "requirements_met": 7,
                        "requirements_partial": 0,
                        "requirements_missed": 0,
                        "repairs": 0,
                        "escalations": 0,
                    },
                    "blockers": [],
                    "pending_consent": None,
                    "phases": [
                        {"name": "Fan-out", "status": "completed"},
                        {"name": "Variance branch", "status": "completed"},
                        {"name": "Critic", "status": "completed"},
                        {"name": "Export", "status": "completed"},
                    ],
                },
                "evidence": {
                    "headline": "Variance 1.8% ≤ 2.0% · critic PASS · pack exported",
                    "prose": (
                        "Parallel fan-out joined. Escalate skipped. Critic 0.91. "
                        "FlightDirector acceptance met on all requirements."
                    ),
                    "tables": [
                        {
                            "title": "Parallel fan-out",
                            "columns": ["Lane", "Metric", "Value"],
                            "rows": [
                                ["GOSI", "Exposure KWD", "184,220"],
                                ["Loans", "Active / outstanding", "42 / 312,400"],
                                ["Leave", "Accrual MoM Δ (d)", "+1,104"],
                            ],
                        },
                        {
                            "title": "Gates",
                            "columns": ["Gate", "Decision"],
                            "rows": [
                                ["XOR variance 1.8%", "continue"],
                                ["Critic", "PASS"],
                                ["Catch repair", "not entered"],
                            ],
                        },
                    ],
                    "sources": [{"label": "payroll_run.PR-2026-10"}, {"label": "flight.acceptance"}],
                    "caveats": ["2 late GOSI enrollments — HR by EOM"],
                },
                "outcome": {
                    "summary": "October payroll closed. Board pack ready. Compensate unused.",
                    "sor_links": [
                        {"label": "PayrollRun PR-2026-10", "path": "/people/payroll/PR-2026-10"}
                    ],
                    "canvas_id": "",
                },
            },
        },
        {
            "brief": (
                "Create DQ rule Water consumption > 0 with exact field set; "
                "FlightDirector repair loop ≤2; never auto-rerun mutation"
            ),
            "run_status": STATUS_PAUSED,  # mid-run feel
            "title": "DQ water rule — FlightDirector repair · exact fields · consent",
            "steps": [
                {
                    "step_id": 0,
                    "intent": "Catalog search: emissions water field (trust-ranked)",
                    "tool_name": "api_catalog_search",
                    "depends_on": [],
                    "status": STEP_COMPLETED,
                },
                {
                    "step_id": 1,
                    "intent": "Resolve DataField water_consumption",
                    "tool_name": "resolve_entity",
                    "depends_on": [0],
                    "status": STEP_COMPLETED,
                },
                {
                    "step_id": 2,
                    "intent": "Consent: create_dq_rule (mutation)",
                    "tool_name": "create_dq_rule",
                    "depends_on": [1],
                    "status": STEP_COMPLETED,
                    "is_mutation": True,
                },
                {
                    "step_id": 3,
                    "intent": "FlightDirector re-query created_entity",
                    "tool_name": "host_get",
                    "depends_on": [2],
                    "status": STEP_COMPLETED,
                },
                {
                    "step_id": 4,
                    "intent": "Accept #1: table_fields → PARTIAL",
                    "tool_name": "flight_acceptance",
                    "depends_on": [3],
                    "status": STEP_COMPLETED,
                },
                {
                    "step_id": 5,
                    "intent": "Repair #1: inject ACTUAL diff + re-consent",
                    "tool_name": "create_dq_rule",
                    "depends_on": [4],
                    "status": STEP_COMPLETED,
                    "is_mutation": True,
                },
                {
                    "step_id": 6,
                    "intent": "FlightDirector re-check after repair",
                    "tool_name": "host_get",
                    "depends_on": [5],
                    "status": STEP_COMPLETED,
                },
                {
                    "step_id": 7,
                    "intent": "Accept #2 + learn playbook pattern",
                    "tool_name": "flight_acceptance",
                    "depends_on": [6],
                    "status": STEP_RUNNING,
                },
            ],
            "phases": [
                {"phase_id": 0, "name": "Discover", "strategy": "sequential", "step_ids": [0, 1]},
                {"phase_id": 1, "name": "Mutate + repair", "strategy": "sequential", "step_ids": [2, 3, 4, 5, 6]},
                {"phase_id": 2, "name": "Close", "strategy": "sequential", "step_ids": [7]},
            ],
            "related_object": {"type": "dq.Rule", "id": "129", "label": "Water consumption > 0"},
            "layers": {
                "intent": {
                    "ask": "Durable DQ rule with FlightDirector exact field-set acceptance",
                    "success_criteria": "Rule exists; accept met or escalated after ≤2 repairs",
                    "contract": "agent",
                },
                "job_map": {
                    "steps": [],
                    "tools": ["api_catalog_search", "resolve_entity", "create_dq_rule", "host_get"],
                    "capabilities": ["dq:manage", "catalog:view", "ai:run_agent"],
                    "entities": [
                        {"type": "dq.Rule", "id": "129"},
                        {"type": "dataschema.DataField", "name": "water_consumption"},
                    ],
                    "workflow_graph": {
                        "pattern": "mutate→accept→repair→accept→learn",
                        "resilience": {"max_repairs": 2, "mutation_auto_rerun": False},
                    },
                },
                "live_run": {
                    "progress_pct": 88,
                    "status": "running",
                    "qos": {
                        "acceptance_status": "partial",
                        "requirements_total": 4,
                        "requirements_met": 3,
                        "requirements_partial": 1,
                        "requirements_missed": 0,
                        "repairs": 1,
                    },
                    "blockers": [],
                    "pending_consent": None,
                    "phases": [
                        {"name": "Discover", "status": "completed"},
                        {"name": "Mutate+repair", "status": "completed"},
                        {"name": "Accept#2 + learn", "status": "running"},
                    ],
                },
                "evidence": {
                    "headline": "Rule #129 live after 1 repair · table_fields still partial",
                    "prose": (
                        "First create had extra=['unit_code']. FlightDirector injected "
                        "repair with ACTUAL diff. RULE_21: mutation never auto-replayed."
                    ),
                    "tables": [
                        {
                            "title": "Acceptance timeline",
                            "columns": ["Pass", "Requirement", "Verdict"],
                            "rows": [
                                ["1", "created_entity", "met"],
                                ["1", "table_fields exact", "partial"],
                                ["2", "created_entity", "met"],
                                ["2", "table_fields exact", "partial"],
                            ],
                        },
                        {
                            "title": "Repair ledger",
                            "columns": ["#", "Diff", "Consent"],
                            "rows": [["1", "drop unit_code", "granted"]],
                        },
                    ],
                    "sources": [{"label": "dq/rules/129"}, {"label": "flight.ledger"}],
                    "caveats": ["Partial ≠ failed — tighten field set in DQ UI"],
                },
                "outcome": {
                    "summary": "Rule 129 durable. Final learn step still running.",
                    "sor_links": [{"label": "DQ rule 129", "path": "/admin/dq/rules/129"}],
                    "canvas_id": "",
                },
            },
        },
        {
            "brief": (
                "Mark OSCE reflective run with LCT HITL, release, then stage "
                "compensation deny for linked employee 333 under RULE_21 consent"
            ),
            "run_status": STATUS_PAUSED,
            "title": "Cross-domain OSCE HITL → People subagent → compensation deny (blocked)",
            "steps": [
                {
                    "step_id": 0,
                    "intent": "Load OSCE-7741 + assignment pack",
                    "tool_name": "gradevance_fetch_run",
                    "depends_on": [],
                    "status": STEP_COMPLETED,
                    "agent_role": "eduos_marker",
                },
                {
                    "step_id": 1,
                    "intent": "Auto LCT Semantics codes (SG/SD)",
                    "tool_name": "gradevance_lct_code",
                    "depends_on": [0],
                    "status": STEP_COMPLETED,
                },
                {
                    "step_id": 2,
                    "intent": "HITL ExpertEdit seg2 SG+→SG−",
                    "tool_name": "gradevance_expert_edit",
                    "depends_on": [1],
                    "status": STEP_COMPLETED,
                },
                {
                    "step_id": 3,
                    "intent": "Confidence gate + ceremonial release",
                    "tool_name": "gradevance_release",
                    "depends_on": [2],
                    "status": STEP_COMPLETED,
                },
                {
                    "step_id": 4,
                    "intent": "AGS passback dry-run",
                    "tool_name": "gradevance_ags_preview",
                    "depends_on": [3],
                    "status": STEP_COMPLETED,
                },
                {
                    "step_id": 5,
                    "intent": "Subagent: resolve Employee 333 + leave portfolio",
                    "tool_name": "resolve_entity",
                    "depends_on": [3],
                    "status": STEP_COMPLETED,
                    "agent_role": "people_ops",
                },
                {
                    "step_id": 6,
                    "intent": "Subagent: list compensation CR-4412",
                    "tool_name": "list_compensation_requests",
                    "depends_on": [5],
                    "status": STEP_COMPLETED,
                    "agent_role": "people_ops",
                },
                {
                    "step_id": 7,
                    "intent": "Save WorkObjective: post-OSCE people follow-up",
                    "tool_name": "save_work_objective",
                    "depends_on": [6],
                    "status": STEP_COMPLETED,
                },
                {
                    "step_id": 8,
                    "intent": "BLOCKED — deny_compensation_request CR-4412",
                    "tool_name": "deny_compensation_request",
                    "depends_on": [6],
                    "status": STEP_AWAITING_APPROVAL,
                    "is_mutation": True,
                },
                {
                    "step_id": 9,
                    "intent": "Audit ledger after grant",
                    "tool_name": "write_audit",
                    "depends_on": [8],
                    "status": STEP_PENDING,
                },
            ],
            "phases": [
                {"phase_id": 0, "name": "OSCE mark", "strategy": "sequential", "step_ids": [0, 1, 2, 3, 4]},
                {"phase_id": 1, "name": "People subagent", "strategy": "sequential", "step_ids": [5, 6, 7]},
                {"phase_id": 2, "name": "Consent deny", "strategy": "sequential", "step_ids": [8, 9]},
            ],
            "related_object": {
                "type": "gradevance.AssessmentRun",
                "id": "OSCE-7741",
                "label": "OSCE reflective · employee 333",
            },
            "layers": {
                "intent": {
                    "ask": "EduOS OSCE close + People compensation deny under RULE_21",
                    "success_criteria": "OSCE released; deny only after human grant",
                    "contract": "agent",
                },
                "job_map": {
                    "steps": [],
                    "tools": [
                        "gradevance_fetch_run",
                        "gradevance_lct_code",
                        "gradevance_expert_edit",
                        "gradevance_release",
                        "resolve_entity",
                        "deny_compensation_request",
                    ],
                    "capabilities": [
                        "gradevance:mark",
                        "gradevance:release",
                        "people:manage_compensation",
                        "ai:run_agent",
                    ],
                    "entities": [
                        {"type": "gradevance.AssessmentRun", "id": "OSCE-7741"},
                        {"type": "people.Employee", "id": "333"},
                    ],
                    "workflow_graph": {
                        "pattern": "eduos ∥ people_subagent → consent",
                        "subagents": ["eduos_marker", "people_ops"],
                        "human_gates": ["deny_compensation_request"],
                    },
                },
                "live_run": {
                    "progress_pct": 72,
                    "status": "blocked",
                    "qos": {
                        "acceptance_status": "partial",
                        "requirements_total": 5,
                        "requirements_met": 4,
                        "requirements_partial": 0,
                        "requirements_missed": 1,
                        "escalations": 1,
                    },
                    "blockers": [
                        "RULE_21: deny_compensation_request awaiting human consent (step 8)"
                    ],
                    "pending_consent": {
                        "step_id": 8,
                        "tool": "deny_compensation_request",
                        "intent": "Deny CR-4412 for employee 333",
                        "reason": "Irreversible SoR write",
                    },
                    "phases": [
                        {"name": "OSCE mark+HITL", "status": "completed"},
                        {"name": "People subagent", "status": "completed"},
                        {"name": "Compensation deny", "status": "blocked"},
                    ],
                },
                "evidence": {
                    "headline": "OSCE released · mean conf 0.86 · paused on compensation consent",
                    "prose": (
                        "EduOS path complete. People subagent found CR-4412. "
                        "Deny staged — will not execute until grant."
                    ),
                    "tables": [
                        {
                            "title": "OSCE segments (post-HITL)",
                            "columns": ["#", "SG", "SD", "Conf", "Edited?"],
                            "rows": [
                                ["1", "SG+", "SD-", "0.91", ""],
                                ["2", "SG-", "SD+", "0.78", "ExpertEdit"],
                                ["3", "SG+", "SD-", "0.88", ""],
                            ],
                        },
                        {
                            "title": "Consent queue",
                            "columns": ["Step", "Tool", "Grant?"],
                            "rows": [["8", "deny_compensation_request", "WAITING"]],
                        },
                    ],
                    "sources": [
                        {"label": "gradevance.run.OSCE-7741"},
                        {"label": "people.Employee.333"},
                    ],
                    "caveats": ["AGS passback dry-run only"],
                },
                "outcome": {
                    "summary": "EduOS closed. Compensation deny blocked on consent — grant on run surface.",
                    "sor_links": [
                        {"label": "OSCE workbench", "path": "/apps/gradevance/runs/OSCE-7741"},
                        {"label": "Employee 333", "path": "/people/employees/333"},
                    ],
                    "canvas_id": "",
                },
            },
        },
    ]


def _steps_for_job_map(steps: list[dict]) -> list[dict]:
    return [
        {
            "id": str(s["step_id"]),
            "title": s["intent"],
            "tool": s.get("tool_name") or "",
            "status": s.get("status") or "pending",
            "deps": list(s.get("depends_on") or []),
        }
        for s in steps
    ]


class Command(BaseCommand):
    help = "Seed Agent tasks + Job Maps so Agent tab is not empty."

    def add_arguments(self, parser):
        parser.add_argument("--user", default="ahmed")
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete prior showcase Job Maps + Runs for this user",
        )

    def handle(self, *args, **options):
        username = options["user"]
        User = get_user_model()
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist as exc:
            raise CommandError(f"User {username!r} not found") from exc

        user_pk = str(user.pk)

        if options["reset"]:
            # Showcase runs
            showcase_runs = Run.objects.filter(
                host_user_id=user_pk,
                instance_id=PLAN_INSTANCE_ID,
            )
            # Prefer tagged; also wipe by conversation title link later
            tagged = [
                r
                for r in showcase_runs
                if (r.working_notes or {}).get(SHOWCASE_NOTE)
            ]
            for r in tagged:
                RunStep.objects.filter(run_id=r.id).delete()
                r.delete()
            n_maps = AIArtifact.objects.filter(
                artifact_type=ARTIFACT_TYPE, created_by=user
            ).count()
            AIArtifact.objects.filter(
                artifact_type=ARTIFACT_TYPE, created_by=user
            ).delete()
            AIConversation.objects.filter(
                user=user, title__startswith="Ops Canvas"
            ).delete()
            self.stdout.write(
                self.style.WARNING(
                    f"Reset: {len(tagged)} showcase run(s), {n_maps} Job Map(s)"
                )
            )

        conv = AIConversation.objects.create(
            user=user,
            title=DEMO_CONV_TITLE,
            conversation_type="chat",
            status="active",
        )
        self.stdout.write(f"Conversation {conv.id}")

        for spec in _showcases():
            run_id = generate_uuid()
            steps = spec["steps"]
            plan_json = {
                "pattern": "custom",
                "source": "showcase",
                "brief": spec["brief"],
                "synthesis_instruction": "Summarize run outcome for the Job Map.",
                "needs_confirmation": True,
                "steps": [
                    {
                        "step_id": s["step_id"],
                        "intent": s["intent"],
                        "tool_name": s.get("tool_name"),
                        "tool_args": s.get("tool_args") or {},
                        "depends_on": s.get("depends_on") or [],
                        "is_mutation": bool(s.get("is_mutation")),
                        "agent_role": s.get("agent_role", "orchestrator"),
                        "status": s.get("status"),
                    }
                    for s in steps
                ],
                "phases": spec.get("phases") or [],
                "workflow_graph": (spec.get("layers") or {})
                .get("job_map", {})
                .get("workflow_graph"),
            }

            Run.objects.create(
                id=run_id,
                instance_id=PLAN_INSTANCE_ID,
                conversation_id=str(conv.id),
                host_user_id=user_pk,
                user_message=spec["brief"],
                status=spec["run_status"],
                plan_json=plan_json,
                working_notes={
                    SHOWCASE_NOTE: True,
                    "title": spec["title"],
                    "seeded_at": now().isoformat(),
                },
                final_response=(
                    spec["layers"]["outcome"]["summary"]
                    if spec["run_status"] == STATUS_COMPLETED
                    else None
                ),
            )

            for s in steps:
                st = s.get("status") or STEP_PENDING
                step_state = {
                    STEP_COMPLETED: "succeeded",
                    STEP_SKIPPED: "skipped",
                    STEP_AWAITING_APPROVAL: "awaiting_approval",
                    STEP_RUNNING: "executing",
                    STEP_PENDING: "planned",
                }.get(st, "planned")
                RunStep.objects.create(
                    run_id=run_id,
                    step_index=s["step_id"],
                    intent=s["intent"],
                    tool_name=s.get("tool_name"),
                    tool_args_json=s.get("tool_args") or {},
                    depends_on_json=s.get("depends_on") or [],
                    status=st,
                    step_id=str(s["step_id"]),
                    step_state=step_state,
                )

            layers = dict(spec["layers"])
            job = dict(layers.get("job_map") or {})
            job["steps"] = _steps_for_job_map(steps)
            layers["job_map"] = job

            payload = build_payload(
                mode=MODE_AGENT,
                ask=spec["brief"],
                layers=layers,
                related_object=spec.get("related_object"),
                plan_id=run_id,
                conversation_id=str(conv.id),
                title=spec["title"],
            )
            art = AIArtifact.objects.create(
                conversation=conv,
                created_by=user,
                title=spec["title"][:255],
                artifact_type=ARTIFACT_TYPE,
                content_json=payload,
                visibility="private",
            )
            content = dict(art.content_json or {})
            ly = dict(content.get("layers") or {})
            outcome = dict(ly.get("outcome") or {})
            outcome["canvas_id"] = str(art.id)
            ly["outcome"] = outcome
            content["layers"] = ly
            art.content_json = content
            art.save(update_fields=["content_json"])

            self.stdout.write(
                f"  · Agent task {run_id[:8]}…  [{spec['run_status']}]  {spec['title'][:60]}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(_showcases())} Agent tasks + Job Maps. "
                f"Open Pulse → Agent → pick a task from the dropdown "
                f"(not Chat Artifacts)."
            )
        )
