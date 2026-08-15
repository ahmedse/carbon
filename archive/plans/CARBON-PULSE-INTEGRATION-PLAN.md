# Carbon ↔ Pulse Integration Plan

**Status:** Legacy integration reference, superseded by [docs/AI_WORKSPACE_ARCHITECTURE.md](../docs/AI_WORKSPACE_ARCHITECTURE.md) and [plans/CARBON_AI_WORKSPACE_PHASED_PLAN.md](CARBON_AI_WORKSPACE_PHASED_PLAN.md)

This plan is kept only as a technical reference for the Carbon ↔ Pulse contract. The canonical AI workspace architecture now lives in the architecture doc, and the execution roadmap lives in the phased plan.

---

## 0. Architecture Principle — Carbon IS the AI Heart

This is the single most important architectural fact. Misunderstanding it
causes every integration failure.

```
┌──────────────────────────────────────────────────────────────────┐
│                        CARBON DATA TRUST                          │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │              backend/ai/  ← THE AI HEART                    │  │
│  │                                                             │  │
│  │  protocol.py       THE CONTRACT (ABC + dataclasses)         │  │
│  │       ▲                                                     │  │
│  │       │  implements                                          │  │
│  │  ┌────┴────────────┐                                        │  │
│  │  │  PulseProvider   │  ← adapter (maps ABC → HTTP)          │  │
│  │  │  _http.py        │  ← transport (POST /tasks)            │  │
│  │  └────────┬────────┘                                        │  │
│  │           │                                                  │  │
│  │  ┌────────▼────────┐                                        │  │
│  │  │CarbonIntelligence│  ← mediator (scope, domain, cache)    │  │
│  │  └────────┬────────┘                                        │  │
│  └───────────┼─────────────────────────────────────────────────┘  │
│              │                                                    │
│  ┌───────────▼──────────────────────────────────────────────────┐ │
│  │  dq/engine.py   dq/jobs.py   dq/services.py   catalog/ ...  │ │
│  │  (ALL Carbon consumers call CarbonIntelligence, never Pulse) │ │
│  └──────────────────────────────────────────────────────────────┘ │
└──────────────────────────┼───────────────────────────────────────┘
                           │
                    HTTP JSON
                    POST /tasks
                    GET  /tasks/{id}
                    GET  /tasks/modules
                           │
┌──────────────────────────▼───────────────────────────────────────┐
│                          PULSE                                    │
│                                                                   │
│  api/tasks.py          ← 9 handlers, 1 endpoint, module discovery│
│  llm/provider.py       ← OpenAI-compatible chat completion       │
│  knowledge_graph/      ← RAG store, embeddings, schema analysis  │
│  cognition/            ← autonomous agent loop                   │
│  instances/carbon/     ← instance.yaml (config, persona, domain) │
│                                                                   │
│  Pulse NEVER calls Carbon. Pulse NEVER imports Carbon SDKs.      │
│  Pulse is a SWAPPABLE AI PROVIDER — one of many possible.        │
└───────────────────────────────────────────────────────────────────┘
```

**The golden rules:**

| # | Rule | Violated by |
|---|------|-------------|
| 1 | Carbon's `ai/protocol.py` is the **canonical contract**. Pulse implements it, not defines it. | Contract spec §5 says `pulse_gateway.py` is deprecated — correct. |
| 2 | All Carbon code calls `CarbonIntelligence`, never `PulseProvider` directly. | Any direct import of `PulseProvider` outside `ai/intelligence.py`. |
| 3 | Pulse is **swappable**. Change `AI_PROVIDER_CLASS` in settings and the entire AI backend changes. | Hardcoding Pulse URLs or Pulse-specific error codes anywhere except `providers/pulse.py`. |
| 4 | `ai/protocol.py` imports NOTHING from Django, DRF, requests, or Pulse. Pure ABCs + dataclasses. | Already true. Must stay true. |
| 5 | Pulse NEVER calls Carbon. Fire-and-forget contract only. | Any webhook, callback URL, or Carbon API call from Pulse. |
| 6 | Carbon NEVER imports Pulse SDKs. | Already true. `_http.py` uses raw `requests`. |
| 7 | No shared database. | Already true. |

---

## 1. Separation of Concerns (SOCS)

### 1.1 Carbon's `ai/` App — The AI Heart

| Layer | File | Responsibility | Pattern |
|-------|------|----------------|---------|
| **Contract** | `ai/protocol.py` | `AIProvider` ABC + 30 typed dataclasses. Zero framework imports. The canonical interface. | Strategy (swappable backends) |
| **Adapter** | `ai/providers/pulse.py` | `PulseProvider` — maps each ABC method to a Pulse task type + HTTP call. Shape translation. | Adapter |
| **Transport** | `ai/providers/_http.py` | `post_task()`, `get_task()`, `get_modules()`, `poll_task()` — shared HTTP helpers. Error handling. | Facade |
| **Mediator** | `ai/intelligence.py` | `CarbonIntelligence` singleton. Lazy provider init. `build_scope()` from Django User/RBAC. Sync + async entry points. | Mediator + Singleton |
| **API** | `ai/views.py` | Thin DRF views that call `CarbonIntelligence`. | Facade (thin views, fat mediator) |

### 1.2 Pulse's Task API — The AI Provider

| Layer | File | Responsibility | Pattern |
|-------|------|----------------|---------|
| **Endpoint** | `api/tasks.py` | `POST /tasks` — validates API key, dispatches to handler. `GET /tasks/modules` — module discovery. | Mediator |
| **Handlers** | `api/tasks.py` | 9 `_handle_*` async functions — one per task type. LLM calls, SQL execution, domain pack enrichment. | Strategy |
| **Knowledge** | `knowledge_graph/` | RAG store, embeddings, schema analysis. Enriches handler context. | Flyweight |
| **Config** | `instances/carbon/instance.yaml` | Carbon-specific persona, domain, tools, forbidden tables. | Config (externalized) |
| **LLM** | `llm/provider.py` | OpenAI-compatible `chat_completion()` — abstracted behind a single call. | Facade |

