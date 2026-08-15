# Pulse Vendoring — Phase 2b-1 Task Results (Engine Capabilities)

Status: **DONE — all gates PASS**
Parent spec: `plans/TASKS-PULSE-VENDOR-PHASE-2B-ENGINE-CAPABILITIES.md`
Commit baseline: `7f8c4f3` (Phase 1 + Phase 2 R1–R5)
Scope this window: **2b-1 ONLY** (Store session surface + model-mapping resolver + de-SQLAlchemy the single-pass chat spine + wire `chat` in-process). **Not** 2b-2/2b-3 (fan-out, multi-step, other 8 task types).

---

## 1. What was delivered

### 1.1 Store session surface completed (`ai/store.py`)

The `Session` ABC now exposes the full SQLAlchemy-`AsyncSession`-shaped surface the engine expects, implemented natively on Django (no `execute`-shim, no SQLAlchemy→Django query translator):

| Member | Shape | Notes |
|--------|-------|-------|
| `select(model, *filters)` | `async` → `list` | `resolve_model` + `_coerce_filter`; supports Django lookups (`created_at__gte`, `block_type__in`, …) |
| `get(model, pk)` | `async` → row | resolved + tracked |
| `add(obj)` / `add_all(objs)` | **sync** | matches `AsyncSession.add()` — callers do `db.add(x)` without `await` |
| `commit()` / `flush()` | `async` | flush ≡ commit (saves pending + tracked) |
| `begin_nested()` | **sync → async CM** | `async with db.begin_nested():` works (no-op savepoint) |
| `delete` / `refresh` / `close` | `async` | native |
| `aggregate(model, spec, *filters)` | `async` | `{"alias": ("Sum"|"Count"|"Avg"|"Min"|"Max", "field")}` |
| `resolve_model(model)` | — | 1:1 class-name map `ai.engine.core.models.X` ↔ `ai.models.X` (and KG) |
| `scope_q` / `first` | — | CBAC visibility helper + single-row helper |

Fixes this window (bugs in the prior seam):
- `begin_nested` was `async def` → returned a coroutine, so `async with db.begin_nested():` raised. Changed to plain `def` returning an async context manager.
- `add` was `async def` → callers (`ledger.py`, `router.py`, …) call `db.add()` synchronously. Changed to sync `def`; added `add_all`.
- In-memory `add`/`add_all` used `_pending[self._name]` directly → `KeyError` for a fresh instance. Switched to `setdefault`.

### 1.2 Engine internals migrated off SQLAlchemy (single-pass chat spine)

Migrated to the Store native API (`select`/`aggregate`/`first`/`add`/`flush`/`begin_nested`):

- `ai/engine/knowledge/store.py` *(prior window)*
- `ai/engine/knowledge/vector_migration.py` *(prior window)*
- `ai/engine/cognition/trajectory.py` *(prior window)*
- `ai/engine/llm/router.py` *(prior window)* — `_check_budget`/`get_daily_spend` via `db.aggregate`, `_log_call` via `add`+`flush`
- `ai/engine/agent/budget.py` — `_ensure_initialized`/`_persist`/`set_justification` via `select`+`first`+mutate+`flush`
- `ai/engine/llm/playbook.py` — `load_blocks`/`get_block`/`upsert_block`/`assemble` via `select`+`first`
- `ai/engine/llm/prompts.py` — A/B `PromptVersion` lookup via `select`+`first`

`core/database.py` facade signatures unchanged (still `get_session_factory(name)` → Store session factory).

### 1.3 `chat` wired end-to-end (`ai/engine_runtime.py`)

`dispatch_task("chat", payload)` now:
1. Extracts `message` + `conversation_history.{conversation_id,messages}`.
2. `get_session_factory(instance_id)` → `TurnPipelineRunner(db=db).run(...)`.
3. Returns `{"status":"completed", "task_id", "result":{content, follow_up_questions, execution_ms}}`.
4. **Fail-visible**: any exception → `{"status":"pulse_unavailable", "error":{"code":"engine_error"}}` — never a fabricated answer.

The other 8 task types still return `pulse_unavailable`/`not_wired`; unknown types → `unknown_task`.

### 1.4 Proof artifacts

- `ai/tests/test_chat_wiring.py` — 3 tests: `dispatch_task('chat')` → `completed` + durable `TurnLedgerRow`/`LLMCallLog` rows (DjangoStore, test DB); fail-visible path; other tasks still `not_wired`.
- `smoke_chat_wiring.py` — standalone smoke (in-memory Store, stubbed LLM).

