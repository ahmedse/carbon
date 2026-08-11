# Carbon Phase 2 — AI Intelligence Service

**Date:** 2026-08-11  
**Status:** Wave A 🔶 READY FOR WORKERS (`TASK-CARBON-AI-WAVE-A.md`) | Waves B–P ※ SPEC READY  
**Depends on:** Phase 1 DQ Core (P0–P4 complete per `TASK-DQ-CORE-P4-PULSE.md`)  
**Companion docs:** `docs/CARBON-DESIGN.md`, `docs/PULSE_CONTRACT_SPEC.md`, `plans/CARBON_DQ_CORE_PLAN.md`, `plans/TASK-CARBON-AI-WAVE-A.md`

---

## 0. Vision

Carbon's AI capability is **not** a chatbot. It is a **platform intelligence service** that any Carbon subsystem can consume — DQ engine, chat UI, report generator, anomaly scanner, schema analyzer, rule suggester.

Today: each subsystem calls `pulse_gateway.py` directly. This is fragile — Pulse is wired into DQ code, chat code, everywhere. Swap Pulse for another AI backend? Rewrite every consumer.

**Phase 2** introduces a single `ai/` Django app that:
- Defines **one crystal-clear protocol** (`AIProvider` ABC) — the contract any AI backend must implement
- Implements **one Pulse provider** (`PulseProvider`) behind that protocol
- Provides **one intelligence service** (`CarbonIntelligence`) that resolves scope, injects domain context, and delegates to the provider
- Can be **swapped to any AI backend** (Azure OpenAI, Claude, local LLM) by changing **one config variable**

```
                    ┌──────────────────────────────────────┐
                    │           CARBON AI (ai/)            │
                    │                                      │
    DQ Engine ─────→│  POST /api/v1/ai/dq/validate/        │
    Chat UI ───────→│  POST /api/v1/ai/chat/              │
    Report Gen ────→│  POST /api/v1/ai/report/draft/      │──→ AIProvider
    Anomaly ───────→│  POST /api/v1/ai/anomaly/detect/    │     │
    Rule Suggest ──→│  POST /api/v1/ai/dq/suggest/        │     │
    Schema ────────→│  POST /api/v1/ai/schema/analyze/    │     │
                    │                                      │     ▼
                    │  One module:                         │  PulseProvider
                    │  - User scope resolution             │  (or ClaudeProvider)
                    │  - Domain context injection          │  (or AzureProvider)
                    │  - AI provider dispatch              │
                    │  - Response caching                  │
                    │  - Fail-visible degradation          │
                    │  - Audit trail + cost tracking       │
                    └──────────────────────────────────────┘
```

---

## 1. Design Principles

1. **Protocol-first.** `ai/protocol.py` is the single source of truth. It has ZERO imports from Pulse, Django ORM, or any provider. Pure ABCs and dataclasses.
2. **Provider-agnostic.** Carbon never imports `PulseProvider`. It imports `AIProvider`. Swap backends in `.env` — zero code changes.
3. **Scope is mandatory.** Every AI call carries a `Scope` (org_units, modules, read_only). Providers MUST respect it.
4. **Domain-aware.** Carbon injects GHG vocabulary, business rules, and reporting period semantics before any AI call.
5. **Fail-visible, never fail-open.** AI unavailable → `status: "provider_unavailable"`. No silent pass.
6. **API gateway for chat, direct DB for analytics.** Chat/coworker queries go through Carbon's REST API (RBAC, soft-delete, audit). DQ profiling and anomaly detection use direct DB with injected scope filters (performance).
7. **Pulse is a plug.** The PulseProvider is ~300 lines of HTTP mapping. Delete it, write a new one, change one config — everything works.

---

## 2. Architecture

### 2.1 File structure

