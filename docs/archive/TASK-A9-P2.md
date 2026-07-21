# TASK: RUN A9 - PHASE 2 - Frontend Bulk Import Wizard

## Context

You are executing **Phase 2 of 5** for RUN A9 (Bulk Import/Export).

**Phase 1 Status:** ✅ Complete
- Backend API implemented: `bulk_import()` and `download_template()` actions
- Endpoints available: `POST /carbon-api/datarows/bulk-import/` and `GET /carbon-api/datarows/download-template/`

**Phase 2 Objective:** Create React `BulkImportWizard` component with 3-step wizard interface.

---

## Objective

Create a [`BulkImportWizard.jsx`](carbon-frontend/src/components/import/BulkImportWizard.jsx) React component that provides a user-friendly 3-step wizard for bulk data import:

1. **Step 1: Upload** - Drag-and-drop file upload (CSV/Excel)
2. **Step 2: Map Columns** - Match CSV headers to table field names
3. **Step 3: Validate** - Preview validation results before import

---

## Scope - IN

✅ Create `BulkImportWizard.jsx` component (modal dialog)  
✅ Step 1: File upload with drag-and-drop (react-dropzone)  
✅ Step 2: Column mapping interface with auto-mapping logic  
✅ Step 3: Validation preview showing valid/error rows  
✅ Install and use papaparse for CSV parsing  
✅ Client-side validation (required fields, types)  
✅ API call to backend bulk_import endpoint  
✅ Success/error notifications

---

## Scope - OUT

❌ Backend API changes (Phase 1 complete)  
❌ TableDataPage integration (Phase 3)  
❌ Excel client-side parsing (backend handles all parsing)  
❌ Import job history UI  
❌ Advanced fuzzy matching algorithms

---

## Prerequisites

1. Phase 1 backend API complete and tested
2. Frontend dev server can run: `cd carbon-frontend && npm run dev`
3. `react-dropzone@^19.0.2` installed (from A8)
4. Material-UI `@mui/material@^7.1.0` installed

---

## Implementation Steps

### Step 1: Install papaparse

**Command:**
```bash
cd carbon-frontend && npm install papaparse
```

**Verify:**
```bash
npm list papaparse
# Expected: papaparse@5.4.1
```

---

### Step 2: Create BulkImportWizard Component

**File:** `carbon-frontend/src/components/import/BulkImportWizard.jsx` (NEW)

**Component Structure:**
- Modal dialog (Material-UI Dialog)
- Stepper with 3 steps (Material-UI Stepper)
- Props: `open`, `onClose`, `tableId`, `fields`, `token`, `onImportComplete`

**Step 1 UI (Upload):**
- react-dropzone drag-and-drop zone
- Accept CSV (.csv) and Excel (.xlsx, .xls)
- Max file size: 10MB
- Show file name and size after selection
- Parse CSV with papaparse to extract headers

**Step 2 UI (Column Mapping):**
- Display CSV headers on left, table fields on right
- Material-UI Select dropdowns for mapping
- Auto-mapping logic:
  - Exact match (case-insensitive)
  - Normalized match (remove spaces, underscores)
- Show unmapped CSV columns in warning color
- Show required fields indicator

**Step 3 UI (Validation Preview):**
- Run client-side validation on parsed rows
- Validation rules:
  - Required fields must have values
  - Number fields must be numeric
  - Boolean fields must be true/false/yes/no/1/0
  - Select fields must match option values
- Display validation summary:
  - Total rows
  - Valid rows (green)
  - Invalid rows (red)
- Show first 5 errors in table
- "Import" button (disabled if all rows invalid)

**API Integration:**
- Construct FormData with file, data_table, column_mapping JSON
- POST to `/carbon-api/datarows/bulk-import/`
- Handle success: call onImportComplete with results
- Handle errors: show error notification

**Full implementation available in:** [`TASK-A9-PHASE2.md`](TASK-A9-PHASE2.md:88-443)

---

### Step 3: Verify Component Renders

**Manual Test:**

Create test file: `carbon-frontend/src/components/import/BulkImportWizardTest.jsx`

```jsx
import React, { useState } from 'react';
import { Button } from '@mui/material';
import BulkImportWizard from './BulkImportWizard';

export default function BulkImportWizardTest() {
  const [open, setOpen] = useState(false);

  const mockFields = [
    { name: 'date', label: 'Date', type: 'string', required: true },
    { name: 'distance', label: 'Distance', type: 'number', required: false },
    { name: 'fuel_type', label: 'Fuel Type', type: 'select', required: false, options: [
      { value: 'diesel', label: 'Diesel' },
      { value: 'gasoline', label: 'Gasoline' }
    ]}
  ];

  return (
    <div style={{ padding: 20 }}>
      <Button variant="contained" onClick={() => setOpen(true)}>
        Test Bulk Import
      </Button>
      <BulkImportWizard
        open={open}
        onClose={() => setOpen(false)}
        tableId={1}
        fields={mockFields}
        token="test-token"
        onImportComplete={(result) => {
          console.log('Import result:', result);
          setOpen(false);
        }}
      />
    </div>
  );
}
```

---

### Step 4: Component Testing

**Browser Test Checklist:**

1. **Step 1 (Upload):**
   - [ ] Modal opens with Stepper showing "Upload" active
   - [ ] Drag-and-drop zone displays correctly
   - [ ] Clicking zone opens file picker
   - [ ] CSV file upload shows file name and size
   - [ ] Excel file upload accepted
   - [ ] Invalid file type shows error
   - [ ] File over 10MB shows error
   - [ ] "Next" button enabled after valid file upload
   - [ ] "Cancel" button closes modal

