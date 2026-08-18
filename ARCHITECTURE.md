# Carbon Data Trust Platform — Architecture
# Single source of truth. Replaces all plans/*ARCHITECTURE*.md.
# Updated: 2026-08-17 | Owner: Master Architect

---

## What Carbon Is

Carbon is a **Data Trust Platform** — infrastructure for trusted, governed data —
that hosts domain applications on top. The first domain app is **Carbon Footprint**
(GHG Protocol emissions accounting). More follow (water, waste, supply chain).

The philosophy: data products earn trust through governance (catalog, DQ, MDM, lineage).
AI is the platform's living intelligence — it knows the data, the rules, and the users,
and it grows smarter with every interaction.

Carbon is now an **AI-Driven Data Platform**. Beyond emissions accounting, the platform
adds a **Data Trust Core** (Dataset Hub, data contracts, health scoring), a **TurnKey
Bridge** (bidirectional ML-serving link), an **App Registry** (domain-app manifests and
activation), and a growing set of **Domain Apps** (emissions, healthy, and future apps).
The full specification is `docs/DESIGN-PLATFORM.md`.

---

## System Map

```
┌────────────────────────────────────────────────────────────────────────────────┐
│  Carbon (this repo) — Data Trust Core + AI + Domain Apps                      │
│                                                                                │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  Domain Apps  (may use core; core NEVER imports domain)                 │  │
│  │  emissions/   healthy/   (future: energy_forecast/, supply_chain/, …)   │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                                                                │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  New Platform Layers (this spec)                                        │  │
│  │  datahub/              integrations/turnkey/    appregistry/            │  │
│  │  Dataset versioning    Push artifacts           App manifests            │  │
│  │  Health scoring        Receive predictions      Activation + CBAC        │  │
│  │  Data contracts        Drift ↔ DQ link          Capability extension     │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                                                                │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  Existing Platform Core (do not modify except where this doc says to)   │  │
│  │  accounts  catalog   mdm    dq    dataschema  connections                │  │
│  │  evidence  importexport  ai/  emissions  core                           │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────────┘
                              │ HTTP (async client)
                              ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│  TurnKey (separate repo/service) — ML Serving Tier                            │
│  registry/  inference/  monitoring/  A-B testing  drift alerts  projects       │
│  API keys   model versions   predictions   SHAP   accuracy snapshots           │
└────────────────────────────────────────────────────────────────────────────────┘
                              │ Azure PostgreSQL (read-only connection via DataSource)
                              ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│  Healthy ERP  (external, read-only)                                           │
│  healthy_legacy_2026 on Azure PostgreSQL                                       │
│  readable.* views — 1,047 decoded views over the legacy Arabic ERP            │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

## Stack

| Layer | Technology |
|---|---|
| Backend | Django 5.2 + DRF, Python 3.12, PostgreSQL 16, Redis |
| Frontend | React 19.1 + Vite 6, MUI v7.1 (zinc/blue, compact density) |
| AI engine | Vendored in-process (`backend/ai/engine/`), LLM via API key |
| Auth | JWT (SimpleJWT) + RBAC via ScopedRole (org-unit-scoped) |
| Dev ops | `./manage.sh` for all ops; Docker for prod; `.venv` at repo root |
| Ports | Backend :8009, Frontend :5179 |

---

## New Platform Layers (Phase 1–4)

Specified in `docs/DESIGN-PLATFORM.md` (§2, §4–§9, §13–§14). Four additions turn Carbon
from an emissions-accounting platform into a general AI-Driven Data Platform.

| Layer | Django app | Purpose | Depends on | Spec |
|---|---|---|---|---|
| Dataset Hub | `datahub/` | Versioned, governed, contracted datasets — the trust anchor for all AI. | dataschema, catalog, dq, connections, mdm, core, accounts | §5 |
| TurnKey Bridge | `integrations/turnkey/` | Bidirectional link to the TurnKey ML serving tier (push artifacts; receive predictions + drift). | datahub | §6 |
| App Registry | `appregistry/` | Domain-app manifest, activation, and CBAC scoping. | catalog, accounts (parallel with Phase 2) | §7 |
| First domain app | `healthy/` | Healthy Foods Factory — 5 AI pipelines on ERP data. | datahub, integrations, appregistry | §8 |

**Dependency graph rule** (§13): build order is Phase 1 → Phase 2 → Phase 4, with
Phase 3 runnable in parallel with Phase 2. Each layer imports only downward:
`datahub/` imports core/dataschema/catalog/dq/connections/mdm/accounts and is imported
by `integrations/turnkey/`, `appregistry/`, and `healthy/`. No new layer imports a
domain app (`emissions/` or `healthy/`).

**CBAC extension contract** (§4):
- `Dataset.module` (FK → `core.Module`) is the scope anchor — the existing
  `ScopedRole(module=…)` already applies; no new ScopedRole FK is needed.
- New capabilities (datahub:view/ingest/approve/manage, turnkey:view/manage,
  appregistry:view/manage, healthy:view/manage) live ONLY in
  `backend/accounts/capabilities.py` plus `GROUP_CAPABILITIES`.
- `DatasetAccessPolicy` (per-dataset override) takes precedence over module-level
  ScopedRole: explicit policy > ScopedRole module-level > deny.

**Closed loop** (§9) — the platform's core value, an 8-step cycle:
Ingest → Govern → Approve → Model Link → Serve → Feedback → Actuals → Drift Response.

---

## AI Architecture

### Naming
- **"AI"** or **"Carbon AI"** = the entire `backend/ai/` system
- **"AI engine"** = `backend/ai/engine/` — the stateless inference core
- Never: "Pulse", "AI Heart" (retired terms)

### Principle
> **Carbon is the system of intelligence. The LLM is just the voice.**
>
> All durable AI state — memory, knowledge graph, feedback, learning — is Carbon-owned,
> CBAC-partitioned, and auditable. The LLM (whatever sits behind `LLM_API_KEY`) is
> stateless and swappable. Swapping the LLM changes nothing in Carbon.

### Layers

```
Layer 1: CarbonIntelligence  (ai/intelligence.py)
         ↳ single entry point; builds Scope from RBAC; runs GuardChain; owns memory