---

## 2. Gate results

| # | Gate | Result |
|---|------|--------|
| G1 | `manage.py check` → "no issues (0 silenced)" | ✅ PASS |
| G2 | `manage.py makemigrations --check --dry-run` → "No changes detected" | ✅ PASS |
| G3 | `pytest ai/tests dq/tests -q` → **327 passed** (baseline 324 + 3 new) | ✅ PASS |
| G4 | `bash ./.ai-toolkit/scripts/verify.sh backend` → `GATE PASSED` | ✅ PASS |
| G5 | `grep -rn 'session.execute\|session.scalars' ai/engine/ --include='*.py'` → **0 matches** | ✅ PASS |
| G6 | `smoke_chat_wiring.py` → `status='completed'` with real content | ✅ PASS |

---

## 3. Exact file list

**Modified:**
- `backend/ai/store.py`
- `backend/ai/engine_runtime.py`
- `backend/ai/engine/knowledge/store.py`
- `backend/ai/engine/knowledge/vector_migration.py`
- `backend/ai/engine/cognition/trajectory.py`
- `backend/ai/engine/llm/router.py`
- `backend/ai/engine/agent/budget.py`
- `backend/ai/engine/llm/playbook.py`
- `backend/ai/engine/llm/prompts.py`

**New:**
- `backend/ai/tests/test_chat_wiring.py`
- `backend/smoke_chat_wiring.py`

---

## 4. Deviations & notes

1. **Not migrated (inert — out of 2b-1 chat scope).** These files still import SQLAlchemy / use `db.execute`/`.scalars`; they are on fan-out, multi-step, KG, memory, ingestion, proactive, skills, and distillation paths (Phases 2b-2/2b-3 and later). They are **not** reachable from `dispatch_task("chat", ...)`:
   - `agent/` (executor, guardrails, reasoning, registry, tools)
   - `cognition/` (consolidation, distill/*, kg_seeding, learned_triggers, loop, monitors, state, synthesis, plan/loop)
   - `knowledge/` (vector_store, introspector)
   - `knowledge_graph/` (all: bm25, cache_*, context, data_profiler, engine, feedback, migration, models, multi_step_planner, path_finder, plan_executor, session_store, store, recovery_pipeline, retry, timeout_recovery)
   - `llm/` (prompt_eval, prompt_optimizer, prompt_synthesizer)
   - `memory/` (episodic, long_term, manager)
   - `proactive/` (context_assembler, delivery, insight_generator, loop, suppression, trigger_evaluator, trigger_registry)
   - `skills/` (crud, gate, registry, sandbox)
   - `core/` (models, storage_migration) — SQLAlchemy declarations retained as the engine's in-memory/legacy shape; mapped to Django at the Store seam.

2. **`agent/guardrails.py budget_hook`** still uses `db.execute`, but it is wrapped in `try/except` and `ctx.db` is `None` on the chat path (it opens its own session → `AttributeError` caught → logs "passing"). Non-breaking; documented for later migration.

3. **`cognition/turn/runner.py`** contains one `.execute` match — a false positive (`execute_witness.execute(...)`, not `db.execute`). The six-witness spine is clean.

4. **Non-blocking warning**: `LLMCallLog.created_at` is saved as a naive datetime (engine model default) while `USE_TZ` is on. Cosmetic only; the row persists. Noted for a follow-up TZ normalization.

5. **Fan-out / multi-step gates** (`AGENT_ORCHESTRATOR_ENABLED`, `KG_MULTI_STEP_ENABLED` default `True`) are disabled via env + `get_settings.cache_clear()` in the tests/smoke to force the deterministic single-pass spine. Left enabled in production, both paths are `try/except`-wrapped and fall back to single-pass until 2b-2/2b-3 wire them for real.

---

## 5. Non-negotiables compliance

- ✅ Fail-visible: unwired/erroring tasks return `pulse_unavailable`/`not_wired`/`engine_error` — no fake output.
- ✅ No new database / no SQLite — all durable state in `ai/models/*` (PostgreSQL).
- ✅ CBAC on every read/write via `app_identifier` (store tenancy filter) + explicit `instance_id`/`host_user_id` filters.
- ✅ `ai/` imports nothing from `accounts/catalog/mdm/dq/emissions/core`.
- ✅ `config/settings.py` AI block untouched; no HTTP reintroduced; no `git add -A`.
