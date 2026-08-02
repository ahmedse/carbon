# CARBON ENTERPRISE READINESS PLAN — E0→E6

**Author:** Master Architect · **Date:** 2026-08-02
**Basis:** `CARBON_MASTER_AUDIT_20260802.md` (read first — every task cites its evidence)
**Goal:** enterprise-deployable Data Trust Platform + carbon domain app (AASTMT).
**Supersedes:** open items of `CARBON_QA_ENTERPRISE_VALIDATION_PLAN.md` (its P13/P15/P16 map into E3/E5/E6).
**Naming:** E-prefix avoids the burned P13/P14 labels (three historical schemes collided — see audit §4).

## Worker model policy (budget directive)

| Role | Model | Used for |
|---|---|---|
| Master Architect | DeepSeek V4 Pro | specs, review, ADRs (handed over 2026-08-02) |
| All workers (backend, frontend, devops, debugger, qa) | **DeepSeek-V3** (VSCode Copilot custom model) | execution |
| Researcher / Curator | DeepSeek-R1 | analysis, retrospectives |
| Kimi | **off roster** (cost) | — |

## Execution rules (bind every worker)

1. Read `.ai-toolkit/project.config.md` + `shared/base-rules.md` + role file + this phase before starting.
2. One worker = one domain (backend XOR frontend). Never cross.
3. Registry-first: `./.ai-toolkit/scripts/scan.sh`, grep before creating anything.
4. Every gate must pass with pasted terminal output in TASK-RESULTS-E*.md — no output, no completion.
5. Every bug fix ships a regression test + a `troubleshooting/playbook.md` entry.
6. Standard gates: backend `cd backend && ../.venv/bin/python -m pytest --reuse-db -q`;
   frontend `cd carbon-frontend && npm run lint && npm test && npm run build`;
   phase end `./.ai-toolkit/scripts/verify.sh all`.

## Phase map

| Phase | Scope | Worker | Size | Depends on |
|---|---|---|---|---|
| E0 | Gate & toolkit trust | debugger-fixer | S | — (verify.sh core already fixed 2026-08-02) |
| E1 | Security lockdown | backend-worker | S/M | E0 |
| E2 | Carbon deployment blockers (B1→B6, then F1/F2) | backend + frontend | L | E1 |
| E3 | Carbon enterprise features | backend + frontend | L | E2 |
| E4 | Frontend hygiene & design system | frontend-worker | M | E0 (parallel with E2/E3 backend) |
| E5 | Backend hygiene & platform coverage | backend-worker | M | E2 (parallel with E3 frontend/E4) |
| E6 | Docs, archive, deployment readiness | devops-worker + Master | M | E1–E5 |

**Human decisions required (collect before E1/E6):**
- [ ] Rotate the 7 plaintext credentials exposed in docs (E1 only scrubs the docs).
- [ ] Git history scrub for the 20 tracked upload files, or accept `git rm --cached` only.
- [ ] Canonical Egypt grid factor: 0.4584 (`setup_carbon_app.py`) vs 0.527 vs 0.475.
- [ ] PDF report output required at go-live, or Excel+CSV sufficient? (E3-1)
- [ ] PROD_HOST / PROD_STACK_PATH / PROD_DB values (project.config.md TBD).
- [ ] CI platform: GitHub Actions or local gate runbook only?

---

## E0 — Gate & toolkit trust (debugger-fixer, DeepSeek-V3) · S

`verify.sh` venv + false-PASS bugs were fixed 2026-08-02 (toolkit pass). Remaining:

**FILES TO READ FIRST:** `carbon-frontend/src/api/api.js`, `carbon-frontend/src/components/NetworkStatusBanner.jsx`, `.ai-toolkit/QUICK-START.md`, `~/ai-toolkit/roles/{backend-worker,data-ml-worker,researcher,frontend-worker}.md`, `.ai-toolkit/scripts/verify.sh`.

**TASKS:**
1. Fix the 7 ESLint errors (0 errors is the gate):
   - `src/api/api.js:13` unused `buildQuery`; `:69,:80,:225` unused caught `e`; `:215` `process` undef (use `import.meta.env` or keep the `typeof process` guard and satisfy eslint); `:275` unused `refreshError`.
   - `src/components/NetworkStatusBanner.jsx:5` unused `useCallback`.
