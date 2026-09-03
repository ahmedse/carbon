# AI Contract — Carbon AI (Strict)

**Version:** 2.0.0  (updated 2026-08-15 — ADR-0007/0008/0009 incorporated)
**Status:** Enforced
**Read by:** ALL roles — Backend Worker, Master Architect, QA Validator, DevOps Worker
**Purpose:** This is THE binding contract for every AI operation in Carbon.
            No AI call may deviate from these rules. Violation = rejected in review.

**Naming:** "AI" or "Carbon AI" = the ENTIRE `backend/ai/` system — orchestrator, guards,
memory, engine, workspace, all tiers. "AI engine" = `engine/` specifically (inference only).

---

## §0. SOVEREIGNTY

Carbon's `backend/ai/` app is **THE** canonical AI interface. It is the single
location where AI operations are defined, validated, dispatched, and audited.

| Rule | What it means |
|------|---------------|
| **0.1** | `ai/protocol.py` is the canonical contract. The AI engine implements it. |
| **0.2** | `ai/protocol.py` imports NOTHING from Django, DRF, requests, or any provider. Pure ABCs + dataclasses. |
| **0.3** | NO domain app imports from `ai/providers/` or `ai/engine/` directly. All calls go through `CarbonIntelligence`. |
| **0.4** | The AI engine (`engine/`) is co-deployed in-process. It holds NO durable state; Carbon owns all memory, knowledge, and learning. |
| **0.5** | The engine adapter (`ai/providers/pulse.py`) is the single contained seam. There is no runtime provider swapping. |
| **0.6** | `CarbonIntelligence` (`ai/intelligence.py`) is the SINGLE entry point. All Carbon code calls it, never the engine directly. |

```
  Carbon code (any app)
         │
         ▼
  ┌─────────────────────────────────────────────┐
  │  CarbonIntelligence  (ai/intelligence.py)   │  ← ONLY entry point
  │                                             │
  │  GuardChain:                                │
  │    ScopeGuard → AccessGuard →               │
  │    DataIsolationGuard → MutationGuard →     │
  │    RateLimiter                              │
  │                                             │
  │  Memory: knowledge store, feedback          │
  └──────────────────┬──────────────────────────┘
                     │  in-process call
                     ▼
  ┌──────────────────────────────────────────┐
  │  AI engine  (ai/engine/ — in-process)    │
  │  Stateless reasoning: TurnPipelineRunner │
  │  LLM router → LLM provider (via API key) │
  │  Knowledge graph, vector store           │
  └──────────────────────────────────────────┘
```

---

## §1. SCOPE — MANDATORY, NEVER OPTIONAL

Every AI call MUST carry a `Scope` object. If scope cannot be built (no user,
no org units), the call is **rejected before it reaches the provider**.

### Scope Dataclass (canonical in `ai/protocol.py`)

```python
@dataclass
class Scope:
    user_identifier: str           # WHO — for audit trail
    org_unit_ids: list[str]        # WHERE — NEVER empty in live calls
    app_identifier: str | None     # WHAT domain app (None = platform/common)
    module_ids: list[str]          # WHICH tables the user can access
    is_read_only: bool             # True → provider MUST NOT suggest mutations
    is_superuser: bool             # True → full access (audit-only)
```

### Scope Rules

| Rule | Enforcement |
|------|-------------|
| **1.1** | `org_unit_ids` MUST NOT be empty in any live (non-test) call. |
| **1.2** | `app_identifier` is `None` for platform operations (dq.validate, query.nl, schema.analyze, fix.suggest). |
| **1.3** | `app_identifier` is REQUIRED for domain operations (anomaly.detect, report.draft, etc.). |
| **1.4** | `is_read_only: True` means the provider MUST NOT suggest INSERT/UPDATE/DELETE. |
| **1.5** | Scope is built from `request.user` + RBAC. NEVER from client-supplied JSON. |
| **1.6** | `CarbonIntelligence.build_scope(user)` is the ONLY scope factory. |

---

## §2. OPERATION CATEGORIES — THREE, NOT TWO

Every AI operation fits into exactly ONE category:

### CATEGORY A: Platform Operations (available to ALL domain apps)

These work on ANY table in ANY app. They carry ZERO domain-specific logic.

