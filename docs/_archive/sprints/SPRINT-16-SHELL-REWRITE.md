# Sprint 16 — Frontend Shell Rewrite (durable sessions, stream-all, interrupt)

**Owner:** Master Architect · **Status:** 🚀 Ready for Frontend Worker dispatch (after Sprints 13+14 backend)
**Design:** `docs/DESIGN_AI_WORKSPACE_NEXTGEN.md` §7
**Contract:** `.ai-toolkit/shared/design-system.md` + RULE_8 (tokens), RULE_10 (apiFetch), RULE_17 (Tabs)

## Goal
Rewrite the shell around durable, id-keyed, streamable, interruptible sessions. Fix the
inert follow-up chips (real bug) and the `indexOf` tab identity (fragile).

## Current state (verified facts — do not re-discover)
- `src/api/aiWorkspace.js` — `createConversation`, `listConversations`, `getConversation`,
  `sendMessage`, `sendMessageStream` (handles only `chunk`/`done`/`error` frames), `recordFeedback`,
  `acceptSuggestion`, `rejectSuggestion`. No PATCH/DELETE/messages-list/stop.
- `src/shell/AIWorkspace.jsx` — flat `conversations` array, `handleCloseTab` is client-side
  `filter` only (bug G1). `LOCAL_STORAGE_KEY = 'carbon-ai-active-conversation'`.
- `src/shell/AIConversationTabs.jsx` — `value={conversations.indexOf(conv)}` (bug G6),
  `STATUS_DOT_COLORS`, `CONVERSATION_TYPE_LABELS`.
- `src/shell/AIConversationView.jsx` — 2s polling for non-chat (`POLL_INTERVAL_MS`), disabled
  input while `working`, `handleFollowUp` exists and is wired to `needs_input` Buttons, but
  the follow-up `Chip`s in `AIMessageBubble.jsx` render `clickable` with NO `onClick` (bug G7).
- `src/shell/AIInputBar.jsx` — single send button, disabled during working.
- `src/shell/AIMessageBubble.jsx` — follow-up `Chip`s inert; no usage chip; no stopped marker.

## Tasks

### 1. API client additions
MODIFY `src/api/aiWorkspace.js`:
- `updateConversation(token, id, { title, is_pinned, is_archived, visibility })` → PATCH.
- `deleteConversation(token, id)` → DELETE.
- `listMessages(token, conversationId, { limit, before, after })` → GET messages list.
- `stopGeneration(token, conversationId)` → POST `stop/`.
- `regenerateMessage(token, conversationId, messageId)` → POST `regenerate/`.
- `editMessage(token, conversationId, messageId, content)` → PATCH message.
- `exportConversation(token, conversationId, format)` → GET export.
- Extend `sendMessageStream` to also handle `progress` (call new `onProgress(stage, message)`)
  and `stopped` (call new `onStopped(conversation)`) frames. Use `apiFetch` where possible;
  for the raw stream keep the existing fetch+ReadableStream approach.

### 2. Rewrite AIWorkspace.jsx (durable id-keyed store)
MODIFY `src/shell/AIWorkspace.jsx`:
- Replace flat array with normalized state: `{ byId, order, pinnedIds, archivedIds, activeId, query }`
  (a plain object + arrays in useState is fine; no external store lib).
- `handleCloseTab` → call `updateConversation(token, id, { is_archived: true })` then remove
  from active `order` (persistent). Archive is reversible via a search filter
  (`archivedIds` list + a small "Archived" filter toggle).
- Add rename (inline via a small prompt-less TextField in the tabs context menu or a
  `Rename` action), pin toggle, delete (confirm dialog → `deleteConversation`).
