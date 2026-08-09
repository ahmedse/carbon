# PULSE INTEGRATION CONTRACT — CARBON DATA TRUST

**Version:** 2.0.0  
**Status:** Spec — not yet implemented  
**Last updated:** 2026-08-09  
**Informed by:** Google A2A Protocol v1.0, MCP, OpenAI Agents SDK

---

## 0. Architecture Principle

Carbon and Pulse are two independent, opaque systems. Carbon owns the **trigger**
and the **data**. Pulse owns the **reasoning** and the **models**. They meet at a
clean contract boundary.

```
┌──────────────────────┐       HTTP JSON        ┌──────────────────────┐
│       CARBON         │ ◄──────────────────────►│        PULSE         │
│                      │   POST /tasks           │                      │
│  Owns: schema, rows, │   GET  /tasks/{id}      │  Owns: LLM, RAG,     │
│  profiles, rules,    │                          │  embeddings, agents  │
│  UI, workflow engine │   Pulse never calls      │                      │
│                      │   Carbon (fire-forget)   │  No Carbon SDK       │
│  Carbon never        │                          │  imported here       │
│  imports Pulse SDKs  │                          │                      │
└──────────────────────┘                          └──────────────────────┘
```

**Golden rule**: Carbon sends a task. Pulse returns a result. That's the entire
contract. There is no back-channel, no shared database, no SDK dependency.

---

## 1. The Task Envelope (NEVER CHANGES)

Every interaction between Carbon and Pulse is a **Task**. The task envelope is
the thin, stable wrapper that all task types share. It does not change with new
use cases.

### 1.1 Submit a Task

```
POST /instances/carbon/tasks
Content-Type: application/json

{
  "auth": {
    "instance_id": "carbon",
    "api_key": "pulse-api-key-from-env"
  },
  "task": {
    "id": "c7b8a9d1-...",       // UUID v4 — Carbon generates for idempotency
    "type": "dq.validate",       // namespaced task type (see §2)
    "payload": { ... },          // type-specific input (see §3)
    "meta": {                    // optional — passed through, not interpreted
      "tenant": "aastmt",
      "user": "admin@aastmt.edu",
      "trace_id": "req-abc123"
    }
  }
}
```

### 1.2 Task Response (Sync — completed immediately)

```
HTTP 200

{
  "task_id": "c7b8a9d1-...",
  "status": "completed",         // completed | failed | partial
  "result": { ... },             // type-specific output
  "meta": {
    "model": "gpt-4o",
    "latency_ms": 1234,
    "tokens": {"input": 500, "output": 200}
  }
}
```

### 1.3 Task Response (Async — accepted, still working)

```
HTTP 202

{
  "task_id": "c7b8a9d1-...",
  "status": "pending",
  "poll_url": "/instances/carbon/tasks/c7b8a9d1-..."
}
```

### 1.4 Poll Task Status

```
GET /instances/carbon/tasks/{task_id}

Response (still working):
HTTP 200
{ "task_id": "...", "status": "working" }

Response (completed):
HTTP 200
{ "task_id": "...", "status": "completed", "result": { ... } }

Response (failed):
HTTP 200
{
  "task_id": "...",
  "status": "failed",
  "error": {
    "code": "model_error",
    "message": "LLM returned invalid JSON after 3 retries"
  }
}
```

### 1.5 Task Lifecycle

```
                    ┌──────────┐
       Carbon ─────►│ pending  │──── Pulse accepted, queued
                    └────┬─────┘
                         │
                    ┌────▼─────┐
                    │  working  │──── Pulse processing
                    └────┬─────┘
                         │
            ┌────────────┼────────────┐
            ▼            ▼            ▼
       ┌─────────┐ ┌─────────┐ ┌──────────┐
       │completed│ │ failed  │ │ partial  │   ← terminal states
       └─────────┘ └─────────┘ └──────────┘
```

- **pending**: Pulse received the task, hasn't started yet
- **working**: Pulse is actively processing
- **completed**: All good, result in `result`
- **failed**: Something broke, error in `error`
- **partial**: Some items succeeded, some failed — `result` + `error` both present

