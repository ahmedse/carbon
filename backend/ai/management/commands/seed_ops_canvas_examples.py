"""Seed complex Ops Canvas Job Map examples (ADR-0041).

Creates a dedicated conversation plus several multi-layer Job Maps so Pulse →
Artifacts → Ops Canvas has something to open immediately.

Usage:
    python manage.py seed_ops_canvas_examples
    python manage.py seed_ops_canvas_examples --user ahmed
    python manage.py seed_ops_canvas_examples --reset
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from ai.models import AIArtifact, AIConversation
from ai.ops_canvas import MODE_AGENT, MODE_CHAT, ARTIFACT_TYPE, build_payload


DEMO_CONV_TITLE = "Ops Canvas · demo maps"


def _examples() -> list[dict]:
    """Complex Job Map payloads — closed kit only."""
    return [
        {
            "title": "Payroll variance board pack (Agent)",
            "mode": MODE_AGENT,
            "ask": (
                "Build October payroll variance board pack: fetch run, compute "
                "variance vs prior month, branch escalate if >2%, critic gate, "
                "export docx/xlsx pack for Finance."
            ),
            "plan_id": "demo-plan-payroll-board",
            "related_object": {
                "type": "people.PayrollRun",
                "id": "oct-2026",
                "label": "October 2026 payroll",
            },
            "layers": {
                "intent": {
                    "ask": "October payroll variance board pack for Finance",
                    "success_criteria": (
                        "Pack exported only after critic pass; escalate path "
                        "taken when variance_pct > 2.0"
                    ),
                    "contract": "agent",
                },
                "job_map": {
                    "steps": [
                        {
                            "id": "1",
                            "title": "Fetch October payroll run + headcount",
                            "tool": "resolve_entity",
                            "status": "completed",
                            "depends_on": [],
                        },
                        {
                            "id": "2",
                            "title": "Compute MoM variance + GOSI exposure",
                            "tool": "aggregate_entity",
                            "status": "completed",
                            "depends_on": ["1"],
                        },
                        {
                            "id": "3",
                            "title": "Branch: variance ≤ 2% → continue else escalate",
                            "tool": "plan_task",
                            "status": "completed",
                            "depends_on": ["2"],
                        },
                        {
                            "id": "4",
                            "title": "Critic review of board narrative",
                            "tool": "cross_synthesize",
                            "status": "completed",
                            "depends_on": ["3"],
                        },
                        {
                            "id": "5",
                            "title": "Export board pack (docx + xlsx)",
                            "tool": "export_document",
                            "status": "completed",
                            "depends_on": ["4"],
                        },
                    ],
                    "tools": [
                        "resolve_entity",
                        "aggregate_entity",
                        "plan_task",
                        "cross_synthesize",
                        "export_document",
                    ],
                    "capabilities": ["people:view", "ai:run_agent", "ai:export"],
                    "entities": [
                        {"type": "people.PayrollRun", "id": "oct-2026"},
                        {"type": "people.Employee", "metric": "headcount"},
                    ],
                },
                "live_run": {
                    "progress_pct": 100,
                    "status": "completed",
                    "qos": {
                        "acceptance_status": "met",
                        "requirements_total": 5,
                        "requirements_met": 5,
                        "requirements_partial": 0,
                        "requirements_missed": 0,
                    },
                    "blockers": [],
                    "pending_consent": None,
                },
                "evidence": {
                    "headline": "Variance 1.8% ≤ 2.0% band — escalate skipped",
                    "prose": (
                        "October closed within tolerance. GOSI exposure "
                        "KWD 184,220. Critic passed; pack allowed."
                    ),
                    "tables": [
                        {
                            "title": "Board metrics",
                            "columns": ["Metric", "Value"],
                            "rows": [
                                ["Headcount", "529"],
                                ["Variance %", "1.8"],
                                ["GOSI exposure (KWD)", "184,220"],
                                ["Active loans", "42"],
                                ["Late enrollments", "2"],
                            ],
                        }
                    ],
                    "sources": [
                        {"label": "payroll_run.oct-2026"},
                        {"label": "gosi_ledger"},
                    ],
                    "caveats": [
                        "2 late enrollment cases — HR to close by month-end"
                    ],
                },
                "outcome": {
                    "summary": (
                        "Board pack exported. Escalate branch not taken. "
                        "Finance can download from run artifacts."
                    ),
                    "sor_links": [
                        {
                            "label": "Payroll run Oct 2026",
                            "path": "/people/payroll/oct-2026",
                        }
                    ],
                    "canvas_id": "",
                },
            },
        },
        {
            "title": "Leave portfolio brief — Eslam (Chat)",
            "mode": MODE_CHAT,
            "ask": (
                "What leave does Eslam have left, by type, and any pending "
                "requests that would affect next week's draft?"
            ),
            "related_object": {
                "type": "people.Employee",
                "id": "1416",
                "label": "Eslam (demo)",
            },
            "layers": {
                "intent": {
                    "ask": "Leave entitlements + pending for Eslam",
                    "success_criteria": (
                        "Per-type balances + pending request count; advisory only"
                    ),
                    "contract": "advisory",
                },
                "job_map": {
                    "steps": [
                        {
                            "id": "1",
                            "title": "Resolve employee Eslam / 1416",
                            "tool": "resolve_entity",
                            "status": "done",
                        },
                        {
                            "id": "2",
                            "title": "List leave entitlements by type",
                            "tool": "list_leave_entitlements",
                            "status": "done",
                        },
                        {
                            "id": "3",
                            "title": "List open leave requests",
                            "tool": "list_leave_requests",
                            "status": "done",
                        },
                        {
                            "id": "4",
                            "title": "Synthesize portfolio brief",
                            "tool": "cross_synthesize",
                            "status": "done",
                        },
                    ],
                    "tools": [
                        "resolve_entity",
                        "list_leave_entitlements",
                        "list_leave_requests",
                        "cross_synthesize",
                    ],
                    "capabilities": ["people:view"],
                    "entities": [{"type": "people.Employee", "id": "1416"}],
                },
                "live_run": {
                    "progress_pct": 100,
                    "status": "complete",
                    "qos": None,
                    "blockers": [],
                },
                "evidence": {
                    "headline": "Five leave types · 1 pending request",
                    "prose": (
                        "Advisory brief only — Chat will not submit leave. "
                        "Draft next week would consume Annual."
                    ),
                    "tables": [
                        {
                            "title": "Entitlements",
                            "columns": ["Type", "Balance (d)", "Used"],
                            "rows": [
                                ["Annual", "14.5", "15.5"],
                                ["Sick", "12", "3"],
                                ["Emergency", "3", "0"],
                                ["Unpaid", "∞", "0"],
                                ["Maternity", "0", "0"],
                            ],
                        }
                    ],
                    "sources": [{"label": "leave_entitlement"}, {"label": "leave_request"}],
                    "caveats": [
                        "Pending request #8821 (Annual 3d) not yet approved"
                    ],
                },
                "outcome": {
                    "summary": (
                        "Portfolio ready for manager review. No SoR writes "
                        "from Chat mode."
                    ),
                    "sor_links": [
                        {
                            "label": "Employee 360 (demo id)",
                            "path": "/people/employees/1416",
                        }
                    ],
                    "canvas_id": "",
                },
            },
        },
        {
            "title": "DQ water rule + FlightDirector repair (Agent)",
            "mode": MODE_AGENT,
            "ask": (
                "Create DQ rule 'Water consumption > 0' on emissions fact table; "
                "FlightDirector must verify created_entity; repair if missed."
            ),
            "plan_id": "demo-plan-dq-water",
            "related_object": {
                "type": "dq.Rule",
                "id": "pending",
                "label": "Water consumption > 0",
            },
            "layers": {
                "intent": {
                    "ask": "Durable DQ rule for water consumption",
                    "success_criteria": (
                        "Rule row exists; acceptance met or escalated after ≤2 repairs"
                    ),
                    "contract": "agent",
                },
                "job_map": {
                    "steps": [
                        {
                            "id": "1",
                            "title": "Locate emissions water field",
                            "tool": "search_entity",
                            "status": "completed",
                        },
                        {
                            "id": "2",
                            "title": "Create DQ rule (mutation · consent)",
                            "tool": "create_dq_rule",
                            "status": "completed",
                        },
                        {
                            "id": "3",
                            "title": "FlightDirector re-query created_entity",
                            "tool": "host_get",
                            "status": "completed",
                        },
                        {
                            "id": "4",
                            "title": "Repair: exact field set mismatch",
                            "tool": "create_dq_rule",
                            "status": "completed",
                        },
                        {
                            "id": "5",
                            "title": "Acceptance report close",
                            "tool": "flight_acceptance",
                            "status": "completed",
                        },
                    ],
                    "tools": ["search_entity", "create_dq_rule"],
                    "capabilities": ["dq:manage", "ai:run_agent"],
                    "entities": [
                        {"type": "dataschema.DataField", "name": "water_consumption"},
                        {"type": "dq.Rule", "name": "Water consumption > 0"},
                    ],
                },
                "live_run": {
                    "progress_pct": 100,
                    "status": "partial",
                    "qos": {
                        "acceptance_status": "partial",
                        "requirements_total": 3,
                        "requirements_met": 2,
                        "requirements_partial": 1,
                        "requirements_missed": 0,
                    },
                    "blockers": [],
                    "pending_consent": None,
                },
                "evidence": {
                    "headline": "Rule created after 1 repair · table_fields partial",
                    "prose": (
                        "First create missed exact field set; FlightDirector "
                        "injected repair instructions with actual missing/extra "
                        "diff. Mutation never auto-re-run without consent."
                    ),
                    "tables": [
                        {
                            "title": "Acceptance",
                            "columns": ["Requirement", "Verdict"],
                            "rows": [
                                ["created_entity rule", "met"],
                                ["table_fields exact set", "partial"],
                                ["artifact export", "met"],
                            ],
                        }
                    ],
                    "sources": [{"label": "dq/rules"}, {"label": "flight.acceptance"}],
                    "caveats": [
                        "Partial = field set still has 1 extra column vs brief"
                    ],
                },
                "outcome": {
                    "summary": (
                        "Rule id 129 live. Human may tighten field set; "
                        "learning pattern queued for playbook."
                    ),
                    "sor_links": [
                        {"label": "DQ rules", "path": "/admin/dq/rules"}
                    ],
                    "canvas_id": "",
                },
            },
        },
        {
            "title": "GradeVance OSCE run — LCT HITL (Agent)",
            "mode": MODE_AGENT,
            "ask": (
                "Mark reflective OSCE segment with LCT Semantics (SG/SD), open "
                "HITL edit drawer, gate on mean confidence, release for AGS dry-run."
            ),
            "plan_id": "demo-plan-gv-osce",
            "related_object": {
                "type": "gradevance.AssessmentRun",
                "id": "demo-osce-1",
                "label": "OSCE reflective · demo",
            },
            "layers": {
                "intent": {
                    "ask": "Formative OSCE mark + HITL + release ceremony",
                    "success_criteria": (
                        "All segments coded; mean confidence ≥ gate; released=true"
                    ),
                    "contract": "agent",
                },
                "job_map": {
                    "steps": [
                        {
                            "id": "1",
                            "title": "Load run + assignment pack",
                            "tool": "gradevance_fetch_run",
                            "status": "completed",
                        },
                        {
                            "id": "2",
                            "title": "Auto LCT codes (SG / SD)",
                            "tool": "gradevance_lct_code",
                            "status": "completed",
                        },
                        {
                            "id": "3",
                            "title": "HITL ExpertEdit on segment 2 SG",
                            "tool": "gradevance_expert_edit",
                            "status": "completed",
                        },
                        {
                            "id": "4",
                            "title": "Confidence gate + release",
                            "tool": "gradevance_release",
                            "status": "completed",
                        },
                        {
                            "id": "5",
                            "title": "AGS passback dry-run",
                            "tool": "gradevance_ags_preview",
                            "status": "completed",
                        },
                    ],
                    "tools": [
                        "gradevance_fetch_run",
                        "gradevance_lct_code",
                        "gradevance_expert_edit",
                        "gradevance_release",
                        "gradevance_ags_preview",
                    ],
                    "capabilities": [
                        "gradevance:mark",
                        "gradevance:release",
                        "ai:run_agent",
                    ],
                    "entities": [
                        {
                            "type": "gradevance.AssessmentRun",
                            "id": "demo-osce-1",
                        }
                    ],
                },
                "live_run": {
                    "progress_pct": 100,
                    "status": "completed",
                    "qos": {
                        "acceptance_status": "met",
                        "requirements_total": 4,
                        "requirements_met": 4,
                        "requirements_partial": 0,
                        "requirements_missed": 0,
                    },
                    "blockers": [],
                    "pending_consent": None,
                },
                "evidence": {
                    "headline": "Released · mean conf 0.86 · gate pass",
                    "prose": (
                        "ExpertEdit on seg2 SG+ → SG- with rationale captured "
                        "for proposal miner."
                    ),
                    "tables": [
                        {
                            "title": "Segments",
                            "columns": ["#", "SG", "SD", "Conf"],
                            "rows": [
                                ["1", "SG+", "SD-", "0.91"],
                                ["2", "SG-", "SD+", "0.78"],
                                ["3", "SG+", "SD-", "0.88"],
                            ],
                        }
                    ],
                    "sources": [
                        {"label": "lct_device"},
                        {"label": "expert_edit"},
                    ],
                    "caveats": ["AGS passback was dry-run only"],
                },
                "outcome": {
                    "summary": (
                        "Run released. Learning loop may draft a Proposal from "
                        "ExpertEdit."
                    ),
                    "sor_links": [
                        {
                            "label": "Run workbench",
                            "path": "/apps/gradevance/runs/demo-osce-1",
                        }
                    ],
                    "canvas_id": "",
                },
            },
        },
        {
            "title": "Kuwaitization headcount + trust-ranked catalog (Chat)",
            "mode": MODE_CHAT,
            "ask": (
                "How many Kuwaiti vs non-Kuwaiti employees, and which catalog "
                "assets should I trust for the headcount definition?"
            ),
            "layers": {
                "intent": {
                    "ask": "Kuwaitization split + trusted headcount definition",
                    "success_criteria": (
                        "Counts by nationality band + top trust_tier assets cited"
                    ),
                    "contract": "advisory",
                },
                "job_map": {
                    "steps": [
                        {
                            "id": "1",
                            "title": "Aggregate headcount by nationality",
                            "tool": "aggregate_entity",
                            "status": "done",
                        },
                        {
                            "id": "2",
                            "title": "Search catalog for headcount definition",
                            "tool": "api_catalog_search",
                            "status": "done",
                        },
                        {
                            "id": "3",
                            "title": "Rank assets by trust_index",
                            "tool": "api_catalog_search",
                            "status": "done",
                        },
                        {
                            "id": "4",
                            "title": "Compose advisory brief",
                            "tool": "cross_synthesize",
                            "status": "done",
                        },
                    ],
                    "tools": [
                        "aggregate_entity",
                        "api_catalog_search",
                        "cross_synthesize",
                    ],
                    "capabilities": ["people:view", "catalog:view"],
                    "entities": [{"type": "people.Employee"}],
                },
                "live_run": {
                    "progress_pct": 100,
                    "status": "complete",
                    "qos": None,
                    "blockers": [],
                },
                "evidence": {
                    "headline": "529 headcount · 41% Kuwaiti · trust A assets preferred",
                    "prose": (
                        "Counts use Employee.is_active. Catalog trust_tier=A "
                        "definition preferred over stale warehouse views."
                    ),
                    "tables": [
                        {
                            "title": "Nationality band",
                            "columns": ["Band", "Count", "%"],
                            "rows": [
                                ["Kuwaiti", "217", "41.0"],
                                ["GCC", "38", "7.2"],
                                ["Other", "274", "51.8"],
                            ],
                        },
                        {
                            "title": "Catalog assets (trust)",
                            "columns": ["Asset", "Tier", "Index"],
                            "rows": [
                                ["emp_headcount_def", "A", "0.94"],
                                ["hr_snapshot_v3", "B", "0.71"],
                                ["legacy_payroll_hdct", "C", "0.42"],
                            ],
                        },
                    ],
                    "sources": [
                        {"label": "people.Employee"},
                        {"label": "catalog.AssetProfile.trust_index"},
                    ],
                    "caveats": [
                        "Trust Index grounding is advisory until Pulse ranks live"
                    ],
                },
                "outcome": {
                    "summary": (
                        "Prefer emp_headcount_def (A). Do not use "
                        "legacy_payroll_hdct for board reporting."
                    ),
                    "sor_links": [
                        {"label": "Catalog search", "path": "/admin/catalog"}
                    ],
                    "canvas_id": "",
                },
            },
        },
        {
            "title": "Consent-gated compensation deny (Agent · blocked)",
            "mode": MODE_AGENT,
            "ask": (
                "Deny compensation adjustment for employee 333 — must stage "
                "consent; Chat must never mutate."
            ),
            "plan_id": "demo-plan-comp-deny",
            "related_object": {
                "type": "people.Employee",
                "id": "333",
                "label": "Employee 333 (demo)",
            },
            "layers": {
                "intent": {
                    "ask": "Deny compensation adjustment with consent",
                    "success_criteria": (
                        "Mutation staged; human grant; SoR deny recorded"
                    ),
                    "contract": "agent",
                },
                "job_map": {
                    "steps": [
                        {
                            "id": "1",
                            "title": "Resolve employee 333",
                            "tool": "resolve_entity",
                            "status": "completed",
                        },
                        {
                            "id": "2",
                            "title": "Load open compensation request",
                            "tool": "list_compensation_requests",
                            "status": "completed",
                        },
                        {
                            "id": "3",
                            "title": "Stage deny mutation (consent)",
                            "tool": "deny_compensation_request",
                            "status": "blocked",
                        },
                        {
                            "id": "4",
                            "title": "Audit ledger entry",
                            "tool": "write_audit",
                            "status": "pending",
                        },
                    ],
                    "tools": [
                        "resolve_entity",
                        "list_compensation_requests",
                        "deny_compensation_request",
                    ],
                    "capabilities": ["people:manage_compensation", "ai:run_agent"],
                    "entities": [{"type": "people.Employee", "id": "333"}],
                },
                "live_run": {
                    "progress_pct": 50,
                    "status": "blocked",
                    "qos": {
                        "acceptance_status": "missed",
                        "requirements_total": 2,
                        "requirements_met": 1,
                        "requirements_partial": 0,
                        "requirements_missed": 1,
                    },
                    "blockers": [
                        "RULE_21: deny_compensation_request awaiting human consent"
                    ],
                    "pending_consent": {
                        "tool": "deny_compensation_request",
                        "reason": "Compensation deny is irreversible SoR write",
                    },
                },
                "evidence": {
                    "headline": "Paused on consent — no SoR write yet",
                    "prose": (
                        "Agent correctly staged the deny. Approver must grant "
                        "in the run surface before step 3 executes."
                    ),
                    "tables": [
                        {
                            "title": "Request",
                            "columns": ["Field", "Value"],
                            "rows": [
                                ["Request id", "CR-4412"],
                                ["Amount (KWD)", "120"],
                                ["Status", "pending_manager"],
                            ],
                        }
                    ],
                    "sources": [{"label": "compensation_request"}],
                    "caveats": ["Chat mode would refuse this mutation entirely"],
                },
                "outcome": {
                    "summary": "Waiting on human grant. Job Map stays reopenable.",
                    "sor_links": [
                        {
                            "label": "Employee 333",
                            "path": "/people/employees/333",
                        }
                    ],
                    "canvas_id": "",
                },
            },
        },
    ]


class Command(BaseCommand):
    help = "Seed complex Ops Canvas Job Map examples for Pulse Artifacts."

    def add_arguments(self, parser):
        parser.add_argument(
            "--user",
            default="ahmed",
            help="Username that owns the demo conversation (default: ahmed)",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete prior demo conversation + its job_map artifacts first",
        )

    def handle(self, *args, **options):
        username = options["user"]
        User = get_user_model()
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist as exc:
            raise CommandError(f"User {username!r} not found") from exc

        if options["reset"]:
            old = AIConversation.objects.filter(user=user, title=DEMO_CONV_TITLE)
            n_art = AIArtifact.objects.filter(
                conversation__in=old, artifact_type=ARTIFACT_TYPE
            ).count()
            deleted, _ = old.delete()
            self.stdout.write(
                self.style.WARNING(
                    f"Reset: removed {deleted} conversation row(s), ~{n_art} maps"
                )
            )

        conv, created = AIConversation.objects.get_or_create(
            user=user,
            title=DEMO_CONV_TITLE,
            defaults={
                "conversation_type": "chat",
                "status": "active",
            },
        )
        if created:
            self.stdout.write(f"Created conversation {conv.id}")
        else:
            self.stdout.write(f"Reusing conversation {conv.id}")

        # Drop prior demo maps on this conversation (idempotent re-seed).
        AIArtifact.objects.filter(
            conversation=conv, artifact_type=ARTIFACT_TYPE
        ).delete()

        created_ids = []
        for ex in _examples():
            payload = build_payload(
                mode=ex["mode"],
                ask=ex["ask"],
                layers=ex.get("layers"),
                related_object=ex.get("related_object"),
                plan_id=ex.get("plan_id"),
                conversation_id=str(conv.id),
                title=ex["title"],
            )
            art = AIArtifact.objects.create(
                conversation=conv,
                created_by=user,
                title=ex["title"][:255],
                artifact_type=ARTIFACT_TYPE,
                content_json=payload,
                visibility="private",
            )
            content = dict(art.content_json or {})
            layers = dict(content.get("layers") or {})
            outcome = dict(layers.get("outcome") or {})
            outcome["canvas_id"] = str(art.id)
            layers["outcome"] = outcome
            content["layers"] = layers
            art.content_json = content
            art.save(update_fields=["content_json"])
            created_ids.append(str(art.id))
            self.stdout.write(f"  · {art.title}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(created_ids)} Job Maps on conversation {conv.id}. "
                f"Open Pulse → Artifacts → Job Maps."
            )
        )
