# TASKS-PULSE-AI-DEMO-SEED — Dummy data for the AI Admin console

## Goal
Populate the AI Admin studio (`/admin/ai`) panels + the Phase E graph with
deterministic, idempotent **demo** data so every panel renders non-empty
without needing a live LLM.

## Context (already verified by Master)
- Interpreter: `/home/ahmed/aast/carbon/.venv/bin/python`; run Django as
  `cd backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py ...`.
- All AI models live in `backend/ai/models/` (single `app_label="ai"`),
  inherit `AppScopeMixin` (app_identifier="carbon" default, org_unit_id null,
  host_user_id null, visibility default "private").
- The 13 console panels are driven by `backend/ai/observability_api.py`
  `PANEL_REGISTRY` (read-only Django ORM, **no tenancy filter** at this layer).
- The graph panel uses `GET /carbon-api/ai/pulse/graph/` (`backend/ai/graph_api.py`):
  `KnowledgeNode`+`KnowledgeEdge` primary; `KgNode`+`KgEdge` merged with a
  `source_model` discriminator. Edges resolve by `(source_model, id)`.

## Deliverable
ONE new idempotent management command:

`backend/ai/management/commands/seed_ai_demo.py`

Flags:
- `--reset`  → delete all `ai` demo rows first, then reseed.
- default → upsert (skip existing, by stable natural key) so re-running is safe.

Print a concise summary at the end (rows created per panel).

## Data spec (deterministic, carbon-domain themed)

### 1. Instance (MCP panel)
One row: `name="carbon-demo"`, `display_name="Carbon Data Trust Platform"`,
`host_db_url="postgresql://carbon:****@localhost:5432/carbon"`,
`host_api_url="http://127.0.0.1:8009"`, `status="active"`,
`config={"llm":{"model":"gpt-4o"},"budget_usd":5.0}`. `visibility="shared"`.

### 2. Knowledge Graph (graph panel + `graph/` endpoint) — the centerpiece
Seed a **connected** graph (all `instance_id` = the Instance id above,
`visibility="shared"`).

`KnowledgeNode` (~18), `node_type` ∈ {Table, Field, Metric, Concept, Organization}:
- Tables: `monthly_electricity`, `monthly_water`, `monthly_chilled_water`
- Fields: `total_kwh`, `total_m3`, `total_tr`, `month`
- Metrics: `Scope 2 Emissions`, `Scope 3 Emissions`
- Concepts: `Electricity Consumption`, `Water Consumption`, `Chilled Water`,
  `Grid Emission Factor`, `Water Emission Factor`
- Organizations: `AASTMT`, `Facilities & Utilities`
- Give each a `description`, `confidence` (0.7–1.0), some `verified=True`.

`KnowledgeEdge` (~24) connecting them, `relationship` ∈
{HAS_FIELD, OWNED_BY, CONTRIBUTES_TO, MEASURED_BY, CALCULATED_FROM, EMITS}:
- table → field: HAS_FIELD
- table → concept: MEASURED_BY
- concept → metric: CONTRIBUTES_TO
- metric → factor: CALCULATED_FROM
- org → table: OWNED_BY
- table → metric: EMITS
Set varied `weight` (0.5–1.0) and `confidence`. **Every edge's source/target
must be an id you created** (dangling edges are dropped by the endpoint).

Also seed 4–6 `KgNode` (`type` ∈ {entity, attribute}) + 4–6 `KgEdge`
(`edge_type` ∈ {has, related_to}) pointing only at the `KgNode` ids, to demo
the `source_model` discriminator in the graph stats.

### 3. Remaining panels — 2–4 rows each (just enough to render)
Use the same `instance_id`; `visibility="shared"` where the field exists.
- **knowledge**: 3 `KnowledgeEntity` (entity_type ∈ {table, metric, glossary},
  name + semantic_description) + 3 `Insight` (insight_type, title, content,
  confidence).
- **memory**: 3 `MemoryLongTerm` (category, content, confidence) + 3
  `MemoryEpisodic` (event_type, summary, occurred_at=TZ-aware now).
- **agents**: 3 `Agent` (name, role) + 2 `AgentHandoff` (from_agent_id,
  to_agent_id → the Agent ids).
- **tools**: 2 `ToolExecution` (conversation_id, tool_name, status) + 2
  `TaskExecution` (instance_id, task_type, external_task_id, status,
  request_payload, response_payload).
- **skills**: 2 `Skill` (name, kind, author_user_id, status="active") + 2
  `SkillAdmissionLog` (skill_id → Skill id, instance_id, verdict="admitted").
- **prompts**: 2 `PromptVersion` (instance_id, prompt_text, content_hash) + 1
  `PlaybookBlock` (instance_id, block_type, content).
- **feedback**: 2 `Feedback` (message_id, rating) + 2 `KgFeedbackRecord`
  (instance_id, conversation_id, signal_type, original_utterance).
- **learning**: 2 `OpsRun` (instance_id, workflow, status="completed") + 1
  `KgRecoveryLog` (instance_id, question, error_type, recovery_type, succeeded).
- **monitoring**: 2 `Notification` (instance_id, severity, title) + 2
  `Insight` (may reuse above if count already ≥2, else add).
- **audit**: 3 `AuditLog` (actor, actor_type, action, target).
- **logs / usage**: 3 `LLMCallLog` (instance_id, conversation_id, model,
  total_tokens, cost_usd, duration_ms) — spread `created_at` via `bulk` is not
  possible for auto_now_add; just create 3 with distinct conversation ids.

## Hard rules
- Use ONLY `ai.models.*` imports; do NOT import accounts/catalog/dq/emissions.
- No `ForeignKey` assumptions — graph edges reference string ids you created.
- All datetimes timezone-aware (`django.utils.timezone.now()`); never
  `datetime.now()`.
- No `print()` debug noise except the final summary (CLI print is exempt).
- Do NOT create migrations. Do NOT touch `graph_api.py` / `observability_api.py`
  / any endpoint. Seed data only.

## Verification (Master will rerun)
1. `cd backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py seed_ai_demo`
2. `... manage.py seed_ai_demo` again → idempotent (no duplicate counts).
3. `... manage.py check` + `makemigrations --check --dry-run` → clean.
4. `pytest ai/tests dq/tests -q` → still green (no regressions).
5. HTTP smoke (Master): `GET /carbon-api/ai/pulse/inventory/` non-zero counts;
   `GET /carbon-api/ai/pulse/graph/` returns nodes+edges+stats with
   `node_count>=18`, `edge_count>=24`.

## Optional (skip if d3/jsdom mocking is heavy)
A vitest for `KnowledgeGraphPanel` is NOT required (same as Phase E).
