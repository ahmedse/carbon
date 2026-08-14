# TASKS — PULSE VENDOR PHASE E: KG Graph Visualization + Scheduler Sidecar

**Role:** backend-worker + frontend-worker (two scoped workers; see §3)
**Model:** DeepSeek V4 Flash (customendpoint)
**Domain:** backend (Django + vendored Pulse engine) + frontend (React 19 + Vite + MUI)
**Status:** Ready for execution
**Precedes:** Phase F — CBAC capability-gating on the read endpoints (out of scope here)

---

## 0. Goal

Two concrete gaps left open by Phase D:

1. **Rich KG graph visualization** — the knowledge graph (`KnowledgeNode` / `KnowledgeEdge`)
   is persisted and queryable, but the admin console only renders it as flat DataGrid rows
   (`data/graph/`). This phase adds a real **force-directed graph view** backed by a
   dedicated normalized read endpoint.
2. **Scheduler production wiring** — `run_cognition_loop` exists but nothing *runs* it.
   This phase runs it as a supervised sidecar (docker-compose service) and **fixes a latent
   bug** in the command's blocking mode (see §1, Fact 6) so scheduled sweeps actually fire.

**Out of scope (DO NOT build):** CBAC capability-gating (Phase F), Celery/Redis jobstore,
any new LLM work, writes/mutations to the graph, changes to `ai/store.py`'s public API.

---

## 1. CRITICAL FACTS (read before touching anything)

1. **Interpreter:** `/home/ahmed/aast/carbon/.venv/bin/python` (repo-root venv, NOT `backend/.venv`).
   Every Django command: `cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py ...`
2. **Import root:** `ai.engine.*` (never bare `engine.*`).
3. **Store API (`backend/ai/store.py`)** is the only persistence API the engine may use —
   `select/add/add_all/commit/get/delete/aggregate`, **NO `execute()` / `scalars()`**.
   The *Django ORM* (`Model.objects.*`) is correct and expected for the **Django read API
   layer** (`observability_api.py` and the new `graph_api.py`) — that layer is NOT the engine.
4. **Existing read-layer pattern to copy** — `backend/ai/observability_api.py`:
   - GET-only `APIView`, `permission_classes = [IsAuthenticated]`.
   - Generic `_make_serializer(model)` factory; `_redact_secrets(value)` recursively masks
     any JSON key matching `token|secret|password|api_key` (case-insensitive).
   - Routes are mounted in `backend/ai/ops_urls.py` under `/carbon-api/ai/pulse/`.
5. **Frontend pattern to copy** — `carbon-frontend/src/pages/admin/ai/PulseDataPanel.jsx`
   (loading → offline → grounded empty → rows states; RULE_8 tokens only, RULE_10 `apiFetch`
   only via `src/api/aiPulse.js`). The current `KnowledgeGraphPanel.jsx` is a **thin wrapper**
   over `PulseDataPanel` with `dataKey="graph"` — this phase replaces it with a real graph view.
   Routing: `App.jsx` already has `/admin/ai/graph` → `KnowledgeGraphPanel`; the sidebar entry
   (`ShellSidebar.jsx`, "ai-admin" case, "Knowledge Graph" → `/admin/ai/graph`) already exists.
6. **LATENT BUG (must fix in Task C):** `backend/ai/management/commands/run_cognition_loop.py`
   default mode calls `start_scheduler()` then `signal.pause()`. `start_scheduler()` uses
   APScheduler's `AsyncIOScheduler`, which **does NOT manage its own event loop** — it schedules
   coroutine jobs onto the current asyncio loop, which must be *running*. `signal.pause()` blocks
   the main thread without running any loop, so **jobs silently never fire**. The command's
   docstring ("manages its own event loop … background thread") is factually wrong. The fix must
   run a real event loop: e.g. an `asyncio.run(...)` wrapper that (a) calls `start_scheduler()`,
   (b) installs SIGINT/SIGTERM handlers via `loop.add_signal_handler(...)` → `stop_scheduler()`,
   and (c) blocks with `await asyncio.Event().wait()` (or `loop.run_forever()`).
7. **LLM provider is POE (OpenAI-compatible):** `LLM_MODEL=gpt-4o`, but
   `LLM_COGNITION_MODEL` defaults to `anthropic/claude-haiku-4.5`, which is **NOT POE-compatible**.
   So LLM-dependent sweeps (synthesize, reflect, self_reflect, prompt_refine, consolidation,
   trigger_learning, kg_seeding, etc.) are expected to log errors and persist a `last_status` of
   `error: ...` via `_persist_sweep_run` — they must **degrade gracefully, never crash the loop**.
   Non-LLM sweeps (health_check, freshness_check, error_check, snapshot, schema_drift, decay,
   episodic_decay) should succeed. `_tracked()` already wraps each job in try/except, so
   per-job resilience exists; the fix only needs to ensure the *scheduler's* event loop runs.

