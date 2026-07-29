# Design: Row Detail Page + Right-Side Metrics Panel (Refined)

**Status**: Refined Architectural Design  
**Date**: 2026-07-19  
**Priority**: High (UX Enhancement)  
**Complexity**: Medium-High (7-8 hours estimated)

---

## Executive Summary

**Three-part layout** for row detail page:

1. **Main Content Panel** (Left/Center): Row details with tabs
   - Overview, Edit, Evidence tabs (now)
   - History, Comments tabs (future)

2. **Right-Side Metrics Panel** (New): Resizable info panels
   - **DQ Metrics Tab**: Data quality results for this row
   - **Data Lineage Tab**: Source/upstream data & transformations
   - **Related Records Tab**: Parent/child relationships
   - **Audit History Tab**: Change log (when approved)

3. **Grid Enhancements**: View icon + Evidence badge

**Key Principle**: "Whenever a detail of any entity opens, show a multitab side panel"

---

## Refined Architecture

### Layout Structure

```
┌─────────────────────────────────────────────────────────────────────┐
│ HEADER (Breadcrumbs, Title, Close Button)                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  MAIN CONTENT                │ │ METRICS PANEL (Resizable)          │
│  ─────────────────────       │ │ ─────────────────────────          │
│                              │ │                                    │
│  Tabs:                       │ │ [DQ Metrics]│[Lineage]│[Related]   │
│  ├─ Overview                 │ │ ┌──────────────────────────┐      │
│  ├─ Edit                     │ │ │                          │      │
│  ├─ Evidence                 │ │ │  DQ Results:             │      │
│  └─ [Future]                 │ │ │  ✓ Passed (3/3 checks)   │      │
│                              │ │ │                          │      │
│  [Content renders here]      │ │ │  • Range: 0-1000 ✓       │      │
│                              │ │ │  • Format: Valid ✓       │      │
│  [Save] [Delete] [▼]         │ │ │  • Unique: No dup ✓      │      │
│                              │ │ │                          │      │
│                              │ │ │  Last Run: 10:15         │      │
│                              │ │ │  Status: ✓ Verified      │      │
│                              │ │ │                          │      │
│                              │ │ └──────────────────────────┘      │
│                              │ │                                    │
│                              │ │  [Collapse ⟨]                    │
│                              │ │                                    │
└──────────────────────────────┴─┴────────────────────────────────────┘
                                  ↑
                        Resizable divider
                        (min width: 250px)
                        (max width: 50% of viewport)
```

### Refined Tab Structure

#### Main Content (Left/Center)

**Current Tabs** (5 hours):
- **Overview Tab**: Read-only row display
- **Edit Tab**: Full row form editor
- **Evidence Tab**: File upload + viewer

**Future Tabs** (roadmap):
- **Comments Tab**: Row-level discussion thread
- **Validation Details Tab**: Extended DQ info

#### Metrics Panel (Right, Resizable)

**Initial Tabs** (2-3 hours, can be phased):

1. **DQ Metrics Tab** ⭐ (Priority)
   - Overall status badge (Passed/Failed/Warning)
   - Individual rule results
   - Timestamp of last validation run
   - Quick re-run button
   - Links to rule definitions

2. **Data Lineage Tab** (Phase 2)
   - Upstream data sources
   - Transformation history
   - Related datasets
   - Dependency graph (text or visual)

3. **Related Records Tab** (Phase 2)
   - Parent records
   - Child records
   - Cross-references
   - One-click navigation

---

## Component Hierarchy

```
RowDetailPage.jsx [MODIFIED]
├── RowDetailHeader.jsx
│   ├── Breadcrumbs
│   ├── Title
│   └── Close button
│
├── RowDetailLayout.jsx [NEW]
│   │
│   ├── RowDetailMainPanel.jsx [NEW]
│   │   ├── RowDetailTabs.jsx (Tab switcher)
│   │   │   ├── RowOverviewTab.jsx
│   │   │   ├── RowEditTab.jsx
│   │   │   ├── RowEvidenceTab.jsx
│   │   │   └── [Future tabs]
│   │   │
│   │   └── RowDetailActions.jsx (buttons)
│   │
│   ├── ResizableDivider.jsx [NEW]
│   │   └── Draggable divider with min/max constraints
│   │
│   └── RowMetricsPanel.jsx [NEW]
│       ├── RowMetricsTabs.jsx (Tab switcher)
│       │   ├── DQMetricsTab.jsx [NEW]
│       │   ├── DataLineageTab.jsx [NEW] (Future)
│       │   ├── RelatedRecordsTab.jsx [NEW] (Future)
│       │   └── AuditHistoryTab.jsx [NEW] (Future)
│       │
│       ├── MetricsRefreshButton.jsx
│       └── MetricsLoadingState.jsx
```

