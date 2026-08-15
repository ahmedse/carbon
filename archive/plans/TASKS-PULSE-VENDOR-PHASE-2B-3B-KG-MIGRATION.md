# Pulse Vendoring — Phase 2b-3b: KnowledgeGraphStore cluster de-SQLAlchemy + live KG capabilities

**Master Architect spec** · auto-approval mode · worker = DeepSeek V4 Flash (customendpoint)

## 0. Objective

The final deferred SQLAlchemy surface is the KnowledgeGraph cluster under
`backend/ai/engine/knowledge_graph/`. Its data-access layer (`store.py`) still
talks SQLAlchemy (`AsyncSession`, `db.execute(select(...))`, `.scalars()`,
`sa_update`, `.scalar_one_or_none()`), and the remaining 17 files in the
cluster (`models.py`, `migration.py`, `data_profiler.py`, `schema_analyzer.py`,
`context.py`, `path_finder.py`, `bm25.py`, `cache_store.py`, `cache_warmer.py`,
`cache_invalidator.py`, `session_store.py`, `feedback.py`, `plan_executor.py`,
`plan_synthesizer.py`, `synthesis.py`) still use it.

This phase swaps the KG persistence seam to the **Django Store** (the same
`ai.store.Session` surface already used by chat in 2b-1 and the 7 KG/analytics
handlers in 2b-2), so the whole cluster can run in-process against Carbon's
PostgreSQL (`ai.models.knowledge_graph`, 15 tables, already migrated).

After the swap, `schema.analyze`, `anomaly.detect`, and `report.draft` are wired
to the real KG entry points (`run_schema_analysis`, `run_data_profiling`) with
graceful degradation when no host DB / schema is supplied.

## 1. Authoritative Django Store Session surface (`backend/ai/store.py`)

`get_session_factory()` (via `ai.engine.core.database.get_session_factory`)
returns a `Session` with this exact surface. `KnowledgeGraphStore` must use
ONLY these:

- `add(obj)` — sync; wraps via `_to_django_instance` (SQLAlchemy → Django
  attribute copy, skips `None` so Django defaults apply).
- `add_all(objs)` — sync.
- `await commit()` — persists pending adds + re-saves fetched/tracked objects
  (dirty-flush mirror).
- `await select(model, *filters) -> list[DjangoModel]` — CBAC-partitioned,
  returns a **list** (never a cursor). `filters` may be a Django `Q`, a dict,
  or a 2-tuple `("field", value)` (→ `Q(field=value)`). Multiple conditions =
  AND.
- `await get(model, pk) -> obj` — **raises `DoesNotExist`** on miss (do NOT
  use it where `None` is expected; use `select` + `first`).
- `await delete(obj) -> None` — obj must be a Django model instance.
- `await refresh(obj)` — `refresh_from_db`.
- `await flush()` — aliases `commit`.
- `begin_nested()` — returns an async context manager (no-op savepoint).
- `await aggregate(model, spec, *filters) -> dict` — `spec` maps alias →
  `(Func, field)`, `Func` ∈ `Sum|Count|Avg|Min|Max`.
- `await close()`.

Module-level helpers to import from `ai.store`: `first(rows)` (first of a
`select` list or `None`), `resolve_model(model)` (class-name → `ai.models.*`),
`scope_q(...)`, `_coerce_filter(...)`.

## 2. Migration idiom map (apply mechanically)

| SQLAlchemy (current) | Django Store (target) |
|---|---|
| `r = await db.execute(select(X).where(X.a==1, X.b=="y")); x = r.scalar_one_or_none()` | `x = first(await db.select(X, ("a", 1), ("b", "y")))` |
| `r = await db.execute(select(X).where(...)); xs = list(r.scalars().all())` | `xs = await db.select(X, ("a", 1), ...)` |
| `r = await db.execute(select(X).where(...)); n = r.scalar()` | `rows = await db.select(X, ...); n = rows[0] if rows else None` |
| `await db.get(X, pk)` (expects `None` on miss) | `first(await db.select(X, ("id", pk)))` |
| `db.add(x); await db.commit()` | unchanged |
| `await db.execute(sa_update(X).where(...).values(**u)); await db.commit()` | fetch `x = first(await db.select(X, ...))`, mutate attributes, `await db.commit()` |
| `await db.execute(delete(X).where(...))` | fetch rows then `await db.delete(row)` per row (or add a helper) |
| `await db.delete(x)` | unchanged (x must be a fetched Django instance) |
| `select(sqlfunc.count()).select_from(X).where(...)` → `.scalar()` | `(await db.aggregate(X, {"n": ("Count", "id")}, *filters))["n"]` |
| `X.id.in_(ids)` | split into per-id `select` or `select` with `("id__in", ids)` (Django lookup) |

