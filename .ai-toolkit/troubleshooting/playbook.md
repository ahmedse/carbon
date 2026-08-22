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

### PB-17 — OrgUnit write path not RBAC-scoped: scoped data owner can CREATE org units (QA-F3)
- Symptom: scoped user `alamein.transport` (visible orgs = only Transportation) POSTs `/carbon-api/mdm/org-units/` with `parent: 1` (AAST, admin territory) → **HTTP 201 created**. PATCH/DELETE out-of-scope returned 404 (safe) — only CREATE leaked. Docstring on `OrgUnitViewSet` claims "Only admin can write".
- Layer: backend / security (RBAC)
- Root cause: `OrgUnitViewSet` (`backend/mdm/views.py`) declared `permission_classes = [IsAuthenticated]` and had **no write-time admin/scope check** — `perform_create` accepted the client-supplied `parent` FK unchecked. Read scoping worked (`get_queryset` → `get_visible_org_units`), but write authorization was entirely absent.
- Fix: switched `OrgUnitViewSet.permission_classes` to the existing `ReadAnyWriteGlobalAdmin` (`accounts/permissions.py`, already used by `BindFieldView` in the same file) — any authenticated user reads; only superusers or holders of a GLOBAL `admins_group` role (org_unit=None) write. Org-scoped admins become read-only (matches the documented "Only admin can write" contract).
- Design question (for Master): if org-scoped admins should someday write within their own subtree, that needs a new scoped-write permission class — deliberately NOT invented here (reuse over invent; minimal fix).
- Regression guard: `backend/mdm/tests/test_org_units.py::OrgUnitRbacScopingTestCase::test_scoped_user_cannot_create_org_unit` (out-of-scope parent → 403) + `test_scoped_user_cannot_write_in_own_subtree` (in-scope PATCH → 403). Red: 201/200 before fix; green: 403 after. Live: curl as `alamein.transport` → HTTP 403; admin POST → 201.
- First seen: 2026-08-11 (QA-F3, TASK-RESULTS-QA-BUGQUEUE-2026-08-11)

### PB-18 — verify.sh tests never runs tests: empty-string label `ValueError: Empty module name` (QA-F1)
- Symptom: `./.ai-toolkit/scripts/verify.sh tests` → `✗ backend tests` + traceback `ValueError: Empty module name` (Django `import_module('')`). Tests NEVER ran through the gate; `manage.py test ""` reproduces it, `manage.py test` (no args) runs the full suite OK.
- Layer: tooling (verify.sh)
- Root cause: `verify.sh` line `"$PY" manage.py test "${TEST_ARGS:-}"` — with `TEST_ARGS` unset the quoted expansion still passes an **empty-string argument**, which Django's test runner rejects at discovery.
- Fix: guarded the invocation — `if [ -n "${TEST_ARGS:-}" ]; then "$PY" manage.py test $TEST_ARGS; else "$PY" manage.py test; fi` (exit code captured in `rc`, same log-to-/tmp/vt.log + pass/fail structure).
- Regression guard: `verify.sh tests` now prints `✓ backend tests (Ran 274 test)`; negative: `TEST_ARGS=mdm.tests.does_not_exist verify.sh tests` → `✗` + `GATE FAILED` + exit 1.
- First seen: 2026-08-11 (QA-F1)

### PB-19 — verify.sh is a FALSE GREEN: subshell `fail()` never propagates (QA-F2)
- Symptom: `verify.sh tests` printed `✗ backend tests` AND THEN `GATE PASSED` (exit 0). Every prior gate green was untrustworthy — backend/frontend/tests failures were silently masked.
- Layer: tooling (verify.sh)
- Root cause: `verify_backend`, `verify_tests`, `verify_frontend` each ran their checks inside `( cd ... )` **subshells**; the `fail()` helper set `FAIL=1` inside the subshell, which never reaches the parent shell — the final `if [ "$FAIL" -eq 0 ]` always saw 0 → always "GATE PASSED".
- Fix: hoisted the `cd` OUT of the subshells (function does `cd "$BACKEND_DIR"`, runs checks, then `cd "$ROOT"`), so `fail()` sets the parent's `FAIL` directly. Same output format, no rewrite.
- Regression guard: negative self-test — `TEST_ARGS=mdm.tests.does_not_exist verify.sh tests` → `✗` + `GATE FAILED — fix before reporting done` + exit 1 (before: `GATE PASSED` exit 0). Also: `verify.sh full` now honestly reports `GATE FAILED` when pre-existing debt (MUI v5 Grid in DQHubPage.jsx, raw fetch in password pages, 4 print calls) is present.
- First seen: 2026-08-11 (QA-F2)

