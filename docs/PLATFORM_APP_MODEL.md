# Platform App Model — Architecture Reference

> **Status:** Living document. Canonical reference for the platform-as-OS / apps-as-plugins model.
> **Version:** 1.0 — 2026-07-23
> **Supersedes:** The "hosted apps" section previously scattered across STRATEGY_DATA_TRUST_PLATFORM.md
>   and CARBON_PRODUCT_APPS_ARCHITECTURE.md.
> **Scope:** This document defines HOW apps plug into the platform. It does not define any specific
>   app's feature set (see each app's own architecture file for that).

---

## 1. The Core Mental Model

> **The platform is the operating system. Apps are the applications running on it.**

This is not a metaphor — it is the literal design constraint. Every decision must pass this test:

> *"When Research Management arrives in 2027, does adding it require changing the platform core —
>   or just adding a manifest and an app folder?"*

If the answer is **just a manifest**, the platform is working. If it's **change the core**, the
model has been violated.

This is exactly how the highest-leverage platforms in enterprise software are structured:

| Platform | "OS" layer | "Apps" on top |
|---|---|---|
| **Salesforce** | CRM Platform, Apex, Flows | Sales Cloud, Service Cloud, Net Zero Cloud |
| **ServiceNow** | Now Platform, CMDB, Auth, Workflows | ITSM, HR Service Delivery, SecOps |
| **SAP BTP** | Dataverse, Auth, MDM, Governance | S/4HANA, Sustainability Control Tower |
| **Microsoft** | Power Platform, Dataverse | Finance, Supply Chain, Sustainability |
| **Palantir Foundry** | Ontology, Auth, Data Fabric | AIP apps, operational apps |

The one that nailed it earliest for data: **Palantir Foundry**. Its Ontology layer is the reason
a new app is AI-ready the moment it registers — the AI reasons over the ontology, not over app tables.

---

## 2. Four-Layer Architecture

```
┌───────────────────────────────────────────────────────────────────────────┐
│  LAYER 4 — AI / EXPERIENCE FABRIC                                          │
│                                                                             │
│  Conversational copilot (Pulse) · Agentic workflows · Unified search       │
│  Dashboards · Report generation · Notifications                            │
│                                                                             │
│  ← ONE assistant reasons across ALL apps via the shared Ontology →         │
│  ← Apps expose "skills" to the AI; AI orchestrates across them →           │
├───────────────────────────────────────────────────────────────────────────┤
│  LAYER 3 — DOMAIN APPS (pluggable, isolated, replaceable)                  │
│                                                                             │
│  Carbon Footprint │ Academic Portfolio │ Research Projects                  │
│  Sustainability Goals │ Facilities Mgmt │ Procurement │ ...                 │
│                                                                             │
│  Each app: manifest + own models + own UI namespace + own roles             │
│  Consumes platform services. Never touches another app's tables.            │
├───────────────────────────────────────────────────────────────────────────┤
│  LAYER 2 — PLATFORM SERVICES (the "Data Trust Core")                       │
│                                                                             │
│  catalog · mdm · dq · governance · audit · dataschema engine               │
│  auth + ScopedRole RBAC · workflow engine · notifications · file store      │
│  event bus · lineage · observability                                        │
│                                                                             │
│  ← Domain-agnostic. No Carbon-specific logic here. →                       │
│  ← Apps consume these as services via stable internal APIs. →               │
├───────────────────────────────────────────────────────────────────────────┤
│  LAYER 1 — SEMANTIC CORE / ONTOLOGY                                        │
│                                                                             │
│  Entity registry · Relationship graph · OrgUnit hierarchy                  │
│  Shared metric definitions · Policy bindings · Lifecycle states            │
│                                                                             │
│  ← The shared language every app AND every AI agent speaks. →              │
│  ← Apps extend it; they never bypass it. →                                 │
└───────────────────────────────────────────────────────────────────────────┘
         ↑ built on ↑
┌───────────────────────────────────────────────────────────────────────────┐
│  INFRASTRUCTURE                                                             │
│  Django + DRF · PostgreSQL · Redis · Celery · Object Storage    │
└───────────────────────────────────────────────────────────────────────────┘
```

### Layer Ownership Rules (inviolable)

| Rule | Why |
|---|---|
| Core (L1/L2) never imports from apps (L3) | Prevents reverse dependency / coupling |
| Apps never import each other's models | Isolation; cross-app data flows only via ontology events |
| New platform features extend L1/L2, never L3 | Keeps platform generic and reusable |
| L4 (AI/UX) reasons over L1 ontology, not over app tables | Makes AI work for all apps without per-app training |

---

## 3. Layer 1 — The Ontology: Why It's the Key to AI

Most platforms fail at AI because they train models per-app. The insight from Palantir Foundry and
Microsoft Dataverse: **AI that reasons over a shared ontology works for every app, automatically.**