```
backend/ai/
├── __init__.py              # Django AppConfig: "Carbon AI Intelligence"
├── protocol.py              # THE CONTRACT — AIProvider ABC + all dataclasses
├── providers/
│   ├── __init__.py
│   ├── _http.py             # Thin HTTP helpers (shared across HTTP providers)
│   └── pulse.py             # PulseProvider — implements AIProvider via POST /tasks
├── intelligence.py          # CarbonIntelligence — scope + domain + provider dispatch
├── cache.py                 # Response cache (Pulse answers, DQ results per row version)
├── views.py                 # DRF views — thin, delegates to intelligence.py
├── serializers.py           # Request/response DRF serializers
├── permissions.py           # HasAiAccess permission
├── urls.py                  # /api/v1/ai/*
├── signals.py               # Audit logging, cost tracking
├── apps.py                  # AppConfig
└── tests/
    ├── test_protocol.py     # Protocol contract tests (dataclass integrity)
    ├── test_protocol_swap.py # MockProvider → proves swap works with zero Carbon changes
    ├── test_pulse_provider.py # PulseProvider unit tests
    ├── test_intelligence.py  # CarbonIntelligence scope + domain tests
    ├── test_views.py         # API endpoint tests
    └── test_cache.py         # Cache behavior tests
```

### 2.2 Data flow

```
Carbon consumer (DQ engine / Chat UI / Report)
        │
        ▼
CarbonIntelligence(user)
        │
        ├── 1. resolve_scope(user) → Scope(org_units, modules, read_only)
        ├── 2. load_domain_context() → GHG vocab, business rules, period semantics
        ├── 3. enrich_request(payload, scope, domain)
        │
        ▼
AIProvider (abstract)
        │
        ▼
PulseProvider (concrete)
        │
        ├── _post_task(base_url, api_key, task_type, payload)
        │     │
        │     ▼
        │   POST /tasks  (Pulse)
        │
        └── parse response → typed dataclass
              │
              ▼
CarbonIntelligence ← response dataclass
        │
        ├── 4. cache_response (if cacheable)
        ├── 5. log_audit (user, task_type, latency, cost)
        │
        ▼
Consumer ← business-logic response
```

### 2.3 Provider loading

```python
# backend/config/settings.py

# ── AI Provider ──────────────────────────────────────────
# Swap AI backends by changing these two values.
# Everything else in Carbon remains unchanged.

AI_PROVIDER_CLASS = os.environ.get(
    "AI_PROVIDER_CLASS",
    "ai.providers.pulse.PulseProvider"
)

AI_PROVIDER_URL = os.environ.get(
    "AI_PROVIDER_URL",
    "http://127.0.0.1:9100"
)

AI_PROVIDER_API_KEY = os.environ.get(
    "AI_PROVIDER_API_KEY",
    ""
)

# ── AI Intelligence ─────────────────────────────────────
AI_CACHE_TTL_SECONDS = int(os.environ.get("AI_CACHE_TTL_SECONDS", 300))
AI_MAX_CHAT_HISTORY = int(os.environ.get("AI_MAX_CHAT_HISTORY", 50))
AI_RATE_LIMIT_PER_MINUTE = int(os.environ.get("AI_RATE_LIMIT_PER_MINUTE", 30))
```

---

## 3. The Protocol — `ai/protocol.py`

The protocol defines **everything** in dataclasses. No behavior, no imports from Django/Pulse/providers. This file is the contract.

### 3.1 Scope

```python
@dataclass
class Scope:
    """User scope — injected into every AI call."""
    org_unit_ids: list[str]          # ["*"] = all, ["ou-1","ou-2"] = scoped
    module_ids: list[str]             # Specific modules the user can access
    is_read_only: bool = False        # True → provider must not suggest mutations
    is_superuser: bool = False        # True → full access
    user_identifier: str = ""         # For audit trail
```

### 3.2 Shared response envelope

Every response dataclass follows this pattern:
```python
@dataclass
class SomeResponse:
    status: str                       # "completed" | "provider_unavailable" | "failed"
    error: dict[str, str] | None = None  # {"code": "...", "message": "..."}
    execution_ms: int = 0
```

### 3.3 Task contracts (summary — see §8 for full definition)

