# TASKS.md — Pulse Ops Read API (Backend Phase 2c)

**Status:** FINAL (supersedes `plans/TASKS-PULSE-OPS-API-BACKEND.md` DRAFT)
**Role:** Backend Worker
**Model:** DeepSeek V4 Flash (customendpoint)
**Domain:** backend
**Prerequisite:** Phase 2b-3b committed (`9bd21e8`) — all 10 task types wired, KG cluster on Django Store.
**Primary context:** `backend/ai/engine_runtime.py` (`list_modules` / `dispatch_task` / `get_task`), `backend/ai/intelligence.py` (`CarbonIntelligence.health_check()`), `backend/ai/workspace_api.py` (existing DRF pattern).

## Objective

Expose a **read-only** ops API under `/carbon-api/ai/pulse/` that the AI admin console
consumes to show the in-process engine's advertised capabilities and task status.
This is the ops/observability surface for the vendored Pulse engine — NOT a mutation
surface. The engine runs in-process; there is no HTTP transport to Pulse.

Scope is intentionally minimal and grounded in what actually exists post-2b-3b:
`list_modules()` + `get_task()` + `health_check()`. The older DRAFT spec's
`knowledge/ memory/ graph/ agents/ mcp/ tools/ skills/ archetypes/ prompts/ feedback/
learning/ monitoring/ audit/ logs/` model-backed endpoints are **OUT OF SCOPE** for 2c —
those become read-only viewsets over the Phase 2 models in a later phase (only if/when
the console panels actually need them).

## Endpoints (all under `/carbon-api/ai/pulse/`)

| Method | Path | Returns | Backing |
|---|---|---|---|
| `GET` | `health/` | `{name, version, healthy, modules_available[], error}` | `CarbonIntelligence().health_check()` → `dataclasses.asdict` |
| `GET` | `modules/` | `{modules:[{type}], count:N}` | `engine_runtime.list_modules()` |
| `GET` | `tasks/{task_id}/` | task envelope (`status`, `task_id`, `result`\|`error`) | `engine_runtime.get_task(task_id)` |

No `POST`/`PUT`/`PATCH`/`DELETE`. Read-only is enforced structurally (GET-only views).

## Tasks

1. **CREATE `backend/ai/ops_api.py`**
   - Use plain `APIView` subclasses (NOT `ReadOnlyModelViewSet` — no models backing these
     three endpoints). `permission_classes = [IsAuthenticated]` (matches `workspace_api.py`).
   - `PulseHealthView(GET)` → `from ai.intelligence import CarbonIntelligence`;
     `status = CarbonIntelligence().health_check()`; `return Response(dataclasses.asdict(status))`.
     Wrap in try/except so an engine error never 500s — return a
     `{name:"pulse", version:"unknown", healthy:False, modules_available:[], error:str(exc)}`
     body with HTTP 200 (the console renders `healthy:false`, it does not need a 5xx).
   - `PulseModulesView(GET)` → `from ai.engine_runtime import list_modules`;
     `data = list_modules()`; `return Response({"modules": data.get("modules", []), "count": len(...)})`.
   - `PulseTaskStatusView(GET, task_id path param)` → `from ai.engine_runtime import get_task`;
     `return Response(get_task(task_id))`. Do NOT raise on missing task — `get_task` already
     returns a fail-visible `{status:"pulse_unavailable", error:{code:"not_found", ...}}` envelope.
   - Import style: use the same mixed convention as the rest of `ai/` — `from ai.intelligence import ...`
     and `from ai.engine_runtime import ...` (workspace_api.py already does `from ai.intelligence import CarbonIntelligence`).
   - No Carbon domain imports. No `backend.ai.*` alias needed (these are `ai.*`).

2. **CREATE `backend/ai/ops_urls.py`**
   ```python
   from django.urls import path
   from ai.ops_api import PulseHealthView, PulseModulesView, PulseTaskStatusView
   urlpatterns = [
       path("health/", PulseHealthView.as_view(), name="ai-pulse-health"),
       path("modules/", PulseModulesView.as_view(), name="ai-pulse-modules"),
       path("tasks/<str:task_id>/", PulseTaskStatusView.as_view(), name="ai-pulse-task-status"),
   ]
   ```

3. **MODIFY `backend/config/urls.py`** — add directly after the existing `ai/workspace/` mount:
   ```python
   path(f'{api_prefix}/ai/pulse/', include('ai.ops_urls')),
   ```

4. **CREATE `backend/ai/tests/test_ops_api.py`** (pytest-django, `@pytest.mark.django_db`)
   - `test_health_returns_healthy_modules`: use `pytest.mark.urls`/`client` + JWT auth
     (mirror `test_workspace_messages.py` auth pattern) → `GET /carbon-api/ai/pulse/health/`
     returns 200, `healthy is True`, `"dq.validate"` and `"chat"` in `modules_available`.
   - `test_modules_returns_ten_types`: `GET .../modules/` → 200, `count == 10`, and every
     `{"type": ...}` value is in `engine_runtime.MODULES`.
   - `test_task_status_unknown_is_fail_visible`: `GET .../tasks/nope/` → 200 (NOT 404),
     body `status == "pulse_unavailable"` and `error.code == "not_found"`.
   - `test_endpoints_require_auth`: anonymous `GET` on all three → 401.
   - `test_read_only_no_write_methods`: assert `POST`/`PUT`/`DELETE` on `health/` return 405
     (method not allowed) — proves structural read-only.

## DO NOT TOUCH
- `carbon-frontend/**`
- `backend/ai/protocol.py`, `intelligence.py`, `engine_runtime.py`, `providers/pulse.py`
  (reuse their existing public surface — do NOT change signatures).
- `backend/ai/workspace_api.py`, `workspace_urls.py` (leave as-is).
- `backend/ai/store.py`, `backend/ai/engine/**`.

## GATES (worker must run; Master will independently re-run ALL)
```
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py check
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests -q
cd /home/ahmed/aast/carbon && bash ./.ai-toolkit/scripts/verify.sh backend
```
Note: `makemigrations --check` MUST report "No changes detected" — this phase adds NO models/migrations.

## HARD RULES
- Read-only. No write endpoints. No `ModelViewSet` with mutation actions.
- No raw SQLAlchemy. No new DB tables/models/migrations.
- No hardcoded secrets, naive datetimes, or `print()` (verify.sh will fail on these).
- Report deviations + a test summary in `plans/TASK-RESULTS-PULSE-VENDOR-PHASE-2C-OPS-API.md`.
