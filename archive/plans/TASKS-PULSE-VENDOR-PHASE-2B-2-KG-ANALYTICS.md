# Pulse Vendoring — Phase 2b-2: Wire KG + Analytics Task Types In-Process

Status: **FINAL SPEC — for worker dispatch**
Parent: `plans/TASKS-PULSE-VENDOR-PHASE-2B-ENGINE-CAPABILITIES.md` (2b-1 COMMITTED `c6cb515`)
Commit baseline: `c6cb515` (chat wired, Store session surface complete)

## Objective

2b-1 proved the de-SQLAlchemy seam with a single `chat` vertical slice. 2b-2
wires the **seven KG/analytics task types** — `carbon.query.nl`,
`carbon.query.explain`, `carbon.schema.analyze`, `carbon.anomaly.detect`,
`carbon.anomaly.explain`, `carbon.report.draft`, `carbon.fix.suggest` — to their
concrete engine entry points, completing the de-SQLAlchemy migration of the
`knowledge_graph/`, `knowledge/`, `ingestion/`, and `cognition/monitors.py` files
as each task gets wired.

`dq.validate` / `dq.suggest` remain **out of scope** (2b-3).

## Verified current state (do not re-do)

- `engine_runtime.py`: `dispatch_task("chat", ...)` works end-to-end via
  `TurnPipelineRunner`. The other 8 task types return `{"status":"pulse_unavailable","error":{"code":"not_wired"}}`.
- `store.py` `Session` ABC exposes `select/get/add/add_all/commit/flush/begin_nested/
  delete/refresh/close/aggregate` + `resolve_model` (class-name map `ai.engine.*.models.X`
  ↔ `ai.models.X`). DjangoStore filters by `app_identifier="carbon"` (CBAC) + visibility.
- `providers/pulse.py` `PulseProvider` already builds the **payload** for each task
  type and maps the **result** back to a typed `*Response`. The result dict shape
  that `dispatch_task` must return for each task type is fixed by that mapping
  (table below). Do NOT change `providers/pulse.py` — only `engine_runtime.py`.
- Interpreter: **`/home/ahmed/aast/carbon/.venv/bin/python`** (repo-root venv, Django
  5.2.3). NOT `backend/.venv`. All gate commands use it (or `cd backend && ../.venv/bin/python`).

## Task-type → entry point + payload/result contract

The **payload keys** are what `PulseProvider` already sends (verified in
`providers/pulse.py`). The **result keys** are what `PulseProvider` reads back.
`dispatch_task` MUST return those exact keys or the console will silently drop data.

| task_type | entry point(s) | payload keys | result keys (must return) |
|---|---|---|---|
| `carbon.query.nl` | `knowledge_graph/multi_step_planner.py MultiStepPlanner` → `plan_executor.py PlanExecutor.execute` → `plan_synthesizer.py PlanSynthesizer.synthesize` | `question`, `max_rows`, `tables?`, `conversation_history?`, `domain_vocabulary?` | `sql`, `rows`, `row_count`, `execution_ms`, `recovery_applied` |
| `carbon.query.explain` | `knowledge_graph/plan_synthesizer.py PlanSynthesizer.synthesize` (plan-explanation mode) | `question`, `sql`, `row_count`, `sample_rows` | `explanation`, `caveats` |
| `carbon.schema.analyze` | `knowledge_graph/schema_analyzer.py run_schema_analysis` (SchemaAnalyzer.enrich_column_semantics + analyze_implicit_relationships + score_entity_importance) | `schema_changes` (`[{change, table_name, field_name}]`), `context` | `analysis` (`[{change, impact, severity, suggested_action}]`) |
| `carbon.anomaly.detect` | `knowledge_graph/data_profiler.py run_data_profiling` (DataProfiler.profile_table + validate_graph_relationships) | `table_name`, `profile_history`, `sensitivity`, `volume_threshold_pct`, `conversation_history?` | `anomalies` (`[{metric, expected_range:{low,high}, observed, z_score, severity, explanation}]`), `history_snapshots` |
| `carbon.anomaly.explain` | `knowledge_graph/synthesis.py ResponseSynthesizer.synthesize` (anomaly-explanation mode) | `table_name`, `anomaly` | `explanation`, `investigation_steps` |
| `carbon.report.draft` | `llm/playbook.py` + `ingestion/ops_workflow.py OpsWorkflowRunner.run` | `report_type`, `period_start`, `period_end` | `title`, `summary`, `report_type`, `period_start`, `period_end`, `generated_at`, `sections` (`[{title, narrative, sql, data_table, caveats}]`) |
| `carbon.fix.suggest` | `knowledge/semantic_layer.py SemanticEnricher.enrich_schema` (fix-suggestion mode) | `issue_type`, `table_name`, `issue_description`, `affected_rows?`, `profile?` | `issue_type`, `table_name`, `suggestions` (`[{description, confidence, estimated_affected_rows, suggested_action_type}]`) |