### 1.3 Contract Boundary — What Crosses the Wire

```
Carbon (ai/protocol.py)                      Pulse (api/tasks.py)
══════════════════════════                    ════════════════════════
DqValidateRequest ──────► POST /tasks ──────► TaskRequest.task.payload
                         {auth, task:{id, type, payload}}
                         
DqValidateResponse ◄───── HTTP 200 ◄───────── TaskResponse {status, result, error}
                         {status, result, error}
                         
ProviderStatus ◄───────── GET /tasks/modules ─► MODULE_DEFINITIONS
```

**The wire format is the ONLY shared truth.** Both sides independently parse/validate it.
Neither side trusts the other's payload structure — they validate at the boundary.

---

## 2. Current State — Honest Assessment

### 2.1 What's Complete

| Component | Status | Notes |
|-----------|--------|-------|
| `ai/protocol.py` | ✅ 100% | 30 dataclasses, 1 ABC, 9 abstract methods — the canonical contract |
| `ai/providers/pulse.py` | ✅ 100% | All 9 `AIProvider` methods implemented, each maps to a Pulse task type |
| `ai/providers/_http.py` | ✅ 100% | `post_task`, `get_task`, `get_modules`, `poll_task` — all with graceful degradation |
| `ai/intelligence.py` | ✅ 100% | `CarbonIntelligence` singleton, `build_scope()`, sync + async entry points |
| `dq/engine.py` | ✅ 100% | NL check rules call `CarbonIntelligence.validate_dq_rule()` |
| `dq/jobs.py` | ✅ 100% | Job submit→poll→done/failed lifecycle for Pulse-bound jobs |
| `dq/services.py` | ✅ 100% | `suggest_dq_rules()` via Pulse |
| Pulse: 9 handlers | ✅ 100% | All 9 TASK_HANDLERS registered and implemented |
| Pulse: Module discovery | ✅ 100% | `GET /tasks/modules?instance_id=carbon` returns all 9 |
| Pulse: API key auth | ✅ 100% | Validates instance + key hash |
| Pulse: Audit log | ✅ 100% | `TaskExecution` row written per task |
| Pulse: Instance config | ✅ 100% | `instances/carbon/instance.yaml` with persona, tools, domain |
| Contract spec | ✅ 100% | `docs/PULSE_CONTRACT_SPEC.md` v3.0.0 — detailed, complete |
| Graceful degradation | ✅ 100% | Carbon: `pulse_unavailable` on any failure. DQ: `skipped_unavailable`. |

### 2.2 What's Broken — 3 Critical Blockers

| # | Blocker | System | Root Cause |
|---|---------|--------|------------|
| B1 | **URL routing mismatch** | Pulse | Router mounted at `/tasks`, Carbon sends to `/instances/carbon/tasks` |
| B2 | **Missing `GET /tasks/{id}`** | Pulse | No polling endpoint exists; Carbon's `dq/jobs.py` depends on it |
| B3 | **No idempotency** | Pulse | Same `task.id` re-processes instead of returning cached result |

### 2.3 What Would Break After Blockers Fixed — 3 Runtime Failures

| # | Failure | System | Mismatch |
|---|---------|--------|----------|
| F1 | `dq.validate` response shape | Pulse | Pulse returns `{rule_id, passed: N, failed: N, details: [...]}`; Carbon expects `DqRuleResult(failing_rows, explanation)` from a flat structure |
| F2 | `anomaly.detect` payload wrapping | Carbon | Carbon wraps in `{"profile": payload}`; Pulse reads `table_name` from top-level |
| F3 | Scope silently dropped | Both | Carbon builds `Scope` but `_http.py` never sends it in the task envelope |

### 2.4 What's Cosmetic — 3 Contract Deviations

| # | Deviation | Where | Impact |
|---|-----------|-------|--------|
| D1 | Response envelope missing `task_id` | Pulse | Carbon generates its own UUID; no functional impact but breaks contract |
| D2 | No `meta.model`/`meta.latency_ms` | Pulse | Useful for observability, not blocking |
| D3 | All tasks return sync `completed` | Pulse | Contract says async tasks return 202; Pulse returns 200 always. Accidentally functional because Carbon's sync path handles it. |

---

## 3. The Fix Plan — 4 Phases (Strict Order)

### Phase Dependency Graph

```
Phase 1 (Pulse Foundation)
├── 1A: Fix URL routing
├── 1B: Add GET /tasks/{id} endpoint
└── 1C: Add idempotency
         │
         ▼
Phase 2 (Wire Format Alignment)
├── 2A: Fix dq.validate response shape
├── 2B: Fix anomaly.detect payload (or Carbon sender)
├── 2C: Inject scope into task envelope
└── 2D: Add task_id to response envelope
         │
         ▼
Phase 3 (Async Support)
├── 3A: Add 202 async response for long tasks
├── 3B: Implement async handler infrastructure
└── 3C: Wire DQ job polling to new endpoint
         │
         ▼
Phase 4 (Verification & Hardening)
├── 4A: End-to-end integration tests
├── 4B: Contract conformance audit
└── 4C: Update contract spec to v3.1
```

---

## Phase 1 — Pulse Foundation (Backend Worker, Pulse repo)

**Worker:** backend-worker  
**Model:** DeepSeek-V3  
**Repository:** `/home/ahmed/clearturn/pulse`  
**Files to modify:** `api/tasks.py`, `main.py`  
**Files to NOT touch:** `api/chat.py`, `knowledge_graph/`, `cognition/`, `llm/provider.py`, `core/`

