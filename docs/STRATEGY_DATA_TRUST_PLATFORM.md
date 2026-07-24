# Strategy — Carbon → AI-Era Data Trust Platform

> **Status:** Living document. North star for architecture and roadmap decisions.
> **Version:** 1.1 — 2026-07-23 (Platform App Model formalised)
> **Naming:** The product keeps the **"Carbon"** name for now. The *architecture* underneath evolves into a general-purpose **Data Trust Platform** on which domain apps (Carbon being the first) are hosted.
> **New in v1.1:** Platform-as-OS / apps-as-plugins model formalised. See [`docs/PLATFORM_APP_MODEL.md`](PLATFORM_APP_MODEL.md) for the full specification.

---

## 1. Vision

Build an **Ataccama-inspired, next-generation, AI-era Data Trust Platform** — but **lighter in weight** — that:

1. Treats **data as a first-class, governed, trustworthy asset** (not rows in random tables).
2. **Hosts apps on top of that trusted data.** Carbon/Sustainability is the first hosted app; more follow (e.g. ESG, energy, water, transport, compliance).
3. Is **AI-native**: quality, cataloging, search, and insight are driven by embeddings, LLMs, and agents — not manual rule-writing alone.

One sentence: **a trusted, metadata-driven data layer + an AI brain, with pluggable domain apps sitting on top.**

---

## 2. What "Data Trust" means (the Ataccama principles, adapted & lighter)

Ataccama ONE unifies data quality, governance, catalog, MDM/RDM, and observability. We adopt the *principles*, not the heavyweight platform:

| Ataccama principle | Our lighter-weight adaptation |
|---|---|
| **Unified platform** — one place for all data management | One Django + Postgres core; apps plug in, no sprawl of services. |
| **Metadata-driven** — schema/rules described as metadata, not hard-coded | Already have it: `dataschema` engine (`DataTable`/`DataField`/`DataRow` = schema stored *as data*). This is our biggest asset — invest here. |
| **Data catalog** — describe, tag, own, find data | Add a catalog layer over `DataField`/`DataTable`: descriptions, owners, semantic tags, quality status, lineage. |
| **AI-powered / self-driving data quality** | LLM-assisted profiling, anomaly detection, and rule *suggestion* over data rows. |
| **Data governance & RBAC** | Already have contextual `ScopedRole` (project/module). Extend with catalog-level governance. |
| **Reference/Master data** | Lightweight reference tables via existing `reference` field type + `reference_table` FK. |
| **Data observability** | Track freshness, completeness, and DQ trends per table over time. |
| **Semantic layer** | Embeddings over metadata + data → semantic search and natural-language querying. |

**Trust = Governed (who) + Quality (how good) + Cataloged (what/where) + Observable (is it still good) + Explainable (why).**

---

## 3. Architecture decisions (locked)

### 3.1 Keep the core — do NOT migrate to Supabase now
- Core stays **Django + DRF + PostgreSQL + Redis**.
- Rationale: our differentiators — the **metadata-driven schema engine**, **contextual RBAC**, and **calculation engine** — are exactly what Supabase's auto-API (PostgREST) and RLS fight against. Migrating now = rewriting our moat for infra convenience we don't need.
- Supabase revisited **only later**, and if so, **as managed Postgres + Storage** with Django still in front — never a full PostgREST/RLS/Edge-Functions rewrite at this stage.

### 3.2 AI / semantic / agentic — owned by **Pulse** (external), not built in-repo
- **Pulse** is a separate semantic + agentic system that **integrates with Carbon** (like other hosted systems). It owns embeddings, RAG, LLM orchestration, and agents.
- Therefore, **in this repo we do NOT build**: pgvector RAG, an LLM gateway, or a homegrown AI copilot. The existing `ai_copilot` app is **superseded by Pulse** and is out of active scope (to be integrated/replaced, not extended).
- The platform's job is to expose **clean, governed, well-cataloged data + metadata** that Pulse (and other apps) consume.

### 3.3 Platform scope now — the Data Trust core
What we build here, inside Django + Postgres:
1. **Metadata / Catalog layer** — the Ataccama seed. A catalog over the existing schema engine (`DataTable`/`DataField`): descriptions, business glossary terms, owners/stewards, semantic tags, classification, and quality status.
2. **MDM (Master Data Management), lightweight** — reference/master data, golden records, entity matching/merge, survivorship, stewardship — starting from the existing `reference` field type + `reference_table` FK.
3. **Data Quality & profiling** — per-table/field profiling (completeness, uniqueness, patterns), DQ rules, scoring, and status surfaced in the catalog.
4. **Governance & lineage** — ownership, policies, and table/field lineage to make data explainable and trustworthy.

### 3.4 Naming / domain separation
- Keep user-facing **"Carbon"** branding.
- Internally, structure the code so **platform** (data trust core) and **app** (Carbon domain logic) are separable. Carbon becomes *the first app hosted on the platform*, not the platform itself. **Pulse** is a peer system that plugs in for AI/semantic/agentic capability.
- Every domain app (Carbon, and future apps such as Academic Portfolio, Research Projects, Facilities Mgmt, Sustainability Goals) follows the **App Contract**: a `manifest.js` file that declares the app's route namespace, API namespace, ontology extensions, RBAC roles, navigation items, platform dependencies, and AI skills. The platform shell reads manifests and configures everything automatically — routes, nav, roles. No core changes needed to add a new app.
- The Catalog, MDM, and DQ layers are **platform services** — never part of any app. Apps consume them via stable internal APIs.
- See **[`docs/PLATFORM_APP_MODEL.md`](PLATFORM_APP_MODEL.md)** for the full platform-app architecture, manifest contract, ontology model, and migration path.

---

## 4. Target shape: four-layer platform

