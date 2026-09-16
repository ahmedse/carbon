# SPRINT-6-WORKSPACE-CONTEXT.md
# Master Architect — Phase Spec
# Date: 2026-08-15
# Status: READY FOR WORKERS
# Depends on: Sprint 2 (COMPLETE), Sprint 3 AI Workspace Phase 2 (COMPLETE)

---

## Summary

Make the AI Workspace **context-aware**. When a user clicks `[AI]` from any
workspace (DQ, Catalog, DataSchema, Emissions), the frontend serializes *what the
user is doing* into a structured `WorkspaceContext` object and sends it when
opening the AI tab. The backend stores it on the conversation and injects it into
the system prompt so the AI opens already knowing the user's context — no
screenshots, no scraping.

This is DQ+AI target scenario **step 2**: *"AI opens already knowing your context."*

---

## Architecture — what Sprint 6 adds

```
Main Workspace                         AI Workspace
──────────────                        ──────────────
DQ Rules page                          Conversation #42
  user is viewing table X        ──→    system prompt prefix:
  intent = "create rule"                "User is in DQ workspace, viewing
  [Ask AI] click                        table X (emissions_fuel), intent:
                                        create. Recent actions: …"
```

The `WorkspaceContext` is a plain JSON object — the same shape the roadmap
defines for Phase 6-B. It is **optional**: existing conversations (created
without it) keep working exactly as they do today.

---

## PHASE 6-A: Backend — Protocol + storage + prompt injection

**Role:** Backend Worker
**Model:** DeepSeek-V3
**Domain:** backend/ai/

### PRE-FLIGHT (read before writing)

| File | Why |
|------|-----|
| `backend/ai/protocol.py` | Add `WorkspaceContext` dataclass next to `ConversationContext` (§10) |
| `backend/ai/serializers.py` | `CreateConversationSerializer` — add `workspace_context` field |
| `backend/ai/intelligence.py` | `create_conversation()` (line ~215) + `_send_chat_message()` (line ~732) |
| `backend/ai/models/workspace.py` | `AIConversation` — confirm `task_payload_json` exists (it does) |
| `.ai-toolkit/shared/ai-contract.md` | §11 Workspace Context (canonical shape) |
| `ARCHITECTURE.md §AI` | WorkspaceContext design intent |

### TASKS

#### TASK 1: Add `WorkspaceContext` dataclass to `protocol.py`

Add near `ConversationContext` (after §10 block):

```python
# ── Workspace Context (§11 user situation) ────────────────────────────

@dataclass
class WorkspaceContext:
    """Structured description of what the user is currently doing.

    Sent by the frontend when opening the AI workspace tab.
    Never inferred — always explicitly serialized by the source workspace.
    """

    workspace: str                      # "dq" | "catalog" | "emissions" | "dataschema" | ...
    current_view: str                   # page or tab name, e.g. "rule_list", "table_detail"
    entity_type: str | None = None      # "table" | "rule" | "calculation" | "asset" | ...
    entity_id: str | None = None        # PK or slug of the focused entity
    entity_name: str | None = None      # human-readable name
    form_state: dict | None = None      # partial form data if user was filling a form (SANITIZED — §11.5)
    recent_actions: list[str] = field(default_factory=list)  # last 3-5 user actions
    intent_signal: str | None = None    # "create" | "edit" | "debug" | "explore" | None
    app_identifier: str | None = None   # domain app scope (mirrors Scope.app_identifier)

    def to_prompt_prefix(self) -> str:
        """Render a compact system-prompt prefix describing the user's situation."""
        if not self.workspace:
            return ""
        parts = [f"User is in the {self.workspace} workspace"]
        if self.current_view:
            parts.append(f"viewing {self.current_view}")
        if self.entity_type and self.entity_name:
            parts.append(f"on {self.entity_type} '{self.entity_name}'")
        elif self.entity_type:
            parts.append(f"on a {self.entity_type}")
        if self.intent_signal:
            parts.append(f"with intent '{self.intent_signal}'")
        if self.recent_actions:
            parts.append(f"recent actions: {', '.join(self.recent_actions[:3])}")
        return ". ".join(parts) + "."

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "WorkspaceContext | None":
        if not data or not isinstance(data, dict) or not data.get("workspace"):
            return None
        known = {
            "workspace", "current_view", "entity_type", "entity_id",
            "entity_name", "form_state", "recent_actions",
            "intent_signal", "app_identifier",
        }
        return cls(**{k: v for k, v in data.items() if k in known})
```

Note: `form_state` MUST be sanitized by the frontend before sending (§11.5) —
no passwords or secrets. `WorkspaceContext` is NEVER used for security decisions
(§11.4) — that is Scope's job.

**Verify:**
```bash
cd backend && /home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests/test_protocol.py -q
```

#### TASK 2: Accept `workspace_context` on `CreateConversationSerializer`

