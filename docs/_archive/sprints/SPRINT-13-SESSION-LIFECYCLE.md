# Sprint 13 — Session Lifecycle Persistence + Message Pagination

**Owner:** Master Architect · **Status:** 🚀 Ready for Backend Worker dispatch
**Design:** `docs/DESIGN_AI_WORKSPACE_NEXTGEN.md` §4–5 (Phase 0 + Phase 1 backend)
**Contract:** `.ai-toolkit/shared/ai-contract.md` (v2.0.0)

## Goal
Make AI conversations **durably manageable**: rename, archive, pin, delete, search,
filter, and message cursor pagination. Today close-tab is client-side only and
`get_conversation` loads ALL messages.

## Current state (verified facts — do not re-discover)

- `backend/ai/models/workspace.py` — `AIConversation` + `AIMessage` (2 models, exact fields
  as read). `AIConversation` has: id, user, title, app_identifier, conversation_type,
  status, scope_json, task_payload_json, created_at, updated_at. `AIMessage` has: id,
  conversation, role, content, metadata_json, created_at, outcome, correction_text, learned_at.
- `backend/ai/serializers.py` — `CreateConversationSerializer`, `SendMessageSerializer`,
  `ConversationListSerializer` (status/limit only), `MessageFeedbackSerializer`.
- `backend/ai/workspace_api.py` — `WorkspaceConversationViewSet` (list/create/retrieve/
  send_message/message_feedback/send_message_stream). No update/delete/messages-list.
- `backend/ai/intelligence.py` — `create_conversation`, `send_message`, `send_message_stream`,
  `get_conversation`, `record_feedback`, `list_conversations`, `_serialize_conversation`,
  `_serialize_message`, `_default_title`. `_serialize_conversation` returns the dict shape
  the API returns; `_serialize_message` returns the message dict shape.
- `backend/ai/workspace_urls.py` — DefaultRouter on `conversations`.

## Tasks

### 1. Extend models (migration)
MODIFY `backend/ai/models/workspace.py`:
- `AIConversation` add:
  - `is_archived = models.BooleanField(default=False)`
  - `is_pinned = models.BooleanField(default=False)`
  - `summary = models.TextField(blank=True, default="")` (rolling compaction — written in Sprint 15, just the field here)
  - `last_message_at = models.DateTimeField(null=True, blank=True, default=None)`
  - `visibility = models.CharField(max_length=20, default="private", choices=[("private","Private"),("shared","Shared")])`
  - `context_snapshot_json = models.JSONField(blank=True, default=dict)`
  - Add `indexes` to `Meta`: `models.Index(fields=["user","is_archived","is_pinned","-last_message_at"], name="ai_conv_user_org_idx")` and `models.Index(fields=["user","app_identifier"], name="ai_conv_user_app_idx")`.
- `AIMessage` add:
  - `token_usage_json = models.JSONField(blank=True, default=dict)`
  - `parent_message_id = models.UUIDField(null=True, blank=True, default=None)`
  - `status = models.CharField(max_length=20, default="completed", choices=[("completed","Completed"),("partial","Partial"),("stopped","Stopped"),("failed","Failed")])`
  - `provider_model = models.CharField(max_length=64, blank=True, default="")`
  - Add `Meta.indexes`: `models.Index(fields=["conversation","created_at"], name="ai_msg_conv_time_idx")`.
- Keep everything else unchanged. Never touch the engine tables.
- Run `makemigrations ai` to generate ONE migration.

### 2. New `AIGeneration` model (durable cancellation lease)
MODIFY `backend/ai/models/workspace.py` — add `AIGeneration` model:
```python
class AIGeneration(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(AIConversation, on_delete=models.CASCADE, related_name="generations")
    token = models.CharField(max_length=64, blank=True, default="")
    started_at = models.DateTimeField(auto_now_add=True)
    cancelled_at = models.DateTimeField(null=True, blank=True, default=None)
    status = models.CharField(max_length=20, default="running", choices=[("running","Running"),("cancelled","Cancelled"),("completed","Completed"),("failed","Failed")])
    class Meta:
        app_label = "ai"
```
(Only the model + migration this sprint. Registry/stop logic is Sprint 14.)

### 3. Serializers
MODIFY `backend/ai/serializers.py`:
- Extend `ConversationListSerializer`: add `q` (CharField, required=False), `is_archived`
  (BooleanField, required=False), `is_pinned` (BooleanField, required=False),
  `conversation_type` (ChoiceField same list, required=False), `cursor` (CharField, required=False).