| Operation | Engine task type | What it does |
|-----------|------|-------------|
| `dq.validate` | `dq.validate` | Validate rows against NL DQ rules |
| `dq.suggest` | `dq.suggest` | Propose DQ rules from table profile |
| `query.nl` | `carbon.query.nl` | NL question → SQL + data |
| `query.explain` | `carbon.query.explain` | Explain what a SQL query means |
| `schema.analyze` | `carbon.schema.analyze` | Analyze schema change impact |
| `fix.suggest` | `carbon.fix.suggest` | Suggest data fixes for issues |
| `chat` | `chat` | Free-form conversational AI (six-witness pipeline) |

**Contract:** Platform operations have `app_identifier = None` in scope. The provider
MUST NOT apply domain-specific heuristics. The provider filters results by
`scope.org_unit_ids` and `scope.module_ids`.

### CATEGORY B: Domain Operations (scoped to ONE app)

These are app-specific. They carry `app_identifier` in scope. Each domain app
defines its own operations as a `DomainAIOperations` ABC in `ai/domain/{app_name}.py`.

| App | Operation | Type | Defined in |
|-----|-----------|------|------------|
| `emissions` | `anomaly.detect` | Domain | `ai/domain/emissions.py` |
| `emissions` | `anomaly.explain` | Domain | `ai/domain/emissions.py` |
| `emissions` | `report.draft` | Domain | `ai/domain/emissions.py` |
| (future) | (future) | Domain | `ai/domain/{app}.py` |

**Contract:** Domain operations MUST carry `app_identifier` matching the ABC's `app_identifier`.
The provider MUST isolate domain data — no cross-app training, caching, or context sharing.

### CATEGORY C: Provider Meta-Operations (infrastructure)

| Operation | Type | What it does |
|-----------|------|-------------|
| `health_check` | Meta | Returns `ProviderStatus` |
| `get_modules` | Meta | Returns available task types |

---

## §3. DATA ISOLATION — NON-NEGOTIABLE

**The AI heart MUST prevent data leakage between domain apps and between org units.**

### Isolation Rules

| Rule | What it means | Enforcement point |
|------|---------------|-------------------|
| **3.1** | Provider MUST NOT use data from App A when processing requests for App B. | Provider (Pulse) |
| **3.2** | Provider MUST NOT cache embeddings/knowledge graphs across apps unless explicitly partitioned by `app_identifier`. | Provider (Pulse) |
| **3.3** | Provider MUST filter ALL SQL queries by `scope.org_unit_ids` before execution. | Provider (Pulse) |
| **3.4** | Provider MUST NOT return data rows belonging to org units outside `scope.org_unit_ids`. | Provider (Pulse) |
| **3.5** | Carbon's `DataIsolationGuard` sanitizes provider responses before returning to caller — strips any `app_identifier` mismatch. | `ai/guards.py` |
| **3.6** | Carbon's `CarbonIntelligence` caches results keyed by `(operation, app_identifier, org_unit_ids_hash)` — no cross-app cache hits. | `ai/intelligence.py` |

### What Data Isolation Prevents

| Threat | How it's blocked |
|--------|-----------------|
| Emissions data appearing in supply-chain NL query | `DataIsolationGuard` strips cross-app rows |
| User in org-A seeing org-B's anomaly results | `Scope.org_unit_ids` filters at the provider |
| Pulse caching emissions embeddings for supply-chain use | Partitioned by `app_identifier` |
| AI suggesting tables the user can't access | `Scope.module_ids` restricts visibility |

---

## §4. NO AUTO-MUTATION

**AI suggests. Carbon executes. Never the reverse.**

| Rule | What it means |
|------|---------------|
| **4.1** | Provider MUST NOT execute INSERT/UPDATE/DELETE/DROP. |
| **4.2** | Provider MAY suggest SQL (in `query.nl`) but Carbon executes it with its own permissions. |
| **4.3** | Fix suggestions have `requires_confirmation: True` ALWAYS. Carbon's UI prompts before applying. |
| **4.4** | Report drafts are DRAFTS. Carbon publishes them. Pulse never writes to Carbon's database. |
| **4.5** | `MutationGuard` in `ai/guards.py` validates that provider responses contain no mutation instructions unless explicitly expected by the operation type. |

---

## §5. ENGINE ADAPTER SEAM

**The engine adapter is the single contained swap point. There is no runtime provider swapping.**

| Rule | What it means |
|------|---------------|
| **5.1** | `ai/providers/pulse.py` is the ONLY file that knows engine internals (task names, call signatures). |
| **5.2** | `AIProvider` ABC (`ai/protocol.py`) is the ONLY interface Carbon code depends on. |
| **5.3** | If the underlying LLM or engine is replaced, only `ai/providers/pulse.py` and `ai/engine/` change. Zero changes elsewhere. |
| **5.4** | LLM provider is configured via `LLM_API_KEY` + `LLM_BASE_URL` + `LLM_MODEL` in settings. The engine is LLM-agnostic. |
| **5.5** | To extend the engine with a new operation: add task handler in `engine_runtime.py` → add method to `AIProvider` ABC → implement in `CarbonIntelligence`. |