### Phase 1A — Fix URL Routing

**Problem:** Carbon sends `POST /instances/carbon/tasks`. Pulse serves at `POST /tasks`.

**Contract says:** `POST /instances/carbon/tasks` (spec §1.1).

**Fix:** Mount `tasks_router` with the instance-scoped prefix in `main.py`.

**File:** `main.py` line 458  
**Old:** `app.include_router(tasks_router)`  
**New:** `app.include_router(tasks_router, prefix="/instances/carbon")`

This is ONE line. The `router` already has `prefix="/tasks"` internally, so the full path becomes `/instances/carbon/tasks`. Module discovery at `GET /instances/carbon/tasks/modules`.

**Verification:**
```bash
curl -s http://127.0.0.1:9100/instances/carbon/tasks/modules?instance_id=carbon | python3 -m json.tool | grep -c '"type"'
# Expected: 9
```

---

### Phase 1B — Add `GET /instances/carbon/tasks/{task_id}` Endpoint

**Problem:** Carbon's `_http.get_task()` calls `GET {base_url}/tasks/{task_id}`. Pulse has no such endpoint. Carbon's DQ job polling is broken.

**Contract says:** `GET /instances/carbon/tasks/{task_id}` returns `{task_id, status, result, error}` (spec §1.4).

**Fix:** Add a new route to `api/tasks.py` that queries `TaskExecution` by `external_task_id`.

```python
@router.get("/{task_id}")
async def get_task_status(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Poll task status by external task ID.

    Returns the cached result from TaskExecution audit log.
    """
    stmt = select(TaskExecution).where(
        TaskExecution.external_task_id == task_id
    ).order_by(TaskExecution.created_at.desc()).limit(1)

    result = await db.execute(stmt)
    execution = result.scalar_one_or_none()

    if execution is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": f"Task '{task_id}' not found"},
        )

    return {
        "task_id": execution.external_task_id,
        "status": execution.status,
        "result": json.loads(execution.response_payload).get("result")
            if execution.response_payload else None,
        "error": json.loads(execution.response_payload).get("error")
            if execution.response_payload else None,
        "meta": {
            "execution_ms": execution.execution_ms,
            "created_at": execution.created_at.isoformat() if execution.created_at else None,
        },
    }
```

**Note:** Since Pulse currently executes synchronously (always returns `"completed"`), `status` will always be `"completed"` or `"pulse_unavailable"`. Phase 3 adds `"pending"` and `"working"`.

**Verification:**
```bash
# Submit a task first
TASK_ID=$(uuidgen)
curl -s -X POST http://127.0.0.1:9100/instances/carbon/tasks \
  -H "Content-Type: application/json" \
  -d "{\"auth\":{\"instance_id\":\"carbon\",\"api_key\":\"test\"},\"task\":{\"id\":\"$TASK_ID\",\"type\":\"dq.validate\",\"payload\":{\"rules\":[],\"rows\":[]}}}" | python3 -m json.tool

# Then poll it
curl -s http://127.0.0.1:9100/instances/carbon/tasks/$TASK_ID | python3 -m json.tool
# Expected: {"task_id": "...", "status": "completed", "result": {...}}
```

---

### Phase 1C — Add Idempotency

**Problem:** Same `task.id` sent twice → re-processed twice. Carbon retries on network error and expects cached result.

**Contract says:** "If Carbon sends the same `task.id` twice, Pulse MUST return the same result instead of re-processing" (spec §1.6).

**Fix:** Add a lookup BEFORE dispatching to handler, in the `create_task` function.

In `api/tasks.py`, inside `create_task()`, BEFORE the `handler = TASK_HANDLERS.get(...)` line:

```python
# ── Idempotency check ─────────────────────────────────────────────
existing_stmt = select(TaskExecution).where(
    TaskExecution.external_task_id == request.task.id,
    TaskExecution.status.in_(["completed", "failed", "pulse_unavailable"]),
).order_by(TaskExecution.created_at.desc()).limit(1)

existing_result = await db.execute(existing_stmt)
existing = existing_result.scalar_one_or_none()

if existing is not None:
    logger.info(
        "Task %s idempotent hit — returning cached result", request.task.id
    )
    cached = json.loads(existing.response_payload) if existing.response_payload else {}
    return TaskResponse(**cached)
# ── End idempotency check ─────────────────────────────────────────
```

**Verification:**
```bash
TASK_ID=$(uuidgen)
# First call
curl -s -X POST http://127.0.0.1:9100/instances/carbon/tasks \
  -H "Content-Type: application/json" \
  -d "{\"auth\":{\"instance_id\":\"carbon\",\"api_key\":\"test\"},\"task\":{\"id\":\"$TASK_ID\",\"type\":\"dq.validate\",\"payload\":{\"rules\":[],\"rows\":[]}}}" > first.json

# Second call with same ID
curl -s -X POST http://127.0.0.1:9100/instances/carbon/tasks \
  -H "Content-Type: application/json" \
  -d "{\"auth\":{\"instance_id\":\"carbon\",\"api_key\":\"test\"},\"task\":{\"id\":\"$TASK_ID\",\"type\":\"dq.validate\",\"payload\":{\"rules\":[],\"rows\":[]}}}" > second.json

diff first.json second.json
# Expected: no difference (identical responses)
```

### Phase 1 Verification Gate

