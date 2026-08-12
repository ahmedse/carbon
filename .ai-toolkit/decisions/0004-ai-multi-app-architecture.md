# ADR-0004: Multi-App AI Heart Architecture

## Status
Accepted (2026-08-12)

## Context

Carbon is a **platform**, not a single-domain application. It currently hosts
one domain app (`emissions` — carbon footprint accounting per GHG Protocol).
More domain apps will follow (supply chain, water usage, waste management, etc.).

The AI heart (`backend/ai/`) currently has a flat `AIProvider` ABC with 9 methods
covering both platform-level operations (DQ, NL query, schema analysis) and
emissions-specific operations (anomaly detection, report drafting).

Without architectural intervention, each new domain app will add 3-5 methods to
this ABC. By 5 apps, the `AIProvider` ABC would grow to ~30 methods, creating:

1. **God interface** — a single ABC implementing every AI operation for every app
2. **Cross-app data leakage risk** — no structural boundary between emissions AI
   context and supply-chain AI context at the provider level
3. **Provider coupling** — Pulse (or any provider) must understand domain-specific
   semantics for every app, defeating the swappable-provider Strategy pattern
4. **Domain developer confusion** — which methods are "platform" (use anywhere)
   vs "domain" (specific to one app)?

## Decision

We adopt a **three-layer AI architecture** with strict structural separation:

### Layer 1: Platform AI (`ai/protocol.py`)

Common operations that work on ANY table in ANY domain app. These carry ZERO
domain-specific logic. The existing `AIProvider` ABC retains only these 6 methods:

- `validate_dq` — NL DQ rule validation
- `suggest_dq` — DQ rule suggestion from table profiles
- `query_nl` — Natural language → SQL + data
- `explain_query` — Explain SQL query results
- `analyze_schema` — Schema change impact analysis
- `suggest_fix` — Data fix suggestions

### Layer 2: Domain AI (`ai/domain/{app_name}.py`)

Domain-specific operations. Each domain app defines its own `DomainAIOperations`
ABC in `ai/domain/{app_name}.py`. These are structurally independent — no domain
ABC imports from another domain's types.

- `ai/domain/emissions.py` — `EmissionsAIOperations` (anomaly.detect, anomaly.explain, report.draft)
- `ai/domain/supply_chain.py` — `SupplyChainAIOperations` (future)
- `ai/domain/water.py` — `WaterAIOperations` (future)

### Layer 3: Security Guards (`ai/guards.py`)

Runtime enforcement that runs BEFORE any AI call reaches the provider:

- **`ScopeGuard`** — Validates scope is non-empty, app_identifier matches operation
- **`AccessGuard`** — User must have RBAC access to the target app
- **`DataIsolationGuard`** — Sanitizes provider responses; strips cross-app data
- **`MutationGuard`** — Blocks any mutation when `is_read_only: True`
- **`AuditTrail`** — Logs every AI call with scope snapshot

### Provider Model

`PulseProvider` implements both `AIProvider` (platform ABC) and all registered
`DomainAIOperations` ABCs. It remains a single class to avoid HTTP connection
duplication, but its methods are organized by layer.

`CarbonIntelligence` remains the SINGLE entry point — no domain code calls
`PulseProvider` directly. It builds scope, runs guards, dispatches to the
provider, sanitizes the response, and logs the audit trail.

### Updated Scope Dataclass

`app_identifier` is added to distinguish platform operations from domain operations:

```python
@dataclass
class Scope:
    user_identifier: str           # WHO
    org_unit_ids: list[str]        # WHERE (NEVER empty)
    app_identifier: str | None     # WHAT domain app (None = platform)
    module_ids: list[str]          # WHICH tables
    is_read_only: bool             # HOW
    is_superuser: bool             # HOW
```

## Consequences

### Positive
- **Anti-spaghetti**: Domain AI operations are structurally in their own files.
  Adding a new app never touches `protocol.py` or existing domain files.
- **Data isolation by construction**: Guards run on every call. Cross-app leakage
  is a code defect, not a configuration oversight.
- **Provider swappability preserved**: A new provider implements the same ABCs.
  Domain semantics are in the ABC, not the provider.
- **Clear developer contract**: See `shared/ai-contract.md` — every rule is
  numbered and enforceable.
- **Audit trail mandatory**: Every call logged with scope. Compliance-ready.

### Negative
- **More files**: `ai/domain/{app}.py` per app + `ai/guards.py`. Currently ~3 new
  files, growing linearly with apps.
- **Multiple inheritance for provider**: `PulseProvider(AIProvider, EmissionsAIOperations,
  WaterAIOperations, ...)` — grows with apps. Mitigated by the fact that this
  is ONE class in ONE file (`providers/pulse.py`), and only changes when apps
  are added (rare).
- **Learning curve**: New domain developers must understand `DomainAIOperations`
  ABC pattern. Mitigated by the template in `ai/domain/__init__.py` docstring.

### Risks
- **Guard performance**: Running 3-4 guards per AI call adds overhead. Each
  guard is <1ms (in-memory validation, no DB queries for ScopeGuard/AccessGuard).
  DataIsolationGuard scans response rows — O(n) in response size. Acceptable for
  typical response sizes (<1000 rows).
- **ABC proliferation**: If a future app needs only 1 AI operation, does it
  deserve its own ABC? Yes — the isolation benefit outweighs the file count.
  One method in its own file is fine.

## References
- `.ai-toolkit/shared/ai-contract.md` — THE binding contract
- `.ai-toolkit/shared/security.md` — AI-specific security rules (§10)
- `.ai-toolkit/shared/design-patterns.md` — Strategy, Adapter, Mediator, Facade, Proxy
- `backend/ai/protocol.py` — Current AIProvider ABC (to be reorganized per this ADR)
- `docs/PULSE_CONTRACT_SPEC.md` — Wire-level contract for Pulse provider
