# Sprint 19 — W1-A: Agent/Tool/MCP execution seam + streamed events + verbosity + abort

**Owner:** Master Architect · **Worker Role:** backend-worker · **Model:** DeepSeek V4-Flash
**Status:** 🚀 READY for dispatch
**Design:** `docs/DESIGN_AI_WORKSTATION.md` §2.2, §2.5 (clustered frame protocol)
**Master index:** `TASKS.md` Phase W1-A (lines 1753–1816)
**Depends on:** chat SSE (`dispatch_task_stream` + `workspace_api` `messages/stream`) and `generation_registry`.

## Goal
Give the workstation a **user-initiated "run an agent action / tool" path** that streams
**clustered** progress frames (`turn_*` / `tool_*`), honours `verbosity` (concise/full),
and can be **aborted** mid-run — without rewriting the engine or forking the existing
RULE_21 confirmation gate.

## Current state (verified facts — do NOT re-discover or rebuild)

### Already exists — REUSE, do not duplicate
- `backend/ai/engine/agent/executor.py` — `HostAPIExecutor` with `create_pending_execution`,
  `confirm_execution`, `decline_execution`, `call_api_direct` (RULE_21 staging).
- `backend/ai/host_executor.py` — a `host_executor` that re-implements the same
  confirm/decline semantics (used by the current `confirm_tool_execution` view).
- `backend/ai/workspace_api.py` — `confirm_tool_execution` (`url_path="tool-executions/confirm"`,
  ~line 396) and `decline_tool_execution` (~line 542), both via `ToolExecutionActionSerializer`.
- `backend/ai/serializers.py:143` — `ToolExecutionActionSerializer`.
- `backend/ai/engine/agent/registry.py` — `AgentRegistry.register_agent / get_agent /
  can_handoff / get_workers_for`.
- `backend/ai/engine/agent/tools.py` — `get_tool_definitions()` (static + plugin + MCP),
  `get_tool_executors()` (static + plugin + MCP), `STATIC_TOOL_DEFINITIONS`, `MCP_TOOLS`,
  `init_mcp_tools(registry)`, and the `execute_*` functions.
- `backend/ai/engine/agent/mcp_client.py` — `MCPToolRegistry.connect_all`, `MCPServer`, `MCPTool`.
- `backend/ai/generation_registry.py` — `GENERATIONS.start/cancel/is_cancelled/finish`
  (per-conversation `threading.Event`, process-local).
- `backend/ai/observability_api.py` — `_redact_secrets(value)` (line 173) + `_SECRET_KEY_RE`.
- **Catalog read endpoints already exist** — `backend/ai/activation_api.py::PulseSettingsView`
  (`GET /carbon-api/ai/pulse/settings/`) returns `mcp_servers` (`{name,command,args}`),
  `tools_catalog` (`{name,description,kind,requires_confirmation,capability,app_identifier}`),
  and `agents` (names). **Do not create a second catalog route.**

### The genuine gap
- No streamed "run this tool/agent action now" path. `engine_runtime.dispatch_task_stream`
  only handles `task_type == "chat"` and yields `("chunk"|"done"|"error", value)`.
- No clustered `turn_*`/`tool_*` frame emitter with `verbosity` + abort.
- Tool `parameters` (args JSON schema) is NOT currently surfaced in `tools_catalog` —
  the run form needs it to render arg inputs.

## Files to Change
- `backend/ai/engine_runtime.py` — MODIFY: add `dispatch_action_stream(...)` that yields
  **clustered** frames keyed by `turn_id`/`step_id`, honours `verbosity`, checks
  `generation_registry.is_cancelled()` between steps.
- `backend/ai/providers/pulse.py` — MODIFY: `run_tool_stream(...)` passthrough (mirror
  `chat_stream` at line 511 which delegates to `dispatch_task_stream`).
- `backend/ai/intelligence.py` — MODIFY: `run_agent_action_stream(...)` generator + guard
  chain (scope/mutation/rate).
- `backend/ai/workspace_api.py` — MODIFY: `POST .../conversations/{id}/actions/stream/` SSE action.
- `backend/ai/activation_api.py` — MODIFY: add `parameters` (args schema) to each
  `_settings_tools()` entry, and enrich `_settings_agents()` to return
  `{id, name, role, tool_set, is_active}` (not just names).
