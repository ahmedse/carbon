# TASKS — PULSE VENDOR PHASE D: Cognition Loop Activation (scheduler + sweep migration)

**Role:** backend-worker
**Model:** DeepSeek V4 Flash (customendpoint)
**Domain:** backend (Django + vendored Pulse engine)
**Status:** Ready for execution
**Precedes:** Frontend "Sweeps" console panel (out of scope here — backend only)

---

## 0. Goal

The vendored engine's **conscious cognition loop** is fully written but **never started**,
and its sweep runners are **still SQLAlchemy-bound** (the one cluster Phase 2b/2b-3b
deliberately left for later). This phase:

1. Migrates the cognition/memory/proactive **sweep cluster** from SQLAlchemy to the
   Django Store (`ai.store.Session`) — exactly the same mechanical de-SQLAlchemy already
   done for the KG cluster in Phase 2b-3b.
2. Wires a **scheduler lifecycle** (a blocking management command) that calls the
   already-written `start_scheduler()`.
3. Adds a **durable sweep-run record** + a read-only ops endpoint so the loop's state is
   visible across processes.

**Out of scope (DO NOT build):** frontend panels, Celery, Redis jobstore, new LLM work,
any change to `ai/store.py`'s public API.

---

## 1. CRITICAL FACTS (read before touching anything)

- **Interpreter:** `/home/ahmed/aast/carbon/.venv/bin/python` (repo-root venv, NOT backend/.venv).
  Every command: `cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py ...`
- **Import root:** `ai.engine.*` (never bare `engine.*`).
- **Store API (`backend/ai/store.py`) — the ONLY persistence API you may use:**
  `Session.select(model, *filters) -> list`, `first(rows)`, `get`, `add`, `add_all`,
  `await commit()`, `delete`, `aggregate(model, spec, *filters)`, `begin_nested`.
  **There is NO `execute()`, NO `scalars()`, NO `Session.query()`.** Any `db.execute(select(...))`
  or `result.scalars()` in the sweep path MUST be rewritten.
- **`resolve_model()` (store.py) maps 1:1 by class name**: engine `ai.engine.core.models.Instance`
  ↔ Django `ai.models.Instance`. Django models (`ai.models.core.Instance`, `Conversation`,
  `Message`, `MemoryLongTerm`, `MemoryEpisodic`, `Insight`, `Trajectory`, `Skill`,
  `PromptVersion`, plus `ai.models.knowledge_graph.*`) all inherit `AppScopeMixin`
  (app_identifier/org_unit_id/host_user_id/visibility) and use **string-UUID columns**
  (`instance_id`, `conversation_id`, etc. — no FK objects). Filter by `instance_id=<str>`.
- **`ai.engine.core.database.get_session_factory()` is already a facade** → `ai.store.get_store()`.
  The loop's `_for_each_instance()` already calls it — but then misuses SQLAlchemy
  (`db.execute(select(Instance)...)` + `.scalars()`), which fails against the Store.
- **The scheduler already exists**: `ai/engine/cognition/loop.py::start_scheduler()` registers
  ~20 jobs on `apscheduler.schedulers.asyncio.AsyncIOScheduler` and calls `scheduler.start()`.
  `get_loop_status()` / `stop_scheduler()` / `trigger_task(name)` also exist. APScheduler is
  already in `backend/requirements.txt`. Nothing calls `start_scheduler()` in the Django process.
- **Config (`ai/engine/core/config.py`)** already has `COGNITION_*_INTERVAL`,
  `CONSOLIDATION_SWEEP_ENABLED`, `KG_PROACTIVE_ENABLED`, `CONSOLIDATION_SWEEP_MAX_LLM_CALLS`
  (default 10), `CONSOLIDATION_SWEEP_MIN_CONFIDENCE`. Respect these — do not invent new keys.
- **RULE_21 nuance:** the sweeps write to the engine's OWN learning state (`MemoryLongTerm`,
  `MemoryEpisodic`, `Insight`, `Skill`, `Trajectory` — all in `ai.models`). That is allowed.
  Sweeps MUST NOT write to or read Carbon business tables (catalog/mdm/dq/dataschema/emissions).
  The single read of host data is `monitors.check_schema_drift` (psycopg2, already migrated in
  2b-2) — leave it as-is.

---

## 2. FILES TO READ FIRST

- `backend/ai/store.py` — the Session API + `resolve_model`/`first`/`_coerce_filter`.
- `backend/ai/engine/cognition/loop.py` — `_for_each_instance`, `_tracked`, all `_run_*`,
  `start_scheduler`, `get_loop_status`, `stop_scheduler`.
