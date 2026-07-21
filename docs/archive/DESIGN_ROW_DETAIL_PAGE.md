# Design: Row Detail Page Architecture

**Status**: Architectural Design (Pre-Implementation)  
**Date**: 2026-07-19  
**Priority**: High (UX Improvement)  
**Complexity**: Medium (5-6 hours estimated)

---

## Executive Summary

Instead of managing row operations (edit/delete/evidence) through modals, create a dedicated **Row Detail Page** with tabbed interface. This provides:

- ✅ Clear separation of concerns
- ✅ Better UX for complex operations
- ✅ Visual indicators in grid (View icon, Evidence badge)
- ✅ Scalable for future features (history, validation, comments)
- ✅ Full viewport for detailed work
- ✅ Better mobile experience

---

## Current Architecture (Before)

```
TableDataPage (Grid View)
├── DataTableGrid (grid + inline modals)
│   ├── Row Add/Edit Modal (Drawer→Dialog)
│   ├── Delete Confirmation Modal
│   └── Row action buttons
├── Evidence Modal (separate from row context)
└── Bulk Import Wizard
```

**Problem**: Evidence management disconnected from row edit flow. User context scattered across multiple modals.

---

## Proposed Architecture (After)

```
App Router
├── /dataschema/table/{moduleId}/{tableId}          ← TableDataPage (List View)
│   ├── Grid with View icon + Evidence badge
│   ├── Bulk Import Wizard
│   └── Delete confirmation
│
└── /dataschema/table/{moduleId}/{tableId}/row/{rowId}  ← RowDetailPage (Detail View) [NEW]
    ├── Tabs:
    │   ├── Overview (data display, edit button)
    │   ├── Edit (full form for updating)
    │   ├── Evidence (upload + manage attachments)
    │   ├── History (audit trail) [Future]
    │   └── Validation (DQ results) [Future]
    ├── Action buttons (Save, Delete, Close)
    └── Breadcrumb navigation
```

---

## Component Hierarchy

### New Components

```
RowDetailPage.jsx [NEW]
├── RowDetailHeader (Title, Breadcrumbs, Close button)
├── RowDetailTabs (Tab switcher)
│   ├── RowOverviewTab (read-only view, Edit button triggers Edit tab)
│   ├── RowEditTab (edit form, Save/Cancel)
│   ├── RowEvidenceTab (evidence upload + viewer)
│   ├── RowHistoryTab [Future - audit trail]
│   └── RowValidationTab [Future - DQ metrics]
├── RowDetailActions (Delete, Close buttons)
└── RowDetailFooter (Status bar, last modified, etc.)
```

### Modified Components

```
TableDataPage.jsx [MODIFIED]
├── Remove: Evidence Modal, Row Edit Modal, Delete Modal
├── Add: View icon to grid actions
├── Add: Evidence badge to grid
└── Simplify: Only show Bulk Import, Delete confirmation

DataTableGrid.jsx [MODIFIED]
├── Remove: Edit/Delete modals
├── Add: onClick handler to View icon → navigate to detail page
├── Add: Evidence indicator badge
└── Simplify: Row actions to just View + Delete
```

---

## URL Structure & Navigation

### List View
```
/dataschema/table/{moduleId}/{tableId}
  ↓ (click "View" icon on row)
  ↓
/dataschema/table/{moduleId}/{tableId}/row/{rowId}
  ↓ (click Close or Escape)
  ↓
/dataschema/table/{moduleId}/{tableId}
```

### Breadcrumb Trail
```
Data Schema > [Module Name] > [Table Name] > Row {rowId}
                                               └── Shows "Edit" when in Edit tab
```

### Query Parameters (Optional)
```
?tab=overview              ← Default
?tab=edit                  ← Jump to edit tab
?tab=evidence              ← Jump to evidence tab
```

---

## Grid UI Changes

