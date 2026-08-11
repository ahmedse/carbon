# Carbon Wave B — Results

**Date**: 2026-08-11
**Status**: COMPLETE ✅
**Tests**: 76 passed (14 protocol + 14 swap + 28 pulse + 20 http)

---

## Deliverables

### B1: `backend/ai/providers/_http.py` — Shared HTTP Helpers

Created shared HTTP helpers extracted from PulseProvider so future providers (Azure, Claude, etc.) reuse the same envelope format and error handling.

| Function | Purpose |
|---|---|
| `post_task(base_url, api_key, task_type, payload, timeout, instance_id)` | POST envelope to `/tasks` |
| `get_modules(base_url, instance_id, timeout)` | GET `/tasks/modules` (health check) |
| `poll_task(base_url, api_key, task_id, poll_interval, max_wait, instance_id)` | Poll `/tasks/{id}` until completed |

All three return parsed JSON or a `pulse_unavailable`-shaped error dict:
```python
{"status": "pulse_unavailable", "error": {"code": "...", "message": "..."}}
```

Error codes: `timeout`, `unreachable`, `request_failed`, `unexpected`

### B2: Refactored PulseProvider to use `_http.py`

- Removed `import uuid, requests`
- Replaced inline `requests.post` in `health_check()` with `get_modules()`
- Replaced all 9 task methods' `self._post(TASK_TYPE, payload, timeout=N)` with `post_task(self._url, self._key, TASK_TYPE, payload, timeout=N)`
- Removed `_post()` method entirely (~60 lines deleted)
- Fixed `health_check()` error formatting to include code prefix (`f"{code}: {message}"`) so `test_unreachable` passes

Task type constants kept inline (not worth extracting yet).

### B3: `backend/ai/tests/test_provider_http.py` — 20 tests

| Class | Tests | Covers |
|---|---|---|
| `TestPostTask` | 8 | Happy path, defaults, custom timeout, ConnectionError, Timeout, RequestException, unexpected |
| `TestGetModules` | 7 | Happy path, defaults, custom timeout, ConnectionError, Timeout, RequestException, unexpected |
| `TestPollTask` | 5 | Immediate complete, immediate fail, polling loop, timeout return, connection params |

---

## Gate Results

| Gate | Result |
|---|---|
| All 76 tests pass | ✅ 76/76 |
| `_http.py` has 3 exported helpers | ✅ |
| PulseProvider imports from `_http` | ✅ |
| No unused pytest import in test files | ✅ |
| `isinstance(PulseProvider(), AIProvider)` | ✅ |
| All 12 ABC members callable | ✅ |

---

## Decisions

1. **get_modules default timeout = 10s** (not 30s like post_task). Rationale: health checks should be fast.
2. **poll_task returns error dict on timeout** (doesn't raise). Rationale: provider methods expect consistent `pulse_unavailable` envelopes, not exceptions.
3. **get_modules catches only Timeout + ConnectionError explicitly** — RequestException falls to generic `except Exception`. Rationale: health check is simple; adding more handlers is YAGNI until needed.
4. **Error message format for health_check**: `f"{code}: {message}"` — so the code is always present in the error string (tests assert on substring).