### 1.6 Idempotency

Carbon generates the `task.id` (UUID v4). If Carbon sends the same `task.id`
twice (retry on network error), Pulse MUST return the same result instead of
re-processing. Carbon can safely retry without fear of double-execution.

### 1.7 Graceful Degradation

Carbon treats Pulse as unreliable by design:

| Scenario | Carbon behavior |
|----------|----------------|
| Pulse unreachable (connection refused) | Log warning, return `status: "pulse_unavailable"`, fall back to deterministic path |
| Pulse timeout (>10s for sync, >60s for async wait) | Abort, log warning, treat as `pulse_unavailable` |
| Pulse returns `status: "failed"` | Log the error, surface to user if appropriate |
| Pulse returns malformed response | Log, treat as `pulse_unavailable` |

Carbon NEVER blocks user workflows waiting for Pulse.

---

## 2. Task Type Registry (EXTENSIBLE)

Task types are namespaced strings following the pattern `{domain}.{action}`.
New task types can be added without changing the envelope.

### 2.1 Current Task Types (priority order)

| # | Type | Domain | Mode | Description |
|---|------|--------|------|-------------|
| 1 | `dq.validate` | Data Quality | sync | Validate row data against NL DQ rules |
| 2 | `dq.suggest` | Data Quality | async | Suggest DQ rules from table profile |
| 3 | `classification.infer` | Classification | sync | Classify fields → glossary terms, PII detection |
| 4 | `query.answer` | Query | stream | NL question → structured answer |
| 5 | `anomaly.detect` | Anomaly | async | Scan profile for anomalies |
| 6 | `report.draft` | Report | async | Dashboard data → narrative report |

### 2.2 Adding a New Task Type

To add a 7th task type, the only things needed are:
1. Define the `payload` schema (what Carbon sends)
2. Define the `result` schema (what Pulse returns)
3. Register the type on Pulse's side
4. Add a caller in Carbon's `pulse_gateway.py`

The envelope (§1) does not change. Existing task types are unaffected.

### 2.3 Versioning

Task types can be versioned: `dq.validate/v1`, `dq.validate/v2`. Pulse advertises
supported versions in its Agent Card (§4). Carbon requests the version it needs.
If Pulse doesn't support it, the task fails with `code: "unsupported_version"`.

---

## 3. Task Type Schemas

### 3.1 `dq.validate` — Validate rows against NL DQ rules

**Mode**: sync  
**Timeout**: 10s

#### Payload

```json
{
  "rules": [
    {
      "id": "rule-uuid-1",
      "prompt": "Monthly electricity for Building 401 must not deviate >50% from 12-month rolling average",
      "fields": ["building_id", "month", "electricity_kwh"],
      "severity": "error"
    }
  ],
  "rows": [
    {"building_id": "401", "month": "2026-06", "electricity_kwh": 15000},
    {"building_id": "401", "month": "2026-07", "electricity_kwh": 9500}
  ],
  "context": {
    "table_name": "energy_consumption",
    "row_count_hint": 24
  }
}
```

#### Result

```json
{
  "results": [
    {
      "rule_id": "rule-uuid-1",
      "status": "pass",
      "failing_rows": [],
      "explanation": "All rows within 50% of 12-month rolling average.",
      "confidence": 0.95
    },
    {
      "rule_id": "rule-uuid-2",
      "status": "fail",
      "failing_rows": [0, 5, 12],
      "explanation": "Rows 0, 5, 12 deviate by 67%, 72%, 55% respectively.",
      "confidence": 0.92
    },
    {
      "rule_id": "rule-uuid-3",
      "status": "error",
      "failing_rows": null,
      "explanation": "Insufficient data — only 3 rows provided, need 12 for rolling average.",
      "confidence": null
    }
  ]
}
```

#### Partial result (some rules failed, some succeeded)