- `backend/ai/tests/test_agent_action_stream.py` — ADD.

## Tasks

### 1. Clustered frame protocol (design §2.5)
Emit frames in this order, nested by id:
```
turn_start {turn_id, label, verbosity}
  tool_start {turn_id, step_id, tool, category}      category ∈ agent|mcp|tool
  tool_arg   {step_id, args}                          (full verbosity only)
  tool_result{step_id, result}                        (full verbosity only, redacted)
  tool_end   {step_id, status}                        status ∈ completed|failed|stopped|needs_confirmation
turn_end {turn_id, status, summary}
```
- `verbosity ∈ {concise, full}`: `concise` emits `tool_start` + `tool_end` only
  (name + status); `full` additionally emits `tool_arg` + `tool_result`.
- Route every `tool_result` through `_redact_secrets` (import from `observability_api`).

### 2. Streamed run path
- `engine_runtime.dispatch_action_stream(...)` — an async generator yielding `(kind, value)`
  tuples (`kind ∈ {"frame", "done", "error"}`), parallel to `dispatch_task_stream`.
  Resolve the tool executor via `tools.get_tool_executors()` (or agent via `AgentRegistry`);
  do NOT write a second tool registry.
- `intelligence.run_agent_action_stream(...)`:
  1. Persist the user message + mark the conversation `working` (mirror `send_message_stream`).
  2. `GENERATIONS.start(conversation_id)` at start, `GENERATIONS.finish(...)` in `finally`.
  3. Yield `turn_start`, then per step the `tool_*` frames, then `turn_end`.
  4. Between steps: `if GENERATIONS.is_cancelled(conversation_id)` → emit
     `tool_end{status:"stopped"}` then `turn_end{status:"stopped", summary:"Stopped by user"}`
     and return (never `error`, never leave `working`).
- Every step writes a `ToolExecution` row (`backend/ai/models/core.py:188`, already exists):
  status `running` → `completed|failed|stopped`. Host-mutating tools stay
  `requires_confirmation=True` (RULE_21) — stage via `HostAPIExecutor.create_pending_execution`
  and emit `tool_end{status:"needs_confirmation", execution_id}` so the frontend reuses the
  existing confirm/decline endpoints. Do NOT auto-run mutations.

### 3. SSE endpoint
`workspace_api.py`: `@action(detail=True, methods=["post"], url_path="actions/stream")`
wrapping `intelligence.run_agent_action_stream`, streaming the same `data:` frame shape as
`send_message_stream`. Request body: `{action_type: "tool"|"agent", tool?, agent?, args, verbosity}`.

### 4. Catalog enrichment (activation_api.py)
- `_settings_tools()`: add `"parameters": function.get("parameters", {})` to each entry.
- `_settings_agents()`: return `list(Agent.objects.filter(is_active=True).values("id","name","role","tool_set","is_active"))`.

## DO NOT TOUCH
- Frontend files.
- `engine/agent/executor.py` + `host_executor.py` confirmation semantics (call them, don't fork).
- `activation_api.py` route registration — keep `GET /ai/pulse/settings/` as the single catalog surface.

## Verification Gate
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python manage.py check
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai -q
```
No new models are expected; if you add fields, also run
`/home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run`.

## Hard rules
- `python -m pytest`, **never** `manage.py test` (Conflicting 'aiconversation' models).
- Venv is `/home/ahmed/aast/carbon/.venv` (repo root, NOT `backend/`).
- API prefix `/carbon-api/` (RULE_4). Engine stays stateless (RULE_6). Timezone-aware datetimes.

## Output contract
Append a Summary + Task Results + Files Changed + Verification Output + Deviations +
Issues Found section to `TASK-RESULTS.md`.

## Notes for the Master
- Abort correctness is the acceptance bar: `cancel()` mid-run must yield a `stopped`
  final frame, a `ToolExecution(status="stopped")` row, and no stuck `working` message.
  Test this explicitly (add a `test_agent_action_stream.py` case that cancels mid-run).