| Contract | Input dataclass | Output dataclass |
|----------|----------------|------------------|
| `validate_dq` | `DqValidateRequest` | `DqValidateResponse` |
| `suggest_dq` | `DqSuggestRequest` | `DqSuggestResponse` |
| `query_nl` | `NlQueryRequest` | `NlQueryResponse` |
| `explain_query` | `NlExplainRequest` | `NlExplainResponse` |
| `detect_anomalies` | `AnomalyDetectRequest` | `AnomalyDetectResponse` |
| `explain_anomaly` | `AnomalyExplainRequest` | `AnomalyExplainResponse` |
| `draft_report` | `ReportDraftRequest` | `ReportDraftResponse` |
| `analyze_schema` | `SchemaAnalyzeRequest` | `SchemaAnalyzeResponse` |
| `suggest_fix` | `FixSuggestRequest` | `FixSuggestResponse` |

### 3.4 The AIProvider ABC

```python
class AIProvider(ABC):
    """One abstract class. Nine methods. Each backend implements them."""

    @property
    @abstractmethod
    def provider_name(self) -> str: ...

    @property
    @abstractmethod
    def provider_version(self) -> str: ...

    @abstractmethod
    def health_check(self) -> ProviderStatus: ...

    @abstractmethod
    def validate_dq(self, request: DqValidateRequest) -> DqValidateResponse: ...
    @abstractmethod
    def suggest_dq(self, request: DqSuggestRequest) -> DqSuggestResponse: ...
    @abstractmethod
    def query_nl(self, request: NlQueryRequest) -> NlQueryResponse: ...
    @abstractmethod
    def explain_query(self, request: NlExplainRequest) -> NlExplainResponse: ...
    @abstractmethod
    def detect_anomalies(self, request: AnomalyDetectRequest) -> AnomalyDetectResponse: ...
    @abstractmethod
    def explain_anomaly(self, request: AnomalyExplainRequest) -> AnomalyExplainResponse: ...
    @abstractmethod
    def draft_report(self, request: ReportDraftRequest) -> ReportDraftResponse: ...
    @abstractmethod
    def analyze_schema(self, request: SchemaAnalyzeRequest) -> SchemaAnalyzeResponse: ...
    @abstractmethod
    def suggest_fix(self, request: FixSuggestRequest) -> FixSuggestResponse: ...
```

---

## 4. The Intelligence Layer — `ai/intelligence.py`

```python
class CarbonIntelligence:
    """
    Domain-aware, scope-respecting AI service.
    
    Every Carbon subsystem calls this — never the provider directly.
    """
    
    def __init__(self, user):
        self.user = user
        self.scope = self._resolve_scope(user)
        self.provider = self._load_provider()
        self.domain = self._load_domain_context()
    
    def _resolve_scope(self, user) -> Scope:
        """Carbon RBAC → Scope the AI provider MUST respect."""
        # Uses accounts.rbac_utils: get_allowed_org_unit_ids, user_has_global_role
        # Uses accounts.constants: READ_ONLY_ROLES
        ...
    
    def _load_provider(self) -> AIProvider:
        """import_string(settings.AI_PROVIDER_CLASS)"""
        ...
    
    def _load_domain_context(self) -> dict:
        """GHG vocabulary, emission factor semantics, reporting period logic.
        Loaded from instance YAML + DB (EmissionFactor, ReportingPeriod metadata)."""
        ...
    
    # ── Public API ──────────────────────────────────────────
    
    def chat(self, question: str, conversation_id: str = None,
             page_context: dict = None) -> dict:
        """NL question → scoped answer. The coworker interface."""
        ...
    
    def validate_dq(self, rules, rows) -> dict:
        """DQ validation through AI provider."""
        ...
    
    # ... same for all 9 task types
```

**Key behaviors:**
1. `_resolve_scope()` is called once per `CarbonIntelligence` instance. Result cached.
2. `_load_domain_context()` includes: GHG vocabulary (terms → column mappings), business rules (co2e = activity × factor × GWP), reporting period semantics, recent emission factor changes.
3. Every public method: resolve scope → enrich with domain → delegate to provider → cache → audit log → return.
4. Provider errors are caught and converted to `provider_unavailable` — never propagate to callers.

---

## 5. Waves

### Wave A: Protocol + Mock Provider (Carbon side, ~2 days)