### What the Ontology is

The Ontology is not a database schema. It's a **semantic graph** of:
- **Entities** — what things exist in the platform (`OrgUnit`, `Asset`, `Metric`, `Policy`)
- **Relationships** — how they connect (`OrgUnit` owns `Asset`; `Asset` measured_by `Metric`)
- **App extensions** — each app registers its domain entities into the shared graph

```
PLATFORM ONTOLOGY (shared, always present)
│
├── OrgUnit ──owns──> DataProduct ──has──> Asset ──measured_by──> Metric
│       │                                         │
│       └──governed_by──> Policy                  └──scored_by──> QualityResult
│
├── User ──has_role──> ScopedRole ──scoped_to──> OrgUnit
│
└── Event ──attributed_to──> OrgUnit

CARBON APP EXTENSION (registered by Carbon manifest)
│
├── Emission ──attributed_to──> OrgUnit
│       ├── scope: (1 | 2 | 3)
│       └── reporting_period ──> ReportingPeriod
│
├── EmissionFactor ──referenced_by──> Emission
└── ReportingPeriod ──lifecycle──> (draft→open→locked→closed)

ACADEMIC APP EXTENSION (future, registered by Academic manifest)
│
├── Program ──belongs_to──> OrgUnit
├── KPI ──measured_for──> Program
└── AccreditationCycle ──lifecycle──> (open→submitted→reviewed→closed)

RESEARCH APP EXTENSION (future)
│
├── Project ──led_by──> OrgUnit
├── Grant ──funds──> Project
└── Publication ──produced_by──> Project
```

### Why this enables next-gen AI

```
User (to AI copilot): "Which campuses missed their carbon targets AND have
                       research projects with overdue milestones?"

AI reasoning path (via ontology, NO app-specific code):
  1. Carbon App   → ReportingPeriod(status=open) + Emission totals per OrgUnit
  2. Research App → Project(milestones=overdue) per OrgUnit
  3. Ontology     → JOIN via OrgUnit entity (shared reference)
  4. Answer       → [Smart Village: -12% vs target, 3 overdue projects]

No app knows about the other. The ONTOLOGY is the join key.
```

The ontology is what makes a question about Carbon + Research possible without writing Carbon-Research
integration code. This is the architectural bet: **invest in the ontology, get AI for free.**

---

## 4. Layer 3 — The App Contract (Pluggability, Concretely)

Every domain app is a **self-describing package**. The platform shell reads the manifest at startup
and configures everything automatically: routes, navigation, roles, AI skills, lifecycle hooks.

### App Manifest Structure

```javascript
// apps/carbon/manifest.js  ← Every app ships this file
export default {

  // ── IDENTITY ──────────────────────────────────────────────────
  id:          'carbon',
  name:        'Carbon Footprint',
  version:     '1.0.0',
  description: 'GHG emissions tracking, reporting, and analysis',
  icon:        'Co2',                       // MUI icon name
  color:       '#2e7d32',                   // theme color for this app

  // ── NAMESPACE ─────────────────────────────────────────────────
  // The platform guarantees these are exclusive to this app.
  routePrefix: '/carbon',                   // frontend owns /carbon/*
  apiPrefix:   'api/v1/carbon',             // backend owns this namespace

  // ── ONTOLOGY EXTENSION ─────────────────────────────────────────
  // What new entities and relationships this app teaches the platform.
  ontology: {
    entities: [
      { type: 'Emission',         metric: true,  owned_by: 'OrgUnit' },
      { type: 'ReportingPeriod',  lifecycle: true },
      { type: 'EmissionFactor',   reference: true },
      { type: 'CalculationRule',  reference: true },
    ],
    relationships: [
      { from: 'Emission',  to: 'OrgUnit',          rel: 'attributed_to' },
      { from: 'Emission',  to: 'ReportingPeriod',  rel: 'reported_in'   },
    ],
  },

  // ── RBAC ───────────────────────────────────────────────────────
  // App-scoped roles that extend the platform ScopedRole system.
  // Platform RBAC handles assignment; app just declares what roles exist.
  roles: [
    { key: 'carbon:data_owner', label: 'Data Owner',    scoped: true,  description: 'CRUD on assigned org-unit data' },
    { key: 'carbon:analyst',    label: 'Analyst',       scoped: false, description: 'Read-only, cross-org visibility' },
    { key: 'carbon:admin',      label: 'Carbon Admin',  scoped: false, description: 'Manage factors, rules, periods' },
  ],

  // ── NAVIGATION ─────────────────────────────────────────────────
  // Injected into platform shell nav by role. Platform renders this.
  navigation: {
    section: 'Carbon Footprint',
    items: [
      { label: 'Dashboard',          path: '/carbon/dashboard',         role: '*'                },
      { label: 'My Portal',          path: '/carbon/owner/portal',      role: 'carbon:data_owner'},
      { label: 'My Emissions',       path: '/carbon/owner/emissions',   role: 'carbon:data_owner'},
      { label: 'My Assets',          path: '/carbon/owner/assets',      role: 'carbon:data_owner'},
      { label: 'Analytics',          path: '/carbon/analytics',         role: 'carbon:analyst'   },
      { label: 'Reporting Periods',  path: '/carbon/reporting/periods', role: 'carbon:admin'     },
      { label: 'Emission Factors',   path: '/carbon/admin/factors',     role: 'carbon:admin'     },
    ],
  },

  // ── PLATFORM DEPENDENCIES ──────────────────────────────────────
  // Declares which platform services this app needs. Validated at install.
  requires: ['auth', 'rbac', 'catalog', 'mdm', 'dq', 'audit', 'workflow'],

  // ── AI SKILLS ──────────────────────────────────────────────────
  // What the platform copilot (Pulse) can do with this app's data.
  aiSkills: [
    { intent: 'query_emissions',       entity: 'Emission',         description: 'Retrieve emission totals by scope, period, org' },
    { intent: 'explain_calculation',   entity: 'Emission',         description: 'Explain how an emission was calculated' },
    { intent: 'summarize_period',      entity: 'ReportingPeriod',  description: 'Summarize org-unit data for a reporting period' },
    { intent: 'compare_periods',       entity: 'Emission',         description: 'Compare emissions across periods' },
  ],

  // ── LIFECYCLE HOOKS ────────────────────────────────────────────
  // Called by platform registry at install/uninstall time.
  hooks: {
    onInstall:   'carbon.registry.on_install',
    onEnable:    'carbon.registry.on_enable',
    onDisable:   'carbon.registry.on_disable',
    onUninstall: 'carbon.registry.on_uninstall',
  },
}
```

