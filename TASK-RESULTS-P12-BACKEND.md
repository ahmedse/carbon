# TASK-RESULTS-P12-BACKEND.md — Backend N+1 Audit + Profiling

**Phase:** P12 — Backend N+1 Audit + Profiling · **Date:** 2026-08-02
**Executor:** Backend Worker (Copilot) · **Environment:** development (`DJANGO_ENV=development`, backend :8009, prefix `/carbon-api/`)
**Status:** ✅ COMPLETE — all gates pass (317 tests)

---

## G1 — select_related / N+1 fixes (DQ + MDM)

### Changes applied

| File | Location | Change |
|------|----------|--------|
| `backend/dq/views.py` | `FieldProfileViewSet.get_queryset` (~L73-80) | `FieldProfile.objects.all()` → `select_related('data_field__data_table__module')` (serializer touches `data_field.name`; org-scope filter traverses `data_field__data_table__module`) |
| `backend/dq/views.py` | `TableProfileViewSet.get_queryset` (~L104-111) | `TableProfile.objects.all()` → `select_related('data_table__module')` (serializer touches `data_table.name`) |
| `backend/dq/views.py` | `DQRuleViewSet.get_queryset` (~L136-154) | `DQRule.objects.filter(...)` → `select_related('data_field__data_table__module', 'data_table__module', 'created_by')` + `prefetch_related('results')` (serializer `created_by_name` + per-rule `results_count`) — applied to **both** superuser and org-scoped branches |
| `backend/mdm/views.py` | `ReferenceValueViewSet.get_queryset` (~L307-309) | `ReferenceValue.objects.all()` → `select_related('reference_set')` |
| `backend/mdm/views.py` | `OrgUnitViewSet.get_queryset` (~L491-494) | `OrgUnit.objects.filter(is_active=True)` → `select_related('parent').filter(is_active=True)` (serializer exposes `parent_name`) |

