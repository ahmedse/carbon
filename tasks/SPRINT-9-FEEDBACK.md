# Sprint 9 — Feedback Persistence: the learning flywheel

**Owner:** Master Architect · **Status:** 🔨 Spec written — ready for Backend Worker dispatch
**Goal:** Every accept / reject / correct a user makes on an AI answer is persisted on
the message and becomes learnable signal for the org's knowledge.

---

## Scope

| Piece | What | Included |
|---|---|---|
| `AIMessage.outcome` + `correction_text` + migration | persist user judgement | ✅ Phase 9-A |
| `POST .../messages/{message_id}/feedback/` | set outcome on a message | ✅ Phase 9-A |
| Accept / Reject / Correct controls on AI bubbles | user-facing feedback UI | ✅ Phase 9-B |
| Async learning job (KG weights + long-term memory) | consume feedback | ⭕ Phase 9-C (follow-on) |

Do **not** change the `send_message` / `send_message_stream` paths. Feedback is a
separate, idempotent write on an already-persisted message.

> **Important distinction (do not confuse):** DQ *suggestion* accept/reject
> (Phase G, `acceptSuggestion`/`rejectSuggestion` → creates a DQ rule, gated on
> `dq:manage_rules`) is a **different feature** from Sprint 9 message *feedback*
> (`outcome` on an `AIMessage`). Sprint 9 does not touch DQ suggestions at all.

---

## Current state (verified facts — do not re-discover)

1. `backend/ai/models/workspace.py` — `AIMessage` has `id` (UUID PK), `conversation` (FK),
   `role` (`user`/`assistant`/`system`), `content` (Text), `metadata_json` (JSON, default dict),
   `created_at` (auto_now_add). **No `outcome` / `correction_text` yet.**
2. `backend/ai/intelligence.py`:
   - `_serialize_message(message)` (~line 1189) returns `{id, conversation_id, role, content,
     metadata_json, created_at}`. Must gain `outcome` + `correction_text`.
   - `get_conversation(user, conversation_id)` (~line 506) loads
     `AIConversation.objects.get(id=…, user=user)` and serializes `.messages.order_by("created_at")`.
     This is the ownership pattern to reuse for feedback (conversation must belong to the user).
   - `_save_assistant_message(conversation, content, *, metadata, status)` creates assistant
     messages — leave untouched.
3. `backend/ai/workspace_api.py` — `WorkspaceConversationViewSet` (GenericViewSet,
   `permission_classes=[IsAuthenticated]`). Existing actions: `send_message`
   (`url_path="messages"`), `send_message_stream` (`url_path="messages/stream"`).
   The `intelligence` property lazily builds `CarbonIntelligence()`.
4. `backend/ai/serializers.py` — `CreateConversationSerializer`, `SendMessageSerializer`,
   `ConversationListSerializer`. Add a `MessageFeedbackSerializer` here.
5. Migrations: latest `ai` migration is `0004_cognitionsweeprun`. The new one is the **next**
   sequential number (worker: let `makemigrations` name it).
6. Frontend:
   - `carbon-frontend/src/api/aiWorkspace.js` — `apiFetch`-based CRUD + `sendMessageStream`.
   - `carbon-frontend/src/shell/AIMessageBubble.jsx` — renders a message; `message` prop shape
     `{role, content, created_at, metadata, metadata_json}` (PropTypes at bottom). Assistant
     messages render `SmartToyIcon`; user messages `PersonIcon`. `isUser = message.role === 'user'`.
   - `carbon-frontend/src/shell/AIConversationView.jsx` — holds conversation + messages state,
     renders `AIMessageBubble` (passes `onAcceptSuggestion`/`onRejectSuggestion`/`canManageRules`),
     uses `notifyFromError` for error toasts.

---

## Wire contract

`POST /carbon-api/ai/workspace/conversations/{conversation_id}/messages/{message_id}/feedback/`

Request body:

```json
{ "outcome": "accepted", "correction_text": "" }
```

| field | type | required | notes |
|---|---|---|---|
| `outcome` | string enum `accepted`\|`rejected`\|`corrected`\|`ignored` | ✅ | persisted judgement |
| `correction_text` | string | no (default `""`) | required-in-spirit when `outcome="corrected"` (server does not hard-enforce) |

Success response — `200` with the serialized message (same shape as `_serialize_message`,
now including `outcome` and `correction_text`):

```json
{ "id": "...", "conversation_id": "...", "role": "assistant", "content": "...",
  "metadata_json": {}, "outcome": "accepted", "correction_text": "", "created_at": "..." }
```

Errors (all `{"error": "..."}`):
- `400` — invalid `outcome` (serializer) or empty `correction_text` for `outcome="corrected"`
  (worker MUST add a `validate()` on the serializer: if `outcome == "corrected"` and
  `correction_text` is blank → `serializers.ValidationError`).
