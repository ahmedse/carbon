# Carbon Domain — Design & Architecture v3.0

> Updated: 2026-08-11 | Master: GitHub Copilot + DeepSeek V4 Pro

---

## 1. System Identity

Carbon is a **GHG emissions management domain app** built on the AASTMT Data Trust Platform. It serves institutional carbon accounting needs following **GHG Protocol Corporate Standard** and **ISO 14064**.

**Not a generic carbon calculator.** Carbon is purpose-built for AASTMT's organizational structure (university → campus → college → department → facility), with Egypt-specific emission factors and bilingual readiness.

---

## 2. Data Trust Platform Foundation

Carbon sits on top of these platform primitives:

| Layer | Provides | Carbon Uses It For |
|---|---|---|
| **core.Module** | Data collection unit, org-scoped | Emission source (e.g., "Abu Qir Electricity") |
| **dataschema.DataTable** | Dynamic schema, virtual tables | Activity data structure (e.g., monthly kWh) |
| **dataschema.DataRow** | JSON row storage | Individual activity records |
| **mdm.OrgUnit** | Hierarchical org tree | Organizational boundary (campus → facility) |
| **mdm.ReferenceSet** | Master data lists | Fuel types, grid regions, GWP reference |
| **catalog.AssetProfile** | Metadata + quality score | Per-source DQ tracking |
| **catalog.GovernanceEvent** | Immutable audit trail | Who changed what, when, why |
| **dq** | Rule-based quality engine | Data completeness, range checks |

---

## 3. Architecture Principles

1. **Domain isolation**: `emissions` may import `core`, `dataschema`, `mdm`, `catalog`, `dq`. Platform apps MUST NOT import `emissions`.
2. **Emission factors are global** (not org-scoped). Activity data + calculations are org-scoped.
3. **Dynamic schema, static calculation**: DataTables are user-defined, but CalculationRules bridge dynamic fields to typed emission factors.
4. **Immutable calculations**: Once verified, calculations are locked. Modifications create new versions, not edits.
5. **Monthly reporting cycles**: Default cadence, with annual aggregation.
6. **No auto-approval**: Calculations must be manually reviewed before verification.

---

## 4. AI Intelligence Layer (Planned — Phase 2)

Carbon's AI capability is a **platform intelligence service**, not a siloed chatbot. It lives in `backend/ai/` and provides a single swappable interface that every Carbon subsystem consumes.

### 4.1 Architecture

```
backend/ai/
├── protocol.py          # AIProvider ABC + typed dataclasses (the swappable contract)
├── providers/
│   └── pulse.py         # PulseProvider — default backend, implements AIProvider via POST /tasks
├── intelligence.py      # CarbonIntelligence — scope resolution, domain context, caching
├── views.py             # DRF endpoints: /api/v1/ai/chat/, /dq/validate/, /anomaly/detect/, etc.
├── cache.py             # TTL cache for AI responses
└── signals.py           # Audit logging + cost tracking
```

### 4.2 Key Components

| Component | Role |
|-----------|------|
| **`AIProvider` (ABC)** | Swappable protocol — 9 methods. Any AI backend implements this. |
| **`PulseProvider`** | Default implementation — maps AIProvider methods to `POST /tasks` |
| **`CarbonIntelligence`** | Service layer — resolves user scope, injects GHG domain vocabulary, delegates to provider, caches results, logs audit |

### 4.3 Design Principles

1. **Protocol-first.** `ai/protocol.py` imports nothing from Django, Pulse, or any provider. Pure ABCs and dataclasses.
2. **Provider-agnostic.** Carbon never imports `PulseProvider`. Swap backends via `settings.AI_PROVIDER_CLASS`.
3. **Scope is mandatory.** Every AI call carries a `Scope(org_unit_ids, module_ids, read_only)` from Carbon's RBAC.
4. **Fail-visible, never fail-open.** AI unavailable → `status: "provider_unavailable"`, scores reflect the gap.
5. **Chat through API, analytics through DB.** Coworker chat goes through Carbon's REST API (RBAC, soft-delete). DQ profiling uses direct DB with injected scope filters.
6. **Suggestions are data.** Persisted, reviewed, accepted/rejected. Nothing auto-creates or auto-applies.

