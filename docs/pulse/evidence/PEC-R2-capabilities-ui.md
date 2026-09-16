# PEC-R2 — Capabilities registry UI (Console)

**Date:** 2026-09-16  
**Worker:** frontend-worker (Pulse)  
**Scope:** Read-only Console Capabilities registry wired to `GET /carbon-api/ai/catalog/capabilities/` (PEC-R1). Closes PEC-6B deferred gap.

## What shipped

| Surface | Detail |
|---------|--------|
| API | `listCapabilities(token)` → `ai/catalog/capabilities/` via `apiFetch` |
| Panel | `CapabilitiesPanel.jsx` — DataGrid + detail drawer (loading / empty / offline / success) |
| Console | AIWorkspace activity bar tab **Capabilities** next to Skills / Processes |
| Route | `/admin/ai/capabilities` gated by `AI_VIEW_CONSOLE` |
| Nav | AI Admin sidebar item under Agents & Tooling |

## UI contract (RULE_23)

Primary grid columns: **business_name**, **kind** (outcome labels), **purpose**, **owner**, **version**, **requires_confirmation**.  
`host_action` only in the detail drawer under **Technical id**. No create/edit/delete.

Kind labels: `read_only`→Look up · `human_task`→Needs a person · `mutation`→Changes data · `assertion`→Verify.

## CBAC

Same as Skills/Processes: `ai:view_console`. Panel shows a lock message and skips fetch without it; App route uses `AdminRoute requiredCapability={AI_VIEW_CONSOLE}`.

## Verification

```bash
cd carbon-frontend && npm run lint
# ✖ 0 errors (warnings only) — exit 0

npx vitest run src/__tests__/CapabilitiesPanel.test.jsx src/__tests__/aiCatalog.test.js
# Test Files  2 passed (2)
# Tests  22 passed (22)

npm run build
# ✓ built in 19.79s
```

## Files touched

| File | Change |
|------|--------|
| `carbon-frontend/src/api/aiCatalog.js` | `listCapabilities` |
| `carbon-frontend/src/pages/admin/ai/CapabilitiesPanel.jsx` | New read-only panel |
| `carbon-frontend/src/shell/AIWorkspace.jsx` | Mount Capabilities tab |
| `carbon-frontend/src/App.jsx` | Route + lazy import |
| `carbon-frontend/src/shell/ShellSidebar.jsx` | Nav item |
| `carbon-frontend/src/i18n/locales/{en,ar}/{ai,shell}.json` | Labels |
| `carbon-frontend/src/i18n/shellLabels.js` | Nav i18n key |
| `carbon-frontend/src/__tests__/CapabilitiesPanel.test.jsx` | loading/empty/success + CBAC |
| `carbon-frontend/src/__tests__/aiCatalog.test.js` | Endpoint contract |
| `docs/pulse/evidence/PEC-R2-capabilities-ui.md` | This evidence |

## Compliance checklist

- [x] Pulse only — no people/my/team edits
- [x] RULE_8 design tokens (MUI theme / outlined Paper / Chip)
- [x] RULE_10 `apiFetch` only via `aiCatalog.js`
- [x] RULE_23 outcome copy in primary labels; `host_action` detail-only
- [x] Read-only UI — no mutate actions
- [x] SkillsPanel patterns (DataGrid, loading/empty/error, drawer)
- [x] CBAC `ai:view_console` (route + panel gate)
- [x] Vitest + lint (0 errors) + build proof