```json
{
  "status": "partial",
  "result": {
    "results": [
      {"rule_id": "...", "status": "pass", ...},
      {"rule_id": "...", "status": "pass", ...}
    ]
  },
  "error": {
    "code": "partial_failure",
    "message": "2 of 5 rules failed evaluation",
    "failed_rules": ["rule-uuid-3", "rule-uuid-5"]
  }
}
```

### 3.2 `dq.suggest` — Suggest DQ rules from table profile

**Mode**: async  
**Timeout**: 60s (wait for completion)

#### Payload

```json
{
  "table": {
    "name": "energy_consumption",
    "description": "Monthly energy consumption per building",
    "row_count": 240,
    "fields": [
      {"name": "building_id", "type": "string", "distinct_count": 12},
      {"name": "month", "type": "date", "min": "2025-01", "max": "2026-06"},
      {"name": "electricity_kwh", "type": "number", "min": 5000, "max": 25000, "mean": 12000, "stddev": 4500}
    ]
  }
}
```

#### Result

```json
{
  "suggestions": [
    {
      "prompt": "Monthly electricity for any building must not deviate >50% from its 12-month rolling average",
      "rationale": "Field shows high variance (stddev 4500 on mean 12000) but per-building patterns are stable. Flag outliers at building level.",
      "suggested_severity": "warning",
      "confidence": 0.88
    }
  ]
}
```

### 3.3 `classification.infer` — Auto-classify field metadata

**Mode**: sync  
**Timeout**: 5s

#### Payload

```json
{
  "fields": [
    {
      "name": "employee_id",
      "label": "Employee ID",
      "type": "string",
      "sample_values": ["EMP-00142", "EMP-00143", "EMP-00144"]
    }
  ]
}
```

#### Result

```json
{
  "classifications": [
    {
      "field_name": "employee_id",
      "classifications": [
        {"term": "Employee Identifier", "confidence": 0.97, "source": "glossary"},
        {"term": "Personnel ID", "confidence": 0.85, "source": "glossary"}
      ],
      "pii": {
        "is_pii": false,
        "pii_type": null,
        "confidence": 0.99
      },
      "data_type_suggestion": "string"
    }
  ]
}
```

### 3.4 `query.answer` — NL question → structured answer

**Mode**: stream (SSE)  
**Timeout**: 15s

#### Payload

```json
{
  "question": "What was the total electricity consumption for Building 401 in Q1 2026?",
  "context": {
    "available_tables": ["energy_consumption", "buildings"],
    "schema_hint": {
      "energy_consumption": ["building_id", "month", "electricity_kwh"],
      "buildings": ["id", "name", "area_sqm"]
    }
  }
}
```

#### Result

```json
{
  "answer": "Building 401 consumed 38,500 kWh in Q1 2026 (Jan: 12,000, Feb: 13,200, Mar: 13,300).",
  "confidence": 0.94,
  "data": {
    "total_kwh": 38500,
    "breakdown": [
      {"month": "2026-01", "kwh": 12000},
      {"month": "2026-02", "kwh": 13200},
      {"month": "2026-03", "kwh": 13300}
    ]
  },
  "sources": ["energy_consumption table, rows 45-47"]
}
```

### 3.5 `anomaly.detect` — Scan profile for anomalies

**Mode**: async  
**Timeout**: 120s

#### Payload

```json
{
  "profile": {
    "table": "energy_consumption",
    "fields": [
      {
        "name": "electricity_kwh",
        "stats": {
          "mean": 12000, "stddev": 4500, "min": 100, "max": 95000,
          "p5": 6200, "p95": 21000
        }
      }
    ],
    "row_count": 240,
    "trend": "monthly"
  }
}
```

#### Result

```json
{
  "anomalies": [
    {
      "field": "electricity_kwh",
      "type": "extreme_outlier",
      "description": "Value 95,000 kWh is 18.4 standard deviations above mean (12,000). Possible data entry error or exceptional event.",
      "severity": "critical",
      "affected_rows_estimate": 1,
      "confidence": 0.99
    }
  ]
}
```

### 3.6 `report.draft` — Dashboard data → narrative report

**Mode**: async  
**Timeout**: 60s

#### Payload