---

## §6. GRACEFUL DEGRADATION

**If the AI provider is unreachable, Carbon MUST continue functioning.**

| Rule | What it means |
|------|---------------|
| **6.1** | ALL provider calls return `provider_unavailable` status on timeout/error — never crash, never 500. |
| **6.2** | DQ Level 1 (deterministic: unique, threshold, reference_integrity) runs locally regardless of AI availability. |
| **6.3** | DQ Level 2 (`nl_check`) returns `skipped_unavailable` when AI is down — doesn't block the DQ job. |
| **6.4** | `PULSE_UNAVAILABLE_LIMIT = 20` in `dq/jobs.py` — after 20 consecutive failures, job is marked failed. |
| **6.5** | AI-powered UI features show "AI unavailable" state, not a loading spinner forever. |
| **6.6** | Provider timeout: 10s for sync operations, 60s for async, 120s for report.draft. |

---

## §7. AUDIT TRAIL

**Every AI call is logged. No exceptions.**

| Rule | What's logged |
|------|---------------|
| **7.1** | `timestamp` — when the call was made |
| **7.2** | `user_identifier` — from `Scope` |
| **7.3** | `app_identifier` — from `Scope` (None for platform ops) |
| **7.4** | `operation_type` — e.g., `dq.validate`, `anomaly.detect` |
| **7.5** | `scope_snapshot` — serialized `Scope` at time of call |
| **7.6** | `latency_ms` — how long the provider took |
| **7.7** | `status` — `completed`, `failed`, `provider_unavailable`, `denied` |
| **7.8** | `error` — sanitized error (no stack traces, no internal paths) |

Pulse stores this in `TaskExecution`. Carbon stores this in `AICallLog` (or a
lightweight log table). The two are correlated by `task_id`.

---

## §8. DOMAIN APP REGISTRATION — HOW TO ADD A NEW APP'S AI

When a new domain app (e.g., `water`) needs AI operations:

### Step 1: Define the domain ABC

```python
# ai/domain/water.py
from ai.domain_protocol import DomainAIOperations

class WaterAIOperations(DomainAIOperations):
    app_identifier = "water"
    
    def usage_forecast(self, request: UsageForecastRequest) -> UsageForecastResponse:
        ...
    def quality_predict(self, request: QualityPredictRequest) -> QualityPredictResponse:
        ...
```

### Step 2: Implement in the provider

```python
# ai/providers/pulse.py (or a new provider)
class PulseProvider(AIProvider, EmissionsAIOperations, WaterAIOperations):
    def usage_forecast(self, request): ...
    def quality_predict(self, request): ...
```

### Step 3: Register in Pulse

Add handlers in Pulse's `TASK_HANDLERS`:
```python
"water.usage.forecast": _handle_water_usage_forecast,
"water.quality.predict": _handle_water_quality_predict,
```

### Step 4: Expose through CarbonIntelligence

```python
# ai/intelligence.py
def submit_water_usage_forecast(self, *, user, **params) -> UsageForecastResponse:
    scope = build_scope(user, app_identifier="water")
    ScopeGuard.validate(scope)
    return self.provider.usage_forecast(UsageForecastRequest(scope=scope, ...))
```

### What the domain developer NEVER does:
- ❌ Never touches `ai/protocol.py` (the common ABC)
- ❌ Never touches `ai/guards.py` (security is automatic)
- ❌ Never calls `PulseProvider` directly (always through `CarbonIntelligence`)
- ❌ Never handles scope manually (`build_scope()` does it automatically)
- ❌ Never imports from another domain's AI module

---

## §9. CONTRACT ENFORCEMENT — VIOLATIONS

| Violation | Severity | Action |
|-----------|----------|--------|
| AI call without scope | **BLOCKER** | Rejected in `ScopeGuard`. Never reaches provider. |
| Cross-app data in response | **BLOCKER** | Stripped by `DataIsolationGuard`. Alert logged. |
| User without app access calling domain AI | **BLOCKER** | `AccessGuard` returns 403 before provider call. |
| Provider suggests mutation when `is_read_only: True` | **BLOCKER** | `MutationGuard` strips mutation SQL. Alert logged. |
| Direct `PulseProvider` import outside `ai/` | **REJECTED** | Caught in review. Violates §0.3. |
| Hardcoded Pulse URL in domain code | **REJECTED** | Caught in review. Violates §5.3. |
| AI call not logged | **REJECTED** | Caught in review. Violates §7. |
| Provider returns 500 on unavailable | **REJECTED** | Violates §6.1. Must return `provider_unavailable`. |

