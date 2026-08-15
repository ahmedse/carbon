# Carbon "My Data" — Unified Page Architecture

## Current State Analysis

### Two Separate Pages, Two Separate Concerns

| Page | Route | What It Does | Problems |
|------|-------|-------------|----------|
| **DataHubHome** | `/carbon/data-entry` | Module browser — shows emission source modules (Scope 1/2/3) as cards, click to drill into tables | Generic "Data Hub" branding, no carbon context, no asset quality info, no submission status |
| **DataOwnerAssetsPage** | `/carbon/owner/assets` | Asset table — DataGrid of emission source assets with quality scores, domain filter, search | Read-only table, no data entry path, disconnected from the module→table→row workflow |

### The Disconnect

A data owner's workflow is:
1. See their emission sources (modules/assets)
2. Check data quality and submission status
3. Enter or update activity data
4. Review results

Currently this is split across two pages with no visual connection. The user must mentally map "modules" (DataHubHome) to "assets" (DataOwnerAssetsPage) — they're the same entities viewed differently.

### What the Data Trust Platform Provides

- **Modules**: Emission source categories (Electricity, Fuel, Travel, etc.) organized by Scope 1/2/3
- **Tables**: Data tables within each module (e.g., "Monthly Electricity Bills", "Generator Fuel Logs")
- **Rows**: Individual data records within tables
- **Assets**: Emission-generating entities scoped to org units with quality scores
- **Context**: `useAuth()` provides `context.modules`, `context.org_units`, `tablesByModule`
- **APIs**: `fetchOwnerAssets()`, `fetchOwnerSummary()`, `fetchOwnerActivity()`

---

## Unified Design: `MyDataPage.jsx`

### Concept

A single page at `/carbon/my-data` that merges the module browser AND asset overview into one cohesive experience. The page has two view modes toggled by tabs:

```
┌─────────────────────────────────────────────────────┐
│  My Data                                            │
│  Manage your emission sources and activity data     │
│                                                     │
│  [Data Entry]  [Emission Sources]                   │  ← Tab bar
│                                                     │
│  ┌─────────────────────────────────────────────┐    │
│  │  Quick Stats Row                            │    │
│  │  [Modules: 5] [Tables: 12] [Quality: 87%]   │    │
│  │  [Last Updated: 2h ago]                     │    │
│  └─────────────────────────────────────────────┘    │
│                                                     │
│  ┌─ Scope Filter Tabs ─────────────────────────┐    │
│  │ [All] [Scope 1 (2)] [Scope 2 (1)] [Scope 3 (2)]│  │
│  └─────────────────────────────────────────────┘    │
│                                                     │
│  ┌─ Search ────────────────────────────────────┐    │
│  │ 🔍 Search modules, tables, or assets...      │    │
│  └─────────────────────────────────────────────┘    │
│                                                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐            │
│  │ Module   │ │ Module   │ │ Module   │            │
│  │ Card     │ │ Card     │ │ Card     │            │
│  │          │ │          │ │          │            │
│  │ Scope 1  │ │ Scope 2  │ │ Scope 3  │            │
│  │ 3 tables │ │ 1 table  │ │ 2 tables │            │
│  │ Q: 92%   │ │ Q: 78%   │ │ Q: 85%   │            │
│  │ [Enter]  │ │ [Enter]  │ │ [Enter]  │            │
│  └──────────┘ └──────────┘ └──────────┘            │
└─────────────────────────────────────────────────────┘
```

### Tab 1: "Data Entry" (default)

The module browser — enhanced with asset quality context.

**Module Card** (reuses WorkflowCard pattern from CarbonConsolePage):
- Module name + scope icon + scope chip
- Description
- Table count with row count summary
- **NEW**: Data quality score badge (pulled from owner assets API)
- **NEW**: Last submission date
- **NEW**: Submission status indicator (complete/incomplete/overdue)
- "Enter Data" button → navigates to `/modules/:moduleId`

**Empty State**:
- If no modules assigned: illustration + "No emission sources assigned to your organizational unit"
- CTA: "Contact your administrator"

### Tab 2: "Emission Sources"

The asset overview — enhanced with data entry shortcuts.

**Asset Table** (reuses DataGrid from DataOwnerAssetsPage):
- Asset name (with linked data table/field)
- Domain chip
- Quality status badge (passing/warning/failing with score)
- Owner
- **NEW**: "Enter Data" action button → navigates directly to the table data entry
- **NEW**: Row count column
- **NEW**: Last updated column

**Filters**:
- Search (name, description, table, field)
- Domain dropdown
- Quality status filter (passing/warning/failing)
- Scope filter

---

## Component Architecture

