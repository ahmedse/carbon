# PULSE INTEGRATION CONTRACT — CARBON DATA TRUST

**Version:** 3.0.0  
**Status:** v3.0 — All 9 Phase 7 task types implemented Pulse-side. Carbon `ai/` app in planning.  
**Last updated:** 2026-08-11  
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

### 1.8 Async Task Status — Required for Carbon DQ Jobs (Phase 3)

Carbon's DQ Jobs (`dq/jobs.py`, TASK-DQ-CORE-P3-JOBS) submit `nl_check` and
`suggest` tasks asynchronously and poll status via `GET /tasks/{id}` (see
§1.4). **Flag to Pulse team — documented here, NOT implemented Pulse-side.**

Polling semantics Carbon relies on:

- **Response shape** (HTTP 200): `{task_id, status: pending|working|completed|failed, result?, error?}`.
  `pending`/`working` → Carbon keeps the job `running`; `completed` → Carbon
  stores `result` and marks the job `done`; `failed` → Carbon marks the job
  `failed` with the returned `error`.
- **Pulse unavailable** (unreachable/timeout): Carbon counts consecutive
  `pulse_unavailable` polls; after **N=20** consecutive unavailable polls the
  job is marked `failed` (best-effort — Carbon never blocks user workflows
  waiting for Pulse, per §1.7).
- **Cancel is best-effort**: Carbon's `POST /dq/jobs/{id}/cancel/` marks the
  job `canceled` locally and does **not** notify Pulse. If Pulse-side cancel is
  desired, a `POST /tasks/{id}/cancel` endpoint should be added to the
  contract; until then canceled Carbon jobs may still complete on Pulse's side.

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
| 3 | `carbon.query.nl` | Carbon Query | sync | NL question → SQL + structured answer |
| 4 | `carbon.query.explain` | Carbon Query | sync | Human-readable explanation of query results |
| 5 | `carbon.anomaly.detect` | Anomaly | async | Statistical anomaly detection on table profiles |
| 6 | `carbon.anomaly.explain` | Anomaly | sync | LLM-generated anomaly explanation |
| 7 | `carbon.report.draft` | Report | async | Dashboard data → narrative report (7-stage pipeline) |
| 8 | `carbon.schema.analyze` | Schema | sync | Analyze schema changes for impact → action |
| 9 | `carbon.fix.suggest` | Fix | sync | Suggest data quality fixes (always requires confirmation) |

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

### 2.4 Scope Contract (v3.0 — NEW)

Every AI call that touches Carbon data MUST carry a `scope` object. The scope
represents the user's RBAC boundaries — org units they can see, whether they have
write access, and domain context the AI provider should inject.

#### Scope Schema

```json
{
  "scope": {
    "org_unit_ids": ["*"],                   // ["*"] = all; ["ou-1","ou-2"] = scoped
    "module_ids": ["em-abuqir-elec"],          // Specific modules user can see
    "is_read_only": false,                     // true → provider MUST NOT suggest mutations
    "is_superuser": false,                     // true → full access
    "user_identifier": "admin@aastmt.edu"      // For audit trail
  }
}
```

#### Provider Obligations

1. **Scoped queries**: Generated SQL MUST include `WHERE org_unit_id IN (:scope_ids)` or equivalent.
2. **Scoped profiles**: Anomaly detection and report drafting MUST filter source data to `org_unit_ids`.
3. **Read-only enforcement**: When `is_read_only: true`, ALL `fix.suggest` results MUST have `requires_confirmation: true` (already the default per Pulse HR-CRITICAL rule).
4. **Always present**: Scope is optional in the task envelope for backward compatibility — but CARBON WILL ALWAYS SEND IT. Pulse MUST handle missing scope by assuming no restriction (worst-case: full access).

#### Why Scope Exists

Carbon's RBAC is hierarchical: a campus manager sees one org unit, a dean sees several,
a global admin sees all. The AI must operate within the same boundaries as the user.
Without scope injection, the coworker chatbot would leak data across org units.

### 2.5 Module Discovery (v3.0 — NEW)

