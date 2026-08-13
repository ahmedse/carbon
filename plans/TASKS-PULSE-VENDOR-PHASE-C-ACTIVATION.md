# TASKS — Pulse Vendor Phase C: Intelligence Core Activation & Operations

**Owner:** Master Architect (verify-then-commit)
**Status:** in progress
**Depends on:** Phase B (observability read layer, commit `9c86575`)

## Context

The full Pulse engine is vendored at `backend/ai/engine/` (import root `ai.engine.*`).
It ALREADY contains: per-run `BudgetTracker` (`agent/budget.py`), guardrails
(`agent/guardrails.py` — rate-limit + budget hooks), the LLM router
(`llm/router.py` — task→model routing, `estimate_cost`, `_check_budget` daily $ cap,
`route_chat`), caching (`knowledge_graph/cache_store.py` + `AI_CACHE_TTL_SECONDS`),
MCP (`agent/mcp_client.py`), tool catalog (`agent/tools.py` + `registry.py` +
`ToolExecution`/`TaskExecution`), agents (`agent/workers.py`/`executor.py` +
`Agent`/`AgentHandoff`), planning (`knowledge_graph/multi_step_planner.py` +
`KgQueryPlan`/`KgPlanStep`), and the knowledge graph (`KnowledgeNode`/`KnowledgeEdge`/
`KgNode`/`KgEdge`).

Phase B wired a read-only console layer (13 panels, `backend/ai/observability_api.py`)
and the engine runs in-process (`backend/ai/engine_runtime.py`).

**The gap is now operational, not structural.** The LLM provider is now LIVE
(POE, OpenAI-compatible: `LLM_API_KEY`/`LLM_BASE_URL`/`LLM_MODEL` in `backend/.env`,
verified returning a real completion). Phase C surfaces the "manage" knob set and
proves the live LLM flows through the runtime and writes real cost/ledger rows.

## Deliverables

### C1 — Budget & usage aggregate endpoint (backend)
`GET /carbon-api/ai/pulse/usage/` (read-only `APIView`, `IsAuthenticated`), reading
`ai.models.core.LLMCallLog` (fields: `model`, `llm_calls`, `total_tokens`, `cost_usd`,
`duration_ms`, `created_at`, `instance_id`):

- `budget_usd` — from `get_settings().LLM_DAILY_BUDGET_USD`
- `spent_today_usd`, `tokens_today`, `calls_today`, `calls_total`, `tokens_total`
  (aggregate over today's `created_at__date` and over all rows)
- `remaining_usd`, `budget_exceeded` (bool)
- `by_model` — per-`model` sum of `cost_usd` / `total_tokens` / `llm_calls`
- `by_day` (last 7 days) — per-day `cost_usd` / `total_tokens` / `llm_calls`

Guard with `try/except` → `{error: "..."}` (never 500 the console, mirrors `ops_api.py`).

### C2 — Engine settings/knobs endpoint (backend)
`GET /carbon-api/ai/pulse/settings/` (read-only, `IsAuthenticated`), returning the
EFFECTIVE engine configuration from `ai.engine.core.config.get_settings()` plus the
registries that back the capabilities. MUST NOT leak secrets — apply the same
`_SECRET_KEY_RE` redaction used in `observability_api.py` to any dict value; never
return `LLM_API_KEY`. Include:

- `llm`: `base_url`, `model`, `normal_model`, `cognition_model`, `embedding_model`,
  `eval_model`, `daily_budget_usd`, `allow_expensive_models`
- `limits`: `max_tokens_per_run`, `max_tool_calls_per_run`, `budget_enforcement`,
  `run_token_budget_default`, `run_token_budget_worker_share`, `run_token_budget_min_worker`,
  `default_autonomy_level`, `max_workers`, `worker_timeout_sec`
- `cache`: `AI_CACHE_TTL_SECONDS` (from Django settings), plus cache-store stats if
  reachable (`knowledge_graph/cache_store.py`) — hits/misses/size, empty `{}` if no-op
- `rate_limit`: `AI_RATE_LIMIT_PER_MINUTE` (Django settings)
- `routing`: the engine `_TASK_MODEL_MAP` (task → resolved model name) via
  `get_model_for_task(task)` for the known task list
- `mcp_servers`: from the engine MCP config/registry (empty list if none configured)
- `tools_catalog`: registered tool names/descriptions from `agent/tools.py`/`registry.py`
- `agents`: registered agent names from `agent/registry.py` (or `agent/__init__.py`)

Return everything under safe keys; on any sub-step failure, degrade to that key's
empty value rather than failing the whole request.

### C3 — Frontend: two console surfaces
- `carbon-frontend/src/api/aiPulse.js`: add `getUsage()` and `getSettings()` (via
  `apiFetch`, matching existing `getInventory`/`getData` style).
- New `BudgetUsagePanel.jsx` and `EngineSettingsPanel.jsx` under
  `carbon-frontend/src/pages/admin/ai/` (follow the existing panel pattern). Add a
  Budget/Usage summary card (spent vs budget, tokens, per-model table) and a settings
  read view (key/value sections, no secrets). Wire the lazy imports + routes in
  `carbon-frontend/src/App.jsx` and the AI admin nav (same place Phase B's panels are
  registered).

### C4 — Real-execution verification + tests
- A guarded pytest `backend/ai/tests/test_live_llm_activation.py`:
  `@pytest.mark.skipif(not os.environ.get("LLM_API_KEY"), reason="no live LLM")` —
  asserts `chat_completion` returns non-empty text; asserts `route_chat` returns
  `finish_reason != "budget_exceeded"` with a populated `model` and `cost_usd >= 0`.
- Assert the `usage/` and `settings/` endpoints return 200 and non-leaky payloads
  (no `LLM_API_KEY` string, no key named `api_key`/`token` with a real value) in
  `test_observability_api.py` style (authenticated client).

## Non-goals (deferred)
- Scheduler for the periodic cognition sweeps (memory consolidation, distillation,
  proactive insights, skills consolidation, schema-drift) — Phase D.
- Rich KG graph visualization (D3/force layout) — Phase D.
- Any write/mutation surface (this phase is read-only; the knobs stay env-driven).

## Verification gates (Master runs before commit)
```
cd backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py check
cd backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run
cd backend && /home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests dq/tests -q
cd backend && bash .ai-toolkit/scripts/verify.sh backend
cd backend && bash .ai-toolkit/scripts/verify.sh antipatterns
cd carbon-frontend && npm run build
```
Commit scoped files only (never `git add -A`).
