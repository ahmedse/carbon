# Sprint 27 — R4: 429 throttle storm from uncached table refetch (F-07)

**Owner:** Master Architect · **Worker Role:** frontend-worker · **Model:** DeepSeek V4-Flash
**Status:** 🚀 READY for dispatch
**Source:** `docs/TASK-RESULT-QA-AI-PULSE-SIMULATION.md` finding F-07
**Priority:** P2 (degrades all AI admin pages under sustained use).

## Goal
Stop `refetchTables` from hammering the shared throttle — cache + dedupe so it fires at most
once per module per TTL, instead of 1 request/module on every full page load.

## Root cause (verified)
`carbon-frontend/src/auth/AuthContext.jsx:318-350` `refetchTables`:
- Fires 1 `apiFetch(API_ROUTES.tables, …)` **per module** on every full page load (invoked from
  the effect at line 190 and `TableManagerPage.jsx:191,211,229`).
- No cache, no in-flight dedupe.
- Backend `DEFAULT_THROTTLE_RATES.user = '1000/hour'` (settings.py:304) is **shared across all
  endpoints**, so ~15–20 page loads exhausts it → ~30 min 429 lockout.

## Files to Change
- `carbon-frontend/src/auth/AuthContext.jsx` — MODIFY `refetchTables`: add module-level TTL
  cache + in-flight dedupe.
- `carbon-frontend/src/__tests__/AuthContext.refetchTables.test.jsx` — ADD (or extend existing).

## Tasks
1. **In-flight dedupe**: keep a module-level `let tablesInFlight = null;` promise. Concurrent
   callers share one promise instead of stacking requests.
2. **TTL cache**: cache `{ [moduleId]: { rows, ts } }`; a `refetchTables({ force = false })`
   short-circuits to the cache when `Date.now() - ts < TTL` (TTL ~60s). `force: true` bypasses
   the cache (used after a table create/edit in `TableManagerPage.jsx`).
3. Update the three `TableManagerPage.jsx` call sites (191/211/229) to pass `{ force: true }`
   where a refresh is genuinely required after a mutation, and leave the plain call cached
   elsewhere.
4. Test: two rapid calls share one fetch (mock `apiFetch`); a cached call within TTL issues no
   fetch; `force: true` always fetches.

## DO NOT TOUCH
- Backend throttle settings (a scoped `tables` throttle rate is a **separate** follow-up; this
  task is frontend-only).
- Other `apiFetch` consumers.

## Verification Gate
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npm run lint
npx vitest run src/__tests__/AuthContext.refetchTables.test.jsx
npm run build
```

## Hard rules
- `apiFetch` only (RULE_10). No raw fetch.

## Output contract
Append an `R4` section to `TASK-RESULTS.md`.

## Notes for the Master
- Acceptance: reload the workspace 3× and confirm the tables endpoint is hit once (not once per
  module ×3), and `force` refresh still works after a table mutation.
