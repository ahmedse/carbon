# TASKS — Phase 3: Frontend Gate Hygiene (lint config + exhaustive-deps residuals)

**Date:** 2026-08-12
**Role:** Frontend Worker (DeepSeek-V3)
**Domain:** frontend
**Status:** worker-ready spec (Master Architect)
**Refs:** [CARBON_AI_WORKSPACE_EXECUTION_DELTA.md](CARBON_AI_WORKSPACE_EXECUTION_DELTA.md) §2, §3 Phase 3

## Why this phase exists

The AI Workspace shell normalization (the originally-planned Phase 3 scope) is
**already complete and verified** — no action needed on the shell files:

- `carbon-frontend/src/shell/AIConversationView.jsx` — clean, has `normalizeConversationShape` in-file helper (fine, not exported)
- `carbon-frontend/src/shell/AITaskTransferContext.jsx` (provider) + `aiTaskTransferContext.js` (context object) + `aiTaskTransferUtils.js` (normalize) + `useAITaskTransfer.js` (hook) — this is the deliberate react-refresh split. DO NOT merge or rename.

The REAL remaining frontend work is the `verify.sh frontend` gate, which currently
FAILS on two concrete, verified root causes (discovered 2026-08-12):

1. `eslint.config.js` does not ignore `.vite/` → `eslint .` lints the Vite
   pre-bundle cache (vendored MUI/Monaco/dnd-kit) → **1236 bogus errors**.
2. 4 real `react-hooks/exhaustive-deps` warnings in app code.

## Files to Read First

- `carbon-frontend/eslint.config.js` — full config (note the `{ ignores: ['dist'] }` block at the top)
- `carbon-frontend/src/pages/emissions/EmissionFactorsPage.jsx` (around line 84)
- `carbon-frontend/src/pages/emissions/ReportGeneratorPage.jsx` (around line 53)
- `carbon-frontend/src/pages/emissions/SavedReportsPage.jsx` (around line 123)
- `carbon-frontend/src/shell/CommandPalette.jsx` (around line 235)

## Tasks

### 1. FIX ESLINT IGNORES (eliminates 1236 bogus errors)

- MODIFY `carbon-frontend/eslint.config.js`: change the top-level ignores block
  from `{ ignores: ['dist'] }` to also ignore Vite's pre-bundle cache and other
  generated dirs:
  `{ ignores: ['dist', '.vite', 'node_modules', 'coverage', 'test-results'] }`
- The `.vite` entry is the critical one — it removes the vendored
  `@mui_material`, `@monaco-editor_react`, `@dnd-kit` cache from the lint run.
- Verify: `npm run lint` error count drops to 0 errors (only warnings may remain).

### 2. FIX 4 EXHAUSTIVE-DEPS WARNINGS (pattern: wrap loader in useCallback)

All three page loaders have the identical bug — a plain `async` function declared
after `useEffect(..., [])` and called inside it:

- MODIFY `carbon-frontend/src/pages/emissions/EmissionFactorsPage.jsx`:
  wrap `loadData` in `useCallback` with deps `[token]`, declare it BEFORE the
  `useEffect`, and change the effect deps to `[loadData]`.
- MODIFY `carbon-frontend/src/pages/emissions/ReportGeneratorPage.jsx`:
  same fix for `loadPeriods` — `useCallback(..., [token])`, declare before the
  effect, deps `[loadPeriods]`.
- MODIFY `carbon-frontend/src/pages/emissions/SavedReportsPage.jsx`:
  same fix for `loadConfigs` — `useCallback(..., [token])`, deps `[loadConfigs]`.
- MODIFY `carbon-frontend/src/shell/CommandPalette.jsx`:
  the keydown `useEffect` calls `handleCommandSelect(...)` but omits it from the
  deps array `[open, filteredCommands, selectedIndex]`. Add `handleCommandSelect`
  to the deps array; if it is not already stable, wrap it in `useCallback`.

Do NOT suppress warnings with `// eslint-disable-next-line` — fix the dependency
array / memoization properly.

## DO NOT TOUCH

- `carbon-frontend/src/shell/AIConversationView.jsx` (already clean)
- `carbon-frontend/src/shell/AITaskTransferContext.jsx` + `aiTaskTransferContext.js` + `aiTaskTransferUtils.js` + `useAITaskTransfer.js` (deliberate split — do NOT merge/rename)
- `backend/**` (this is frontend-only)
- `TASK-RESULTS-*.md` files
- `docs/` and `plans/` (except appending your completion report)

## GATES (run ALL in order before reporting done)

```
cd /home/ahmed/aast/carbon/carbon-frontend && npm run lint            → 0 errors, 0 warnings
cd /home/ahmed/aast/carbon/carbon-frontend && npm run build           → build passes
cd /home/ahmed/aast/carbon/carbon-frontend && npm test                → 322 passed (baseline is green)
cd /home/ahmed/aast/carbon && bash ./.ai-toolkit/scripts/verify.sh frontend  → GATE PASSED
```

## HARD RULES

- Frontend-only. Do not touch backend files.
- Fix dependency arrays properly — no `eslint-disable` suppression.
- Do not merge or rename the react-refresh-split shell files.
- Use `apiFetch` (already the case in touched files) — do not introduce `fetch()`.
- No hardcoded hex/px — theme tokens only (not expected in these edits, but keep it clean).

## REPORT BACK

List each task with ✅ pass / ❌ fail, the `npm run lint` final error/warning
count, terminal proof of all four gates, and any deviations from spec.
