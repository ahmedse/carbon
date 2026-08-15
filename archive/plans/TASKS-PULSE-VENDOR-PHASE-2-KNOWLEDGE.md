# TASKS.md — Pulse Vendoring Phase 2: Migrate System-of-Intelligence Modules

**Status:** FINAL — finalized by Master Architect 2026-08-12 after Phase 1 (engine vendor) landed (`3ec6def`).
**Role:** Backend Worker
**Model:** DeepSeek-V3
**Domain:** backend
**Prerequisite:** `TASKS-PULSE-VENDOR-PHASE-1-ENGINE.md` completed (engine is in-hand + inert at `backend/ai/engine/`).

**Primary context:** `.ai-toolkit/decisions/0007-pulse-inhand-stateless-engine.md`, `docs/AI_INTELLIGENCE_ARCHITECTURE.md` (knowledge/learning loop, CBAC).

## Objective

Two things, in one phase:
1. **Swap the persistence seam.** Replace `engine/core/database.py` (SQLAlchemy session
   factory) with a `Store` interface. Provide two implementations: in-memory (per-task
   working memory — the "stateless" contract) and Django ORM (durable, CBAC-partitioned).
   Re-model the engine's **49 tables** as Django models in `backend/ai/models/`
   (one migration namespace, per ADR-0008 — NO new Django apps).
2. **Wire the engine in-process.** Point `backend/ai/providers/pulse.py` at the in-hand
   engine; retire the HTTP path; remove `AI_PROVIDER_CLASS` runtime swapping.

This is what actually makes the engine **stateless + Carbon-owned** (ADR-0007/0009).
Every durable query is scoped by `app_identifier` + org subtree.

## Modules to migrate (from `/home/ahmed/clearturn/pulse`)

All as packages under `backend/ai/` — models into `backend/ai/models/`, one migration namespace:

| Pulse source | Carbon destination (package) | Notes |
|---|---|---|
| `memory/` (manager.py unified retrieval) | `backend/ai/memory/` | semantic/procedural memory → Django ORM |
| `knowledge/` | `backend/ai/knowledge/` | Django ORM |
| `knowledge_graph/` | `backend/ai/graph/` | Postgres JSONB/adjacency for v1 (NOT pgvector) |
| `ingestion/` | `backend/ai/ingestion/` | re-model durable state |
| `proactive/` | `backend/ai/proactive/` | re-model durable state |
| `archetypes/` | `backend/ai/archetypes/` | re-model durable state |
| `cognition/{loop,consolidation,distillation,monitors,learned_triggers}` | `backend/ai/learning/` | learning/consolidation loop |
| feedback (accept/reject/correct) | `backend/ai/feedback/` | first-class, idempotent, revertible |

## Extensibility + portability (binding, per ADR-0008)

- **No new Django apps.** One app (`backend/ai/`), one `models/`, one `migrations/`.
- **New capability = register a tool/workflow** via `engine/agent/registry.py` +
  `tools.py` (ToolPlugin/WorkflowPlugin ABC), never a new app. MCP servers are discovered
  remote tools via `engine/agent/mcp_client.py`.
- **Zero upward imports:** `backend/ai/` imports NOTHING from catalog/mdm/dq/emissions/
  accounts/core. Domain apps plug IN via `ai/domain/{app}.py`.
- **Single facade:** all Carbon code calls `CarbonIntelligence` — never engine internals.
- **Injected deps:** config/DB/cache via a bootstrap, so the layer stays relocatable.

## Master Architect rulings (LOCKED 2026-08-12 — replaces the draft pre-work)

