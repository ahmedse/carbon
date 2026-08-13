# TASK-RESULTS-PULSE-VENDOR-PHASE-2C — Pulse Ops Read API (Backend)

**Task spec**: `plans/TASKS-PULSE-VENDOR-PHASE-2C-OPS-API.md`
**Role**: backend-worker · **Date**: 2026-08-13
**Scope**: read-only ops API at `/carbon-api/ai/pulse/` over the in-process engine's
existing public surface (`list_modules` / `get_task` / `health_check`). No models,
no migrations, no write endpoints.

---

## 1. Deliverables

### D1 — `backend/ai/ops_api.py` (created)
- `PulseHealthView(APIView)` GET `health/` → `CarbonIntelligence().health_check()`
  serialized with `dataclasses.asdict(status)`. Engine errors are caught and returned
  as HTTP 200 with `{name:"pulse", version:"unknown", healthy:False,
  modules_available:[], error:str(exc)}` — never a 500.
- `PulseModulesView(APIView)` GET `modules/` → `{"modules":[...], "count":N}` from
  `engine_runtime.list_modules()`.
- `PulseTaskStatusView(APIView)` GET `tasks/{task_id}/` → `engine_runtime.get_task(task_id)`
  passed through unchanged (fail-visible `pulse_unavailable` / `not_found`, never raises).
- All three: `permission_classes = [IsAuthenticated]`, GET-only (structural read-only).
- Imports use the `ai.*` convention (`from ai.intelligence import CarbonIntelligence`,
  `from ai.engine_runtime import get_task, list_modules`). Logging via
  `logging.getLogger("carbon.ai.ops_api")` — no `print()`.

### D2 — `backend/ai/ops_urls.py` (created)
- Routes exactly per spec: `health/` → `ai-pulse-health`, `modules/` → `ai-pulse-modules`,
  `tasks/<str:task_id>/` → `ai-pulse-task-status`.

### D3 — `backend/config/urls.py` (modified)
- Added `path(f'{api_prefix}/ai/pulse/', include('ai.ops_urls'))` immediately after the
  existing `ai/workspace/` mount. No other line touched.

### D4 — `backend/ai/tests/test_ops_api.py` (created, pytest-django, 5 tests)
- `test_health_returns_healthy_modules` — JWT GET `health/` → 200, `healthy is True`,
  `dq.validate` and `chat` in `modules_available`.
- `test_modules_returns_ten_types` — GET `modules/` → 200, `count == 10`, every
  `{"type": ...}` value in `engine_runtime.MODULES`.
- `test_task_status_unknown_is_fail_visible` — GET `tasks/nope/` → 200 (not 404),
  `status == "pulse_unavailable"`, `error.code == "not_found"`.
- `test_endpoints_require_auth` — anonymous GET on all three → 401.
- `test_read_only_no_write_methods` — POST/PUT/DELETE on `health/` → 405.
- Auth fixture: `User.objects.create_user` + real JWT via conftest `get_token_for_user`
  (RefreshToken.for_user), set on the DRF `api_client` via `credentials(...)`.

---

## 2. Gate outputs (full)

### `manage.py check`
```
System check identified no issues (0 silenced).
```

### `manage.py makemigrations --check --dry-run`
```
No changes detected
```

### `pytest ai/tests -q`
```
bringing up nodes...
........................................................................ [ 61%]
..............................................                           [100%]
118 passed in 3.56s
```

### `verify.sh backend`
```
Verification gate: backend
════════════════════════════════════════
── Backend ─────────────────────────────
✓ django check
════════════════════════════════════════
GATE PASSED
```

---

## 3. Deviations
- **None.** All four deliverables match the spec exactly. The only judgment call:
  the spec's auth pattern reference (`test_workspace_messages.py`) exercises
  `CarbonIntelligence` directly (no HTTP), so the tests obtain a JWT via the
  project-wide conftest fixture `get_token_for_user` (same `RefreshToken.for_user`
  mechanism, no login throttling) instead of an HTTP `POST /token/` — a stronger,
  equivalent JWT-auth check.

## 4. Hard rules
- Read-only: GET-only `APIView`s, no `ModelViewSet`, no write methods (405-verified).
- No new models/migrations (`makemigrations --check` → "No changes detected").
- No raw SQLAlchemy, no Carbon domain imports, no `print()`.
- Untouched: `protocol.py`, `intelligence.py`, `engine_runtime.py`, `providers/pulse.py`,
  `workspace_api.py`, `workspace_urls.py`, `store.py`, `ai/engine/**`, `carbon-frontend/**`.
- No `git add` / `git commit` performed (Master Architect commits).
