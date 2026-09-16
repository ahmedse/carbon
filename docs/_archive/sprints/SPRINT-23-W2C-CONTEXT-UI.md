# Sprint 23 — W2-C: Context clear/restore + checkpoint/fork UI

**Owner:** Master Architect · **Worker Role:** frontend-worker · **Model:** DeepSeek V4-Flash
**Status:** 🚀 READY for dispatch (after W1-B)
**Design:** `docs/DESIGN_AI_WORKSTATION.md` §2.3
**Master index:** `TASKS.md` Phase W2-C (lines 1983–2029)
**Depends on:** W1-B (checkpoint/restore/fork/clear endpoints).

## Goal
Expose the context-lifecycle actions in the workstation header: **Clear context**, **Save
checkpoint**, **Restore**, and **Fork from here** — via a single header kebab menu.

## Current state (verified facts — do NOT re-discover)
- `carbon-frontend/src/shell/AIWorkspaceHeader.jsx` — header (PulseLogo + Close); the kebab mounts here.
- `carbon-frontend/src/api/aiWorkspace.js` — conversation API wrappers (`createConversation`,
  `listConversations`, `getConversation`, `updateConversation`, `deleteConversation`, …).
  No `checkpoint/restore/fork/clear` wrappers yet.
- `carbon-frontend/src/shell/AIContextPanel.jsx` — context telemetry surface (restore refreshes this).
- W1-B adds backend actions: `GET .../checkpoints/`, `POST .../checkpoint/`, `POST .../restore/`,
  `POST .../fork/`, `POST .../clear-context/`.

## Files to Change
- `carbon-frontend/src/api/aiWorkspace.js` — MODIFY: `listCheckpoints`, `checkpointConversation`,
  `restoreConversation`, `forkConversation`, `clearContext`.
- `carbon-frontend/src/shell/AIContextMenu.jsx` — ADD (checkpoint picker + clear/fork confirm).
- `carbon-frontend/src/shell/AIWorkspaceHeader.jsx` — MODIFY: mount `AIContextMenu` (kebab).
- `carbon-frontend/src/__tests__/AIContextMenu.test.jsx` — ADD.

## Tasks
1. **API wrappers** (`aiWorkspace.js`): `listCheckpoints(token, conversationId)`,
   `checkpointConversation(token, conversationId, {name, note})`,
   `restoreConversation(token, conversationId, checkpointId)`,
   `forkConversation(token, conversationId, checkpointId)`,
   `clearContext(token, conversationId)`. All via `apiFetch` (RULE_10).
2. **Header kebab** → Context menu: **Clear context** (confirm), **Save checkpoint** (name +
   note), **Restore** (picker), **Fork from here**.
3. Clear/fork show a confirm dialog (destructive-ish). Fork navigates to the NEW conversation id
   returned by W1-B. Restore refreshes `AIContextPanel` telemetry.
4. Checkpoint picker: 4-state (empty / loading / error / list). Theme tokens only (RULE_8).

## DO NOT TOUCH
- Backend files.
- `AIConversationView.jsx` message stream.

## Verification Gate
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npm run lint
npx vitest run src/__tests__/AIContextMenu.test.jsx
npm run build
```

## Hard rules
- `apiFetch` only (RULE_10). Theme tokens only (RULE_8). MUI v6 Grid `<Grid size={{...}}>`.

## Output contract
Append to `TASK-RESULTS.md`.

## Notes for the Master
- Fork/clear never delete the durable conversation — make that visible in the copy.