Pulse publishes available modules at `GET /tasks/modules`. This is a no-auth endpoint
that returns the task type definitions Carbon's `ai/` app uses to build its API surface.

```
GET /tasks/modules?instance_id=carbon
// Or:
GET /tasks/modules
X-Pulse-Instance: carbon
```

Response shape: `{ instance_id, modules: { task_type: { description, input_schema, output_schema }, ... } }`

The `enabled_modules` field in the Carbon instance config controls which modules are visible.
`"*"` means all modules.

Carbon's `PulseProvider` calls this on startup to discover what's available and
validate that requested task types are supported.

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

### 3.3 `carbon.query.nl` — NL question → SQL + structured answer

**Mode**: sync  
**Timeout**: 30s

#### Payload

```json
{
  "question": "What was the total electricity consumption for Building 401 in Q1 2026?",
  "tables": ["energy_consumption"],
  "max_rows": 100,
  "scope": {
    "org_unit_ids": ["ou-abuqir"],
    "module_ids": ["em-abuqir-elec"],
    "is_read_only": true,
    "user_identifier": "admin@aastmt.edu"
  },
  "domain_vocabulary": {
    "energy_kwh": "Total electricity consumption in kilowatt-hours",
    "scope_2": "Purchased electricity (indirect emissions)"
  }
}
```

#### Result

```json
{
  "sql": "SELECT SUM(electricity_kwh) FROM energy_consumption WHERE org_unit_id = 'ou-abuqir' AND date >= '2026-01-01' AND date < '2026-04-01'",
  "rows": [{"total_kwh": 38500}],
  "row_count": 1,
  "execution_ms": 450,
  "recovery_applied": false
}
```

### 3.4 `carbon.query.explain` — Human-readable explanation of query results

**Mode**: sync  
**Timeout**: 15s

#### Payload

```json
{
  "question": "What was the total electricity consumption for Building 401 in Q1 2026?",
  "sql": "SELECT SUM(electricity_kwh) FROM energy_consumption WHERE ...",
  "row_count": 1,
  "sample_rows": [{"total_kwh": 38500}],
  "scope": { "org_unit_ids": ["ou-abuqir"], ... }
}
```

#### Result

```json
{
  "explanation": "Abu Qir campus consumed 38,500 kWh in Q1 2026 — that's 38.5 MWh of purchased electricity (Scope 2). This represents a 5% increase from Q4 2025.",
  "caveats": ["Covers Abu Qir campus only", "Does not include solar generation offsets"],
  "confidence": 0.94,
  "citations": ["energy_consumption table, 3 rows aggregated"]
}
```

### 3.5 `anomaly.detect` — Statistical anomaly detection on table profiles

> **Status: consumed by Carbon (Phase 4) — Pulse-side implementation pending.**  
> Carbon sends this task envelope today (`pulse_gateway.detect_anomalies`, invoked by
> `dq/jobs.py` for `job_type='anomaly'`); the Pulse implementation is not built yet.
> Until then Carbon degrades honestly (fail-visible): if the task cannot be
> submitted, the job is `failed` with an error — anomalies are never fabricated.
> With fewer than 6 profile snapshots Carbon completes the job locally with
> `result.state = 'insufficient_history'` and never calls Pulse.

**Mode**: async  
**Timeout**: 120s  
**Task envelope type**: `anomaly.detect` (payload nested under `payload.profile`)

#### Payload

```json
{
  "profile": {
    "table": {
      "name": "energy_consumption",
      "description": "Energy consumption readings"
    },
    "sensitivity": 25,
    "volume_anomaly_pct": 25,
    "history": [
      {
        "at": "2026-01-01T00:00:00+00:00",
        "row_count": 230,
        "completeness_pct": 99.0,
        "null_counts": {"kwh": 2},
        "mean_values": {"kwh": 12000},
        "min_values": {"kwh": 0},
        "max_values": {"kwh": 24500},
        "distinct_counts": {"kwh": 150}
      }
    ],
    "fields": {
      "kwh": [
        {
          "at": "2026-01-01T00:00:00+00:00",
          "row_count": 230,
          "null_count": 2,
          "null_pct": 0.87,
          "distinct_count": 150,
          "mean_value": 12000,
          "min_value": 0,
          "max_value": 24500
        }
      ]
    },
    "rules": [
      {
        "name": "Volume anomaly",
        "prompt": "Detect unusual row-count changes",
        "severity": "warn"
      }
    ]
  }
}
```