- `backend/ai/models/core.py` + `backend/ai/models/__init__.py` — exact Django model field names.
- `backend/ai/engine/cognition/monitors.py` — see how `check_schema_drift` was ALREADY migrated
  to native `Store.select` (copy that style for `check_model_health`/`check_data_freshness`/
  `check_failed_jobs`).
- `backend/ai/engine/cognition/consolidation.py`, `distill/*.py`, `synthesis.py`, `state.py`,
  `learned_triggers.py`, `kg_seeding.py` — the SQLAlchemy surfaces to migrate.
- `backend/ai/engine/memory/*.py`, `backend/ai/engine/proactive/*.py` — same.
- `backend/ai/ops_urls.py` — where the new sweep-status endpoint mounts.
- `backend/ai/management/` (create `commands/`) — pattern for a management command.

---

## 3. TASKS

### D-1. Migrate `_for_each_instance` + the deterministic, no-LLM sweeps first
- Rewrite `_for_each_instance(callback)` in `cognition/loop.py` to use the Store:
  `rows = await db.select(Instance, ("status", "active"))` (or equivalent filter) then
  `for instance in rows: await callback(db, instance)`. Drop `get_session_factory`+`execute`
  +`scalars()`. The Store's CBAC partition filters apply automatically — do not re-add them.
- Migrate `cognition/monitors.py`: `check_model_health`, `check_data_freshness`,
  `check_failed_jobs` → native `db.select(...)`/`first()`. (`check_schema_drift` already done.)
- Migrate `cognition/state.py::take_snapshot` → native Store.
- Migrate `memory/episodic.py::EpisodicMemory.apply_decay` (used by `_run_episodic_decay`)
  → native Store.

### D-2. Migrate the LLM-gated learning sweeps (respect the enabled flags)
- `cognition/distill/episodic_to_semantic.py::run_distillation`,
  `cognition/distill/promotion.py::run_promotion`,
  `cognition/distill/decay.py::run_decay` → native Store (select → mutate → commit).
- `cognition/synthesis.py`: `decay_stale_memories`, `learn_user_preferences`,
  `detect_recurring_queries`, `run_self_reflection`, `synthesize_insights`,
  `reflect_on_insights` → native Store. Guard LLM calls behind the relevant
  `CONSOLIDATION_SWEEP_*`/`KG_PROACTIVE_*` flags and cap with `CONSOLIDATION_SWEEP_MAX_LLM_CALLS`.
- `cognition/consolidation.py::extract_candidates` + `_run_consolidation_for_all_instances` →
  native Store (`db.select(Trajectory, ...)`, mutate `consolidation_round`, `await db.commit()`).
- `cognition/learned_triggers.py`, `cognition/kg_seeding.py` → native Store.
- `proactive/loop.py::run_proactive_evaluation` + `run_daily_briefing` and the helpers they
  import (`trigger_evaluator`, `trigger_registry`, `context_assembler`, `delivery`,
  `suppression`, `insight_generator`) → native Store. Respect `KG_PROACTIVE_ENABLED`.

> **Pattern for every rewrite:** `result = await db.execute(select(X).where(...)); rows = result.scalars().all()`
> becomes `rows = await db.select(X, ("col", value), ...)`. Mutation: set attributes on the
> Django model instances then `await db.commit()`. "Delete all matching" → `for r in rows: await db.delete(r)` then commit.

### D-3. Durable sweep-run record (cross-process visibility)
- Add model `CognitionSweepRun` to `backend/ai/models/core.py` (inherit `AppScopeMixin`,
  fields: `task_name` TextField(db_index=True), `last_run` DateTimeField(null=True),
  `last_status` TextField(default="pending"), `last_duration_ms` IntegerField(default=0),
  `run_count` IntegerField(default=0), `last_error` TextField(null=True, blank=True)).
  `app_label = "ai"`. Additive migration (`makemigrations ai`).
- In `cognition/loop.py::_tracked`, after updating `_loop_state`, **best-effort** persist the
  same values to `CognitionSweepRun` (upsert by `task_name`) via the Store, wrapped in
  try/except so a persistence failure NEVER breaks a sweep. Use `django.utils.timezone.now()`.

### D-4. Management command `run_cognition_loop`
- Create `backend/ai/management/__init__.py`, `backend/ai/management/commands/__init__.py`,
  and `backend/ai/management/commands/run_cognition_loop.py`.