- New `ConversationUpdateSerializer`: `title` (CharField required=False max_length=255),
  `is_pinned` (BooleanField required=False), `is_archived` (BooleanField required=False),
  `visibility` (ChoiceField ["private","shared"] required=False). Validate at least one field present.
- New `MessageListSerializer`: `limit` (IntegerField default 50 max 200 min 1),
  `before` (CharField required=False — message id cursor), `after` (CharField required=False).

### 4. Intelligence methods
MODIFY `backend/ai/intelligence.py`:
- `update_conversation(self, user, conversation_id, **fields)` — loads own conversation,
  applies only the provided fields (title/is_pinned/is_archived/visibility), saves
  `update_fields`, returns `_serialize_conversation`. `ValueError` if not found.
- `delete_conversation(self, user, conversation_id)` — load own conversation, delete,
  return `{"deleted": conversation_id}`. `ValueError` if not found.
- `list_messages(self, user, conversation_id, limit=50, before=None, after=None)` —
  load own conversation; qs = `conversation.messages.order_by("created_at")`; if `before`
  is set, filter `id` < the message with that id's created_at (resolve `before` id to a
  message, else `ValueError`); if `after` set, filter `created_at` > that message's
  created_at. Return `{"messages": [...], "has_more": bool}` where `has_more` is True when
  there are older messages before the returned window (for `before` pagination). Serialize
  with `_serialize_message`.
- `list_conversations` — add params `query=None, is_archived=None, is_pinned=None, conversation_type=None`.
  Filter: exclude archived by default (only include archived when `is_archived=True` is
  explicitly passed); `is_pinned` filter; `conversation_type` filter; `query` does
  `Q(title__icontains=query)` (icontains). Keep `-updated_at` ordering + limit.
- Auto-title: in `create_conversation`, after the conversation is created, if `title` is
  empty AND the first user message arrives in `send_message`, set the title to the first
  40 chars of the first user message (when `conversation.title` is still a default title
  from `_default_title`). Implement a small helper `_maybe_autotitle(conversation, content)`.
- Update `_serialize_conversation` to include the new fields: `is_archived`, `is_pinned`,
  `summary`, `last_message_at` (isoformat or None), `visibility`, `context_snapshot_json`.
- Update `_serialize_message` to include `token_usage_json`, `parent_message_id` (str or
  None), `status`, `provider_model`.

### 5. API endpoints
MODIFY `backend/ai/workspace_api.py`:
- `partial_update(self, request, pk=None)` → `ConversationUpdateSerializer` → `intelligence.update_conversation`. 404 on ValueError.
- `destroy(self, request, pk=None)` → `intelligence.delete_conversation`. 404 on ValueError.
- `@action(detail=True, methods=["get"], url_path="messages")` `list_messages` → `MessageListSerializer` (query params) → `intelligence.list_messages`.
- `list` — pass new filters through to `intelligence.list_conversations`.
- Import the new serializers.

### 6. Tests (REQUIRED — regression coverage)
CREATE `backend/ai/tests/test_workspace_lifecycle.py`:
- rename conversation persists (update → re-fetch)
- archive excludes from default list, appears with `is_archived=true`
- pin/unpin round-trips
- delete removes + subsequent get 404 (assert `ValueError`)
- message pagination: create 5 messages, `limit=2 before=<3rd id>` returns 2 + has_more True
- auto-title sets first 40 chars on first user message
- cross-user: user B cannot update/delete user A's conversation (assert ValueError/404)

## DO NOT TOUCH
- `backend/ai/engine/**` (stateless engine)
- `backend/ai/providers/pulse.py`
- `carbon-frontend/**` (frontend is Sprint 16)
- any file outside `backend/ai/models/workspace.py`, `backend/ai/serializers.py`,
  `backend/ai/workspace_api.py`, `backend/ai/intelligence.py`, `backend/ai/tests/`, and the migration.

## GATES (run ALL, paste output)
```bash
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python -m pytest ai -q
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py check
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run
./.ai-toolkit/scripts/verify.sh backend
./.ai-toolkit/scripts/verify.sh antipatterns
```

## HARD RULES
- Use `django.utils.timezone.now()` — never `datetime.now()`.
- All new business logic in `intelligence.py` methods (viewset stays thin).
- API prefix `/carbon-api/` is handled by config/urls.py — do not add a prefix.
- Never import from `emissions`.
- `ValueError` on not-found (matches existing pattern) — viewset maps to 404.

## REPORT BACK
Task-by-task ✅/❌, test count, exact terminal output from every gate, deviations.
