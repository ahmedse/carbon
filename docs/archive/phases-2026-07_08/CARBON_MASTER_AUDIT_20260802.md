# CARBON MASTER AUDIT — 2026-08-02

**Auditor:** Master Architect (AI toolkit role)
**Method:** registry regeneration + 5 parallel audit streams (docs, plans/root, backend, frontend, live verification gates) + toolkit self-inspection
**Scope:** `docs/` (34 files + diagrams), `plans/` (22 files + carbon-phase tree), root (38 .md files), `backend/` (10 apps), `carbon-frontend/src/`, `.ai-toolkit/`, live services and test/build/lint gates
**Predecessor:** `CARBON_COMPLETE_AUDIT_20260729.md` (superseded by this document)

---

## 0. Executive Summary

The platform is **functionally healthy but operationally blind**: all services run, 329 backend
tests pass, frontend builds — yet the verification gate (`verify.sh`) reports PASS on failing
gates, so this health was luck, not proof. The codebase is clean on its historic removals
(tenant, Project, ai_copilot, SQLAlchemy, ChromaDB — all verified gone from code), but three
systemic problems remain:

1. **Trust infrastructure is broken** — verify.sh false-passes, no CI exists, the secret guard
   hook is not wired, and quality gates are decorative.
2. **Security posture has real holes** — plaintext passwords in docs, 20 uploaded files tracked
   in git, permissive RBAC fallback in mdm, ~20 inline auth checks, Swagger live in production,
   raw `fetch()` auth-bypass regression in live admin pages.
3. **Documentation actively misleads** — ~17 of 34 docs stale (two fossil layers), `index.md`
   indexes only the stalest cluster, four conflicting port/prefix "truths", removed concepts
   (tenant/Project/pgvector) presented as live, three colliding phase-numbering schemes.

**Bottom line:** not yet enterprise-deployable. The gap list is known, bounded, and sequenced in
`plans/CARBON_ENTERPRISE_READINESS_PLAN.md`.

---

## 1. System Health & Verification Gates (live run, 2026-08-02 ~15:15 UTC)

| Gate | Result | Evidence |
|---|---|---|
| Services (`./manage.sh status`) | ✅ | backend :8009 (PID 76149), frontend :5179 (PID 76200), PostgreSQL up |
| `manage.py check` (correct venv) | ✅ | 1 benign warning (`urls.W005` namespace 'carbon' not unique) |
| `makemigrations --check --dry-run` | ✅ | No changes detected |
| Backend tests (`pytest --reuse-db -q`) | ✅ | **329 passed** in 71.5s (2 deprecation warnings: `CheckConstraint.check`→`.condition` at `emissions/models.py:69`; drf_yasg renderer) |
| Frontend unit tests (`npm test`) | ✅ | 3 files / **8 passed** (Vitest 4 + RTL) |
| Frontend build (`npm run build`) | ✅ | 10.2s; mui chunk 622 kB (>500 kB warning) |
| ESLint (`npm run lint`) | ❌ | **7 errors / 58 warnings** — errors: `src/api/api.js:13,69,80,215,225,275` (unused vars, `process` undef), `src/components/NetworkStatusBanner.jsx:5` |
| `verify.sh backend` | ❌ **false-pass** | Ran a *foreign project's* Python (gigacast venv via leaked `VIRTUAL_ENV`; `backend/venv` doesn't exist) → `ModuleNotFoundError: pythonjsonlogger`, then printed `GATE PASSED` |
| `verify.sh frontend` | ❌ **false-pass** | Lint failed (7 errors), printed `GATE PASSED` anyway — `FAIL=1` lost in subshell |
| `verify.sh antipatterns` | ✅ w/ warnings | raw fetch at `RegisteredAppsPage.jsx:23,41`; 187 `print()` in backend root scripts |
| Docker validation | ⚠ skipped | Docker Desktop WSL integration inactive in this environment |

**P0 tooling defects:** (a) `verify.sh` venv resolution — expects `backend/venv`, real venv is
repo-root `.venv`; (b) `FAIL=1` set inside `( … )` subshells never propagates → GATE PASSED on
genuine failures. Any workflow trusting this gate is flying blind.

---

## 2. Critical Findings (act first)

