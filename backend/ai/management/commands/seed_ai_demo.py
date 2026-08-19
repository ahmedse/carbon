"""Seed deterministic demo data for the AI Admin console panels + Phase E graph.

One idempotent command. Default behaviour upserts by natural key (safe to
re-run); ``--reset`` deletes all seeded ``ai`` rows first, then reseeds.

Usage:
    python manage.py seed_ai_demo            # upsert (idempotent)
    python manage.py seed_ai_demo --reset    # wipe seeded ai rows, reseed

Data is carbon-domain themed (AASTMT campus electricity / water / chilled
water) and deliberately references only string ids created in this command,
so the Phase E graph endpoint resolves every edge without dangling nodes.
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.timezone import now

from ai.models.core import (
    Agent,
    AgentHandoff,
    AuditLog,
    Feedback,
    Instance,
    Insight,
    KgEdge,
    KgNode,
    KnowledgeEntity,
    LLMCallLog,
    MemoryEpisodic,
    MemoryLongTerm,
    Notification,
    OpsRun,
    PlaybookBlock,
    PromptVersion,
    Skill,
    SkillAdmissionLog,
    TaskExecution,
    ToolExecution,
)
from ai.models.knowledge_graph import (
    KgFeedbackRecord,
    KgRecoveryLog,
    KnowledgeEdge,
    KnowledgeNode,
)

# Models this command seeds (deleted in this order by --reset).
SEEDED_MODELS = [
    KnowledgeEdge,
    KgEdge,
    AgentHandoff,
    SkillAdmissionLog,
    KgFeedbackRecord,
    KgRecoveryLog,
    TaskExecution,
    ToolExecution,
    Feedback,
    LLMCallLog,
    AuditLog,
    Notification,
    OpsRun,
    PlaybookBlock,
    PromptVersion,
    Insight,
    KnowledgeEntity,
    MemoryEpisodic,
    MemoryLongTerm,
    Skill,
    Agent,
    KnowledgeNode,
    KgNode,
    Instance,
]

# (key, node_type, name, description, confidence, verified)
NODE_SPECS = [
    ("tbl_elec", "Table", "monthly_electricity",
     "Monthly electricity consumption in kWh per building.", 0.95, True),
    ("tbl_water", "Table", "monthly_water",
     "Monthly water consumption in m\u00b3 per building.", 0.95, True),
    ("tbl_chw", "Table", "monthly_chilled_water",
     "Monthly chilled water consumption in ton-hours (TR).", 0.95, True),
    ("fld_kwh", "Field", "total_kwh",
     "Total kilowatt-hours consumed.", 0.9, True),
    ("fld_m3", "Field", "total_m3",
     "Total cubic meters of water consumed.", 0.9, True),
    ("fld_tr", "Field", "total_tr",
     "Total ton-hours of chilled water.", 0.9, True),
    ("fld_month", "Field", "month",
     "Reporting month (YYYY-MM).", 0.98, True),
    ("fld_bldg", "Field", "building_id",
     "Building identifier the reading belongs to.", 0.85, False),
    ("met_s2", "Metric", "Scope 2 Emissions",
     "Indirect emissions from purchased electricity and chilled water.", 0.9, True),
    ("met_s3", "Metric", "Scope 3 Emissions",
     "Other indirect emissions including purchased water.", 0.85, False),
    ("con_elec", "Concept", "Electricity Consumption",
     "Energy drawn from the grid, measured in kWh.", 0.92, True),
    ("con_water", "Concept", "Water Consumption",
     "Water usage, measured in m\u00b3.", 0.92, True),
    ("con_chw", "Concept", "Chilled Water",
     "District chilled water used for cooling, in TR.", 0.9, True),
    ("con_gf", "Concept", "Grid Emission Factor",
     "kgCO\u2082e per kWh for grid electricity.", 0.8, False),
    ("con_wf", "Concept", "Water Emission Factor",
     "kgCO\u2082e per m\u00b3 for water supply.", 0.75, False),
    ("con_ci", "Concept", "Carbon Intensity",
     "Normalised emissions intensity for reporting.", 0.8, False),
    ("org_aastmt", "Organization", "AASTMT",
     "Arab Academy for Science, Technology & Maritime Transport.", 0.99, True),
    ("org_fu", "Organization", "Facilities & Utilities",
     "Facilities and utilities department.", 0.9, True),
]

# (source_key, target_key, relationship, weight, confidence)
EDGE_SPECS = [
    # table -> field: HAS_FIELD
    ("tbl_elec", "fld_kwh", "HAS_FIELD", 0.95, 0.98),
    ("tbl_elec", "fld_month", "HAS_FIELD", 0.9, 0.98),
    ("tbl_elec", "fld_bldg", "HAS_FIELD", 0.85, 0.9),
    ("tbl_water", "fld_m3", "HAS_FIELD", 0.95, 0.98),
    ("tbl_water", "fld_month", "HAS_FIELD", 0.9, 0.98),
    ("tbl_chw", "fld_tr", "HAS_FIELD", 0.95, 0.98),
    ("tbl_chw", "fld_month", "HAS_FIELD", 0.9, 0.98),
    # table -> concept: MEASURED_BY
    ("tbl_elec", "con_elec", "MEASURED_BY", 0.9, 0.95),
    ("tbl_water", "con_water", "MEASURED_BY", 0.9, 0.95),
    ("tbl_chw", "con_chw", "MEASURED_BY", 0.9, 0.95),
    # concept -> metric: CONTRIBUTES_TO
    ("con_elec", "met_s2", "CONTRIBUTES_TO", 0.9, 0.9),
    ("con_water", "met_s3", "CONTRIBUTES_TO", 0.85, 0.85),
    ("con_chw", "met_s2", "CONTRIBUTES_TO", 0.9, 0.9),
    # metric -> factor: CALCULATED_FROM
    ("met_s2", "con_gf", "CALCULATED_FROM", 0.9, 0.85),
    ("met_s3", "con_wf", "CALCULATED_FROM", 0.85, 0.8),
    ("met_s2", "con_ci", "CALCULATED_FROM", 0.7, 0.75),
    ("met_s3", "con_ci", "CALCULATED_FROM", 0.7, 0.75),
    # org -> table: OWNED_BY
    ("org_aastmt", "tbl_elec", "OWNED_BY", 0.95, 0.98),
    ("org_aastmt", "tbl_water", "OWNED_BY", 0.95, 0.98),
    ("org_aastmt", "tbl_chw", "OWNED_BY", 0.95, 0.98),
    ("org_fu", "tbl_elec", "OWNED_BY", 0.8, 0.85),
    ("org_fu", "tbl_water", "OWNED_BY", 0.8, 0.85),
    ("org_fu", "tbl_chw", "OWNED_BY", 0.8, 0.85),
    # table -> metric: EMITS
    ("tbl_elec", "met_s2", "EMITS", 0.95, 0.95),
    ("tbl_chw", "met_s2", "EMITS", 0.9, 0.9),
    ("tbl_water", "met_s3", "EMITS", 0.85, 0.85),
]

# (key, type, name)
KG_NODE_SPECS = [
    ("kg_campus", "entity", "AASTMT Campus"),
    ("kg_abuqir", "entity", "Abu Qir"),
    ("kg_emeter", "entity", "Electricity Meter"),
    ("kg_wmeter", "entity", "Water Meter"),
    ("kg_kwh", "attribute", "Total KWh"),
    ("kg_m3", "attribute", "Total M3"),
]

# (source_key, target_key, edge_type)
KG_EDGE_SPECS = [
    ("kg_campus", "kg_abuqir", "related_to"),
    ("kg_campus", "kg_emeter", "has"),
    ("kg_campus", "kg_wmeter", "has"),
    ("kg_emeter", "kg_kwh", "has"),
    ("kg_wmeter", "kg_m3", "has"),
]

PANEL_ORDER = [
    "Instance", "KnowledgeNode", "KnowledgeEdge", "KgNode", "KgEdge",
    "KnowledgeEntity", "Insight", "MemoryLongTerm", "MemoryEpisodic",
    "Agent", "AgentHandoff", "ToolExecution", "TaskExecution",
    "Skill", "SkillAdmissionLog", "PromptVersion", "PlaybookBlock",
    "Feedback", "KgFeedbackRecord", "OpsRun", "KgRecoveryLog",
    "Notification", "AuditLog", "LLMCallLog",
]


class Command(BaseCommand):
    help = "Seed idempotent demo data for the AI Admin console (--reset to wipe first)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete all seeded ai demo rows before reseeding.",
        )

    def handle(self, *args, **options):
        self._counts = {}  # panel -> (total, created)
        with transaction.atomic():
            if options.get("reset"):
                self._reset()
            self._seed_all()
        self._summarize()

    # ── helpers ────────────────────────────────────────────────────────────

    def _upsert(self, model_cls, panel, defaults, **lookup):
        """get_or_create by natural key, tracking per-panel counts."""
        obj, created = model_cls.objects.get_or_create(defaults=defaults, **lookup)
        total, new = self._counts.get(panel, (0, 0))
        self._counts[panel] = (total + 1, new + (1 if created else 0))
        return obj

    def _reset(self):
        for model in SEEDED_MODELS:
            model.objects.all().delete()
        self.stdout.write(self.style.WARNING("Cleared seeded ai demo rows."))

    def _summarize(self):
        self.stdout.write(self.style.SUCCESS("AI demo seed complete."))
        for panel in PANEL_ORDER:
            total, new = self._counts.get(panel, (0, 0))
            self.stdout.write(f"  {panel:<20} total={total:<4} new={new}")

    # ── seeders ────────────────────────────────────────────────────────────

    def _seed_all(self):
        instance = self._seed_instance()
        nodes = self._seed_knowledge_nodes(instance)
        self._seed_knowledge_edges(instance, nodes)
        kg_nodes = self._seed_kg_nodes(instance)
        self._seed_kg_edges(instance, kg_nodes)
        self._seed_knowledge(instance)
        self._seed_memory(instance)
        agents = self._seed_agents(instance)
        self._seed_agent_handoffs(agents)
        self._seed_tools(instance)
        self._seed_skills(instance)
        self._seed_prompts(instance)
        self._seed_feedback(instance)
        self._seed_learning(instance)
        self._seed_monitoring(instance)
        self._seed_audit()
        self._seed_llm_logs(instance)

    def _seed_instance(self):
        from django.conf import settings as dj_settings

        platform_name = (
            getattr(dj_settings, "PLATFORM_TITLE", "")
            or getattr(dj_settings, "PLATFORM_NAME", "")
            or "Data Trust Platform"
        )
        return self._upsert(
            Instance,
            "Instance",
            defaults={
                "display_name": platform_name,
                "host_db_url": "postgresql://carbon:****@localhost:5432/carbon",
                "host_api_url": "http://127.0.0.1:8009",
                "status": "active",
                "config": {"llm": {"model": "gpt-4o"}, "budget_usd": 5.0},
                "visibility": "shared",
            },
            name="carbon-demo",
        )

    def _seed_knowledge_nodes(self, instance):
        nodes = {}
        for key, node_type, name, description, confidence, verified in NODE_SPECS:
            nodes[key] = self._upsert(
                KnowledgeNode,
                "KnowledgeNode",
                defaults={
                    "node_type": node_type,
                    "description": description,
                    "confidence": confidence,
                    "verified": verified,
                    "visibility": "shared",
                },
                instance_id=instance.id,
                name=name,
            )
        return nodes

    def _seed_knowledge_edges(self, instance, nodes):
        for src_key, tgt_key, relationship, weight, confidence in EDGE_SPECS:
            self._upsert(
                KnowledgeEdge,
                "KnowledgeEdge",
                defaults={
                    "weight": weight,
                    "confidence": confidence,
                    "visibility": "shared",
                },
                instance_id=instance.id,
                source_node_id=nodes[src_key].id,
                target_node_id=nodes[tgt_key].id,
                relationship=relationship,
            )

    def _seed_kg_nodes(self, instance):
        kg_nodes = {}
        for key, type_, name in KG_NODE_SPECS:
            kg_nodes[key] = self._upsert(
                KgNode,
                "KgNode",
                defaults={"type": type_, "visibility": "shared"},
                instance_id=instance.id,
                name=name,
            )
        return kg_nodes

    def _seed_kg_edges(self, instance, kg_nodes):
        for src_key, tgt_key, edge_type in KG_EDGE_SPECS:
            self._upsert(
                KgEdge,
                "KgEdge",
                defaults={"visibility": "shared"},
                instance_id=instance.id,
                source_node_id=kg_nodes[src_key].id,
                target_node_id=kg_nodes[tgt_key].id,
                edge_type=edge_type,
            )

    def _seed_knowledge(self, instance):
        entities = [
            ("table", "monthly_electricity",
             "Monthly electricity consumption per building in kWh."),
            ("metric", "Scope 2 Emissions",
             "Indirect emissions from purchased electricity and chilled water."),
            ("glossary", "Grid Emission Factor",
             "kgCO\u2082e per kWh conversion factor for grid electricity."),
        ]
        for entity_type, name, desc in entities:
            self._upsert(
                KnowledgeEntity,
                "KnowledgeEntity",
                defaults={
                    "semantic_description": desc,
                    "visibility": "shared",
                },
                instance_id=instance.id,
                entity_type=entity_type,
                name=name,
            )

        insights = [
            ("anomaly", "Electricity spike detected",
             "July 2024 electricity usage was 42% above the trailing 6-month average, concentrated in building 2401.", 0.88),
            ("efficiency", "Chilled water intensity improving",
             "Chilled water ton-hours per square meter fell 8% quarter-over-quarter.", 0.82),
            ("trend", "Water consumption declining",
             "Campus water consumption trended downward 12% year-over-year.", 0.9),
        ]
        for insight_type, title, content, confidence in insights:
            self._upsert(
                Insight,
                "Insight",
                defaults={
                    "content": content,
                    "confidence": confidence,
                    "visibility": "shared",
                },
                instance_id=instance.id,
                insight_type=insight_type,
                title=title,
            )

    def _seed_memory(self, instance):
        long_term = [
            ("domain", "AASTMT electricity totals are reported in kWh per building per month.", 0.95),
            ("domain", "Scope 2 covers purchased electricity and district chilled water; Scope 3 includes purchased water.", 0.9),
            ("preference", "User prefers monthly aggregations with year-over-year deltas.", 0.8),
        ]
        for category, content, confidence in long_term:
            self._upsert(
                MemoryLongTerm,
                "MemoryLongTerm",
                defaults={"confidence": confidence, "visibility": "shared"},
                instance_id=instance.id,
                category=category,
                content=content,
            )

        episodic = [
            ("user_query", "User asked for Scope 2 emissions by month for FY 2024."),
            ("graph_build", "Knowledge graph rebuilt from catalog schema tables."),
            ("tool_call", "Generated and executed SQL for the monthly electricity rollup."),
        ]
        for event_type, summary in episodic:
            self._upsert(
                MemoryEpisodic,
                "MemoryEpisodic",
                defaults={"occurred_at": now(), "visibility": "shared"},
                instance_id=instance.id,
                event_type=event_type,
                summary=summary,
            )

    def _seed_agents(self, instance):
        agents = {}
        specs = [
            ("carbon-planner", "planner"),
            ("carbon-analyst", "analyst"),
            ("carbon-reviewer", "critic"),
        ]
        for name, role in specs:
            agents[name] = self._upsert(
                Agent,
                "Agent",
                defaults={"role": role, "visibility": "shared"},
                instance_id=instance.id,
                name=name,
            )
        return agents

    def _seed_agent_handoffs(self, agents):
        handoffs = [
            ("carbon-planner", "carbon-analyst",
             "Planner delegates rollup tasks to the analyst."),
            ("carbon-analyst", "carbon-reviewer",
             "Analyst hands results to the reviewer for critique."),
        ]
        for from_name, to_name, description in handoffs:
            self._upsert(
                AgentHandoff,
                "AgentHandoff",
                defaults={"description": description, "visibility": "shared"},
                from_agent_id=agents[from_name].id,
                to_agent_id=agents[to_name].id,
            )

    def _seed_tools(self, instance):
        tools = [
            ("conv-demo-1", "query_sql", "completed"),
            ("conv-demo-2", "write_csv", "completed"),
        ]
        for conversation_id, tool_name, status in tools:
            self._upsert(
                ToolExecution,
                "ToolExecution",
                defaults={"status": status, "visibility": "shared"},
                conversation_id=conversation_id,
                tool_name=tool_name,
            )

        tasks = [
            ("schema_introspection", "task-demo-1", "succeeded",
             {"tables": ["monthly_electricity"]}, {"nodes": 18, "edges": 26}),
            ("emissions_rollup", "task-demo-2", "succeeded",
             {"scope": "2", "year": 2024}, {"kg_co2e": 123456.7}),
        ]
        for task_type, external_task_id, status, req, resp in tasks:
            self._upsert(
                TaskExecution,
                "TaskExecution",
                defaults={
                    "task_type": task_type,
                    "status": status,
                    "request_payload": req,
                    "response_payload": resp,
                    "visibility": "shared",
                },
                instance_id=instance.id,
                external_task_id=external_task_id,
            )

    def _seed_skills(self, instance):
        skills = {}
        specs = [
            ("rollup_monthly_emissions", "sql",
             "Rolls up monthly consumption into Scope 2/3 emissions."),
            ("detect_emissions_anomaly", "analysis",
             "Flags anomalous monthly consumption vs trailing average."),
        ]
        for name, kind, description in specs:
            skills[name] = self._upsert(
                Skill,
                "Skill",
                defaults={
                    "kind": kind,
                    "author_user_id": "demo-user",
                    "status": "active",
                    "description": description,
                    "visibility": "shared",
                },
                instance_id=instance.id,
                name=name,
            )

        for name in skills:
            self._upsert(
                SkillAdmissionLog,
                "SkillAdmissionLog",
                defaults={
                    "structural_passed": True,
                    "harmlessness_passed": True,
                    "consistency_passed": True,
                    "marginal_gain_passed": True,
                    "verdict": "admitted",
                    "admitted_by": "demo-user",
                    "visibility": "shared",
                },
                skill_id=skills[name].id,
                instance_id=instance.id,
            )

    def _seed_prompts(self, instance):
        from django.conf import settings as dj_settings

        platform_name = (
            getattr(dj_settings, "PLATFORM_TITLE", "")
            or getattr(dj_settings, "PLATFORM_NAME", "")
            or "Data Trust Platform"
        )
        prompts = [
            (f"You are a data assistant for {platform_name}. Answer using only the knowledge graph and catalog schema.", "demo-hash-000001"),
            ("Given a user question about emissions, decompose it into data queries and explain each step.", "demo-hash-000002"),
        ]
        for prompt_text, content_hash in prompts:
            self._upsert(
                PromptVersion,
                "PromptVersion",
                defaults={"prompt_text": prompt_text, "visibility": "shared"},
                instance_id=instance.id,
                content_hash=content_hash,
            )

        self._upsert(
            PlaybookBlock,
            "PlaybookBlock",
            defaults={
                "title": "Scope 2 calculation",
                "content": "When computing Scope 2, sum electricity kWh \u00d7 grid factor plus chilled water TR \u00d7 cooling factor.",
                "visibility": "shared",
            },
            instance_id=instance.id,
            block_type="instruction",
        )

    def _seed_feedback(self, instance):
        feedback = [
            ("msg-demo-1", 5, "Thanks, exactly what I needed."),
            ("msg-demo-2", 4, "Please include building-level breakdown next time."),
        ]
        for message_id, rating, correction_text in feedback:
            self._upsert(
                Feedback,
                "Feedback",
                defaults={
                    "rating": rating,
                    "correction_text": correction_text,
                    "visibility": "shared",
                },
                message_id=message_id,
            )

        kg_records = [
            ("conv-demo-1", "thumbs_up", "Show me Scope 2 emissions by month",
             "SELECT month, SUM(total_kwh) FROM monthly_electricity GROUP BY month"),
            ("conv-demo-2", "thumbs_down", "Compare water usage across buildings", ""),
        ]
        for conversation_id, signal_type, utterance, sql in kg_records:
            self._upsert(
                KgFeedbackRecord,
                "KgFeedbackRecord",
                defaults={
                    "original_utterance": utterance,
                    "generated_sql": sql,
                    "visibility": "shared",
                },
                instance_id=instance.id,
                conversation_id=conversation_id,
                signal_type=signal_type,
            )

    def _seed_learning(self, instance):
        runs = [
            ("monthly_emissions_rollup", 36),
            ("knowledge_graph_bootstrap", 18),
        ]
        for workflow, rows in runs:
            self._upsert(
                OpsRun,
                "OpsRun",
                defaults={
                    "status": "completed",
                    "rows_ingested": rows,
                    "visibility": "shared",
                },
                instance_id=instance.id,
                workflow=workflow,
            )

        self._upsert(
            KgRecoveryLog,
            "KgRecoveryLog",
            defaults={
                "error_type": "ambiguous_column",
                "recovery_type": "schema_disambiguation",
                "original_sql": "SELECT month, total FROM t",
                "repaired_sql": "SELECT month, total_kwh FROM monthly_electricity",
                "succeeded": True,
                "visibility": "shared",
            },
            instance_id=instance.id,
            question="Total kWh by month",
        )

    def _seed_monitoring(self, instance):
        notifications = [
            ("info", "Knowledge graph refreshed"),
            ("warning", "Monthly electricity data missing for July"),
        ]
        for severity, title in notifications:
            self._upsert(
                Notification,
                "Notification",
                defaults={"visibility": "shared"},
                instance_id=instance.id,
                severity=severity,
                title=title,
            )
        # Insight rows are already >= 2 from the knowledge panel; nothing to add.

    def _seed_audit(self):
        logs = [
            ("seed_ai_demo", "system", "seed", "Instance:carbon-demo"),
            ("demo-user", "user", "query", "KnowledgeGraph"),
            ("carbon-analyst", "agent", "generate_sql", "monthly_electricity"),
        ]
        for actor, actor_type, action, target in logs:
            self._upsert(
                AuditLog,
                "AuditLog",
                defaults={"visibility": "shared"},
                actor=actor,
                actor_type=actor_type,
                action=action,
                target=target,
            )

    def _seed_llm_logs(self, instance):
        calls = [
            ("conv-demo-1", "gpt-4o", 1250, 0.03, 1200),
            ("conv-demo-2", "gpt-4o", 980, 0.02, 950),
            ("conv-demo-3", "gpt-4o-mini", 540, 0.005, 410),
        ]
        for conversation_id, model_name, tokens, cost, duration in calls:
            self._upsert(
                LLMCallLog,
                "LLMCallLog",
                defaults={
                    "total_tokens": tokens,
                    "cost_usd": cost,
                    "duration_ms": duration,
                    "visibility": "shared",
                },
                instance_id=instance.id,
                conversation_id=conversation_id,
                model=model_name,
            )