---

## 2. FILES TO READ FIRST

**Backend:** `backend/ai/observability_api.py`, `backend/ai/ops_urls.py`,
`backend/ai/models/knowledge_graph.py`, `backend/ai/models/core.py` (the `CognitionSweepRun`
model near line 594), `backend/ai/engine/cognition/loop.py` (`start_scheduler`, `_tracked`,
`_persist_sweep_run`, `get_loop_status`, `stop_scheduler`),
`backend/ai/management/commands/run_cognition_loop.py`, `backend/entrypoint.sh`,
`docker-compose.yml`, `backend/config/settings.py` (env loading), and the existing
`backend/ai/tests/test_observability_api.py` (auth/test conventions).

**Frontend:** `carbon-frontend/src/api/aiPulse.js`, `carbon-frontend/src/pages/admin/ai/PulseDataPanel.jsx`,
`carbon-frontend/src/pages/admin/ai/KnowledgeGraphPanel.jsx`, `carbon-frontend/src/App.jsx`
(routes), `carbon-frontend/src/shell/ShellSidebar.jsx` ("ai-admin" case), `carbon-frontend/package.json`.

---

## 3. TASKS

### Task A — Backend: normalized graph read endpoint (backend-worker)

1. Create `backend/ai/graph_api.py` with `GraphDataView(APIView)`, GET-only, `IsAuthenticated`.
2. Normalize `KnowledgeNode` → nodes and `KnowledgeEdge` → edges:
   - node: `{ id, label (name), type (node_type), confidence, verified, properties, instance_id }`
   - edge: `{ source (source_node_id), target (target_node_id), relationship, weight, confidence }`
   - If `KgNode`/`KgEdge` (`ai.models.core`) also carry node/edge structure AND are non-empty,
     include them with a `"source_model"` discriminator; otherwise scope to `KnowledgeNode`/`KnowledgeEdge`
     only (primary). Do **not** invent structure for models that don't have source/target.
3. Caps + dangling-edge safety: limit to **500 nodes** and **1000 edges**. Only include edges
   whose `source` **and** `target` resolve to a node in the capped node set (no dangling edges in the viz).
   Emit `"truncated": true` when a cap is applied.
4. Redact `properties` via `_redact_secrets` (import from `observability_api` — do not duplicate).
5. Response envelope: `{ nodes: [...], edges: [...], stats: { node_count, edge_count, truncated, node_types: {type: n}, relationship_counts: {rel: n} } }`.
6. Mount `path("graph/", GraphDataView.as_view(), name="ai-pulse-graph")` in `backend/ai/ops_urls.py`.
7. Add `backend/ai/tests/test_graph_api.py` (auth pattern from `test_observability_api.py`):
   - seeds `KnowledgeNode` + `KnowledgeEdge` through the Store/Django ORM,
   - asserts node/edge shapes (`id`/`label`/`type`; `source`/`target`/`relationship`),
   - asserts secret redaction of a `properties` key containing `token`,
   - asserts dangling edges are dropped and `truncated` reflects the cap,
   - asserts the endpoint is auth-gated (unauthenticated → 401/403).

### Task B — Frontend: force-directed graph panel (frontend-worker)

1. Add `getPulseGraph(token)` to `carbon-frontend/src/api/aiPulse.js` → `apiFetch('ai/pulse/graph/', { token })`.
2. Add deps: `d3-force`, `d3-drag`, `d3-zoom`, `d3-selection` (modular, minimal). Use `npm install`.
3. Rewrite `carbon-frontend/src/pages/admin/ai/KnowledgeGraphPanel.jsx` as a real component:
   - Fetch via `getPulseGraph`; render loading / offline / empty states mirroring `PulseDataPanel`
     (no fabricated data; offline state when the endpoint errors).
   - SVG force-directed graph (d3-force simulation in a `useEffect`, `requestAnimationFrame` tick,
     **clean up the simulation + timers on unmount**).
   - **Drag** (d3-drag) + **zoom/pan** (d3-zoom); node **radius by degree**, **color by `node_type`**
     (theme-aware palette, no raw hex — use the existing theme token approach), **edge stroke by
     `confidence`**, **hover** shows `label` + `relationship`, **click** a node → compact side
     panel showing its `properties` (pretty-printed, redacted already server-side).
   - A small **legend** for node types and a **node/edge count** from `stats`.
   - A **Graph / Table toggle**: Graph (default) uses the new viz; Table renders the existing
     `PulseDataPanel` with `dataKey="graph"` (reuse — do not delete `PulseDataPanel`).