---

## Data Flow & State Management

### State in RowDetailPage

```javascript
const [mainTabIndex, setMainTabIndex] = useState(0);        // Active main tab
const [metricsTabIndex, setMetricsTabIndex] = useState(0);  // Active metrics tab
const [panelWidth, setPanelWidth] = useState(350);          // Metrics panel width (px)
const [rowData, setRowData] = useState(null);               // Row data
const [dqMetrics, setDQMetrics] = useState(null);           // DQ results
const [lineageData, setLineageData] = useState(null);       // Data lineage
const [relatedRecords, setRelatedRecords] = useState(null); // Related records
const [loading, setLoading] = useState(true);               // Overall loading
const [metricsLoading, setMetricsLoading] = useState(false);// Metrics loading
```

### Loading Order

```
1. Mount RowDetailPage
   ↓
2. Fetch row data in parallel:
   - GET /api/rows/{rowId}/
   - GET /api/dq-metrics/?row_id={rowId} (for metrics panel)
   ↓
3. Render main content + metrics panel
   ↓
4. User switches to different metric tab
   ↓
5. Lazy-load lineage/related data on demand
   - GET /api/data-lineage/?row_id={rowId}
   - GET /api/related-records/?row_id={rowId}
```

---

## Detailed Tab Specifications

### Main Content Tabs

#### Overview Tab (Read-Only)
```
Row ID: 123
Building: 401
Water (m³): 404
Status: Verified

Last Modified: 2026-07-19 10:15 by Ahmed
Created: 2026-07-15 14:30 by Admin

[Edit] [Delete] [Download] [More ▼]
```

#### Edit Tab
```
Building _____________________ [B401]
Water (m³) ___________________ [404] [↻]
Status [Verified ▼]
Notes ______________________________
      ______________________________

[Save Changes] [Cancel] [Reset]
```

#### Evidence Tab
```
Drag & drop files here or click to browse
(PDF, Images, Excel, CSV, Word - Max 50MB)

─────────────────────────────────────

Attached Files (3):
📄 Invoice_2026-07-15.pdf (2.3 MB) [⬇️] [🗑️]
📷 Water_meter_photo.jpg (1.8 MB) [⬇️] [🗑️]
📊 Sensor_reading.xlsx (156 KB) [⬇️] [🗑️]
```

### Metrics Panel Tabs

#### DQ Metrics Tab ⭐
```
STATUS: ✓ PASSED
       (3 of 3 checks passed)

RULES:
✓ Range Check: 0 < Water ≤ 1000
✓ Format Check: Valid date
✓ Uniqueness: No duplicates

Last Run: 2026-07-19 10:15
By: Auto Scheduler

[Re-run Validation] [View Rules]
```

#### Data Lineage Tab (Future)
```
SOURCE DATA:
├─ Water Sensor #14
│  └─ Last reading: 10:05
│  └─ Status: Active
│
└─ Manual Override Log
   └─ No overrides

TRANSFORMATIONS:
├─ Unit Conversion (m³)
├─ Daily Aggregation
└─ Quality Check

DOWNSTREAM:
├─ Monthly Report (B401)
└─ Dashboard Widget
```

#### Related Records Tab (Future)
```
PARENT RECORDS:
• Building 401 (Monthly Summary)
  └─ Water Total: 12,845 m³

CHILD RECORDS:
(No sub-records)

CROSS-REFERENCES:
• Linked to Emissions Calc #456
• Referenced in Report #789
```

---

## Resizable Divider Implementation

### Constraints

```javascript
const MIN_PANEL_WIDTH = 250;  // Minimum metrics panel width
const MAX_PANEL_WIDTH = 0.5;  // Maximum 50% of viewport

const handleDividerDrag = (e) => {
  const newWidth = window.innerWidth - e.clientX;
  
  if (newWidth >= MIN_PANEL_WIDTH && newWidth <= MAX_PANEL_WIDTH * window.innerWidth) {
    setPanelWidth(newWidth);
  }
};
```

### Mouse Events

```
1. User positions cursor on divider
   └─ Cursor changes to resize-x (↔️)

2. User clicks and drags right/left
   └─ Panel resizes smoothly (with min/max constraints)

3. User releases mouse
   └─ Panel width persists in localStorage for next session

4. Double-click on divider
   └─ Reset to default width (350px)
```

