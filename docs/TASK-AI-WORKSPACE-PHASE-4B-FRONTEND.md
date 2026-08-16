# TASK — AI Workspace Phase 4B Frontend

- **Role:** Frontend Worker
- **Recommended model:** Kimi K3
- **Domain:** Frontend (React/MUI)
- **Task ID:** AI-WORKSPACE-PHASE-4B-FRONTEND
- **Parent:** `docs/DESIGN_AI_WORKSPACE_NEXTGEN.md` §16, Phase 4-B
- **Goal:** Add the enterprise artifacts layer to the AI Workspace frontend: artifacts tab, artifact cards/browser, export refinements, and full provenance rendering.

## Why this phase exists

Phase 3 completed mentions and the context panel. The frontend still needs the enterprise governance layer: users should be able to browse promoted artifacts, export the current conversation from the conversation view, and inspect a real provenance payload in the message bubble.

This phase is frontend-only. Do not touch backend code.

## Files to read first

- `.ai-toolkit/project.config.md` — project hard rules, paths, and verification commands
- `.ai-toolkit/shared/base-rules.md` — terminal, verification, and registry rules
- `.ai-toolkit/roles/frontend-worker.md` — your exact constraints and handoff rules
- `docs/DESIGN_AI_WORKSPACE_NEXTGEN.md` — Phase 4-B scope and browser checklist
- `carbon-frontend/src/shell/AIWorkspace.jsx` — current fixed-tab shell layout
- `carbon-frontend/src/shell/AIConversationView.jsx` — export menu, send pipeline, thread view
- `carbon-frontend/src/shell/AIMessageBubble.jsx` — usage, provenance, structured cards
- `carbon-frontend/src/shell/AIWorkspaceHeader.jsx` — shell header baseline
- `carbon-frontend/src/api/aiWorkspace.js` — `exportConversation`, `summarizeConversation`, stream contract
- `carbon-frontend/src/components/dq/AIActionButton.jsx` — compact action button pattern used in the workspace
- `carbon-frontend/src/components/detail/BaseDetailPage.jsx` — shell/page layout conventions

## Scope

### 1. Add the Artifacts tab to `AIWorkspace`

- Add a fourth fixed tab for Artifacts in the AI workspace shell.
- Keep the existing fixed-tab rule intact; do not create dynamic per-thread tabs.
- The tab should load the artifact browser component and fit the current shell density.

### 2. Create `AIArtifactBrowser` and `AIArtifactCard`

- Build a filterable artifact browser component.
- Each artifact should render as a card with at least:
  - type icon or label
  - title
  - created date
  - open action
- Support basic filtering and empty/loading/error states consistent with the rest of the shell.
- Keep the implementation compact and theme-token driven.

### 3. Add artifact promotion entry points

- Add a visible `Promote to Artifact` action where the design doc expects it.
- The action should prepare the payload shape the backend API expects:
  - `conversation_id`
  - `message_id`
  - `title`
  - `artifact_type`
  - `content_json`
- If a small client-side helper is needed, place it in the AI workspace API layer or the shell component that owns the action.

### 4. Finish export behavior in the conversation view

- Keep the export menu in `AIConversationView` and make sure it works cleanly with the new artifact flow.
- Export should still produce Markdown and JSON downloads with sensible filenames.
- Keep the existing `?fmt=` backend contract.
- If any presentation changes are needed for artifact promotion, keep them localized to the conversation view.

### 5. Make provenance fully useful in `AIMessageBubble`

- Render the backend `message.provenance` payload when present.
- The tooltip should show model, scope snapshot, context snapshot, guard results, and engine turn id in a human-readable format.
- Preserve the existing fallback behavior when provenance is missing.
- Keep the usage chip and structured card rendering unchanged except where needed to surface the new provenance content.

### 6. Add regressions

- Add tests for the artifacts tab/browser/card.
- Add a test for the promotion action payload if you wire one in the frontend.
- Add or update provenance tooltip tests.
- Keep the existing mention/context tests and AI workspace shell tests passing.

## Do not touch

- Any backend files
- The DQ workspace shell
- Mention resolution logic from Phase 3B except where needed to read provenance or artifact state
- Any unrelated routes outside the AI workspace shell

## Verification gate

Run these after the edits are complete:

```bash
cd /home/ahmed/aast/carbon/carbon-frontend && npm test -- --run
cd /home/ahmed/aast/carbon/carbon-frontend && npm run lint
cd /home/ahmed/aast/carbon/carbon-frontend && npm run build
```

## Browser checklist

- The Artifacts tab renders in the workspace shell.
- Artifact cards render with title, type, and created date.
- Export JSON downloads a file with the expected name.
- Export Markdown downloads a file with the expected name.
- `↩ Why?` shows provenance details from the backend payload.
- Promoted artifacts appear in the browser after refresh or re-fetch.

## Deliverable

Report back with:

- files changed
- how the artifacts tab/browser/card is wired
- how promotion and export were handled
- how provenance is rendered
- test and build proof
- any follow-up issues that should become a separate task
