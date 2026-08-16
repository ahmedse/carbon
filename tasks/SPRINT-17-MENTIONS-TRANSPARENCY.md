# Sprint 17 — Context Mentions + Transparency + Export UI (frontend)

**Owner:** Master Architect · **Status:** 🚀 Ready for Frontend Worker dispatch (after Sprints 15+16)
**Design:** `docs/DESIGN_AI_WORKSPACE_NEXTGEN.md` §6.3 + §8

## Goal
Explicit `#`-mentions in the input, per-turn token/cost transparency, and transcript export
UI. Surfacing what the SOTA leaders surface (Copilot `#`-mentions, Claude usage, ChatGPT export).

## Current state (verified facts — do not re-discover)
- `src/api/aiWorkspace.js` (post-Sprint 16) has `exportConversation`, `createConversation`
  with `workspace_context`, `sendMessageStream` with `onProgress`.
- `src/shell/AIInputBar.jsx` — plain multiline TextField, no mentions.
- `src/shell/AIMessageBubble.jsx` — post-Sprint 16 has usage chip + follow-up onClick.
- `src/components/NotificationProvider` — `notify`/`notifyFromError`.

## Tasks

### 1. `#`-mentions in AIInputBar
MODIFY `src/shell/AIInputBar.jsx`:
- Parse a leading `#` trigger in the input; show a small autocomplete list of entity
  kinds the WorkspaceContext knows: `table`, `rule`, `field`, `module` (fixed kind list —
  do not fetch entities; the source workspace supplies ids). Selecting a kind inserts
  `#table ` / `#rule ` etc. into the text. Keep it lightweight (no remote entity search this
  sprint; a documented `TODO` for entity resolution).
- Accept an optional `onMentionsChange(mentions)` prop so the parent can append resolved
  mentions to `workspace_context`. Minimal: pass `mentions: string[]` up on send.

### 2. Per-turn transparency
MODIFY `src/shell/AIMessageBubble.jsx` (if not already done in Sprint 16):
- Ensure the usage chip renders `model · N tok · $cost · latency` from `token_usage_json`
  when present, with a `Tooltip` showing the breakdown.

### 3. Export UI
MODIFY `src/shell/AIConversationView.jsx` (or a small header action):
- Add an "Export" control that calls `exportConversation(token, id, 'markdown')` and triggers
  a client-side download (Blob → `<a download>`). Also offer JSON via a small menu.
- Use `notify` on success / `notifyFromError` on failure.

### 4. "Why this answer" tooltip (provenance)
MODIFY `src/shell/AIMessageBubble.jsx`:
- If the message has `metadata_json.type` (structured) or the conversation scope is available,
  render a small info icon with a `Tooltip` showing `conversation_type`, `app_identifier`,
  and `scope_json` org-unit count. Keep it read-only. Wire the needed fields via props from
  `AIConversationView` (it already has the `conversation` object).

### 5. Tests (REQUIRED)
- `AIInputBar` `#` trigger shows the kind list and inserting a kind sets the text.
- `AIMessageBubble` usage chip `Tooltip` and "why this answer" tooltip render without crashing.

## DO NOT TOUCH
- `backend/**`
- `src/theme/**`, `src/shell/Shell.jsx`, `src/shell/ShellSidebar.jsx`, `src/shell/Breadcrumbs.jsx`

## GATES (run ALL, paste output)
```bash
cd /home/ahmed/aast/carbon/carbon-frontend && npm test -- --run
cd /home/ahmed/aast/carbon/carbon-frontend && npm run lint
cd /home/ahmed/aast/carbon/carbon-frontend && npm run build
grep -rn "\bitem\b.*xs=\|<Grid item\b" src/ --include="*.jsx"   # expect ZERO
```

## HARD RULES
- RULE_8 tokens; RULE_10 apiFetch; RULE_17 Tabs.
- No raw hex/px; no `alert()`; `notifyFromError` in catch blocks.

## REPORT BACK
Task-by-task ✅/❌, test count, lint/build output, deviations.