**Task file:** `plans/TASK-CARBON-AI-WAVE-A.md` (787 lines — worker prompts, exact specs, gates)

**Goal:** Define the contract. Prove it works with a fake backend.

| # | Deliverable | File |
|---|------------|------|
| A1 | `ai/protocol.py` — all dataclasses + `AIProvider` ABC + `ProviderStatus` | new |
| A2 | `tests/ai/test_protocol.py` — dataclass integrity tests (serialization, defaults) | new |
| A3 | `tests/ai/test_protocol_swap.py` — `MockProvider` implements all 9 methods; prove `CarbonIntelligence` works with it | new |

**Gate:** MockProvider passes full test suite. If a real provider implements the same ABC, Carbon requires zero code changes.

**Config:** `AI_PROVIDER_CLASS`, `AI_PROVIDER_URL`, `AI_PROVIDER_API_KEY` added to settings.

---

### Wave B: Pulse Provider (Carbon side, ~2–3 days)

**Goal:** Implement `PulseProvider` — the only file in Carbon that knows Pulse exists.

| # | Deliverable | File |
|---|------------|------|
| B1 | `ai/providers/_http.py` — thin HTTP helpers (`_post_task`, `_get_modules`, `_poll_task`) | new |
| B2 | `ai/providers/pulse.py` — `PulseProvider(AIProvider)` with all 9 methods | new |
| B3 | `tests/ai/test_pulse_provider.py` — HTTP-level tests (mocked `requests`) | new |

**PulseProvider details:**
- `_post_task()` wraps `requests.post(f'{base_url}/tasks', json=envelope, timeout=...)`
- Every method: build Pulse task envelope → POST → parse response → return typed dataclass
- On HTTP error / timeout / malformed: return response with `status="provider_unavailable"`
- `health_check()` → `GET /tasks/modules?instance_id=carbon` → `ProviderStatus`

**Existing code:** `pulse_gateway.py` remains untouched during Wave B. It is deprecated in Wave C.

---

### Wave C: CarbonIntelligence + Migration (Carbon side, ~2–3 days)

**Goal:** Build the intelligence service. Wire DQ to use it instead of raw `PulseGateway`.

| # | Deliverable | File |
|---|------------|------|
| C1 | `ai/intelligence.py` — `CarbonIntelligence` with scope resolution + domain context | new |
| C2 | `ai/cache.py` — simple TTL cache for AI responses (keyed on task_type + hash of payload) | new |
| C3 | `ai/signals.py` — audit logging (who called what AI task, latency, cost) | new |
| C4 | Migrate `dq/services.py` — replace `PulseGateway()` calls with `CarbonIntelligence(user)` | edit |
| C5 | Migrate `dq/jobs.py` — same treatment for async job paths | edit |
| C6 | `tests/ai/test_intelligence.py` — scope resolution, domain injection, cache hits | new |

**Migration pattern:**
```python
# Before (dq/services.py):
gateway = PulseGateway()
result = gateway.validate_dq_rules(rules, rows)

# After:
ai = CarbonIntelligence(request.user)
result = ai.validate_dq(rules, rows)
```

**Backward compatibility:** `pulse_gateway.py` is NOT deleted. It's marked deprecated with a docstring. Removed in a cleanup wave after all consumers are migrated.

---

### Wave D: DQ Level 2 — Business Rules + Pulse Integration (Carbon side, ~3–4 days)

**Goal:** DQ engine runs business-level rules (cross-field, cross-table, temporal) powered by the AI intelligence service.

