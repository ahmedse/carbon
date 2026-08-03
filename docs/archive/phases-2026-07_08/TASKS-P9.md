# TASKS-P9: Deep Web Simulations — Role Coverage, Bug Fixes & UX Testing

**Date:** 2026-07-31
**Author:** Ahmed (via GitHub Copilot)
**Session:** P9 Deep Track — Row Detail, Data Entry, RBAC hardening, Dark Mode, Search/Filter, Error States
**Related:** P7 (4 RBAC bugs), P8 (4 RBAC bugs), P9 (3 bugs)

---

## Objective
Go deeper in web simulations: Row Detail page, Data Entry, token refresh, Calculations, Verification, Analytics, search/filter, dark mode, error states. Full 5-role coverage (admin, dataowner, auditor, viewer, analyst).

---

## Test Matrix

| # | Test | admin1 | dataowner2 | auditor1 | viewer1 | analyst1 | Status |
|---|------|--------|------------|----------|---------|----------|--------|
| 1 | RowDetail (Overview) | ✅ | ✅ | ✅ | ✅ (fixed) | ✅ (fixed) | PASS |
| 2 | RowDetail (Edit tab) | ✅ | ✅ | ✅ | (read-only) | (read-only) | PASS |
| 3 | RowDetail (Evidence tab) | ✅ | ✅ | ✅ | ✅ | ✅ | PASS |
| 4 | Data Entry Tool | ✅ | ✅ | ✅ | (read-only) | (read-only) | PASS |
| 5 | Calculations page | ✅ | ✅ | N/A | N/A | N/A | PASS |
| 6 | Verification page | ✅ | ✅ | ✅ | N/A | N/A | PASS |
| 7 | Analytics & Trends | ✅ | N/A | N/A | N/A | ✅ | PASS |
| 8 | Token refresh | ✅ | ✅ | ✅ | ✅ | ✅ | PASS* |
| 9 | Dark mode toggle | ✅ | ✅ | ✅ | ✅ | ✅ | PASS |
| 10 | Search/Filter (My Data) | ✅ | ✅ | ✅ | ✅ | ✅ | PASS |
| 11 | Error 404 page | ✅ | ✅ | ✅ | ✅ | ✅ | PASS |
| 12 | Write-protection (PATCH) | — | — | — | 403 ✅ | 403 ✅ | PASS |

\* Token refresh: intentional corruption → 401 → `globalLogout()`. Expected behavior.

---

## Bugs Found & Fixed (3)

### Bug #1: RowDetailPage 403 for viewer/analyst roles
- **Symptom:** `DataRowViewSet.retrieve()` returned 403 for viewer1 and analyst1
- **Root cause:** `retrieve()` only checked admin/write roles via `get_allowed_module_ids()`, not visibility roles
- **File:** `backend/dataschema/views.py`
- **Fix:** 
  1. Added `VISIBILITY_ROLES` and `ScopedRole` imports
  2. `retrieve()` now checks `ScopedRole.objects.filter(group__name__in=VISIBILITY_ROLES)` for global visibility first
  3. Expanded `get_allowed_module_ids` roles list to include `viewers_group`, `analysts_group`
- **Status:** ✅ Fixed & verified

### Bug #2: RowDetailPage JSON/Response mismatch
- **Symptom:** "Failed to fetch row: undefined" on RowDetailPage load
- **Root cause:** `apiFetch` already parses JSON response, returns plain data object (not `Response`). `fetchRowData` and `handleRefresh` treated the return value as a `Response` object calling `response.json()`.
- **File:** `carbon-frontend/src/pages/dataschema/RowDetailPage.jsx`
- **Fix:** Changed from `const response = await apiFetch(...); setRowData(await response.json())` to `const rowData = await apiFetch(...); setRowData(rowData)`
- **Status:** ✅ Fixed & verified
- **Risk:** Many pages may have the same pattern. Proactive audit recommended.

### Bug #3: HasScopedRole allowing writes for read-only roles
- **Symptom:** viewer1 could PATCH data row values despite having only `viewers_group`
- **Root cause:** `HasScopedRole.has_permission()` allowed any matching role to write
- **File:** `backend/accounts/permissions.py`
- **Fix:**
  1. Added `READ_ONLY_ROLES = {"viewers_group", "analysts_group"}`
  2. In `has_permission()`: for non-safe methods, check if user's roles intersect with `READ_ONLY_ROLES`. If the intersection is the ONLY match (no write roles), block the request.
  3. Also checks `ScopedRole` for write role at module level
- **Status:** ✅ Fixed & verified (PATCH → 403, GET → 200)

---

## Files Modified

| File | Change |
|------|--------|
| `backend/dataschema/views.py` | Added VISIBILITY_ROLES import; retrieve() checks global visibility roles |
| `carbon-frontend/src/pages/dataschema/RowDetailPage.jsx` | Fixed apiFetch JSON/Response mismatch |
| `backend/accounts/permissions.py` | Added READ_ONLY_ROLES + write-blocking logic in HasScopedRole |

---

## Key Lessons

1. **apiFetch pattern is fragile** — `apiFetch` returns parsed JSON, not `Response`. Many pages may have the same bug as RowDetailPage. Audit all callers.
2. **HasScopedRole write-permission hardening** — The fix in Bug #3 should be validated across ALL viewsets using this permission class. The write-check is now universal for any viewset using `HasScopedRole`.
3. **Visibility roles are separate from write roles** — VISIBILITY_ROLES allow reading but not writing. This distinction needs to be maintained in every view method.
4. **Token refresh corruption** — Intentional token corruption → 401 → `globalLogout()`. This is correct behavior; the app cannot decode a corrupted JWT.

---

## Completion Status

- [x] Deep Track 1a-e: RowDetail bugs found & fixed
- [x] Deep Track 2: Token refresh tested
- [x] Deep Track 3-4: Calculations, Verification, Analytics pages verified
- [x] Deep Track 5a: Dark mode toggled
- [x] Deep Track 5b: Search/filter on My Data tested
- [x] Deep Track 5c: Error states tested (404 page)
- [x] All 3 bug fixes verified via API and browser

**P9 COMPLETE** ✅
