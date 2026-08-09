# Playbook — Known Issues → Root Cause → Verified Fix

Search before debugging: `grep -i "<symptom>" .ai-toolkit/troubleshooting/playbook.md`
Append a new entry every time you confirm+fix a non-trivial bug (see `shared/debugging.md`).

**Entry format:**
```
### PB-NN — <short symptom>
- Symptom: <what you observe>
- Layer: backend | frontend | data | deploy | infra
- Root cause: <the real cause, confirmed>
- Fix: <the verified fix>
- Best practice note: <the RIGHT long-term fix, if the applied fix was a workaround>
- Regression guard: <test path / verify.sh check / N/A>
- First seen: YYYY-MM-DD
```

> NOTE: Some entries below describe **workarounds for existing tech debt**. Where the
> current codebase forces a workaround, the "Best practice note" states the RIGHT fix.
> Do the right thing — don't treat a workaround as the target design.

---

### PB-01 — Terminal hangs / command never returns
- Symptom: a command (often starting a server) hangs the session indefinitely.
- Layer: infra / dev-env
- Root cause: a background/long-lived process keeps stdin attached to the terminal PTY,
  so the shell never sees a clean command boundary.
- Fix: use the ops script (`./manage.sh start <svc>`) which fully detaches. For ad-hoc:
  `setsid <cmd> </dev/null >/tmp/x.log 2>&1 &` (the `</dev/null` is mandatory).
- Best practice note: services belong in a supervised process manager (systemd / compose),
  not started ad-hoc in an interactive shell.
- Regression guard: base-rules §2/§3; never run `runserver`/`npm run dev` raw.
- First seen: recurring.

### PB-02 — Code "deployed" but production still runs the old behavior
- Symptom: fixed a file, rsynced + restarted, prod unchanged. `grep` for the change in
  the container returns 0.
- Layer: deploy
- Root cause: this project BAKES code into the Docker image at `/app`; bind mounts don't
  cover the code tree, and `docker restart` doesn't re-pull host code.
- Fix (hotfix): `docker cp <hostfile> <container>:/app/<path>` → `docker restart` →
  verify `docker exec ... grep -c <marker> /app/<path>` > 0.
- Best practice note: the RIGHT fix is a CI/CD pipeline that rebuilds+redeploys the image
  on merge. `docker cp` is an emergency hotfix (lost on recreate), not a deploy method.
- Regression guard: deploy checklist in shared/config.md; verify-in-container step.
- First seen: 2026-07-27.

### PB-03 — Dashboard/stale data after source update
- Symptom: updated/deleted source data, dashboard/aggregates still show old values.
- Layer: backend / data
- Root cause: derived/cached copies of data not invalidated when source changes.
- Fix: clear ALL derived copies too, not just the source-of-truth table.
- Best practice note: compute derived values in the write pipeline with a single
  invalidation point, or cache with explicit invalidation.
- Regression guard: integration test asserting reset clears derived fields.
- First seen: recurring.

### PB-04 — API endpoint unexpectedly slow (seconds for a list)
- Symptom: a list/aggregate endpoint takes seconds.
- Layer: backend
- Root cause: `select_related()` pulls JSONField-bearing parent rows that get deserialized
  for every row (or an N+1 query in a loop).
- Fix: `select_related(None)` + `.defer()` the heavy JSON fields; annotate only needed
  values in the DB; verify query count in `./manage.sh shell`.
- Best practice note: measure before optimizing; keep list serializers lean by default.
- Regression guard: shared/data-layer.md query rules; a test asserting query count.
- First seen: recurring.

### PB-05 — Model predictions systematically biased (all high/low)
- Symptom: forecasts consistently above/below actuals during a regime shift.
- Layer: data / ML
- Root cause: online bias correction is a no-op because the active forecaster lacks the
  expected method (guarded by `hasattr`), or the residual window has no backfilled actuals.
- Fix: ensure the forecaster implements the correction hook AND actuals are backfilled for
  the residual window; confirm the correction actually applies (peak delta == expected).
- Best practice note: a capability gated by `hasattr` should fail loud in dev/test, not
  silently no-op. Add an explicit capability check + test.
- Regression guard: unit test: correction ON vs OFF produces the expected delta.
- First seen: 2026-07.