| # | Deliverable | File |
|---|------------|------|
| D1 | `ai/views.py` — `POST /api/v1/ai/dq/validate/`, `/dq/suggest/`, `/anomaly/detect/`, `/anomaly/explain/`, `/fix/suggest/` | new |
| D2 | `ai/serializers.py` — DRF serializers for all AI endpoints | new |
| D3 | `ai/permissions.py` — `HasAiAccess` (requires authenticated + scoped role) | new |
| D4 | `ai/urls.py` — wire all endpoints under `/api/v1/ai/` | new |
| D5 | Extend `dq/gate.py` — gate now runs business_rule types (deterministic) + dispatches `nl_check` to `CarbonIntelligence` | edit |
| D6 | Wire `carbon.anomaly.detect` + `carbon.anomaly.explain` through `CarbonIntelligence` | edit |
| D7 | `DQSuggestion` model + accept/reject flow (from TASK-DQ-CORE-P4-PULSE) | edit |
| D8 | `DQAnomaly` model + anomaly job (from TASK-DQ-CORE-P4-PULSE) | edit |
| D9 | Fail-visible: `DQResult.status = 'skipped_unavailable'` when AI is down | edit |
| D10 | `tests/ai/test_views.py` — integration tests through DRF test client | new |

**Note:** D5–D9 are the implementation of `TASK-DQ-CORE-P4-PULSE.md` but wired through `CarbonIntelligence` instead of raw `PulseGateway`.

---

### Wave E: Coworker Chatbot (Carbon + Frontend, ~4–5 days)

**Goal:** A chat UI in Carbon that talks to `POST /api/v1/ai/chat/`. Domain-aware, scope-respecting, conversation-persistent.

| # | Deliverable | File |
|---|------------|------|
| E1 | `ai/views.py` — `POST /api/v1/ai/chat/` — delegates to `CarbonIntelligence.chat()` | edit |
| E2 | `ai/views.py` — `GET /api/v1/ai/chat/history/` — conversation history for current user | edit |
| E3 | `ai/views.py` — `GET /api/v1/ai/chat/context/` — page-aware context hints | edit |
| E4 | `ai/models.py` — `AiConversation` + `AiMessage` models (if not using Pulse-side storage) | new |
| E5 | Frontend: `src/apps/coworker/CoworkerPanel.jsx` — chat UI component | new |
| E6 | Frontend: `src/apps/coworker/CoworkerContext.jsx` — conversation state management | new |
| E7 | Frontend: Integrate `CoworkerPanel` into `Shell.jsx` (replaces or extends `PulsePane`) | edit |
| E8 | Frontend: Page-aware context — current table/module injected as system context | edit |

**Chat behavior:**
1. User types: "What's my Scope 2 total for Q1 2025 at Alamein?"
2. `CarbonIntelligence.chat()`:
   - Resolves scope: user's org_units includes Alamein campus
   - Enriches with domain: "Scope 2" means purchased electricity, "Q1 2025" maps to ReportingPeriod, emission factors use `co2e_kg = activity_amount × emission_factor × GWP`
   - Calls `provider.query_nl()` with scope filters injected
   - Calls `provider.explain_query()` for business-English answer
   - Returns: `{answer, sql, rows, citations, caveats}`
3. Chat UI renders answer with markdown, shows citations/source data on expand, offers follow-up suggestions.

**Graceful degradation:** If Pulse is down → "I'm currently unavailable. Carbon's DQ checks and calculations continue to work normally."

**Key difference from current `PulsePane.jsx`:**
- PulsePane: embeds Pulse's generic widget iframe → Pulse sees Carbon's DB but not Carbon's RBAC
- CoworkerPanel: calls Carbon's API → Carbon resolves scope → Carbon calls Pulse → Carbon returns scoped answer

This means the chatbot **actually behaves like an employee** — same data perimeter, same permissions, same audit trail.

---

### Wave P: Pulse Scope Contract (Pulse side, ~1–2 days)

**Goal:** Pulse's `carbon.query.nl` handler accepts and enforces scope filters.

| # | Deliverable | File |
|---|------------|------|
| P1 | Update `api/tasks.py:_handle_nl_query` — accept `scope` in payload, inject `WHERE org_unit_id IN (...)` into generated SQL | edit |
| P2 | Update `api/tasks.py:_handle_anomaly_detect` — accept `scope`, filter profile history to org_units | edit |
| P3 | Update `api/tasks.py:_handle_report_draft` — accept `scope`, scope-filter all SQL sections | edit |
| P4 | Update `api/tasks.py:_handle_schema_analyze` — accept `scope`, only analyze tables within org_units | edit |
| P5 | Carbon domain pack enrichment — update `instances/carbon/instance.yaml` with GHG vocabulary, business rules, reporting period semantics | edit |
| P6 | System prompt: add coworker persona for Carbon queries ("You are a carbon accounting expert at AASTMT...") | edit |
| P7 | `tests/test_tasks.py` — scope injection tests (SQL contains org_unit filter, rows scoped correctly) | edit |