```
┌───────────────────────────────────────────────────────────────────────┐
│  L4 — AI / EXPERIENCE FABRIC                                           │
│  Pulse copilot · Agentic workflows · Unified search · Notifications    │
│  ONE AI reasons across ALL apps via the shared Ontology (L1)           │
├───────────────────────────────────────────────────────────────────────┤
│  L3 — DOMAIN APPS (pluggable, isolated, each ships a manifest)         │
│                                                                         │
│  Carbon  │  Academic Portfolio  │  Research Projects                   │
│  Sustainability Goals  │  Facilities Mgmt  │  Procurement  │  ...       │
│                                                                         │
│  Each app: manifest + own models + own /app-id/* routes + own roles    │
├───────────────────────────────────────────────────────────────────────┤
│  L2 — PLATFORM SERVICES (Data Trust Core — domain-agnostic)            │
│  catalog · mdm · dq · governance · audit · dataschema engine           │
│  auth + ScopedRole RBAC · workflow · event bus · lineage               │
├───────────────────────────────────────────────────────────────────────┤
│  L1 — SEMANTIC CORE / ONTOLOGY                                         │
│  Entity registry · Relationship graph · OrgUnit hierarchy              │
│  Shared metric definitions · Policy bindings · Lifecycle states        │
│  ← The language every app and every AI agent speaks →                  │
└───────────────────────────────────────────────────────────────────────┘
         ↑ built on
┌───────────────────────────────────────────────────────────────────────┐
│  INFRASTRUCTURE: Django + DRF · PostgreSQL + pgvector · Redis          │
└───────────────────────────────────────────────────────────────────────┘
```

**The single most important architectural bet:** invest in the Ontology (L1). Every entity a new
app registers is one more thing the AI (Pulse) can reason about — for free, for every user, without
per-app AI training. A question spanning Carbon + Research + Facilities is answerable because they
all share the same OrgUnit entity as a join key in the ontology graph.

See **[`docs/PLATFORM_APP_MODEL.md`](PLATFORM_APP_MODEL.md)** § 3 for the full ontology design.

---

## 5. Phased roadmap (strangler, not big-bang)

**Stage 0 — Stabilize (done / ongoing):** Django + Postgres + Redis solid. Tenant removed. Auth/RBAC working.

**Stage 1 — Data Trust core (current):**
- [ ] **Catalog layer** over `dataschema` — descriptions, business glossary, owners/stewards, semantic tags, quality status.
- [ ] **MDM (lightweight)** — reference/master data, golden records, entity matching/merge, stewardship.
- [ ] **Data profiling** — completeness, uniqueness, patterns per field.
- [ ] **DQ status per table/field** — rules, scoring, surfaced in the catalog.

> AI/semantic/RAG (pgvector, LLM gateway, agents) are **owned by Pulse**, not built here. The in-repo `ai_copilot` app is superseded by Pulse.

**Stage 2 — Data Trust features:**
- Semantic search over catalog + data (embeddings).
- AI-suggested validation/DQ rules; anomaly detection on rows.
- Data observability (freshness/completeness trends).
- Lineage between tables/fields.

**Stage 3 — Platform/app separation (formalised 2026-07-23):**
- Factor Carbon domain logic into `apps/carbon/` — a self-contained package with a manifest.
- App manifest contract covers: route namespace, API namespace, ontology extensions, RBAC roles, navigation items, platform dependencies, AI skills, lifecycle hooks.
- Platform shell reads manifests dynamically → automatic nav injection, route guards, role registration.
- Prove the pattern by registering a second stub app (zero-feature, just validates isolation).
- Future apps (Academic, Research, Facilities, Goals) are additive: drop a folder + manifest, zero core changes.
- Full specification: **[`docs/PLATFORM_APP_MODEL.md`](PLATFORM_APP_MODEL.md)**

**Stage 4 — Optional infra evolution:**
- Managed Postgres/Storage (possibly Supabase) *behind* Django, only if ops demands it.

---

## 6. Principles to hold the line on
- **The platform is the OS; apps are the applications.** Every architectural decision must pass: *"Does adding a new app require changing the core?"* If yes, the boundary was violated.
- **Lighter than Ataccama** — resist enterprise sprawl; one core, pluggable apps, no per-app microservices.
- **Metadata-driven first** — new capability should be describable as metadata (or an ontology entity), not hard-coded.
- **Ontology-first for AI** — the AI reasons over the ontology, not over app tables. Every registered entity = one more AI capability for free.
- **Isolation is sacred** — core never imports apps; apps never import each other; cross-app data flows only via ontology + platform events.
- **AI-native, provider-agnostic** — never hard-couple to a single model vendor. Pulse is the AI layer; the platform exposes capabilities to it.
- **Trust is the product** — governed, quality-checked, cataloged, observable, explainable data.
- **Strangler over big-bang** — evolve in place. Never rewrite the moat for architectural purity.

---

## 7. Key Reference Documents

| Document | Purpose |
|---|---|
| **[`docs/PLATFORM_APP_MODEL.md`](PLATFORM_APP_MODEL.md)** | **Canonical reference.** Four-layer model, ontology design, app manifest contract, route namespaces, AI integration, migration path. |
| [`docs/DESIGN_DATA_TRUST_CORE.md`](DESIGN_DATA_TRUST_CORE.md) | Platform services design (Catalog, MDM, DQ, Governance) |
| [`docs/DESIGN_ORG_ACCESS_MODEL.md`](DESIGN_ORG_ACCESS_MODEL.md) | ScopedRole RBAC design |
| [`plans/CARBON_PRODUCT_APPS_ARCHITECTURE.md`](../plans/CARBON_PRODUCT_APPS_ARCHITECTURE.md) | Carbon as App #1 — feature portfolio and delivery plan |