Notes:
- Django `select` returns Django model instances, so every `.scalars().all()`
  and `.scalar_one_or_none()` collapses to a list / `first()`.
- `properties` is a `JSONField` on the Django models but the engine stores a
  JSON **string** via `json.dumps`. Keep that string round-trip intact: write
  `json.dumps(...)` strings as-is (JSONField stores the string and returns a
  string on read, so existing `json.loads(...)` reads keep working). Do NOT
  rewrite write-sites to pass dicts, and do NOT rewrite read-sites to drop
  `json.loads` — preserve the existing `json.dumps`/`json.loads` + defensive
  `isinstance(x, str)` pattern everywhere.
- `id` is a `CharField(primary_key=True, default=generate_uuid)` on Django
  models — engine already assigns `id=str(uuid4())`, so copy-through is fine.
- `instance_id` is `TextField(db_index=True)`; CBAC `app_identifier` defaults
  to `"carbon"` via `AppScopeMixin`, so no per-node tenancy fields are needed.

## 3. File-by-file plan

### 3.1 `store.py` (core — do this first)
- Remove `from sqlalchemy import ...` and `AsyncSession` imports. Keep the
  in-memory adjacency/cache helpers (`_adj_for`, `_cache_for`, `_adj_add_edge`,
  `_cache_node`, etc.) unchanged — they are pure Python and instance-isolated.
- Import Django models: `from ai.models.knowledge_graph import KnowledgeNode,
  KnowledgeEdge` (drop the `ai.engine.knowledge_graph.models` import). Also keep
  `NODE_TYPES`, `RELATIONSHIP_TYPES`, `SOURCE_TYPES` — import from
  `ai.engine.knowledge_graph.models` (constants only) OR redefine; prefer
  importing the constants so validation stays identical.
- `__init__(self, db_session, chroma_client=None)`: keep `self.db = db_session`.
  Make vector-store acquisition **lazy/graceful**: wrap `get_vector_store(...)`
  in try/except and set `self._vector = None` on failure (ChromaDB may be
  absent). `semantic_search`/`upsert` already degrade via try/except — ensure
  `self._vector` can be `None` and every use is guarded.
- Convert every `self.db.execute(...)` to the idiom map in §2. `upsert_node`'s
  `sa_update` path becomes fetch → mutate → `commit`. `update_node`,
  `delete_node`, `add_edge`, `query_edges`, `update_edge`, `delete_edge`,
  `get_edges_from`, `get_edges_to`, `get_stats`, `load_graph`,
  `store_table_profile`, `get_entity_profile`, `get_column_values`, `search`,
  `get_entity` — all flow through the same conversion.
- `get_stats`: replace `select(node_type, count)`/`count()` with `aggregate`
  (§2 last two rows).
- `_get_bm25()` and BM25 calls: degrade to a **no-op stub** (see §3.2). Keep
  the call sites wrapped in try/except so a missing/disabled BM25 never fails
  a write.
- `load_graph(instance_id)`: use `select` to load nodes/edges into the
  in-memory adjacency dicts; keep the instance-isolation logic.
- `store_table_profile(node_id, table_profile)`: `table_profile` is the
  `TableProfile` dataclass. Serialize its `columns` (each a `ColumnProfile`
  dataclass) with `dataclasses.asdict` and `json.dumps` into the node's
  `properties` (preserving the existing key names — read the current impl and
  keep them exact).

### 3.2 `bm25.py`
- Replace the SQLite FTS5 (`db.execute(text(_CREATE_FTS_TABLE))`,
  `select` + `text`) with a no-op / in-memory fallback. `index_node`,
  `delete_node`, `search`, `rebuild` become graceful no-ops (return empty /
  `None` as the existing callers expect). Do NOT delete the file — keep the
  class surface so `_get_bm25()` call sites compile.