---

## 6. API Surface — Complete

All under `/api/v1/ai/`:

| Endpoint | Method | Consumer | Auth | Pulse task |
|----------|--------|----------|------|------------|
| `/chat/` | POST | Coworker UI | `HasAiAccess` | `carbon.query.nl` + `carbon.query.explain` |
| `/chat/history/` | GET | Coworker UI | `HasAiAccess` | (Carbon DB) |
| `/chat/context/` | GET | Coworker UI | `HasAiAccess` | (Carbon DB) |
| `/dq/validate/` | POST | DQ Engine | `HasAiAccess` | `dq.validate` |
| `/dq/suggest/` | POST | DQ Rules UI | `HasAiAccess` | `dq.suggest` |
| `/anomaly/detect/` | POST | DQ Jobs | `HasAiAccess` | `carbon.anomaly.detect` |
| `/anomaly/explain/` | POST | DQ UI | `HasAiAccess` | `carbon.anomaly.explain` |
| `/report/draft/` | POST | Report UI | `HasAiAccess` | `carbon.report.draft` |
| `/schema/analyze/` | POST | Schema UI | `HasAiAccess` | `carbon.schema.analyze` |
| `/fix/suggest/` | POST | DQ UI | `HasAiAccess` | `carbon.fix.suggest` |
| `/status/` | GET | Any | `IsAuthenticated` | Pulse health check |

---

## 7. Gates — Per Wave

### Wave A: Protocol
- [ ] `ai/protocol.py` exists with 0 imports from Django/Pulse/providers
- [ ] `MockProvider` passes all 9 method calls
- [ ] `CarbonIntelligence` works identically with `MockProvider` and `PulseProvider`
- [ ] `AI_PROVIDER_CLASS`, `AI_PROVIDER_URL`, `AI_PROVIDER_API_KEY` in settings

### Wave B: Pulse Provider
- [ ] `PulseProvider` implements all 9 `AIProvider` methods
- [ ] HTTP-level tests with mocked `requests` cover: success, timeout, connection error, malformed JSON
- [ ] `health_check()` returns `ProviderStatus` from real `GET /tasks/modules`

### Wave C: Intelligence + Migration
- [ ] `CarbonIntelligence._resolve_scope()` correctly resolves org_units and read_only from user
- [ ] `CarbonIntelligence._load_domain_context()` returns GHG vocabulary and business rules
- [ ] All DQ paths use `CarbonIntelligence` instead of raw `PulseGateway`
- [ ] `pulse_gateway.py` marked deprecated but NOT deleted
- [ ] Existing DQ tests still pass (backward compatibility)

### Wave D: DQ Level 2
- [ ] `POST /api/v1/ai/dq/validate/` returns scoped validation results
- [ ] Business rules evaluate correctly in gate and jobs
- [ ] `DQSuggestion` accept → creates `DQRule` with `RuleFieldAssignment`
- [ ] `DQAnomaly` stores expected-vs-observed with Pulse explanation
- [ ] Pulse down → `DQResult.status='skipped_unavailable'`, score reflects gap
- [ ] ≥ 20 new tests across DQ Level 2 paths

### Wave E: Coworker Chatbot
- [ ] `POST /api/v1/ai/chat/` returns scoped, domain-aware answers
- [ ] Chat history persists per user across sessions
- [ ] Page-aware context: current table/module injected into system prompt
- [ ] Graceful degradation: Pulse down → friendly unavailable message
- [ ] CoworkerPanel renders in Shell, replaces PulsePane
- [ ] ≥ 10 new tests for chat endpoints

### Wave P: Pulse Scope
- [ ] `carbon.query.nl` injects scope filters into generated SQL
- [ ] Scoped queries return only data within user's org_units
- [ ] Carbon domain pack enriched with GHG vocabulary
- [ ] ≥ 4 new Pulse tests for scope injection

