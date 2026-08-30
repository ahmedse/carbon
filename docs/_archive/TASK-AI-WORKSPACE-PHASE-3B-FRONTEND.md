# TASK — AI Workspace Phase 3B Frontend

- **Role:** Frontend Worker
- **Recommended model:** Kimi K3
- **Domain:** Frontend (React/MUI)
- **Task ID:** AI-WORKSPACE-PHASE-3B-FRONTEND
- **Parent:** `docs/DESIGN_AI_WORKSPACE_NEXTGEN.md` §16, Phase 3-B
- **Goal:** Finish the AI Workspace frontend context layer: `#` mentions, a collapsible context panel, a summarize action, and complete provenance visibility.

## Why this phase exists

The backend context assembler and summary memoization are now in place. The frontend still needs the user-facing part of the context contract: the input bar must resolve mentions rather than only exposing kind labels, the conversation view must surface context/provenance in a stable panel, and the message bubble must show the full transparency cues that Phase 3 expects.

This phase is frontend-only. Do not touch backend code.

## Files to read first

- `.ai-toolkit/project.config.md` — project hard rules, paths, and verification commands
- `.ai-toolkit/shared/base-rules.md` — terminal, verification, and registry rules
- `.ai-toolkit/roles/frontend-worker.md` — your exact constraints and handoff rules
- `docs/DESIGN_AI_WORKSPACE_NEXTGEN.md` — Phase 3-B scope and browser checklist
- `carbon-frontend/src/shell/AIWorkspace.jsx` — current shell layout and conversation manager
- `carbon-frontend/src/shell/AIConversationView.jsx` — send modes, export menu, follow-ups
- `carbon-frontend/src/shell/AIInputBar.jsx` — current `#` kind picker
- `carbon-frontend/src/shell/AIMessageBubble.jsx` — usage chip, provenance affordance, structured cards
- `carbon-frontend/src/shell/AIWorkspaceHeader.jsx` — shell header baseline
- `carbon-frontend/src/api/aiWorkspace.js` — `summarizeConversation` wrapper and stream contract
- `carbon-frontend/src/api/dataschema.js` — table/field fetch helpers already available on the frontend side
- `carbon-frontend/src/api/catalog.js` — asset/profile lookup helpers already available on the frontend side
- `carbon-frontend/src/__tests__/AIInputBar.mentions.test.jsx` — existing mention regression baseline

## Scope

### 1. Upgrade `AIInputBar` from kind-picker to real mention resolver

- Keep the `#table / #rule / #field / #module` trigger contract.
- Replace the current fixed list only behavior with a real resolver flow:
  - on `#` trigger, show entity kinds
  - on kind selection, fetch candidate entities from the existing frontend API wrappers
  - on entity selection, insert the display token into the input and append a normalized mention object to the local mentions state
- Preserve the current send-mode behavior (`queue` / `steer` / `stop`).
- Keep the accessibility labels intact (`Message input`, `Send message`, `Send mode`, `Mention kinds`).
- Keep the existing mention regression tests passing and add any new tests needed for entity selection.

### 2. Add `AIContextPanel`

- Create a new collapsible right-side context panel for `AIConversationView`.
- The panel must show:
  - scope chips (org, module, app)
  - the current thread’s resolved mentions
  - the token budget bar from `context_snapshot_json` (T0–T4)
  - a `Summarize now` action that calls `summarizeConversation(token, conversationId)`
- The panel should read naturally alongside the existing `AIConversationView` layout and not break the current send/stream controls.
- Keep the panel presentable in compact enterprise UI density.

### 3. Surface provenance and context clearly in `AIMessageBubble`

- Complete the `↩ Why?` affordance so it uses the backend provenance payload from the API response, not just static scope text.
- The tooltip should show the human-readable model / scope / guard / context breakdown when available.
- Keep the existing usage chip and structured card rendering intact.
- Make sure follow-up chips still dispatch through `onFollowUp`.

### 4. Thread the new context data through the conversation view

- `AIConversationView` must pass the current mentions/context state into the send pipeline so the workspace context round-trips correctly.
- The summarize action should refresh the current thread and update the panel without forcing a full page reload.
- If any small API helper adjustment is needed on the frontend side, make it in `carbon-frontend/src/api/aiWorkspace.js` only.

## Do not touch

- Any backend files
- Any DQ backend API routes
- Phase 4 artifacts functionality
- The routing surface outside the AI workspace shell

## Verification gate

Run these after the edits are complete:

```bash
cd /home/ahmed/aast/carbon/carbon-frontend && npm test -- --run
cd /home/ahmed/aast/carbon/carbon-frontend && npm run lint
cd /home/ahmed/aast/carbon/carbon-frontend && npm run build
```

If the worker adds any new frontend tests or test fixtures, they must stay inside `carbon-frontend/src/__tests__/` or the existing shell/component test locations.

## Browser checklist

- `#` opens the mention menu.
- `#table ele` shows matching tables and inserts a selected entity token.
- The context panel renders scope chips, mentions, and the token budget bar after a message send.
- `Summarize now` succeeds and updates the summary/context state.
- The `↩ Why?` affordance shows provenance details, not just a label.

## Deliverable

Report back with:

- files changed
- how mentions are resolved and serialized
- how the context panel is wired
- how provenance is surfaced
- test and build proof
- any follow-up issues that should become a separate task
