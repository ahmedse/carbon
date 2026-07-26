# TASK-FE-00 — Shared Component Library Foundation

> **Priority**: ⚠️ BLOCKING — Must complete before any other FE phase
> **Estimated effort**: 4-6 hours
> **Worker**: Frontend Engineer (DeepSeek Flash)
> **Before starting**: Read `plans/carbon-phase/SHARED-CONTEXT.md` fully. Re-read every DO/DON'T in `plans/carbon-phase/PROTOCOL.md`.

---

## Why this phase exists

Every page in the Carbon platform would otherwise re-implement the same tables, cards, headers, and empty states. Instead, we build 12 reusable components ONCE. All subsequent FE tasks MUST import from this library. No page creates inline cards or ad-hoc data tables.

---

## Architecture

```
carbon-frontend/src/
  components/
    DataGrid/
      CarbonDataGrid.jsx       ← THE one and only data table
    Cards/
      StatCard.jsx             ← Metric card with optional sparkline
      WorkflowCard.jsx         ← Navigation/CTA card
    Page/
      PageHeader.jsx           ← Title + subtitle + breadcrumb + actions
      EmptyState.jsx           ← Icon + title + description + CTA
      LoadingSkeleton.jsx      ← Skeleton matching page layout
      ErrorAlert.jsx           ← Alert with retry button
    Layout/
      TabPanel.jsx             ← Tab content wrapper
      RightPanel.jsx           ← Collapsible entity metadata sidebar
    Feedback/
      PeriodBanner.jsx         ← Active reporting period status bar
      ActivityFeed.jsx         ← Compact timeline of events
    Form/
      SaveBar.jsx              ← Bottom-pinned Cancel + Save
      FormField.jsx            ← Standard field wrapper (label above, size=small)
```

---

## Component Specifications

### 1. CarbonDataGrid.jsx — `src/components/DataGrid/CarbonDataGrid.jsx`

The **ONLY** table component used anywhere in Carbon. All pages import this.

```jsx
<CarbonDataGrid
  columns={columns}           // Array of { field, headerName, width, type?, renderCell? }
  rows={rows}                 // Array of data objects
  loading={false}             // Show skeleton
  getRowId={(row) => row.id}  // Default: 'id'
  checkboxSelection={false}   // Show checkboxes
  onSelectionChange={fn}      // Callback for selection
  pageSize={25}               // Default 25
  pageSizeOptions={[10, 25, 50, 100]}
  stickyHeader={true}
  density="compact"           // Always compact (24px rows)
  height="auto"               // Or number for fixed height
  emptyMessage="No data found"
  onRowClick={fn}             // Optional: navigate on click
  highlightRow={(row) => row.status === 'pending'}  // Conditional highlighting
  showColumnToggle={true}     // Enable column show/hide
/>
```

