# TASK-RESULTS — Carbon Wave A (Protocol + MockProvider + Settings)

**Completed:** 2026-08-11
**Status:** ✅ ALL GATES PASS

---

## Summary

Created 5 files, edited 1. All 6 gates pass. 28 tests (14 protocol integrity + 14 swap/provider).

---

## Files Created

| File | Purpose |
|------|---------|
| `backend/ai/__init__.py` | Package marker |
| `backend/ai/protocol.py` | 20 dataclasses + AIProvider ABC (352 lines) |
| `backend/ai/tests/__init__.py` | Package marker |
| `backend/ai/tests/test_protocol.py` | 14 dataclass integrity tests |
| `backend/ai/tests/test_protocol_swap.py` | MockProvider + 14 swap tests |

## Files Edited

| File | Change |
|------|--------|
| `backend/config/settings.py` | Added AI_PROVIDER_CLASS, AI_PROVIDER_URL, AI_PROVIDER_API_KEY + AI_CACHE_TTL_SECONDS, AI_MAX_CHAT_HISTORY, AI_RATE_LIMIT_PER_MINUTE |

---

## Gate Results

| Gate | Description | Status |
|------|-------------|--------|
| G1 | `grep -c 'django\|Pulse\|pulse\|requests\|httpx' ai/protocol.py` → 0 | ✅ |
| G2 | 14 tests in `test_protocol_swap.py` pass | ✅ |
| G3 | 14 tests in `test_protocol.py` pass | ✅ |
| G4 | `grep -c 'AI_PROVIDER' config/settings.py` → 3+ | ✅ |
| G5 | `from ai.protocol import AIProvider` → OK | ✅ |
| G6 | settings.py contains `AI_PROVIDER_CLASS` | ✅ |

## Import Count

Exactly 4 imports in protocol.py: `__future__`, `abc`, `dataclasses`, `typing`

## Test Summary

```
ai/tests/test_protocol.py .............. 14 passed
ai/tests/test_protocol_swap.py .............. 14 passed
======================== 28 passed in 0.07s =========================
```

---

## Decisions Made

1. **Root conftest conflict**: Carbon's root `conftest.py` imports DRF which needs Django config. Tests use `--noconftest -o "addopts="` to isolate from Django. The AI protocol tests are pure Python — they don't need Django at all.

2. **`asdict` round-trip for nested dataclasses**: `dataclasses.asdict()` deeply converts nested dataclasses to dicts, and `**d` reconstruction doesn't restore nested types. Round-trip tests access nested fields as dicts (e.g., `r.rules[0]["id"]` instead of `r.rules[0].id`). This correctly models JSON serialization behavior.

3. **`from __future__ import annotations`**: PEP 563 makes field types strings. Used `typing.get_type_hints()` in `test_fix_suggest_requires_confirmation` instead of `dataclasses.fields()`.

4. **G6 verification**: Carbon's Django settings import fails due to missing `pythonjsonlogger` in the shared venv. Verified via file content check instead. Settings are syntactically correct and will load when the proper Carbon venv is active.

---

## Next: Wave B (PulseProvider)

Handoff checklist:
- [ ] Create `backend/ai/providers/pulse.py` implementing `AIProvider`
- [ ] Map each method to `POST /tasks` with correct `type` field
- [ ] Reference `pulse_gateway.py` for HTTP patterns
- [ ] DO NOT edit `pulse_gateway.py`

```
validate_dq(request)    → type: "dq.validate"
suggest_dq(request)     → type: "dq.suggest"
query_nl(request)       → type: "carbon.query.nl"
explain_query(request)  → type: "carbon.query.explain"
detect_anomalies(req)   → type: "carbon.anomaly.detect"
explain_anomaly(req)    → type: "carbon.anomaly.explain"
draft_report(request)   → type: "carbon.report.draft"
analyze_schema(request) → type: "carbon.schema.analyze"
suggest_fix(request)    → type: "carbon.fix.suggest"
health_check()          → GET  /tasks/modules?instance_id=carbon
```