```
MyDataPage.jsx
├── QuickStatsBar          (reused StatCard pattern from CarbonConsolePage)
├── ScopeFilterTabs        (reused from DataHubHome, extracted as shared)
├── SearchBar              (reused from DataOwnerAssetsPage)
├── DataEntryTab
│   ├── ModuleCard[]       (enhanced WorkflowCard variant)
│   │   ├── ScopeChip
│   │   ├── QualityBadge   (reused from DataOwnerAssetsPage)
│   │   └── SubmissionStatus
│   └── EmptyState
└── EmissionSourcesTab
    ├── FilterBar
    │   ├── SearchField
    │   ├── DomainSelect
    │   └── QualityFilter
    ├── DataGrid            (reused MUI DataGrid)
    │   ├── QualityStatusBadge (reused)
    │   └── ActionButton
    └── EmptyState
```

### Shared Components to Extract/Reuse

| Component | Source | Reused In |
|-----------|--------|-----------|
| `StatCard` | CarbonConsolePage.jsx:112-133 | QuickStatsBar |
| `WorkflowCard` | CarbonConsolePage.jsx:41-107 | ModuleCard (adapted) |
| `QualityStatusBadge` | DataOwnerAssetsPage.jsx:42-67 | Both tabs |
| `ScopeFilterTabs` | DataHubHome.jsx:95-145 | Extracted as shared |
| `SCOPE_COLORS` / `SCOPE_ICONS` | DataHubHome.jsx:9-19 | Shared constants |
| `DataGrid` | MUI x-data-grid | EmissionSourcesTab |

---

## Data Flow

```
MyDataPage
  │
  ├─ useAuth() → context.modules, context.org_units, tablesByModule, token
  │
  ├─ useEffect → fetchOwnerSummary(token) → stats (total_modules, total_tables, avg_quality)
  ├─ useEffect → fetchOwnerAssets({}, token) → assets[] with quality scores
  │
  ├─ useMemo → merge modules + assets by module_id
  │   │  module.enriched = {
  │   │    ...module,
  │   │    quality_score: asset.quality_score,
  │   │    quality_status: asset.quality_status,
  │   │    last_updated: asset.updated_at,
  │   │    row_count: sum of table row_counts
  │   │  }
  │
  ├─ DataEntryTab ← enriched modules (filtered by scope, search)
  └─ EmissionSourcesTab ← assets (filtered by domain, quality, search)
```

---

## Route Changes

| Old Route | New Route | Component |
|-----------|-----------|-----------|
| `/carbon/data-entry` | `/carbon/my-data` | `MyDataPage` (tab: data-entry) |
| `/carbon/owner/assets` | `/carbon/my-data?tab=sources` | `MyDataPage` (tab: sources) |
| `/carbon/owner/assets` | Redirect → `/carbon/my-data?tab=sources` | Legacy redirect |

---

## Navigation Updates

### manifest.js
```js
{ type: 'group', label: 'My Data' },
{ label: 'Data Entry',       path: '/carbon/my-data',              role: 'carbon:data_owner' },
{ label: 'Emission Sources', path: '/carbon/my-data?tab=sources',  role: 'carbon:data_owner' },
```

### ShellSidebar.jsx
```js
'Data Entry':       AddCircleOutlineIcon,
'Emission Sources': StorageIcon,
```

### SidebarMenu.jsx (DataOwnerSidebar)
```js
<MenuItem to="/carbon/my-data" icon={<DataEntryIcon />} label="Data Entry" />
<MenuItem to="/carbon/my-data?tab=sources" icon={<TableIcon />} label="Emission Sources" />
```

---

## UX Principles Applied

1. **Single source of truth**: One page, two views of the same data
2. **Progressive disclosure**: Overview stats → filtered modules → drill into tables
3. **Contextual actions**: "Enter Data" button on every module card and asset row
4. **Quality visibility**: Quality scores visible at every level (overview, module card, asset row)
5. **Consistent patterns**: Reuses StatCard, WorkflowCard, QualityBadge, ScopeFilterTabs from existing codebase
6. **Empty states**: Helpful messages with clear CTAs for every empty scenario
7. **Responsive**: Cards grid on desktop, list on mobile; DataGrid adapts

---

## Files to Create/Modify

### Create
1. `carbon-frontend/src/pages/carbon/MyDataPage.jsx` — New unified page (~400 lines)

### Modify
2. `carbon-frontend/src/App.jsx` — Add `/carbon/my-data` route, redirect old paths
3. `carbon-frontend/src/apps/carbon/manifest.js` — Update navigation paths
4. `carbon-frontend/src/shell/ShellSidebar.jsx` — Update icon mappings
5. `carbon-frontend/src/components/SidebarMenu.jsx` — Update DataOwnerSidebar

### Keep (unchanged)
- `DataHubHome.jsx` — Still used by `/dataschema` and `/carbon/data-entry` (legacy)
- `DataOwnerAssetsPage.jsx` — Still used by `/carbon/owner/assets` (legacy redirect)
- `ModuleLandingPage.jsx` — Still used for drill-down from module cards
- `DataEntryPage.jsx` — Still used for table-level data entry