```json
{
  "report_type": "ghg_annual",
  "period": {"start": "2026-01", "end": "2026-12"},
  "data": {
    "scope1_total_tco2e": 1250.5,
    "scope2_total_tco2e": 3400.2,
    "scope3_total_tco2e": 8900.0,
    "scope1_breakdown": {
      "stationary_combustion": 800.0,
      "mobile_combustion": 400.0,
      "fugitive_emissions": 50.5
    }
  },
  "comparison_period": "2025",
  "requirements": ["GHG Protocol Corporate Standard", "AASTMT reporting template"]
}
```

#### Result

```json
{
  "draft": "# Annual GHG Report 2026\n\n## Executive Summary\nTotal emissions for AASTMT in 2026 were 13,550.7 tCO₂e...",
  "sections": [
    {"title": "Executive Summary", "content": "...", "confidence": 0.92},
    {"title": "Scope 1 — Direct Emissions", "content": "...", "confidence": 0.95}
  ],
  "warnings": [
    "Scope 3 data may be incomplete — only 4 of 15 categories reported"
  ]
}
```

---

## 4. Agent Card (Discovery)

Pulse publishes an Agent Card at `GET /instances/carbon/agent-card`. Carbon
reads it on startup to know what's available.

```json
{
  "agent": "Pulse AI",
  "version": "2.0.0",
  "endpoint": "http://127.0.0.1:9100/instances/carbon",
  "supported_task_types": {
    "dq.validate": {
      "version": "1",
      "mode": "sync",
      "timeout_ms": 10000,
      "max_rows_per_request": 1000,
      "max_rules_per_request": 50
    },
    "dq.suggest": {
      "version": "1",
      "mode": "async",
      "timeout_ms": 60000
    },
    "classification.infer": {
      "version": "1",
      "mode": "sync",
      "timeout_ms": 5000,
      "max_fields_per_request": 50
    },
    "query.answer": {
      "version": "1",
      "mode": "stream",
      "timeout_ms": 15000
    },
    "anomaly.detect": {
      "version": "1",
      "mode": "async",
      "timeout_ms": 120000
    },
    "report.draft": {
      "version": "1",
      "mode": "async",
      "timeout_ms": 60000
    }
  },
  "capabilities": {
    "streaming": true,
    "async": true
  }
}
```

Carbon's `pulse_gateway.py` reads this card at startup and validates that
requested task types exist before sending.

---

## 5. Carbon-Side Implementation (`pulse_gateway.py`)

A thin HTTP client — no AI logic, no model config, no SDK imports.

```python
# Conceptual — not actual code, but shows the shape

class PulseGateway:
    """
    Thin HTTP client for Pulse. No AI logic lives here.
    """

    def __init__(self):
        self.base_url = settings.PULSE_URL  # http://127.0.0.1:9100/instances/carbon
        self.api_key = settings.PULSE_API_KEY
        self.default_timeout = 10  # seconds
        self.agent_card = None  # loaded on first call

    # ── Public API: one method per task type ──

    def validate_dq_rules(self, rules: list, rows: list, context: dict = None) -> dict:
        """Send DQ rules + rows to Pulse for NL validation."""
        return self._submit_sync("dq.validate", {
            "rules": rules,
            "rows": rows,
            "context": context or {}
        })

    def suggest_dq_rules(self, table_profile: dict) -> str:
        """Ask Pulse to suggest DQ rules from a table profile. Returns task_id for polling."""
        return self._submit_async("dq.suggest", {"table": table_profile})

    def classify_fields(self, fields: list) -> dict:
        """Auto-classify field metadata."""
        return self._submit_sync("classification.infer", {"fields": fields})

    def answer_query(self, question: str, context: dict = None) -> dict:
        """NL question → structured answer."""
        return self._submit_sync("query.answer", {
            "question": question,
            "context": context or {}
        })

    def detect_anomalies(self, profile: dict) -> str:
        """Scan profile for anomalies. Returns task_id for polling."""
        return self._submit_async("anomaly.detect", {"profile": profile})

    def draft_report(self, report_spec: dict) -> str:
        """Draft a narrative report. Returns task_id for polling."""
        return self._submit_async("report.draft", report_spec)

    # ── Internal ──

    def _submit_sync(self, task_type: str, payload: dict) -> dict:
        """Submit a sync task. Blocks until completed or timeout."""
        task_id = str(uuid.uuid4())
        try:
            resp = requests.post(
                f"{self.base_url}/tasks",
                json={
                    "auth": {"instance_id": "carbon", "api_key": self.api_key},
                    "task": {"id": task_id, "type": task_type, "payload": payload}
                },
                timeout=self.default_timeout
            )
            resp.raise_for_status()
            return resp.json()
        except requests.Timeout:
            return {"task_id": task_id, "status": "pulse_unavailable", "error": {"code": "timeout"}}
        except requests.ConnectionError:
            return {"task_id": task_id, "status": "pulse_unavailable", "error": {"code": "unreachable"}}

    def _submit_async(self, task_type: str, payload: dict) -> str:
        """Submit an async task. Returns task_id immediately."""
        ...
        return task_id

    def poll_task(self, task_id: str) -> dict:
        """Poll an async task for completion."""
        ...
```