---

## API Endpoints (Required)

### Already Exist
- `GET /api/rows/{rowId}/` - Row data
- `GET /api/evidence/?data_row={rowId}` - Evidence files
- `PATCH /api/rows/{rowId}/` - Update row
- `DELETE /api/rows/{rowId}/` - Delete row

### Need to Implement (A10 Phase 2+)
- `GET /api/dq-metrics/?row_id={rowId}` - DQ results for specific row
- `GET /api/data-lineage/?row_id={rowId}` - Data source tracking
- `GET /api/related-records/?row_id={rowId}` - Parent/child/cross-refs
- `POST /api/dq-validation/run-row/` - Trigger validation for specific row

---

## Implementation Timeline

### Phase 1: Core Detail Page (2 hours)
- [ ] Create RowDetailPage + RowDetailLayout
- [ ] Main content tabs (Overview, Edit, Evidence)
- [ ] Basic routing

### Phase 2: Metrics Panel - DQ Tab (2 hours)
- [ ] Create RowMetricsPanel + ResizableDivider
- [ ] Implement DQMetricsTab
- [ ] Connect to DQ metrics API (A10 Phase 2)
- [ ] Add re-run button

### Phase 3: Metrics Panel - Additional Tabs (2-3 hours) [Future]
- [ ] DataLineageTab
- [ ] RelatedRecordsTab
- [ ] AuditHistoryTab
- [ ] Lazy-load on tab switch

### Phase 4: Grid UI Updates (1 hour)
- [ ] Add View icon
- [ ] Add Evidence badge
- [ ] Navigate to detail page

### Phase 5: Polish & Testing (1-2 hours)
- [ ] Mobile responsiveness
- [ ] Accessibility (keyboard nav, focus)
- [ ] Error handling
- [ ] Loading states

---

## Layout Variants

### Desktop (Full Width)
```
┌──────────────────────────────────────────────────────────────────┐
│ Header (Breadcrumbs, Title, Close)                               │
├────────────────────────────────┬────────────────────────────────┤
│                                │                                │
│ MAIN (65%)                     │ METRICS (35%)                 │
│                                │                                │
│ Tabs | Content              │ │ Tabs | Content                 │
│                                │                                │
└────────────────────────────────┴────────────────────────────────┘
```

### Tablet (Breakpoint: 1024px)
```
┌──────────────────────────────────────┐
│ Header                               │
├──────────────────────────────────────┤
│                                      │
│ MAIN (100%)                          │
│                                      │
│ [Tabs] | [Metrics ≡] (Collapsed)    │
│                                      │
└──────────────────────────────────────┘

Metrics available via collapsible drawer/modal
```

### Mobile (Breakpoint: 768px)
```
┌────────────────────┐
│ Header             │
├────────────────────┤
│                    │
│ MAIN (Full Width)  │
│ - Tabs             │
│ - Content          │
│                    │
│ [Show Metrics ▼]   │
│                    │
└────────────────────┘

Metrics shown as full-width modal or drawer
```

---

## Grid UI Changes

### Before
```
Row ID │ Building │ Water │ Actions
─────────────────────────────────────
123    │ B401     │ 404   │ [Edit] [Delete] [Evidence] [☐]
```

### After
```
Row ID │ Building │ Water │ Evidence │ Actions
─────────────────────────────────────────────────────
123    │ B401     │ 404   │ 📎 3     │ [👁️ View] [🗑️] [☐]
```

**Grid Changes:**
1. Add "Evidence" column with badge
   - Empty = no files
   - ✓ = 1 file
   - 📎 3 = 3 files (etc.)

2. Change row actions to minimal
   - 👁️ View icon → opens detail page
   - 🗑️ Delete icon → shows confirmation

3. All other operations move to detail page

---

## State Persistence

### localStorage Keys
```javascript
'carbonRowDetail:panelWidth'      // Metrics panel width
'carbonRowDetail:mainTab'         // Last active main tab
'carbonRowDetail:metricsTab'      // Last active metrics tab
'carbonRowDetail:darkMode'        // User theme preference
```

### Session Storage
```javascript
sessionStorage['rowDetail:edits']  // Unsaved edits (prevent loss)
```

---

## Future Enhancements (Roadmap)

### Phase 2+ (Not in scope for A11)
- [ ] Data lineage visualization
- [ ] Related records navigation
- [ ] Audit history timeline
- [ ] Comments thread
- [ ] Validation workflow state
- [ ] File version history
- [ ] Change diff viewer
- [ ] Bulk row operations from detail page
- [ ] Print/export row details
- [ ] Share row URL
- [ ] Keyboard shortcuts (e, d, s = Edit, Delete, Save)

