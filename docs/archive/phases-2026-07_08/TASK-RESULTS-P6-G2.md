# TASK-RESULTS-P6-G2.md — Phase 6 · G2: Frontend Test Scaffolding (COMPLETE)
# Master Architect ← Frontend Worker | Date: 2026-07-31
# Result: ✅ Vitest + Testing Library scaffolded (4 config files, 3 test files, 7 tests), ALL 3 gates passed

---

## Summary

Executed **Phase 6-G2** per `TASKS-P6.md`: installed Vitest + Testing Library, created the test
config stack (`vitest.config.js`, `src/setupTests.js`, `package.json` scripts), and added **3 smoke
test files** (7 tests total): `NotFound.test.jsx` (3), `PlatformHome.test.jsx` (2), `api.test.js` (2).

**Result**: `npx vitest run` → **7 passed / 0 failed** · `npm run build` → ✓ clean · `npm run lint` →
**exactly baseline** (6 errors / 58 warnings — all 6 errors are pre-existing DO-NOT-TOUCH
`src/api/api.js`).

| Gate | Command | Expected | Actual |
|---|---|---|---|
| 1 | `npx vitest run` | 7+ tests, 0 failures | **7/7 passed** (3 files) |
| 2 | `npm run build` | ✓ built, no new errors | ✓ built in 28.00s, no new errors (pre-existing chunk-size warning only) |
| 3 | `npm run lint` | No new lint problems vs baseline | ✅ exactly baseline: 6 errors / 58 warnings |

---

## Task Results

| # | Task | Status | Result |
|---|---|---|---|
| 1 | Install test deps | ✅ | `npm install -D vitest @testing-library/react @testing-library/jest-dom @testing-library/user-event jsdom` → added 82 packages (vitest 4.1.10) |
| 2 | Create `vitest.config.js` | ✅ | Exact spec code: `defineConfig` + `react()` plugin + `test: { globals, jsdom, setupFiles, css:false }` |
| 3 | Create `src/setupTests.js` | ✅ | `import '@testing-library/jest-dom/vitest';` |
| 4 | Modify `package.json` scripts | ✅ | Added `"test": "vitest run"`, `"test:watch": "vitest"` — **only** scripts key touched |
| 5 | Create `src/__tests__/NotFound.test.jsx` | ✅ | 3 tests (404 heading / "Page Not Found" / "Go Home" → `/`) — spec code verbatim |
| 6 | Create `src/__tests__/PlatformHome.test.jsx` | ✅ | 2 tests (page title / renders with empty apps) — 2 spec fixes applied (see Deviations) |
| 7 | Create `src/__tests__/api.test.js` | ✅ | 2 tests (`apiFetch` + `fetchEmissionsDashboard` are functions) — dynamic `import()` per spec |

### Test-by-test results

| Test | Result |
|---|---|
| `NotFound > renders 404 heading` | ✅ |
| `NotFound > renders "Page Not Found" message` | ✅ |
| `NotFound > has a "Go Home" link pointing to /` | ✅ |
| `PlatformHome > renders the page title` | ✅ (heading-scoped query — see Deviations) |
| `PlatformHome > renders without crashing when apps list is empty` | ✅ |
| `apiFetch > api module exports apiFetch` | ✅ |
| `emissions API > fetchEmissionsDashboard exports a function` | ✅ |

---

## Files Created / Modified

| File | Action | Notes |
|---|---|---|
| `carbon-frontend/vitest.config.js` | CREATE | Spec verbatim |
| `carbon-frontend/src/setupTests.js` | CREATE | Spec verbatim |
| `carbon-frontend/src/__tests__/NotFound.test.jsx` | CREATE | Spec verbatim |
| `carbon-frontend/src/__tests__/PlatformHome.test.jsx` | CREATE | 2 spec fixes (below) |
| `carbon-frontend/src/__tests__/api.test.js` | CREATE | `vi` import removed (unused) |
| `carbon-frontend/package.json` | MODIFY | `"scripts"` only: +`test`, +`test:watch` |

**DO-NOT-TOUCH respected**: no existing source file, theme file, page component, API file, or
eslint config was modified.

---

## Deviations from Spec (3 — all required to make the tests actually pass)

1. **`PlatformHome.test.jsx` — `useEnabledApps` mock**: spec mock returned only
   `{ apps: [], loading: false, error: null }`, but `PlatformHome` destructures and calls
   `isAppEnabled(app.id)` in its filter → would throw `TypeError: isAppEnabled is not a function`.
   Added `isAppEnabled: () => true` (matches real hook's default "not loaded → show all" behavior).
2. **`PlatformHome.test.jsx` — page-title query**: spec's `getByText(/platform/i)` matches **two**
   elements ("Carbon Data Trust **Platform**" heading AND "Trusted data **platform** hosting…"
   subtitle) → `TestingLibraryElementError: Found multiple elements`. Changed to
   `getByRole('heading', { name: /platform/i })` — same intent (page title), unambiguous.
3. **`api.test.js` — unused `vi` import**: spec imported `vi` but neither test uses it → lint
   error `no-unused-vars` (would add a 7th lint error). Removed `vi` from import.

No other deviations. No raw px/hex introduced (HARD RULE respected — no styling in test files).
No duplicated components (HARD RULE respected — tests render real `NotFound`/`PlatformHome`
with mocked hooks only).

---

## Verification Output

### Gate 1 — `npx vitest run` (after fixes)

```
Test Files  3 passed (3)
     Tests  7 passed (7)
```

### Gate 2 — `npm run build`

```
✓ 12571 modules transformed.
dist/assets/index-DPm43Ou9.js  2,084.55 kB │ gzip: 609.65 kB
(!) Some chunks are larger than 500 kB ...   [pre-existing, not new]
✓ built in 28.00s
```

### Gate 3 — `npm run lint`

```
✖ 64 problems (6 errors, 58 warnings)   [= exact baseline]
```
All 6 errors are pre-existing in `src/api/api.js` (DO-NOT-TOUCH: `buildQuery` L12, `e` L68/79/224,
`process` L214, `refreshError` L274). Zero new lint problems from the 5 new test/config files.

---

## Notes for Later Phases

- `vitest.config.js` and `vite.config.js` coexist — `vite build` unaffected (28.00s, same output).
- Tests use `MemoryRouter` + `vi.mock()` — no backend required; run via `npm test` / `npm run test:watch`.
- React Router v6 prints future-flag warnings in test output (informational, non-failing).
- `npm audit` reports 13 vulnerabilities in the dependency tree — pre-existing scope, not addressed
  here (out of task scope).