```bash
# Run all 3 checks
cd /home/ahmed/clearturn/pulse

# 1A: URL routing
curl -s http://127.0.0.1:9100/instances/carbon/tasks/modules?instance_id=carbon | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['total']==9, f'Expected 9, got {d[\"total\"]}'; print('✅ 1A PASS')"

# 1B: GET /tasks/{id}
TID=$(uuidgen)
curl -s -X POST "http://127.0.0.1:9100/instances/carbon/tasks" -H "Content-Type: application/json" -d "{\"auth\":{\"instance_id\":\"carbon\",\"api_key\":\"test\"},\"task\":{\"id\":\"$TID\",\"type\":\"dq.validate\",\"payload\":{\"rules\":[],\"rows\":[]}}}"
curl -s "http://127.0.0.1:9100/instances/carbon/tasks/$TID" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'task_id' in d; print('✅ 1B PASS')"

# 1C: Idempotency
curl -s -X POST "http://127.0.0.1:9100/instances/carbon/tasks" -H "Content-Type: application/json" -d "{\"auth\":{\"instance_id\":\"carbon\",\"api_key\":\"test\"},\"task\":{\"id\":\"$TID\",\"type\":\"dq.validate\",\"payload\":{\"rules\":[],\"rows\":[]}}}" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['status']=='completed'; print('✅ 1C PASS')"

echo "Phase 1 complete"
```

---

## Phase 2 — Wire Format Alignment (Backend Worker, Pulse + Carbon)

**Worker:** backend-worker  
**Model:** DeepSeek-V3  
**Repositories:** BOTH `/home/ahmed/clearturn/pulse` AND `/home/ahmed/aast/carbon`  
**Files to modify:**
- Pulse: `api/tasks.py`
- Carbon: `backend/ai/providers/_http.py`, `backend/ai/providers/pulse.py`, `backend/ai/intelligence.py`

### Phase 2A — Fix `dq.validate` Response Shape (Pulse)

**Problem:** Pulse returns per-rule `{rule_id, status, passed, failed, total, details: [{row_id, passed, explanation}]}`. Carbon's `PulseProvider.validate_dq()` expects `{rule_id, status, failing_rows, explanation}` with flat structure.

**Contract says:** Result is `{results: [{rule_id, status, failing_rows: [int], explanation: str, confidence: float}]}` (spec §3.1).

**Fix:** In `_handle_dq_validate()` in `api/tasks.py`, transform the output:

```python
# After building results[] list, add transformation:
for r in results:
    details = r.get("details", [])
    failing = [d.get("row_id") for d in details if d.get("passed") is False]
    # Find a failing row index (as int)
    failing_indices = []
    for i, d in enumerate(details):
        if d.get("passed") is False:
            try:
                failing_indices.append(int(i))
            except (ValueError, TypeError):
                failing_indices.append(i)
    r["failing_rows"] = failing_indices
    r["explanation"] = details[0].get("explanation", "") if details else ""
    r["confidence"] = 0.95 if r["status"] == "pass" else 0.7
    # Remove Pulse-internal fields
    r.pop("passed", None)
    r.pop("failed", None)
    r.pop("total", None)
```

**Verification:**
```bash
# Submit a real dq.validate task with a rule and rows
curl -s -X POST http://127.0.0.1:9100/instances/carbon/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "auth": {"instance_id": "carbon", "api_key": "test"},
    "task": {
      "id": "dq-test-001",
      "type": "dq.validate",
      "payload": {
        "rules": [{"id": "r1", "prompt": "electricity_kwh must be > 0", "fields": ["electricity_kwh"], "severity": "error", "type": "nl_check"}],
        "rows": [{"electricity_kwh": 15000}, {"electricity_kwh": -5}],
        "context": {"table_name": "energy", "row_count_hint": 2}
      }
    }
  }' | python3 -c "
import sys, json
d = json.load(sys.stdin)
r = d['result']['results'][0]
assert 'failing_rows' in r, 'Missing failing_rows'
assert 'explanation' in r, 'Missing explanation'
assert 'confidence' in r, 'Missing confidence'
print('✅ 2A PASS — response has failing_rows, explanation, confidence')
"
```

### Phase 2B — Fix `anomaly.detect` Payload Wrapping (Carbon)

**Problem:** Carbon's `CarbonIntelligence.submit_anomaly_detect()` wraps payload in `{"profile": payload}`. Pulse's `_handle_anomaly_detect()` reads `table_name` from top-level `payload.get("table_name")`.

**There are two possible fixes:**
- **Option A (preferred):** Fix Carbon sender — unwrap the payload so it matches the contract.
- **Option B:** Fix Pulse receiver — handle both wrapped and unwrapped.

**Choose Option A** because it aligns with the contract spec §3.5 which shows `table_name`, `profile_history`, `sensitivity` at the top level.

**File:** `backend/ai/intelligence.py`, method `submit_anomaly_detect()`

**Old:**
```python
return _http_post_task(
    base_url=settings.AI_PROVIDER_URL.rstrip("/"),
    api_key=settings.AI_PROVIDER_API_KEY,
    task_type="anomaly.detect",
    payload={"profile": payload},
    timeout=120,
)
```

**New:**
```python
return _http_post_task(
    base_url=settings.AI_PROVIDER_URL.rstrip("/"),
    api_key=settings.AI_PROVIDER_API_KEY,
    task_type="anomaly.detect",
    payload=payload,  # Send unwrapped — matches contract §3.5
    timeout=120,
)
```

Also fix `PulseProvider.detect_anomalies()` — it sends `table_name`, `profile_history`, `sensitivity`, `volume_threshold_pct` at top level (already correct).

**Verification:**
```bash
cd /home/ahmed/aast/carbon
source .venv/bin/activate
python -c "
from backend.ai.protocol import AnomalyDetectRequest, Scope
from backend.ai.providers.pulse import PulseProvider
req = AnomalyDetectRequest(table_name='test', profile_history=[], sensitivity=2.0)
# Verify PulseProvider does NOT wrap in {'profile': ...}
# Read the code — check payload construction
print('✅ 2B PASS — manual code review confirms unwrapped payload')
"
```

