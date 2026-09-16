# Sprint 8 — Streaming SSE: human-speed AI responses

**Owner:** Master Architect · **Status:** 🔨 Spec written — ready for Backend Worker dispatch
**Goal:** AI responses arrive chunk by chunk with a typing effect, instead of a single
blob after the whole pipeline finishes.

---

## Scope

| Conversation type | Streaming behavior | Included |
|---|---|---|
| `chat` | Token/chunk streaming of the final answer (typing effect) | ✅ Phase 8-A + 8-B |
| `dq_suggest` | Stage-progress streaming, structured result at end | ⭕ Phase 8-C (optional, follow-on) |
| all others (`dq_validate`, `nl_query`, `anomaly`, …) | unchanged (non-streaming) | ❌ out of scope |

Do **not** change the behavior of any non-`chat` task. The existing
`POST /messages/` endpoint stays intact as the non-streaming path.

---

## Current state (verified facts — do not re-discover)

These are already in the codebase. Build on them; do not rebuild.

1. `backend/ai/engine/cognition/turn/runner.py` — `TurnPipelineRunner.run(..., stream_callback=None)` **already**
   accepts a `stream_callback` and forwards it to `ExecuteWitness.execute(...)`
   (S5, ~line 488) and the ReAct path (~line 272 / 709).
2. `backend/ai/engine/cognition/turn/execute.py` — `ExecuteWitness.execute(...)` **already**
   chunks `text` and calls `await stream_callback(delta)` per chunk when a callback
   is supplied (~lines 125–140). Callback signature: **`async fn(delta: str)`**.
3. `backend/ai/engine_runtime.py`:
   - `dispatch_task()` is **sync** and returns one dict — no streaming variant yet.
   - `_run_chat(instance_id, payload, task_id)` is **async** and currently does **not**
     accept/pass `stream_callback` (needs a small change).
   - `_run_async(coro)` bridges sync→async via `asyncio.run`.
4. `backend/ai/intelligence.py`:
   - `send_message(user, conversation_id, content)` is the sync template: saves the
     user message, builds `ConversationContext` + `Scope`, routes by
     `conversation_type`, then `_send_chat_message(...)` → `_build_ai_message(...)`.
   - `_send_chat_message(conversation, content, conv_ctx, scope)` already applies
     `_prepend_workspace_context` + `_prepend_domain_context` and calls
     `self.provider.chat(chat_request)`.
5. `backend/ai/providers/pulse.py` — `PulseProvider.chat(request)` maps
   `ChatRequest` → `dispatch_task(T_CHAT, payload, timeout=15)` and returns
   `ChatResponse`.
6. `backend/ai/workspace_api.py` — `WorkspaceConversationViewSet.send_message` is the
   DRF `@action(detail=True, methods=["post"], url_path="messages")` returning `Response(result)`.
7. `backend/ai/engine/llm/provider.py` — LLM client is `AsyncOpenAI`
   (`client.chat.completions.create(**kwargs)`); `stream=True` is supported by the
   SDK but **not** used today.
8. Frontend: `carbon-frontend/src/api/aiWorkspace.js` `sendMessage()` does a single
   `POST .../messages/` and gets the full persisted response back.
   `carbon-frontend/src/shell/AIConversationView.jsx` `handleSend` displays it and
   also polls while `conversation.status === "working"`.

> **Streaming strategy decision:** Phase 8-A streams the **final answer text** via
> the existing S5 `ExecuteWitness` chunking. This produces the typing effect with
> the least new plumbing. The S3 draft LLM call still runs first (non-streamed), so
> there is a short latency head before the first chunk — acceptable for this sprint.
> True token-level streaming of the S3 draft (via OpenAI `stream=True`) is a future
> optimization, deliberately out of scope.

---

## SSE wire contract

`POST /carbon-api/ai/workspace/conversations/{id}/messages/stream/`
Content-Type: `text/event-stream`. Body: `{"content": "..."}` (same as `SendMessageSerializer`).

Frames are `data: <json>\n\n`:

| `type` | payload | meaning |
|---|---|---|
| `chunk` | `{"type":"chunk","content":"…"}` | one text delta to append to the streaming bubble |
| `done` | `{"type":"done","conversation":{...}}` | terminal success; `conversation` is the same shape `GET .../{id}/` returns (persisted messages included) |
| `error` | `{"type":"error","error":"…"}` | terminal failure; human-readable message |

Rules:
- Exactly one terminal frame (`done` **or** `error`) per request.
- On `error`, the user message **must still be persisted** (mirror `send_message`'s
  save-before-work behavior) and conversation `status` reset to a non-working state.
- No keep-alive comments required (Django `StreamingHttpResponse` + uvicorn/gunicorn
  is fine without them; add a `retry:` line only if the frontend needs it).

---

## Phase 8-A — Backend (Backend Worker)

### Task 8-A1 — thread streaming in `_run_chat`