Layer 2: GuardChain  (ai/guards.py)
         ↳ ScopeGuard → AccessGuard → DataIsolationGuard → MutationGuard → RateLimiter
         ↳ runs BEFORE every AI call, ALWAYS, no exceptions

Layer 3: AI engine  (ai/engine/ — in-process)
         ↳ TurnPipelineRunner: S1 Salience → S2 Retrieval → S3 Draft → S4 Critic
                               → S5 Execute → S6 Ledger
         ↳ LLM router → LLM provider (Claude / GPT-4o / local via API key)
         ↳ KnowledgeGraphStore, vector store (pgvector), short/long/episodic memory

Layer 4: Domain AI  (ai/domain/{app}.py)  ← PARTLY MISSING, see Gaps
         ↳ EmissionsDomainAI: GHG Protocol vocabulary, scope 1/2/3 context
         ↳ (future) WaterDomainAI, WasteDomainAI
```

### AI Operations (10 task types, all wired)

| Operation | Category | Engine task |
|---|---|---|
| `chat` | Platform | `chat` → TurnPipelineRunner (six-witness) |
| `dq.validate` | Platform | `dq.validate` → LLM |
| `dq.suggest` | Platform | `dq.suggest` → LLM |
| `query.nl` | Platform | `carbon.query.nl` → KG + LLM |
| `query.explain` | Platform | `carbon.query.explain` → LLM |
| `schema.analyze` | Platform | `carbon.schema.analyze` → KG + LLM |
| `fix.suggest` | Platform | `carbon.fix.suggest` → LLM |
| `anomaly.detect` | Domain/emissions | `carbon.anomaly.detect` → KG heuristics + LLM |
| `anomaly.explain` | Domain/emissions | `carbon.anomaly.explain` → LLM |
| `report.draft` | Domain/emissions | `carbon.report.draft` → LLM |

### Fail-visible contract
Every AI operation degrades gracefully. LLM unavailable → deterministic fallback.
Never a fake answer. Never a hanging spinner. Status: `pulse_unavailable` not 500.

### The DQ + AI scenario (target UX — in progress)
```
User opens DQ workspace
 └─ clicks [AI]
     └─ frontend serializes WorkspaceContext {workspace:"dq", entity_type:"rule", intent_signal:"create"}
         └─ POST /ai/workspace/conversations/ with workspace_context
             └─ CarbonIntelligence injects context into system prompt
                 └─ AI: "I see you're in DQ. Want to create a new rule?
                         Based on this table's profile, I'd suggest an email
                         format check. Want me to fill in the definition?"
                     └─ User: "yes, validate email, here are examples"
                         └─ AI fills RuleJsonEditor live (streaming SSE → typing animation)
                             └─ User reviews, approves
                                 └─ AI calls POST /dq/rules/ (with user approval)
                                     └─ AI: "Rule created. Running validation now... ✓ 3 rows failed"
```
**Status:** Steps 1–3 done. Steps 4–8 are Sprints 3–8 in ROADMAP.md.

---

## Data Quality System

```
DQ Rule (standalone policy — not bound to a table at creation)
    ↓ bound via RuleFieldAssignment (at data product level)
    ↓