### Before (Current)
```
┌─────────────────────────────────────────────────────────────┐
│ Row ID  │ Building │ Water │ Actions                         │
├─────────────────────────────────────────────────────────────┤
│ 123     │ B401     │ 404   │ [Edit] [Delete] [Evidence] [☐]  │ ← Multiple buttons
├─────────────────────────────────────────────────────────────┤
│ 124     │ B2401    │ 422   │ [Edit] [Delete] [Evidence] [☐]  │
└─────────────────────────────────────────────────────────────┘
```

### After (Proposed)
```
┌──────────────────────────────────────────────────────────────────┐
│ Row ID  │ Building │ Water │ Evidence │ Actions                   │
├──────────────────────────────────────────────────────────────────┤
│ 123     │ B401     │ 404   │ 📎 3     │ [👁️ View] [🗑️ Delete] [☐] │
├──────────────────────────────────────────────────────────────────┤
│ 124     │ B2401    │ 422   │ ✓        │ [👁️ View] [🗑️ Delete] [☐] │
└──────────────────────────────────────────────────────────────────┘
       ↑ New column with badge/icon
       
Legend:
  👁️       = View icon (click to open detail page)
  📎 3     = Evidence badge (3 files attached)
  ✓        = Evidence exists (1+ files)
  [empty]  = No evidence
```

---

## Row Detail Page Layout

### Header Section
```
╔═══════════════════════════════════════════════════════════════╗
║ ← Back   Data Schema > Module > Table > Row 123               ║
║          [Close Button X]                                    ║
╚═══════════════════════════════════════════════════════════════╝
```

### Tab Navigation
```
┌─────────────────────────────────────────────────────────────┐
│ Overview │ Edit │ Evidence │ History │ Validation │         │
├─────────────────────────────────────────────────────────────┤
```

### Tab Content Area

#### Overview Tab (Default)
```
┌─────────────────────────────────────────────────────────────┐
│ OVERVIEW                                                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Row ID: 123                                                │
│  Building: 401                                              │
│  Water (m³): 404                                            │
│                                                              │
│  Last Modified: 2026-07-19 09:25 by Ahmed                   │
│  Created: 2026-07-15 14:30 by Admin                         │
│                                                              │
│  [Edit] [Delete] [Download] [More Actions ▼]               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

#### Edit Tab
```
┌─────────────────────────────────────────────────────────────┐
│ EDIT ROW DATA                                                │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Building _________________________________________ [B401]  │
│                                                              │
│  Water (m³) _________________________________ [404]  [↻]   │
│             (refreshed from sensor)                         │
│                                                              │
│  Status    [Verified ▼]                                     │
│                                                              │
│  Notes     ________________                                 │
│            ________________                                 │
│            ________________                                 │
│                                                              │
│  [Save Changes] [Cancel] [Reset to Original]               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

#### Evidence Tab
```
┌─────────────────────────────────────────────────────────────┐
│ EVIDENCE & ATTACHMENTS                                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Drag & drop files here                                     │
│  or click to browse                                         │
│  (PDF, Images, Excel, CSV, Word - Max 50MB)               │
│                                                              │
│  ─────────────────────────────────────────────────────────  │
│                                                              │
│  Attached Files (3):                                        │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 📄 Invoice_2026-07-15.pdf      (2.3 MB)  [⬇️] [🗑️]  │  │
│  │ 📷 Water_meter_photo.jpg        (1.8 MB)  [⬇️] [🗑️]  │  │
│  │ 📊 Sensor_reading_2026-07-19.xlsx (156 KB) [⬇️] [🗑️]  │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

#### History Tab (Future)
```
┌─────────────────────────────────────────────────────────────┐
│ AUDIT TRAIL                                                  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ 2026-07-19 10:15   Ahmed         Updated "Water" 404→405   │
│ 2026-07-19 09:30   Ahmed         Added 3 evidence files    │
│ 2026-07-18 14:20   Admin         Created row               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