2. `verify.sh` antipatterns scope fix: hex check must cover `src/pages/` + `src/components/` (today it reports "no hex" while ~237 exist) — report as **warning with count** (don't fail; E4 burns it down); print() check must exclude backend root loose scripts from the "app code" count (report separately).
3. `.ai-toolkit/QUICK-START.md`: role count 8→10, model names per new policy, remove "hook live" claims (mirror ROLES.md).
4. Generic-ize shared role bodies (`~/ai-toolkit/roles/`): remove Gigacast specifics — `backend-worker.md` (Forecaster Contract, ai_engines), `data-ml-worker.md` + `researcher.md` (datahub_v2, ml_feature_service, MAPE), `frontend-worker.md` (aihub route example, "MUI v6" heading → generic MUI). **`researcher.md:52` hardcodes `/home/ahmed/aast/carbon/backend && source .venv/bin/activate`** — replace with project.config.md variable references (`BACKEND_DIR`, `VENV_PATH`). Keep files generic — no carbon paths.

**DO NOT TOUCH:** `backend/`, other `carbon-frontend/src/` files, verify.sh pass/fail semantics.

**GATES:**
```
cd carbon-frontend && npm run lint            # 0 errors (58 warnings baseline OK)
./.ai-toolkit/scripts/verify.sh backend       # PASS
./.ai-toolkit/scripts/verify.sh frontend      # PASS
grep -c "8 roles" .ai-toolkit/QUICK-START.md  # 0
grep -rn "gigacast\|ai_engines\|datahub_v2\|ml_feature_service" .ai-toolkit/roles/  # 0
```

---

## E1 — Security lockdown (backend-worker, DeepSeek-V3) · S/M

**FILES TO READ FIRST:** `backend/config/urls.py`, `backend/config/settings.py`, `backend/connections/models.py` + serializers, `docs/QUICKSTART_DEPLOYMENT.md:77-84`, `docs/DEPLOYMENT_PLAN_AASTMT_CARBON.md:798-835`, audit §2.

**TASKS:**
1. Replace all plaintext passwords in the two deployment docs with `<set-at-deploy>` + add a "credentials rotated 2026-08, rotate again before production" banner. (Human rotates the real accounts — not the worker's job.)
2. `git rm --cached` the 20 tracked runtime files: `backend/dataschema_uploads/` (15), `backend/mediafiles/` (5). Verify `git ls-files backend/dataschema_uploads backend/mediafiles | wc -l` → 0. Do NOT delete the files from disk.
3. `config/urls.py`: gate swagger (`:73`) on development env (same predicate as debug_toolbar); remove legacy `api/v1/carbon/` mount (`:65`) and review the targets-only legacy mount (`:76`) — remove or document in ADR; fix `urls.W005` duplicate namespace 'carbon'; delete dead commented routes (`:51,:55`); add `app_name` to `evidence/urls.py`.
4. Unify env gating: `settings.py:85-86` (DJANGO_ENV) vs `urls.py:79` (DEBUG) — one predicate, helper in settings (`IS_DEVELOPMENT`).
5. `connections`: mask secrets in `connection_config` — serializer returns masked view (values `***`), full write-only; admin masked; regression test that GET never leaks a stored secret value.

**DO NOT TOUCH:** emissions logic, frontend, migrations other than none-needed, `.env`.

**GATES:**
```
cd backend && ../.venv/bin/python -m pytest --reuse-db -q   # all pass + ≥3 new tests
git ls-files backend/dataschema_uploads backend/mediafiles | wc -l   # 0
grep -rn "P@ssw0rd\|password123\|admin123" docs/ | wc -l             # 0 (real values gone)
../.venv/bin/python manage.py check                                   # 0 issues (W005 gone)
./.ai-toolkit/scripts/verify.sh backend                               # PASS
```

---

## E2 — Carbon deployment blockers (backend-worker → frontend-worker, DeepSeek-V3) · L

Order matters: **B1 (RBAC) first**, then B2 (verification backend) + B3 (locking), then B4/B5/B6, then frontend F1/F2. Audit §8 is the evidence base.

### E2-B1 — RBAC reconciliation (backend)
**READ:** `backend/accounts/rbac_utils.py:89` (VISIBILITY_ROLES), `accounts/permissions.py`, `accounts/views.py:168`, `backend/deploy_aastmt_carbon.py:436`, `emissions/views.py:97,115,211`, `carbon-frontend/src/auth/AdminRoute.jsx:35` + `App.jsx:191-206` (read-only) + `apps/carbon/manifest.js` (read-only).
1. Single source of truth for group names: `accounts/constants.py` (or settings) — canonical set: `admins_group`, `analysts_group`, `viewers_group`, `carbon_data_owners_group`, `carbon_analysts_group`. VISIBILITY_ROLES, protected groups, and the deploy seeder all import from it.
2. Fix deploy mismatch: `deploy_aastmt_carbon.py` creates `carbon_admin` (recognized nowhere) → create/alias canonical groups so a deployed carbon admin actually has app admin rights.
3. Close the write hole: `CalculationViewSet` create → ScopedRole-based permission (analyst/admin for module), not bare `IsAuthenticated`.
4. verify/reject (`emissions/views.py:97,115`): replace raw `groups.filter(name=...)` with the same ScopedRole/permission-class mechanism used elsewhere.
5. Frontend alignment note (no frontend edits here): report which `/carbon/*` AdminRoute guards contradict manifest roles — output feeds F1.
**GATES:** pytest pass + ≥6 new RBAC regression tests (calc create denied for viewer, allowed for analyst; verify denied for non-admin; deployed groups resolve); `verify.sh backend` PASS.

### E2-B2 — Verification workflow + ReportingPeriod state machine (backend)
**READ:** `emissions/views.py:83-130`, `emissions/models.py:25-33,98-124`, `emissions/serializers.py:27-37`, `emissions/services.py`, audit §8-M3/M4.
1. Move the submit/verify/reject lifecycle out of the view into `VerificationService` (views thin). 
2. ReportingPeriod: `VALID_TRANSITIONS` + `transition_to()` on the model (pattern: `mdm/models.py:29-105`); view actions become thin wrappers; block invalid transitions with 409.
3. On `submit` → create **pending** VerificationRecord (this populates the UI's Pending tab).
4. `VerificationRecordViewSet`: add `verify`/`reject` actions (the frontend calls these); keep period-level actions delegating to the same service.
5. Fix `unique_together(reporting_period, verifier)` 500: service does get-or-update per (period, verifier); re-verify by same verifier updates, different verifier inserts. Regression test: double-verify → 200, not 500.
6. Serializer: expose the fields the grid expects (`scope`, `total_co2e`, org unit, period label).
**GATES:** pytest pass + verification-flow tests (submit→pending→verify, reject with reason, double-verify, invalid transition 409); `verify.sh backend` PASS.

### E2-B3 — Period-lock enforcement (backend)
**READ:** `emissions/services.py:418-422`, `dataschema/views.py:142` (is_locked), `dataschema/models.py`, audit §8-M3.
1. Calculation gating: `locked`/`verified`/`closed` periods block calculation (today only `closed`).
2. Add period transition actions `open`/`lock`/`close` (thin views → service, uses E2-B2 state machine); UI's raw status PATCH gets retired in F1.
3. Lock propagation: service method `set_period_tables_locked(period, locked)` → flips `DataTable.is_locked` on activity tables linked via CalculationRule; called on lock/unlock transitions. (Row-date-level enforcement = ADR candidate — note in TASK-RESULTS, don't build.)
**GATES:** pytest pass + tests: calc blocked on locked period; lock flips table locks; data POST to locked table → 403/409.

### E2-B4 — Notifications, minimal (backend)
**READ:** `backend/accounts/models.py`, `emissions/views.py` lifecycle points, `carbon-frontend/src/` NotificationProvider (read-only).
1. `core.Notification` model: user FK, verb, message, link, read_at, created_at (+ migration).
2. `NotificationService.notify(...)`; emit on: period submitted/verified/rejected, batch calculation complete.
3. Endpoints: `GET /carbon-api/notifications/` (paginated, unread count), `POST .../mark-read/`.
**GATES:** pytest pass + ≥4 tests (emission on each event, mark-read); verify.sh backend PASS.

### E2-B5 — importexport execution (backend)
**READ:** `importexport/services.py:9-45`, `importexport/models.py`, `dataschema/services.py` BulkImportService, audit §8-M7.
1. `ImportService.run_import`: parse CSV → delegate to BulkImportService; statuses pending→running→done/failed with error text; synchronous execution (no Celery — note as ADR if async needed).
2. `ExportService.run_export`: DataTable → CSV in media; status→ready; download endpoint.
3. Scheduled exports: leave unimplemented; remove or hide the schedule field from serializer (don't advertise what doesn't run — note in TASK-RESULTS).
**GATES:** pytest pass + import/export round-trip tests; verify.sh backend PASS.

### E2-B6 — Recalculate endpoints (backend, small)
1. `POST /carbon-api/carbon/calculations/{id}/recalculate/` + `batch-recalculate/` — thin actions delegating to CalculationEngineService (frontend already calls these paths).
**GATES:** pytest pass + 2 action tests.

### E2-F1 — Verification UI repair (frontend-worker, after B1–B3 land)
**READ:** `src/api/emissions-extended.js:317-344`, `src/pages/carbon/VerificationPage.jsx`, B2 serializer shape, `src/components/detail/` tabs pattern.
1. Repoint verify/reject to the new `verifications/{id}/verify|reject/`; delete dead `submitPeriod()`.
2. Pending tab consumes pending records; grid columns ↔ serializer fields; reject requires a reason (dialog).
3. Evidence-in-context: link each row to its period/org data — deep-link to `RowDetailPage` evidence tab (existing `RowEvidenceTab`).
4. Replace the ReportingPeriodsPage raw-status dropdown with transition action buttons (submit/verify/reject/lock per `VALID_TRANSITIONS`).
5. Wire the E2-B1 guard alignment: route guards match manifest roles (AdminRoute vs analyst/data-owner pages).
**GATES:** lint PASS (0 errors), `npm test` PASS, build PASS, manual checklist: pending→verify, pending→reject w/ reason, evidence link resolves, invalid transition hidden.

### E2-F2 — Notifications badge + CalculationsPage fix (frontend-worker)
1. StatusBar/AppBar unread badge + dropdown panel fed by `/notifications/` (extend NotificationProvider — do NOT fork a new system).
2. CalculationsPage recalc buttons now hit real endpoints (B6); Analytics: remove or implement the dead "Compare" button.
**GATES:** lint/test/build PASS; badge increments on test event (screenshot or manual note).

---

## E3 — Carbon enterprise features (backend + frontend, DeepSeek-V3) · L

### E3-1 — Reporting: Excel + by-gas + export audit (backend)
**READ:** `emissions/views.py:451-506`, `emissions/services.py:259-373,1019-1109`, `api/emissions.js:38`.
1. Add `xlsxwriter` (pinned) → Excel GHG inventory: sheets = summary (scope→category), by-gas (CO2/CH4/N2O from Calculation gas fields), detail rows, org-unit rollup.
2. Fix param drift: accept both `format` and `output_format` (or update client — pick one, note in TASK-RESULTS).
3. Honor `include_dq_status`; implement `grouping=month|category` or trim the choices.
4. `ExportAudit` (who/when/config hash/format) written per generated report; list endpoint.
5. PDF: implement simple reportlab summary **only if** the human decision says go-live requires PDF; otherwise ADR-defer.
**GATES:** pytest pass + test asserting xlsx bytes > 0 and by-gas totals match Calculation sums; verify.sh backend PASS.

### E3-2 — SBTi real progress (backend + small frontend)
**READ:** `emissions/serializers.py:290-306`, `emissions/services.py:167-168,238-254,989-1016`.
1. Endpoint `targets/{id}/progress/` exposing `TargetService.get_progress` (% achieved, trajectory vs target).
2. `_build_sbti_trajectory` uses the SBTiTarget table (drop hardcoded 50%-by-2030); baseline from `ReportingPeriod.is_baseline` (drop hardcoded 2020 fallback except as default).
3. SBTiTargetsPage: progress bars from the endpoint.
**GATES:** pytest + progress math test; lint/test/build PASS.

### E3-3 — Calculation integrity (backend)
**READ:** `emissions/models.py:624-776`, audit §8-M1/M2.
1. Enforce factor validity: `valid_from`/`valid_to` checked against activity date in `calculate_for_row`; expired/mismatched → row flagged, counted, reported in audit (not silently calculated).
2. Fix missing `is_active` filter on default-factor lookup (`models.py:656`).
3. Recalc policy: supersede instead of delete — keep previous Calculation rows marked `superseded_by` (new nullable FK) or equivalent; recalc audit stores before/after totals.
4. Factor edit → mark affected Calculations stale (service + flag on model); surface "N stale calculations" in dashboard summary endpoint.
5. ADR: factor versioning pattern (new-row-per-version recommended).
**GATES:** pytest + tests (expired factor rejected, recalc preserves history, stale flag set).

### E3-4 — Auto-calculate (backend)
1. `post_save` on DataRow → `transaction.on_commit` → recalc affected rules **only** when the table's rule has `auto_calculate=True` and setting `EMISSIONS_AUTO_CALC` enabled; guard against recursive loops; document sync behavior (async = future ADR).
**GATES:** pytest + test: row save triggers calc exactly once; flag off → no calc.

### E3-5 — Unified audit UI (frontend)
1. AuditLogPage tabs: Role assignments (existing) + Calculation audits (`calculation-audits/`) + Schema changes (`dataschema/schema-logs/`). Reuse existing table primitives.
**GATES:** lint/test/build PASS; each tab renders live data (manual note).

### E3-6 — Analytics truthfulness (frontend)
1. Date-range pickers send real start/end params (not just `endDate.year()`); backend honors them (small backend assist if missing).
2. Compare button: implement or remove. Yearly-comparison: consume the endpoint in AnalyticsDashboard or remove the endpoint (decide, note).
3. Delete dead client fns (`fetchYearlyComparison`, `fetchCalculationDetail`) after the above.
**GATES:** lint/test/build PASS.

---

## E4 — Frontend hygiene & design system (frontend-worker, DeepSeek-V3) · M — can run parallel with E2/E3 backend

**READ:** audit §6 (full dead-code list), `src/api/api.js`, `src/components/Page/PageHeader.jsx`, `src/components/layout/PageHeader.jsx`, `src/theme/carbonTheme.js`, `src/constants/terminology.js`, `.env.example:12-14`.

**TASKS:**
1. Kill the 4 raw-fetch violations (`RegisteredAppsPage.jsx:23,41`, `SettingsPage.jsx:192,265`) → apiFetch; consolidate AuthContext token refresh onto the api.js helper (one refresh implementation).
2. Dead purge (audit §6 list — ~25 files): 6 unrouted pages, legacy Layout chain (`Layout.jsx`/`Sidebar.jsx`/`SidebarMenu.jsx`), dead Navigation/Loaders/Inputs components, `dq/DQMetricsPanel`, `Feedback/StatCard`, `widgets/*`, dead hooks, `App.jsx:9` unused import + `VITE_USE_SHELL_LAYOUT`, `public/favicon.ico:Zone.Identifier`, `public/vite.svg`.
3. PageHeader merge: ONE primitive (keep `components/Page/PageHeader.jsx`, **remove its Breadcrumbs**); migrate `components/layout/PageHeader` consumers; remove `breadcrumbs` prop usage on MyDataPage; update `components/detail/DETAIL_PAGE_PATTERN.md`.
4. Token debt: add chart palette to carbonTheme; refactor `AnalyticsDashboard.jsx` (73 hex) + `EmissionsDashboard.jsx` (33 hex) to theme; then remaining sx hex 34→0 and px 52→0 (verify.sh now counts them); `App.jsx:144` inline style; fold `theme/carbonDesign.jsx` into carbonTheme (one token source).
5. Terminology sweep: route all user-visible labels through `constants/terminology.js`; fix "Module" labels (Breadcrumbs, StatusBar, CarbonConsole, TableManager, …) and "Schema Admin" label/route text.
6. VITE_BASE: canonical = `/carbon/`; fix `.env.example` misleading warning; centralize URL joins (no `${VITE_BASE}login` string concat — helper with single slash semantics).
7. Tests: 8 → ≥25 (shell smoke, carbon pages render, apiFetch 401-refresh unit test).
**DO NOT TOUCH:** `src/api/api.js` public signature, backend, manifest nav structure (E2-F1 owns guard alignment).
**GATES:** lint 0 errors; `npm test` ≥25 pass; build PASS; `grep -rn "#[0-9a-fA-F]\{6\}" src/pages src/components --include=*.jsx | wc -l` → 0 (theme/assets exempt); verify.sh frontend PASS.

---

## E5 — Backend hygiene & platform coverage (backend-worker, DeepSeek-V3) · M — after E2 backend

**READ:** audit §5, `dq/views.py`, `dataschema/views.py`, `accounts/views.py`, `catalog/views.py`, `mdm/views.py`, `backend/requirements.txt`, `backend/pytest.ini`.

**TASKS:**
1. Services extraction (views thin): dq (14 ORM sites) → dq/services.py; dataschema (13); accounts (13); catalog (10 — its services.py is a 17-line facade, make real); mdm (9); create `core/services.py`. Target: zero `*.objects.*` in any views.py except trivial `get_object_or_404`.
2. Permission dedup: single `ReadAnyWriteAdmin` + `AdminOrSuperuserOnly` in `accounts/permissions.py`; catalog/mdm/dq import from there.
3. Remove mdm permissive fallback (`mdm/views.py:76-79`) → restrictive empty queryset + test.
4. Coverage: connections/evidence/importexport 0 → CRUD + permission + masking tests; suite 329 → ≥400.
5. Seeder consolidation: delete loose root scripts (`seed_*.py` ×5, `transport_analysis.py`, `profile_endpoints.py`, `_test_*.py` ×2); `deploy_aastmt_carbon.py` → management command; surviving scripts use logging, not print (188 prints die with the files).
6. requirements: verify-zero-imports then drop `tenacity`, `colorlog`, `factory-boy`, `numpy`; wire `CACHES` to Redis (keeps `redis` dep honest, matches config) with locmem fallback for tests; pin drf-yasg, gunicorn, pytest, pytest-django, pytest-asyncio, pytest-cov.
7. Deprecations: `CheckConstraint.check`→`.condition` (`emissions/models.py:69`); note drf_yasg renderer deprecation (drf-spectacular migration = ADR note only).
8. OPTIONAL: rename `importexport.ExportProject` → `ExportDefinition` (+ migration) to bury the banned noun.
**GATES:** pytest ≥400 pass; `grep -rn "\.objects\." backend/*/views.py | wc -l` → ≤5 (documented exceptions); `grep -rn "is_staff\|is_superuser" backend/*/views.py | wc -l` → 0; verify.sh backend PASS.

---

## E6 — Docs, archive & deployment readiness (devops-worker + Master) · M — last

**TASKS:**
1. Archive: 29 root historical files → `docs/archive/phases-2026-07_08/` (list in audit §4); plans/ completed set likewise; stamp `CARBON_SELF_CONTAINED_ARCHITECTURE.md` **REJECTED** and `CARBON_PRODUCTION_ROADMAP.md` **SUPERSEDED** in their headers.
2. `docs/index.md` rewrite — index only CURRENT docs (audit §3 list); delete orphans (`reading-templates.md`, `DEEPSEEK_VSCODE_COPILOT_PROFILE.md`; `MASTER-WORKER-PROTOCOL.md` — superseded by `.ai-toolkit/universal/handoff.md`); refresh `README.md` (real dir names, live links, drop MongoDB).
3. Fix doc data conflicts: single grid factor (per human decision), deployment totals, rate limits, ports/prefix; purge pgvector from `STRATEGY_DATA_TRUST_PLATFORM.md:96` + `PLATFORM_APP_MODEL.md:79`; fix `EXECUTIVE_REPORT_AAST.md` ai-copilot claim; fix `CARBON-DESIGN.md` stale §9.
4. Deployment: fill PROD_* in project.config.md (human supplies); audit backend env template vs settings.py; production runbook (gunicorn + nginx from SECURITY_DEPLOYMENT Part 2, swagger-off proof, migrations, collectstatic, backup note); validate `docker-compose.yml` on a docker-enabled host.
5. CI per human decision: GitHub Actions (lint + vitest + pytest + verify.sh) or documented local-gate runbook.
6. ADRs (Master writes): notifications model, period-lock design, factor versioning, group-name source of truth, export audit, (E3-1 PDF if deferred).
7. Close-out: `./.ai-toolkit/scripts/scan.sh`; `./.ai-toolkit/scripts/retro.sh`; verify.sh **full** green; map QA-plan P13/P15/P16 → executed E-phases in `CARBON_QA_ENTERPRISE_VALIDATION_PLAN.md` header.
**GATES:** verify.sh full PASS; `grep -rln "8000\|5173\|/api/v1" docs/*.md | wc -l` → 0 outside archive; index covers every non-archive doc; deployment checklist signed by human.

---

## What "done" looks like (enterprise gate)

- verify.sh full PASS, and this time it means it.
- Carbon app: verification works end-to-end from UI, periods enforce locks, notifications fire,
  import/export jobs execute, Excel GHG inventory downloadable with audit record, SBTi progress real.
- 0 lint errors, ≥400 backend tests, ≥25 frontend tests, CI or runbook enforcing both.
- No secrets in docs/git, no tracked uploads, swagger dark in prod, RBAC groups consistent
  between deploy seed and permission code.
- docs/ indexes only the truth; root holds ≤5 .md files.