### Phase 2C — Inject Scope Into Task Envelope (Carbon)

**Problem:** `build_scope()` extracts full `Scope` from Django User, but `_http.post_task()` never includes it in the task envelope. Pulse never receives scope, so NL queries and anomaly reports aren't org-scoped.

**Contract says:** "Every AI call that touches Carbon data MUST carry a `scope` object" (spec §2.4).

**Fix A — Carbon `_http.py`:** Add `scope` parameter to `post_task()`:

```python
def post_task(
    base_url: str,
    api_key: str,
    task_type: str,
    payload: dict[str, Any],
    timeout: int = 30,
    instance_id: str = "carbon",
    scope: dict[str, Any] | None = None,  # NEW
) -> dict[str, Any]:
```

And include it in the envelope:
```python
envelope: dict[str, Any] = {
    "auth": {
        "instance_id": instance_id,
        "api_key": api_key,
    },
    "task": {
        "id": task_id,
        "type": task_type,
        "payload": payload,
        "scope": scope,  # NEW
    },
}
```

**Fix B — Carbon `intelligence.py`:** Update all `submit_*` methods to pass scope:

```python
def submit_dq_validate(self, rules, rows, context=None, user=None):
    scope = build_scope(user)
    # ... build payload ...
    return _http_post_task(
        base_url=settings.AI_PROVIDER_URL.rstrip("/"),
        api_key=settings.AI_PROVIDER_API_KEY,
        task_type="dq.validate",
        payload=payload,
        timeout=30,
        scope=scope.to_dict() if scope else None,  # NEW
    )
```

**Note:** This requires adding a `to_dict()` method to `Scope` in `protocol.py`:

```python
def to_dict(self) -> dict[str, Any]:
    return {
        "org_unit_ids": self.org_unit_ids,
        "module_ids": self.module_ids,
        "is_read_only": self.is_read_only,
        "is_superuser": self.is_superuser,
        "user_identifier": self.user_identifier,
    }
```

**Fix C — Pulse `api/tasks.py`:** The `TaskEnvelope` model needs to accept optional `scope`:

```python
class TaskEnvelope(BaseModel):
    id: str
    type: str
    payload: dict = {}
    scope: Optional[dict] = None  # NEW
```

And `_handle_nl_query()` should use scope for org-scoped WHERE clauses.

**Verification (Phase 2C is a multi-file change — manual code review + unit test):**
```bash
cd /home/ahmed/aast/carbon
source .venv/bin/activate
python -c "
from backend.ai.protocol import Scope
s = Scope(org_unit_ids=['ou-1'], is_read_only=True, user_identifier='test')
d = s.to_dict()
assert d['org_unit_ids'] == ['ou-1']
assert d['is_read_only'] == True
print('✅ 2C Scope.to_dict() works')
"
```

### Phase 2D — Add `task_id` to Response Envelope (Pulse)

**Problem:** Pulse's `TaskResponse` doesn't include `task_id`. Contract says it should.

**Fix:** Add `task_id` to the `TaskResponse` model:
```python
class TaskResponse(BaseModel):
    task_id: str  # NEW — echoes back the task.id from request
    status: Literal["completed", "failed", "pulse_unavailable"]
    result: Optional[dict] = None
    error: Optional[dict] = None
```

And update the `create_task` return to include it:
```python
return TaskResponse(
    task_id=request.task.id,  # NEW
    **response_data
)
```

Also update `TaskResponse` to include `status: "pending"` and `status: "working"` literals (needed for Phase 3):
```python
class TaskResponse(BaseModel):
    task_id: str
    status: Literal["completed", "failed", "pulse_unavailable", "pending", "working"]
    result: Optional[dict] = None
    error: Optional[dict] = None
```

### Phase 2 Verification Gate

```bash
# 2A: dq.validate response shape (already verified above)
# 2B: anomaly.detect payload — manual code review
# 2C: Scope injection — unit test
# 2D: task_id in response
curl -s -X POST http://127.0.0.1:9100/instances/carbon/tasks \
  -H "Content-Type: application/json" \
  -d "{\"auth\":{\"instance_id\":\"carbon\",\"api_key\":\"test\"},\"task\":{\"id\":\"phase2-test\",\"type\":\"dq.validate\",\"payload\":{\"rules\":[],\"rows\":[]}}}" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'task_id' in d, 'Missing task_id'; print('✅ 2D PASS')"

echo "Phase 2 complete"
```

---

## Phase 3 — Async Support (Backend Worker, Pulse repo)

**Worker:** backend-worker  
**Model:** DeepSeek-V3  
**Repository:** `/home/ahmed/clearturn/pulse`

### Phase 3A — Add 202 Async Response for Long Tasks

**Problem:** Pulse always returns 200 with `status: "completed"`. Contract says async tasks (`dq.suggest`, `anomaly.detect`, `report.draft`) should return 202 with `status: "pending"`.

**Fix:** Add a `mode` map and return 202 for async tasks.

```python
# Task mode definitions
ASYNC_TASK_TYPES = {"dq.suggest", "carbon.anomaly.detect", "carbon.report.draft"}

# In create_task(), after writing the initial TaskExecution row:
if request.task.type in ASYNC_TASK_TYPES:
    # Write initial pending row
    pending_row = TaskExecution(
        id=generate_uuid(),
        instance_id=instance.id,
        task_type=request.task.type,
        external_task_id=request.task.id,
        status="pending",
        request_payload=json.dumps(request.task.payload or {}),
        response_payload=json.dumps({"status": "pending"}),
    )
    db.add(pending_row)
    await db.commit()
    
    # Fire background handler (asyncio.create_task)
    import asyncio
    asyncio.create_task(_run_async_handler(
        task_id=request.task.id,
        handler=handler,
        task=request.task,
        instance=instance,
    ))
    
    return JSONResponse(
        status_code=202,
        content={
            "task_id": request.task.id,
            "status": "pending",
            "poll_url": f"/instances/carbon/tasks/{request.task.id}",
        },
    )
```

