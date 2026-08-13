# Pulse Vendoring — Phase 2b: Wire Engine Capabilities In-Process

Status: **DRAFT — final spec for worker dispatch**
Parent: `plans/TASKS-PULSE-VENDOR-PHASE-2-KNOWLEDGE.md` (Phase 2 R1–R5, COMMITTED `7f8c4f3`)

## Objective

Phase 2 retired the HTTP transport and installed the in-process seam
(`engine_runtime.py` + `store.py` + 49 Django tables). But **the engine does not
execute anything yet** — `dispatch_task` returns `pulse_unavailable` for every
task type. Phase 2b wires each task type to a concrete engine capability so the
console's panels can do real AI work.

## Verified current state (do not re-do)

- Session acquisition already routes through the Store: engine internals do
  `from ai.engine.core.database import get_session_factory` → `ai.store.get_store()`.
- `backend/ai/engine_runtime.py` = stub. `dispatch_task` returns
  `{"status":"pulse_unavailable","error":{"code":"not_wired"}}` for all 9 task types.
- `backend/ai/store.py` = `Store` ABC + `InMemoryStore` + `DjangoStore` (sync_to_async).
- `backend/ai/models/` = 49 Django tables (34 core + 15 KG), `AppScopeMixin`,
  single `app_label="ai"`. `VectorEmbedding.embedding_json = JSONField` (no pgvector).

## Two gaps that block real execution

1. **Session surface mismatch.** The engine has ~90 call sites that use SQLAlchemy
   `await session.execute(select(Model).where(...))` and `session.scalars(...)`.
   The Store `Session` ABC only exposes `select(model, *filters) -> list`, `get`,
   `add`, `commit`, `delete`, `refresh`, `flush`, `close`. No `execute`/`scalars`.
2. **Engine uses SQLAlchemy models.** `ai/engine/core/models.py` and
   `ai/engine/knowledge_graph/models.py` are SQLAlchemy ORM classes; the Store's
   Django backend operates on `ai/models/*` Django classes. `session.select(EngineModel)`
   must resolve to the Django table, not a SQLAlchemy table.

## Approach (architect ruling)

**De-SQLAlchemy the engine.** Migrate the engine's DB call sites to the Store's
native async API, and swap SQLAlchemy model imports to the Django models. Do NOT
build a SQLAlchemy→Django query translator (a permanent dual-ORM tax). This is
the persistence-seam swap ADR-0009 intended; R1/R2 built the target surface, 2b
completes the swap.

## Task-type → capability mapping

| task_type | concrete capability | entry point |
|---|---|---|
| `chat` | turn runner (agent loop + LLM) | `cognition/turn/runner.py` `TurnRunner.run` |
| `carbon.query.nl` | NL→SQL KG query | `knowledge_graph/multi_step_planner.py` + `plan_executor.py` + `plan_synthesizer.py` |
| `carbon.query.explain` | explain a KG query plan | `knowledge_graph/plan_synthesizer.py` |
| `carbon.schema.analyze` | implicit-relationship + column-semantics analysis | `knowledge_graph/schema_analyzer.py` `SchemaAnalyzer` |
| `carbon.anomaly.detect` | profile + relationship validation | `knowledge_graph/data_profiler.py` `DataProfiler.profile_table` / `validate_graph_relationships` |
| `carbon.anomaly.explain` | KG synthesis over detected anomalies | `knowledge_graph/synthesis.py` / `cognition/monitors.py` |
| `carbon.report.draft` | LLM playbook / report draft | `llm/playbook.py` + `ingestion/ops_workflow.py` |
| `carbon.fix.suggest` | semantic-layer fix suggestion | `knowledge/semantic_layer.py` |
| `dq.validate` / `dq.suggest` | Carbon DQ engine + engine LLM NL interpretation | `backend/dq/engine.py` (NOT vendored engine) |

## Sub-phases (dependency order)

### 2b-1 — Complete the Store session surface + first vertical slice
1. Extend `Session` ABC (and both backends) with whatever the engine actually
   needs. Preferred: migrate call sites to the existing native `select/get/add/
   commit/delete` API and add a **model-mapping resolver** so
   `session.select(EngineSqlAlchemyModel)` / `session.get(...)` resolve to the
   Django table (map `ai.engine.core.models.X` ↔ `ai.models.X`).
2. Migrate engine internals off `session.execute(select(...))` / `session.scalars(...)`:
   replace with the Store native `select`/`get`. Keep `core/database.py` facade
   signatures (`get_engine`, `get_session_factory`, `get_db`, `get_instance_db`,
   `init_db`, `list_initialized_instances`) unchanged.
3. Wire `chat` end-to-end: `engine_runtime.dispatch_task("chat", ...)` → `TurnRunner.run`
   with a real result, writing trajectory/turn/ledger rows through the Store.
   This is the proof that the de-SQLAlchemy seam works.

### 2b-2 — Wire KG + analytics task types
Wire `carbon.query.nl`, `carbon.query.explain`, `carbon.schema.analyze`,
`carbon.anomaly.detect`, `carbon.anomaly.explain`, `carbon.report.draft`,
`carbon.fix.suggest` to their entry points (table above).

### 2b-3 — Wire `dq.validate` / `dq.suggest`
Route `dq.validate` / `dq.suggest` to Carbon's `dq/engine.py` deterministic
evaluation with the engine LLM as the NL-interpretation layer. Preserve
fail-visible degradation (`provider_unavailable`) on any engine error.

## Non-negotiables

- **Fail-visible, never fabricate.** On any engine error or unwired task, return
  `pulse_unavailable`/`provider_unavailable` — never a plausible-but-fake answer.
- **No new database.** All durable state lives in `ai/models/*` (PostgreSQL), no
  separate AI DB, no SQLite.
- **CBAC on every read/write.** `app_identifier`/`org_unit_id`/`host_user_id`/
  `visibility` partition all engine rows (already in `DjangoStore._select`).
- **No HTTP transport reintroduced.** Stay in-process.
- **`ai` imports nothing from `accounts`/`catalog`/`mdm`/`dq`/`emissions`/`core`**
  (org-subtree expansion happens at the query boundary).

## Acceptance gates (per sub-phase)

- `cd backend && .venv/bin/python manage.py check` — 0 issues.
- `makemigrations --check --dry-run` — no drift.
- `pytest ai/tests dq/tests -q` — all green (baseline 324, expect growth).
- `verify.sh backend` — GATE PASSED.
- Residual scan: no `session.execute`/`session.scalars` remaining in `ai/engine/`
  (except in documented inert files) after 2b-1.
- `dispatch_task("chat", ...)` returns `status="completed"` with a real result
  after 2b-1 (not `not_wired`).

## Rollback / safety

- `git checkout 7f8c4f3 -- backend/ai/` restores the Phase 2 baseline.
- Never `git add -A`. Stage only `backend/ai/**` + affected test files.