2. **Step 2 (Column Mapping):**
   - [ ] CSV headers displayed on left
   - [ ] Table fields displayed in dropdowns
   - [ ] Auto-mapping works for exact matches
   - [ ] Auto-mapping works for normalized matches (e.g., "Date" → "date")
   - [ ] Manual dropdown selection works
   - [ ] Unmapped columns shown with warning
   - [ ] Required fields marked with asterisk
   - [ ] "Back" button returns to Step 1
   - [ ] "Next" button enabled

3. **Step 3 (Validation Preview):**
   - [ ] Validation summary shows total/valid/invalid counts
   - [ ] Valid rows count is green
   - [ ] Invalid rows count is red
   - [ ] Error table shows first 5 errors
   - [ ] Error table shows row number, field, and error message
   - [ ] "Import" button enabled if valid rows > 0
   - [ ] "Import" button disabled if all rows invalid
   - [ ] "Back" button returns to Step 2
   - [ ] "Cancel" button closes modal

4. **Import Execution:**
   - [ ] Clicking "Import" shows loading state
   - [ ] API call made to `/carbon-api/datarows/bulk-import/`
   - [ ] Success: onImportComplete called with results
   - [ ] Success: modal closes
   - [ ] Error: error message displayed
   - [ ] Error: modal remains open

---

### Step 5: Integration Test with Real Backend

**Prerequisites:**
- Backend server running: `./manage.sh backend`
- Valid auth token
- Existing DataTable with fields

**Test CSV File:**
Create `test_import.csv`:
```csv
date,distance,fuel_type
2026-01-01,100,diesel
2026-01-02,150,gasoline
2026-01-03,200,invalid_fuel_type
```

**Test Steps:**
1. Open BulkImportWizard with real tableId and token
2. Upload `test_import.csv`
3. Verify auto-mapping works
4. Proceed to validation
5. Verify row 3 shows validation error (invalid fuel_type)
6. Click Import
7. Verify API response: `{created: 2, failed: 1, errors: [...]}`
8. Verify onImportComplete receives results

---

## Acceptance Criteria

### Component Structure (4 criteria)
- [ ] BulkImportWizard.jsx created in `carbon-frontend/src/components/import/`
- [ ] Component is a Modal Dialog with Stepper
- [ ] Stepper has 3 steps: Upload, Map Columns, Validate
- [ ] Props interface matches: `{open, onClose, tableId, fields, token, onImportComplete}`

### Step 1: Upload (4 criteria)
- [ ] react-dropzone drag-and-drop zone renders
- [ ] CSV and Excel file types accepted
- [ ] File size validation (max 10MB)
- [ ] CSV parsing with papaparse extracts headers

### Step 2: Column Mapping (3 criteria)
- [ ] CSV headers mapped to table field dropdowns
- [ ] Auto-mapping logic works (exact + normalized)
- [ ] Manual mapping via dropdown selection works

### Step 3: Validation Preview (4 criteria)
- [ ] Client-side validation runs on parsed rows
- [ ] Validation summary shows total/valid/invalid counts
- [ ] Error table displays first 5 validation errors
- [ ] Import button disabled if all rows invalid

### API Integration (3 criteria)
- [ ] API call to `/carbon-api/datarows/bulk-import/` with FormData
- [ ] Column mapping sent as JSON string
- [ ] onImportComplete called with API response

### Error Handling (3 criteria)
- [ ] Network errors caught and displayed
- [ ] Invalid file types rejected
- [ ] Empty files rejected

### UI/UX (4 criteria)
- [ ] Navigation buttons (Back/Next/Cancel/Import) work correctly
- [ ] Loading states shown during API call
- [ ] Success feedback via onImportComplete callback
- [ ] Modal closes on cancel or successful import

**Total: 25 Acceptance Criteria**

---

## Deliverables

1. **Component File:**
   - `carbon-frontend/src/components/import/BulkImportWizard.jsx` (~500 lines)

2. **Updated package.json:**
   - Add papaparse dependency

3. **Test Results:**
   - Browser test checklist completed
   - Integration test with real backend successful

4. **Screenshots (optional):**
   - Step 1: Upload screen
   - Step 2: Column mapping
   - Step 3: Validation preview

---

## Next Phase

After Phase 2 completion:
- **Phase 3:** Integrate BulkImportWizard into TableDataPage
- **Phase 4:** Comprehensive testing (backend + frontend + integration)
- **Phase 5:** Documentation and RUN_LOG update

---

## Reference Files

- **Phase 2 Full Details:** [`TASK-A9-PHASE2.md`](TASK-A9-PHASE2.md:1) (722 lines with full component code)
- **Phase 1 Implementation:** [`backend/dataschema/views.py`](backend/dataschema/views.py:134) (bulk_import, download_template)
- **Evidence Uploader (A8 Reference):** [`carbon-frontend/src/components/evidence/EvidenceUploader.jsx`](carbon-frontend/src/components/evidence/EvidenceUploader.jsx:1) (drag-and-drop pattern)

---

## Success Criteria

Phase 2 is complete when:

1. ✅ papaparse installed
2. ✅ BulkImportWizard.jsx component created
3. ✅ All 3 steps implemented (Upload, Map, Validate)
4. ✅ Auto-mapping logic works
5. ✅ Client-side validation works
6. ✅ API integration successful
7. ✅ All 25 acceptance criteria met
8. ✅ Browser testing completed
9. ✅ Integration test with backend successful
10. ✅ No console errors

---

## Notes

- Follow A8 EvidenceUploader patterns for file upload UI
- Use Material-UI Stepper component for wizard navigation
- papaparse only needed for CSV preview (backend handles all parsing)
- Validation is client-side preview only (backend does final validation)
- Column mapping JSON format: `{"CSV_Header": "field_name", ...}`
- Excel files are uploaded directly (no client-side parsing)

**Good luck with Phase 2 implementation! 🚀**