- Add search input filtering by title (client-side over `byId` + refetch with `?q=` on submit).
- Keep `LOCAL_STORAGE_KEY` persistence of `activeId`.
- Keyboard: `Ctrl+\` toggles close (existing), `Ctrl+W` archives active tab, `Ctrl+Shift+T`
  restores last-archived.

### 3. Rewrite AIConversationTabs.jsx (id-keyed)
MODIFY `src/shell/AIConversationTabs.jsx`:
- `value` = conversation `id` (NOT index). Remove `conversations.indexOf(conv)`.
- Add context menu (right-click or a `MoreVert` icon) with Pin/Unpin, Rename, Archive, Delete.
- Keep `STATUS_DOT_COLORS`/`CONVERSATION_TYPE_LABELS`; add `anomaly` label.
- Pass new props: `onRename(id, title)`, `onPin(id)`, `onArchive(id)`, `onDelete(id)`.

### 4. Rewrite AIConversationView.jsx (stream-all + interrupt + paginate)
MODIFY `src/shell/AIConversationView.jsx`:
- Remove the 2s poll path entirely. Route ALL types through `sendMessageStream` with
  `onProgress` (render a live status line — pass stage/message to `AIWorkingIndicator`),
  `onDone`, `onStopped`, `onError`.
- Input is NOT disabled while `working`: pass a `working` prop to `AIInputBar` and add a
  small send-mode dropdown (queue / steer / stop): default `queue` (buffer client-side,
  send on `done`), `steer` (call `stopGeneration` then send immediately), `stop`
  (call `stopGeneration` only). Implement a minimal dropdown; do not over-engineer.
- Infinite scroll: load messages via `listMessages` with `before` cursor when scrolled to
  top; append new streamed messages at bottom. Keep `getConversation` for initial load.
- Render `stopped` state: show "Interrupted" + a "Continue" button that re-sends.

### 5. Fix AIMessageBubble.jsx (follow-ups + usage + stopped)
MODIFY `src/shell/AIMessageBubble.jsx`:
- **BUG G7**: wire `onClick={() => onFollowUp?.(q)}` on follow-up `Chip`s (add `onFollowUp`
  prop, pass from `AIConversationView`).
- Add usage chip: when `message.token_usage_json` has `total_tokens`/`model`/`cost_usd`/
  `latency_ms`, render a small `Chip` (`{model} · {total_tokens} tok · ${cost_usd} · {latency_ms}ms`).
- `status === "stopped"` renders an "Interrupted" `Chip` (color warning).
- `status === "failed"` renders an "Error" `Chip` (color error).

### 6. AIInputBar.jsx (queue/steer/stop)
MODIFY `src/shell/AIInputBar.jsx`:
- Accept `working` prop. When `working`, show a small `Select` (Send on done / Interrupt & send / Stop)
  in place of (or beside) the send button; otherwise normal send. Enter still sends (queues when working).

### 7. Tests (REQUIRED)
CREATE/EXTEND `src/shell/__tests__/` (or existing test location — READ FIRST where AI tests live):
- `AIConversationTabs` uses id-based `value` (assert no `indexOf` regression via behavior).
- `AIMessageBubble` follow-up Chip invokes `onFollowUp` on click (the regression test for G7).
- `AIMessageBubble` renders usage chip when `token_usage_json` present; renders "Interrupted"
  when `status === "stopped"`.
- `AIWorkspace` close-tab calls `updateConversation` with `is_archived: true` (mock apiFetch).

## DO NOT TOUCH
- `backend/**`
- `src/shell/Shell.jsx`, `src/shell/ShellSidebar.jsx`, `src/shell/Breadcrumbs.jsx`
- `src/theme/**`, `src/components/layout/**`, `src/components/detail/**`

## GATES (run ALL, paste output)
```bash
cd /home/ahmed/aast/carbon/carbon-frontend && npm test -- --run
cd /home/ahmed/aast/carbon/carbon-frontend && npm run lint
cd /home/ahmed/aast/carbon/carbon-frontend && npm run build
grep -rn "\bitem\b.*xs=\|<Grid item\b" src/ --include="*.jsx"   # expect ZERO
```

## HARD RULES
- RULE_8: theme tokens only — no raw hex/px/inline font sizes.
- RULE_10: all API via `apiFetch` (or the existing stream helper); never raw `fetch` outside `sendMessageStream`.
- RULE_17: tab switching stays MUI `Tabs` + `Tab`.
- MUI v6 Grid: `size={{ xs: 12 }}` — never `item` / `xs=` direct props.
- Notifications via `useNotification` (`notifyFromError` in catch blocks); never `alert()`.

## REPORT BACK
Task-by-task ✅/❌, test count, lint/build output, deviations.