### 3.3 `migration.py`
- Convert the two `store.db.execute(delete(...))`/`select(...)` blocks to
  `store.select` + `store.delete` per-row. Keep the `load_knowledge_graph`
  / bootstrap surface unchanged (it populates ENTITY/ATTRIBUTE nodes from a
  supplied schema).

### 3.4 `data_profiler.py`
- `DataProfiler` itself is **already Django-Store-clean** (it reads Carbon's
  host PostgreSQL via `psycopg2` read-only in `asyncio.to_thread` — this is
  the sanctioned "read host data" pattern, NOT engine state; keep it).
- Only `run_data_profiling` has a direct SQLAlchemy block
  (`edge_stmt = select(KnowledgeEdge)...; kg_store.db.execute(...)`). Replace it
  with `await kg_store.query_edges(...)` (or a new store helper) filtered by
  `instance_id` + `source="INFERRED"`. Add that helper to `store.py` if one
  does not already exist.
- Remove `from sqlalchemy import select` and `from ai.engine.knowledge_graph.models
  import KnowledgeEdge, KnowledgeNode` (the latter is replaced by the store
  helper).

### 3.5 `schema_analyzer.py`
- It only talks to `store.*` methods (already clean) EXCEPT the
  `run_schema_analysis` fallback which opens a session via
  `ai.engine.core.database.get_session_factory()`. That now returns the Django
  Store session, so it is already correct — only confirm no `AsyncSession`
  import remains and the docstring no longer claims "SQLite".
- No SQLAlchemy imports should remain.

### 3.6 `context.py`
- Remove `from sqlalchemy import select`. Replace the direct
  `select(KnowledgeNode).where(KnowledgeNode.id == nid)` with
  `await store.get_node(nid)` / `first(await store.select(KnowledgeNode, ("id", nid)))`
  depending on the local `store` reference in scope. Import `KnowledgeNode`
  from `ai.models.knowledge_graph`.

