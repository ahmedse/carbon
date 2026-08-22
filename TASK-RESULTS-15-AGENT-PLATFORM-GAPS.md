# TASK-RESULTS-15 — Next-Gen AI Agent Platform: 5-Gap Implementation

Date: 2026-08-21 · Role: Master Architect (implementation) · Phase: gap-closure workstream · Source: "go do all" (Proposal #2 gap list), ADR-0013

---

## Executive Summary

**Verdict: PASS** — All five gaps implemented, lint-clean, backend check clean,
migration applied, and runtime wiring verified. One new justified migration
(`0019_plan_template`), no engine edits, no new apps.

| # | Gap | Surface | Result |
|---|-----|---------|--------|
| 1 | Output-quality drift dashboard | `/admin/ai/output-quality` | ✅ |
| 2 | Bounded retry/backoff | `plans_service._run_plan_frames` | ✅ |
| 3 | Plan templates | Workspace Tasks → Templates tab | ✅ |
| 4 | Run comparison (side-by-side diff) | `/admin/ai/runs` (Run A vs Run B) | ✅ |
| 5 | Non-data domain adapters (finance/hr/customer) | domain-protocol manifest seam | ✅ |

---

## Task Results

| # | Gate | Command | Result |
|---|------|---------|--------|
| 1 | Backend lint | `get_errors` on all modified files | ✅ No errors |
| 2 | Migrations in sync | `makemigrations --check --dry-run` | ✅ No changes detected |
| 3 | Apply migration | `manage.py migrate ai` | ✅ 0018 + 0019 applied |
| 4 | Django check | `manage.py check` | ✅ 0 issues |
| 5 | Domain unit tests | `pytest test_domain_{non_data,water,emissions}.py` | ✅ 50 passed |
| 6 | Plan/durable tests | `pytest test_plans.py test_durable.py test_plan_task.py` | ✅ 63 passed |
| 7 | Runtime route/domain check | `manage.py shell` (reverse + list_domains) | ✅ finance/hr/customer registered; compare/templates routes resolve |
| 8 | Frontend build | `npm run build` | ✅ built (26s) |
| 9 | Frontend lint | `eslint` on modified files | ✅ 0 errors (1 pre-existing warning in `AITaskPanel.jsx` polling effect) |
| 10 | Backend restart | `./manage.sh restart` | ✅ backend :8009, frontend :5179 |

---

## Files Changed

### Backend

| File | Change |
|------|--------|
| `backend/ai/observability_api.py` | `OutputQualityTrendView` + `"quality"` panel (Gap 1) |
| `backend/ai/ops_urls.py` | `quality-trend/` route (Gap 1) |
| `backend/ai/plans_service.py` | `_execute_plan_once` + bounded retry/backoff (Gap 2); `PlanTemplate` promote/list/instantiate (Gap 3) |
| `backend/ai/models/core.py` | `PlanTemplate(AppScopeMixin)` model (Gap 3) |
| `backend/ai/models/__init__.py` | export `PlanTemplate` (Gap 3) |
| `backend/ai/migrations/0019_plan_template.py` | generated migration (Gap 3) |
| `backend/ai/plans_api.py` | template serializer + `list_templates`/`promote_template`/`instantiate_template` (Gap 3) |
| `backend/ai/plans_urls.py` | `templates/` + `promote-template/` routes (Gap 3) |
| `backend/ai/durable_service.py` | `compare_runs` step-ledger diff (Gap 4) |
| `backend/ai/durable_api.py` | `compare` action (Gap 4) |
| `backend/ai/durable_urls.py` | `compare/` route (Gap 4) |
| `backend/ai/domain/finance.py` | `FinanceDomainAI` manifest-only adapter (Gap 5) |
| `backend/ai/domain/hr.py` | `HRDomainAI` manifest-only adapter (Gap 5) |
| `backend/ai/domain/customer.py` | `CustomerOpsDomainAI` manifest-only adapter (Gap 5) |
| `backend/ai/domain/__init__.py` | register finance/hr/customer (Gap 5) |
| `backend/ai/tests/test_domain_non_data.py` | tests for the three adapters (Gap 5) |

### Frontend

| File | Change |
|------|--------|
| `src/api/aiPulse.js` | `getQualityTrend` (Gap 1) |
| `src/pages/admin/ai/OutputQualityPanel.jsx` | new panel (Gap 1) |
| `src/App.jsx` | lazy route `/admin/ai/output-quality` (Gap 1) |
| `src/shell/ShellSidebar.jsx` | Observability → Output Quality link (Gap 1) |
| `src/api/aiWorkspace.js` | `promotePlanTemplate`/`listPlanTemplates`/`instantiatePlanTemplate` (Gap 3) |
| `src/shell/AITaskPanel.jsx` | Templates tab (save/list/use) (Gap 3) |
| `src/api/aiCatalog.js` | `compareRuns` (Gap 4) |
| `src/pages/admin/ai/RunTimelinePanel.jsx` | Run A vs Run B diff view (Gap 4) |

### Docs

| File | Change |
|------|--------|
| `.ai-toolkit/decisions/0013-ai-agent-platform-gap-closure.md` | new ADR |
| `.ai-toolkit/decisions/README.md` | index row for 0013 |

---

## Key Decisions & Gotchas

- **Gap 2 lives in `plans_service.py`, not `engine/`** — retry reuses public seams and a fresh SQLAlchemy session per attempt; it never bypasses the consent gate (`awaiting_approval` stops retry).
- **Gap 3 literal `templates/` routes declared before `"<str:pk>/"`** so the literal segment wins.
- **Gap 4 diffs `RunStep` rows by `step_index`, not serialized timeline event lists** — timestamp-fragile event diffing was rejected.
- **Gap 5 adapters are manifest-only and reject `table_id`** — non-data verticals have no tables to isolate; `DataIsolationGuard` pass-throughs are fine because no table is ever referenced.

---

## Verification Output

- `pytest` domain: **50 passed** · plans/durable: **63 passed**
- `manage.py check`: **System check identified no issues (0 silenced)**
- `npm run build`: **✓ built in 26.29s**
- `eslint`: **0 errors, 1 warning (pre-existing `react-hooks/exhaustive-deps` on the plan polling effect — not introduced by this workstream)**
