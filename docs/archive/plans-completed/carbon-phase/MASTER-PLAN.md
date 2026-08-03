# Carbon Domain — Master Plan v1.0

## Vision

Carbon is a **GHG emissions management platform** built on the Data Trust Platform. It serves three personas — Data Owners, Analysts, and Admins — through purpose-built workflows that follow GHG Protocol and ISO 14064 standards.

**Design principle**: Every page answers one question. Every number has provenance. Every action is auditable.

---

## UI/UX Philosophy

| Principle | Implementation |
|---|---|
| **Compact** | MUI dense mode, `size="small"` inputs, 24px row heights in tables — **Decision B** |
| **Enterprise** | Professional typography, no animations >200ms, clear hierarchy |
| **Beautiful** | Light (default): Blue #2563eb + Zinc. Dark: Blue #3b82f6 + Zinc. Theme switch button. |
| **Data-forward** | Charts + tables balanced equally (Decision C). Sparklines in stat cards. |
| **Progressive** | Summary → breakdown → raw data → right panel (entity metadata, collapsible/resizable) |

**Layout decisions (2026-07-26):**
- Density: **B — Compact**
- Color: **Blue + Zinc** with light/dark theme switch
- Navigation: **Sidebar + Tabs + Right collapsible resizable panel**
- Cards: **A — Minimal bordered** (1px border, no shadow)
- Data: **C — Balanced** charts + tables
- Width: **A — Full fluid** (no max-width)
- Animations: **B — Subtle** (<200ms hover only)
- Empty: **B — Illustrated** (icon + title + desc + CTA)

**Reference inspirations**: Linear.app (task density), Stripe Dashboard (data cards), Bloomberg Terminal (information density), Vercel Analytics (clean charts)

---

## Architecture

```
┌──────────────────────────────────────────────────┐
│                   Carbon App                       │
│  Console │ My Data │ Dashboard │ Reports │ Admin   │
├──────────────────────────────────────────────────┤
│              Unified Component Library             │
│  DataGrid │ Cards │ Page │ Layout │ Feedback │ Form│
├──────────────────────────────────────────────────┤
│              Emissions Engine                      │
│  Factors · GWPs · Rules · Calculations · Periods  │
├──────────────────────────────────────────────────┤
│            Data Trust Platform                     │
│  core │ catalog │ dataschema │ mdm │ dq │ audit   │
└──────────────────────────────────────────────────┘
```

---

## Phased Roadmap

### Phase 00 — Component Library Foundation
**Goal**: Build the shared UI components that ALL subsequent phases depend on.
- `CarbonDataGrid` — standardized table with pagination, sort, resize, show/hide, row highlight, action column
- `StatCard`, `WorkflowCard` — card components
- `PageHeader`, `EmptyState`, `LoadingSkeleton`, `ErrorAlert` — page structure
- `PeriodBanner`, `ActivityFeed` — feedback components
- `TabPanel`, `RightPanel` — layout components
- `SaveBar`, `FormField` — form components
- Light/dark theme switch implementation

### Phase 01 — Carbon Console (Landing)
**Question answered**: "What needs my attention?"
- Active period status
- DQ alerts & submission deadlines
- Quick stats (total emissions, sources, quality score)
- Role-aware workflow cards
- Recent activity feed

### Phase 02 — My Data (Data Owner Portal)
**Question answered**: "What data do I need to enter?"
- Org unit context header
- Module cards with scope badge, quality, status
- Data entry form (dynamic, based on DataTable schema)
- Bulk import (CSV)
- Submission workflow (draft → submitted)

### Phase 03 — Emissions Dashboard
**Question answered**: "What's our carbon footprint?"
- Scope 1/2/3 breakdown (donut + bar)
- YoY comparison chart
- Top emission sources table
- Org unit drill-down
- Period selector

### Phase 04 — Calculations & Verification
**Question answered**: "Are our numbers correct?"
- Calculation queue (pending, running, complete)
- Per-row calculation results with factor traceability
- DQ score overlay
- Verification workflow (review → approve → lock)
- Recalculate / recalculate-all actions

### Phase 05 — Reporting
**Question answered**: "How do we report our emissions?"
- Report builder (4-step wizard: scope → period → grouping → format)
- Preview before export
- Saved reports library with re-run
- CSV + JSON export
- Share via link

### Phase 06 — Admin Configuration
**Question answered**: "How do we configure the system?"
- Emission Factors CRUD with import
- Calculation Rules CRUD with test-run
- Reporting Periods CRUD with workflow transitions
- GWP reference table

### Phase 07 — Targets & Goals
**Question answered**: "Are we on track?"
- Science-based targets definition
- Reduction goal tracking
- Progress bars vs baseline
- Forecast projection

### Phase 08 — Hardening
- RBAC enforcement (remove `role: '*'`)
- DQ engine wiring (real validation on calculate)
- Governance policy enforcement
- Performance optimization
- Test coverage

---

## Phase 01 — Console: Detailed Spec

### What exists today
- `CarbonConsolePage.jsx` — workflow cards, active period alert, quick stats
- `fetchOwnerSummary()` API from `emissions/api.py`
- `fetchActiveReportingPeriod()` API from `emissions/api.py`

### What needs to change

#### Backend (BE-01)
1. **New endpoint**: `GET /emissions/console/` — aggregates all console data in one call
   - Active period (name, dates, status, days remaining)
   - Quick stats (total modules, total tables, total calculations, avg DQ)
   - Pending submissions (modules with data entered but not submitted)
   - DQ alerts (modules with quality below threshold)
   - Recent activity (last 10 calculations with timestamps)

2. **Enhance**: `OwnerSummaryAPIView` → add `pending_submissions`, `dq_alerts`

3. **New model or computed**: Submission status tracking on Module level

#### Frontend (FE-01) — Uses shared component library (Phase 00)
1. **Rewrite** `CarbonConsolePage.jsx` using shared components:
   - `<PageHeader>` — title + subtitle + role badge
   - `<PeriodBanner>` — active period with countdown and status
   - `<StatCard>` × 5 — emissions, modules, tables, quality, calculations (with sparklines)
   - `<WorkflowCard>` × 6 — Dashboard, My Data, Reports, Factors, Rules, Periods
   - `<ActivityFeed>` — last 10 calculations in compact timeline
   - `<ErrorAlert>`, `<LoadingSkeleton>`, `<EmptyState>` — for all states
   - Alert chips row — DQ warnings + pending submission chips
   - **Remove** "Getting Started" paper entirely
   - **Max 200 lines** — components handle the complexity

### Contract: Console API

```
GET /api/v1/emissions/console/

Response:
{
  "active_period": {
    "id": 1,
    "name": "FY 2026",
    "start_date": "2026-01-01",
    "end_date": "2026-12-31",
    "status": "open",
    "days_remaining": 159
  },
  "stats": {
    "total_modules": 5,
    "total_tables": 12,
    "total_calculations": 44,
    "avg_quality_score": 87.5,
    "total_emissions_tonnes": 2669.9
  },
  "alerts": [
    {"type": "dq", "module": "Electricity S2", "score": 45, "message": "Quality below threshold"},
    {"type": "pending", "module": "Water S3", "rows": 12, "message": "12 rows pending submission"}
  ],
  "recent_activity": [
    {"action": "calculation", "module": "Electricity S2", "timestamp": "2026-07-25T10:30:00Z", "detail": "12 rows calculated"}
  ]
}
```