**Rules**:
- Uses MUI DataGrid `density="compact"`, `size="small"`
- Row height: 24px
- Column header: 12px font, weight 600, uppercase
- Cell: 13px font, body2 variant
- Striped rows: alternate grey-50/grey-100 in light, zinc-900/zinc-800 in dark
- Actions column: always last, right-aligned, icon buttons only
- No inline editing (that's a separate form/modal concern)
- Empty state: shows emptyMessage string centered

### 2. StatCard.jsx — `src/components/Cards/StatCard.jsx`

```jsx
<StatCard
  title="Total Emissions"
  value={2669.9}
  unit="tCO₂e"
  icon={<CloudIcon />}       // MUI icon component
  color="primary"             // primary | success | warning | error | info
  sparkline={[12, 34, 23, 45, 56]}  // Optional: 5 data points
  trend={+12.5}               // Optional: percentage change
  trendLabel="vs last period"
  loading={false}
  onClick={fn}                // Optional: make clickable to navigate
/>
```

**Rules**:
- `border: 1px solid divider`, `borderRadius: 2` (8px), `p: 2` (16px)
- No shadow (boxShadow: 1 only for interactive overlays)
- Icon: 32px, color mapped from `color` prop
- Value: h4 (24px), weight 700
- Unit: body2, grey-500, after value
- Sparkline: 80px wide, 24px tall, using a tiny SVG line chart (no external chart lib)
- Trend: green if positive and color=success, red if negative and color=error, otherwise neutral
- Hover: bg shifts 50 (grey-50 → grey-100 or zinc-900 → zinc-800)

### 3. WorkflowCard.jsx — `src/components/Cards/WorkflowCard.jsx`

```jsx
<WorkflowCard
  icon={<DashboardIcon />}
  title="Dashboard"
  description="View emissions trends and analytics"
  onClick={() => navigate('/dashboard')}
  disabled={false}
/>
```

**Rules**:
- Same visual style as StatCard (border, radius, padding)
- Icon: 48px, primary color, centered at top
- Title: h6, 16px, text center
- Description: body2, grey-600, text center, 2 lines max
- `disabled`: opacity 0.5, no pointer events
- Grid layout: 3 per row on desktop, 2 on tablet, 1 on mobile

### 4. PageHeader.jsx — `src/components/Page/PageHeader.jsx`

```jsx
<PageHeader
  title="Carbon Console"
  subtitle="FY 2026 — July"
  breadcrumbs={[
    { label: 'Home', path: '/' },
    { label: 'Carbon', path: '/carbon' },
    { label: 'Console' }
  ]}
  badge={{ label: 'Admin', color: 'primary' }}
  actions={
    <Button size="small" variant="outlined">Export</Button>
  }
/>
```

**Rules**:
- Breadcrumbs: 12px, grey-600, with chevron separators
- Title: h4 (20px), weight 600, `mb: 0.5`
- Subtitle: body2, grey-500
- Badge: MUI Chip, `size="small"`, `variant="outlined"`, right of title
- Actions: right-aligned in same row
- Bottom border: `borderBottom: 1px solid divider`, `pb: 2`, `mb: 3`

### 5. EmptyState.jsx — `src/components/Page/EmptyState.jsx`

```jsx
<EmptyState
  icon={<InboxIcon />}
  title="No data yet"
  description="Start by entering your first emissions data"
  actionLabel="Go to Data Entry"
  onAction={() => navigate('/my-data')}
/>
```

**Rules**:
- Icon: 64px, grey-400
- Title: h6
- Description: body2, grey-500
- CTA: MUI Button, `variant="outlined"`, `size="small"`
- Centered in parent, `py: 8` (64px)

### 6. LoadingSkeleton.jsx — `src/components/Page/LoadingSkeleton.jsx`

```jsx
<LoadingSkeleton variant="console" />   // Page-specific variants
<LoadingSkeleton variant="table" />
<LoadingSkeleton variant="detail" />
<LoadingSkeleton variant="card" />
```

**Rules**:
- Each variant renders Skeletons in the exact shape of the loaded page
- `variant="console"`: header skeleton + 5 stat card skeletons + 6 workflow card skeletons
- `variant="table"`: header + 10-row skeleton grid
- `variant="detail"`: header + 2-column skeleton with right panel skeleton
- `variant="card"`: single card skeleton (used inside other components)
- Use MUI `<Skeleton variant="rounded">` with matching heights

### 7. ErrorAlert.jsx — `src/components/Page/ErrorAlert.jsx`

```jsx
<ErrorAlert
  message="Failed to load console data"
  onRetry={() => refetch()}
/>
```

**Rules**:
- MUI `<Alert severity="error">` with icon
- Retry button: `variant="outlined"`, `size="small"`, `color="error"`
- Positioned at top of affected content area
- Never use toast/snackbar for errors

### 8. TabPanel.jsx — `src/components/Layout/TabPanel.jsx`

```jsx
<TabPanel value={tabValue} index={0}>
  <CarbonDataGrid ... />
</TabPanel>
```

**Rules**:
- Simple wrapper: renders children when `value === index`
- `pt: 2` (16px top padding for tab content spacing)

### 9. RightPanel.jsx — `src/components/Layout/RightPanel.jsx`

```jsx
<RightPanel
  open={panelOpen}
  onClose={() => setPanelOpen(false)}
  title="Metadata"
  width={320}                // Default 320px, resizable
>
  {/* Metadata content */}
  <MetadataSection title="Details">
    <MetadataItem label="Created" value="2026-07-25" />
    <MetadataItem label="Status" value="Draft" />
  </MetadataSection>
  <MetadataSection title="History">
    <ActivityFeed items={history} />
  </MetadataSection>
</RightPanel>
```

**Rules**:
- MUI Drawer, `anchor="right"`, `variant="persistent"` or `variant="temporary"` (responsive)
- Resizable via drag handle on left edge (3px wide, grey-300)
- Width range: 280px → 480px
- Header: close button (X) + title
- Content: scrollable
- Transition: slide in/out, 200ms
- On mobile (<768px): overlay mode, full width
- Also export `MetadataSection` and `MetadataItem` as named exports

### 10. PeriodBanner.jsx — `src/components/Feedback/PeriodBanner.jsx`

```jsx
<PeriodBanner
  name="FY 2026"
  startDate="2026-01-01"
  endDate="2026-12-31"
  status="open"              // open | closing | closed
  daysRemaining={159}
  onAction={() => navigate('/periods')}
/>
```

**Rules**:
- Status colors: open=success (green), closing=warning (amber), closed=default (grey)
- Shows: period name | date range | status chip | "X days remaining" badge
- Compact single row: `mb: 2`, `p: 2`, same border/card style
- Action: optional "View details" link on right

### 11. ActivityFeed.jsx — `src/components/Feedback/ActivityFeed.jsx`

```jsx
<ActivityFeed
  items={activity}
  maxItems={10}
  emptyMessage="No recent activity"
  loading={false}
/>

// items structure:
[
  {
    id: 1,
    action: "calculation",     // calculation | submission | verification | dq_alert
    module: "Electricity S2",
    timestamp: "2026-07-25T10:30:00Z",
    detail: "12 rows calculated",
    user: "Ahmed"              // Optional
  }
]
```

**Rules**:
- Compact timeline: icon + text, no lines between items
- Icons per action type: calculation=calculator, submission=upload, verification=shield, dq_alert=warning
- Font: 13px, grey-700 for text, grey-500 for timestamp
- Max height: `maxHeight: 400px`, `overflow: 'auto'`
- Empty: shows `emptyMessage` (grey-500, italic)
- Loading: 5 skeleton rows

### 12. SaveBar.jsx — `src/components/Form/SaveBar.jsx`

```jsx
<SaveBar
  onSave={handleSave}
  onCancel={handleCancel}
  saving={false}
  saveLabel="Save Changes"
  dirty={true}                // Only show if form is dirty
/>
```

**Rules**:
- Pinned to bottom: `position: 'sticky'`, `bottom: 0`, `zIndex: 10`
- Background: `background.paper` with top border
- Layout: Cancel button (left) | space | Save button (right, contained, primary)
- Hidden when `!dirty`
- Cancel: outlined, grey
- Save: contained, primary, disabled during `saving`
- `p: 2` (16px padding)

### 13. FormField.jsx — `src/components/Form/FormField.jsx`

```jsx
<FormField
  label="Period Name"
  required={true}
  helperText="Use fiscal year format (e.g. FY 2026)"
  error="Name is required"   // Optional error message
>
  <TextField size="small" fullWidth />
</FormField>
```

**Rules**:
- Label above input (not beside), 13px, weight 500
- Required: red asterisk after label
- Helper text: 12px, grey-500, below input
- Error: 12px, error color
- Gap: `mb: 2` (16px between fields)

---

## DO (Always)

- ✅ Export each component as default export from its directory
- ✅ Use MUI `sx` prop only (no inline `style={}`)
- ✅ Support light + dark theme (use `theme.palette.mode`)
- ✅ All components must be `React.memo` wrapped
- ✅ All components must have PropTypes or JSDoc types
- ✅ Use `useTheme()` for theme-aware styling
- ✅ Responsive: all components must handle mobile (<768px)
- ✅ Index barrel file: `src/components/index.js` re-exports all
- ✅ Each component in its own directory with `index.js` re-export
- ✅ Test each component renders without error (`npm run build` passes)

## DON'T (Never)

- ❌ No `style={{}}` — only MUI `sx`
- ❌ No hardcoded colors (use `theme.palette.*`)
- ❌ No `console.log` in production code
- ❌ No components larger than 150 lines
- ❌ No external CSS files (MUI theme + sx only)
- ❌ No ad-hoc table or card components in pages
- ❌ No shadow on cards (boxShadow: 1 only)
- ❌ No animations longer than 200ms
- ❌ No hero sections or gradient backgrounds
- ❌ No Google Fonts or custom fonts

---

## Files to Create

| # | File | Purpose |
|---|---|---|
| 1 | `src/components/DataGrid/CarbonDataGrid.jsx` | Standardized data table |
| 2 | `src/components/Cards/StatCard.jsx` | Metric card with sparkline |
| 3 | `src/components/Cards/WorkflowCard.jsx` | Navigation/CTA card |
| 4 | `src/components/Page/PageHeader.jsx` | Page title + breadcrumb + actions |
| 5 | `src/components/Page/EmptyState.jsx` | Empty state with icon + CTA |
| 6 | `src/components/Page/LoadingSkeleton.jsx` | Multi-variant skeleton |
| 7 | `src/components/Page/ErrorAlert.jsx` | Error alert with retry |
| 8 | `src/components/Layout/TabPanel.jsx` | Tab content wrapper |
| 9 | `src/components/Layout/RightPanel.jsx` | Collapsible metadata sidebar |
| 10 | `src/components/Feedback/PeriodBanner.jsx` | Active period status bar |
| 11 | `src/components/Feedback/ActivityFeed.jsx` | Compact timeline |
| 12 | `src/components/Form/SaveBar.jsx` | Bottom-pinned save bar |
| 13 | `src/components/Form/FormField.jsx` | Standard form field wrapper |
| 14 | `src/components/index.js` | Barrel re-exports |

---

## Acceptance Criteria

- [ ] All 13 components created in correct directories
- [ ] `src/components/index.js` re-exports all components
- [ ] `npm run build` passes with zero errors
- [ ] Each component supports light + dark theme
- [ ] Each component is under 150 lines
- [ ] No inline `style={}` anywhere — only `sx`
- [ ] No hardcoded colors — all from `theme.palette`
- [ ] Components are `React.memo` wrapped
- [ ] PropTypes defined on all components
- [ ] No `console.log` in any file

---

## How to verify

1. `cd carbon-frontend && npm run build`
2. Check all files exist: `ls src/components/*/`
3. Check no `style={{` anywhere: `grep -r "style={{" src/components/` (should be empty)
4. Check no hardcoded colors: `grep -rE "'#[0-9a-fA-F]{3,6}'" src/components/` (should be empty)

---

## Deliverables

- TASK-RESULTS-FE-00.md filled with:
  - All 13 file paths created
  - Build output (npm run build)
  - grep verification output
  - Screenshot of any component rendered (optional)
  - Notes on any deviations from spec