#### Validation Tab (Future)
```
┌─────────────────────────────────────────────────────────────┐
│ DATA QUALITY RESULTS                                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ Status: ✓ PASSED (3 checks passed, 0 failed)              │
│                                                              │
│ ✓ Range Check: 0 < Water ≤ 1000  ........................ OK  │
│ ✓ Format Check: Valid date format ........................ OK  │
│ ✓ Uniqueness: No duplicates in week ..................... OK  │
│                                                              │
│ Last Run: 2026-07-19 10:15                                 │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### Load Detail Page
```
TableDataPage
  ↓
User clicks "View" icon on Row 123
  ↓ navigate(/table/{moduleId}/{tableId}/row/123)
  ↓
RowDetailPage mounts
  ├── Fetch row data: GET /api/rows/123/
  ├── Fetch evidence: GET /api/evidence/?data_row=123
  ├── Fetch history: GET /api/audit-log/?row_id=123 [Future]
  └── Fetch DQ results: GET /api/dq-results/?row_id=123 [Future]
  ↓
Display Overview Tab (read-only)
```

### Edit Row
```
User clicks "Edit" button or switches to Edit Tab
  ↓
Show edit form with current values
  ↓
User makes changes and clicks "Save Changes"
  ↓
PATCH /api/rows/123/ { field: value, ... }
  ↓
Success → Show notification, update UI
  ↓
Return to Overview Tab
```

### Upload Evidence
```
User switches to Evidence Tab
  ↓
User drags/drops files or clicks to browse
  ↓
POST /api/evidence/bulk-upload/ (FormData)
  ↓
Upload shows progress bar
  ↓
Success → Add files to list, refresh file count
  ↓
Badge in grid updates (📎 4 files)
```

### Delete Row
```
User clicks [Delete] button
  ↓
Show confirmation modal
  ↓
User confirms
  ↓
DELETE /api/rows/123/
  ↓
Navigate back to table list
  ↓
Grid refreshes without row 123
```

---

## API Requirements (Already Exist)

### Get Row Data
```
GET /carbon-api/datarows/{rowId}/
```
**Returns**: Single row object with all fields

### Update Row Data
```
PATCH /carbon-api/datarows/{rowId}/
Body: { values: { field1: value1, ... } }
```
**Returns**: Updated row object

### Delete Row
```
DELETE /carbon-api/datarows/{rowId}/
```
**Returns**: 204 No Content

### Get Evidence for Row
```
GET /carbon-api/evidence/?data_row={rowId}
```
**Returns**: List of evidence files for this row

### Upload Evidence
```
POST /carbon-api/evidence/bulk-upload/
Body: FormData { data_row: 123, files: [File, File, ...] }
```
**Returns**: { results: [{ filename, status, ... }, ...] }

---

## Implementation Plan (5 Phases)

### Phase 1: Core Detail Page (2 hours)
- [ ] Create `RowDetailPage.jsx` component
- [ ] Setup route `/table/{moduleId}/{tableId}/row/{rowId}`
- [ ] Create `RowDetailHeader.jsx` (breadcrumbs, close)
- [ ] Create `RowDetailTabs.jsx` (tab switcher)
- [ ] Fetch and display row data

### Phase 2: Overview & Edit Tabs (1.5 hours)
- [ ] Create `RowOverviewTab.jsx` (read-only display)
- [ ] Create `RowEditTab.jsx` (edit form)
- [ ] Connect edit form to update API
- [ ] Add loading/error states

### Phase 3: Evidence Tab Integration (1 hour)
- [ ] Create `RowEvidenceTab.jsx`
- [ ] Move EvidenceUploader to new tab
- [ ] Move EvidenceViewer to new tab
- [ ] Update evidence badge logic

### Phase 4: Grid UI Updates (1 hour)
- [ ] Add "View" icon to grid actions
- [ ] Add "Evidence" column with badge/count
- [ ] Implement View icon click → navigate to detail page
- [ ] Clean up row action buttons

### Phase 5: Testing & Polish (0.5 hours)
- [ ] Test all navigation flows
- [ ] Test edit/save/cancel
- [ ] Test evidence upload
- [ ] Mobile responsiveness

---

## Benefits Analysis

| Aspect | Before (Modals) | After (Detail Page) |
|--------|---|---|
| **Screen Real Estate** | Limited (modal size) | Full viewport |
| **UX Complexity** | Multiple modals | Single flow |
| **Mobile Experience** | Cramped modals | Full page, responsive |
| **Future Extensibility** | Hard to add features | Easy (just add tabs) |
| **Separation of Concerns** | Mixed (edit + evidence) | Clear (separate tabs) |
| **Navigation** | Modal stack | RESTful URLs |
| **Bookmarkability** | Not possible | ✅ Possible |
| **Evidence Visibility** | Hidden until modal | Badge in grid view |
| **Data Exploration** | Context switching | Single page |
| **Accessibility** | Modal focus trap | Full page navigation |

---

## Grid Icon Indicators (Detailed)

### View Icon
```
Icon: 👁️ (Eye icon from Material-UI: Visibility)
Action: onClick → navigate to detail page
Tooltip: "View row details"
Color: primary.main (blue)
Hover Effect: Background highlight
```

### Evidence Badge
```
No Evidence:      [empty]              (nothing shown)
1 File:          ✓                    (checkmark icon)
2-9 Files:       📎 {count}           (paperclip + number)
10+ Files:       📎 9+                (capped at "9+")