---

## 6. Error Codes

| Code | Meaning | Carbon action |
|------|---------|---------------|
| `timeout` | Pulse didn't respond within timeout | Log, fall back to deterministic |
| `unreachable` | Connection refused / DNS failure | Log, fall back to deterministic |
| `invalid_payload` | Payload doesn't match schema | Log, fix the caller (dev error) |
| `model_error` | LLM returned garbage after retries | Log, surface to user as "AI unavailable" |
| `unsupported_version` | Task type version not supported | Log, check agent card |
| `rate_limited` | Too many requests | Back off, retry with exponential delay |
| `partial_failure` | Some items failed, some succeeded | Use `result` for successes, log `error.failed_rules` |
| `unknown` | Something unexpected | Log full response, treat as `pulse_unavailable` |

---

## 7. What This Contract ENABLES

Because the envelope is abstract and task types are pluggable:

- **Today**: DQ validation, field classification
- **Tomorrow**: NL query answering, anomaly detection, report drafting
- **Next month**: A new `import.mapping` task that suggests schema mappings for CSV imports
- **Next year**: A `compliance.check` task that vets data against GHG Protocol rules
- **Never**: Changing the envelope format. `task.id`, `task.type`, `task.payload`, `status`, `result`, `error` — these are forever.

---

## 8. What This Contract PREVENTS

- ❌ Carbon importing Pulse SDKs as a dependency
- ❌ Pulse calling Carbon APIs directly
- ❌ Shared database between the two systems
- ❌ Hardcoded LLM model names in Carbon config
- ❌ Per-use-case API endpoints (`/validate-dq`, `/classify`, `/answer` — all collapsed into one `/tasks`)
- ❌ Carbon knowing anything about how Pulse works internally (RAG, embeddings, agent framework)
- ❌ Pulse knowing Carbon's schema beyond what's in the payload

---

## 9. Comparison to Industry Standards

| Feature | Google A2A | MCP | This Contract |
|---------|------------|-----|---------------|
| Primitive | Task + Message | Tool + Resource | Task only |
| Discovery | Agent Card (JSON) | server/discover | Agent Card (simplified) |
| Sync/Async | Both (return_immediately) | Sync + Task extension | Both (sync/async modes) |
| Streaming | SSE + gRPC streams | SSE | SSE (for query.answer) |
| Auth | OAuth2, API keys | OAuth2, Bearer | API key (simple) |
| Complexity | Full protocol (11 operations) | Full protocol | 2 operations (POST + GET) |

**Design decision**: We're NOT implementing full A2A. We're adopting its **task-oriented
philosophy** and **Agent Card discovery pattern** but keeping the wire protocol
minimal — 2 endpoints instead of 11. Carbon doesn't need multi-turn conversations,
push notifications, or task cancellation (at least not yet).

If we ever need full A2A, the migration path is clear: the task envelope maps 1:1.