Notes:
- `history` is the ordered `TableProfile` snapshot history (oldest first); `fields.<name>`
  is the per-field `FieldProfile` history.
- `sensitivity` and `volume_anomaly_pct` both come from `DQProfileConfig.volume_anomaly_pct`
  (default 25) — the row-count anomaly threshold in percent.
- `rules` lists the active `anomaly_detect` rules bound to the table (name/prompt/severity).

#### Result

```json
{
  "anomalies": [
    {
      "metric": "row_count",
      "group_key": {"building": "401"},
      "expected_range": {"low": 80, "high": 100},
      "observed": 120,
      "score": 3.2,
      "severity": "warn",
      "explanation": "Row count jumped 20% above the expected range."
    }
  ]
}
```

- `severity`: one of `info | warn | error` (anything else is coerced to `warn`).
- Carbon stores each entry as a `DQAnomaly` row. Entries missing `observed` are
  dropped (never fabricated), and a `notify_event(event_type='dq_anomaly', ...)`
  notification is emitted per stored anomaly.
- If the whole response is `pulse_unavailable`/fails, Carbon records the job as
  `failed` with the honest error.

### 3.6 `carbon.anomaly.explain` — LLM-generated anomaly explanation

**Mode**: sync  
**Timeout**: 15s

> Future: `dq.suggest.feedback` — a planned async task type for user
> accept/reject feedback on DQ suggestions (Carbon `POST /dq/suggestions/<id>/accept|reject/`
> writes the feedback locally; a future Pulse task may consume it for model tuning).

#### Payload

```json
{
  "table_name": "energy_consumption",
  "anomaly": {
    "metric": "mean_kwh",
    "expected_range": {"min": 7500, "max": 16500},
    "observed": 18500,
    "z_score": 3.2,
    "severity": "warning"
  },
  "scope": { "org_unit_ids": ["ou-abuqir"], ... }
}
```

#### Result

```json
{
  "explanation": "The 54% increase in mean electricity consumption at Abu Qir is likely driven by new cooling equipment installed in January 2026. This is not a data error — it reflects real operational change. Recommend reviewing the Facility Change Log for Jan 2026.",
  "investigation_steps": [
    "Check Facility Change Log for Jan 2026",
    "Compare per-building breakdown for Abu Qir",
    "Review if this level persists in Feb-Mar 2026"
  ]
}
```

### 3.7 `carbon.report.draft` — Dashboard data → narrative report (7-stage pipeline)

**Mode**: async  
**Timeout**: 60s

#### Payload

```json
{
  "report_type": "ghg_annual",
  "period_start": "2026-01-01",
  "period_end": "2026-12-31",
  "scope": { "org_unit_ids": ["ou-abuqir", "ou-smouha"], "is_read_only": true, ... }
}
```

#### Result

```json
{
  "title": "Annual GHG Report — Abu Qir & Smouha Campuses",
  "summary": "Total emissions for the selected campuses in 2026 were 13,550.7 tCO₂e, a 3.2% reduction from 2025.",
  "report_type": "ghg_annual",
  "period_start": "2026-01-01",
  "period_end": "2026-12-31",
  "generated_at": "2026-08-11T12:00:00Z",
  "sections": [
    {
      "title": "Executive Summary",
      "content": "Total emissions for AASTMT in 2026 were 13,550.7 tCO₂e...",
      "sql": "SELECT scope, SUM(tco2e) FROM ...",
      "data": [{"scope": "Scope 1", "tco2e": 1250.5}],
      "narrative": "Scope 1 emissions decreased 8% year-over-year, driven by...",
      "caveat": "Excludes Abu Qir solar generation offsets"
    }
  ]
}
```