---

## Testing Checklist

### Navigation
- [ ] View icon opens detail page
- [ ] Breadcrumb navigation works
- [ ] Close button returns to list
- [ ] URL contains row ID
- [ ] Back button works in browser

### Main Content
- [ ] Overview tab displays row data
- [ ] Edit tab loads with values
- [ ] Evidence tab shows files
- [ ] Tab switching works
- [ ] Unsaved edits prevention

### Metrics Panel
- [ ] Panel displays on right side
- [ ] Resizable (drag divider)
- [ ] Min/max width constraints
- [ ] DQ metrics load correctly
- [ ] Metrics tab switching works
- [ ] Re-run button works
- [ ] Panel width persists (localStorage)

### Grid Integration
- [ ] View icon visible on all rows
- [ ] Evidence badge shows correctly
- [ ] Click View icon → detail page
- [ ] Delete confirmation works

### Responsive
- [ ] Desktop: 2-column layout
- [ ] Tablet (1024px): Collapsible metrics
- [ ] Mobile (768px): Full-width with drawer

### Performance
- [ ] Detail page loads < 2s
- [ ] Metrics load < 1s
- [ ] Lazy-load lineage/related data
- [ ] No unnecessary re-renders

---

## Comparison with Previous Design

| Feature | Old (Modals) | New (Detail Page) | Refined (w/ Metrics) |
|---------|---|---|---|
| Main Operations | Modal | Tabbed page | Tabbed page |
| Evidence Mgmt | Separate modal | Tab in page | Tab in page |
| DQ Metrics | Dashboard only | Future tab | Right panel |
| Data Lineage | Not visible | Future | Right panel |
| Related Records | Not visible | Future | Right panel |
| Screen Space | Limited | Full viewport | 65% + 35% panel |
| Mobile UX | Poor | Good | Drawer-based |
| Extensibility | Medium | High | Very high |

---

## File Structure

```
carbon-frontend/src/
├── pages/
│   └── RowDetailPage.jsx [NEW]
│
├── components/
│   ├── row-detail/
│   │   ├── RowDetailHeader.jsx [NEW]
│   │   ├── RowDetailLayout.jsx [NEW]
│   │   ├── RowDetailMainPanel.jsx [NEW]
│   │   ├── RowDetailTabs.jsx [NEW]
│   │   ├── RowOverviewTab.jsx [NEW]
│   │   ├── RowEditTab.jsx [NEW]
│   │   ├── RowEvidenceTab.jsx [NEW]
│   │   ├── RowDetailActions.jsx [NEW]
│   │   │
│   │   ├── metrics/ [NEW]
│   │   │   ├── RowMetricsPanel.jsx [NEW]
│   │   │   ├── RowMetricsTabs.jsx [NEW]
│   │   │   ├── DQMetricsTab.jsx [NEW]
│   │   │   ├── DataLineageTab.jsx [NEW] (Future)
│   │   │   ├── RelatedRecordsTab.jsx [NEW] (Future)
│   │   │   └── AuditHistoryTab.jsx [NEW] (Future)
│   │   │
│   │   └── ResizableDivider.jsx [NEW]
│   │
│   ├── DataTableGrid.jsx [MODIFIED - add View icon, badge]
│   └── TableDataPage.jsx [MODIFIED - remove modals]
│
└── App.jsx [MODIFIED - add route]
```

---

## Success Criteria

✅ **Must Have:**
- Detail page opens with View icon
- Main tabs work (Overview, Edit, Evidence)
- Metrics panel shows on right
- DQ metrics load and display
- Resizable divider with constraints
- Mobile responsive (drawer-based)
- Back navigation works

✅ **Should Have:**
- Breadcrumb navigation
- Panel width persists (localStorage)
- Tab state persists
- Lazy-load additional metrics
- Error handling & loading states

✅ **Nice to Have:**
- Keyboard shortcuts
- Validation on unsaved edits
- Print view
- Share URL
- Undo/redo in edit

---

## Status

**Refined Architecture**: Complete ✅  
**Next**: Implementation (5-8 hours across 5 phases)  
**Dependencies**: DQ API endpoints (A10 Phase 2)  
**Can Start**: Phase 1 immediately (main content)  

---

**Design Date**: 2026-07-19  
**Refined By**: Zoo (Architecture)  
**Type**: Feature Enhancement (UX/Metrics Integration)
