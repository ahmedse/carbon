# Task Results — Pulse Vendoring Phase 2b-3b: KnowledgeGraphStore cluster de-SQLAlchemy + live KG capabilities

Status: **COMPLETE — worker implementation, awaiting Master Architect commit**
Spec: `plans/TASKS-PULSE-VENDOR-PHASE-2B-3B-KG-MIGRATION.md`

## Summary

Swapped the KnowledgeGraph cluster's persistence seam from SQLAlchemy to the
**Django Store** (`ai.store.Session`), making the whole cluster run in-process
against Carbon's PostgreSQL (`ai.models.knowledge_graph`, 15 tables). All 13
cluster modules under `backend/ai/engine/knowledge_graph/` are migrated; the
only file still importing SQLAlchemy is the inert engine `models.py` (gate
exclusion, kept for the `NODE_TYPES`/`RELATIONSHIP_TYPES`/`SOURCE_TYPES`
constants). `engine_runtime.py` now wires `schema.analyze`, `anomaly.detect`,
`report.draft` to real KG entry points (`run_schema_analysis`,
`DataProfiler.profile_table`, KG node/edge context counts) with graceful
degradation (fail-visible, never fabricated).

## Files changed

| Path | Change |
|------|--------|
| `backend/ai/engine/knowledge_graph/store.py` | Core `KnowledgeGraphStore` — all `db.execute/select` → `first(await db.select(...))`; `add_node`/`add_edge`/`upsert_node`/`update_node`/`get_node`/`get_nodes_by_type`/`query_edges`/`delete_node`/`delete_edge`/`load_graph`/`store_table_profile`/`get_entity_profile`/`semantic_search` migrated; vector store optional (`self._vector = None` on failure); fetch-mutate-commit pattern; JSONField `json.dumps`/`json.loads` convention. |
| `backend/ai/engine/knowledge_graph/bm25.py` | No-op stubs (no FTS index in migrated path); `search`/`index_node` degrade to empty/skip. |
| `backend/ai/engine/knowledge_graph/migration.py` | Migration helpers → Django Store `select`/`add`/`commit`. |
| `backend/ai/engine/knowledge_graph/data_profiler.py` | `run_data_profiling` uses `kg_store.db.select(KnowledgeEdge, ("instance_id", instance_id), ("source", "INFERRED"))`; `TableProfile`/`ColumnProfile` dataclasses unchanged. |
| `backend/ai/engine/knowledge_graph/schema_analyzer.py` | `run_schema_analysis(instance_id, force=False, session=None)` — opens own session via `get_session_factory()` when `session` is None; idempotency via `importance_score` presence check; docstring at the pipeline helper updated to Django Store semantics. |
| `backend/ai/engine/knowledge_graph/context.py` | KG context builder → Store `select`; Python-side sort/limit. |
| `backend/ai/engine/knowledge_graph/path_finder.py` | Path search on Store-selected edges; Python BFS. |
| `backend/ai/engine/knowledge_graph/cache_store.py` | `_get`/`_set` on `KgCacheEntry` via Store; removed `await db.rollback()` (Django Store has no `rollback()`); `_deserialize` guards; hit-count increment via mutate + commit. |
| `backend/ai/engine/knowledge_graph/cache_warmer.py` | `_mine_queries` on `KgQueryFeedback` (`("succeeded", True)`); docstring fixed to "Django Store session (use `get_session_factory()` from core.database)". |
| `backend/ai/engine/knowledge_graph/cache_invalidator.py` | Invalidation via Store `select` + `delete`. |
| `backend/ai/engine/knowledge_graph/session_store.py` | Conversation persistence on `ai.models.core.ConversationContextRecord` via Store. |
| `backend/ai/engine/knowledge_graph/feedback.py` | `detect_rephrase`/`detect_abandonment`/`record_feedback`/`FeedbackLearner`/`ReviewQueue`/`DriftDetector` migrated: `first(await db.select(...))`, Python grouping/sorting, `db.aggregate(KgReviewItem, {"n": ("Count", "id")}, ...)` for `pending_count`, `db.flush()` before golden-pair FK, JSONField `isinstance(str)` guards on `evidence_json`. |
| `backend/ai/engine/knowledge_graph/plan_executor.py` | `_persist_step_result`/`_update_plan_status` → fetch-mutate-commit on `KgPlanStep`/`KgQueryPlan`; `self._current_plan_id` derived from `plan.db_plan_id` (replaces removed `session.info`); `utcnow()` from `ai.engine.core.clock`. |
| `backend/ai/engine/knowledge_graph/context.py`, `path_finder.py`, `session_store.py` | Same Store-seam conversion (see above). |
| `backend/ai/engine_runtime.py` | Wired `_run_schema_analyze` (bootstrap ENTITY/ATTRIBUTE nodes + HAS_ATTRIBUTE edges from `schema`/`schema_changes`, then `run_schema_analysis(force=True)`), `_run_anomaly_detect` (live `DataProfiler.profile_table` when `HOST_DB_URL` set, else z-score heuristic; `live_profile` in result), `_run_report_draft` (KG entity/attribute/edge context counts via Store; `kg_context` in result). All real-KG work try/except with `degraded` markers. |
| `backend/ai/tests/test_kg_cluster_migration.py` | **NEW** — 6 tests (see below). |
| `backend/smoke_kg_cluster.py` | **NEW** — Django Store smoke (see below). |