### 3.8 `carbon.schema.analyze` — Schema change impact analysis

**Mode**: sync  
**Timeout**: 15s

#### Payload

```json
{
  "schema_changes": [
    {"change": "column_removed", "table_name": "energy_consumption", "field_name": "building_name"},
    {"change": "column_added", "table_name": "energy_consumption", "field_name": "co2e_factor"}
  ],
  "context": "Migration: replacing building_name with foreign key to buildings table",
  "scope": { "org_unit_ids": ["*"], ... }
}
```

#### Result

```json
{
  "analysis": [
    {
      "change": "column_removed:energy_consumption.building_name",
      "impact": "Any DQ rules referencing building_name will break. The nl_query handler currently generates SQL that joins on building_name for human-readable output.",
      "severity": "high",
      "suggested_action": "Update all DQ rules to use buildings.name via JOIN. Regenerate the knowledge graph's table relationships."
    },
    {
      "change": "column_added:energy_consumption.co2e_factor",
      "impact": "New emission factor column will be ignored by existing DQ rules. Consider adding validation rules for co2e_factor range and nullability.",
      "severity": "low",
      "suggested_action": "Add DQ rule: co2e_factor must be >0 and not null when activity > 0."
    }
  ]
}
```

### 3.9 `carbon.fix.suggest` — Suggest data quality fixes

**Mode**: sync  
**Timeout**: 15s

> ⚠️ HR-CRITICAL: ALL fix suggestions hardcode `requires_confirmation: true`. Even if the LLM returns `requires_confirmation: false`, Pulse overrides it to `true`. Never auto-apply fixes.

#### Payload

```json
{
  "issue_type": "null_values",
  "table_name": "energy_consumption",
  "issue_description": "12 rows have NULL electricity_kwh values for Jan 2026",
  "affected_rows": [
    {"building_id": "401", "month": "2026-01", "electricity_kwh": null},
    {"building_id": "402", "month": "2026-01", "electricity_kwh": null}
  ],
  "profile": {"mean_kwh": 12000, "stddev_kwh": 4500},
  "scope": { "org_unit_ids": ["ou-abuqir"], ... }
}
```

#### Result

```json
{
  "issue_type": "null_values",
  "table_name": "energy_consumption",
  "suggestions": [
    {
      "description": "Fill NULL electricity_kwh with the monthly mean (12,000 kWh) for Jan 2026. This is low risk because January typically has low variance across buildings.",
      "confidence": 0.82,
      "estimated_affected_rows": 12,
      "requires_confirmation": true,
      "suggested_action_type": "impute_from_mean"
    },
    {
      "description": "Query the electricity meter database for Jan 2026 readings for these 12 buildings. This is the most accurate approach if meter data is available.",
      "confidence": 0.95,
      "estimated_affected_rows": 12,
      "requires_confirmation": true,
      "suggested_action_type": "external_lookup"
    }
  ]
}
```

---

## 4. Agent Card (Discovery)

Pulse publishes task type definitions at `GET /tasks/modules?instance_id=carbon`.
Carbon's `PulseProvider` reads this on startup to know what's available.

