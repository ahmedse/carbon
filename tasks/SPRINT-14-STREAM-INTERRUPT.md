# Sprint 14 — Streaming + Interrupt for ALL types

**Owner:** Master Architect · **Status:** 🚀 Ready for Backend Worker dispatch (after Sprint 13)
**Design:** `docs/DESIGN_AI_WORKSPACE_NEXTGEN.md` §5.1–5.2 (Phase 2 backend)
**Contract:** `.ai-toolkit/shared/ai-contract.md` §6 (graceful degradation)

## Goal
Replace 2s polling for non-chat types with **server-driven progress streaming**, and add
**stop/regenerate/edit**. The user never loses agency mid-turn.

## Current state (verified facts — do not re-discover)
- `backend/ai/engine_runtime.py` — `dispatch_task_stream(task_type, payload)` currently
  only supports `task_type == "chat"` (returns `("error", ...)` otherwise). `dispatch_task`
  is sync and covers all task types via `_TASK_HANDLERS`. `_run_chat` is async.
- `backend/ai/providers/pulse.py` — `PulseProvider.chat_stream` calls
  `dispatch_task_stream(T_CHAT, payload)`. Non-chat provider methods are sync
  (`dispatch_task(T_DQ_SUGGEST, ...)` etc.).
- `backend/ai/intelligence.py` — `send_message_stream` routes non-chat to `send_message`
  (sync, no progress). `_send_*_message` methods exist per type. `_save_assistant_message`,
  `_build_ai_message`, `_serialize_conversation` are the persistence helpers.
- `backend/ai/workspace_api.py` — `send_message_stream` wraps `intelligence.send_message_stream`.

## Tasks

### 1. Progress-frame streaming for non-chat (in-process, no engine rewrite)
MODIFY `backend/ai/intelligence.py` `send_message_stream`:
- For non-chat types, do NOT delegate to `send_message`. Instead:
  1. Persist user message (same as chat path).
  2. Build history + fresh scope, mark `working` (same as chat path).
  3. `yield {"type":"progress","stage":"start","message": <stage label>}`.
  4. Call the existing `_send_*_message` for the type (they are sync and return the
     serialized assistant message dict). Wrap in try/except as in chat path (fail-visible,
     never stuck in working).
  5. `yield {"type":"progress","stage":"done","message":"Done"}`.
  6. `yield {"type":"done","conversation": self.get_conversation(user, conversation_id)}`.
- Add a `_progress_stage_label(conversation_type)` helper returning the human label
  (e.g. `dq_suggest` → "Analyzing table profile…", `nl_query` → "Translating question to SQL…",
  `anomaly` → "Detecting anomalies…", `dq_validate` → "Validating rows…").
- For the "working" stage, also yield a progress frame BEFORE the blocking call so the
  frontend immediately shows activity (replaces the 2s poll).

### 2. GenerationRegistry + stop
CREATE `backend/ai/generation_registry.py`:
```python
import threading
class GenerationRegistry:
    def __init__(self):
        self._events: dict[str, threading.Event] = {}
        self._lock = threading.Lock()
    def start(self, conversation_id: str) -> None:  # set a fresh Event
    def cancel(self, conversation_id: str) -> bool:  # set Event, return whether one was running
    def is_cancelled(self, conversation_id: str) -> bool:
    def finish(self, conversation_id: str) -> None:  # remove
GENERATIONS = GenerationRegistry()
```
MODIFY `backend/ai/intelligence.py`:
- Import `GENERATIONS`. In `send_message_stream`, call `GENERATIONS.start(conversation_id)`
  at the start and `GENERATIONS.finish(conversation_id)` in a `finally`. Check
  `GENERATIONS.is_cancelled` between frames (chat chunks and progress frames). If cancelled:
  persist a `status="stopped"` assistant message with the partial content (chat) or
  "Interrupted by user." (non-chat), set conversation status `completed`, and yield
  `{"type":"stopped","conversation": ...}` then return.
- New method `stop_generation(self, user, conversation_id)` → `GENERATIONS.cancel(str)` +
  mark the latest `AIGeneration` row (if exists) `cancelled`. Return `{"stopped": bool}`.
- Create an `AIGeneration` row in `send_message_stream` when a generation starts (token =
  uuid4 hex), mark it `completed` on normal done, `cancelled` on stop, `failed` on error.

### 3. stop / regenerate / edit endpoints
MODIFY `backend/ai/workspace_api.py`:
- `@action(detail=True, methods=["post"], url_path="stop")` `stop_generation` → `intelligence.stop_generation`.
- `@action(detail=True, methods=["post"], url_path="messages/(?P<message_id>[^/.]+)/regenerate")`
  `regenerate_message` → new `intelligence.regenerate_message(user, conversation_id, message_id)`:
  finds the assistant message, sets `parent_message_id` on the new assistant reply, and
  re-runs the send path with the user message that preceded it (find the user message with
  the largest `created_at` < that assistant message's `created_at`). Returns serialized
  conversation (non-streaming, sync is fine).
- `@action(detail=True, methods=["patch"], url_path="messages/(?P<message_id>[^/.]+)")`
  `edit_message` → new `intelligence.edit_message(user, conversation_id, message_id, content)`:
  updates a USER message's `content` (only user messages editable), then re-runs send.
  Returns serialized conversation. 404 on ValueError; 400 on non-user message.
- New serializer `EditMessageSerializer` (`content` required, non-blank).

### 4. Frontend SSE contract (document only — do NOT touch frontend)
The stream now emits `progress`, `done`, `error`, `stopped`, `chunk` frames. The
`done` frame should include `"usage": {...}` when available (model, tokens, cost, latency).
Populate `AIMessage.token_usage_json` in `_save_assistant_message`/`_build_ai_message` via an
optional `usage` kwarg; for chat streaming, capture provider `execution_ms` from the done
result if present.

### 5. Tests (REQUIRED)
CREATE `backend/ai/tests/test_workspace_stream.py`:
- non-chat `send_message_stream` yields a `progress` frame then a `done` frame
- `stop_generation` sets the cancellation event and returns `{"stopped": true}`
- cancellation mid-stream persists a `stopped` assistant message and never leaves status `working`
- `regenerate_message` creates a new assistant message with `parent_message_id` set
- `edit_message` on a user message updates content; on an assistant message raises ValueError
- provider failure yields `error` frame and persists a `failed` message (never stuck `working`)

## DO NOT TOUCH
- `backend/ai/engine/**` (keep the engine stateless; do NOT add progress to the engine runner)
- `carbon-frontend/**`
- `backend/ai/providers/pulse.py` (no change needed — non-chat stays sync)

## GATES (run ALL, paste output)
```bash
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python -m pytest ai -q
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py check
./.ai-toolkit/scripts/verify.sh backend
./.ai-toolkit/scripts/verify.sh antipatterns
```

## HARD RULES
- `timezone.now()` only.
- Conversation must NEVER be left `working` after a stream ends (all terminal paths persist + set status).
- Stop is idempotent (cancelling with no running generation returns `{"stopped": false}`, not an error).
- Graceful degradation: provider timeout/error → `error` frame, never a 500.

## REPORT BACK
Task-by-task ✅/❌, test count, terminal output, deviations.