**R1 — Model enumeration (49 tables).** Port ALL of the vendored engine's durable
state to Django models in `backend/ai/models/` (split across `models/` sub-modules by
domain for readability, all in ONE `app_label = "ai"` migration namespace). The 34
tables in `engine/core/models.py` (instances, conversations, messages, memory_long_term,
memory_episodic, knowledge_entities, system_snapshots, notifications, feedback,
user_keys, insights, tool_executions, llm_call_logs, conversation_context_records,
audit_log, ops_runs, csv_uploads, vector_embeddings, turn_ledger, runs, run_steps,
trajectory, agents, agent_handoffs, kg_node, kg_edge, kg_provenance, skill,
skill_admission_log, prompt_versions, prompt_evals, playbook_blocks, task_executions,
pulse_users) + the 15 in `engine/knowledge_graph/models.py` (knowledge_nodes,
knowledge_edges, kg_query_feedback, kg_cache_entries, kg_recovery_log,
kg_feedback_records, kg_golden_pairs, kg_review_items, kg_quality_scores,
kg_query_plans, kg_plan_steps, kg_domain_packs, kg_bootstrap_runs,
kg_proactive_triggers, kg_proactive_insights). Fields mirror the SQLAlchemy columns
1:1 (Text→TextField, DateTime→DateTimeField, JSON-string→JSONField, Float→FloatField,
Boolean→BooleanField). Every model gets a common `AppScopeMixin` with
`app_identifier = CharField(default="carbon")` + `org_unit_id = BigIntegerField(null=True)`
+ `host_user_id = CharField(null=True)` + `visibility = CharField(default="private")`.

**R2 — Store interface.** Define `backend/ai/store.py` with an async `Store` ABC whose
surface matches what `engine/core/database.py` already provides: `get_engine(name)`,
`get_session_factory(name)`, `get_effective_storage_mode(name)`, `init_db(names)`, plus
the session operations the engine calls (`add`, `commit`, `select`, `get`, `delete`,
`refresh`, `flush`, `close`). Two impls: `InMemoryStore` (dict-backed, per-task working
memory — the "stateless" contract) and `DjangoStore` (Django ORM, wrapped async via
`sync_to_async`/`asgiref`). `engine/core/database.py` becomes a facade that returns the
configured `Store` (selected by a `settings.AI_STORE_BACKEND` bootstrap); the SQLAlchemy
import in `core/models.py` is retired once Django models exist, but the vendored
`core/models.py` may stay INERT during Phase 2 (do not delete until engine call sites
compile against the Store). Target: engine executes against `InMemoryStore` by default,
`DjangoStore` when a task asks for durable retention.

**R3 — Storage format v1.** Dedicated Django tables for all 49 (NO JSONB blob entities);
vectors stored as `JSONField` float arrays + an adjacency table for the graph (NO
pgvector service — RULE_6). If/when native vector search is needed, revisit as a Phase 3
decision, not now.

**R4 — CBAC partitioning.** `app_identifier` = `"carbon"` always (single-tenant now);
`org_unit_id` partitions durable rows by org subtree (reuse `accounts.rbac_utils`
subtree expansion at the query boundary); `visibility` (global/shared/private) filters
exactly as `_apply_tenancy_filter` does today. Store queries always inject
`app_identifier` + subtree filter — never let a caller bypass it.

**R5 — In-process adapter.** Rewrite `backend/ai/providers/pulse.py` so `PulseProvider`
calls the in-hand engine (via the `CarbonIntelligence` facade in `ai/intelligence.py`)
**in-process** — no HTTP, no `_http.py` `post_task`. Keep the `AIProvider` ABC
(`ai/protocol.py`) as the public contract. Remove `AI_PROVIDER_CLASS` runtime swapping
(settings.py + intelligence.py); the engine IS the provider. Delete `providers/_http.py`
and the `AI_PROVIDER_CLASS` block in `config/settings.py` once no tests reference them.

## Guiding hard rules (already binding)

- No separate AI database — durable state in Carbon Postgres, keyed by `app_identifier`.
- No pgvector as a separate service (RULE_6).
- CBAC at three boundaries: request (capability + org subtree + task class), context
  (scoped cache keyed by scope hash), write (mutation guard + human approval).
- No auto-mutation (RULE_21). AI suggests, Carbon executes.

## Verification gate (same shape as Phase 1)

  cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py check → pass
  cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run → no drift
  cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests -q → pass
  cd /home/ahmed/aast/carbon && bash ./.ai-toolkit/scripts/verify.sh backend → pass