### Wiring notes (architect guidance)

1. **`carbon.query.nl`** — the full multi-step spine. `MultiStepPlanner.should_plan(utterance)`
   decides single- vs multi-step. If single-step, generate SQL directly; if
   multi-step, `decompose` → `PlanExecutor.execute` → `PlanSynthesizer.synthesize`.
   `KG_MULTI_STEP_ENABLED` (env, default true) gates the multi-step path; when
   false, fall back to single-pass. `recovery_applied` mirrors the executor's
   retry/recovery result (default `False`). `sql` is the executed SQL string;
   `rows` the fetched rows (list of dicts); `row_count` the length; `execution_ms`
   the measured wall time.
2. **`carbon.query.explain`** — synthesize a human explanation + caveats for an
   already-executed `sql` (given `question`, `row_count`, `sample_rows`). Use the
   LLM synthesizer; on LLM unavailability, return a deterministic fallback
   explanation (never an empty/None explanation).
3. **`carbon.schema.analyze`** — `run_schema_analysis(db_session, ...)` is the
   top-level function; it takes a Store session. Return `analysis` keyed by the
   three `schema_changes` inputs (impact/severity/suggested_action per change).
4. **`carbon.anomaly.detect`** — `DataProfiler(host_db_url, schema=...)` connects to
   **Carbon's PostgreSQL** to profile real tables. `host_db_url` MUST come from
   Django settings (`settings.DATABASES["default"]` → build a
   `postgresql://user:pass@host:port/dbname` URL or pass `asyncpg`-compatible
   params), NOT a hardcoded URL. `profile_history` = prior snapshots for z-score
   comparison; `sensitivity`/`volume_threshold_pct` tune thresholds. `history_snapshots`
   = count of snapshots considered.
5. **`carbon.anomaly.explain`** — take the already-detected `anomaly` dict + `table_name`,
   synthesize `explanation` + `investigation_steps` via the LLM (`ResponseSynthesizer`
   or `cognition/monitors.py`). Deterministic fallback if LLM absent.
6. **`carbon.report.draft`** — `OpsWorkflowRunner` (or a playbook assemble) drafts
   `sections` for `report_type` over `period_start`–`period_end`. `generated_at`
   is an ISO-8601 **timezone-aware** string (`django.utils.timezone.now()`), never
   `datetime.now()`. Each section carries `title`/`narrative`/`sql`/`data_table`/`caveats`.
7. **`carbon.fix.suggest`** — `SemanticEnricher` + LLM produce fix `suggestions`
   (description/confidence/estimated_affected_rows/suggested_action_type) for the
   `issue_type`/`table_name`/`issue_description`. `requires_confirmation` is set
   by the provider (ALWAYS true) — you do NOT return it.

## De-SQLAlchemy scope (migrate as you wire)

