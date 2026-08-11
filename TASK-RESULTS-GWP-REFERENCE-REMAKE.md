# TASK-RESULT — GWP Reference Total Remake (AI-Toolkit Compliance)

**Date:** 2026-08-11
**Role:** Frontend Worker
**Scope:** `carbon-frontend/src/pages/emissions/GWPReferencePage.jsx` only (no backend edits)
**Task:** "audit and total remake to follow AI toolkit: GWP Reference" (http://localhost:5179/carbon/carbon/admin/gwp)

---

## 1. Audit Findings (OLD page)

| # | Violation | Severity |
|---|-----------|----------|
| 1 | **Admin gate broken**: `isAdmin = user?.is_superuser || user?.groups?.includes('admins_group')` — ALWAYS false for the actual user object → **"New GWP" button and Actions column never rendered** (CB-13 violation) | CRITICAL |
| 2 | MUI `Table` + `TableContainer` — not using `FilteredDataGrid` list shell (CB-15) | High |
| 3 | `GwpDrawer` — Drawer-based form (CB-14 violation, design system mandates SystemDialog) | High |
| 4 | Raw `Dialog` for delete confirmation — not `ConfirmDialog` | Medium |
| 5 | Manual `Snackbar` state — not `useNotification` | Medium |
| 6 | `fmtGwp` used `minimumFractionDigits: 1` → rows showed "1.0", "3,170.0" | Low |
| 7 | No search / no empty-state in grid shell | Medium |
| 8 | `loadData` defined after `useEffect(() => { loadData(); }, [])` + no defensive `Array.isArray` (CB-09) | Medium |

## 2. Remake — What Changed

- **Admin gate**: `const isAdmin = can(user, 'manage', 'carbon', { perspectives, isGlobalAdminFlag, capabilities, modules: context?.modules || [] })` — same gate as AdminRoute (CB-13). ✅
- **Shell**: `FilteredDataGrid` (title "GWP Reference", subtitle "N of M gases", description, countLabel, actions=New GWP button when isAdmin, search-only `filterDefs={[]}`, emptyMessage, loading, onSearchChange/onClearFilters).
- **Form**: `GwpDialog` on `SystemDialog` (width 520 / height 600 / minWidth 420 / minHeight 460; Gas Name + Formula, then two row-Stacks for AR5/AR6 100yr and AR5/AR6 20yr, CAS, Notes; actions = Create/Update Button size=small). (CB-14) ✅
- **Delete**: `ConfirmDialog` destructive (message: "This action cannot be undone. Calculations using this gas may be affected."). ✅
- **Notifications**: `useNotification` (`notify` success on create/update/delete; `notifyFromError` on failures). ✅
- **Numbers**: `fmtNum(v)` — null/'' → "—", else toLocaleString maxFractionDigits 2 (GWP model is decimal_places=2; display strips trailing zeros). ✅
- **Data**: `loadData` as `useCallback` with `Array.isArray(data) ? data : data?.results || []`, catch resets `setGwpValues([])`; `useEffect(() => { loadData(); }, [loadData])`. ✅
- **9 DataGrid columns**: Gas Name (flex 1, min 170), Formula (110), AR5 100yr / AR6 100yr / AR5 20yr / AR6 20yr (105, right-aligned, valueFormatter fmtNum), CAS # (130), Notes (220), Actions (100, isAdmin-only: EditIcon → handleEdit, DeleteIcon error.main → ConfirmDialog).

## 3. Verification Gate Results

| Check | Result |
|-------|--------|
| `npm run lint` | ✅ **0 errors**; GWP page: **0 warnings** (filtered output clean) |
| `npm run build` | ✅ `✓ built in 16.64s` (chunk-size warnings pre-existing, not errors) |
| MUI v6 Grid syntax grep (`\bitem\b.*xs=`, `<Grid item`) | ✅ 0 hits |
| Leftover symbol grep (RefreshIcon/InboxIcon/Snackbar/drawerOpen/fmtGwp/GwpDrawer/TableContainer/is_superuser/admins_group) | ✅ 0 hits (only a CB-13 comment) |
| **Browser** — "New GWP" button visible | ✅ **RENDERS** (can() gate fixed — the critical bug is confirmed resolved) |
| **Browser** — DataGrid headers render (Gas Name, AR5 100yr, AR6 100yr, AR5 20yr, AR6 20yr, CAS #, Notes) | ✅ |
| **Browser** — "New GWP" click → SystemDialog opens with all 8 fields + Create/Cancel | ✅ |
| **Browser** — live data rows / edit / delete | ⚠️ **BLOCKED** — backend down (see §4) |

## 4. Blocker (NOT frontend scope)

Backend fails to start — Django `ImportError`:

```
backend/dq/urls.py, line 4: cannot import name 'DQJobViewSet' from 'dq.views'
```

- `backend/dq/urls.py` (modified, unstaged) imports `DQJobViewSet` and registers `router.register(r'jobs', DQJobViewSet, ...)`.
- `DQJobViewSet` is defined **nowhere** — not in `dq/views.py`, not in untracked `dq/jobs.py`, not in staged `views.py`.
- The `dq` app has extensive **uncommitted WIP from another agent** (DQ jobs Phase 3/4: `jobs.py`, migrations 0013–0015, `test_phase3_jobs.py`, `test_phase4_pulse.py`).
- **Frontend worker did not touch backend.** Backend was running earlier today (PID 173960 :8009) — this breakage landed after, from the parallel backend work.

**Recommendation:** backend worker must define `DQJobViewSet` (or wire `jobs.py`) and unstage/complete the WIP before `./manage.sh start` works again. Once backend is up, GWP data rows + edit/delete actions can be re-verified in-browser (CB-17: hard-reload frontend if stale).