### The Isolation Contract

Apps communicate through **declared relationships in the ontology and platform events** — never
through direct model imports. This is enforced by convention now, automated by the registry later.

```
✅ ALLOWED                              ❌ FORBIDDEN
────────────────────────────────────    ─────────────────────────────────────
Carbon reads platform catalog API       Carbon imports Research's models
Research reads platform DQ API          Academic writes to Carbon's DB tables
Facilities emits platform event         Carbon app code in platform/catalog/
AI reads all apps via ontology          Apps sharing a database connection string
```

---

## 5. Route and API Namespace Structure

### Frontend — Current (Carbon is App #1)

```
/                      → Platform shell (role-aware landing)
/login                 → Platform auth

/platform/             → Platform-level tools (admin, power users)
  /catalog/            → Data catalog, assets, domains, glossary
  /admin/              → Org units, users, RBAC
  /quality/            → DQ dashboard, DQ rules (cross-app)
  /governance/         → Audit trail, policies

/carbon/               → Carbon Footprint App (App #1)
  /dashboard           → All carbon users
  /owner/              → Data Owner persona (scoped)
    /portal            → My domains + quality badges
    /emissions         → My scoped emissions dashboard
    /assets            → My scoped data assets
  /analytics/          → Analyst persona
  /reporting/          → Reporting cycle management
    /periods           → Period lifecycle
    /submissions       → Submission status
  /admin/              → Carbon admin only
    /factors           → Emission factor management
    /rules             → Calculation rules

/[app-id]/             → Future apps follow identical pattern
```

### Backend — Current (stable) + Future namespace

```
/api/v1/               → Platform services (stable, don't namespace under /platform/)
  /accounts/           → Auth, users, roles
  /catalog/            → Asset catalog, governance
  /mdm/                → Master data management
  /dq/                 → Data quality
  /dataschema/         → Schema engine
  /emissions/          → Carbon domain (existing, stable, keep as-is)
  /core/               → Org units, modules

/api/v1/carbon/        → New Carbon app features (new namespace, additive)
  /owner-dashboard/    → Scoped owner dashboard endpoint
  /reporting-periods/  → Period management
  /submission-workflow/→ Multi-step submission

/api/v1/[app-id]/      → Future apps follow identical pattern
```

> **Note:** Existing `/api/v1/emissions/` endpoints remain stable. New carbon-specific endpoints
> go under `/api/v1/carbon/`. No migration needed.

---

## 6. Future Apps — The Platform's Promise

The platform is designed to host these domain apps without core changes. Each follows the manifest
contract above.

