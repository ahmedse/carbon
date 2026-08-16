# TASK — AI Workspace Phase 5B Frontend

- **Role:** Frontend Worker
- **Recommended model:** Kimi K3
- **Domain:** Frontend (React/MUI)
- **Task ID:** AI-WORKSPACE-PHASE-5B-FRONTEND
- **Parent:** `docs/DESIGN_AI_WORKSPACE_NEXTGEN.md` §16, Phase 5 (frontend render targets)
- **Goal:** Consume the Phase 5 backend endpoints in the AI Workspace shell: render a 🔔 Suggestions rail at the top of the thread rail, and a pinned "catch-up" summary when a user returns to a thread after more than 24 hours.

## Why this phase exists

Phase 5 backend shipped the durable-intelligence layer: proactive suggestions, long-term memory, and resume catch-up. Those surfaces are backend-only — the frontend still has nowhere to show them. This phase wires the two render targets the design doc calls out:

1. a `🔔 Suggestions` section at the top of the thread rail (proactive insights from `KgProactiveInsight`), and
2. a pinned catch-up summary at the top of the conversation ("Since your last visit: 3 new DQ violations, 1 anomaly detected.").

This phase is frontend-only. Do not touch backend code.

## Backend contract (already live — do not re-implement)

Both endpoints are already mounted under the AI Workspace router (`backend/ai/workspace_api.py`). Routes are relative to the workspace conversations base (`/carbon-api/ai/workspace/conversations/`).

### `GET .../conversations/{id}/suggestions/?limit=N`

`limit` clamps 1–50 (default 10). Returns:

```json
{
  "suggestions": [
    {
      "id": "uuid-string",
      "severity": "info|warn|error|...",
      "title": "string",
      "narrative": "string",
      "insight_type": "string",
      "recommended_actions": ["string", "..."],
      "context": { },
      "created_at": "ISO-8601 string"
    }
  ]
}
```

- `id` is the `KgProactiveInsight` primary key serialized as a **string**.
- `recommended_actions` and `context` are already coerced from JSON strings to native arrays/objects server-side (do not `JSON.parse` them again).
- Returns **404** with `{"error": "Conversation {id} not found."}` when the conversation is inaccessible/unknown.

### `POST .../conversations/{id}/resume/`

Marks the thread as viewed and returns a catch-up when stale. Returns:

```json
{
  "conversation": { "...": "serialized conversation object" },
  "catch_up": {
    "since": "ISO-8601 string",
    "hours_since_last_view": 27,
    "new_dq_violations": 3,
    "new_anomalies": 1,
    "new_memory_facts": 2,
    "new_suggestions": 0,
    "summary_lines": ["3 new DQ violation(s)", "1 new anomaly/anomalies"]
  }
}
```

- `catch_up` is **`null`** when the user last viewed the thread less than 24 hours ago (no summary to show).
- `summary_lines` is always non-empty; the empty-activity case is a single `"No new activity since your last visit."`.
- Returns **404** with `{"error": "Conversation {id} not found."}` on an inaccessible/unknown id.
- **Idempotency note:** each successful `resume` bumps `last_viewed_at`, so the catch-up is only returned the first time a stale thread is reopened. Call it once per thread-open (see wiring notes below); do not poll it.

## Files to read first

- `.ai-toolkit/project.config.md` — project hard rules, paths, and verification commands
- `.ai-toolkit/shared/base-rules.md` — terminal, verification, and registry rules
- `.ai-toolkit/roles/frontend-worker.md` — your exact constraints and handoff rules
- `docs/DESIGN_AI_WORKSPACE_NEXTGEN.md` — §16 Phase 5 + §15 instrumentation contract
- `carbon-frontend/src/api/aiWorkspace.js` — API layer (add `getSuggestions` + `resumeConversation`)
- `carbon-frontend/src/shell/AIWorkspace.jsx` — shell layout; where the suggestion rail mounts
- `carbon-frontend/src/shell/AIConversationTabs.jsx` — the thread rail (horizontal tab bar)
- `carbon-frontend/src/shell/AIConversationView.jsx` — conversation render; where the catch-up summary pins
- `carbon-frontend/src/shell/AIMessageBubble.jsx` — the DQ-suggestion card pattern (for visual consistency, NOT the same data source)
- `carbon-frontend/src/components/NotificationProvider.jsx` — `notifyFromError` for 404/error handling
- `carbon-frontend/src/components/layout/PageHeader.jsx` — density conventions

## Scope

### 1. Add API functions in `carbon-frontend/src/api/aiWorkspace.js`

Add two thin wrappers using the existing `apiFetch` pattern:

- `getSuggestions(token, conversationId, limit = 10)` → `GET .../conversations/{conversationId}/suggestions/?limit={limit}` → returns the parsed `{ suggestions }` body.
- `resumeConversation(token, conversationId)` → `POST .../conversations/{conversationId}/resume/` → returns the parsed `{ conversation, catch_up }` body.

Keep the path builder consistent with the existing `conversations/${id}/...` helpers already in the file. Return the full parsed body (the callers own unwrapping `suggestions` / `catch_up`).