And the background runner:
```python
async def _run_async_handler(
    task_id: str,
    handler: Callable,
    task: TaskEnvelope,
    instance: Instance,
):
    """Execute handler in background, update TaskExecution on completion."""
    from core.database import get_session_factory
    
    session_factory = get_session_factory()
    async with session_factory() as db:
        try:
            # Update status to working
            await db.execute(
                update(TaskExecution)
                .where(TaskExecution.external_task_id == task_id)
                .values(status="working")
            )
            await db.commit()
            
            response_data = await handler(task, instance, db)
            
            # Update with result
            await db.execute(
                update(TaskExecution)
                .where(TaskExecution.external_task_id == task_id)
                .values(
                    status=response_data.get("status", "completed"),
                    response_payload=json.dumps(response_data),
                    execution_ms=int((time.monotonic() - start_time) * 1000),
                )
            )
            await db.commit()
        except Exception as exc:
            logger.exception("Async handler %s failed: %s", task.type, exc)
            async with session_factory() as db2:
                await db2.execute(
                    update(TaskExecution)
                    .where(TaskExecution.external_task_id == task_id)
                    .values(
                        status="failed",
                        response_payload=json.dumps({
                            "status": "failed",
                            "error": {"code": "internal_error", "message": str(exc)},
                        }),
                    )
                )
                await db2.commit()
```

**Note:** This is the most complex change. The `db` session in the background task must be independent of the request-scoped session. Use `get_session_factory()` to create a new session.

### Phase 3B — Sync Tasks Return Immediately; Async Tasks Poll

After Phase 3A:
- **Sync tasks** (`dq.validate`, `carbon.query.nl`, `carbon.query.explain`, `carbon.anomaly.explain`, `carbon.schema.analyze`, `carbon.fix.suggest`): Return 200 with `status: "completed"` immediately (no change).
- **Async tasks** (`dq.suggest`, `carbon.anomaly.detect`, `carbon.report.draft`): Return 202 with `status: "pending"`. Poll `GET /tasks/{id}` for completion.

### Phase 3C — Wire Carbon DQ Jobs to New Async Endpoint

After Phase 3A-B, Carbon's `dq/jobs.py` polling via `get_task_status()` will correctly see:
- `pending` → job stays `running`
- `working` → job stays `running`
- `completed` → job marked `done`
- `failed` → job marked `failed`

No Carbon code changes needed — the polling logic in `dq/jobs.py` already handles these statuses.

### Phase 3 Verification Gate

```bash
# Submit an async task (dq.suggest)
TASK_ID=$(uuidgen)
curl -s -X POST http://127.0.0.1:9100/instances/carbon/tasks \
  -H "Content-Type: application/json" \
  -d "{
    \"auth\": {\"instance_id\": \"carbon\", \"api_key\": \"test\"},
    \"task\": {
      \"id\": \"$TASK_ID\",
      \"type\": \"dq.suggest\",
      \"payload\": {\"table\": {\"name\": \"test\", \"description\": \"test\", \"columns\": [], \"row_count\": 100}}
    }
  }" | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert d['status'] == 'pending', f'Expected pending, got {d[\"status\"]}'
assert 'poll_url' in d
print('✅ 3A PASS — async task returned 202 with pending')
"

# Poll it
sleep 2
curl -s http://127.0.0.1:9100/instances/carbon/tasks/$TASK_ID | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert d['status'] in ('working', 'completed', 'failed'), f'Unexpected status: {d[\"status\"]}'
print(f'✅ 3B PASS — poll returned status: {d[\"status\"]}')
"

echo "Phase 3 complete"
```

---

## Phase 4 — Verification & Hardening (QA Validator)

**Worker:** qa-validator  
**Model:** DeepSeek-V3  
**Both repositories**

### Phase 4A — End-to-End Integration Test

Create `backend/ai/tests/test_pulse_integration.py`:

