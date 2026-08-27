# TASK-RESULTS-19-CONTEXTUAL-INSPECTOR-CALCULATIONS — Frontend Worker Report

Date: 2026-08-27 · Role: Frontend Worker · Model: DeepSeek V4 Pro · Phase: ADR-0019 Phase C (final page) · Area: `carbon-frontend/` only

---

## Executive Summary

**Verdict: PASS** — the last deferred ADR-0019 page (`CalculationsPage.jsx`, entityType `calculation`) is migrated off its custom inline right panel onto the centralized Contextual Inspector drawer. This completes the ADR-0019 migration across all 14 pages.

**Scope (this task):**
1. Lift the page's inline `OverviewTab` / `DataQualityTab` into a self-contained context-driven registry contribution module (`calculationTabs.jsx`).
2. Migrate `CalculationsPage.jsx` to the canonical drawer pattern (`useNotes` + `registerCalculationInspectorTabs` + memoized `inspectorContext` → `setContexts`).
3. Relocate the per-row "Recalculate" action into a DataGrid **Actions** column (was embedded in the deleted 360px panel).
4. Regression test + full verification gate + registry regen.

---

## Files Changed

| File | Change |
|------|--------|
| `carbon-frontend/src/inspector/tabs/calculationTabs.jsx` | **CREATED** — `registerCalculationInspectorTabs()` registers `calculation-overview` (order 10) + `calculation-quality` (order 20), both `matches: ctx => ctx.entityType === 'calculation'`. Re-exports `STATUS_CFG` / `ScopeBadge` / `StatusChip` / `fmtDate` / `fmtNum` as single source of truth for the page DataGrid. |
| `carbon-frontend/src/pages/carbon/CalculationsPage.jsx` | **MIGRATED** — removed 360px inline panel + `detailTab`/`detailLoading` state; added `useNotes().setContexts` wiring + `registerCalculationInspectorTabs()` effect; added conditional Actions column (Recalculate, admin-only) with a `<span>` wrapper so MUI `Tooltip` doesn't warn when the button is disabled. |
| `carbon-frontend/src/inspector/tabs/helpers.jsx` | **FIXED** — `registerEntityInspectorTab` destructured `Component` in the parameter list (treated as an unused "arg" by `no-unused-vars`, which has no `jsx-uses-vars` since `eslint-plugin-react` isn't installed). Moved destructure into the body so `Component` is a var matching `varsIgnorePattern: '^[A-Z_]'`. Resolves the 1 blocking lint **error**. |
| `carbon-frontend/src/__tests__/calculationTabs.test.jsx` | **CREATED** — 6 regression tests: registration + unregister, `matches` filtering, ordering, Overview loaded/empty states, Data Quality loaded/empty states. |

---

## Verification (terminal proof)

### Regression test (new)
```bash
cd carbon-frontend && npx vitest run src/__tests__/calculationTabs.test.jsx
# Test Files  1 passed (1)   Tests  6 passed (6)
```

### Full frontend suite
```bash
npx vitest run
# Test Files  81 passed (81)   Tests  901 passed (901)
```

### Lint
```bash
npx eslint src/inspector/tabs/helpers.jsx src/inspector/tabs/calculationTabs.jsx src/pages/carbon/CalculationsPage.jsx
# 0 errors (1 pre-existing react-refresh warning, documented debt)
```

### Verify gate (frontend)
```bash
./.ai-toolkit/scripts/verify.sh frontend
# ✓ lint   ✓ build   ✓ route audit clean (81 paths, 17 namespace roots)   → GATE PASSED
```

### Registry regenerated
```bash
./.ai-toolkit/scripts/scan.sh
# ✓ registry/api.md services.md models.md components.md config-keys.md README.md
```

### Browser verification (live)
`/carbon/calculations` (admin): legacy 360px panel gone; drawer shows **Notes / Overview / Data Quality** tabs + context chip "Calculation". Overview renders the full 11-row `Calculation Metadata` block; Data Quality renders the DQ section (empty-state copy for the selected Draft run, which has no DQ scores — correct).

---

## Issues / Deviations

| Severity | Item | Resolution |
|----------|------|------------|
| P0/P1/P2/P3 | none introduced | — |
| Pre-existing | 2 backend test failures in `verify.sh full` — `test_maturity_empty_db_is_novice_with_zero_score` + `test_rollups_totals_and_per_run_shape` | Unrelated to this frontend-only change; the observability rollups failure is already documented as known order-dependent debt in `TASK-RESULTS-16-FLIGHT-DIRECTOR.md`. |
| Pre-existing | `verify.sh antipatterns` warnings (raw `fetch()` in export/AITaskPanel/ForgotPassword, `datetime.now()` in catalog_service/export_document, 28 `print()` in backend) | Pre-existing debt, out of frontend scope. |
| Documented debt | `/* eslint-disable react-refresh/only-export-components */` in `calculationTabs.jsx` + `react-refresh` warning in `helpers.jsx` | Accepted trade-off for registry contribution modules (mixes component + non-component exports). Flagged per base-rules §0. |
| Out of scope | Per-row Recalculate is gated behind the page's `isAdmin` flag, which is not true for the current superuser session, so the Actions column doesn't render for `ahmed` | Pre-existing gating, unchanged by this migration. Flagged for separate fix if desired. |

---

## Definition of Done (self-check)

- [x] Correct — does exactly the task, follows design-system tokens + reuse rules.
- [x] Reuses — `InspectorTabRegistry`/`registerInspectorTab`/`helpers.jsx` reused; no duplication.
- [x] Verified — `verify.sh frontend` GATE PASSED (lint + build + routes).
- [x] Tested — new regression test; full 901-test suite green.
- [x] Safe — no secrets, no naive datetimes, no new `print()`, no raw `fetch()` in this change.
- [x] Clean — no debug leftovers.
- [x] Captured — registry regenerated; ADR-0019 already exists; this results file.