### 2. Create the Suggestions rail

Build a compact, theme-token-driven `AISuggestionRail.jsx` in `carbon-frontend/src/shell/`:

- **Data:** fetch via `getSuggestions(token, activeConversationId)` when the shell has an active conversation. Handle `loading` / `error` / `empty` (show nothing, or a collapsed 🔔 with a count) / `loaded` states.
- **Presentation:** render each suggestion as a compact row/card with at least `severity` (chip), `title`, and `narrative` (truncated, expandable on click or hover). `insight_type` and `created_at` are optional secondary text.
- **Read-only:** these are proactive insights with **no** accept/reject endpoint in scope. Do not reuse `acceptSuggestion`/`rejectSuggestion` from `aiWorkspace.js` — those hit `dq/suggestions/{id}/...` (DQ rule suggestions, a different model). The rail is display-only in this phase.
- **Collapse behavior:** if it would dominate the rail, make the section collapsible (🔔 with a pending count in the header, expand to show items). Persist the open/closed state to localStorage under a stable key (e.g. `carbon-ai-suggestions-rail-open`), following the shell's existing localStorage conventions.

### 3. Mount the rail in `AIWorkspace.jsx`

- Render `AISuggestionRail` **above** `AIConversationTabs` (top of the thread rail), only when `hasAny` and there is a non-null `effectiveActiveId`.
- It must not push the conversation tabs or view out of the layout — keep it compact and bounded (e.g. `maxHeight` with internal scroll).
- Do not change the fixed-tab rule (`Chat` / `Artifacts` modes) or add any dynamic tabs.

### 4. Pinned catch-up summary in `AIConversationView.jsx`

- On mount (and when `conversationId` changes), call `resumeConversation(token, conversationId)` **once**.
  - On success: if `catch_up` is non-null, render a pinned "Since your last visit" banner at the top of the message list. It must be clearly separate from normal chat messages (e.g. a distinct `info`/`warning` surface, not an `AIMessageBubble`).
  - On `catch_up === null`, render nothing and proceed normally.
  - On 404/error: do **not** block the conversation view — log/handle quietly (the thread still renders its messages). Use `notifyFromError` only for non-404 failures, and avoid spamming on 404.
- Render the summary from `summary_lines` (ordered list) plus an optional `hours_since_last_view` caption. Ignore `new_*` counts except as an alternative display source if `summary_lines` is absent.
- Do not re-trigger `resume` on every re-render or message poll — guard with a ref keyed on `conversationId`.
- Preserve the existing `dq_suggestions` accept/reject flow, streaming, stop/regenerate, and export behavior untouched.

### 5. Add regressions

- `carbon-frontend/src/__tests__/aiWorkspacePhase5.test.jsx` (or extend an existing AI workspace test file):
  - `AISuggestionRail` renders items from a mocked `getSuggestions` response (severity chip + title + narrative).
  - `AISuggestionRail` renders nothing (or collapsed 🔔) when the response is empty.
  - `AIConversationView` shows the pinned catch-up banner when `resumeConversation` resolves with a non-null `catch_up`.
  - `AIConversationView` shows no banner when `resumeConversation` resolves `catch_up: null`.
  - `AIConversationView` still renders messages when `resumeConversation` rejects (404 path).
- Mock the API layer at the module boundary (`vi.mock('../api/aiWorkspace')`), consistent with the existing test conventions (see `src/__tests__/` for the current mock style — note `@mui/x-data-grid` may require importing pure helpers rather than the component under vitest `css:false`; follow the Phase H `pulseFormat.js` precedent if a DataGrid is involved).
- Keep the existing AI workspace shell + mention/context tests passing.

## Do not touch

- Any backend files (`backend/**`)
- `AIMessageBubble`'s DQ-suggestion card logic (different data source)
- The DQ workspace shell
- Mention resolution logic from Phase 3B
- Any routes outside the AI workspace shell

## Verification gate

Run these after the edits are complete:

```bash
cd /home/ahmed/aast/carbon/carbon-frontend && npm test -- --run
cd /home/ahmed/aast/carbon/carbon-frontend && npm run lint
cd /home/ahmed/aast/carbon/carbon-frontend && npm run build
```

## Browser checklist

- 🔔 Suggestions rail appears above the thread rail when an active conversation exists and there are pending insights.
- Suggestion rows show severity, title, and narrative; collapse toggles and persists across reloads.
- Opening a thread last viewed >24h ago shows the pinned "Since your last visit" summary; reopening it again within 24h shows no banner.
- Opening a thread last viewed <24h ago shows no banner.
- Conversations with no messages still render normally even if `resume` or `suggestions` 404s.
- Streaming, stop, regenerate, export, and DQ-suggestion accept/reject still work.

## Deliverable

Report back with:

- files changed
- how `getSuggestions` / `resumeConversation` are wired
- how the suggestion rail and catch-up banner are rendered and where they mount
- the idempotency/guard behavior on `resume`
- test and build proof
- any follow-up issues that should become a separate task