1. **RBAC enforcement inconsistent + partially permissive.** ~20 inline `is_staff`/`is_superuser`
   checks bypass the permission-class proxy model (`dq/views.py` ×8, `mdm/views.py` ×3,
   `emissions/views.py` ×3 incl. raw `groups.filter(name='admins_group')` at :97/:115,
   `dataschema/views.py` ×3, `core/views.py` ×2, `accounts/views.py` ×2, `catalog/views.py` ×1).
   `mdm/views.py:76-79` has an explicit **"show all reference sets (permissive mode)… TODO"**
   fallback when a user has no scoped roles. 27 view classes sit on bare `IsAuthenticated`.
   `ReadAnyWriteAdmin` is **triplicated** (`catalog/permissions.py:6`, `mdm/permissions.py:7`,
   `dq/permissions.py:6`) and can drift.
2. **ReportingPeriod verification lifecycle lives in views** (`emissions/views.py:85-130`):
   state transitions + `VerificationRecord.objects.create` + inline group authorization, no
   model-level transition guards — on the platform's most audit-sensitive workflow.
3. **Auth-bypassing raw `fetch()` in live admin pages** — `RegisteredAppsPage.jsx:23,41` and
   `SettingsPage.jsx:192,265` hand-roll Bearer headers, no 401 refresh (the exact bug class fixed
   in commit fd82d77; regressed).
4. **Committed runtime/upload data** — 20 files tracked under `backend/dataschema_uploads/`
   (15) and `backend/mediafiles/` (5, incl. evidence PDFs) despite correct `.gitignore` rules.
   Needs `git rm --cached` + history decision.
5. **Plaintext passwords in docs** — `docs/QUICKSTART_DEPLOYMENT.md:77-84` and
   `docs/DEPLOYMENT_PLAN_AASTMT_CARBON.md:798-835` print passwords for 7 accounts incl. the
   platform superuser.
6. **Swagger live in production** (`config/urls.py:73`, unconditional; `drf_yasg` in base
   INSTALLED_APPS). Emissions URLs **double-mounted**: legacy `api/v1/carbon/` +
   `carbon-api/carbon/` (`config/urls.py:65-66`). `DEBUG`/`DJANGO_ENV` gating mismatch
   (`settings.py:85-86` vs `urls.py:79`) → startup ImportError if DEBUG=True in production env.

---

## 3. Documentation Audit (`docs/` — 34 files + diagrams)

**Verdicts: 13 CURRENT · ~17 STALE · 3 ORPHAN · 1 CONTRADICTED.**

- **CURRENT (Jul-30 Data Trust generation):** TERMINOLOGY, DESIGN_DATA_TRUST_CORE,
  DESIGN_ORG_ACCESS_MODEL, DESIGN_UI_ARCHITECTURE_A5, DESIGN_ROW_DETAIL_PAGE_REFINED,
  STRATEGY_DATA_TRUST_PLATFORM, PLATFORM_APP_MODEL, ADMIN_USER_GUIDE, CARBON-DESIGN,
  QUICKSTART_DEPLOYMENT, DEPLOYMENT_PLAN_AASTMT_CARBON, env.md, PLAN_DATA_TRUST_PHASES (as history).
- **STALE fossils:** (i) May-2025 legacy cluster — `design.md`, `data-model.md`, `workflows.md`,
  `roadmap.md`, `index.md`, all 8 `diagrams/*.mmd` (Project/Cycle/ModuleData + TENANT ERDs);
  (ii) Jan-2026 expert-review bundle (~115k words) — `TECHNICAL_REVIEW_2026.md`,
  `EXPERT_REVIEW_SUMMARY.md`, `MISSING_FEATURES_IMPLEMENTATION.md`, `TESTING_QA_GUIDE.md`,
  `SECURITY_DEPLOYMENT.md` (all sample code imports removed `Tenant`/`Project`);
  (iii) config cluster — `CONFIGURATION_ARCHITECTURE.md`, `CONFIGURATION_BEST_PRACTICES.md`
  (ai_copilot routes, 8000/5173, `/api/v1/`); `api.md` (wrong prefix, LLM chat artifacts);
  `debug.md`, `deployment.md`.
- **ORPHAN:** `reading-templates.md` (Poe chat export, never-built models, poe.com citations),
  `DEEPSEEK_VSCODE_COPILOT_PROFILE.md`, `MASTER-WORKER-PROTOCOL.md` (tooling doc in product docs).
