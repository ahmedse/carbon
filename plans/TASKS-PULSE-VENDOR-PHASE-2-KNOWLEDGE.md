# TASKS.md — Pulse Vendoring Phase 2: Migrate System-of-Intelligence Modules (DRAFT)

**Status:** DRAFT — finalize after Phase 1 (in-hand engine) lands.
**Role:** Backend Worker
**Model:** DeepSeek-V3
**Domain:** backend
**Prerequisite:** `TASKS-PULSE-VENDOR-PHASE-1-ENGINE.md` completed.

**Primary context:** `.ai-toolkit/decisions/0007-pulse-inhand-stateless-engine.md`, `docs/AI_INTELLIGENCE_ARCHITECTURE.md` (knowledge/learning loop, CBAC).

## Objective

Migrate Pulse's durable-state modules into Carbon as **internal Python packages inside
the ONE `backend/ai/` Django app** (per ADR-0008 — modular monolith, NO new Django apps).
They become Carbon's System of Intelligence: Carbon Postgres, CBAC-partitioned by
`app_identifier`. This is NOT a copy-paste — persistence is re-modeled on Django ORM
(drop SQLAlchemy/pgvector sessions), and every query is scoped by `app_identifier` + org
subtree.

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

## Pre-work (Master will finalize this spec)

- [ ] Read each Pulse module's model layer to enumerate exact Django models + fields.
- [ ] Decide JSONB vs dedicated tables vs a Postgres-native vector option for v1.
- [ ] Confirm CBAC partitioning strategy per module (RULE_20).

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