**MODIFY** `backend/ai/serializers.py` — add one field:

```python
workspace_context = serializers.JSONField(required=False, default=None)
```

#### TASK 3: Store `workspace_context` in `create_conversation()`

**MODIFY** `backend/ai/intelligence.py`:

1. Add `workspace_context: dict[str, Any] | None = None` parameter to
   `create_conversation()`.
2. Merge it into the stored payload:
   ```python
   task_payload = dict(task_payload or {})
   if workspace_context:
       task_payload["workspace_context"] = workspace_context
   ```
3. Pass `workspace_context` through from the view (see TASK 4).

#### TASK 4: Thread the field through the view

**MODIFY** `backend/ai/workspace_api.py` — `WorkspaceConversationViewSet.create()`
is the only consumer of `CreateConversationSerializer`. Pass
`serializer.validated_data.get("workspace_context")` into
`create_conversation()`.

#### TASK 5: Inject workspace context into the chat system prompt

**MODIFY** `_send_chat_message()` in `backend/ai/intelligence.py`:

1. Read `WorkspaceContext.from_dict(conversation.task_payload_json.get("workspace_context"))`.
2. If present, prepend its `to_prompt_prefix()` to the chat message content
   (or set it as a leading system message in `ChatRequest` if the provider
   supports a `system` field — follow the existing `ChatRequest` shape; do NOT
   change the provider ABC).
3. Guard: never fail the conversation if the context is malformed — treat
   `from_dict()` returning `None` as "no context" and proceed normally.

**Rules for ALL:**
- `WorkspaceContext` is optional and additive. Zero behavior change for
  conversations created without it.
- No new DB fields — `task_payload_json` already persists arbitrary JSON.
- No change to `guards.py`, `providers/pulse.py`, or `engine_runtime.py`.

### DO NOT TOUCH

- `backend/ai/guards.py`
- `backend/ai/providers/pulse.py` (provider ABC unchanged)
- `backend/ai/engine_runtime.py` / `engine/` — out of scope
- Any frontend files

### GATES

```bash
cd backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py check
cd backend && /home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests -q
cd backend && /home/ahmed/aast/carbon/.venv/bin/python -m pytest ai dq accounts -q
```

---

## PHASE 6-B: Frontend — Emit `WorkspaceContext` from each workspace

**Role:** Frontend Worker
**Model:** DeepSeek-V3
**Domain:** carbon-frontend/src/
**Depends on:** Phase 6-A complete

### PRE-FLIGHT (read before writing)

| File | Why |
|------|-----|
| `src/shell/AITaskTransferContext.jsx` | `transferTask()` + `enrichPayload()` — the single choke point |
| `src/shell/useAITaskTransfer.js` | hook consumed by every workspace page |
| `src/api/aiWorkspace.js` | `createConversation()` — add `workspace_context` to the payload |
| `src/pages/dq/DQWorkspacePage.jsx` | DQ workspace — the primary emitter |
| `src/pages/dq/RuleDetailPage.jsx` | DQ rule detail — secondary emitter |
| `src/pages/catalog/SchemaDetailPage.jsx` | Catalog/DataSchema — emitter |
| `src/pages/emissions/*` | Emissions workspace — emitter (one or two key pages) |

### TASKS

#### TASK 6: Add `workspace_context` to `createConversation` API wrapper

**MODIFY** `src/api/aiWorkspace.js` — extend the create payload to include an
optional `workspace_context` field (send only when non-null).

#### TASK 7: Add a `workspaceContext` param to `transferTask()`

**MODIFY** `src/shell/AITaskTransferContext.jsx`:

1. `transferTask(type, payload, metadata = {})` — read
   `metadata.workspaceContext` and pass it through to `createConversation`.
2. Do **not** build the context inside the provider — the *caller* (each
   workspace page) builds it. The provider just forwards it.
3. Keep `enrichPayload()` unchanged.

#### TASK 8: Emit context from the DQ workspace

**MODIFY** `src/pages/dq/DQWorkspacePage.jsx`:

Build a `workspaceContext` object wherever the user opens AI (the "Ask AI about
DQ health", "Suggest rules with AI", and "Analyze anomalies" buttons):

```js
const workspaceContext = {
  workspace: 'dq',
  current_view: activeTab,        // 'overview' | 'rules' | 'jobs' | 'suggestions' | 'monitoring'
  entity_type: selectedTable ? 'table' : 'workspace',
  entity_id: selectedTable?.id ?? null,
  entity_name: selectedTable?.table_name ?? null,
  intent_signal: 'explore',
  recent_actions: [],             // optional — see TASK 11
};
```

Pass it via `transferTask(type, payload, { workspaceContext, ... })`.

**MODIFY** `src/pages/dq/RuleDetailPage.jsx`:

```js
const workspaceContext = {
  workspace: 'dq',
  current_view: 'rule_detail',
  entity_type: 'rule',
  entity_id: rule?.id ?? null,
  entity_name: rule?.name ?? null,
  intent_signal: 'debug',         // viewing a specific rule (its results/failures)
};
```

#### TASK 9: Emit context from Catalog / DataSchema

**MODIFY** `src/pages/catalog/SchemaDetailPage.jsx` (or the table-detail page
that hosts the AI trigger): emit
`{ workspace: 'catalog', current_view: 'table_detail', entity_type: 'table',
entity_id: table?.id, entity_name: table?.name, intent_signal: 'explore' }`.

#### TASK 10: Emit context from Emissions

Pick the primary Emissions workspace page (e.g. the dashboard or a data-entry
page with an AI trigger) and emit
`{ workspace: 'emissions', current_view: <view>, entity_type: <type>,
entity_id: <id>, entity_name: <name>, intent_signal: 'explore' }`.

#### TASK 11 (stretch, if time): recent_actions

If a workspace already tracks a lightweight `recentActions` array, slice the last
3 into `recent_actions`. Otherwise leave `[]` — do NOT introduce new state
tracking to satisfy this.

**Rules:**
- Every emission is best-effort: if the context can't be built (no selection),
  omit it entirely — never throw.
- Use theme tokens only; no new raw hex/px.
- `apiFetch` only (via existing wrappers).

### GATES

```bash
cd carbon-frontend && npm run build
cd carbon-frontend && npm run lint
cd carbon-frontend && npm test
```

---

## PHASE 6-C: Backend — intent-aware openers (2 days)

**Role:** Backend Worker
**Model:** DeepSeek-V3
**Domain:** backend/ai/
**Depends on:** Phase 6-A + 6-B complete

### TASKS

#### TASK 12: Intent-aware first assistant message

**MODIFY** `backend/ai/intelligence.py` — when a conversation is created with a
`WorkspaceContext` whose `intent_signal` is set, seed an initial assistant
message (or adjust the chat prompt) so the AI opens with a context-aware opener:

- `intent_signal="create"` + `entity_type="rule"` →
  *"I see you want to create a new DQ rule. Based on table X's profile, I'd
  suggest…"*
- `intent_signal="debug"` → open with the failure context pre-loaded.
- `intent_signal="explore"` / `"edit"` → a neutral context-aware opener
  referencing the entity name.

Follow the existing assistant-message creation path; reuse
`_serialize_conversation`/`_build_ai_message` helpers. Do not duplicate logic.

#### TASK 13: Tests

**CREATE** `backend/ai/tests/test_workspace_context.py` (≥ 8 cases):

1. `WorkspaceContext.from_dict(None)` → `None`
2. `WorkspaceContext.from_dict({})` → `None` (no workspace key)
3. `WorkspaceContext.from_dict(valid)` → populated fields
4. `to_prompt_prefix()` includes entity name and intent
5. `create_conversation` with `workspace_context` persists it in `task_payload_json`
6. `create_conversation` without it → `task_payload_json` has no `workspace_context`
7. `_send_chat_message` prepends context prefix when present
8. `_send_chat_message` does not prepend when absent
9. Intent-aware opener emitted for `intent_signal="create"` + `entity_type="rule"`
10. Malformed context (wrong type) → conversation still succeeds (no crash)

**Verify:**
```bash
cd backend && /home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests/test_workspace_context.py -q
```

---

## PHASE ORDER

```
6-A (Backend protocol+storage) ──→ 6-B (Frontend emitters)
                                        │
6-A also unblocks 6-C                  ▼
6-C (Backend intent-aware openers) ←── after 6-B
```

6-B CANNOT start until 6-A's serializer accepts `workspace_context`.
6-C CANNOT start until 6-A is in and 6-B emits real context.

---

## DO NOT TOUCH (whole sprint)

- `backend/ai/guards.py`, `backend/ai/providers/pulse.py`, `backend/ai/engine_runtime.py`, `backend/ai/engine/**`
- `src/shell/Shell.jsx`, `src/shell/useShellState.js`, `src/theme/carbonTheme.js`
- `backend/ai/models/workspace.py` schema (no new DB fields this sprint)

## ACCEPTANCE

- [ ] `WorkspaceContext` dataclass exists in `protocol.py` with `from_dict` + `to_prompt_prefix`
- [ ] `CreateConversationSerializer` accepts optional `workspace_context`
- [ ] `create_conversation` persists it under `task_payload_json.workspace_context`
- [ ] `_send_chat_message` prepends the context prefix when present, ignores when absent
- [ ] DQ, Catalog, DataSchema, Emissions all emit `workspace_context` on AI open
- [ ] Intent-aware opener for `create`+`rule`
- [ ] 10 backend tests pass; full `pytest ai dq accounts` green; `npm run build` green