- **CONTRADICTED:** `EXECUTIVE_REPORT_AAST.md` — markets the removed ai_copilot as a live feature.

**Cross-cutting:**
- `index.md` indexes exactly the 9 stalest docs, omits 25 (incl. TERMINOLOGY.md); links to
  nonexistent `../install.md`, `../progress.md`.
- Four conflicting port/prefix truths: 8000+`/api/v1/`; 8001; bare `/api/`; real 8009+`/carbon-api/`.
  Emissions namespace documented 3 ways; actual `/carbon-api/carbon/` (`config/urls.py:66`).
- Removed concepts presented as live: tenant/multi-tenancy (10+ files), Project model (7+ files),
  **pgvector reappears** in `STRATEGY_DATA_TRUST_PLATFORM.md:96` + `PLATFORM_APP_MODEL.md:79`
  despite the removal decision.
- Doc-vs-doc data conflicts: Egypt grid factor 0.4584 vs 0.527 vs 0.475 (three seeds, three
  values); expected Jan-2026 totals 59.94 t vs 118.7 t; rate limits "30/60s" vs actual
  `5/min login, 100/h anon, 1000/h user` (`settings.py:181-185`).
- **Zero documentation:** `connections`, `evidence`, `importexport` apps; platform-apps registry
  + `useEnabledApps`; current RBAC surface (`viewers_group`, `carbon_*` groups, `/admin/groups`,
  `/admin/role-matrix`); dataschema as-built (TableRelation, GovernancePolicy, soft-delete 405).
- LLM-artifact leakage: `api.md` opens/closes as a chat transcript; `env.md:1-10` duplicated
  header artifact.
- `CARBON-DESIGN.md` undersells reality: "DQ execute action is stub" — implemented
  (`backend/dq/views.py:181-187`).

---

## 4. Plans & Root-Level Audit (60 files)

**Three colliding phase-numbering schemes:** carbon-phase 00–08 (Jul 26–29) · remediation P1–P9
(Jul 31) · QA-plan P10–P16 (Aug 1–2). "P8" exists twice; **"P13/P14" labels are burned** —
executed P13 = error handling, executed P14 = N+1/DQ lockdown, while QA-plan P13 (test coverage
80%) and P14 (architecture) were never run under those labels.

**Phase status (proof-based):**
- Done with full proof: carbon-phase 00–03, 08 · P1–P6 · P8–P9 · P10a-FIX · P11 · P12 · executed-P13.
- Done, proof gaps: P7 (commit only), P10c (commit only), executed-P14 (commit only),
  carbon-phase 04/06/07-G2 (pages exist, no result records), P5-G3/P6-G3 (artifacts only).