File: `backend/ai/engine_runtime.py`

- Add `stream_callback=None` parameter to `_run_chat(instance_id, payload, task_id, *, stream_callback=None)`.
- Pass it through: `runner.run(..., stream_callback=stream_callback)`.

No other behavior change. Non-streaming callers are unaffected (`stream_callback=None`).

### Task 8-A2 — `dispatch_task_stream`

File: `backend/ai/engine_runtime.py`

Add a **sync generator** `dispatch_task_stream(task_type, payload, *, instance_id="carbon")`
that yields `(kind, value)` tuples:

- Only `task_type == "chat"` is supported this sprint. For any other task, yield
  `("error", "streaming not supported for {task_type}")` and stop.
- Bridge the async engine to a sync generator with a `queue.Queue` + daemon thread:

```python
import queue, threading

def dispatch_task_stream(task_type, payload, *, instance_id="carbon"):
    if task_type != "chat":
        yield "error", f"streaming not supported for {task_type!r}"
        return
    q: queue.Queue = queue.Queue()

    async def _collect():
        async def cb(delta: str):
            q.put(("chunk", delta))
        try:
            result = await _run_chat(instance_id, payload, _new_task_id(), stream_callback=cb)
            q.put(("done", result))
        except Exception as exc:  # noqa: BLE001 - fail-visible
            logger.exception("chat stream failed for instance=%s", instance_id)
            q.put(("error", f"chat failed: {exc}"))
        finally:
            q.put(("eof", None))

    def _thread_target():
        _run_async(_collect())

    threading.Thread(target=_thread_target, daemon=True).start()
    while True:
        kind, value = q.get()
        if kind == "eof":
            break
        yield kind, value
```

Export it in `__all__`.

### Task 8-A3 — `PulseProvider.chat_stream`

File: `backend/ai/providers/pulse.py`

Add a method `chat_stream(self, request: ChatRequest)` that mirrors `chat()` but:
- builds the same `payload` (message + conversation_history),
- calls `dispatch_task_stream(T_CHAT, payload)` and yields the `(kind, value)` tuples
  directly (it can be a generator that `yield from`s the dispatcher).
- The `"done"` value is the same dict shape `chat()` reads from `dispatch_task`
  (`{"status":"completed","result":{"content":..., "follow_up_questions":[...], "execution_ms":...}}`).

Keep `chat()` untouched.

### Task 8-A4 — `CarbonIntelligence.send_message_stream`

File: `backend/ai/intelligence.py`

Add `send_message_stream(self, user, conversation_id, content)` — a **generator** that
mirrors `send_message` but yields SSE-ready dicts instead of returning once:

1. Load conversation (same `DoesNotExist → ValueError` guard as `send_message`).
2. Save the user message (`AIMessage(role="user", content=content)`) — identical to `send_message`.
3. Build `conv_ctx` + `scope` + set `conversation.status = "working"` — identical to `send_message`.
4. For `conversation_type == "chat"` only, build the same `ChatRequest` that
   `_send_chat_message` builds (including `_prepend_workspace_context` +
   `_prepend_domain_context`), then:
   - iterate `self.provider.chat_stream(chat_request)`:
     - `("chunk", delta)` → `yield {"type": "chunk", "content": delta}` and accumulate.
     - `("error", msg)` → finalize failure (see below), `yield {"type": "error", "error": msg}`, return.
     - `("done", result)` → build the AI message from `result["result"]["content"]` +
       `follow_up_questions` using `_build_ai_message`, persist it, set
       `conversation.status` to its final value (mirror `send_message`'s completion,
       including `needs_input` detection if present), then
       `yield {"type": "done", "conversation": self.get_conversation(user, conversation_id)}`, return.
5. For **any other** `conversation_type`, fall back to the existing synchronous path
   (`send_message`) and emit a single `done` frame with the resulting conversation —
   do **not** attempt to stream.

**Failure persistence (important):** if the provider errors, still write an AI message
(or set status appropriately) so the conversation is not stuck in `working`, exactly
as the current `send_message` failure path behaves. Reuse the same finalization logic.

### Task 8-A5 — SSE endpoint

File: `backend/ai/workspace_api.py`

Add:

```python
from django.http import StreamingHttpResponse

@action(detail=True, methods=["post"], url_path="messages/stream")
def send_message_stream(self, request, pk=None):
    serializer = SendMessageSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    def event_stream():
        try:
            for frame in self.intelligence.send_message_stream(
                user=request.user,
                conversation_id=pk,
                content=serializer.validated_data["content"],
            ):
                yield f"data: {json.dumps(frame)}\n\n"
        except ValueError as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
    return StreamingHttpResponse(event_stream(), content_type="text/event-stream")
```

Import `json` at module top. Note the `ValueError` from a missing conversation maps to
the `error` frame (404 semantics are intentionally softened for SSE).

---

## Phase 8-B — Frontend (Frontend Worker)

