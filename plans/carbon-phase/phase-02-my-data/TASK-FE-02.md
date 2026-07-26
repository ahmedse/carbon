# TASK-FE-02: My Data Page — Shared Component Refactor

## Context (from master)
Phase 02 — "My Data" is the Data Owner's workspace. A `MyDataPage.jsx` already exists at `src/pages/carbon/MyDataPage.jsx` (~320 lines), but it was built BEFORE the shared component library existed. It imports from `carbonDesign.jsx` (old theme tokens), has inline components (`QualityBadge`, `ModuleCard`), uses raw MUI `CircularProgress`/`Alert` instead of `LoadingSkeleton`/`ErrorAlert`, and uses MUI `DataGrid` directly instead of `CarbonDataGrid`.

**This is the EXACT same problem as FE-01: local components instead of shared library.**

## Before starting
- Read `plans/carbon-phase/SHARED-CONTEXT.md`
- Read `MASTER-WORKER-PROTOCOL.md` DO/DON'T sections
- Study how `CarbonConsolePage.jsx` (143 lines) was fixed — use the same pattern
- Look at ALL components in `src/components/` — understand what each does
- Read the BE-02 API contract: the page calls `GET /api/v1/emissions/my-data/` which returns `{ org_unit, stats, modules[], recent_activity[] }`

## Scope — DO
1. **Rewrite** `src/pages/carbon/MyDataPage.jsx` — target ≤ 200 lines
2. Use ONLY shared components from `src/components/`:
   - `PageWrapper`, `PageHeader` from `src/components/Page/`
   - `StatCard` from `src/components/Cards/`
   - `CarbonDataGrid` from `src/components/DataGrid/`
   - `LoadingSkeleton` from `src/components/Page/` (variant="table")
   - `ErrorAlert` from `src/components/Page/`
   - `EmptyState` from `src/components/Page/`
   - `TabPanel` from `src/components/Layout/`
3. Use `fetchMyData()` (coming from BE-02) — single API call
4. Handle all 4 states: **loading**, **error**, **empty** (no org unit), **data** (org unit + modules)
5. Show: org unit header → 4 stat cards → module cards grid → recent activity
6. Module cards: show name, scope badge, row count, quality status, "Enter Data" button
7. Use `useAuth()` for user/role
8. Use MUI `sx` prop only — no inline `style={{}}`

## Scope — DO NOT
- Do NOT import from `carbonDesign.jsx` (old theme tokens)
- Do NOT create inline components (QualityBadge, ModuleCard, etc.) — use shared cards
- Do NOT use `@mui/x-data-grid` DataGrid directly — use `CarbonDataGrid`
- Do NOT use `CircularProgress` or `Alert` directly — use `LoadingSkeleton`/`ErrorAlert`
- Do NOT use `NotificationProvider` for errors
- Do NOT add new npm dependencies
- Do NOT build the data entry form — that's a separate task
- Do NOT build bulk CSV import — that's a separate task
- Do NOT touch `DataEntryPage.jsx`

## Page Contract

| Route | Component | States |
|---|---|---|
| `/carbon/my-data` | MyDataPage | loading, error, empty (no org unit), data |

### States

**Loading**: `<LoadingSkeleton variant="table" />` — shows header + 4 stat + grid skeletons

**Error**: `<PageHeader>` + `<ErrorAlert message={...} onRetry={load} />`

**Empty (no org unit)**: `<PageHeader>` + `<EmptyState icon={<OrgIcon/>} title="No Organizational Unit" description="...">`

**Data (normal)**:
```
<PageHeader title="My Data" subtitle="..." />
<!-- Org unit context -->
<Paper sx={{ p: 2, mb: 2 }}>OrgUnit: {org_unit.name} ({org_unit.code})</Paper>
<!-- 4 Stat cards -->
<Grid container spacing={2}>
  <StatCard title="Emission Sources" value={stats.total_modules} icon={<StorageIcon/>} color="primary" />
  <StatCard title="With Data" value={stats.modules_with_data} icon={<DataIcon/>} color="success" />
  <StatCard title="Total Rows" value={stats.total_rows} icon={<TableIcon/>} color="info" />
  <StatCard title="DQ Score" value={...} icon={<QualityIcon/>} color="warning" unit="%" />
</Grid>
<!-- Module cards -->
<SectionHeader label="Emission Sources" />
<Grid container spacing={2}>
  {modules.map(m => (
    <Grid item xs={12} sm={6} md={4}>
      <WorkflowCard icon={<ScopeIcon/>} title={m.name} description={m.row_count + " rows"}
        badge={scope_badge} onClick={() => navigate(...)} />
    </Grid>
  ))}
</Grid>
<!-- Recent activity -->
<ActivityFeed items={mappedActivity} maxItems={10} />
```

### Scope badge colors
- Scope 1 → `error` (red)
- Scope 2 → `warning` (orange)  
- Scope 3 → `info` (blue)

### Module card → data entry navigation
Clicking a module card navigates to: `/carbon/data-entry/entry/${module.name}/${module.table_id}`
(Use the first table_id from `module.table_count > 0`)

## Acceptance Criteria
- [ ] `npm run build` passes
- [ ] All 4 states handled (loading, error, empty, data)
- [ ] ALL shared components used (zero imports from carbonDesign.jsx)
- [ ] Zero inline components
- [ ] Page ≤ 200 lines
- [ ] Mobile responsive (xs breakpoints)
- [ ] Light + dark theme compatible
- [ ] Module cards navigate to data entry
- [ ] Scope badges use correct MUI palette colors
