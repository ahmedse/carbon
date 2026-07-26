# TASK-FE-01: Carbon Console — Page Redesign

## Context (from master)

Phase 01 of Carbon rebuild. The Console (`/carbon/console`) is the landing page — it must immediately tell the user "what needs my attention." The current `CarbonConsolePage.jsx` exists but needs a complete redesign per the new UI/UX philosophy: compact, enterprise, beautiful, data-forward.

The backend worker (BE-01) is creating a single `GET /api/v1/emissions/console/` endpoint that returns all data in one call. You consume that.

## Prerequisites

**Read before starting:**
1. `/home/ahmed/aast/carbon/plans/carbon-phase/SHARED-CONTEXT.md` — patterns, auth, API conventions
2. `/home/ahmed/aast/carbon/plans/carbon-phase/PROTOCOL.md` — do's and don'ts, UI conventions
3. `/home/ahmed/aast/carbon/carbon-frontend/src/pages/carbon/CarbonConsolePage.jsx` — current page
4. `/home/ahmed/aast/carbon/carbon-frontend/src/api/emissions.js` — existing API functions
5. `/home/ahmed/aast/carbon/carbon-frontend/src/auth/AuthContext.jsx` — useAuth() shape

## API Contract (from BE-01)

```
GET /api/v1/emissions/console/

Response: {
  active_period: { id, name, start_date, end_date, status, days_remaining } | null,
  stats: { total_modules, total_tables, total_calculations, avg_quality_score, total_emissions_tonnes },
  alerts: [{ type, module_name, score?, threshold?, pending_rows?, message }],
  recent_activity: [{ id, action, module_name, timestamp, detail }]
}
```

## Scope — DO

### 1. Add API function in `src/api/emissions.js`
```javascript
export async function fetchConsoleData() {
  return apiFetch('/api/v1/emissions/console/');
}
```

### 2. Redesign `CarbonConsolePage.jsx`

**Layout (top-to-bottom, full fluid width):**

```
┌──────────────────────────────────────────────────────────┐
│  Carbon Overview                          [Admin] [Chip] │  ← PageHeader component
│  Manage organizational carbon emissions...                │
├──────────────────────────────────────────────────────────┤
│  ⚠ FY 2026 is open · 159 days remaining         [View]   │  ← PeriodBanner component
├──────────────────────────────────────────────────────────┤
│  [DQ Alert chip] [Pending chip] [+N more]                 │  ← Alert row (only if alerts exist)
├──────────────────────────────────────────────────────────┤
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐     │
│  │ 2,670   │ │    5     │ │   12     │ │   88%    │ ... │  ← StatCard components
│  │ tCO₂e   │ │ Modules  │ │ Tables   │ │ Quality  │     │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘     │
├──────────────────────────────────────────────────────────┤
│  Workflows                                               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                 │
│  │ Dashboard│ │ My Data  │ │ Reports  │                 │  ← WorkflowCard components
│  └──────────┘ └──────────┘ └──────────┘                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                 │
│  │ Factors  │ │ Rules    │ │ Periods  │                 │  ← Admin-only row
│  └──────────┘ └──────────┘ └──────────┘                 │
├──────────────────────────────────────────────────────────┤
│  Recent Activity                                         │
│  ● Jul 25 10:30 — Electricity S2 — 12 rows calc'd        │  ← ActivityFeed component
│  ● Jul 24 14:15 — Water S3 — 5 rows calc'd               │
└──────────────────────────────────────────────────────────┘
```

**USE THESE SHARED COMPONENTS** (from `src/components/`):
- `<PageHeader>` — title + subtitle + badge + action buttons
- `<PeriodBanner>` — active period info/warning bar
- `<StatCard>` — each stat metric (5 across)
- `<WorkflowCard>` — each workflow card (6 total, 3-col grid)
- `<ActivityFeed>` — compact timeline

**Specs:**

**PageHeader**: Title "Carbon Overview", subtitle role-aware, show `[Admin]` chip if `isAdmin`.

**PeriodBanner**: Pass `period` prop. Auto-handles active (info), missing (warning with CTA), locked (error).

**Alert row**: Only renders if `alerts.length > 0`. Horizontal `Stack` of `<Chip>`:
- DQ: `color="warning"`, `variant="outlined"`
- Pending: `color="info"`, `variant="outlined"`
- Max 3 visible; "+N more" chip if >3

**StatCards**: 5 cards in a `Grid container spacing={2}`:
- Each: `<StatCard label={...} value={...} unit={...} color={...} icon={...} />`
- Colors: emissions=primary, modules=success, tables=info, quality=warning, calculations=secondary

**WorkflowCards**: 2 rows × 3 columns `Grid`:
- Row 1 (all users): Dashboard, My Data, Reports
- Row 2 (admin only): Factors, Rules, Periods
- Each: `<WorkflowCard title={...} description={...} icon={...} color={...} onClick={...} adminOnly={...} />`

**ActivityFeed**: Pass `items={recentActivity}` prop. Auto-hides if empty.

### 3. ALWAYS use shared components — DO NOT create inline versions

Import from:
```javascript
import PageHeader from '../../components/Page/PageHeader';
import PeriodBanner from '../../components/Feedback/PeriodBanner';
import StatCard from '../../components/Cards/StatCard';
import WorkflowCard from '../../components/Cards/WorkflowCard';
import ActivityFeed from '../../components/Feedback/ActivityFeed';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../components/Page/ErrorAlert';
import EmptyState from '../../components/Page/EmptyState';
```