### 4.4 API Surface — `/api/v1/ai/`

| Endpoint | Method | Consumer | Auth |
|----------|--------|----------|------|
| `/chat/` | POST | Coworker UI | `HasAiAccess` |
| `/chat/history/` | GET | Coworker UI | `HasAiAccess` |
| `/dq/validate/` | POST | DQ Engine | `HasAiAccess` |
| `/dq/suggest/` | POST | DQ Rules UI | `HasAiAccess` |
| `/anomaly/detect/` | POST | DQ Jobs | `HasAiAccess` |
| `/anomaly/explain/` | POST | DQ UI | `HasAiAccess` |
| `/report/draft/` | POST | Report UI | `HasAiAccess` |
| `/schema/analyze/` | POST | Schema UI | `HasAiAccess` |
| `/fix/suggest/` | POST | DQ UI | `HasAiAccess` |
| `/status/` | GET | Any | `IsAuthenticated` |

See [docs/AI_WORKSPACE_ARCHITECTURE.md](AI_WORKSPACE_ARCHITECTURE.md) for the architecture standard and [plans/CARBON_AI_WORKSPACE_PHASED_PLAN.md](../plans/CARBON_AI_WORKSPACE_PHASED_PLAN.md) for the phased implementation plan.

---

## 5. Scope Taxonomy

Three distinct "scope" concepts — never conflate:

| Concept | Meaning | Field |
|---|---|---|
| **GHG Scope** | Emission taxonomy (Scope 1/2/3) | `EmissionFactor.scope`, `Calculation.scope` |
| **Access Scope** | OrgUnit subtree RBAC | `get_visible_org_unit_ids(user)` |
| **AI Scope** | Per-call RBAC boundary injected into AI provider | `Scope(org_unit_ids, module_ids, read_only)` |
| **Module.scope** | Advisory only | `Module.scope` — deprecated in favor of factor-level scope |

---

## 6. UI/UX System — FINALIZED 2026-07-26

### Decisions

| Decision | Choice | Detail |
|---|---|---|
| Density | **B — Compact** | 24px table rows, `size="small"` inputs, 16px card padding |
| Color | **Blue + Zinc** | Light (default): `#2563eb` + slate. Dark: `#3b82f6` + zinc. Theme switch button. |
| Navigation | **Sidebar + Tabs + Right Panel** | Left sidebar, breadcrumbs, tab bars for sub-pages, collapsible/resizable right panel for entity metadata |
| Cards | **A — Minimal bordered** | `border: 1px solid divider`, no shadow, 8px radius |
| Data Presentation | **C — Balanced** | Charts and tables equal weight, sparklines in stat cards |
| Page Width | **A — Full fluid** | No max-width, content fills viewport |
| Animations | **B — Subtle** | Hover color shifts only, <200ms |
| Empty States | **B — Illustrated** | Icon + title + description + CTA |

### Visual Language

| Element | Spec |
|---|---|
| **Typography** | System font stack: `-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif` |
| **Primary (light)** | `#2563eb` (blue-600) |
| **Primary (dark)** | `#3b82f6` (blue-500) |
| **Neutrals (light)** | Zinc/slate: `#18181b` → `#f4f4f5` |
| **Neutrals (dark)** | Zinc dark: `#fafafa` → `#18181b` |
| **Success** | `#16a34a` (green-600) |
| **Warning** | `#d97706` (amber-600) |
| **Error** | `#dc2626` (red-600) |
| **Border radius** | 8px (cards, inputs), 4px (chips, badges) |
| **Shadow** | `boxShadow: 1` only for interactive overlays, never for cards |

### Unified Component Library

Every page MUST use these shared components. Never create ad-hoc tables or cards.