## Result contract (verbatim return statements)

`_run_schema_analyze` (completed path):

```python
    return {
        "status": "completed",
        "task_id": task_id,
        "result": {
            "analysis": analysis,
            "kg_analysis": kg_analysis,
            "execution_ms": int((time.perf_counter() - t0) * 1000),
        },
    }
```

- `analysis`: deterministic per-change list (`_analyze_schema_change`), always present.
- `kg_analysis`: `run_schema_analysis` summary `{"column_semantics", "implicit_relationships", "entity_importance"}` plus a `bootstrap` provenance dict `{"entities": n, "attributes": n, "edges": n}`. Empty `{}` when the payload carries no schema (degradation); `{"error": str(exc), "degraded": True}` when the real path raises.

`_run_anomaly_detect` result now includes `"live_profile": real_profile` (empty dict when no host DB or on failure).

`_run_report_draft` result now includes `"kg_context": kg_context` (`{"entities": n, "attributes": n, "edges": n}` from Store counts, or `{"error": str(exc)}` on failure).

## Gate results (§5, exact order)

| # | Gate | Result |
|---|------|--------|
| 1 | `cd backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py check` | `System check identified no issues (0 silenced).` |
| 2 | `/home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run` | `No changes detected` |
| 3 | `/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests dq/tests -q` | **360 passed** (baseline 354 + 6 new `test_kg_cluster_migration.py` tests), 0 failures |
| 4 | `bash .ai-toolkit/scripts/verify.sh backend` | `GATE PASSED` |
| 5 | literal grep (repo root) | **0 matches** (empty output, exit=1). Even the excluded `models.py` contains none of the literal tokens (it uses `declarative_base`/`Column`, not `AsyncSession`/`create_async_engine`/`.scalars()`). |
| 6 | `backend/smoke_kg_cluster.py` (run from `backend/` and from repo root) | `SMOKE PASSED` (output below) |

### Gate 5 literal grep output (verbatim)

```
$ grep -rn "session\.execute\|session\.scalars\|db\.execute\|AsyncSession\|create_async_engine\|async_sessionmaker\|\.scalars()" backend/ai/engine/knowledge_graph/
(no output)
```

### Smoke output (verbatim, run from repo root)

```
KG cluster smoke (Django Store / PostgreSQL)
  instance: smoke_kg_cluster
  [ok] CRUD round-trip durable: smoke_entity_41552780 (entity=3f48664d…, edge=e1433fee…), profile row_count=777
  [ok] run_schema_analysis -> summary keys: column_semantics, entity_importance, implicit_relationships
  [ok] idempotent second run -> {'skipped': True, 'reason': 'already_analysed'}
  [ok] dispatch schema.analyze -> completed
      kg_analysis keys: ['bootstrap', 'column_semantics', 'entity_importance', 'implicit_relationships']
      bootstrap: {'entities': 1, 'attributes': 2, 'edges': 2}
  [ok] degradation (no schema) -> completed, kg_analysis={}
  [ok] cleaned 6 leftover smoke rows (instance=smoke_kg_cluster)
SMOKE PASSED: kg cluster on Django Store (a) CRUD (b) analysis (c) dispatch
```

Leftover smoke rows after run: **0** (verified via `KnowledgeNode.objects.filter(instance_id='smoke_kg_cluster').count()`).

## New tests (`backend/ai/tests/test_kg_cluster_migration.py`, 6)

