# TASKS.md — AI Admin Menu Section (Frontend)

**Role:** Frontend Worker
**Model:** DeepSeek-V3
**Domain:** frontend
**Primary context:** `.ai-toolkit/shared/design-system.md`, `.ai-toolkit/project.config.md` (RULE_8, RULE_10, RULE_15, RULE_16, RULE_17)

Add a complete, AI-dedicated section to the admin sidebar studio, with routes + pages.
Reuse the existing AI workspace surface and API client. Do NOT invent backend endpoints.

FILES TO READ FIRST:
- `carbon-frontend/src/shell/ShellSidebar.jsx` — admin case (~lines 107-129) where the AI group goes
- `carbon-frontend/src/shell/Shell.jsx` — studioFromPath (RULE_15) — confirm /admin/* already maps to admin studio
- `carbon-frontend/src/App.jsx` — admin route block (~lines 220-295) + AdminRoute usage
- `carbon-frontend/src/api/aiWorkspace.js` — existing conversation API client (listConversations, getConversation, sendMessage)
- `carbon-frontend/src/shell/AIWorkspace.jsx` + `AIConversationView.jsx` — existing AI surface to reuse/embed
- `carbon-frontend/src/components/layout/PageContainer.jsx` — page wrapper (RULE_16)
- `carbon-frontend/src/pages/admin/UsersPage.jsx` — pattern for an admin page

TASKS:

1. ADD THE AI NAV GROUP TO THE ADMIN SIDEBAR
   - MODIFY `carbon-frontend/src/shell/ShellSidebar.jsx`: in `case 'admin'`, insert an "AI" group (with a divider) containing:
     - `{ type: 'group', label: 'AI' }`
     - `{ label: 'AI Workspace', path: '/admin/ai', icon: AutoAwesomeIcon, role: 'admin' }`
     - `{ label: 'Conversations', path: '/admin/ai/conversations', icon: ChatIcon, role: 'admin' }`
   - Reuse MUI icons already imported; add imports only if missing.

2. CREATE THE AI ADMIN PAGES
   - CREATE `carbon-frontend/src/pages/admin/ai/AIAdminPage.jsx` — wrap in PageContainer; embed the existing AI workspace conversation surface (reuse AIWorkspace/AIConversationView, or a focused admin variant). Route `/admin/ai`.
   - CREATE `carbon-frontend/src/pages/admin/ai/AIConversationsPage.jsx` — PageContainer; list conversations via `aiWorkspace.listConversations`; click → `getConversation`. Route `/admin/ai/conversations`.
   - Reuse `src/api/aiWorkspace.js` — never raw fetch (RULE_10).

3. REGISTER ROUTES
   - MODIFY `carbon-frontend/src/App.jsx`: add two `<Route>` entries under `<AdminRoute>` for `/admin/ai` and `/admin/ai/conversations` (lazy-import the pages like existing admin pages).

4. STUDIO MAPPING (RULE_15)
   - Confirm `/admin/*` already maps to 'admin' studio in `Shell.jsx` studioFromPath (it does — `/admin` is covered). If you introduce any NEW top-level prefix, add it; otherwise no change needed.

DO NOT TOUCH:
- `backend/**` (frontend-only phase)
- `carbon-frontend/src/shell/Shell.jsx` (unless RULE_15 requires a new prefix — it should not)
- `carbon-frontend/src/shell/AIWorkspace.jsx`, `AIConversationView.jsx` (reuse, do not refactor)

GATES (run ALL in order before reporting done):
  cd /home/ahmed/aast/carbon/carbon-frontend && npm run lint → clean
  cd /home/ahmed/aast/carbon/carbon-frontend && npm run build → builds without error
  cd /home/ahmed/aast/carbon && bash ./.ai-toolkit/scripts/verify.sh frontend → frontend gate passes

HARD RULES:
- RULE_8: design tokens only — no hardcoded hex/spacing/font sizes.
- RULE_10: apiFetch only — never raw fetch().
- RULE_16: every full page wrapped in PageContainer.
- RULE_17: tab switching via MUI Tabs (if tabs are used).
- Do NOT invent backend endpoints; reuse `src/api/aiWorkspace.js`.

REPORT BACK:
List each task with ✅ pass / ❌ fail, terminal proof, and any deviations from spec.