```
src/components/
  DataGrid/
    CarbonDataGrid.jsx       ← THE standard table (pagination, sort, resize, show/hide, highlight, actions)
  Cards/
    StatCard.jsx             ← Stat metric (value + unit + icon + sparkline + trend)
    WorkflowCard.jsx         ← Navigation card (icon + title + description + onClick)
  Page/
    PageHeader.jsx           ← Title + subtitle + breadcrumb + badge + actions
    EmptyState.jsx           ← Icon + title + description + CTA
    LoadingSkeleton.jsx      ← Skeleton matching layout shape
    ErrorAlert.jsx           ← Alert with retry button
  Layout/
    TabPanel.jsx             ← Tab content container
    RightPanel.jsx           ← Collapsible/resizable entity metadata sidebar
  Feedback/
    PeriodBanner.jsx         ← Active period status bar
    ActivityFeed.jsx         ← Compact timeline
  Form/
    SaveBar.jsx              ← Bottom-pinned Cancel + Save
    FormField.jsx            ← Standard field (label above, size=small)
```

---

## 6. User Personas & Journeys

| Persona | Real Role | Core Question | Primary Page |
|---|---|---|---|
| **Data Owner** | Facilities officer, transport manager | "What data do I need to enter this month?" | My Data |
| **Analyst** | Sustainability analyst, internal auditor | "What's our footprint, and is the data trustworthy?" | Dashboard + Calculations |
| **Admin** | Carbon program manager | "Is the system configured correctly?" | Admin Console |

### Data Owner Journey
```
Login → Console (see alerts) → My Data (enter monthly activity)
  → Submit for review → (Analyst picks up)
```

### Analyst Journey
```
Login → Console (see pending submissions) → Dashboard (review footprint)
  → Calculations (verify DQ, approve) → Reports (generate, export)
```

### Admin Journey
```
Login → Console (system health) → Factors (update grid factor)
  → Rules (configure new source) → Periods (open new cycle)
```

---

## 7. Page Architecture

```
/carbon
  /console           ← Landing: alerts, stats, workflows
  /my-data           ← Data owner portal: modules, data entry
  /dashboard         ← Footprint visualization, trends
  /calculations      ← Calculation queue, verification
  /reporting
    /generate        ← Report builder wizard
    /saved           ← Saved reports library
    /periods         ← Reporting period management
  /admin
    /factors         ← Emission factors CRUD
    /rules           ← Calculation rules CRUD
  /targets           ← Science-based targets, goals
```

---

## 8. Emission Factor Catalog

### Implemented (Phase 0)

| Code | Name | Factor | Unit | Scope |
|---|---|---|---|---|
| `EG_GRID_2024` | Egypt National Grid 2024 | 0.4584 | kg CO2e/kWh | 2 |
| `EG_WATER_2024` | Egypt Water Supply 2024 | 0.344 | kg CO2e/m³ | 3 |

### Planned (Phase 06)

| Code | Category | Priority |
|---|---|---|
| `EG_DIESEL` | Stationary combustion | High |
| `EG_NATURAL_GAS` | Stationary combustion | High |
| `EG_PETROL` | Mobile combustion | High |
| `EG_WASTE` | Waste disposal | Medium |
| `EG_PAPER` | Materials (paper) | Low |

---

## 9. Known Technical Debt

All items below resolved in Enterprise Readiness phases E0-E5. Retained for historical reference.

| # | Item | Severity | Status |
|---|---|---|---|
| 1 | RBAC nav items all `role: '*'` | High | ✅ Fixed (E2) |
| 2 | Governance policy enforcement not wired | High | ✅ Fixed (E3) |
| 3 | DQ execute action is stub | High | ✅ Fixed (E3) |
| 4 | Only 4/15 Scope 3 categories | Medium | ✅ Fixed (E3) |
| 5 | No spend-based calculation | Medium | Deferred |
| 6 | No organizational boundary model | Medium | Deferred |
| 7 | Tests broken/stale | Medium | ✅ 431 passing (E5) |
| 8 | Legacy `reporting_year`/`reporting_month` fields | Low | Deferred |

---

## 10. Master-Worker Protocol

See `.ai-toolkit/universal/handoff.md` for the current task delegation protocol.