- `404` — conversation not found / not owned by user, or message not found / not in that
  conversation (`ValueError` → caught as in `send_message`).
- `400` — message `role != "assistant"` (cannot judge a user/system message).

Rules:
- Idempotent: posting the same outcome twice just overwrites (same result).
- Setting `outcome="rejected"` clears any prior `correction_text` (server stores `""`).
- Feedback is **per-message**, owned by the message's conversation's user — no cross-user leak.

---

## Phase 9-A — Backend (Backend Worker)

### Task 9-A1 — model fields + migration

File: `backend/ai/models/workspace.py`

Add to `AIMessage`:

```python
    OUTCOME_CHOICES = [
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
        ("corrected", "Corrected"),
        ("ignored", "Ignored"),
    ]

    outcome = models.CharField(
        max_length=20,
        choices=OUTCOME_CHOICES,
        blank=True,
        null=True,
        default=None,
        help_text="User judgement on this AI message (learning signal).",
    )
    correction_text = models.TextField(
        blank=True,
        default="",
        help_text="User's correction when outcome='corrected'.",
    )
```

Generate the migration (`makemigrations ai`). No data migration needed.

### Task 9-A2 — serialize the new fields

File: `backend/ai/intelligence.py`, `_serialize_message`

Add `outcome` and `correction_text` to the returned dict (after `metadata_json`).

### Task 9-A3 — `record_feedback` on `CarbonIntelligence`

File: `backend/ai/intelligence.py`

Add a method (place near `get_conversation`):

```python
def record_feedback(self, user, conversation_id, message_id, outcome, correction_text=""):
    from ai.models import AIConversation, AIMessage

    try:
        conversation = AIConversation.objects.get(id=conversation_id, user=user)
    except AIConversation.DoesNotExist:
        raise ValueError(f"Conversation {conversation_id} not found.")

    try:
        message = AIMessage.objects.get(id=message_id, conversation=conversation)
    except AIMessage.DoesNotExist:
        raise ValueError(f"Message {message_id} not found.")

    if message.role != "assistant":
        raise ValueError("Only assistant messages can receive feedback.")

    if outcome == "corrected":
        message.correction_text = correction_text
    else:
        message.correction_text = ""

    message.outcome = outcome
    message.save(update_fields=["outcome", "correction_text"])
    return _serialize_message(message)
```

> `outcome` enum validity is guaranteed by the serializer before reaching here; the
> method may still be defensive (`if outcome not in dict(...)` → `ValueError`).

### Task 9-A4 — serializer

File: `backend/ai/serializers.py`

```python
class MessageFeedbackSerializer(serializers.Serializer):
    outcome = serializers.ChoiceField(
        choices=["accepted", "rejected", "corrected", "ignored"],
    )
    correction_text = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        if attrs.get("outcome") == "corrected" and not attrs.get("correction_text", "").strip():
            raise serializers.ValidationError(
                {"correction_text": "A correction is required when outcome is 'corrected'."}
            )
        return attrs
```

### Task 9-A5 — endpoint

File: `backend/ai/workspace_api.py`

```python
@action(detail=True, methods=["post"], url_path="messages/(?P<message_id>[^/.]+)/feedback")
def message_feedback(self, request, pk=None, message_id=None):
    serializer = MessageFeedbackSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    try:
        message = self.intelligence.record_feedback(
            user=request.user,
            conversation_id=pk,
            message_id=message_id,
            outcome=serializer.validated_data["outcome"],
            correction_text=serializer.validated_data.get("correction_text", ""),
        )
        return Response(message)
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)
```

Import `MessageFeedbackSerializer` at the top.

> **DRF routing note:** the `url_path` contains a named group `(?P<message_id>[^/.]+)`
> so the route becomes `/conversations/{pk}/messages/{message_id}/feedback/`. The
> `message_id` kwarg is passed to the method. Verify the URL resolves in tests (below).

### Task 9-A6 — tests

File: `backend/ai/tests/test_message_feedback.py`

Cover (mirror existing `test_chat_stream.py` conventions — `get_token_for_user` conftest fixture):
1. `accepted` → 200, message serialized with `outcome="accepted"`, persisted on reload.
2. `corrected` with `correction_text` → 200, both fields persisted.
3. `corrected` without `correction_text` → 400 (serializer validation).
4. `outcome` invalid value → 400.
5. message not found / wrong conversation → 404.
6. conversation not owned by user → 404 (no cross-user leak).
7. feedback on a `user`-role message → 400/404 error path (assert error envelope).
8. `rejected` clears prior `correction_text`.
9. idempotency: post `accepted` twice → 200 both times, same `outcome`.
10. non-authenticated → 401.
11. `GET .../messages/{id}/` and `GET .../{id}/` still serialize `outcome`/`correction_text`
    (regression: `_serialize_message` output contains the keys, `null`/`""` when unset).

---

## Phase 9-B — Frontend (Frontend Worker)