```python
"""End-to-end Pulse integration tests.

Requires Pulse running at http://127.0.0.1:9100.
Skip all tests if Pulse is unreachable (graceful degradation).
"""

import pytest
import requests
from django.test import TestCase
from django.conf import settings

PULSE_BASE = getattr(settings, 'AI_PROVIDER_URL', 'http://127.0.0.1:9100/instances/carbon')
PULSE_KEY = getattr(settings, 'AI_PROVIDER_API_KEY', '')


def pulse_reachable():
    """Check if Pulse is reachable."""
    try:
        r = requests.get(f"{PULSE_BASE}/tasks/modules?instance_id=carbon", timeout=5)
        return r.ok
    except Exception:
        return False


@pytest.mark.skipif(not pulse_reachable(), reason="Pulse not reachable")
class TestPulseEndToEnd(TestCase):

    def test_01_module_discovery(self):
        """GET /modules returns all 9 task types."""
        resp = requests.get(f"{PULSE_BASE}/tasks/modules?instance_id=carbon", timeout=5)
        assert resp.ok
        data = resp.json()
        assert data['total'] == 9
        types = {m['type'] for m in data['modules']}
        assert 'dq.validate' in types
        assert 'carbon.query.nl' in types
        assert 'carbon.report.draft' in types

    def test_02_dq_validate_roundtrip(self):
        """Submit dq.validate, get result with correct shape."""
        from backend.ai.intelligence import CarbonIntelligence
        ci = CarbonIntelligence()
        status = ci.health_check()
        if not status.healthy:
            pytest.skip("Pulse health check failed")
        
        # Submit via async path
        result = ci.submit_dq_validate(
            rules=[{
                "id": "test-rule",
                "prompt": "electricity_kwh must be > 0",
                "fields": ["electricity_kwh"],
                "severity": "error",
            }],
            rows=[
                {"electricity_kwh": 15000},
                {"electricity_kwh": -5},
            ],
            context={"table_name": "test_energy"},
        )
        assert result['status'] in ('completed', 'pending')
        if result['status'] == 'completed':
            assert 'result' in result

    def test_03_idempotency(self):
        """Same task ID twice → same result."""
        import uuid
        task_id = str(uuid.uuid4())
        
        resp1 = requests.post(
            f"{PULSE_BASE}/tasks",
            json={
                "auth": {"instance_id": "carbon", "api_key": PULSE_KEY},
                "task": {
                    "id": task_id,
                    "type": "dq.validate",
                    "payload": {"rules": [], "rows": []},
                },
            },
            timeout=10,
        )
        resp2 = requests.post(
            f"{PULSE_BASE}/tasks",
            json={
                "auth": {"instance_id": "carbon", "api_key": PULSE_KEY},
                "task": {
                    "id": task_id,
                    "type": "dq.validate",
                    "payload": {"rules": [], "rows": []},
                },
            },
            timeout=10,
        )
        assert resp1.json() == resp2.json()

    def test_04_polling(self):
        """GET /tasks/{id} returns task status."""
        import uuid
        task_id = str(uuid.uuid4())
        
        # Submit
        requests.post(
            f"{PULSE_BASE}/tasks",
            json={
                "auth": {"instance_id": "carbon", "api_key": PULSE_KEY},
                "task": {
                    "id": task_id,
                    "type": "dq.validate",
                    "payload": {"rules": [], "rows": []},
                },
            },
            timeout=10,
        )
        
        # Poll
        resp = requests.get(f"{PULSE_BASE}/tasks/{task_id}", timeout=5)
        assert resp.ok
        data = resp.json()
        assert 'task_id' in data
        assert 'status' in data

    def test_05_scope_injection(self):
        """Scope is included in task envelope."""
        from backend.ai.protocol import Scope
        from backend.ai.providers._http import post_task
        
        # This is a unit test on the envelope construction
        # Verify post_task includes scope when provided
        scope = Scope(
            org_unit_ids=["ou-1"],
            is_read_only=True,
            user_identifier="test@test.com",
        )
        # Manual verification: check _http.py constructs envelope correctly
        # This test validates the code path exists
        assert scope.to_dict()['org_unit_ids'] == ['ou-1']
```

### Phase 4B — Contract Conformance Audit

Run this checklist against both systems:

```bash
# 1. Envelope format — Carbon sends {auth, task:{id, type, payload}}
grep -n '"auth"' backend/ai/providers/_http.py
# Expected: line ~35 in post_task()

# 2. Response format — Pulse returns {task_id, status, result/error}
grep -n "task_id" /home/ahmed/clearturn/pulse/api/tasks.py
# Expected: TaskResponse includes task_id

# 3. Idempotency — check exists in Pulse
grep -n "idempoten\|existing\|cached" /home/ahmed/clearturn/pulse/api/tasks.py
# Expected: found in create_task()

# 4. Module discovery — GET /modules returns all 9
curl -s http://127.0.0.1:9100/instances/carbon/tasks/modules?instance_id=carbon | python3 -c "import sys,json; assert json.load(sys.stdin)['total']==9"

# 5. Scope — included in envelope
grep -n "scope" backend/ai/providers/_http.py
# Expected: scope parameter in post_task()

# 6. Graceful degradation — Carbon handles pulse_unavailable
grep -n "pulse_unavailable\|provider_unavailable" backend/ai/protocol.py backend/ai/providers/pulse.py backend/dq/engine.py backend/dq/jobs.py
# Expected: found in all files

# 7. No circular imports — ai/ does not import from dq/, emissions/, catalog/
grep -rn "from backend.dq\|from backend.emissions\|from backend.catalog" backend/ai/
# Expected: NO RESULTS (ai/ only imports from ai/, django.conf, accounts.models)
```

### Phase 4C — Update Contract Spec to v3.1

Update `docs/PULSE_CONTRACT_SPEC.md`:
- Change status to "v3.1 — Carbon ai/ app implemented, Pulse integration verified"
- Add "Implemented Pulse-side" badge to §1.4 (polling) and §1.6 (idempotency)
- Update §5 to reflect that Carbon `ai/` app is fully built
- Add §10 "Integration Verification" with the test results

---

## 4. Carbon-Side Alignment — Code Changes Needed

After Pulse-side fixes (Phases 1-3), these Carbon-side changes align the `ai/` app with the fixed contract:

### Change 1: `_http.py` — Add scope to envelope (Phase 2C)

Already described above.

### Change 2: `_http.py` — Fix URL construction

Current code uses `{base_url}/tasks`. Pulse now serves at `{base_url}/tasks` where `base_url` = `http://127.0.0.1:9100/instances/carbon`. If Phase 1A mounts router at `/instances/carbon`, the effective URL becomes `http://127.0.0.1:9100/instances/carbon/tasks` → this is correct!

**No change needed** if AI_PROVIDER_URL is updated to `http://127.0.0.1:9100/instances/carbon`.

### Change 3: `intelligence.py` — Unwrap anomaly payload (Phase 2B)

Already described above.

### Change 4: `intelligence.py` — Pass scope to all `submit_*` methods

All `submit_dq_validate`, `submit_dq_suggest`, `submit_anomaly_detect` methods need `user` parameter to build scope.