### 3.7 `path_finder.py`
- Replace `self.store.db.execute(select(KnowledgeEdge)...)` →
  `await self.store.select(KnowledgeEdge, ("id__in", edge_ids))` (or the
  store's `query_edges` helper). Same for `select(KnowledgeNode)` blocks.

### 3.8 `cache_store.py`, `cache_warmer.py`, `cache_invalidator.py`
- Convert all `db: AsyncSession` method signatures to the Django Store session
  (no signature type change needed — drop the `AsyncSession` import). Replace
  `execute(select/update/delete)` with `select`/`aggregate`/fetch-mutate-commit
  per §2. `get_stats` → `aggregate`.
- `cache_warmer.py`'s `select(sqlfunc.count())` / `func` aggregations →
  `aggregate`.

### 3.9 `session_store.py`
- Convert `select(ConversationContextRecord)` queries to `select` +
  `first()`/list. Drop `AsyncSession`.

### 3.10 `feedback.py`
- Convert all `db.execute(select(...))`/`.scalars().all()`/`.scalar_one_or_none()`
  to `select` + `first`. `select(Message)` blocks (turn/conversation messages)
  → use the Django Store session for the corresponding `ai.models` message
  model if one exists; otherwise keep the signature and return empty on the
  non-migrated path. **Do not fabricate** — if a `Message` model has no Django
  mirror, return empty/None and log a warning (fail-visible, not fake).
- Aggregations (`func.count`, `sa_func`) → `aggregate`.

### 3.11 `plan_executor.py`, `plan_synthesizer.py`, `synthesis.py`
- Convert `update(KgPlanStep)`/`update(KgQueryPlan)`/`select` blocks to
  fetch-mutate-commit + `select`. Drop `AsyncSession`/`select`/`update` imports.

### 3.12 `models.py` (engine)
- Leave the SQLAlchemy ORM definitions in place (they are inert and still
  provide the `NODE_TYPES`/`RELATIONSHIP_TYPES`/`SOURCE_TYPES` constants used
  for validation). Do NOT delete this file. Do NOT import from it in any
  migrated runtime path — runtime code imports Django models from
  `ai.models.knowledge_graph`.

### 3.13 `engine_runtime.py` — wire the 3 real handlers
Keep the existing deterministic handlers as the **degradation fallback**. Add
real KG invocation on top, gated so it never breaks the contract:

- `_run_schema_analyze`: if `payload` carries `schema`/`schema_changes`
  (list/dict of tables+columns), bootstrap the KG for `instance_id` (upsert
  ENTITY/ATTRIBUTE nodes via `KnowledgeGraphStore`) then run
  `run_schema_analysis(instance_id, force=True, session=<django session>)` and
  return `{"status":"completed", "result": {"analysis": <real summary>}}`.
  If bootstrap/analysis raises OR no schema supplied → fall back to the current
  deterministic `_analyze_schema_change` result (still `completed`). Wrap all
  real-KG work in try/except; log the failure.
- `_run_anomaly_detect`: if `payload` provides a live table profile path (or a
  `host_db_url` + table), call `DataProfiler.profile_table(...)` and derive
  anomalies from the profile; otherwise keep the existing z-score
  `profile_history` heuristic. Never fabricate rows — only switch to live
  profile when `host_db_url` is resolvable.
- `_run_report_draft`: keep the deterministic summary as the baseline; if a
  real profiled table is available via the KG (store lookup), enrich the
  summary with actual row/column counts. Do NOT invent figures.

**Constraint (unchanged)**: `engine_runtime.py` and the KG cluster must NOT
`import` Carbon domain apps (`dq`, `accounts`, `catalog`, `mdm`, `emissions`,
`dataschema`, `core`). Host data is read via `psycopg2`/`host_db_url`, never
via Carbon's ORM.

## 4. Degradation rules (fail-visible, never fabricate)
- ChromaDB/vector store unavailable → `semantic_search` returns empty, writes
  skip indexing (already try/except). `self._vector` may be `None`.
- BM25 unavailable → no-op (no FTS index, `search` returns empty).
- Any migrated query that would return `DoesNotExist` → use `first()` → `None`
  and treat as "not found" (return `None`/empty list, never raise into a 500).
- Missing host DB / schema / LLM → deterministic fallback (as in 2b-2/2b-3a).

## 5. Gates (Master re-runs independently — all must be green)
1. `cd backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py check`
   → 0 issues.
2. `/home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run`
   → "No changes detected" (no new migrations — the 15 KG tables already exist).
3. `pytest ai/tests dq/tests -q` → all pass (baseline **354**, expect +new KG
   migration tests; must be ≥354 with 0 failures).
4. `bash .ai-toolkit/scripts/verify.sh backend` → GATE PASSED.
5. Literal de-SQLAlchemy gate (from repo root):
   `grep -rn "session\.execute\|session\.scalars\|db\.execute\|AsyncSession\|create_async_engine\|async_sessionmaker\|\.scalars()" backend/ai/engine/knowledge_graph/`
   → **0 matches** (except `models.py` inert ORM definitions, which are allowed
   and excluded: `backend/ai/engine/knowledge_graph/models.py`).
6. New smoke script `backend/smoke_kg_cluster.py`: Django Store + in-memory
   fallback; (a) `KnowledgeGraphStore.add_node`/`add_edge`/`get_node`/
   `get_neighbors`/`store_table_profile`/`load_graph` round-trip → durable in
   test DB; (b) `run_schema_analysis(instance_id, force=True)` → summary dict;
   (c) `dispatch_task("carbon.schema.analyze", ...)` → `completed`. Must run
   green with no real host DB (stub/empty schema path).

## 6. Deliverables / DoD
- All files in §3 migrated; §5 gates green (Master re-verified).
- New tests in `backend/ai/tests/test_kg_cluster_migration.py` covering: node/
  edge CRUD round-trip via Django Store, `store_table_profile` persists profile
  keys, `run_schema_analysis` runs + is idempotent, `dispatch_task` returns
  `completed` for schema.analyze with a supplied schema, and degradation when
  no schema.
- New `backend/smoke_kg_cluster.py`.
- Update `plans/TASK-RESULTS-PULSE-VENDOR-PHASE-2B-3B-KG-MIGRATION.md` with the
  exact result shapes, deviations, and gate output.

## 7. Non-goals (explicitly deferred)
- Live **Carbon** table profiling end-to-end (host_db_url wiring against the
  real AASTMT tables) is gated behind the Carbon boundary supplying
  `host_db_url` + schema; this phase ships the *capability* with graceful
  degradation, not the production data pipeline.
- ChromaDB/pgvector embedding restore, BM25 FTS rebuild, and multi-step KG
  planner fan-out (query.nl still uses the 2b-2 `ExecutionEngine` path).
- Any import of Carbon domain apps into `ai`.