### Task 9-B1 — API function

File: `carbon-frontend/src/api/aiWorkspace.js`

```js
export function recordFeedback(token, conversationId, messageId, outcome, correctionText = '') {
  return apiFetch(
    `${BASE}conversations/${conversationId}/messages/${messageId}/feedback/`,
    { token, method: 'POST', body: { outcome, correction_text: correctionText } },
  );
}
```

### Task 9-B2 — controls on `AIMessageBubble`

File: `carbon-frontend/src/shell/AIMessageBubble.jsx`

- Only render feedback controls for **assistant** messages (`!isUser`).
- Show a small action row under the content (Accept / Reject / Correct, `size="small"`
  `variant="outlined"`). Reuse the existing `Button` import.
- "Correct" opens a lightweight inline input (a `TextField` + Save/Cancel, or a prompt-based
  `SystemDialog` — match the project's dialog convention; see `src/components/SystemDialog.jsx`).
  On save, call `onCorrect(message, correctionText)`.
- After feedback is persisted, render a status chip (`Accepted`/`Rejected`/`Corrected`) and,
  if `correction_text` is present, show it below the message in a distinct style. Read the
  current state from `message.outcome` / `message.correction_text`.
- Add propTypes: `outcome` (string), `correction_text` (string) on `message`; new callback
  props `onAccept`, `onReject`, `onCorrect`, and an `onFeedbackError` (or reuse the existing
  parent error path — keep it minimal).

Do **not** change the DQ-suggestion accept/reject block.

### Task 9-B3 — wire in `AIConversationView`

File: `carbon-frontend/src/shell/AIConversationView.jsx`

- Add handlers `handleAcceptFeedback(message)`, `handleRejectFeedback(message)`,
  `handleCorrectFeedback(message, correctionText)` that call `recordFeedback(...)`, then
  update the message in local state (set `outcome`/`correction_text`) and `notifyFromError`
  on failure.
- Pass the new props down to each `AIMessageBubble` render.
- Optimistic-update or refresh-from-response: prefer updating from the returned serialized
  message (the endpoint returns the full message).

### Task 9-B4 — tests

- Extend or add a vitest file (e.g. `src/__tests__/AIMessageBubble.feedback.test.jsx`) asserting:
  assistant bubble shows Accept/Reject/Correct; user bubble does NOT; clicking Accept calls the
  callback; a persisted `outcome` renders the status chip. Mock `recordFeedback` and the MUI
  grid import (follow `PulseDataPanel.test.jsx` convention: import `pulseFormat`-style pure
  helpers, or mock the heavy grid — avoid `@mui/x-data-grid` CSS import under vitest `css:false`).

---

## Phase 9-C — Async learning job (follow-on, NOT this sprint)

Deferred: a management command + periodic job that reads `AIMessage` rows with
`outcome in ("accepted","corrected")` and feeds them into the engine's KG weights +
long-term memory (`ai/engine/memory/…`, `ai/engine/knowledge_graph/…`). Spec as
`tasks/SPRINT-10-LEARNING.md` when Phase 9-A/B are verified.

---

## Verification gates

Backend (run from `cd /home/ahmed/aast/carbon/backend`):

```bash
/home/ahmed/aast/carbon/.venv/bin/python manage.py check
/home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai dq accounts -q
```

- All existing tests stay green (baseline **786** + new feedback tests).
- `makemigrations --check` reports no drift after the migration is committed.

Frontend (run from `cd /home/ahmed/aast/carbon/carbon-frontend`):

```bash
npm run lint      # 0 errors (53 pre-existing warnings unchanged)
npm test          # 336 + new feedback tests
npm run build     # success
```

---

## Critical hazards

1. **Do not confuse message feedback with DQ suggestion accept/reject.** Sprint 9 only adds
   `outcome`/`correction_text` on `AIMessage` + its endpoint + bubble controls.
2. **Ownership check is mandatory.** `record_feedback` must scope the message lookup through
   the user's own conversation (`AIConversation.objects.get(id=…, user=user)` then
   `AIMessage.objects.get(id=…, conversation=conversation)`). Never `AIMessage.objects.get(id=…)`
   alone — that leaks across users.
3. **Migration ordering.** Let `makemigrations` assign the filename (next after `0004`).
   Do not hand-number and risk a collision.
4. **`url_path` regex group** must be `(?P<message_id>[^/.]+)` exactly; test the URL resolves
   via the DRF test client (the feedback endpoint should be reachable at
   `/carbon-api/ai/workspace/conversations/{cid}/messages/{mid}/feedback/`).
5. **`_serialize_message` is shared** by `send_message`, `send_message_stream` (`done` frame),
   and `get_conversation`. Adding `outcome`/`correction_text` there must remain backward
   compatible (values are `null`/`""` for pre-feedback messages) — verify the stream `done`
   frame and `get_conversation` still work.