| Test | Covers |
|------|--------|
| `test_node_edge_crud_roundtrip_is_durable` | `add_node`/`add_edge`/`get_node`/`get_nodes_by_type`/`query_edges`/`get_neighbors`/`delete_edge`/`delete_node` round-trip; rows gone after delete. |
| `test_store_table_profile_persists_profile_keys` | `store_table_profile` → `get_entity_profile` returns `row_count_actual`/`profiled_at`/`column_profiles`; re-readable through a fresh session. |
| `test_run_schema_analysis_runs_and_is_idempotent` | `run_schema_analysis(force=True)` summary keys; `force=False` second run → `{"skipped": True, "reason": "already_analysed"}`. |
| `test_dispatch_schema_analyze_completed_with_schema` | `dispatch_task("carbon.schema.analyze", {"schema": [...]})` → `completed`, `kg_analysis` present, `bootstrap` counts ≥ expectations. |
| `test_dispatch_schema_analyze_degrades_without_schema` | no schema / `schema_changes` without `table_name` / empty payload → `completed`, `kg_analysis == {}`. |
| `test_cluster_imports_no_sqlalchemy` | Literal gate-5 tokens absent from every cluster `*.py` except `models.py` (documented exclusion). |

## Deviations / decisions

1. **`upsert_node` has no `source` parameter** — the bootstrap helper calls
   `store.upsert_node(name=..., instance_id=..., node_type=..., properties=...)`
   only; source defaults to `"SCHEMA"` via `add_node` on the create path
   (verified). No schema source is lost.
2. **Dev DB needed `ai.0003` applied** — the KG tables migration existed but the
   dev PostgreSQL DB was behind. Ran `manage.py migrate ai` (applies existing
   migration — **no new migration created**; gate 2 still reports
   "No changes detected"). This is a routine dev-DB sync, not a schema change.
3. **Test writes escape pytest transactions** — Django Store commits run on their
   own connection, so rows written by a *failed* test run can survive in a
   reused test DB (observed 4 duplicate `profile_target` rows → `MultipleObjectsReturned`).
   Tests therefore use per-run unique node names and avoid raw `objects.get`.
4. **`_generate_step_sql` pre-existing bug** (`step.step_id` undefined,
   should be `spec`) — **NOT fixed**: out of scope, pre-existing, inside
   try/except. Noted for a follow-up.
5. **`schema_analyzer.py` class docstring** (~line 72) still reads
   "Uses only in-memory graph traversal + async SQLite updates" — cosmetic
   only; the work order required only the pipeline-helper docstring (done).
   Recommend a one-line docstring touch-up in a later cleanup.
6. **`feedback.py`** — `quality_score` default 0.7 mirrors the
   `KgFeedbackRecord` model default; `evidence_json` guarded with
   `isinstance(str)` JSON loads because Django JSONField returns a list.
7. **`cache_store.py` rollback removed** — the Django Store has no
   `rollback()`; the except-block now just logs (Django autocommit means
   nothing is half-written).
8. **`engine_runtime.py` degradation markers** — real-KG failures return
   `{"error": str(exc), "degraded": True}` for `kg_analysis` and log a warning;
   empty payloads return `kg_analysis == {}`; handlers still return
   `status="completed"` with the deterministic baseline (never fabricated).
9. **Smoke instance** — smoke writes under `smoke_kg_cluster` (not `carbon`)
   and deletes its rows on success; `_cleanup()` purges leftovers on start
   and finish (verified 0 remaining).
10. **Gate 5** — the literal grep returned **zero** matches across the whole
    cluster, including `models.py` (its SQLAlchemy usage is `declarative_base`
    + `Column`, which do not match any gate token).

## Not completed (explicitly deferred — per spec §7)

- Live Carbon table profiling end-to-end (real AASTMT `host_db_url`) — the
  capability ships with graceful degradation; `HOST_DB_URL` is empty in dev,
  so `anomaly.detect`'s live-profile path is skipped by design.
- ChromaDB/pgvector embedding restore, BM25 FTS rebuild, multi-step KG planner
  fan-out (`query.nl` still uses the 2b-2 `ExecutionEngine` path).
- Any import of Carbon domain apps (`dq`, `accounts`, `catalog`, `mdm`,
  `emissions`, `dataschema`, `core`) into `ai` — constraint respected
  (host data is read via `host_db_url`, never Carbon's ORM).