### PB-06 — Naive-datetime / timezone bugs (off-by-hours, flaky time tests)
- Symptom: timestamps off by the UTC offset; tests that pass/fail by time of day.
- Layer: backend / data
- Root cause: `datetime.now()` / `datetime.utcnow()` producing naive datetimes.
- Fix: use `django.utils.timezone.now()`; store UTC-aware; convert at presentation only.
- Best practice note: THIS is the right way regardless of what existing code does — the
  codebase still has naive-datetime debt (verify.sh flags it); fix on touch.
- Regression guard: `verify.sh antipatterns` greps for naive datetime.
- First seen: recurring (existing debt).

### PB-07 — MUI DataGrid crashes: `Cannot read properties of undefined (reading 'size')`
- Symptom: `gridRowSelectionSelector.js:12 Uncaught TypeError: Cannot read properties of undefined (reading 'size')`
- Layer: frontend
- Root cause: `rowSelectionModel` and `onRowSelectionModelChange` are passed to `<DataGrid>` unconditionally, but when `checkboxSelection={false}` the DataGrid does not initialize internal row selection state. The selector then tries to read `.size` on `undefined`.
- Fix: Conditionally spread `rowSelectionModel`/`onRowSelectionModelChange` only when `checkboxSelection` is true:
  ```jsx
  checkboxSelection={isAdmin}
  {...(isAdmin ? {
    rowSelectionModel: selectedRows,
    onRowSelectionModelChange: (ids) => setSelectedRows(ids),
  } : {})}
  ```
- Best practice note: Never pass selection-model props to MUI DataGrid when `checkboxSelection` is false. The grid state machine expects a valid selection object when those props are present.
- Regression guard: N/A (runtime error, not a grep-able pattern)
- First seen: 2026-07-30

### PB-08 — API 404 from frontend: singular vs plural route mismatch
- Symptom: Frontend page 404s with `GET /carbon-api/carbon/verification/` → Django returns "Page not found"
- Layer: frontend / api-config
- Root cause: The frontend config (`src/config.js`) used `carbon/verification/` (singular), but the backend Django router registered the ViewSet as `verifications` (plural). DRF `DefaultRouter` uses the registered basename verbatim.
- Fix: Align the frontend API route with the backend: `"carbon/verifications/"` in `config.js`.
- Best practice note: When a DRF router registers `r'verifications'`, the generated URL prefix is `verifications/`. Always check `urls.py` router registration when debugging frontend 404s.
- Regression guard: N/A (config mismatch, not programmatically detectable without integration test)
- First seen: 2026-07-30

### PB-09 — Duplicate navigation items pointing to same page
- Symptom: Two sidebar menu items ("Data Entry" and "Emission Sources") both navigate to `/carbon/my-data`, confusing users.
- Layer: frontend / navigation
- Root cause: The app manifest declared two distinct menu items for the same page (one with `?tab=sources` query param). Multi-tab pages should have ONE menu entry; tab switching is handled within the page.
- Fix: Remove the redundant menu item. Keep the canonical entry (`Data Entry` → `/carbon/my-data`).
- Best practice note: One page = one menu item. Internal tabs/sub-views are navigated within the page, not via separate sidebar entries.
- Regression guard: N/A
- First seen: 2026-07-30

### PB-10 — AuthZ: "Access denied" despite having capability
- Symptom: User who should have access to a page/app gets denied or sees empty pages.
- Layer: frontend / authz
- Root cause: Capability not present in `me/context` response, or `userCapabilities` stale in localStorage.
- Fix (checklist):
  1. Check `/accounts/me/context/` response — does `capabilities[]` include the needed key?
  2. Check `AuthContext.userCapabilities` in browser console — is it populated?
  3. Verify capability inheritance: if you have `carbon:manage_emission_factors`, you should also get `carbon:view_console`
  4. Hard refresh (Ctrl+Shift+R) if `userCapabilities` is stale in localStorage
- Best practice note: All authz checks go through `can()` in `src/authz.js`. Never write ad-hoc permission checks.
- Regression guard: `src/__tests__/authz.test.jsx` — capability expansion, can() guardrails
- First seen: 2026-08-04

### PB-11 — AuthZ: Menu sections shown with no items
- Symptom: Sidebar shows empty category headers or orphaned divider lines between sections.
- Layer: frontend / navigation
- Root cause: Legacy `filterMenuItems` kept `type: 'group'` and `type: 'divider'` items unconditionally. After stripping inaccessible items, groups could be empty and dividers could be adjacent to nothing.
- Fix: Post-filter cleanup in `ShellSidebar.jsx` prunes empty groups and orphaned dividers.
- Best practice note: If it recurs, check that the group has at least one non-group, non-divider item after filtering.
- Regression guard: visual verification of sidebar with restricted user
- First seen: 2026-08-04

