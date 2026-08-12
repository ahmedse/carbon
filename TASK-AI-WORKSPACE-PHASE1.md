# TASK-AI-WORKSPACE-PHASE1.md
# Master Architect — Phase Spec
# Date: 2026-08-12
# Status: READY FOR WORKERS

---

## Summary

Evolve the Pulse AI pane from a passive external-widget container into an **AI Workspace** — a peer workspace that runs alongside the main workspace. The AI workspace receives task transfers (chat, DQ validate), supports tabbed multi-turn conversations, and persists across sessions.

**Two phases, two workers: Backend Worker first, then Frontend Worker.**

---

## Architecture Reference

```
Main Workspace (existing pages)          AI Workspace (new React app)
─────────────────────────────────       ─────────────────────────────
DQ Rule Detail                              ┌─ Tab: "DQ Check #42" ───┐
┌──────────────────────────┐               │ 🤖 12 rows failed...    │
│ [Validate with AI] ──────┼──transfer──→  │ 👤 Show by org unit     │
└──────────────────────────┘               │ 🤖 Grouped results:     │
                                           └─────────────────────────┘
Dashboard                                  ┌─ Tab: "Chat" ───────────┐
┌──────────────────────────┐               │ 🤖 How can I help?      │
│ [Ask AI] ────────────────┼──transfer──→  │ 👤 Explain scope 3...   │
└──────────────────────────┘               └─────────────────────────┘
                  │                                    │
                  └────────────┬───────────────────────┘
                               ▼
                     ┌──────────────────┐
                     │  Carbon Backend   │
                     │  /carbon-api/ai/  │
                     │  workspace/       │
                     │  (NEW)            │
                     └────────┬─────────┘
                              ▼
                     ┌──────────────────┐
                     │  CarbonIntelligence│
                     │  + guards          │
                     └────────┬─────────┘
                              ▼
                     ┌──────────────────┐
                     │  Pulse (external) │
                     └──────────────────┘
```

### Key Design Decisions (confirmed)

| D# | Decision |
|----|----------|
| D1 | AI Workspace is a React app inside Carbon (not iframe). Pulse provides AI brain; Carbon provides UI. |
| D2 | All AI communication through Carbon backend → AI Heart → Pulse. Never direct from frontend. |
| D3 | Conversations persisted in DB (`AIConversation` + `AIMessage` models). |
| D4 | Task transfer via React Context (`AITaskTransferContext`). |
| D5 | Tabbed conversations — multiple tasks coexist, user switches between them. |
| D6 | AI can request user input (`needs_input` conversation state). |

### Conversation State Machine

```
pending → working → needs_input → working → completed
                 ↘                          ↗
                   failed ─────────────────┘
```

---

## PHASE 1-A: Backend — AI Conversation Models + Workspace API

**Role:** Backend Worker
**Model:** DeepSeek-V3
**Domain:** backend/ai/

### PRE-FLIGHT (read before writing)

| File | Why |
|------|-----|
| `backend/ai/protocol.py` | Current ABCs — you'll add ConversationContext |
| `backend/ai/intelligence.py` | CarbonIntelligence entry point — you'll add workspace methods |
| `backend/ai/guards.py` | 5 guards — workspace calls go through same chain |
| `backend/ai/providers/pulse.py` | Pulse provider — you'll add conversation_history to task payload |
| `backend/ai/providers/_http.py` | HTTP transport — may need timeout adjustments |
| `backend/ai/domain_protocol.py` | Domain ABC — not changed, but read for context |
| `backend/config/settings.py` | Django settings — may need new AI settings |
| `backend/config/urls.py` | URL routing — you'll add workspace API routes |
| `.ai-toolkit/shared/ai-contract.md` | THE contract — every rule still applies |

### TASKS

#### TASK 1: Create AIConversation and AIMessage models

**CREATE** `backend/ai/models.py`

```python
# Models:
# - AIConversation: id (UUID), user (FK→User), title, app_identifier (nullable),
#   conversation_type (choices: chat|dq_validate|dq_suggest|nl_query),
#   status (choices: pending|working|needs_input|completed|failed),
#   scope_json (JSON — frozen copy of Scope at creation time),
#   task_payload_json (JSON — the original task payload),
#   created_at, updated_at
#
# - AIMessage: id (UUID), conversation (FK→AIConversation), role (choices: user|assistant|system),
#   content (Text), metadata_json (JSON — optional: confidence, suggestions, follow_up_questions),
#   created_at
```