These files still use SQLAlchemy `db.execute(select(...))`/`.scalars(...)`/`AsyncSession`
type hints. Migrate them to the Store native API (`select`/`aggregate`/`first`/`add`/
`commit`/`begin_nested`) + `resolve_model`, **only for the paths each wired task
actually executes**:

- `knowledge_graph/` — `multi_step_planner.py`, `plan_executor.py`, `plan_synthesizer.py`,
  `schema_analyzer.py`, `data_profiler.py`, `synthesis.py`, `engine.py`, `store.py`,
  `session_store.py`, `models.py` (SQLAlchemy classes → map via `resolve_model`).
- `knowledge/semantic_layer.py` + `knowledge/store.py` (already migrated) + any
  `knowledge/` helpers on the fix-suggest path.
- `ingestion/ops_workflow.py` (report.draft path).
- `cognition/monitors.py` (anomaly.explain path).
- `agent/tools.py:1182`, `skills/gate.py`, `skills/registry.py`,
  `core/storage_migration.py`, `cognition/loop.py` — **remain out of scope** unless
  a wired task reaches them (they are on fan-out/multi-step/proactive/skills/distill
  paths = 2b-3+). Do NOT pre-migrate unreachable files.

**Do NOT build a SQLAlchemy→Django query translator.** Use `resolve_model` + native
`select`. If a call site genuinely needs raw SQL (e.g. `DataProfiler._run_query`),
that is a direct `asyncpg`/psycopg connection to Carbon's PostgreSQL — not the
engine's ORM — and is acceptable (it reads Carbon's *data*, not the engine's state).

## Non-negotiables (unchanged from 2b)

- **Fail-visible, never fabricate.** On any engine error or unwired task return
  `pulse_unavailable`/`provider_unavailable` — never a plausible-but-fake answer.
  For LLM-dependent results, a deterministic non-LLM fallback is acceptable; an
  empty/fabricated answer is not.
- **No new database.** All engine durable state lives in `ai/models/*` (PostgreSQL).
  The only exception is `DataProfiler` reading Carbon's *data tables* (not engine state).
- **CBAC on every read/write.** `app_identifier`/`org_unit_id`/`host_user_id`/
  `visibility` partition engine rows (already in DjangoStore).
- **No HTTP transport.** Stay in-process.
- **`ai` imports nothing from `accounts`/`catalog`/`mdm`/`dq`/`emissions`/`core`**
  (org-subtree expansion happens at the query boundary). `DataProfiler` may read
  `settings.DATABASES` (Django config, not another app).
- **TZ-aware datetimes.** `generated_at`/any timestamp = `django.utils.timezone.now()`
  (ISO-8601, aware). No `datetime.now()`/`datetime.utcnow()`.

## Acceptance gates

- `cd backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py check` — 0 issues.
- `makemigrations --check --dry-run` — no drift.
- `pytest ai/tests dq/tests -q` — all green (baseline 327, expect growth; add
  `ai/tests/test_kg_wiring.py` covering each of the 7 task types: completed path
  with stubbed LLM + fail-visible path).
- `verify.sh backend` — GATE PASSED.
- Residual scan: `grep -rn 'session\.execute\|session\.scalars' ai/engine/` — 0 in the
  wired KG/analytics paths (the documented inert fan-out/multi-step/skills/distill
  files may remain, but `knowledge_graph/` + `knowledge/semantic_layer.py` +
  `ingestion/ops_workflow.py` + `cognition/monitors.py` must be clean).
- Smoke: a `smoke_kg_wiring.py` that calls each of the 7 task types and prints
  `status=completed` (in-memory Store + stubbed LLM + no real PostgreSQL for the
  DataProfiler path — stub `DataProfiler` or point it at an empty in-memory table).

## Rollback / safety

- `git checkout c6cb515 -- backend/ai/` restores the 2b-1 baseline.
- Never `git add -A`. Stage only `backend/ai/**` + affected test/smoke files +
  this results doc.