---

## 8. Appendix: Full Protocol Definition

### 8.1 DQ Validate

```python
@dataclass
class DqRuleInput:
    id: str
    prompt: str
    fields: list[str]
    severity: str  # "info" | "warn" | "error"

@dataclass
class DqValidateRequest:
    rules: list[DqRuleInput]
    rows: list[dict[str, Any]]
    context: dict[str, Any] = field(default_factory=dict)
    scope: Scope | None = None

@dataclass
class DqRuleResult:
    rule_id: str
    status: str  # "pass" | "fail" | "skipped_unavailable"
    failing_rows: list[int] | None = None
    explanation: str | None = None
    confidence: float | None = None

@dataclass
class DqValidateResponse:
    status: str
    results: list[DqRuleResult] = field(default_factory=list)
    error: dict[str, str] | None = None
    execution_ms: int = 0
```

### 8.2 DQ Suggest

```python
@dataclass
class TableProfile:
    name: str
    description: str
    row_count: int
    columns: list[dict[str, Any]]

@dataclass
class DqSuggestRequest:
    table: TableProfile
    scope: Scope | None = None

@dataclass
class DqSuggestion:
    definition: dict[str, Any]  # Complete v1 rule definition
    rationale: str
    severity: str
    confidence: float
    dimension: str

@dataclass
class DqSuggestResponse:
    status: str
    suggestions: list[DqSuggestion] = field(default_factory=list)
    error: dict[str, str] | None = None
    execution_ms: int = 0
```

### 8.3 NL Query

```python
@dataclass
class NlQueryRequest:
    question: str
    tables: list[str] | None = None
    max_rows: int = 100
    scope: Scope | None = None
    domain_vocabulary: dict[str, str] | None = None

@dataclass
class NlQueryResponse:
    status: str
    sql: str | None = None
    rows: list[dict[str, Any]] | None = None
    row_count: int = 0
    execution_ms: int = 0
    recovery_applied: bool = False
    error: dict[str, str] | None = None
```

### 8.4 NL Query Explain

```python
@dataclass
class NlExplainRequest:
    question: str
    sql: str
    row_count: int
    sample_rows: list[dict[str, Any]]
    scope: Scope | None = None

@dataclass
class NlExplainResponse:
    status: str
    explanation: str | None = None
    caveats: list[str] = field(default_factory=list)
    error: dict[str, str] | None = None
    execution_ms: int = 0
```

### 8.5 Anomaly Detection

```python
@dataclass
class AnomalyDetectRequest:
    table_name: str
    profile_history: list[dict[str, Any]]
    sensitivity: float = 2.0
    volume_threshold_pct: float = 30.0
    scope: Scope | None = None

@dataclass
class DetectedAnomaly:
    metric: str
    expected_range: dict[str, float]
    observed: float
    z_score: float
    severity: str  # "error" | "warning"
    explanation: str | None = None

@dataclass
class AnomalyDetectResponse:
    status: str
    anomalies: list[DetectedAnomaly] = field(default_factory=list)
    history_snapshots: int = 0
    error: dict[str, str] | None = None
    execution_ms: int = 0
```

### 8.6 Anomaly Explain

```python
@dataclass
class AnomalyExplainRequest:
    table_name: str
    anomaly: dict[str, Any]
    scope: Scope | None = None

@dataclass
class AnomalyExplainResponse:
    status: str
    explanation: str | None = None
    investigation_steps: list[str] = field(default_factory=list)
    error: dict[str, str] | None = None
    execution_ms: int = 0
```

### 8.7 Report Draft

```python
@dataclass
class ReportDraftRequest:
    report_type: str
    period_start: str  # ISO date
    period_end: str    # ISO date
    scope: Scope | None = None

@dataclass
class ReportSection:
    title: str
    content: str  # Markdown
    sql: str | None = None
    data: list[dict[str, Any]] | None = None
    narrative: str | None = None
    caveat: str | None = None

@dataclass
class ReportDraftResponse:
    status: str
    title: str | None = None
    summary: str | None = None
    report_type: str = ""
    period_start: str = ""
    period_end: str = ""
    generated_at: str = ""
    sections: list[ReportSection] = field(default_factory=list)
    error: dict[str, str] | None = None
    execution_ms: int = 0
```