- Partial: P10a (3 of 5 roles tested), P10b (route #18 untested, Tier 1 admin-only),
  **P12-G4 Lighthouse never actually run** (no Chrome; "estimated" scores recorded as PASS).
- **Open:** QA-plan P13 (coverage 80%), P15 (feature completeness), P16 (a11y/UX).
- Record-integrity: 3 result files carry impossible dates (e.g. `TASK_RESULTS_P13.md` dated
  2026-07-29, committed 2026-08-02); `TASKS-P10a-FIX-title.md` spec says 11 files, lists 10.

**Most current roadmap:** `CARBON_QA_ENTERPRISE_VALIDATION_PLAN.md` (v2.0, 2026-08-01) — its
P10–P12 match reality; §13/§14 "current state" tables were stale on arrival.

**Architecture plan contradictions (settled, but docs unmarked):**
- DataTrust-architecture (DataRow generic) **won** vs self-contained typed models — but
  `plans/CARBON_SELF_CONTAINED_ARCHITECTURE.md` sits unmarked as rejected.
  `CARBON_ARCHITECTURE_TRADEOFFS.md` recommended Hybrid Option C; reality is Option A.
- Two-tier admin (PLATFORM_RBAC_ADMIN_ARCHITECTURE) **won** vs per-app `carbon:*` manifest roles
  (CARBON_PRODUCT_APPS_ARCHITECTURE) — never materialized.
- API namespace: plans say `/api/v1/*`; reality `/carbon-api/` + a legacy duplicate mount.
- UI terminology audit (CARBON_UI_TERMINOLOGY_ENTERPRISE_AUDIT) never decided either way.

**Root clutter:** 29 of 38 root .md files are completed historical records → archive to
`docs/archive/phases-2026-07_08/` (precedent: AUDIT_CLEANUP_MANIFEST already removed 27 once).
Keep at root: `README.md` (itself stale — dead links, wrong `frontend/` dir name, "MongoDB
planned"), `CARBON_QA_ENTERPRISE_VALIDATION_PLAN.md`, `TASKS.md` (stuck on closed Phase 08).
Misplaced: `plans/TASK-RESULTS-P12-FRONTEND.md` + `TASK-RESULTS-P12-LIGHTHOUSE.md` belong with
the root P12 set. Plans/ keep-list: DATA_TRUST_ARCHITECTURE, ARCHITECTURE_TRADEOFFS,
PLATFORM_RBAC_ADMIN_ARCHITECTURE, WORKFLOW_SPECIFICATION, WORKFLOWS_AND_PROCESSES.

---

## 5. Backend Audit (10 apps, all installed & routed)

**Clean (verified):** timezone discipline (33 `timezone.now()`, zero naive calls); tenant /
Project / ai_copilot / SQLAlchemy / alembic / ChromaDB fully gone from code; core→emissions
import direction respected (one test-only exception: `catalog/tests/test_scoped_access.py:14`);
no unmigrated model changes; 329 tests green.

**Violations by hard rule:**
- **Rule 1 (thin views): 80 direct ORM call sites across 8 view files.** Worst:
  `emissions/views.py` (15 — header claims "views are thin"), `dq/views.py` (14 — 728-line views
  bigger than its 535-line services), `dataschema/views.py` (13), `accounts/views.py` (13),
  `catalog/views.py` (10; catalog services.py is a 17-line facade). `core` has **no services.py**.
- **Rule 3 (permissions as proxies):** ~20 inline checks (§2.1); permission-class triplication;
  27 view classes on bare `IsAuthenticated` with imperative scoping in `get_queryset`.
- **Rule 4 (state machines): partial.** Only `mdm.ReferenceSet` has `VALID_LIFECYCLE_TRANSITIONS`
  + `transition_to`. ReportingPeriod / VerificationRecord / ImportJob / ExportJob / DataSource:
  STATUS_CHOICES only, transitions hard-coded in views. DataTable/DataRow/DQRule: boolean flags.
- **Rule 5 (API prefix):** legacy `api/v1/carbon/` double-mount (`urls.py:65`); evidence mounted
  at bare prefix root without `app_name`; swagger unconditional; dead commented routes
  (`urls.py:51,55`).
- **Rule 6 (no print):** 188 `print()` — ALL in 10 loose root scripts (seed_all 42,
  seed_aastmt_data 31, deploy_aastmt_carbon 22, transport_analysis 22, seed_users 19, …).
  App code / management commands / tests are clean.

**Structural findings:**
- **Seeder sprawl:** 5 loose root seeders duplicating same-named management commands
  (`seed_aastmt_data.py` vs `core/management/commands/seed_aastmt_data.py`; `seed_users.py` vs
  `accounts/populate_demo_users.py`; `seed_all.py` 33KB vs `emissions/seed_demo_data.py`). No
  canonical seeder; zero test coverage; drift/reintroduction risk.
- **`connections`, `evidence`, `importexport`: installed, routed, undocumented, ZERO tests.**
  `connections/models.py:34` `connection_config` JSONField will hold plaintext DB/API credentials.
  `importexport/models.py:11` `ExportProject` resurrects the banned "Project" noun.
- **requirements.txt:** unused: `redis` (no CACHES configured), `tenacity`, `colorlog`,
  `factory-boy`, `numpy` (only loose script), `sqlparse`; 6 unpinned (drf-yasg, gunicorn,
  pytest, pytest-django, pytest-asyncio, pytest-cov).
- `_test_governance_rbc.py` / `_test_swagger_direct.py` at backend root are NOT pytest-collected
  (`_test` prefix mismatches `python_files = test_*.py`) — dead manual scripts tracked in git.
- Cosmetic tenant echoes: `dataschema/models.py:2` docstring, `seed_demo_data.py:5` comment,
  `accounts/models.py:2` comment; `.gitignore:130` stale `backend/chroma_db/`.
- 20 runtime upload files tracked in git (§2.4); `backend/combined-apps_nginx.example`,
  `backend/dev-guide-v1.1.md` tracked clutter.

---

## 6. Frontend Audit (React 19.1 + MUI v7.1 + Vite 6 — config says 18/v5-6)

**Clean (verified):** MUI Grid fully migrated to v7 `size` API (zero legacy `item`); state
Context-only (no redux/zustand); single `createTheme` (`carbonTheme.js:90`) applied in main.jsx;
Router v6 patterns; `dist/` untracked.

**Violations by hard rule:**
- **Rule 10 (apiFetch only):** 11 raw `fetch()` outside api.js; **4 clear violations** —
  `RegisteredAppsPage.jsx:23,41`, `SettingsPage.jsx:192,265` (manual Bearer, no refresh).
  AuthContext duplicates api.js refresh logic. Pulse-host calls = by-design exception.
- **Rule 8 (tokens only):** 34 hex / 52 px in `sx` (11/~30 files); **~237 hardcoded hex across
  37 files total** — worst: `AnalyticsDashboard.jsx` 73, `EmissionsDashboard.jsx` 33 (chart
  palettes bypass `theme.palette` → dark mode silently broken on flagship dashboards),
  DataHubHome 9, ModuleLandingPage 9, AuditLogPage 9. `App.jsx:144` inline hex style.
  `theme/carbonDesign.jsx` is a second token/component source.
- **Rule 9 (one breadcrumb):** `components/Page/PageHeader.jsx:10-22` **renders its own
  MUI `<Breadcrumbs>`**; live consumer `MyDataPage.jsx:433,440,585` → double breadcrumbs in
  production. Stale doc `components/detail/DETAIL_PAGE_PATTERN.md:65,195` still teaches the
  pattern.
- **Rule 4 (compose, don't fork):** TWO `PageHeader` primitives (`components/Page/` vs
  `components/layout/`); TWO detail frameworks (`detail/BaseDetailPage` = 9 pages vs
  `entity/EntityDetailShell` = 4 pages); TWO StatCards (`Cards/` live, `Feedback/` dead).
- **Rule 7 (terminology):** "Module" visible in live UI (`shell/Breadcrumbs.jsx:187`,
  `StatusBar.jsx:56`, `CarbonConsolePage.jsx:48`, +7 more); "Schema Admin" in live breadcrumbs
  (`Breadcrumbs.jsx:182` + `/schema-admin/*` route). `constants/terminology.js` imported by only
  2 files.

**Dead surface (~25 files):** 6 unrouted pages (DomainsPage, GlossaryPage, TagsPage,
SchemaCatalogPage, SchemaManagerPage, DataOwnerPortalPage 430L); legacy Layout chain
(`Layout.jsx`/`Sidebar.jsx`/`SidebarMenu.jsx` 664L, reachable only via unused import
`App.jsx:9`; hosts "Schema" tooltip); dead components (Navigation/*, Loaders/*, Inputs/*,
`dq/DQMetricsPanel`, `Feedback/StatCard`, `widgets/*` — `EmissionsTrendChart.jsx` has a **broken
import** of nonexistent `../components/ErrorBoundary`); dead hooks (useEmissionsDashboard,
useCarbonConsole, useMyData); dead `VITE_USE_SHELL_LAYOUT` flag.

**Quality gates:** 8 tests (2 near-zero-value API signature checks); **no CI at all**
(`.github/` = only copilot-instructions.md); `VITE_BASE` ambiguity — `.env.example:12-14` warns
a `/carbon/` value double-prefixes routes to `/carbon/carbon/*` while `api.js:166` /
`AuthContext.jsx:300` string-concat `${VITE_BASE}login`; junk: `public/favicon.ico:Zone.Identifier`
tracked, boilerplate `vite.svg`.

---

## 7. AI Toolkit Audit

- **`project.config.md` was two files in one** (old `#`-comment block lines 1–84 + KEY=VALUE
  86–227) with conflicts: `BACKEND_VENV=backend/.venv/` (wrong — root `.venv`),
  `FRONTEND_UNIT=NONE` (false — Vitest + 8 tests), React 18/MUI v5-6 (actual 19.1/v7.1),
  "310 tests" (329), sx debt 29/49 (34/52), `ARCH_CORE_APPS` missing connections/evidence/
  importexport. **→ fixed this pass (single format, corrected facts, worker model policy added).**
- **`verify.sh` broken** (§1): wrong venv + subshell FAIL loss → false GATE PASSED. Also its
  antipattern greps are too narrow (passed "no hex in components" while ~237 exist; counted
  root-script prints as app code). **→ fixed this pass; now propagates failures.**
- **Guard hook NOT wired:** `.github/hooks/guard-secrets.json` referenced by config + ROLES.md +
  HOW-TO-USE ("enforcement is LIVE") **does not exist**. `guard.sh` exists and works manually.
  **→ docs corrected this pass (claims downgraded to "available, wiring pending").**
- **ROLES.md table listed 8 roles; `roles/` has 10** — qa-validator + product-designer
  undocumented. **→ fixed; model column moved to DeepSeek roster.**
- **`master-architect.md` carried a stale "Project Architecture (Gigacast)" section**
  (ai_engines/aihub/datahub_v2 — a different project). **→ replaced with generic
  layer-constraints section.**
- **ADR-0002 (Command pattern):** config claimed "P5 COMPLETE"; the ADR itself defers
  implementation — **no Command classes exist in code**. Scorecard should read "ADR only".
- Registry regenerated 2026-08-02 (scan.sh) — current.

---

## 8. Carbon Domain App — Module Completeness

Dedicated 12-module audit of `backend/emissions/` + supporting apps + the frontend carbon app
(manifest, pages, API client). Verdicts: COMPLETE / PARTIAL / STUB / MISSING.

| # | Module | Verdict | Key evidence & gaps |
|---|---|---|---|
| M1 | GHG data model & scopes | **COMPLETE (w/ gaps)** | Scope 1/2/3 via `core.Module.scope` + denormalized on factor/calculation. Factors: 9 categories, per-gas CO2/CH4/N2O components, country/region, source, validity dates. GWP: AR5+AR6, 20yr+100yr, 12 gases seeded. Gaps: `GWP.get_gwp()` **never called** (factors must be pre-computed CO2e); no HFC/PFC/SF6 component fields; no biogenic CO2 handling; `valid_from/valid_to` **never enforced** (`models.py:624-711`) |
| M2 | Calculation engine | **COMPLETE core, material gaps** | `CalculationEngineService` (services.py:378-492): validation, batch, audit trail, zero TODOs. Dynamic per-row factor selectors. Gaps: **`auto_calculate` flag is dead** (no signal; manual admin trigger only); formula rule_type unimplemented; **no factor-edit recalc policy** (recalc deletes+recreates, destroys history); all synchronous (no Celery); default-factor lookup misses `is_active` filter (`models.py:656`) |
| M3 | Reporting period lifecycle | **PARTIAL** | 7 statuses; submit/verify/reject actions only. **No transition actions for draft→open→locked→closed** (raw PATCH via UI dropdown, no state machine). **No period-lock enforcement on data entry** (dataschema never references ReportingPeriod). Only `closed` blocks calculation; locked/verified don't. Periods are global, not org-scoped |
| M4 | Verification workflow | **PARTIAL — UI broken end-to-end** | Backend records work (tested). Frontend calls `verifications/{id}/verify` on a **ReadOnlyModelViewSet** → 405 (`emissions-extended.js:317-334` vs `views.py:861`); "Pending Review" tab can never show records (none created on submit); grid expects fields serializer lacks; no evidence-in-context link for verifiers; `unique_together(period, verifier)` → IntegrityError 500 on re-verify |
| M5 | SBTi targets | **PARTIAL** | Model + org-scoped CRUD real; page API-backed. Progress half-stub: serializer returns raw current-year emissions only; richer `TargetService.get_progress` has **no endpoint**; `YearlyComparisonService._build_sbti_trajectory` **hardcodes "50% by 2030"** ignoring the target table; baseline hardcoded 2020 fallback |
| M6 | Reporting/exports | **PARTIAL** | Real aggregation from Calculation data (scope→category, org-subtree filter). **JSON + CSV-summary only — no PDF/Excel**, no by-gas breakdown (despite gas fields stored), `include_dq_status` persisted but unused, grouping choices mostly inert. Stale `format=` param bug (`api/emissions.js:38` vs `views.py:469`). No export audit record |
| M7 | Data entry & import | **Entry COMPLETE; importexport STUB** | DataEntryPage/MyDataPage real, dataschema bulk-import + template work. **importexport ImportJob/ExportJob are shells** — services only create `pending` rows; no worker/signal/command ever executes them (`importexport/services.py:9-45`); scheduled exports declared, unimplemented |
| M8 | DQ integration | **PARTIAL** | DQ engine covers carbon tables generically; calc triggers profile+DQ *after* calc, non-blocking. **No DQ gating** — can calculate on failed-DQ data; AASTMT seed has zero DQ rules. Dashboard `data_quality_score` is a **fabricated heuristic** (`services.py:73`), unrelated to DQ results |
| M9 | RBAC & org scoping | **PARTIAL** | Read scoping real (module-visibility, owner endpoints, SBTi queryset). **Group naming fragmented**: deploy creates `carbon_admin` (recognized **nowhere** in permission code); code protects `carbon_data_owners_group`/`carbon_analysts_group` (deploy never creates). **Write hole**: `CalculationViewSet` create open to any authenticated user (`views.py:211`). Verify/reject check raw Django groups, not ScopedRole. Frontend `AdminRoute` guards contradict manifest roles (analyst/data-owner pages gated to global admin) |
| M10 | Frontend carbon app | **COMPLETE except 2 broken flows** | All 15 manifest nav entries → real routed pages; **zero mock data** in any carbon page. Broken: VerificationPage (M4); CalculationsPage recalc buttons → non-existent `calculations/{id}/recalculate/` + `batch-recalculate/` (404). Analytics date-range sends only `endDate.year()` (cosmetic); "Compare" button has no handler |
| M11 | API surface | **PARTIAL** | Good coverage (dashboard, console, my-data, batch-calculate, audits, reports, evidence, bulk-import). Missing: recalculate endpoints (frontend expects), verifications actions, period open/lock/close transitions, target-progress endpoint, factor bulk-import, PDF/Excel download, job execution behind importexport |
| M12 | Enterprise features | **MOSTLY MISSING** | **No notifications anywhere** (no model, no send_mail). Single-step verify only (no per-org sign-off). AuditLogPage shows role assignments only; CalculationAudit has no UI; SchemaChangeLog not surfaced. No factor versioning. Yearly-comparison endpoint exists, **no page consumes it**. No uncertainty/DQ scoring on calcs. No unit registry. No async jobs |

**Top enterprise-readiness gaps (ranked):**
1. Verification workflow UI non-functional (the only approval gate can't be used)
2. No period-lock enforcement on data (lifecycle is advisory)
3. RBAC group fragmentation + Calculation create hole
4. No auto-calculation (dead flag; manual admin trigger only)
5. No notifications / approval chain beyond one step
6. importexport jobs are stubs
7. Reports: no PDF/Excel GHG inventory, no by-gas, no export audit
8. SBTi progress cosmetic
9. Calculation integrity: stale results on factor edit, history-destroying recalc, no versioning
10. Broken recalc buttons + dead analytics controls (first-session UX failures)

**Bottom line:** **Module-complete? Largely yes** — every declared module exists with real
models, endpoints, API-backed pages, zero mock data. But Verification (M4) is UI-broken,
importexport (M7) is a stub, period lifecycle (M3) half-wired. **Enterprise-feature-complete?
No** — a solid departmental tool, not yet an enterprise system. Deployment blockers for AASTMT:
working verification UI + evidence-in-context; enforced period locking; reconciled RBAC groups +
Calculation write hole closed; lifecycle notifications; real import/export execution. Then
PDF/Excel inventory + export audit, factor validity/versioning/recalc policy, auto-calculate,
real SBTi progress, unified audit UI.

---

## 9. Remediation Roadmap

Full phased plan with worker assignments and verification gates:
**`plans/CARBON_ENTERPRISE_READINESS_PLAN.md`** (E0 gate repair → E6 deployment).
Summary order: R0 verify.sh + lint → R1 security exposures → R2 RBAC + lifecycle →
R3 frontend regressions/dead code → R4 docs/archive/toolkit → R5 carbon-app gap closure →
R6 enterprise deployment.