### Task 8-B1 — streaming API

File: `carbon-frontend/src/api/aiWorkspace.js`

Add `sendMessageStream(token, conversationId, content, { onChunk, onDone, onError })`
that:

- uses `fetch` + `response.body.getReader()` + `TextDecoder` (NOT `EventSource` —
  `EventSource` cannot send a POST body or an `Authorization` header),
- sends the JWT exactly as `apiFetch` does (read `apiFetch` in `src/api/api.js` and
  replicate its auth header + base URL),
- parses `data: <json>\n\n` frames, calling `onChunk(content)` / `onDone(conversation)`
  / `onError(message)` appropriately,
- handles a non-200 response (e.g. 401) by invoking `onError`.

### Task 8-B2 — streaming bubble

File: `carbon-frontend/src/shell/AIConversationView.jsx`

- In `handleSend`, for the `chat` conversation type, prefer `sendMessageStream`:
  1. append the user message immediately,
  2. create a transient "streaming" AI bubble and append deltas to it,
  3. on `done`, replace the transient bubble with the persisted AI message(s) from the
     returned `conversation`, and reconcile `conversation.status`,
  4. on `error`, drop the transient bubble and surface the error (existing
     `notifyFromError` + offline banner behavior).
- Keep the existing non-streaming `sendMessage` path for non-`chat` conversations.
- Disable the input bar while streaming (reuse `sending` state).
- Keep the existing `working`-state polling as a safety net; it must not clobber the
  streaming bubble — if a poll returns while streaming is active, skip the update.

---

## Phase 8-C (optional follow-on) — `dq_suggest` progress streaming

Not required for this sprint to be complete. If time permits:
- Add a `progress` frame type (`{"type":"progress","stage":"s3_draft",...}`) emitted by
  the runner's existing `_broadcast_run` events, surfaced through the same SSE path.
- Frontend renders a small "working…" stepper for `dq_suggest`.
Do not block the `chat` streaming work on this.

---

## Verification gates (MUST all pass before commit)

```bash
# Backend (interpreter = /home/ahmed/aast/carbon/.venv/bin/python)
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python -m pytest ai dq accounts -q

# Stream endpoint smoke test (manual or via a test):
#   POST /carbon-api/ai/workspace/conversations/{id}/messages/stream/
#   expect: data: {"type":"chunk",...}  ...  data: {"type":"done","conversation":{...}}

# Frontend
cd /home/ahmed/aast/carbon/carbon-frontend && npm run lint && npm test && npm run build
```

Add at least **10 backend tests** in `backend/ai/tests/test_chat_stream.py` covering:
- `dispatch_task_stream("chat", ...)` yields chunks then a `done` (stub the LLM).
- non-`chat` task type yields a single `error`.
- `send_message_stream` persists the user message even when the provider errors.
- the SSE view returns `text/event-stream` and includes a `done` frame.
- the non-streaming `POST /messages/` endpoint is unchanged (regression).

---

## Out of scope

- True token-level streaming of the S3 draft (OpenAI `stream=True` through
  `route_chat` → `DraftWitness.draft`). Future optimization.
- Streaming for `dq_validate`, `nl_query`, `anomaly`, `report_draft`, `schema_analyze`,
  `fix_suggest`.
- WebSocket transport (SSE is sufficient and simpler behind the existing proxy).
- `dq_suggest` progress stepper (Phase 8-C).

---

## Critical hazards (read before coding)

1. **Dual-namespace imports.** The repo is importable as both `ai.*` and `backend.ai.*`,
   which are **different module objects** (verified in Sprint 7). Within one process this
   can cause silent double-registration or a no-op. In `workspace_api.py` and
   `intelligence.py`, the existing convention is `from ai.intelligence import ...` /
   `from ai.serializers import ...`. **Match the surrounding file's existing import style
   exactly** — do not mix `backend.ai.*` and `ai.*` in the same file.
2. **Sync/async bridge.** `StreamingHttpResponse` consumes a **sync** generator, but the
   engine is async. Use the queue+thread bridge exactly as specified in Task 8-A2 — do
   not call `asyncio.run` inside a Django request handler that may already be on an event
   loop, and never block the request thread awaiting the pipeline synchronously.
3. **Never leave a conversation stuck in `working`.** The failure path must finalize
   status exactly like `send_message` does today.
4. **`stream_callback` is `async`.** Any callback you inject must be an `async def`
   `(delta: str)`; a sync callback will break the awaited call site in `execute.py`.
5. **Do not `git add -A`.** Stage only `backend/ai/engine_runtime.py`,
   `backend/ai/providers/pulse.py`, `backend/ai/intelligence.py`,
   `backend/ai/workspace_api.py`, `backend/ai/tests/test_chat_stream.py`,
   `carbon-frontend/src/api/aiWorkspace.js`, and
   `carbon-frontend/src/shell/AIConversationView.jsx`.