### PB-20 — Stale dev credentials: alamein.* users' passwords drifted from documented `Alamein_2026` (QA-F4)
- Symptom: QA plan `plans/TASK-QA-ALAMEIN-VALIDATION.md` + `alamein-campus/README.md` + `ALAMEIN_TEST_JOURNEY.md` document `alamein.transport` / `Alamein_2026`; live `POST /carbon-api/token/` → 401 "No active account found" for BOTH documented passwords (`Alamein_2026`, `Transport_123`). `transport.officer` / `Transport_123` (from `seed_aastmt_org.py`) — user doesn't exist in dev DB (seed never run).
- Layer: data / docs (dev environment)
- Root cause: dev users were (re)seeded at some point with different passwords than the plans document; plans were never re-verified against the live DB.
- Fix: reset all 5 existing `alamein.*` users to the documented dev password via shell (`u.set_password('Alamein_2026')`), verified with `u.check_password` AND live `POST /carbon-api/token/` → HTTP 200. Docs now match reality (no doc edit needed). Dev-only credential, matches project convention of documented dev passwords in seed scripts.
- Regression guard: N/A (docs/data) — verified live: `alamein.transport` / `Alamein_2026` → HTTP 200 tokens.
- First seen: 2026-08-11 (QA-F4)

### PB-21 — Duplicate `TableProfile` rows break profile jobs: Django `update_or_create` raises `MultipleObjectsReturned` (DQ-CORE-P3)
- Symptom: POST `/carbon-api/dq/jobs/` `{job_type: 'profile', data_table_id: 2}` → 201 but job `status: failed`, `error: "get() returned more than one TableProfile -- it returned 3!"`. Only the profile (and suggest) job types hit it — `run_dq`'s sync profile path never did because it tolerates/creates rows differently.
- Layer: backend data integrity (dq)
- Root cause: legacy runs (pre-`update_or_create` era) left 3 `TableProfile` rows for the same table. `TableProfile.objects.update_or_create(data_table=...)` internally calls `get()` on the lookup and raises `MultipleObjectsReturned` when duplicates exist, so the profile job failed every time on that table.
- Fix: in `profile_table` (`dq/services.py`), delete stale duplicates BEFORE `update_or_create` — `stale_ids = filter(data_table=table).order_by('-profiled_at').values_list('id', flat=True)[1:]` → delete → then `update_or_create`. `_get_or_create_table_profile` already used `.first()` so it was unaffected.
- Regression guard: `dq/tests/test_phase3_jobs.py::test_profile_job_survives_duplicate_table_profiles` (creates 2 extra rows, runs the profile job, asserts `status == 'done'` and count collapses to 1). Live-verified: the failing POST now returns `status: done, progress: 100` with a full field-profile result on the same table.
- First seen: 2026-08-11 (TASK-DQ-CORE-P3-JOBS live API smoke)