DQ Engine (dq/engine.py — pure, no DB)
    ├─ Level 1: deterministic (not_null, unique, range, regex, referential)
    └─ Level 2: AI-powered (nl_check → AI engine → fail-visible)
    ↓
DQ Gate (dq/gate.py — stateless write-time enforcement)
    ↓
DQ Job (dq/jobs.py — rule_run, profile, freshness, schema [inline]; nl_check, suggest, anomaly [AI])
    ↓
DQ Result → DQResult model → DQ Workspace frontend
```

**Key rule:** DQ rules are standalone policies. Bindings are separate (ADR-0006).

---

## RBAC Model

```
User
 └─ ScopedRole (org_unit, module, role_type, is_read_only)
     └─ OrgUnit  ← the data boundary (org unit = visibility scope)
     └─ Module   ← which Carbon module this role grants access to
```

- `is_superuser` → all access, all org units
- `is_staff` → global admin (all org units in their module)
- Regular user → scoped to their org_unit_ids + module_ids

AI Scope is derived from RBAC. No separate AI permissions.

---

## Key Architecture Rules (non-negotiable)

1. **Core never imports domain.** `emissions` may import `catalog`/`mdm`/`dq`. Never the reverse.
2. **All AI calls go through `CarbonIntelligence`.** No direct engine calls from domain code.
3. **GuardChain runs on every AI call.** No exceptions. No bypasses.
4. **AI engine holds no durable state.** Carbon owns everything. Engine is stateless per-call.
5. **Fail-visible, never silent.** AI unavailable = honest status, not fabricated answer.
6. **No raw `datetime.now()`.** Always `django.utils.timezone.now()`.
7. **No `tail -f`, no raw `runserver`.** Always `./manage.sh`.
8. **Delete = soft-delete + audit event.** Never silent hard-delete on data entities.
9. **One Django app for AI.** `backend/ai/` only. No new AI Django apps (ADR-0008).
10. **WorkspaceContext, not screenshots.** AI sees structured context, not the browser.

---

## Known Gaps (open work — see ROADMAP.md)

| Gap | Impact | Sprint |
|---|---|---|
| `ai/domain/emissions.py` missing | GHG vocabulary not injected into AI context | 7 |
| WorkspaceContext not implemented | AI doesn't know what user is doing | 6 |
| Streaming SSE not implemented | AI responses arrive as one blob, not "human speed" | 8 |
| Feedback persistence missing | Learning flywheel not turning | 9 |
| 17 unprotected delete endpoints | Data integrity risk | 2 |
| DQ Hub fragmented (6 surfaces) | UX confusion | 5 |

---

## Directory Structure

```
backend/
  ai/           ← entire AI system
    engine/     ← in-process inference engine (vendored)
    domain/     ← per-domain AI (⚠️ emissions.py missing)
    models/     ← Django models for AI state (conversations, KG, memory)
    guards.py   ← GuardChain
    intelligence.py  ← CarbonIntelligence (ONLY entry point)
    protocol.py      ← AIProvider ABC + typed dataclasses
    engine_runtime.py ← dispatch_task (all 10 types wired)
    store.py    ← DjangoStore (CBAC-partitioned)
  accounts/     ← users, RBAC, org units, config
  catalog/      ← metadata, glossary, assets, governance
  mdm/          ← reference sets, reference values, org units
  dq/           ← data quality rules, engine, gate, jobs, results
  dataschema/   ← schema engine (tables, fields, rows)
  connections/  ← data sources
  evidence/     ← evidence upload
  importexport/ ← bulk import/export
  core/         ← modules, feedback, notifications
  emissions/    ← GHG Protocol domain app

carbon-frontend/src/
  apps/carbon/    ← domain app manifests
  pages/          ← all page components
  pages/admin/ai/ ← AI admin console (19 panels)
  api/            ← API wrappers (apiFetch-based)
  shell/          ← app shell (sidebar, breadcrumbs, auth)
  components/     ← shared components
  theme/          ← carbonTheme.js (MUI v7)

tasks/            ← active sprint specs
archive/          ← completed work (do not read)
.ai-toolkit/      ← dev system (roles, contracts, decisions)
```

---

## Contracts (binding for all workers)

| Contract | What it governs |
|---|---|
| `.ai-toolkit/shared/ai-contract.md` | All AI operations, guards, WorkspaceContext spec |
| `.ai-toolkit/shared/api-contract.md` | REST API shape, error format, versioning |
| `.ai-toolkit/shared/security.md` | OWASP compliance, RBAC enforcement |
| `.ai-toolkit/shared/design-system.md` | MUI usage, theme tokens, compact density |
| `.ai-toolkit/shared/testing.md` | Test structure, coverage requirements |
| `.ai-toolkit/decisions/` | ADRs — settled architectural decisions |