4. No changes needed to routing (`/admin/ai/graph`) or the sidebar entry — they already exist.
5. Optional smoke test: `carbon-frontend/src/__tests__/KnowledgeGraphPanel.test.jsx` — renders
   the offline/empty state without crashing when the fetch rejects (mirror existing test style).

### Task C — Backend/devops: scheduler sidecar + event-loop fix (backend-worker)

1. **Fix `run_cognition_loop.py` default mode** per Fact 6: run a real asyncio event loop so
   `AsyncIOScheduler` jobs actually fire. Keep `--run-once` and `--status` behavior identical.
   Correct the misleading docstring.
2. **Verify the loop actually fires** (required evidence, not optional): with a temporarily
   reduced interval (env override e.g. `COGNITION_HEALTH_INTERVAL=5`), run the command briefly
   and confirm `health_check` increments (`--status` in a second process won't see in-process
   state — instead assert via logs or `CognitionSweepRun` rows appearing). Document the evidence
   in the report-back. Do NOT leave the reduced interval in any committed config.
3. Add a scheduler sidecar to `docker-compose.yml`:
   - new `scheduler` service: same `build: ./backend`, same `env_file`, `restart: unless-stopped`,
     `depends_on: [backend]`, `volumes` mirroring the backend service, **no** port publish,
     `command: sh -c "python manage.py migrate --noinput && python manage.py run_cognition_loop"`.
   - Do **not** change the `backend` service's command (Gunicorn stays primary).
4. Add a short note to `README.md` (or `docs/deployment.md`) documenting how to run the scheduler
   locally: `cd backend && ../.venv/bin/python manage.py run_cognition_loop` (and the `--status`/
   `--run-once` shortcuts), plus the expected behavior that LLM sweeps log errors under POE
   (model mismatch) while non-LLM sweeps succeed.
5. **No new tests strictly required for Task C**, but a regression test asserting
   `start_scheduler()` is driven by a running loop is valuable if cheap; otherwise rely on the
   manual evidence in (2).

---

## 4. DO-NOT-TOUCH (hard boundaries)

- `backend/ai/store.py` public API (`Session` methods) — no additions/removals.
- `backend/ai/engine/knowledge_graph/models.py` (inert SQLAlchemy constants — leave as-is).
- The `backend` service command in `docker-compose.yml` and `backend/entrypoint.sh` (Gunicorn).
- `PulseDataPanel.jsx` — **reuse** it for the Table toggle; do not refactor its internals.
- Any auth/permission semantics beyond `IsAuthenticated` (CBAC gating is Phase F).
- Existing `--run-once` / `--status` command-line contract (behavior must not change).

---

## 5. VERIFICATION GATES (Master runs before commit)

```
cd backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py check
cd backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run
cd backend && /home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests dq/tests -q
bash /home/ahmed/aast/carbon/.ai-toolkit/scripts/verify.sh backend
bash /home/ahmed/aast/carbon/.ai-toolkit/scripts/verify.sh frontend
bash /home/ahmed/aast/carbon/.ai-toolkit/scripts/verify.sh antipatterns
cd carbon-frontend && npm run build        # no build errors
cd carbon-frontend && npm test -- --run    # vitest green (or unchanged)
```

Plus targeted smoke:
- `GET /carbon-api/ai/pulse/graph/` returns the normalized `{nodes, edges, stats}` envelope
  (authenticated), with no dangling edges and no leaked secret values.

---

## 6. TESTS TO WRITE

- `backend/ai/tests/test_graph_api.py` — shape, redaction, dangling-edge drop, truncation flag,
  auth-gated (Task A).
- (Optional) `carbon-frontend/src/__tests__/KnowledgeGraphPanel.test.jsx` — offline/empty render
  smoke (Task B).

---

## 7. REPORT BACK

Report, in order:
1. Files created / changed (paths).
2. The exact fix applied to `run_cognition_loop.py` and the **evidence** that a scheduled job
   actually fired (logs or `CognitionSweepRun` rows) — the honest proof the event loop now runs.
3. Graph endpoint response shape (one sample, truncated) and frontend screenshot/description.
4. Gate results (each of the §5 commands, pass/fail).
5. Any deviations from this spec and why.
6. Suggested Phase F scope note (CBAC gating) — one line.