**Rules:**
- `AIConversation` ordered by `-updated_at` (most recent first)
- `AIMessage` ordered by `created_at` within conversation
- `scope_json` stores a frozen Scope (user's org units at conversation creation time). Re-evaluated on each message.
- `task_payload_json` stores the original task context (rule_id, table_name, rows, etc.)
- Use `django.utils.timezone.now()` for all timestamps
- Add to Django admin

**Verify:**
```bash
./manage.sh manage makemigrations ai --check --dry-run  # should show new models
./manage.sh test backend.ai.tests
```

---

#### TASK 2: Add ConversationContext to protocol.py

**MODIFY** `backend/ai/protocol.py` — add at end of file (after existing dataclasses):

```python
@dataclass
class ConversationContext:
    """Multi-turn conversation history carried to every AI call.
    
    AI CONTRACT §10: Provider receives full conversation history
    in every request. Carbon owns conversation state; provider is stateless.
    """
    conversation_id: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    # Each message: {"role": "user"|"assistant"|"system", "content": "...", "timestamp": "..."}
```

**Also modify** `DqValidateRequest` — add optional field:
```python
conversation: ConversationContext | None = None
```

**Rules:**
- `ConversationContext` is protocol-only (dataclass). It does NOT import Django models.
- The `messages` list carries the full conversation history on every turn.
- Provider uses this for context; Carbon owns the canonical state.

**Verify:**
```bash
./manage.sh test backend.ai.tests.test_protocol
```

---

#### TASK 3: Extend CarbonIntelligence with workspace methods

**MODIFY** `backend/ai/intelligence.py` — add these methods to `CarbonIntelligence`:

```python
def create_conversation(
    self,
    user,
    conversation_type: str,  # "chat" | "dq_validate"
    title: str = "",
    app_identifier: str | None = None,
    task_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a new conversation. Returns serialized AIConversation."""
    ...

def send_message(
    self,
    user,
    conversation_id: str,
    content: str,
) -> dict[str, Any]:
    """Send user message → AI responds. Returns updated conversation + new messages."""
    ...

def get_conversation(
    self,
    user,
    conversation_id: str,
) -> dict[str, Any]:
    """Get a conversation with all messages."""
    ...

def list_conversations(
    self,
    user,
    status: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """List user's conversations, most recent first."""
    ...
```

**Rules:**
- `send_message()` must:
  1. Load conversation + messages from DB
  2. Build `ConversationContext` from message history
  3. Build fresh `Scope` from user (NOT from frozen scope_json — user's permissions may have changed)
  4. If `conversation_type == "dq_validate"`, call `provider.validate_dq()` with ConversationContext
  5. If `conversation_type == "chat"`, use a new generic chat path (or call `provider.validate_dq()` with an empty rules list and a chat prompt)
  6. Save both user message and AI response to DB
  7. Detect `needs_input` — if AI response contains follow-up questions, set conversation status to `needs_input`
  8. Run ALL 5 guards before calling provider
  9. Return serialized conversation + new messages
- `create_conversation()` stores a frozen scope_json for audit
- `list_conversations()` is scoped to the requesting user only

**For `chat` type:** When conversation_type is "chat", the `send_message` method should call a new provider method. You have two options:
1. Add a `chat()` method to `AIProvider` ABC in protocol.py
2. Reuse existing infrastructure with a chat-specific prompt

**Recommended approach:** Add a minimal chat path. Create a `ChatRequest`/`ChatResponse` dataclass in protocol.py and a `chat()` abstract method on `AIProvider`. Pulse provider implements it by posting to the same `/tasks` endpoint with type `chat`.

**Verify:**
```bash
./manage.sh test backend.ai.tests.test_intelligence
```

---

#### TASK 4: Add workspace REST API endpoints

**CREATE** `backend/ai/workspace_api.py`

```python
# DRF ViewSet or APIView:
# POST   /carbon-api/ai/workspace/conversations/           → create_conversation
# GET    /carbon-api/ai/workspace/conversations/           → list_conversations
# GET    /carbon-api/ai/workspace/conversations/{id}/      → get_conversation
# POST   /carbon-api/ai/workspace/conversations/{id}/messages/  → send_message
```

**MODIFY** `backend/config/urls.py` — register workspace routes under `carbon-api/ai/workspace/`

**Rules:**
- Use `apiFetch`-compatible responses (consistent with rest of Carbon API)
- Authentication: JWT required
- Permission: authenticated user, scoped to own conversations
- Request/response serializers in `backend/ai/serializers.py` (new file)
- Follow existing DRF patterns in the project (ViewSet with `@action` for custom routes, or APIView)

**Verify:**
```bash
./manage.sh test backend.ai.tests.test_workspace_api
# Manual curl test:
curl -X POST http://localhost:8009/carbon-api/ai/workspace/conversations/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"conversation_type": "chat", "title": "Test"}'
```

---

#### TASK 5: Extend Pulse provider for multi-turn conversations

**MODIFY** `backend/ai/providers/pulse.py`

- In `validate_dq()`: if `request.conversation` is not None, include `conversation_history` in the task payload
- Add `chat()` method: sends task type `chat` to Pulse with conversation history
- Conversation history format in payload:
  ```json
  {
    "conversation_id": "uuid",
    "messages": [
      {"role": "user", "content": "Check emissions_fuel for nulls", "timestamp": "..."},
      {"role": "assistant", "content": "I found 12 null values...", "timestamp": "..."}
    ]
  }
  ```

**MODIFY** `backend/ai/protocol.py` — add ChatRequest/ChatResponse + chat() to AIProvider ABC:

```python
@dataclass
class ChatRequest:
    message: str
    conversation: ConversationContext | None = None
    scope: Scope | None = None

@dataclass
class ChatResponse:
    status: str  # "completed" | "provider_unavailable" | "failed"
    content: str | None = None
    follow_up_questions: list[str] = field(default_factory=list)
    error: dict[str, str] | None = None
    execution_ms: int = 0

# In AIProvider ABC:
@abstractmethod
def chat(self, request: ChatRequest) -> ChatResponse: ...
```

**Rules:**
- Pulse provider's `chat()` posts to same HTTP endpoint with task type `chat`
- Timeout: 15s for chat (sync)
- `follow_up_questions` in response → Carbon sets conversation to `needs_input`
- Provider unavailable → return `ChatResponse(status="provider_unavailable")`

**Verify:**
```bash
./manage.sh test backend.ai.tests.test_provider_pulse
```

---

#### TASK 6: Register models in Django admin

**MODIFY** `backend/ai/admin.py` (create if not exists):

```python
from django.contrib import admin
from .models import AIConversation, AIMessage

@admin.register(AIConversation)
class AIConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'conversation_type', 'status', 'title', 'created_at')
    list_filter = ('conversation_type', 'status')
    search_fields = ('title', 'user__username')
    readonly_fields = ('id', 'created_at', 'updated_at', 'scope_json')

@admin.register(AIMessage)
class AIMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'role', 'created_at')
    list_filter = ('role',)
    readonly_fields = ('id', 'created_at')
```

**Verify:**
```bash
./manage.sh manage check  # no errors
```

---

### DO NOT TOUCH (Phase 1-A)

- `backend/ai/guards.py` — guards unchanged (they already work for all AIProvider calls)
- `backend/ai/domain_protocol.py` — domain ABCs unchanged
- `backend/ai/domain/` — domain implementations unchanged
- `backend/dq/` — DQ services unchanged (they already call CarbonIntelligence)
- `backend/emissions/` — emissions app unchanged
- Any frontend files

### HARD RULES (from project.config.md)

- RULE_3: `ai/` MUST NOT import from `emissions/`
- RULE_6: Do NOT add pgvector, LLM gateway, or AI copilot features in-repo
- RULE_13: Carbon NEVER imports Pulse SDKs
- RULE_18: AI CONTRACT IS BINDING — every call through CarbonIntelligence, scope mandatory
- Use `django.utils.timezone.now()` — NEVER `datetime.now()`

### GATES (run ALL before reporting)

```bash
# 1. Migrations check
./manage.sh manage makemigrations ai --check --dry-run

# 2. All existing AI tests still pass
./manage.sh test backend.ai.tests --keepdb

# 3. All backend tests still pass
./manage.sh test --keepdb

# 4. Django check
./manage.sh manage check

# 5. Anti-pattern scan
./.ai-toolkit/scripts/verify.sh backend
```

---

## PHASE 1-B: Frontend — AI Workspace UI

**Role:** Frontend Worker
**Model:** DeepSeek-V3
**Domain:** carbon-frontend/src/

**PREREQUISITE:** Phase 1-A must be complete (backend API available).

### PRE-FLIGHT (read before writing)

| File | Why |
|------|-----|
| `src/shell/Shell.jsx` | You'll modify the copilot pane area |
| `src/shell/PulsePane.jsx` | Current pane — you'll replace it |
| `src/shell/useShellState.js` | Shell state — copilotVisible, toggleCopilot |
| `src/shell/StatusBar.jsx` | Status bar — copilot button |
| `src/api/api.js` | apiFetch — all AI calls go through this |
| `src/api/dq.js` | DQ API functions — you'll add AI workspace API functions |
| `src/theme/carbonTheme.js` | Theme tokens — AI workspace must use theme, never raw hex |
| `src/components/layout/PageContainer.jsx` | Design primitives |
| `src/auth/pulseAuth.js` | Pulse auth — keep as-is (pulse_key provisioning) |
| `src/apps/registry.js` | App registry |
| `src/shell/Breadcrumbs.jsx` | Breadcrumbs — ONE component only |

### TASKS

#### TASK 7: Create AI Workspace API layer

**CREATE** `src/api/aiWorkspace.js`

```javascript
// API functions for AI Workspace backend:
// createConversation(token, { conversation_type, title, app_identifier, task_payload })
// listConversations(token, { status, limit })
// getConversation(token, conversationId)
// sendMessage(token, conversationId, content)
```

**Rules:**
- Use `apiFetch` (from `src/api/api.js`) — NEVER raw `fetch()`
- Consistent with existing API patterns in `src/api/dq.js`

**Verify:**
```bash
cd carbon-frontend && npm run lint  # your new file passes lint
```

---

#### TASK 8: Create AITaskTransferContext

**CREATE** `src/shell/AITaskTransferContext.jsx`

```javascript
// React Context that enables any page in the main workspace to transfer a task
// to the AI Workspace.
//
// Provides:
//   transferTask(type, payload, metadata)
//     type: "chat" | "dq_validate"
//     payload: { rule_id, table_name, rows, prompt, ... } — task-specific
//     metadata: { title, source_page, ... } — for display
//
// Usage from any page:
//   const { transferTask } = useAITaskTransfer();
//   transferTask('dq_validate', { rule_id: 42, ... }, { title: 'DQ Check: emissions_fuel' });
```

**Rules:**
- Context wraps the Shell (in `App.jsx` or `Shell.jsx`)
- `transferTask()` auto-opens the copilot pane if hidden
- Tasks are queued — if AI workspace is not yet mounted, they wait
- Use `useCallback` for stable references

**Verify:**
```bash
cd carbon-frontend && npm run lint
```

---

#### TASK 9: Create AIWorkspace component (replaces PulsePane)

**CREATE** `src/shell/AIWorkspace.jsx`

This is the main AI Workspace component. It replaces `PulsePane.jsx` in `Shell.jsx`.

Structure:
```
AIWorkspace
├── AIWorkspaceHeader        (title bar: "AI Workspace", collapse button)
├── AIConversationTabs       (tab bar: one tab per active conversation + "+" new chat)
└── AIConversationView       (active conversation: messages + input)
    ├── AIMessageList        (scrollable message history)
    │   ├── AIMessageBubble  (user message — right aligned)
    │   └── AIMessageBubble  (AI message — left aligned, with follow-up prompt buttons)
    └── AIInputBar           (text input + send, disabled when working/offline)
```

**States to handle:**
| State | What user sees |
|-------|---------------|
| No conversations yet | Empty state: "AI Workspace ready. Start a chat or transfer a task from the main workspace." |
| Conversations exist, none active | Tab bar shows conversations. Click one to activate. |
| Active conversation, AI working | Typing indicator ("AI is thinking…") with animated dots |
| Active conversation, AI needs input | Follow-up question buttons + text input active |
| Active conversation, completed | Messages displayed, input active for follow-up |
| AI provider offline | Banner: "AI unavailable — using offline mode. Some features limited." |
| Error | Inline error with retry button |

**Design tokens (NO raw hex/pixels):**
- Use `theme.palette` for all colors
- Use `theme.spacing()` for all spacing
- Use `theme.typography` for all text
- Font: Inter (theme default)
- Compact density (matches platform style)
- Tab bar: `variant="scrollable"` for many tabs
- Message bubbles: subtle background differentiation (user = primary.light at 8% opacity, AI = background.default with border)

**Rules:**
- NEVER use raw hex colors, raw px spacing, or inline font sizes
- Follow existing design patterns (`PageContainer`-style density, zinc/blue palette)
- Tabs use MUI `<Tabs>` + `<Tab>` with localStorage key for selected tab (RULE_17)
- Messages auto-scroll to bottom on new messages
- `Ctrl+\` still toggles the entire pane
- Pulse auth (pulseAuth.js) still runs — don't break it

**Verify:**
```bash
cd carbon-frontend && npm run lint && npm run build
```

---

#### TASK 10: Create AIWorkspace child components

Create these files in `src/shell/`:

**CREATE** `src/shell/AIWorkspaceHeader.jsx`
- Title: "AI Workspace"
- Close button (calls `toggleCopilot`)
- Compact, matches StatusBar aesthetic

**CREATE** `src/shell/AIConversationTabs.jsx`
- Tab bar with one tab per conversation
- "+" button to start new chat
- Close button on each tab (archives/completes conversation)
- Selected tab persisted to localStorage
- Tab label: conversation title or truncated first message
- Status indicator dot (green = completed, amber = needs_input, blue = working)

**CREATE** `src/shell/AIConversationView.jsx`
- Message list + input bar for the active conversation
- Calls `apiWorkspace.getConversation()` and `apiWorkspace.sendMessage()`
- Polls for status changes when conversation is in `working` state (every 2s)
- Handles `needs_input` → shows follow-up question buttons

**CREATE** `src/shell/AIMessageBubble.jsx`
- Renders a single message
- User messages: right-aligned, subtle primary background
- AI messages: left-aligned, white/paper background with border
- Markdown rendering for AI messages (use a lightweight markdown component or simple text formatting)
- Timestamp shown on hover
- If AI message has `follow_up_questions` in metadata → render as clickable chips below the message

**CREATE** `src/shell/AIInputBar.jsx`
- TextField + Send button
- Disabled when conversation status is `working` or provider is offline
- Shift+Enter for newline, Enter to send
- Placeholder changes based on state:
  - Default: "Ask a question or give directions…"
  - `needs_input`: "Respond to AI's question…"
  - `working`: "AI is thinking…" (disabled)

**CREATE** `src/shell/AIEmptyState.jsx`
- Shown when no conversations exist
- Friendly prompt: "Your AI Workspace is ready. Transfer a task from the main workspace or start a chat."
- "Start a Chat" button

**CREATE** `src/shell/AIWorkingIndicator.jsx`
- Animated typing dots
- "AI is analyzing your data…" or "AI is thinking…"

**CREATE** `src/shell/AIOfflineBanner.jsx`
- Yellow/orange banner
- "AI service is currently unavailable. You can still browse past conversations."

**Rules for ALL components:**
- THEME TOKENS ONLY — no hardcoded hex, px, or font sizes (RULE_8)
- Use `Box`, `Typography`, `IconButton` from MUI — match existing patterns
- Compact density (matches the rest of Carbon's UI)
- All text uses theme typography variants

**Verify:**
```bash
cd carbon-frontend && npm run lint && npm run build
```

---

#### TASK 11: Wire AIWorkspace into Shell

**MODIFY** `src/shell/Shell.jsx`:

1. **Replace** `import PulsePane from './PulsePane'` → `import { AIWorkspace } from './AIWorkspace'`
2. **Replace** `<PulsePane />` → `<AIWorkspace />`
3. **Wrap** the Shell (or the copilot pane) with `AITaskTransferProvider`

**MODIFY** `src/shell/StatusBar.jsx`:

1. Update tooltip from "AI Copilot" → "AI Workspace"
2. Update aria-label similarly

**DO NOT change:**
- `useShellState.js` — `copilotVisible`/`toggleCopilot` stay exactly as-is
- `Ctrl+\` shortcut
- Allotment pane sizing logic

**Verify:**
```bash
cd carbon-frontend && npm run lint && npm run build
# Manual: open browser, toggle AI Workspace, verify it renders
```

---

#### TASK 12: Add "Transfer to AI" trigger buttons on DQ pages

**MODIFY** relevant DQ pages to add transfer triggers.

Find the DQ rule run/validate button areas and add an "Open in AI Workspace" variant:

```jsx
import { useAITaskTransfer } from '../../shell/AITaskTransferContext';

// In the component:
const { transferTask } = useAITaskTransfer();

const handleOpenInAI = () => {
  transferTask('dq_validate', {
    rule_id: rule.id,
    rule_name: rule.name,
    table_name: tableName,
    prompt: rule.definition?.prompt || rule.prompt,
    fields: rule.fields,
  }, {
    title: `DQ Check: ${rule.name || 'Rule #' + rule.id}`,
    source_page: window.location.pathname,
  });
};

// Button:
<Button
  variant="outlined"
  size="small"
  startIcon={<AutoAwesomeIcon />}
  onClick={handleOpenInAI}
>
  Validate with AI
</Button>
```

**Find the right pages:** Search for existing "Run" or "Validate" buttons on DQ rule pages. Add the AI Workspace variant alongside them.

**Rules:**
- Use `variant="outlined"` with `startIcon={<AutoAwesomeIcon />}` — consistent visual language
- NEVER remove existing run buttons — the AI variant is ADDITIONAL, not a replacement
- Use theme tokens for styling

**Verify:**
```bash
cd carbon-frontend && npm run lint && npm run build
```

---

### DO NOT TOUCH (Phase 1-B)

- `src/api/api.js` — apiFetch stays as-is
- `src/auth/pulseAuth.js` — pulse key provisioning stays as-is
- `src/shell/useShellState.js` — copilotVisible/toggleCopilot unchanged
- `src/shell/ActivityBar.jsx`, `ShellSidebar.jsx`, `EditorArea.jsx` — shell components unchanged
- `src/theme/carbonTheme.js` — theme unchanged (AI Workspace consumes it, doesn't modify)
- `src/shell/Breadcrumbs.jsx` — ONE breadcrumb, unchanged
- Any backend files

### HARD RULES (from project.config.md)

- RULE_7: UI labels: never "Schema" for table
- RULE_8: Design tokens ONLY — NO hardcoded hex/pixels
- RULE_9: ONE breadcrumb — ShellBreadcrumbs.jsx only
- RULE_10: Use apiFetch for ALL API calls
- RULE_15: New routes added to studioFromPath()
- RULE_16: Full pages wrap in PageContainer or BaseDetailPage
- RULE_17: Tab switching uses MUI Tabs + localStorage

### GATES (run ALL before reporting)

```bash
# 1. Lint
cd carbon-frontend && npm run lint

# 2. Build
cd carbon-frontend && npm run build

# 3. Frontend tests
cd carbon-frontend && npm test

# 4. Anti-pattern scan
./.ai-toolkit/scripts/verify.sh frontend
```

---

## PHASE ORDER & DEPENDENCY

```
Phase 1-A (Backend) ──complete──→ Phase 1-B (Frontend)
```

**Phase 1-B CANNOT start until Phase 1-A is complete** — frontend needs the workspace API endpoints.

---

## WHAT SUCCESS LOOKS LIKE

1. User clicks `Ctrl+\` → AI Workspace opens in right pane
2. User clicks "+" tab → starts a chat conversation → AI responds
3. User is on a DQ rule page → clicks "Validate with AI" → AI Workspace opens with a DQ Check tab → AI analyzes rows → asks follow-ups → user responds → AI gives final results
4. User closes AI Workspace → comes back later → conversations are still there
5. User can switch between chat tab and DQ check tab
6. AI provider is down → AI Workspace shows offline banner, past conversations still visible
7. All existing functionality (sidebar, breadcrumbs, theme, apiFetch) still works

---

## ARCHITECTURE NOTES FOR WORKERS

1. **AI Contract §0 Sovereignty is absolute.** The frontend AI Workspace calls Carbon's backend; Carbon's backend calls Pulse. At no point does the frontend call Pulse directly for conversation messages.

2. **Conversation state lives in Carbon's DB.** Pulse is stateless — it receives the full conversation history on each call and returns a response. Carbon is the system of record.

3. **Scope is re-evaluated on every message.** The user's org-unit access may change between messages. Each `send_message()` call builds a fresh Scope from the current user state — the frozen `scope_json` on the conversation is for audit only.

4. **`needs_input` is a Carbon concept, not a Pulse concept.** Carbon's `send_message()` inspects the AI response for follow-up questions and sets conversation status accordingly. Pulse just returns content.

5. **Tab management is frontend-only.** The backend doesn't know about tabs — it just knows about conversations. The frontend maps conversations → tabs.