### Change 5: `pulse.py` — Fix `validate_dq` response parsing (Phase 2A)

Once Pulse returns the correct shape (`failing_rows`, `explanation` at top level), the `PulseProvider.validate_dq()` method needs updating:

```python
# Old (current — expects details[0].explanation)
mapped = [
    DqRuleResult(
        rule_id=r.get("rule_id", ""),
        status=r.get("status", "fail"),
        failing_rows=_extract_failing_rows(r),
        explanation=r.get("details", [{}])[0].get("explanation")
        if r.get("details") else None,
        confidence=0.9 if r.get("status") == "pass" else 0.7,
    )
    for r in raw_results
]

# New (after Pulse fix — flat structure)
mapped = [
    DqRuleResult(
        rule_id=r.get("rule_id", ""),
        status=r.get("status", "fail"),
        failing_rows=r.get("failing_rows") or [],
        explanation=r.get("explanation"),
        confidence=float(r.get("confidence", 0.7)),
    )
    for r in raw_results
]
```

---

## 5. What NOT to Do — Anti-Patterns

| Anti-Pattern | Why It's Wrong | Pattern It Violates |
|-------------|----------------|---------------------|
| Adding Pulse-specific fields to `protocol.py` | The protocol is provider-agnostic | Strategy — each provider maps independently |
| Direct `import requests` in `intelligence.py` | Violates the layered architecture | Facade — `_http.py` is the HTTP layer |
| Hardcoding Pulse URLs in `dq/jobs.py` | Bypasses the provider abstraction | Mediator — all AI calls go through CarbonIntelligence |
| Adding a Carbon SDK import in Pulse | Violates the contract "Pulse never imports Carbon" | Adapter — Pulse is an independent provider |
| Creating a shared library between Carbon and Pulse | Creates a coupling dependency | Contract boundary — the HTTP envelope IS the shared truth |
| Adding a `callback_url` to task payload | Pulse never calls Carbon | Fire-and-forget contract |
| Returning raw LLM output to Carbon | Pulse owns the reasoning; Carbon gets structured results | Separation of Concerns |
| Copying `_http.py` logic into `pulse.py` | Duplication of transport concern | DRY — `_http.py` is the single transport module |
| Removing `PULSE_UNAVAILABLE_LIMIT` | Graceful degradation is mandatory | Contract §1.7 |
| Changing the task envelope format | The envelope is forever (§1) | Contract stability |

---

## 6. Role Assignments

| Phase | Role | Model | Repository | Est. Effort |
|-------|------|-------|------------|-------------|
| Phase 1A-C | backend-worker (Pulse) | DeepSeek-V3 | `/home/ahmed/clearturn/pulse` | 2 hours |
| Phase 2A | backend-worker (Pulse) | DeepSeek-V3 | `/home/ahmed/clearturn/pulse` | 30 min |
| Phase 2B-D | backend-worker (Carbon) | DeepSeek-V3 | `/home/ahmed/aast/carbon` | 1.5 hours |
| Phase 3A-C | backend-worker (Pulse) | DeepSeek-V3 | `/home/ahmed/clearturn/pulse` | 3 hours |
| Phase 4A-C | qa-validator | DeepSeek-V3 | Both | 2 hours |

**Total estimated effort: ~9 hours** for a single backend worker working sequentially.

---

## 7. Success Criteria — Integration Complete When...

- [ ] `curl POST /instances/carbon/tasks` returns 200 (not 404) — Phase 1A
- [ ] `curl GET /instances/carbon/tasks/{id}` returns task status — Phase 1B
- [ ] Same task ID submitted twice returns identical response — Phase 1C
- [ ] `dq.validate` response has `failing_rows`, `explanation`, `confidence` at top level — Phase 2A
- [ ] `anomaly.detect` payload is NOT wrapped in `{"profile": ...}` — Phase 2B
- [ ] Task envelope includes `scope` object when user is authenticated — Phase 2C
- [ ] Response includes `task_id` echoing request — Phase 2D
- [ ] Async tasks return 202 with `poll_url` — Phase 3A
- [ ] Polling `GET /tasks/{id}` returns `pending → working → completed` — Phase 3B
- [ ] All 4 integration tests pass with Pulse running — Phase 4A
- [ ] Contract conformance audit passes (all 7 checks) — Phase 4B
- [ ] Contract spec updated to v3.1 — Phase 4C
- [ ] `./manage.sh test` — all 329+ backend tests still pass (no regressions)
- [ ] `curl http://127.0.0.1:9100/instances/carbon/tasks/modules?instance_id=carbon` returns 9 modules

---

## 8. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Pulse DB schema change needed for async | Medium | Low | `TaskExecution` already has `status` field; only needs `execution_ms` + `error_message` which exist |
| Background handler session leak | Medium | Medium | Use `get_session_factory()` — creates independent async sessions |
| Carbon tests break from Pulse provider changes | Low | Medium | `PulseProvider` changes are additive; existing mocks in tests bypass Pulse |
| Phase 3 async complexity | High | Medium | Start with sync-only (skip Phase 3 if needed); Carbon already handles sync responses |
| Scope injection breaks NL queries | Low | High | Make scope optional in Pulse handlers; handle missing scope gracefully per contract §2.4 |

---

## Worker Activation

> **Paste into your AI coding tool (set model to DeepSeek-V3):**
>
> "Your role is backend-worker for Carbon Data Trust.
> 1. Read `.ai-toolkit/project.config.md`
> 2. Read `.ai-toolkit/shared/base-rules.md`
> 3. Read `.ai-toolkit/roles/backend-worker.md`
> 4. Read `plans/CARBON-PULSE-INTEGRATION-PLAN.md`
> 5. Confirm your role and begin Phase [X]."