### PB-12 — Browser ERR_CONNECTION_RESET while curl works (stale port forward after Vite restart)
- Symptom: "carbon web not working" — browser page shows `net::ERR_CONNECTION_RESET` on asset loads + WebSocket handshake failure to `ws://localhost:5179/carbon/?token=...`; navigation/reload times out. But `curl http://localhost:5179/carbon/` returns 200 and backend health is OK.
- Layer: infra / dev-environment
- Root cause: Remote workspace port forward. The browser runs on the local client and reaches the dev server through a VS Code port forward. When the Vite dev server was restarted (old PID 373612 stopped, new PID 386139 started), the port forward became stale/wedged: requests to 5179 from the browser were reset, while terminal curl (same host) succeeded. Browser console timestamps predate the current process start time — first clue.
- Fix: `./manage.sh restart frontend` — cleanly restarts Vite, which re-establishes the port forward. Then open a fresh browser page; login redirects to `/carbon/login` (session tokens were lost with the restart), sign in again.
- Best practice note: After ANY frontend restart in a remote workspace, the browser must be reloaded/reopened — do not reuse a pre-restart tab. Verify with a fresh page, not curl alone (curl does not traverse the port forward).
- Regression guard: N/A (infra). Diagnostic checklist: 1) compare process start time vs browser console error timestamps; 2) curl the port from terminal; 3) if curl OK but browser fails → port forward stale → restart service.
- First seen: 2026-08-09

### PB-13 — Phase 2 fields NULL on legacy calculations (scope2_method / emission_factor_snapshot / factor_applied_at)
- Symptom: `Calculation.objects.filter(scope=2, scope2_method__isnull=True).count()` → 362; `emission_factor_snapshot__isnull=True` → all 1993. QA reports BUG-02: Phase 2 GHG Protocol fields unpopulated on existing calculations.
- Layer: data
- Root cause: Rows created by the pre-Phase-2 code path (`Calculation.objects.create()` without Phase 2 kwargs). The fields only populate through `Calculation.create_from_data_row()` / `CalculationRule.calculate_for_row()` — the code path added in migration 0011. Legacy rows never went through it.
- Fix: Non-destructive data migration `emissions/0012_phase2_backfill.py`. For every `Calculation` with a NULL snapshot it: builds the snapshot dict exactly like `calculate_for_row` (`str(ef.factor_value)` — note the decimal_places=10 scale keeps trailing zeros, e.g. `'0.4584000000'`), sets `scope2_method='location_based'` when `scope == 2`, sets `factor_applied_at=calculated_at`, and saves with `update_fields`. Idempotent: filters on `emission_factor_snapshot__isnull=True`.
- Best practice note: Prefer a backfill migration over `setup_carbon_app --recalculate` (recalculate deletes + recomputes rows, rewriting `calculated_by` and destroying the audit trail). Backfill is additive and reversible (noop reverse).
- Regression guard: `backend/emissions/tests/test_phase2_backfill.py` — 4 tests: legacy row starts NULL; backfill populates method+snapshot+applied_at; idempotent on second run; scope-1 rows get snapshot but NOT scope2_method. Assert factor_value against a FRESH DB read (`EmissionFactor.objects.get(pk=...)`) because the in-memory instance holds the pre-rounding Decimal.
- First seen: 2026-08-09

### PB-14 — /mdm/org-units/ exposes full org tree to non-admin users (BUG-03 / F-07)
- Symptom: Data owner `alamein.transport` calls `GET /carbon-api/mdm/org-units/` and receives all 23 org units. Should receive only `النقل — Transportation` (id=5) and its subtree. QA evidence: 8 results for the scoped user.
- Layer: backend / rbac
- Root cause: `OrgUnitViewSet.get_queryset()` filtered only on `is_active=True` + query params — no RBAC scoping. The platform's established visibility helper `get_visible_org_units(user)` (accounts/rbac_utils.py) was already used by `me/context` and emissions services, but the mdm org-units API bypassed it.
- Fix: In `OrgUnitViewSet.get_queryset()`, resolve `visible_ids = {ou.id for ou in get_visible_org_units(user)}`; return `OrgUnit.objects.none()` when empty; otherwise apply the existing select_related/prefetch_related optimizations + `filter(id__in=visible_ids, is_active=True)`. The helper already handles: superusers/global admins → all; global visibility-role holders → all; org-scoped users → assigned subtree expanded to descendants; no roles → [].
- Best practice note: Any endpoint returning OrgUnit rows must scope via `get_visible_org_units(user)` — never a bare `OrgUnit.objects.filter(...)`. `get_object()` inherits scoping automatically (out-of-scope → 404).
- Regression guard: `backend/mdm/tests/test_org_units.py` → `OrgUnitRbacScopingTestCase` (4 tests): data owner sees only own subtree; out-of-scope retrieve → 404; admin sees all; no-role user sees []. List responses are paginated — unwrap `response.data['results']`.
- First seen: 2026-08-09