- Behavior:
  - `--run-once <task>` → `asyncio.run(trigger_task(task))`, print result, exit.
  - `--status` → print `json.dumps(get_loop_status(), indent=2)`, exit.
  - (default) → call `start_scheduler()`, then block until SIGINT/SIGTERM (register handlers
    that call `stop_scheduler()`). The `AsyncIOScheduler` manages its own event loop, so the
    command just needs to keep the main thread alive (`signal.pause()` or a `while` + sleep).
- Ensure `DJANGO_SETTINGS_MODULE` is set via `manage.py`; no raw DB access in the command.

### D-5. Read-only sweep-status endpoint
- Add `SweepsStatusView` (GET-only `APIView`, `IsAuthenticated`) — put it in
  `backend/ai/activation_api.py` or a new small `sweeps_api.py` (your choice, keep it tiny).
- Response: `{ "scheduler_running": <bool>, "tasks": [ {task_name, last_run, last_status,
  last_duration_ms, run_count, last_error} ... ] }` read from `CognitionSweepRun`
  (latest row per `task_name`). Also include the in-process `get_loop_status()` under a
  `"live"` key (may be empty in the web process — that's honest).
- Mount in `backend/ai/ops_urls.py` as `path("sweeps/", SweepsStatusView.as_view(), name="ai-pulse-sweeps")`.

---

## 4. DO NOT TOUCH

- `backend/ai/store.py` (public API frozen).
- The already-migrated KG cluster (`knowledge_graph/` engine files) and `cognition/monitors.py::check_schema_drift`.
- `backend/ai/activation_api.py` existing `PulseUsageView`/`PulseSettingsView` behavior (extend, don't break).
- `backend/ai/ops_api.py`, `observability_api.py`, `engine_runtime.py`.
- Frontend (`carbon-frontend/`), `backend/.env`, `docker-compose.yml`, `manage.sh`.
- No `git add -A`.

---

## 5. GATES (run ALL, paste output)

```bash
cd /home/ahmed/aast/carbon/backend

# 1. Django system check
/home/ahmed/aast/carbon/.venv/bin/python manage.py check

# 2. Migration drift
/home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run

# 3. De-SQLAlchemy gate — ZERO session.execute / session.scalars / db.execute(select) in the
#    sweep cluster (cognition/, memory/, proactive/), minus any remaining truly-inert docstrings.
grep -rn 'session\.execute\|session\.scalars\|db\.execute(select\|\.scalars()' \
  ai/engine/cognition/ ai/engine/memory/ ai/engine/proactive/ | grep -v '#' || echo "0 hits"

# 4. Tests
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests dq/tests -q

# 5. Anti-pattern + framework gates
bash /home/ahmed/aast/carbon/.ai-toolkit/scripts/verify.sh backend
bash /home/ahmed/aast/carbon/.ai-toolkit/scripts/verify.sh antipatterns

# 6. Scheduler smoke — run a deterministic sweep once against the Django Store (no LLM needed)
/home/ahmed/aast/carbon/.venv/bin/python manage.py run_cognition_loop --run-once health_check
/home/ahmed/aast/carbon/.venv/bin/python manage.py run_cognition_loop --status
```

**Expected:** `check` = 0 issues; `makemigrations --check` = no drift (after the additive
migration is committed); sweep-cluster grep = 0 hits; pytest green (baseline **383** + your
new tests); verify.sh backend + antipatterns GATE PASSED; `--run-once health_check` returns
`status: ok` and `--status` shows the sweep-run record.

---

## 6. TESTS (add to `backend/ai/tests/`)

- `test_cognition_scheduler.py`:
  - `_for_each_instance` iterates active instances via the Django Store (seed 2 `Instance`
    rows in `ai.models`, assert callback hit both).
  - `--run-once health_check` (call `trigger_task("health_check")` under a Django test
    async harness, or the management command via `call_command`) → returns `status: ok`,
    does not raise, writes a `CognitionSweepRun`.
  - `SweepsStatusView` GET returns 200 with `tasks` list; anonymous → 401; POST → 405.
  - An unknown `--run-once bogus` returns the `{error, available}` envelope (fail-visible,
    not a 500/exception).
  - `CognitionSweepRun` upsert: running `_tracked` twice for the same task increments
    `run_count` and updates `last_run` (one row, not two).

---

## 7. REPORT BACK

Append to `plans/TASK-RESULTS-PULSE-VENDOR-PHASE-D-COGNITION-SCHEDULER.md`:
task-by-task pass/fail, files changed (table), full terminal output of every gate,
deviations, and issues found (do NOT fix out-of-scope issues).
