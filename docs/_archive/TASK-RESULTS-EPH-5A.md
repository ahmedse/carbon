# TASK-RESULTS — EPH-5A: Structured Error Codes + API Version Header

**Status:** DONE ✅ (verified by master-architect 2026-08-27)
**Worker:** backend-worker (DeepSeek V4-Flash)
**Commit:** `5e2335d` (pushed to `origin/main`)
**Closes:** P1-9 (structured error codes), P1-7 (API versioning)

## Files changed

| File | Change |
|---|---|
| `backend/core/error_codes.py` (NEW) | 17-code taxonomy (`ERR_AUTH_*`, `ERR_CAT_*`, `ERR_DQ_*`, `ERR_MDM_*`, `ERR_SCH_*`, `ERR_VAL_*`, `ERR_AI_*`) + `CarbonAPIError(APIException)` + `infer_error_code()` |
| `backend/core/exception_handler.py` (NEW) | `structured_exception_handler` — wraps `catalog.exceptions.data_trust_exception_handler`, adds `error_code` to every dict payload; skips `AppFeedback` (already has `code`); returns None when base returns None |
| `backend/config/settings.py` (MOD) | `EXCEPTION_HANDLER` → `core.exception_handler.structured_exception_handler`; `ApiVersionMiddleware` appended to `MIDDLEWARE` |
| `backend/core/middleware.py` (MOD) | `ApiVersionMiddleware` — sets `API-Version: 1` on every response |
| `backend/core/tests/test_error_codes.py` (NEW) | 5 tests (below) |

## Verification Output (master-architect ran all gates)

### Gate 1 — Django checks
```
System check identified no issues (0 silenced).
=== makemigrations ===
No changes detected
```

### Gate 2 — pytest
```
collected 5 items
core/tests/test_error_codes.py::test_404_response_carries_taxonomy_error_code PASSED
core/tests/test_error_codes.py::test_401_response_carries_taxonomy_error_code PASSED
core/tests/test_error_codes.py::test_every_response_carries_api_version_header PASSED
core/tests/test_error_codes.py::test_known_code_returns_taxonomy_message PASSED
core/tests/test_error_codes.py::test_unknown_code_falls_back_to_default_message PASSED
============================== 5 passed in 2.63s ===============================
```

### Gate 3 — live curl (backend PID 2048 on :8009)
```
GET /carbon-api/catalog/assets/999999/  (unauthenticated)
→ 401 body: {"error":"NotAuthenticated","message":"Authentication credentials were not provided.",
             "timestamp":"...","path":"...","correlation_id":"...","error_code":"ERR_AUTH_001"}

GET /carbon-api/health/  →  header present:  API-Version: 1
```

### Gate 4 — regression
```
core/ catalog/ accounts/  →  532 passed in 62.61s
```

## Key decisions / notes

1. **Extended, did not replace**: the wired handler `catalog.exceptions.data_trust_exception_handler`
   remains the single source of truth for the envelope (`error/message/timestamp/path/correlation_id/details`).
   The new handler only augments it with `error_code` — no existing keys removed (frontend compatibility).
2. **`AppFeedback` untouched**: its rich `{code, title, detail, severity, reasons, remediation, context}`
   envelope already carries a machine-readable code; no redundant top-level `error_code` added.
3. **Dead code found**: `core/feedback.unified_exception_handler` (line 120) is defined but never referenced
   — NOT wired in; left as-is.
4. **`CarbonAPIError`** subclasses `APIException` (not plain Exception) so DRF propagates it; `default_code`
   is set before `super().__init__` so DRF stamps it on the `ErrorDetail`.
5. **404 inference is context-free** by design (`ERR_SCH_001`) — the taxonomy is the stable contract;
   callers needing precision raise `CarbonAPIError` explicitly.

## Next up

- EPH-4C (Field Visibility + Masking UI — frontend) — **HELD**: concurrent W7-B session has
  uncommitted refactor of `SchemaStructureTab.jsx` + schema-admin decommission (21 files). Dispatch
  only after that session commits.
- EPH-5B (Rate Limiting + OpenAPI Spec — backend, depends on EPH-5A done) — parallel-safe, next
  backend dispatch candidate.
