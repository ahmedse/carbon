# TASK-RESULTS-E2-F1 — Verification UI Repair

**Role:** Frontend Worker
**Date:** 2026-08-03
**Status:** ✅ COMPLETE

---

## Gates

| Gate | Result |
|------|--------|
| `npm run lint` | ✅ 0 errors, 0 warnings in changed files |
| MUI Grid check | ✅ 0 legacy Grid syntax matches |
| `npm run build` | ✅ Built in 10.36s |

---

## Changes Made

### 1. `src/api/emissions-extended.js` — API layer fixed

**Removed:**
- `verifyPeriod(periodId, data, token)` — was hitting wrong endpoint
- `rejectPeriod(periodId, data, token)` — was hitting wrong endpoint

**Added:**
- `verifyVerificationRecord(verificationId, token)` → `POST /carbon-api/carbon/verifications/{id}/verify/`
- `rejectVerificationRecord(verificationId, notes, token)` → `POST /carbon-api/carbon/verifications/{id}/reject/`
- `openPeriod(periodId, token)` → `POST /carbon-api/carbon/periods/{id}/open/`
- `lockPeriod(periodId, token)` → `POST /carbon-api/carbon/periods/{id}/lock/`
- `closePeriod(periodId, token)` → `POST /carbon-api/carbon/periods/{id}/close/`

**Repointed:**
- `submitPeriod(periodId, token)` → `POST /carbon-api/carbon/periods/{id}/submit/` (was hitting wrong endpoint)

### 2. `src/pages/carbon/VerificationPage.jsx` — Columns + actions updated

- **Columns** now match `VerificationRecordSerializer` fields:
  - `period_label` (computed: "FY 2024 (2024-01-01 – 2024-12-31)")
  - `period_status` (Chip with state-machine colors)
  - `total_co2e_tonnes` (formatted number)
  - `scope_summary` (rendered as compact Scope chips: `S1: 12.5`, `S2: 8.3`)
  - `verifier_name` (from `verifier.username`)
  - `created_at` (formatted date)
  - `verified_at` (shown on non-pending tabs)
  - `notes` (shown on pending tab)
  - Actions column (approve/reject on pending tab)

- **Approve dialog** uses `record.id` → `verifyVerificationRecord(record.id, token)`
- **Reject dialog** uses `record.id` → `rejectVerificationRecord(record.id, notes, token)`
- Both dialogs use `record.period_label` for display text
- After action: `loadRecords()` refreshes the grid
- Fixed `useMemo` dependency array (removed redundant `activeTab` — only `isPendingTab` needed)

### 3. `src/pages/emissions/ReportingPeriodsPage.jsx` — State-machine rewrite

**Before:** Raw status dropdown for editing + edit/delete buttons only.

**After:**
- **Status column**: Read-only `Chip` using `STATUS_CFG` color mapping:
  - `draft` → `default` (grey)
  - `open` → `info` (blue)
  - `locked` → `warning` (orange)
  - `submitted` → `secondary` (purple)
  - `verified` → `success` (green)
  - `rejected` → `error` (red)
  - `closed` → `default` (grey)

- **Transitions column**: Action icon buttons based on `VALID_TRANSITIONS`:
  - draft → "Open" button (all users)
  - open → "Lock" button (admin only)
  - locked → "Submit" + "Open" buttons
  - submitted → "Verify" + "Reject" buttons (admin only, points to Verification workflow)
  - rejected → "Submit" button
  - verified → "Close" button (admin only)
  - closed → "Terminal" text (no actions)

- **Admin gating**: `lock`, `close`, `verified`, `rejected` transitions hidden from non-admin users via `canManageAllModules()`

- **Edit dialog**: Status field is now a read-only Chip when editing (managed by state machine). When creating, only `draft` and `open` are available as starting states.

- **Snackbar feedback** on all transitions

- **Loading state** with spinner instead of plain text

---

## Design System Compliance

- ✅ All colors via `theme.palette` (no hex)
- ✅ Spacing via `Stack`/`Box` gap props (no per-child margins)
- ✅ MUI Grid v6 syntax (checked — 0 legacy matches)
- ✅ Status shown as Chip with label + color (not color alone)
- ✅ 4 data states handled (loading spinner, error alert, empty state, loaded table)
- ✅ `apiFetch` wrapper used for all API calls (no raw `fetch()`)
- ✅ `canManageAllModules()` from AuthContext for permission gating

---

## Backend Endpoint Alignment

| Frontend Function | Backend Endpoint | Method |
|-------------------|------------------|--------|
| `verifyVerificationRecord(id)` | `/carbon-api/carbon/verifications/{id}/verify/` | POST |
| `rejectVerificationRecord(id, notes)` | `/carbon-api/carbon/verifications/{id}/reject/` | POST |
| `submitPeriod(id)` | `/carbon-api/carbon/periods/{id}/submit/` | POST |
| `openPeriod(id)` | `/carbon-api/carbon/periods/{id}/open/` | POST |
| `lockPeriod(id)` | `/carbon-api/carbon/periods/{id}/lock/` | POST |
| `closePeriod(id)` | `/carbon-api/carbon/periods/{id}/close/` | POST |

---

## Best Practice Notes

- **Verify/Reject from ReportingPeriodsPage**: The `verified` and `rejected` transition buttons in ReportingPeriodsPage now show a helpful error message directing users to use the Verification Workflow page, since verification is done at the `VerificationRecord` level, not the `ReportingPeriod` level.
- **State machine enforcement**: All transitions go through backend `transition_to()` which validates the state machine. Frontend mirrors `VALID_TRANSITIONS` for UI only — backend is authoritative.
