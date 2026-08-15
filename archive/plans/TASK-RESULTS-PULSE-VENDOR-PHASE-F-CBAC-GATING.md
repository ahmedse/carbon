# TASK RESULTS — PULSE VENDOR PHASE F: CBAC Capability-Gating on the AI Admin Read Surface

**Status:** ✅ COMPLETE (all gates green)
**Spec:** `plans/TASKS-PULSE-VENDOR-PHASE-F-CBAC-GATING.md`

---

## What Changed

### Backend — capability (CBAC single source of truth)

- `backend/accounts/capabilities.py`
  - Added `AI_VIEW_CONSOLE` (`ai:view_console`, domain `ai`, action `view_console`, category `admin`).
  - Registered it in `ALL_CAPABILITIES`. No `IMPLIES` or `GROUP_CAPABILITIES` change —
    global admins (`admin`/`admins_group` → `{"*"}`) and superusers already get it automatically.

### Backend — permission gating (all 10 Pulse read views)

Each view switched from `IsAuthenticated` to `AdminOrSuperuserOnly` + `required_capability = "ai:view_console"`:

| File | Views gated |
|------|-------------|
| `ai/ops_api.py` | `PulseHealthView`, `PulseModulesView`, `PulseTaskStatusView` |
| `ai/observability_api.py` | `PulseInventoryView`, `PulseDataView`, `PulseArchetypesView` |
| `ai/graph_api.py` | `GraphDataView` |
| `ai/activation_api.py` | `PulseUsageView`, `PulseSettingsView` |
| `ai/sweeps_api.py` | `SweepsStatusView` |

### Backend — visibility/scope filter

- New `backend/accounts/ai_scoping.py` → `scope_ai_queryset(qs, user)`:
  - filters `app_identifier="carbon"`;
  - bypasses for superuser/global admin (matches `_check_write_capability` steps 1–2);
  - otherwise filters `visibility` (global|shared, or own private) + allowed org subtree
    (null-org rows if no admin org role).
- Applied at the query boundary in the 5 model-backed read paths:
  - `PulseInventoryView` (per-model `.count()`)
  - `PulseDataView` (per-model `.objects` before ordering/slicing)
  - `GraphDataView` (all four node/edge querysets: KnowledgeNode, KgNode, KnowledgeEdge, KgEdge)
  - `PulseUsageView` (single scoped `LLMCallLog` base reused for today/total/by_model/by_day)
  - `SweepsStatusView` (`CognitionSweepRun.objects` before ordering)
- **Purity preserved:** no `accounts` import added to `ai/models/*`, `ai/store.py`, or
  `ai/engine/*` (grep-verified — only the pre-existing docstring mentions "accounts").

### Frontend — mirror + gating

- `carbon-frontend/src/capabilities.js`
  - Added `AI_VIEW_CONSOLE = 'ai:view_console'`.
  - Added `'/admin/ai': AI_VIEW_CONSOLE` to `ROUTE_CAPABILITIES` (prefix-matched for all
    `/admin/ai/*` paths by `authz.js` `access_route`/`view_page`).
- `carbon-frontend/src/App.jsx`
  - Imported `AI_VIEW_CONSOLE`.
  - Added `requiredCapability={AI_VIEW_CONSOLE}` to all 19 `/admin/ai/*` `<AdminRoute>` wrappers.
- `carbon-frontend/src/shell/useShellState.js`
  - `ai-admin` studio gate now additive: `isGlobalAdmin(...) || hasCap(expandCapabilities(...), AI_VIEW_CONSOLE)`.
- `carbon-frontend/src/__tests__/cbac.test.jsx`
  - Updated the "admin routes require platform capabilities" test to carve out `/admin/ai`
    (asserts `ai:view_console` instead of `platform:*`).

### Backend — tests

- Updated the `user` fixture in 5 files to a **superuser** (bypasses the gate), keeping the
  existing anonymous-401 assertions valid:
  `test_ops_api.py`, `test_observability_api.py`, `test_graph_api.py`,
  `test_activation_api.py`, `test_cognition_scheduler.py`.
- Added `ai/tests/test_cbac_gating.py` (6 tests):
  - plain user → 403 on all 10 paths (sampled),
  - superuser → 200,
  - global admin (`admins_group` @ org=None) → 200,
  - `scope_ai_queryset` hides other users' private rows,
  - `scope_ai_queryset` global admin sees all,
  - `scope_ai_queryset` plain user sees only null-org (shared) rows.

---

## Gate Results

| Gate | Result |
|------|--------|
| `manage.py check` | ✅ no issues |
| `manage.py makemigrations --check` | ✅ "No changes detected" |
| `pytest ai/tests -q` | ✅ 156 passed (150 baseline + 6 new) |
| `pytest ai/tests dq/tests -q` | ✅ 403 passed |
| `npm run build` | ✅ built (13.55s) |
| `npm test` | ✅ 322 passed |
| `verify.sh antipatterns` | ✅ GATE PASSED (only pre-existing warnings) |

---

## Notes

- No new groups/roles were required — global admins and superusers already hold
  `ai:view_console` via the existing `{"*"}` wildcard; the permission + scope filters are
  now in place so a future `ai_lead` group can be added with zero code change.
- No model changes → no migrations.
- Not committed (Master does not `git add -A`; user commits).