Icon: AttachFile or MoreVert (Material-UI icons)
Color: 
  - Green (✓) if evidence present
  - Orange (📎) if multiple files
Badge: Gray background with file count
Tooltip: "X evidence files attached"
OnClick: Optional - could also navigate to detail page Evidence tab
```

---

## Wireframe (ASCII Representation)

```
╔══════════════════════════════════════════════════════════════════════╗
║ CARBON DATA MANAGEMENT                                               ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  TABLE DATA PAGE                                                     ║
║  ─────────────────                                                   ║
║                                                                      ║
║  [📤 Bulk Import] [⬇️ Download Template] [📎 Evidence]             ║
║                                                                      ║
║  ┌──────────────────────────────────────────────────────────────┐   ║
║  │ ☐  Row ID  │ Building │ Water │ Evidence │ Actions          │   ║
║  ├──────────────────────────────────────────────────────────────┤   ║
║  │ ☐  123     │ B401     │ 404   │ 📎 3     │ 👁️ 🗑️         │   ║
║  │    ↓ click View icon navigates to detail page               │   ║
║  │ ☐  124     │ B2401    │ 422   │ ✓        │ 👁️ 🗑️         │   ║
║  │ ☐  125     │ B3      │ 318   │ [empty]  │ 👁️ 🗑️         │   ║
║  └──────────────────────────────────────────────────────────────┘   ║
║                                                                      ║
║                           ⟺ NAVIGATES TO ⟹                        ║
║                                                                      ║
║  ROW DETAIL PAGE (New)                                              ║
║  ──────────────────────                                             ║
║                                                                      ║
║  ← Back | Data Schema > Module > Table > Row 123          [✕]      ║
║                                                                      ║
║  ┌──────────────────────────────────────────────────────────────┐   ║
║  │ Overview │ Edit │ Evidence │ History │ Validation          │   ║
║  ├──────────────────────────────────────────────────────────────┤   ║
║  │                                                              │   ║
║  │  Row ID: 123                                               │   ║
║  │  Building: 401                                             │   ║
║  │  Water (m³): 404                                           │   ║
║  │  Status: Verified                                          │   ║
║  │                                                              │   ║
║  │  Last Modified: 2026-07-19 10:15 by Ahmed                 │   ║
║  │                                                              │   ║
║  │  [Edit] [Delete] [Download] [⋮]                           │   ║
║  │                                                              │   ║
║  └──────────────────────────────────────────────────────────────┘   ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
```

---

## Testing Checklist

### Navigation
- [ ] Clicking View icon opens detail page
- [ ] Back button returns to table list
- [ ] Breadcrumb navigation works
- [ ] URL reflects current state (/row/{rowId})
- [ ] Pressing Escape closes detail page

### Overview Tab
- [ ] Row data loads correctly
- [ ] Edit button switches to Edit tab
- [ ] Delete button shows confirmation
- [ ] Last modified info displays correctly

### Edit Tab
- [ ] Form loads with current values
- [ ] Changes don't save on blur (only on Save)
- [ ] Save Changes calls API correctly
- [ ] Cancel reverts changes
- [ ] Reset to Original button works
- [ ] Success notification appears

### Evidence Tab
- [ ] File upload area visible
- [ ] Drag & drop works
- [ ] File list shows correctly
- [ ] Download/delete buttons work
- [ ] File count badge updates in grid

### Grid Integration
- [ ] View icon appears on all rows
- [ ] Evidence badge shows correct state
- [ ] No evidence shows nothing
- [ ] 1 file shows checkmark
- [ ] Multiple files show count

### Mobile Responsiveness
- [ ] Detail page stacks vertically
- [ ] Tab headers scroll horizontally
- [ ] No horizontal overflow
- [ ] Touch-friendly button sizes

---

## Future Enhancements (Out of Scope for Now)

- [ ] **History Tab**: Audit trail of changes
- [ ] **Validation Tab**: Real-time DQ result display
- [ ] **Comments Tab**: Row-level discussion/notes
- [ ] **Related Rows**: Show parent/child relationships
- [ ] **Export**: Export single row as CSV/PDF
- [ ] **Versioning**: Show version history with diff
- [ ] **Workflows**: Add approval/review workflow UI
- [ ] **Linked Records**: Show relationships to other tables

---

## Files to Create/Modify

### New Files
- `carbon-frontend/src/pages/RowDetailPage.jsx`
- `carbon-frontend/src/components/row-detail/RowDetailHeader.jsx`
- `carbon-frontend/src/components/row-detail/RowDetailTabs.jsx`
- `carbon-frontend/src/components/row-detail/RowOverviewTab.jsx`
- `carbon-frontend/src/components/row-detail/RowEditTab.jsx`
- `carbon-frontend/src/components/row-detail/RowEvidenceTab.jsx`

### Modified Files
- `carbon-frontend/src/App.jsx` (add new route)
- `carbon-frontend/src/components/DataTableGrid.jsx` (add View icon, Evidence badge)
- `carbon-frontend/src/components/TableDataPage.jsx` (remove edit/evidence modals)

---

## Success Criteria

✅ **Must Have:**
- Detail page opens when View icon clicked
- Edit tab allows full row editing with save
- Evidence tab shows upload + file list
- Grid shows evidence indicator badge
- Navigation back to list works

✅ **Should Have:**
- Breadcrumb navigation
- Tab persistence in URL (query param)
- Mobile responsive
- Loading states
- Error handling

✅ **Nice to Have:**
- Keyboard shortcuts (Escape to close)
- Edit confirmation if unsaved changes
- Undo/redo in edit tab
- Print view
- Share URL to specific row

---

## Related Documents

- RUN A9: Bulk Import/Export
- RUN A8: Evidence & Attachments
- DESIGN_UI_ARCHITECTURE_A5.md
- DRAWER_TO_MODAL_UX_FIX.md (predecessor design)

---

## Status

**Current**: Architectural Design Complete  
**Next**: Implementation (when approved)  
**Estimated Duration**: 5-6 hours (5 phases)  
**Dependencies**: None (can start immediately)  
**Blocks**: None identified  

---

**Design Date**: 2026-07-19  
**Designed By**: Zoo (Architecture Analysis)  
**Type**: Feature Enhancement (UX/Architecture Improvement)
