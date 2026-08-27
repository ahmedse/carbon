# EPH-5B — Rate Limiting: Results

- **Date:** 2026-08-27
- **Worker Role:** backend-worker (DeepSeek V4-Flash)
- **Verified by:** Master Architect (DeepSeek V4-Pro)
- **Closes:** P1-8 (rate limiting)

## Scope Note

The original EPH-5B spec combined rate limiting + OpenAPI. Master-architect split the OpenAPI
half out to **EPH-5C** because the platform already ships drf-yasg (dev-gated swagger UI at
`/carbon-api/swagger/`, ~85 `@swagger_auto_schema` sites, `mdm/tests/test_swagger_docs.py`) and
ADR 0003 (Proposed) plans the drf-spectacular migration as its own effort. This phase delivered
rate limiting only.

## Deliverables

| File | Change |
|---|---|
| `backend/core/throttling.py` | **NEW** — 4 scoped DRF throttle classes (LoginRateThrottle house pattern) |
| `backend/config/settings.py` | `DEFAULT_THROTTLE_CLASSES` += `UserMinuteRateThrottle`, `AnonMinuteRateThrottle`; `DEFAULT_THROTTLE_RATES` += `user_minute 1000/min`, `anon_minute 60/min`, `ai 60/min`, `heavy 10/min` |
| `backend/ai/workspace_api.py` | `WorkspaceConversationViewSet.throttle_classes = [AIRateThrottle]` (view-layer complement to in-app RateLimiter — RateLimiter untouched) |
| `backend/importexport/views.py` | `ExportProjectViewSet` + `ImportJobViewSet` get `throttle_classes = [HeavyRateThrottle]` (read-only `ExportJobViewSet` deliberately exempt) |
| `backend/core/tests/test_throttle.py` | **NEW** — 5 tests |

## Throttle classes

```python
class UserMinuteRateThrottle(UserRateThrottle):  scope = 'user_minute'  # 1000/min
class AnonMinuteRateThrottle(AnonRateThrottle):  scope = 'anon_minute'  # 60/min per IP
class AIRateThrottle(UserRateThrottle):          scope = 'ai'           # 60/min per user
class HeavyRateThrottle(UserRateThrottle):       scope = 'heavy'        # 10/min per user
```

Rates live in `DEFAULT_THROTTLE_RATES` (never hardcoded in the classes). Existing `anon
100/hour` / `user 1000/hour` / `login` rates untouched — both apply, stricter wins.

## Verification Gates (master-architect)

```bash
# 1. Django system check
/home/ahmed/aast/carbon/.venv/bin/python manage.py check
# => System check identified no issues (0 silenced)

# 2. No pending migrations
/home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run
# => No changes detected

# 3. Throttle tests
/home/ahmed/aast/carbon/.venv/bin/python -m pytest core/tests/test_throttle.py -v --create-db
# => 5 passed

# 4. Regression (suites affected by global throttles + modified views)
/home/ahmed/aast/carbon/.venv/bin/python -m pytest core/ catalog/ accounts/ mdm/ importexport/ -q --create-db
# => 622 passed, 11 subtests passed in 86.39s

# 5. Live (backend restarted via ./manage.sh restart)
curl -s -o /dev/null -w "%{http_code}" http://localhost:8009/carbon-api/health/
# => 200, header API-Version: 1  (EPH-5A regression intact)

for i in $(seq 1 62); do curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8009/carbon-api/token/refresh/ \
  -H 'Content-Type: application/json' -d '{"refresh":"bogus"}'; done
# => 60x 401 then 429, 429  (anon_minute 60/min trips at exactly request 61)

curl -s -D - -X POST http://localhost:8009/carbon-api/token/refresh/ \
  -H 'Content-Type: application/json' -d '{"refresh":"bogus"}'
# => HTTP/1.1 429, Retry-After: 53
# => {"error":"Throttled","message":"Request was throttled...","error_code":"ERR_AI_002"}
```

## Defects Found & Fixed

1. **Worker test bug (fixed by master):** The original tests used
   `override_settings(REST_FRAMEWORK=...)` to drive 429s. This does NOT work — DRF's
   `SimpleRateThrottle.THROTTLE_RATES` is a class-attribute snapshot captured at import time,
   so runtime settings overrides never change the effective rate. Rewrote the two behavioral
   tests with `mock.patch.object(<Throttle>, 'THROTTLE_RATES', _patched_rates(...))` — the
   documented DRF approach. Root cause confirmed empirically: 2 tests failed (200/401 instead
   of 429) before the fix; 5/5 pass after.

2. **Worker deviations (accepted):** (a) Anon test uses `/carbon-api/token/refresh/` instead of
   `/carbon-api/token/` — `ThrottledTokenObtainPairView` overrides `throttle_classes =
   [LoginRateThrottle]` which REPLACES (not extends) the global classes, so `anon_minute` never
   runs on the login view; token/refresh has no override → globals apply. (b) Conftest pytest
   fixtures can't inject into a `TestCase`, so identical helpers were reimplemented locally.

## OpenAPI Deferred

drf-spectacular migration (ADR 0003) + prod-accessible schema endpoints are now **EPH-5C** in
TASKS.md. drf-yasg remains in place and `mdm/tests/test_swagger_docs.py` still passes.

## Commits

- Backend: `<hash>` — `EPH-5B backend`
- Docs: `<hash>` — `docs EPH-5B DONE + results`