### PB-15 — Evidence list tests intermittently fail depending on test-run composition (BUG-06)
- Symptom: `manage.py test evidence.tests.test_evidence_api` (alone) → `ERROR: test_soft_deleted_not_in_list` — `TypeError: string indices must be integers, not 'str'` at `[item['id'] for item in resp.data]`. But `manage.py test evidence.tests.test_evidence_api evidence.tests.test_evidence` → OK. QA audit recorded the same tests as "fail intermittently / pass in isolation, fail in suite".
- Layer: tests / pagination interaction
- Root cause: `config/pagination.py::CarbonPageNumberPagination.paginate_queryset` skips pagination when `'pytest' in sys.modules or 'test' in sys.argv[0]`. `manage.py test` never matches `'test' in sys.argv[0]` (argv[0] == "manage.py"), so Django-test runs paginate — UNLESS the pytest-style module `evidence/tests/test_evidence.py` (which does `import pytest`) is part of the same run, which puts `pytest` in `sys.modules` and disables pagination globally. Result: list responses are `{count, page_size, page, results}` dicts or plain lists depending on run composition; `test_soft_deleted_not_in_list` crashed on the dict, and `test_list_evidence`/`test_filter_*` only passed spuriously (`len(dict)` counts keys).
- Fix (test-only, per audit "not a runtime bug"): added `_list_data(resp)` static helper in `EvidenceAPITests` that unwraps `data['results']` when `resp.data` is a dict, and used it in `test_list_evidence`, `test_soft_deleted_not_in_list`, `test_filter_by_data_row`, `test_filter_by_uploaded_by`. file_size/`self.pdf_file` items from the audit were already consistent (content `b'PDF content here'` is 16 bytes; `_fresh_pdf()` used everywhere).
- Best practice: Django API tests that assert on list bodies must be shape-agnostic (`isinstance(data, dict) and 'results' in data`) whenever the global pagination class can be active; do not rely on pytest module imports leaking into `sys.modules`.
- Regression guard: `backend/evidence/tests/test_evidence_api.py` — run module ALONE (`manage.py test evidence.tests.test_evidence_api`) which is the mode that previously failed; 3 consecutive runs GREEN.
- First seen: 2026-08-09 (documented in TASK-RESULT-QA-FULL.md BUG-06)

### PB-16 — Frontend "Failed to fetch dynamically imported module" (Vite lazy route) — transient after dev-server restart/dep re-optimization
- Symptom: React error boundary in `AdminRoute.jsx:24` — `Failed to fetch dynamically imported module: http://localhost:5179/carbon/src/pages/admin/RegisteredAppsPage.jsx`. The page 404s or resets even though the file exists and lints clean. Often preceded/followed by `net::ERR_CONNECTION_RESET` on the initial page load.
- Layer: frontend / dev infra (Vite dev server)
- Root cause: transient — Vite was mid-restart or re-optimizing `node_modules/.vite/deps`, which invalidates module URLs by bumping the `?v=<hash>` cache-buster. The browser's stale module URL (from the previous HMR graph) fails to fetch; the first request after a Vite restart can also hit a dead socket (ERR_CONNECTION_RESET) while curl succeeds (PB-12). Not a code bug: `App.jsx` lazy import path exists, module transforms to valid JS (curl → HTTP 200, ~22KB), route renders.
- Fix: no code change. Hard-refresh the browser tab after the dev server settles; if it recurs, restart the Vite dev server to clear the stale `?v=` module cache.
- Best practice: when triaging "failed to fetch dynamically imported module", verify in order — (1) file exists + lints clean, (2) `curl -s -o /dev/null -w "%{http_code}" <module URL>` returns 200 with valid JS, (3) navigate to the route in a fresh tab. Only if the module 404s/500s persistently is it a real code bug.
- Regression guard: N/A (environmental) — checked live: `/carbon/admin/apps` renders all 7 registered apps after refresh.
- First seen: 2026-08-09