### 8.8 Schema Analyze

```python
@dataclass
class SchemaChange:
    change: str
    table_name: str
    field_name: str | None = None

@dataclass
class SchemaAnalyzeRequest:
    schema_changes: list[SchemaChange]
    context: str | None = None
    scope: Scope | None = None

@dataclass
class SchemaImpact:
    change: str
    impact: str
    severity: str  # "low" | "medium" | "high" | "critical"
    suggested_action: str

@dataclass
class SchemaAnalyzeResponse:
    status: str
    analysis: list[SchemaImpact] = field(default_factory=list)
    error: dict[str, str] | None = None
    execution_ms: int = 0
```

### 8.9 Fix Suggest

```python
@dataclass
class FixSuggestRequest:
    issue_type: str
    table_name: str
    issue_description: str
    affected_rows: list[dict[str, Any]] | None = None
    profile: dict[str, Any] | None = None
    scope: Scope | None = None

@dataclass
class FixSuggestion:
    description: str
    confidence: float
    estimated_affected_rows: int
    requires_confirmation: bool  # ALWAYS True — never auto-fix
    suggested_action_type: str

@dataclass
class FixSuggestResponse:
    status: str
    issue_type: str = ""
    table_name: str = ""
    suggestions: list[FixSuggestion] = field(default_factory=list)
    error: dict[str, str] | None = None
    execution_ms: int = 0
```

---

## 9. Migration Timeline

```
Wave A: Protocol          ████░░░░░░░░░░░░░░  2 days
Wave B: Pulse Provider    ░░░░████████░░░░░░░  2-3 days
Wave C: Intelligence      ░░░░░░░░░████████░░  2-3 days
Wave D: DQ Level 2        ░░░░░░░░░░░░░░░████  3-4 days
Wave E: Coworker Chatbot  ░░░░░░░░░░░░░░░░███  4-5 days
Wave P: Pulse Scope       ░░░░░░░░░░░░░░░░░██  1-2 days (parallel)
                          ────────────────────
                          14-19 days total
```

---

## 10. Hard Rules (inherited from Pulse .ai-toolkit)

1. **No hardcoded credentials.** All from `settings.AI_PROVIDER_*`.
2. **No Pulse imports** outside `ai/providers/pulse.py`.
3. **No direct LLM calls** outside `AIProvider` implementations.
4. **Scope is mandatory.** Every `AIProvider` method takes `scope: Scope | None`. Providers MUST inject scope filters.
5. **Never raise from AI calls.** Return `status: "provider_unavailable"` + `error`.
6. **Fail-visible.** AI unavailable → "skipped" / "unavailable", never silent pass.
7. **Suggestions require confirmation.** `requires_confirmation: True` always.
8. **Audit everything.** Every AI call logged with user, task_type, latency, status.
9. **Tests before code.** Protocol tests first (Wave A), then provider tests (Wave B), then integration tests (Wave C+).

---

## 11. Coordination with Pulse

| Carbon needs from Pulse | Pulse file | Status |
|-------------------------|------------|--------|
| Scope injection in `carbon.query.nl` | `api/tasks.py:_handle_nl_query` | 🔶 Wave P |
| Scope injection in `carbon.anomaly.detect` | `api/tasks.py:_handle_anomaly_detect` | 🔶 Wave P |
| Scope injection in `carbon.report.draft` | `api/tasks.py:_handle_report_draft` | 🔶 Wave P |
| Scope injection in `carbon.schema.analyze` | `api/tasks.py:_handle_schema_analyze` | 🔶 Wave P |
| Carbon domain pack enrichment | `instances/carbon/instance.yaml` | 🔶 Wave P |
| Coworker system prompt | `llm/prompts.py` | 🔶 Wave P |
| `GET /tasks/{id}` polling | `api/tasks.py` | 🔶 Already spec'd in `PULSE_CONTRACT_SPEC.md` §1.4 |