---

## §10. RELATIONSHIP TO OTHER CONTRACTS

| Contract | Relationship |
|----------|-------------|
| `shared/security.md` | AI-specific security rules extend §3 (Data Isolation). Scope is a security boundary. |
| `shared/api-contract.md` | AI task envelope follows the same error shape (`{error: {code, message}}`). |
| `shared/design-patterns.md` | AI uses: Adapter (providers/pulse.py maps ABC→engine), Mediator (CarbonIntelligence), Proxy (guards), Singleton (CarbonIntelligence instance), Chain of Responsibility (GuardChain). |
| `shared/config.md` | `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL` — all from env, never hardcoded. |
| `project.config.md` | ARCH_AI_* keys — architecture summary for this project. |
| `decisions/0007-*` | ADR-0007: Carbon as system of intelligence; engine is stateless, in-hand. |
| `decisions/0008-*` | ADR-0008: One Django app (`ai/`), no app explosion. |
| `decisions/0009-*` | ADR-0009: Full engine vendored; persistence seam swapped to DjangoStore. |

---

## §11. WORKSPACE CONTEXT — WHAT THE USER SEES (SPEC — NOT YET IMPLEMENTED)

**AI does NOT see the browser window or screenshots. The frontend actively serializes
what the user is doing into a structured `WorkspaceContext` and sends it when opening
the AI tab. This is deterministic, scoped, auditable, and fast.**

### WorkspaceContext shape (canonical — add to `ai/protocol.py`)

```python
@dataclass
class WorkspaceContext:
    """Structured description of what the user is currently doing.

    Sent by the frontend when opening the AI workspace tab.
    Never inferred — always explicitly serialized by the source workspace.
    """
    workspace: str                      # "dq" | "catalog" | "emissions" | "dataschema" | ...
    current_view: str                   # page or tab name, e.g. "rule_list", "table_detail"
    entity_type: str | None = None      # "table" | "rule" | "calculation" | "asset" | ...
    entity_id: str | None = None        # PK or slug of the focused entity
    entity_name: str | None = None      # human-readable name
    form_state: dict | None = None      # partial form data if user was filling a form
    recent_actions: list[str] = field(default_factory=list)  # last 3-5 user actions
    intent_signal: str | None = None    # "create" | "edit" | "debug" | "explore" | None
    app_identifier: str | None = None   # domain app scope (mirrors Scope.app_identifier)
```

### Per-workspace serialization contracts

| Workspace | `workspace` | `entity_type` examples | `intent_signal` logic |
|---|---|---|---|
| DQ Workspace | `"dq"` | `"rule"`, `"table"`, `"job"` | `"create"` if new-rule form open, `"debug"` if viewing failures |
| Catalog | `"catalog"` | `"asset"`, `"domain"`, `"glossary_term"` | `"explore"` by default |
| DataSchema | `"dataschema"` | `"table"`, `"field"` | `"create"` if field form open |
| Emissions dashboard | `"emissions"` | `"calculation"`, `"period"` | `"explore"` by default |
| Carbon console | `"carbon"` | `"calculation"` | `"debug"` if viewing errors |

### Rules

| Rule | What it means |
|------|---------------|
| **11.1** | Every `POST /ai/workspace/conversations/` that originates from a workspace button MUST include `workspace_context` in the request body. |
| **11.2** | `CarbonIntelligence.create_conversation()` stores `workspace_context` in `task_payload_json`. |
| **11.3** | The AI engine receives WorkspaceContext as part of the system prompt (injected by `CarbonIntelligence`, NOT by the frontend). |
| **11.4** | WorkspaceContext is NEVER used for security decisions — that is Scope's job. |
| **11.5** | `form_state` MUST be sanitized (no passwords, no secrets) before sending. |

### Why NOT screenshots / Computer Use

| Approach | Problem |
|---|---|
| Browser screenshot | Multimodal inference cost per action; unreliable on dynamic React; security risk on multi-tenant data |
| DOM scraping | Fragile to UI changes; not structured |
| WorkspaceContext (chosen) | Deterministic, cheap, structured, auditable, scoped to what Carbon already knows |