### PB-22 — Silent auto-pass on Pulse outage reverses to fail-visible; skipped results fire spurious `dq_violation` alerts (DQ-CORE-P4-PULSE)
- Symptom A (old, removed): Pulse down during a DQ run → rule silently reported as PASSED (`passed=True`, score 100) — scores painted a false green. Symptom B (bug this phase): after introducing `status='skipped_unavailable'` / `passed=None`, the `DQResult` post_save receiver `notify_dq_violation` (`dq/signals.py`) used `if instance.passed: return` — a skipped result (`passed=None`) is falsy, so it did NOT return and FIRED a spurious `dq_violation` alert for every skipped row.
- Layer: backend behavioral contract (dq) + notification signals
- Root cause: Phase 3's nl_check degradation path treated "Pulse unreachable" as a pass (`passed=True`) instead of "unknown". The signal guard `if instance.passed:` conflated `None` (unknown/skipped) with `False` (real failure).
- Fix: **fail-visible, not fail-open** (design decision #1, per TASK-DQ-CORE-P4-PULSE):
  1. `DQResult.passed` is now nullable; `status` = `passed|failed|skipped_unavailable`; data migration `dq.0015` backfills existing rows (`passed=True→'passed'`, `False→'failed'`, `null→'skipped_unavailable'`).
  2. Pulse unavailable → `DQResult(status='skipped_unavailable', passed=None, score=0)`; skipped rules excluded from the score denominator (`GET /dq/metrics/` gains `skipped_rules`; all-skipped → `overall_score: 0.0`, `status: 'unknown'`).
  3. Engine `anomaly_detect` rules → `SKIPPED_UNAVAILABLE` sentinel (never fabricate a verdict); `run_dq` skips `nl_check`/`anomaly_detect` (job-only).
  4. Suggest/anomaly jobs: Pulse unreachable → job `failed` with honest `error`; invalid suggestions quarantined to `job.result.invalid`; never fabricated rows.
  5. Signal guard: `if instance.passed is not False: return` — only real failures (`passed=False`) fire `dq_violation`.
- Regression guard: `dq/tests/test_phase4_pulse.py` — `P4FailVisibleTests` (skipped excluded from score, skipped result status, no spurious violation on `passed=None`, `volume_anomaly_pct` actually read) + updated `dq/tests/test_nl_check.py` (6 degradation tests now assert `passed is None`, `checked=0`, `score=0`). Live-verified: nl_check job with Pulse down → `DQResult(status='skipped_unavailable', passed=None)`; suggest/anomaly jobs with Pulse down → `status: failed` + honest error, zero fabricated rows.
- First seen: 2026-08-11 (TASK-DQ-CORE-P4-PULSE — behavior reversal)

### PB-23 — Frontend worker hand-rolls raw MUI `Table` markup where `PanelTable`/`CarbonDataGrid` exist in the registry (RULE 2 violation)
- Symptom: DQ workspace pages (P5) rendered schema dumps and failure rows with raw `TableContainer`/`Table`/`TableHead`/`TableRow`/`TableCell` markup instead of the standard `PanelTable`; the page layout was hand-rolled `Box`+`Stack`+`Grid` instead of `PageContainer`/`PageHeader`. User (Master Architect) challenge: "why don't you use the standard UI and grid components in the system?!".
- Layer: frontend (design-system compliance)
- Root cause: the P5 dispatch prompt told the worker WHAT to build but did not embed the frontend-worker activation protocol (read `shared/design-system.md` + `shared/api-contract.md` + consult `registry/components.md` before writing). Worker skipped RULE 2 (Reuse Before Create — "never create CustomTable"). `registry/components.md` already indexed `PanelTable`, `CarbonDataGrid`, `PageContainer`, `PageHeader`, `StatCard`.
- Fix: swapped both raw tables → `PanelTable` (schema dialog in `DQWorkspacePage.jsx`, failures drawer in `ResultsTab.jsx`), preserving monospace/truncation styling via `columns[].render` callbacks (PanelTable itself untouched). Grep gate: `grep -rn "TableContainer|<Table" src/pages/dq/` → zero (only `PanelTable.jsx` itself may contain raw markup).
- Best practice note: EVERY worker dispatch MUST embed the role's activation protocol (read config → base-rules → design-system → api-contract → scan.sh + registry grep → task files → confirm "Ready as <Role>"). Registry-first is how multi-agent frontends avoid duplication. QA layer 1 should grep for raw `Table`/`Grid item xs=`/hex colors as a design-system conformance check.
- Regression guard: `grep -rn "<Table\|TableContainer\|Grid item\|#\h*[0-9a-fA-F]{3,6}" carbon-frontend/src/ --include="*.jsx"` (design-system conformance); `npm run lint` (0 errors) + `npm run build`.
- First seen: 2026-08-11 (TASK-DQ-CORE-P5-FRONTEND component audit)

### PB-24 — Shell crashes with "Something went wrong" on dev-server restart (CommandPalette lazy import unguarded)
- Symptom: After a Vite dev-server restart the entire shell UI shows "Something went wrong / Failed to fetch dynamically imported module: .../src/shell/CommandPalette.jsx". The app is completely unusable until page reload. Simultaneously: `ws://localhost:5179/carbon/?token=... net::ERR_CONNECTION_RESET` in console.
- Layer: frontend / dev infra
- Root cause (1 — code bug): `CommandPalette` is lazy-loaded (`React.lazy`) inside `Shell.jsx` and wrapped in `<Suspense>` but with **no `<ErrorBoundary>`**. `Suspense` handles loading state only — it does not catch errors. When the Vite dev server is temporarily unavailable, `import('./CommandPalette')` throws a network `TypeError`. Because `CommandPalette` is always in the component tree (Shell is always mounted), the unguarded error propagates up through `<Shell>` and is caught by the root `<ErrorBoundary>` in `App.jsx`, crashing the entire shell instead of just the palette.
- Root cause (2 — Vite config): `vite.config.js` lacked `strictPort: true` and explicit `hmr` config. Without `strictPort`, a Vite restart may silently bind a different port; the browser WS still targets the original port → ERR_CONNECTION_RESET. Explicit `hmr` config prevents URL mismatch when `base` is set.
- Fix: (a) In `Shell.jsx`, wrap `<Suspense><CommandPalette /></Suspense>` in `<ErrorBoundary>`. The palette failure is now isolated — the shell stays alive; (b) In `vite.config.js`: add `strictPort: true` and `cacheDir: '.vite'` (moves dep cache outside `node_modules/.vite` so `manage.sh`'s `rm -rf node_modules/.vite` no longer forces a full re-optimization on every restart, which was the root of the slow startup window where WS connections fail). Do NOT add an explicit `hmr` block — hardwired `host`/`protocol` values break non-localhost access and bypass Vite's internal readiness handshake, causing "WebSocket closed without opened" errors on startup.
- Best practice note: every `React.lazy()` component that is always mounted (not behind a conditional route) MUST have its own `<ErrorBoundary>` guard in addition to `<Suspense>`. Route-level lazy imports in `App.jsx` are lower risk (loaded on navigation only) but should also be wrapped per-route for maximum resilience.
- Regression guard: build passes (`npm run build`) — confirmed. Visual: restart frontend with `./manage.sh restart frontend`, reload browser — shell renders normally, CommandPalette failure shows a contained error widget rather than crashing the shell.
- First seen: 2026-08-11

### PB-25 — "Page Not Found: /carbon/" on first open (bare namespace root)
- Symptom: opening the app at a namespace root (e.g. `/carbon/`, or a deployment mount
  path) shows NotFound while the sidebar still highlights the correct studio.
- Layer: frontend
- Root cause: routes are absolute + namespace-prefixed (`/carbon/console`, `/admin/users`,
  …) but the namespace root itself (`/carbon`, `/admin`, `/settings/profile`, …) had no
  `<Route>`, so the bare path fell through to `<Route path="*">` → NotFound. The combined
  nginx mount serves the SPA at `/carbon/`, and `VITE_BASE=/` does not strip it.
- Fix: add index redirects at each bare root, e.g.
  `<Route path="/carbon" element={<Navigate to="/carbon/console" replace />} />`, plus
  `/admin` → `/admin/users`, `/settings/profile` & `/settings/preferences` → `/settings`,
  `/emissions/dashboard` → `/carbon/dashboard`, `/data-owner/reports/generate` →
  `/carbon/reporting/generate`, `/modules` → `/carbon/my-data`, `/scopes` & `/dashboards`
  & `/schema-admin` → their canonical pages. Fixed the dead source references too
  (CommandPalette `/emissions/dashboard`, SavedReportsPage `/data-owner/reports/generate`).
- Best practice note: every top-level route namespace MUST declare a bare-root index route
  (RULE_22). A deployment mount path is just the bare root of a namespace.
- Regression guard: `.ai-toolkit/scripts/audit-routes.py` (wired into `verify.sh frontend`)
  fails on any missing namespace root or dangling nav target.
- First seen: 2026-08.

### PB-26 — DQ rule CREATE always 400: JSON-first `definition` vs DRF top-level required fields
- Symptom: "New Rule" dialog always fails with `{"rule_type": required, "name": required}` (UI shows `field: _root (server)` ValidationError). Standalone curl create with a valid `definition` + empty `bindings` succeeds (201) — so the backend accepts the definition, but the UI path never does.
- Layer: backend / frontend (contract mismatch)
- Root cause: `DQRuleSerializer` keeps `rule_type` and `name` as required **top-level** model fields (not read-only), so DRF rejects a payload that only sends `definition`. `createDQRule` (`src/api/dq.js`) sends `{definition, field_assignments_write}` and omits both. ADR-0006 says `definition` is the single source of truth, but the serializer also demands the denormalized columns — **two sources of truth for the same field**.
- Fix: either (a) `createDQRule` forwards top-level `name` + `rule_type` (derived from `definition.name` / `definition.type`), or (b) make the serializer derive/accept them from `definition` (cleaner — honors ADR-0006). Note `definition.type` uses `level: 'field'|'business'` while the model `rule_level` uses `field_validation`/`business_rule` — `DQRule.save()` maps them, but DRF validates the model field **before** `save()`, so any top-level `rule_level:'business'` also 400s (see PB-29).
- Best practice note: when a JSON blob is declared the source of truth, the serializer must NOT also require its denormalized mirror columns on the same payload — derive them server-side (or mark them read-only + populate in `create()`).
- Regression guard: `backend/dq/tests/test_dq.py` — add a create test that POSTs `definition`-only and asserts 201.
- First seen: 2026-08-16.

### PB-27 — DQ standalone rules rejected client-side (bindings hard-required, contradicts ADR-0006)
- Symptom: "why does rule creation require a table and field?" — the New Rule dialog pre-fills `bindings: [{table:'',field:''}]` and client validation hard-fails when `bindings` is empty, even though standalone rules are legal per ADR-0006.
- Layer: frontend
- Root cause: `src/pages/dq/tabs/RulesTab.jsx` `openCreate()` seeds a blank binding, and `src/pages/dq/bindings.js` `resolveBindings()` pushes a hard `code:'empty'` error when `bindings.length === 0`. The backend `rule_schema.py` treats bindings as **optional** (verified: empty-bindings create → 201).
- Fix: stop pre-filling a blank binding; allow `bindings: []` through `resolveBindings` (skip resolution, return `[]`). Bindings are applied separately at the data-product level.
- Best practice note: a client-side "required" guard must mirror the backend contract — if the backend schema marks a field optional, the frontend must not invent a hard requirement.
- Regression guard: unit test `validateDefinitionClient` + `resolveBindings` with `bindings: []` returns no error.
- First seen: 2026-08-16.

### PB-28 — Frontend list API helper drops filter/search params → filters silently no-op
- Symptom: DQ Rules search box + Filters (rule_type/dimension/severity/is_active/tag/include_archived) appear to do nothing — typing "Not Null" still returns every row. Backend list endpoint DOES honor `search`, `rule_type`, `dimension`, etc. (verified via curl).
- Layer: frontend / api
- Root cause: `listDQRules` (`src/api/dq.js`) builds `URLSearchParams` for **only** `data_table` and `data_field`; the UI passes `search`, `rule_level`, `rule_type`, `dimension`, `severity`, `is_active`, `tag`, `include_archived` which are silently dropped before the request.
- Fix: forward every filter the UI exposes (or filter client-side). Add an explicit "unsupported param" guard so unknown filters fail loud instead of vanishing.
- Best practice note: a list API wrapper and its consumer must agree on the full filter surface — when a filter is added to the UI, add it to the query builder in the same change. This is a **candidate for UP promotion** (filter-forwarding drift recurs across list pages).
- Regression guard: integration test asserting `search=` narrows the result set through the real API wrapper.
- First seen: 2026-08-16.

### PB-29 — DQ definition vs model vocabulary drift (`level` field/business vs `rule_level` field_validation/business_rule)
- Symptom: passing top-level `rule_level: "business"` → 400 `invalid choice`; UI/store values look inconsistent.
- Layer: backend
- Root cause: `definition.level` uses `'field'|'business'` (rule_schema RULE_LEVELS), but the `DQRule.rule_level` model field uses DRF choices `field_validation`/`business_rule`. `DQRule.save()` maps `'field'→'field_validation'`, `'business'→'business_rule'`, but DRF validates the model field **before** `save()` runs, so clients that pass the definition-style value are rejected.
- Fix: accept both vocabularies in the serializer (normalize `field`↔`field_validation`, `business`↔`business_rule` in `validate_rule_level`), or expose only one vocabulary to clients.
- Best practice note: one concept = one vocabulary. If a denormalized column must differ from the JSON representation, do the translation in the serializer's `validate_*`/`to_internal_value`, never rely on `Model.save()` (which runs too late for field validation).
- Regression guard: serializer unit test for both `'business'` and `'business_rule'` inputs.
- First seen: 2026-08-16.

### PB-30 — DQ Test tab silently all-passes standalone rules (reader/writer field-fallback mismatch)
- Symptom: testing a standalone regex rule (no bindings) against sample rows shows every row `undefined` → all "Passed" with no reason, even values that should fail (e.g. `"!!!"` against an email regex).
- Layer: frontend
- Root cause: `TestTab.jsx` `evaluateRule` resolved the field to check ONLY from `bindings[0].field`, falling back to `null` when bindings are empty → every row read `undefined`, and `regex`/`not_null` short-circuit "empty" values to pass. `defaultSampleForRule` wrote the sample under a `'value'` key using a **different** fallback, so the evaluator never read the data it generated.
- Fix: unify the fallback — binding field wins, else infer the key from the first sample row's first object key, else `'value'` (the template key). Verified: `[{"value":"abc123@example.com"},{"value":"!!!"},{"value":"test@example.com"}]` → 2/3 passed, `"!!!"` correctly failed.
- Best practice note: when a value's source can be absent (no binding), the reader and writer MUST agree on the same fallback key — a silent `undefined`→pass is the worst failure mode (false green). This is the same class as CB-09 (validate-before-use); see also "test results must fail loud, not pass silently".
- Regression guard: component test for `evaluateRule` with `bindings: []` + a sample row that should fail.
- First seen: 2026-08-16.

### PB-31 — DQ "Save Definition" silently drops field_assignments not present in `definition.bindings` (data loss)
- Symptom: editing/saving a rule's definition removed a bound table/field that was not re-listed in `definition.bindings` (rule 104 went 2 bindings → 1) with no warning.
- Layer: frontend (drift reconciliation)
- Root cause: `DefinitionTab.handleSave()` PATCHes `{definition, name, description, tag_ids, field_assignments_write}` where `field_assignments_write` is derived only from `definition.bindings`. Any existing assignment missing from the definition is silently dropped (replace-all semantics).
- Fix: before replacing, diff `definition.bindings` vs existing `field_assignments` and warn on any drop (or preserve unmentioned assignments unless explicitly removed).
- Best practice note: destructive reconcile (replace-all) of user data requires an explicit diff + confirmation — never silently shrink a relationship list on a partial update.
- Regression guard: test asserting a save that omits a binding does not delete it without confirmation.
- First seen: 2026-08-16.

### PB-32 — DQ flat-column PATCH silently reverted: `DQRule.save()` re-syncs name/is_active from `definition` (double source of truth)
- Symptom: "Lifecycle" Deactivate/Activate button and "Save Definition" rename both appear to work (200 + success snackbar) but the value snaps back on reload — rule stays Active, name stays old.
- Layer: backend (serializer ↔ model `save()` interaction)
- Root cause: `DQRule.save()` re-derives `name`, `severity`, `dimension`, `is_active` (and `rule_level`/`rule_type`) FROM `definition` on every save. The serializer's `validate()` uses `data.setdefault(...)` (flat field "wins"), but `save()` then overwrites the flat value with the (stale) `definition` value. Two sources of truth; the JSON one silently wins at the last moment.
- Fix: in `DQRuleSerializer.update()`, when an explicit flat column is present (`name`/`severity`/`dimension`/`description`/`is_active`), reconcile it INTO the definition before saving. If the client sent `definition`, merge flat→definition and let the normal version-bump run; if flat-only, update `instance.definition` in place (no version bump). Verified: `PATCH {is_active:false}` now sticks (version unchanged); `PATCH {name, definition(stale name)}` sticks + bumps version.
- Best practice note: a `save()` override that re-derives denormalized columns must never clobber an explicitly-provided value — reconcile flat inputs into the source-of-truth document at the serializer boundary, not silently.
- Regression guard: API test that PATCHes `{is_active: false}` (no definition) and asserts the rule is inactive after reload; and a PATCH of `{name, definition}` where `definition.name` differs, asserting the new name wins.
- First seen: 2026-08-16.

### PB-33 — DQ Lifecycle "Delete"/"Archive" buttons 404: `deleteDQRule` called without token
- Symptom: clicking Delete or Archive in the Lifecycle tab fails with a 404 (or "Could not delete rule"), even though the rule exists.
- Layer: frontend
- Root cause: `OperationsTab.handleDelete()` / `handleArchive()` called `deleteDQRule(rule.id)` but the wrapper signature is `deleteDQRule(token, id)` — so `token` received the rule id and `id` was `undefined`, hitting `dq/rules/undefined/`.
- Fix: pass `token` first — `deleteDQRule(token, rule.id)`.
- Best practice note: every `apiFetch`-wrapping helper takes `(token, ...)`; always pass the token from `useAuth()` — a missing-token call compiles fine but hits a bogus URL. A TS signature or an eslint rule flagging the arity mismatch would have caught this statically.
- Regression guard: component test that mocks `deleteDQRule` and asserts it's called with `(token, id)`.
- First seen: 2026-08-16.

### PB-34 — AI `build_scope` AttributeError: `ScopedRole` has no `is_read_only` column
- Symptom: every AI create/send (conversation, message) returns HTTP 500 `{"error":"AttributeError"}` for non-superuser, non-staff users (QA journey SEC2). Superusers unaffected (early `is_superuser` return).
- Layer: backend (RBAC scope builder)
- Root cause: `build_scope()` iterated `ScopedRole` rows and read `role.is_read_only`, but `ScopedRole` has no such field — read-only is derived from the assigned `group.name` against `accounts.constants.READ_ONLY_ROLES` (`viewers_group`, `analysts_group`). The attribute access raised `AttributeError` → 500.
- Fix: derive `is_read_only` from `role.group.name not in READ_ONLY_ROLES` (a single write-capable role flips the user out of read-only), and add `group` to `select_related()` to avoid N+1.
- Best practice note: never read a model attribute that isn't declared on the model — read-only/role semantics that live in `constants.py` must be checked via the actual FK (`group.name`), not a phantom column. A `hasattr`/`.only()` guard or a Pydantic/serializer boundary would surface this at import time instead of runtime.
- Regression guard: unit test that builds a scope from roles whose `group.name` is only read-only roles and asserts `is_read_only is True`, plus one with a write role asserting `False`.
- First seen: 2026-08-16.

### PB-35 — AI export `?format=markdown|xml` → 404 (DRF `URL_FORMAT_OVERRIDE` collision)
- Symptom: `GET conversations/{id}/export/?format=markdown` returns 404; `?format=xml` returns 404 instead of the intended 400 "unsupported format"; only `?format=json` works.
- Layer: backend (DRF content negotiation)
- Root cause: `format` is DRF's reserved `URL_FORMAT_OVERRIDE` query param. Content negotiation runs in `finalize_response` and calls `filter_renderers(renderers, "markdown")`, which raises `NotFound` (404) because no renderer has `format="markdown"` — so the view never even gets to return its 400.
- Fix: rename the export query param to `fmt` (`?fmt=json|markdown`). Updated `workspace_api.export`, `aiWorkspace.exportConversation`, e2e S9, and `DESIGN_AI_WORKSPACE_NEXTGEN.md`.
- Best practice note: never name your own query param `format` (or `callback` for JSONP) — DRF reserves it. Also audit `emissions/views.py` (`?format=` at lines ~265/847), which has the same latent collision.
- Regression guard: API test asserting `?fmt=markdown` → 200 and `?fmt=xml` → 400.
- First seen: 2026-08-16.

### PB-36 — AI pinned conversations missing from default list/search
- Symptom: a conversation pinned via `PATCH {is_pinned:true}` disappears from `GET conversations/` (and `?q=` search) unless the client explicitly passes `?is_pinned=true`.
- Layer: backend (DRF serializer field defaults)
- Root cause: `is_pinned = BooleanField(required=False)` — for absent input DRF's `BooleanField` returns `default_empty_html=False` (NOT None), so `validated_data["is_pinned"]` is `False`, and `list_conversations` filtered OUT pinned rows.
- Fix: `is_pinned = BooleanField(required=False, allow_null=True)` so an absent value stays `None` and the filter is skipped. (Leave `is_archived` as-is: its default `False` = "exclude archived" is the intended default.)
- Best practice note: a filterable `BooleanField(required=False)` means "absent ⇒ no filter", which requires `allow_null=True` (absent ⇒ `None`), not the default `False`.
- Regression guard: test that the default list endpoint includes a pinned conversation.
- First seen: 2026-08-16.

### PB-37 — AI `list_messages` first page always reports `has_more=False`
- Symptom: `GET conversations/{id}/messages/?limit=50` with >50 messages returns 50 rows but `has_more:false`, so clients never page forward.
- Layer: backend (cursor pagination)
- Root cause: `list_messages` computed `has_more` only in the `before`/`after` cursor branches; the no-cursor (first page, oldest-first) branch left it `False`.
- Fix: add an `else` branch — the default page returns the OLDEST `limit` messages ascending, so `has_more = messages.filter(created_at__gt=window[-1].created_at).exists()`.
- Best practice note: every pagination path must set `has_more`; when you add a cursor branch, make sure the no-cursor default branch is also covered (and tested).
- Regression guard: seed 55 messages, assert first page (limit=50) returns `has_more is True`.
- First seen: 2026-08-16.

### PB-38 — Domain-app vocabulary leaks into the generic catalog UI (GHG `scope` on Data Products)
- Symptom: the "Data Products" catalog list exposes a **Scope** filter/column/form field with options Scope 1/2/3 — meaningless to any non-carbon domain, and a smell that the "generic" Data Trust core is hard-wired to the first hosted app.
- Layer: cross-cutting (model + frontend vocabulary)
- Root cause: `Module` (the code entity surfaced as "Data Product") lives in the domain-agnostic `core` app but carries `scope = PositiveSmallIntegerField(choices=[(1,'Scope 1'),(2,'Scope 2'),(3,'Scope 3')])` — GHG emission scope. `DataProductsPage.jsx` mirrors it as a filter/column/form, and `terminology.js` ships `SCOPE_LABEL`/`SCOPE_OPTIONS` next to the generic `DATA_PRODUCT` label.
- Fix: treat emission scope as carbon-domain metadata. Near-term: move `scope` into a per-domain attribute (JSON `domain_attributes` on `Module` keyed by `app_id`, or a `DomainModuleProfile` extension) and add the *generic* filter dimensions that are missing: `domain` (`DataDomain`), `classification`, `tags`, owner/steward, quality status (all already exist on `AssetProfile`, one level below).
- Best practice note: a domain-agnostic core (Catalog/MDM/DQ/schema) must never expose a hosted app's enum in its shared model or UI — same leak class as PB-29 (`level` field/business vs `rule_level`). When a "generic" surface has a filter only one domain understands, it's a boundary violation, not a feature.
- Regression guard: assert `Module`/Data Product serializer and list page expose only generic dimensions (org_unit, domain, classification, tags, quality) — no `scope` unless the active domain app is carbon.
- First seen: 2026-08-16.

### PB-39 — AI tool execution crashes: `'ToolExecution' object has no attribute 'refresh_from_db'`
- Symptom: `create_dq_rule` (Pulse tool) fails at runtime with
  `AttributeError: 'ToolExecution' object has no attribute 'refresh_from_db'`
  at `store.py:437` (called from `host_executor.py:185`). The pending execution row
  IS committed before the crash, so each failed attempt leaves an orphaned
  `pending_confirmation` row. No rule is created; user gets an error note.
- Layer: backend (AI Store two-layer model bridge)
- Root cause: the Store has a two-layer model system — engine (SQLAlchemy `DeclarativeBase`)
  classes in `ai/engine/core/models.py` are plain Python objects, and Django mirrors live in
  `ai/models/`. Every Store method that touches objects (`add`, `select`, `get`) first resolves
  engine→Django mirror via `_to_django_instance()` / `resolve_model()` — but `_DjangoSession.refresh()`
  was the ONLY method that called `obj.refresh_from_db()` on the raw engine instance (which has no
  such method), instead of on its Django mirror. `create_pending_execution()` instantiates the engine
  `ToolExecution`, so the crash was guaranteed.
- Fix: in `_DjangoSession.refresh()` (backend/ai/store.py), resolve the mirror first:
  `dj_obj = _to_django_instance(obj)` then `await sync_to_async(dj_obj.refresh_from_db, thread_sensitive=True)()`.
  Chosen over dropping the post-commit refresh (QA recommendation) — it fixes ALL 6 `refresh()` call
  sites (tool executions, agents, skills, registry) with the same invariant the other methods follow.
- Best practice note: any new Store method that accepts engine instances must run them through
  `_to_django_instance()` before touching Django-ORM-only behavior. Audit `refresh()`-style helpers
  when adding a new model layer. Also keep error paths in `create_pending_execution` atomic (delete
  the staged row on failure) so a crash can't orphan rows.
- Regression guard: `backend/ai/tests/test_tool_execution_actions.py::test_create_pending_execution_stages_via_django_store`
  (drives `CarbonHostExecutor.create_pending_execution()` end-to-end through the Django store).
- First seen: 2026-08-18.

### PB-40 — EnterpriseGraph node collapses to 0×0 / invisible after drag or resize
- Symptom: dragging a node collapses its body to 0×0; resizing a node makes it
  disappear entirely (SVG `transform="translate(NaN, NaN)"`).
- Layer: frontend
- Root cause: `EnterpriseGraph.jsx` `effectiveNodes` copied the override onto the
  layout node **field-by-field** (`x: o.x, y: o.y, w: o.w, h: o.h`). A pure drag
  stores only `{x, y}` and a pure resize only `{w, h}`; the missing field was copied
  as `undefined`, overwriting the layout's real value.
- Fix: merge the override ON TOP of the layout node (`{ ...n, ...o }`) so missing
  fields fall back to the layout geometry. See
  `carbon-frontend/src/components/graph/EnterpriseGraph.jsx` → `effectiveNodes`.
- Best practice note: when layered state (auto-layout + user overrides) is merged,
  ALWAYS spread, never copy field-by-field — a partial record must inherit the
  fields it doesn't specify. Also: E2E tests must assert the **orthogonal** dimension
  (w/h after a drag, x/y after a resize), not just the one being changed, or a
  cross-field regression passes silently.
- Regression guard: `journey-12-task-run.spec.ts` S6.8 (w/h preserved after drag)
  and S6.12 (x/y preserved after resize).
- First seen: 2026-08-21.