**Not touched (per task DO-NOT list):** `emissions/` app, any serializer, any permission class, `DQResultViewSet` (already optimized), `ReferenceSetViewSet` (already optimized), migration files (only silk's own migrations were applied), frontend.

### Audit findings — residual N+1 (requires serializer changes, out of scope)

1. **`DQRuleSerializer.get_results_count`** (`dq/serializers.py`) calls `obj.results.count()` per rule → per-object query even with prefetch (`.count()` on a prefetched manager returns `len()` only if cache already populated; `prefetch_related('results')` was added so the count is served from the cache — **resolved** via prefetch, no serializer change needed).
2. **`OrgUnitSerializer`** method fields `full_path` (ancestor walk), `children_count`, `descendants_count` (recursive BFS) → per-object queries (verified: `mdm/org-units/` = 22 queries for 7 units = 1 + 7×3). `select_related('parent')` removes the parent lookup; full elimination needs serializer changes.
3. **Observation (outside scope):** `dataschema/tables/` = 20 queries for 6 tables (residual N+1 in dataschema serializer); `accounts/scoped-roles/` = 14 queries.

## G2 — django-silk profiling

- Installed `django-silk==5.3.2` (venv + `backend/requirements.txt`), silk migrations applied, UI verified (`GET /silk/ → 200`).
- Gating (dev-only): `if DJANGO_ENV == "development" and not RUNNING_TESTS:` for middleware; silk URLs under the existing `if settings.DEBUG:` block in `backend/config/urls.py`.
- 15 endpoints profiled via `backend/profile_endpoints.py` (8 measured hits each, JWT auth). Full results + analysis: **`TASK-RESULTS-P12-PROFILE.md`**.

Summary of the 15 endpoints (client avg / silk server avg / SQL queries):

| Endpoint | avg ms | p95 ms | SQL queries |
|----------|-------:|-------:|------------:|
| carbon/dashboard/ | 47.3 | 51.2 | 6 |
| carbon/calculations/ | 43.1 | 47.3 | 3 |
| catalog/assets/ | 71.5 | 75.4 | 7 |
| accounts/users/ | 32.9 | 34.7 | 2 |
| accounts/scoped-roles/ | 65.7 | 71.7 | 14 |
| accounts/me/context/ | 43.0 | 53.8 | 5 |
| dq/rules/ | 42.2 | 44.3 | **2** |
| dq/results/ | 35.6 | 37.5 | **2** |
| mdm/org-units/ | 90.7 | 92.8 | 22 |
| mdm/reference-sets/ | 35.6 | 43.5 | 2 |
| dataschema/tables/ | 89.6 | 94.6 | 20 |
| dataschema/fields/ | 44.5 | 106.4 | 2 |
| carbon/targets/ | 65.0 | 81.0 | 11 |
| catalog/governance-policies/ | 33.0 | 34.9 | 2 |
| accounts/audit-log/ | 32.2 | 34.1 | 2 |

All 15 → HTTP 200; worst endpoint (org-units) still < 95 ms client-side.

## N+1 regression tests

**File:** `backend/core/tests/test_performance.py` (extended; 7 new tests → suite 310 → **317 passed**)

- `DQNPlusOneTest` (4 tests) — HTTP-level `CaptureQueriesContext` assertions that query count is **constant** as rows grow (3 → 8):
  - `field-profiles` list — actually `GET /carbon-api/dq/profiles/` (see deviation)
  - `table-profiles` list, `rules` list (bound ≤ 8), `results` list
- `MDMNPlusOneTest` (3 tests):
  - `reference-values` list — constant count
  - `org-units` — queryset-level: `select_related('parent')` evaluates in **1 query**; HTTP list 200 with bounded count (residual serializer N+1 documented)
- Shared `NPlusOneListMixin._assert_no_n_plus_one` (constant-count + absolute bound; avoids brittle exact counts because this project has no DRF default pagination).

**Test-data lesson applied:** OrgUnit `slug` is unique (empty string collides → always explicit slug); DataTable `unique_together (module, name)` → growth functions use a monotonically increasing seed.

## Gates

```
✓ python manage.py check                    — 0 errors (1 pre-existing url W005 warning)
✓ python manage.py makemigrations --check   — "No changes detected"
✓ python -m pytest -q --tb=short            — 317 passed (was 310) + 10 subtests, ~65s
✓ ./.ai-toolkit/scripts/verify.sh backend   — GATE PASSED
✓ ./.ai-toolkit/scripts/verify.sh antipatterns — GATE PASSED (warnings pre-existing; profile_endpoints.py is a CLI script, print() exempt)
✓ Backend left RUNNING on :8009; silk UI 200; API health ok
```

## Deviations from task template

1. **Task sample URL `GET /dq/field-profiles/` does not exist** — the registered route is `GET /carbon-api/dq/profiles/` (`dq/urls.py` registers `FieldProfileViewSet` under `profiles`). All tests and the profiler use the real route.
2. **Silk gating:** task said `if DEBUG:`; codebase convention is `if DJANGO_ENV == "development":` (debug_toolbar uses it). Used the convention, plus `not RUNNING_TESTS` so silk never records during pytest (prevents query-count pollution in `CaptureQueriesContext`).
3. **Emissions URLs** profiled under the canonical mount `carbon/` (`/carbon-api/carbon/dashboard/`, `.../calculations/`, `.../targets/`), not `/emissions/`.
4. **Exact-count assertions** (`assertNumQueries(3)`) from the template are not used — no default DRF pagination makes list queries fewer; constant-count + bound is the correct N+1 criterion.
5. **`prefetch_related('results')`** added to DQRuleViewSet to serve the serializer's `results_count` from cache (template did not mention it; without it, rules-list is still N+1 despite select_related).

## Files changed

- `backend/dq/views.py` (3 ViewSet querysets)
- `backend/mdm/views.py` (2 ViewSet querysets)
- `backend/core/tests/test_performance.py` (+7 tests, 2 new classes + mixin)
- `backend/config/settings.py` (silk dev app + middleware, `RUNNING_TESTS` guard)
- `backend/config/urls.py` (silk URL mount under `settings.DEBUG`)
- `backend/requirements.txt` (`django-silk==5.3.2`)
- `backend/profile_endpoints.py` (new CLI profiling harness)
- `TASK-RESULTS-P12-PROFILE.md` (profiling report)
