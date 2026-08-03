# TASK-RESULTS-P12-PROFILE.md — 15-Endpoint Performance Profile (django-silk)

**Phase:** P12 — Backend N+1 Audit + Profiling · **Gate:** G2 · **Date:** 2026-08-02
**Executor:** Backend Worker (Copilot) · **Environment:** development (`DJANGO_ENV=development`, port 8009, prefix `/carbon-api/`)

## Setup

- `django-silk==5.3.2` installed in project venv, pinned in `backend/requirements.txt`.
- Silk enabled only when `DJANGO_ENV == "development" and not RUNNING_TESTS` (see `backend/config/settings.py`); URLs mounted under `path('silk/', include('silk.urls', namespace='silk'))` inside the existing `if settings.DEBUG:` block (`backend/config/urls.py`).
- Silk migrations applied (`python manage.py migrate silk`); backend restarted; silk UI verified `GET /silk/ → 200`.
- Profiling harness: `backend/profile_endpoints.py` (CLI) — logs in as `admin`, fires **2 warmup + 8 measured** requests per endpoint, reports client-side wall-clock timings. Server-side timings + query counts come from the silk DB (`silk.models.Request`).
- Authentication: JWT (`/carbon-api/token/`).

## Results (client-side avg/p95 from `profile_endpoints.py`; server-side ms + SQL query counts from silk)

| # | Endpoint (actual path) | avg ms | p95 ms | min ms | max ms | silk avg ms | SQL queries (avg/min/max) |
|---|------------------------|-------:|-------:|-------:|-------:|------------:|--------------------------:|
| 1 | `GET /carbon-api/carbon/dashboard/` | 47.3 | 51.2 | 44.7 | 51.2 | 40.7 | 6 / 6 / 6 |
| 2 | `GET /carbon-api/carbon/calculations/` | 43.1 | 47.3 | 40.2 | 47.3 | 35.6 | 3 / 3 / 3 |
| 3 | `GET /carbon-api/catalog/assets/` | 71.5 | 75.4 | 68.7 | 75.4 | 63.4 | 7 / 7 / 7 |
| 4 | `GET /carbon-api/accounts/users/` | 32.9 | 34.7 | 31.3 | 34.7 | 23.0 | 2 / 2 / 2 |
| 5 | `GET /carbon-api/accounts/scoped-roles/` | 65.7 | 71.7 | 60.8 | 71.7 | 49.6 | 14 / 14 / 14 |
| 6 | `GET /carbon-api/accounts/me/context/` | 43.0 | 53.8 | 40.1 | 53.8 | 34.1 | 5 / 5 / 5 |
| 7 | `GET /carbon-api/dq/rules/` | 42.2 | 44.3 | 40.5 | 44.3 | 34.3 | **2** / 2 / 2 |
| 8 | `GET /carbon-api/dq/results/` | 35.6 | 37.5 | 33.9 | 37.5 | 27.5 | **2** / 2 / 2 |
| 9 | `GET /carbon-api/mdm/org-units/` | 90.7 | 92.8 | 87.8 | 92.8 | 67.7 | 22 / 22 / 22 |
| 10 | `GET /carbon-api/mdm/reference-sets/` | 35.6 | 43.5 | 33.5 | 43.5 | 25.9 | 2 / 2 / 2 |
| 11 | `GET /carbon-api/dataschema/tables/` | 89.6 | 94.6 | 85.8 | 94.6 | 70.5 | 20 / 20 / 20 |
| 12 | `GET /carbon-api/dataschema/fields/` | 44.5 | 106.4 | 33.9 | 106.4 | 32.5 | 2 / 2 / 2 |
| 13 | `GET /carbon-api/carbon/targets/` | 65.0 | 81.0 | 61.5 | 81.0 | 49.3 | 11 / 11 / 11 |
| 14 | `GET /carbon-api/catalog/governance-policies/` | 33.0 | 34.9 | 30.8 | 34.9 | 23.1 | 2 / 2 / 2 |
| 15 | `GET /carbon-api/accounts/audit-log/` | 32.2 | 34.1 | 30.7 | 34.1 | 23.3 | 2 / 2 / 2 |

All 15 endpoints returned **HTTP 200**; all client-side averages ≤ 91 ms; silk server-side averages ≤ 68 ms.

## Analysis

### P12-optimized endpoints (DQ + MDM) — verified
- `dq/rules/` and `dq/results/`: **constant 2 queries** (min == max == 2). DQ tables were empty at profile time, but the N+1 regression tests in `core/tests/test_performance.py` prove the count stays constant as rows grow (8 rules + 16 results → still 2 queries).
- `mdm/reference-sets/`: 2 queries (list + nested-values aggregation) — already optimized, untouched.
- `mdm/org-units/`: 22 queries for 7 org units = `1 + 7 × 3` → **residual N+1** from `OrgUnitSerializer` method fields `children_count`, `descendants_count`, `full_path` (each issues per-object queries). `select_related('parent')` was added (G1) and removes the per-object `parent` lookup, but full elimination requires serializer changes — **out of P12 scope** (DO-NOT list), flagged in `TASK-RESULTS-P12-BACKEND.md`.

### Observations outside P12 scope (flagged, not modified)
- `dataschema/tables/`: 20 queries for 6 tables → residual N+1 in the dataschema tables serializer (method fields). Not in P12's DQ/MDM scope.
- `accounts/scoped-roles/`: 14 queries (nested role/permission aggregation) — acceptable for admin-config endpoint; not in scope.
- `carbon/targets/`: 11 queries (computed SBTi fields) — emissions app, **DO NOT touch** per task; verified acceptable.
- `emissions/dashboard/` (6) + `emissions/calculations/` (3): already optimized — confirmed.

## Silk verification
- `GET /silk/ → 200` (UI), requests recorded: 150 profiled + login/health.
- Query counts read from `silk.models.Request.num_sql_queries` aggregated per path (20 records per endpoint = 2 runs × 10 hits).

## Deviations from task template
- Task template paths `emissions/dashboard/`, `emissions/calculations/`, `emissions/targets/` resolve under the canonical emissions mount `carbon/` (`config/urls.py` registers emissions at `carbon/`); targets additionally registered under `emissions/`. Profiled the canonical `carbon/*` paths.
- Silk gated on `DJANGO_ENV == "development"` (project convention, matches debug_toolbar) **plus** `not RUNNING_TESTS` (prevents silk from recording requests during pytest, which would pollute `CaptureQueriesContext` assertions), rather than a bare `if DEBUG:`.