If any of these components don't exist yet, CREATE them in `src/components/` as specified in SHARED-CONTEXT.md section 3. Never define them inline in the page file.
- DQ alerts: `color="warning"`, `variant="outlined"`, clickable (for future drill-down)
- Pending: `color="info"`, `variant="outlined"`
- Max 3 visible; "+N more" if >3

**StatRow**: 5 `Paper` cards in a `Grid`:
- Each: `sx={{ p: 2, textAlign: 'center', border: '1px solid', borderColor: 'divider', borderRadius: 2 }}`
- Top: value (large `h4` weight 700, colored)
- Bottom: label (caption, text.secondary)
- Colors: emissions=primary, modules=success, tables=info, quality=warning, calculations=secondary
- Icons: 16px, next to label

**Workflow grid**: 2-row, 3-column `Grid`:
- Row 1 (all users): Dashboard, My Data, Reports
- Row 2 (admin only): Factors, Rules, Periods
- Cards: `sx={{ p: 2.5, cursor: 'pointer', border: '1px solid', borderColor: 'divider', borderRadius: 2 }}`
- Hover: `borderColor: 'primary.light'`, subtle shadow
- Content: icon (32px, colored), title (subtitle1, 600), description (caption, 2 lines max)
- `onClick` navigates to route

**ActivityFeed**: Only if `recent_activity.length > 0`.
- Title: "Recent Activity" (overline or subtitle2)
- List: compact vertical timeline
- Each item: `●` dot + timestamp (relative: "2h ago") + module name + detail
- Max 5 items
- Use MUI `Timeline` or simple `Stack` with `divider`

### 3. Extract components (for reuse in later phases)

Create these in `src/pages/carbon/components/`:
- `PeriodBanner.jsx` — reusable active-period banner
- `StatCard.jsx` — reusable stat display
- `ActivityFeed.jsx` — reusable activity timeline

### 4. Handle all states

| State | Component to use |
|---|---|
| Loading | `<LoadingSkeleton variant="card-grid" count={6} columns={3} />` |
| Error | `<ErrorAlert message="..." onRetry={loadData} />` |
| Empty (no period) | `<EmptyState icon={...} title="Welcome to Carbon" description="..." action={...} />` |
| No alerts | Hide alert row entirely |
| No activity | `<ActivityFeed>` auto-hides when empty |

## Scope — DO NOT

- DON'T change routing in App.jsx (route already exists at `/carbon/console`)
- DON'T change sidebar or manifest
- DON'T add new npm packages
- DON'T create .css files (use MUI sx prop)
- DON'T exceed 200 lines in CarbonConsolePage.jsx (components handle the complexity)
- DON'T define StatCard, WorkflowCard, PeriodBanner, ActivityFeed, PageHeader inline — import from `src/components/`
- DON'T hardcode colors — use `theme.palette.*`
- DON'T add animations longer than 200ms
- DON'T fetch from two endpoints — use the single `/console/` endpoint
- DON'T create ad-hoc tables or cards — use shared components ONLY

## Files to create/modify

| File | Action | Notes |
|---|---|---|
| `src/pages/carbon/CarbonConsolePage.jsx` | **Rewrite** | Use shared components ONLY |
| `src/api/emissions.js` | **Modify** | Add `fetchConsoleData()` |
| `src/components/Page/PageHeader.jsx` | **Create if missing** | Per SHARED-CONTEXT §3.4 |
| `src/components/Feedback/PeriodBanner.jsx` | **Create if missing** | Per SHARED-CONTEXT §3.8 |
| `src/components/Cards/StatCard.jsx` | **Create if missing** | Per SHARED-CONTEXT §3.2 |
| `src/components/Cards/WorkflowCard.jsx` | **Create if missing** | Per SHARED-CONTEXT §3.3 |
| `src/components/Feedback/ActivityFeed.jsx` | **Create if missing** | Per SHARED-CONTEXT §3.9 |
| `src/components/Page/LoadingSkeleton.jsx` | **Create if missing** | Per SHARED-CONTEXT §3.6 |
| `src/components/Page/ErrorAlert.jsx` | **Create if missing** | Per SHARED-CONTEXT §3.7 |
| `src/components/Page/EmptyState.jsx` | **Create if missing** | Per SHARED-CONTEXT §3.5 |

## Acceptance Criteria

- [ ] Page loads without errors (`npm run build` passes)
- [ ] Period banner shows active period with correct days remaining
- [ ] Stat row shows 5 StatCards with correct values
- [ ] Alert row shows only when alerts exist
- [ ] WorkflowCards navigate to correct routes
- [ ] Admin-only cards hidden for non-admin users
- [ ] ActivityFeed shows recent calculations, auto-hides if empty
- [ ] Loading state: LoadingSkeleton placeholders
- [ ] Error state: ErrorAlert with retry
- [ ] Empty state: EmptyState when no period configured
- [ ] Full fluid width (no max-width)
- [ ] ALL shared components created in `src/components/` and reusable
- [ ] Console page ≤ 200 lines (components handle the complexity)

## Deliverables

Paste results into: `/home/ahmed/aast/carbon/plans/carbon-phase/phase-01-console/TASK-RESULTS-FE-01.md`

Include:
1. List of files created/modified
2. Screenshot description of each state (loading, data, empty, error)
3. `npm run build` output (must pass)
4. Any issues or decisions made