```json
{
  "instance_id": "carbon",
  "modules": {
    "dq.validate": {
      "description": "Validate rows against natural language DQ rules",
      "mode": "sync",
      "input_schema": { "rules": "list[DqRule]", "rows": "list[dict]", "context": "dict" },
      "output_schema": { "results": "list[DqRuleResult]" }
    },
    "dq.suggest": {
      "description": "Suggest DQ rules from table profile",
      "mode": "async",
      "input_schema": { "table": "TableProfile" },
      "output_schema": { "suggestions": "list[DqSuggestion]" }
    },
    "carbon.query.nl": {
      "description": "NL question → SQL + structured answer",
      "mode": "sync",
      "input_schema": { "question": "str", "tables": "list[str]", "scope": "Scope" },
      "output_schema": { "sql": "str", "rows": "list[dict]", "row_count": "int" }
    },
    "carbon.query.explain": {
      "description": "Human-readable explanation of query results",
      "mode": "sync",
      "input_schema": { "question": "str", "sql": "str", "sample_rows": "list[dict]" },
      "output_schema": { "explanation": "str", "caveats": "list[str]" }
    },
    "carbon.anomaly.detect": {
      "description": "Statistical anomaly detection on table profiles",
      "mode": "async",
      "input_schema": { "table_name": "str", "profile_history": "list[dict]", "sensitivity": "float" },
      "output_schema": { "anomalies": "list[Anomaly]" }
    },
    "carbon.anomaly.explain": {
      "description": "LLM-generated anomaly explanation",
      "mode": "sync",
      "input_schema": { "table_name": "str", "anomaly": "dict", "scope": "Scope" },
      "output_schema": { "explanation": "str", "investigation_steps": "list[str]" }
    },
    "carbon.report.draft": {
      "description": "Dashboard data → narrative report (7-stage pipeline)",
      "mode": "async",
      "input_schema": { "report_type": "str", "period_start": "str", "period_end": "str", "scope": "Scope" },
      "output_schema": { "title": "str", "sections": "list[ReportSection]" }
    },
    "carbon.schema.analyze": {
      "description": "Analyze schema changes for impact → action",
      "mode": "sync",
      "input_schema": { "schema_changes": "list[SchemaChange]", "scope": "Scope" },
      "output_schema": { "analysis": "list[SchemaImpact]" }
    },
    "carbon.fix.suggest": {
      "description": "Suggest data quality fixes (always requires confirmation)",
      "mode": "sync",
      "input_schema": { "issue_type": "str", "table_name": "str", "issue_description": "str" },
      "output_schema": { "suggestions": "list[FixSuggestion]" }
    }
  }
}
```

---

## 5. Carbon-Side Implementation (Carbon `ai/` App)

Carbon's AI integration lives in `backend/ai/` — a single Django app with:

- **`ai/protocol.py`** — `AIProvider` ABC + typed dataclasses (the swappable contract)
- **`ai/providers/pulse.py`** — `PulseProvider` (implements `AIProvider` via `POST /tasks`)
- **`ai/intelligence.py`** — `CarbonIntelligence` (scope resolution, domain context, caching)
- **`ai/views.py`** — DRF endpoints at `/api/v1/ai/*`

The `pulse_gateway.py` thin client is DEPRECATED and will be removed after full migration.
See [docs/AI_WORKSPACE_ARCHITECTURE.md](AI_WORKSPACE_ARCHITECTURE.md) for the architecture standard and [plans/CARBON_AI_WORKSPACE_PHASED_PLAN.md](../plans/CARBON_AI_WORKSPACE_PHASED_PLAN.md) for the current phased implementation plan.

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

- **Today (Phase 7 complete)**: All 9 task types implemented Pulse-side — DQ validate/suggest, NL query/explain, anomaly detect/explain, report draft, schema analyze, fix suggest
- **Today (Carbon Phase 2 planned)**: Swappable `AIProvider` protocol + `CarbonIntelligence` service — Carbon never imports Pulse directly
- **Tomorrow**: Carbon DQ Level 2 — business-rule-aware validation with AI-powered exception handling
- **Next month**: Carbon Coworker Chatbot — domain-aware, scope-respecting AI assistant embedded in Carbon's shell
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
| Streaming | SSE + gRPC streams | SSE | N/A (sync task or poll async) |
| Auth | OAuth2, API keys | OAuth2, Bearer | API key (simple) |
| Complexity | Full protocol (11 operations) | Full protocol | 2 operations (POST + GET) |

**Design decision**: We're NOT implementing full A2A. We're adopting its **task-oriented
philosophy** and **Agent Card discovery pattern** but keeping the wire protocol
minimal — 2 endpoints instead of 11. Carbon doesn't need multi-turn conversations,
push notifications, or task cancellation (at least not yet).

If we ever need full A2A, the migration path is clear: the task envelope maps 1:1.
