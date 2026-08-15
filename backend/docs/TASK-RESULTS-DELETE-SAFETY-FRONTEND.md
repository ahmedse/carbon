# Sprint 2 — Delete-Safety UX (Frontend Worker) — Results

> **Date**: 2026-08-15
> **Status**: ✅ Complete
> **Scope**: `tasks/SPRINT-2-DELETE-SAFETY.md` §Deliverable 4 (frontend only, §4A–4E)
> **Gates**: `npm run lint` → 0 errors / 53 pre-existing warnings; `npm run build` → ✓ (15.28s)

## Summary

The backend `destroy()` methods referenced by the spec were already implemented (DQ rule,
EmissionFactor, CalculationRule, ExportProject, DataDomain/GlossaryTerm/Tag, ImportJob).
This frontend pass aligned the UI messaging/error-handling with those live response contracts.

**Result per task:**

| § | Task | Status | Notes |
|---|------|--------|-------|
| 4A | DQ Rule delete archive-awareness | ✅ Fixed | Spec referenced nonexistent `DQHubPage.jsx`; real files are `RulesTab.jsx` + `OperationsTab.jsx` |
| 4B | Calculation Rule archive-awareness | ✅ Already satisfied | `CalculationRulesPage.jsx` already branches on `{archived, audit_count}` — no change |
| 4C | Emission Factor `factor_in_use` display | ✅ Enhanced | Already routed via `notifyFromError`; corrected soft-delete wording |
| 4D | Metadata 405 handling | ✅ Fixed | 405 branch was dead code (`err.data` lost by `apiFetch`); fixed |
| 4E | Import job delete | ✅ Already satisfied | No import-job delete button exists in the Import Jobs tab |

## Changes

| File | Action |
|------|--------|
| `src/pages/dq/tabs/RulesTab.jsx` | `confirmDelete()` captures `result` and branches on `result.archived` / `result.results_count` |
| `src/pages/dq/tabs/OperationsTab.jsx` | `handleArchive()` + `handleDelete()` branch on `result.archived` / `result.results_count` |
| `src/pages/emissions/EmissionFactorsPage.jsx` | Success toast "deleted" → "deactivated" (soft delete); dialog retitled "Deactivate Factor?" with accurate message |
| `src/pages/catalog/MetadataManagementPage.jsx` | 405 branch now uses `err.data?.detail \|\| err.message`, closes dialog, falls back to `notifyFromError` |
| `src/api/api.js` | Propagate `err.data` through the catch re-throw (root-cause fix for §4D) |

## Deviations & Findings

1. **Spec filename wrong (§4A).** `carbon-frontend/src/pages/catalog/DQHubPage.jsx` does not
   exist. The actual DQ rule delete lives in `src/pages/dq/tabs/RulesTab.jsx` (list view) and
   `src/pages/dq/tabs/OperationsTab.jsx` (detail view). Both already use `ConfirmDialog`
   (no `window.confirm`), so the "replace window.confirm with MUI Dialog" requirement was
   already satisfied.

2. **§4D "Archive (PATCH is_active)" is not implementable without backend changes.**
   `DataDomain`, `GlossaryTerm`, and `Tag` models have **no `is_active` field** (verified in
   `backend/catalog/models.py`; only `AssetProfile` does). The 405 detail text
   ("use PATCH {is_active: false}") is therefore misleading, but the spec's
   "DO NOT TOUCH" list includes these entities. I implemented the spec's explicitly-allowed
   alternative: display the 405 remediation message as a warning and close the dialog.

3. **`apiFetch` was dropping `err.data`.** The catch block re-threw `finalErr` with
   `feedback`/`status` but not `data`, so `MetadataManagementPage`'s existing
   `err.data.detail` 405 branch never fired. Fixed by propagating `err.data`.

4. **§4C already routed `factor_in_use` to the rich dialog** via `notifyFromError`
   (which shows `reasons` + `remediation` + rule names in `detail`). I kept that path and
   corrected misleading copy ("deleted" → soft-delete "deactivated").

5. **§4B and §4E required no changes** — verified already compliant against the live backend
   contracts (`audit_count` for CalculationRule; no import-job delete affordance exists).

## Backend Contracts Confirmed (read-only, no backend edits)

| Entity | `destroy()` response |
|--------|----------------------|
| DQRule (`dq/views.py`) | results exist → `200 {archived, results_count, detail}`; else `204` |
| CalculationRule (`emissions/views.py`) | audits exist → `200 {archived, audit_count, detail}`; else `204` |
| EmissionFactor (`emissions/views.py`) | in-use → `400 AppFeedback(factor_in_use)` w/ rule names; else soft-delete `204` |
| DataDomain/GlossaryTerm/Tag (`catalog/views.py`) | `405 {detail, resource}` |
| ExportProject (`importexport/views.py`) | jobs exist → `200 {archived, job_count, detail}`; else `204` |
| ImportJob (`importexport/views.py`) | `405` (audit trail) |

## Gate Results

| Gate | Check | Result |
|------|-------|--------|
| G1 | `npm run lint` | ✅ 0 errors, 53 warnings (all pre-existing `react-hooks/exhaustive-deps`) |
| G2 | `npm run build` | ✅ built in 15.28s |
| G3 | No backend files touched | ✅ |
| G4 | No `window.confirm` introduced | ✅ (`ConfirmDialog` used) |
