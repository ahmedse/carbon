# TASKS.md — Pulse Console Frontend (Phase A: full menu + live panels + gated scaffolding)

**Role:** Frontend Worker
**Model:** DeepSeek-V3
**Domain:** frontend
**Primary context:** `docs/PULSE_CONSOLE_DESIGN.md` (THE full IA), `.ai-toolkit/project.config.md` (RULE_8/10/15/16/17)

Build the COMPLETE Pulse console section in the admin sidebar (16 panels, 5 groups).
Three panels are live now; the rest get a shared placeholder until the backend ops API lands.

FILES TO READ FIRST:
- `docs/PULSE_CONSOLE_DESIGN.md` — the full menu tree + panel mapping (authoritative)
- `carbon-frontend/src/shell/ShellSidebar.jsx` — admin case (current thin AI group)
- `carbon-frontend/src/App.jsx` — admin route block + AdminRoute
- `carbon-frontend/src/shell/Shell.jsx` — studioFromPath (RULE_15)
- `carbon-frontend/src/api/aiWorkspace.js` — existing conversation client
- `carbon-frontend/src/shell/AIWorkspace.jsx` + `AIConversationView.jsx` — reuse
- `carbon-frontend/src/pages/admin/ai/AIAdminPage.jsx` + `AIConversationsPage.jsx` — existing
- `carbon-frontend/src/components/layout/PageContainer.jsx`

TASKS:

1. BUILD THE COMPLETE PULSE MENU
   - MODIFY `carbon-frontend/src/shell/ShellSidebar.jsx` `case 'admin'`: replace the thin
     `AI` group with a full `Pulse` group containing the 5 sub-groups and all 16 items from
     `docs/PULSE_CONSOLE_DESIGN.md` §2, with icons. Order and paths MUST match the design doc.
   - Use appropriate MUI icons (AutoAwesome, Chat, Psychology, Memory, AccountTree, SmartToy,
     Hub, Handyman, Extension, AutoFixHigh, MenuBook, Feedback, Loop, MonitorHeart, History,
     Article). Add imports only for icons not already imported.

2. LIVE PANEL — OVERVIEW (graceful degrade)
   - CREATE `carbon-frontend/src/pages/admin/ai/PulseOverviewPage.jsx`: PageContainer.
     Fetch `ai/pulse/health/` via apiFetch; on 404/error show an offline empty
     state ("Pulse provider offline / not yet wired"). On success render ProviderStatus
     (name, version, healthy, modules). Do NOT invent other data.
   - Register route `/admin/ai` → this page (moves the current AIWorkspace landing).

3. LIVE PANELS — WORKSPACE + CONVERSATIONS
   - MOVE the existing workspace page to route `/admin/ai/workspace` (reuse `AIAdminPage` or
     `AIWorkspace`). Keep `/admin/ai/conversations` as-is (`AIConversationsPage`).

4. GATED PANELS — SHARED PLACEHOLDER
   - CREATE `carbon-frontend/src/pages/admin/ai/PulseModulePlaceholder.jsx`: PageContainer
     with the module title + a message "Requires Pulse backend ops API (Phase 2). Not yet
     wired." Accept a `module` prop.
   - REGISTER routes for all gated panels (`/admin/ai/knowledge|memory|graph|agents|mcp|tools|skills|archetypes|prompts|feedback|learning|monitoring|audit|logs`) each rendering
     `PulseModulePlaceholder module="..."`. Lazy-import once, reuse the component.

5. ROUTES + STUDIO MAPPING
   - MODIFY `carbon-frontend/src/App.jsx`: add all `/admin/ai/*` routes under `<AdminRoute>`.
   - Confirm `/admin/*` maps to admin studio in `Shell.jsx` (RULE_15) — no new top-level prefix, so no change expected.

DO NOT TOUCH:
- `backend/**` (frontend-only)
- `carbon-frontend/src/api/aiWorkspace.js` (extend only if a new function is needed; do not refactor)
- `carbon-frontend/src/shell/AIWorkspace.jsx`, `AIConversationView.jsx` (reuse)

GATES (run ALL in order before reporting done):
  cd /home/ahmed/aast/carbon/carbon-frontend && npm run lint → clean
  cd /home/ahmed/aast/carbon/carbon-frontend && npm run build → builds without error
  cd /home/ahmed/aast/carbon && bash ./.ai-toolkit/scripts/verify.sh frontend → gate passes
  cd /home/ahmed/aast/carbon/carbon-frontend && npm test → existing tests still pass

HARD RULES:
- RULE_8 tokens; RULE_10 apiFetch; RULE_16 PageContainer; RULE_17 MUI Tabs; RULE_15 studioFromPath.
- Read-only console: no mutation controls for gated panels (RULE_21).

REPORT BACK:
List each task with ✅/❌, terminal proof, deviations.