| App ID | Domain | Key Entities | Key Roles |
|---|---|---|---|
| `carbon` | Sustainability, GHG emissions | Emission, Factor, Period | data_owner, analyst, admin |
| `academic` | Programs, KPIs, accreditation | Program, KPI, AccreditationCycle | program_lead, analyst, registrar |
| `research` | Projects, grants, publications | Project, Grant, Milestone, Publication | PI, coordinator, reviewer |
| `facilities` | Buildings, meters, work orders | Building, Meter, WorkOrder, Space | facilities_manager, technician |
| `sustainability-goals` | Strategic goals, targets | Goal, Target, Initiative, Progress | goal_owner, reporter, exec |
| `procurement` | Vendors, contracts, spend | Contract, Vendor, PurchaseOrder | buyer, approver, auditor |
| `hr-travel` | Travel emissions, policies | Trip, TravelPolicy, TravelEmission | traveler, approver, admin |

**When "Academic Portfolio" is built:**
1. Drop `apps/academic/` folder with manifest + models + UI
2. Register entities in ontology (`Program`, `KPI`, `AccreditationCycle`)
3. The AI copilot can now answer *"which programs have poor data quality AND low KPI scores?"*
   — **without writing a single line of AI code**

---

## 7. AI-Native Design (Integration with Pulse)

Pulse is the platform's external AI/agentic system. It integrates via:

1. **Ontology API** — Pulse reads the entity registry and relationship graph. This is how it knows
   what "Emission" is and how it relates to "OrgUnit" without being trained on our database schema.

2. **App Skills API** — Pulse discovers what each app can do via the `aiSkills` block in manifests.
   Skills are verb-noun pairs: `query_emissions(Emission)`, `summarize_period(ReportingPeriod)`.

3. **Scoped data access** — Pulse calls platform APIs with the user's JWT. Platform RBAC enforces
   org-unit scoping. Pulse sees only what the user sees. No special bypass.

4. **Cross-app reasoning pattern:**
   ```
   User intent → Pulse identifies relevant skills across apps
              → Pulse calls each app's skill endpoint
              → Results joined via shared OrgUnit/Entity references
              → Pulse synthesizes and returns unified answer
   ```

This is why **the ontology is the most important architectural investment**. Every entity registered
= one more thing Pulse can reason about, for free, for every user.

---

## 8. Migration Path (Strangler Fig — No Big-Bang)

### Move 1 — Establish the seam (this sprint, low risk, no breaking changes)
- Create `apps/carbon/` folder in frontend; move data-owner + emissions pages there
- Add legacy route redirects: `/data-owner/*` → `/carbon/owner/*`, `/emissions/*` → `/carbon/*`
- Create `apps/carbon/manifest.js` seed (even if shell doesn't fully read it yet)
- New backend features go under `/api/v1/carbon/`; existing endpoints stable
- **Catalog/MDM/DQ untouched** — they are already the platform layer

### Move 2 — Build the registry (next sprint)
- Platform shell reads all manifests at startup
- Dynamic navigation injection (sidebar items come from manifests, not hardcoded)
- Dynamic route registration (app routes registered from manifest, not hardcoded in App.jsx)
- Prove isolation by registering one trivial stub app — validates the pattern works

### Move 3 — Elevate the ontology (the strategic investment)
- Formalize entity/relationship registry as a platform API
- Point Pulse at the ontology API — AI becomes cross-app for free
- Each future app registers entities; AI works immediately

---

## 9. Principles (The Line We Hold)

1. **The core never imports from apps.** Dependency direction is always: apps → platform, never reverse.
2. **Apps never import each other.** Cross-app data only flows through ontology relationships and platform events.
3. **New platform capability = extends L1/L2.** New app capability = extends L3. These are distinct.
4. **The AI lives in L4, reasons over L1.** It does not know about Carbon vs. Research. It knows about Entities and Relationships.
5. **Catalog, MDM, DQ are platform services.** They are not part of any app. Every app consumes them.
6. **Namespace isolation is sacred.** An app's route prefix and API prefix are its exclusive territory.
7. **Lighter than Ataccama.** Resist enterprise sprawl. One core, pluggable apps, no separate microservices per app.
8. **Strangler over big-bang.** Evolve in place. Never rewrite the moat for architectural purity.

---

## 10. Reference: How This Aligns With Top Systems

| Pattern | Source system | Our equivalent |
|---|---|---|
| AppExchange manifest | Salesforce managed packages | `apps/*/manifest.js` |
| Application scope isolation | ServiceNow scoped apps | `routePrefix` + `apiPrefix` namespace |
| Ontology + AIP skills | Palantir Foundry | Entity registry + `aiSkills` in manifest |
| Solution packages | Microsoft Dataverse | App folder + manifest |
| BTP extension apps | SAP BTP | Apps-as-plugins consuming platform APIs |
| Domain app on data fabric | Databricks Lakehouse | Apps consuming Data Trust Core |

The key lesson from all of them: **the platform team and the app team must never share a sprint goal.**
Platform evolves the OS. App teams ship business value. If they're the same team, keep the files
and architectural boundary strict anyway — it's the rule that lets you scale.
