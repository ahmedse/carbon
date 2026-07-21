# 🤖 RAPTOR EXECUTION: RUN A9 - PHASE 2 - Frontend Bulk Import Wizard

## Mission Briefing

You are Raptor, the autonomous execution agent. Your mission is to implement Phase 2 of RUN A9: the **BulkImportWizard** React component.

**Phase 1 Status:** ✅ Backend API complete  
**Phase 2 Goal:** Create 3-step wizard for bulk CSV/Excel import

---

## Task Overview

Create [`BulkImportWizard.jsx`](carbon-frontend/src/components/import/BulkImportWizard.jsx) with:

1. **Step 1: Upload** - Drag-and-drop file upload (react-dropzone)
2. **Step 2: Map Columns** - Auto-map CSV headers to table fields
3. **Step 3: Validate** - Preview validation results before import

---

## Execution Steps

### STEP 1: Install papaparse

```bash
cd carbon-frontend && npm install papaparse
```

**Verify installation:**
```bash
npm list papaparse
# Expected: papaparse@5.4.1 or similar
```

**Why papaparse?** CSV parsing for header extraction and row preview.

---

### STEP 2: Create Component Directory

```bash
mkdir -p carbon-frontend/src/components/import
```

---

### STEP 3: Create BulkImportWizard.jsx

**File:** `carbon-frontend/src/components/import/BulkImportWizard.jsx`

**Full component code is in:** [`TASK-A9-PHASE2.md`](TASK-A9-PHASE2.md:88-443) (lines 88-443)

**Key Requirements:**

1. **Imports:**
   ```jsx
   import React, { useState } from 'react';
   import { Dialog, DialogTitle, DialogContent, DialogActions, Button, Stepper, Step, StepLabel, Box, Typography, Select, MenuItem, FormControl, InputLabel, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper, Alert, CircularProgress } from '@mui/material';
   import { useDropzone } from 'react-dropzone';
   import Papa from 'papaparse';
   import UploadFileIcon from '@mui/icons-material/UploadFile';
   ```

2. **Component Structure:**
   ```jsx
   export default function BulkImportWizard({ open, onClose, tableId, fields, token, onImportComplete }) {
     const [activeStep, setActiveStep] = useState(0);
     const [file, setFile] = useState(null);
     const [parsedData, setParsedData] = useState({ headers: [], rows: [] });
     const [columnMapping, setColumnMapping] = useState({});
     const [validationResults, setValidationResults] = useState({ valid: [], invalid: [] });
     const [loading, setLoading] = useState(false);
     const [error, setError] = useState(null);

     const steps = ['Upload File', 'Map Columns', 'Validate & Import'];

     // ... implementation
   }
   ```

3. **Step 1: File Upload with react-dropzone**
   - Accept: `.csv`, `.xlsx`, `.xls`
   - Max size: 10MB
   - Parse CSV with papaparse to extract headers
   - Store file and parsed data

4. **Step 2: Column Mapping**
   - Auto-mapping logic:
     ```javascript
     function normalizeString(str) {
       return str.toLowerCase().replace(/[_\s-]/g, '');
     }

     function autoMapColumns(csvHeaders, tableFields) {
       const mapping = {};
       csvHeaders.forEach(header => {
         // Exact match
         const exactMatch = tableFields.find(f => f.name === header);
         if (exactMatch) {
           mapping[header] = exactMatch.name;
           return;
         }
         // Normalized match
         const normalized = normalizeString(header);
         const fuzzyMatch = tableFields.find(f => normalizeString(f.name) === normalized);
         if (fuzzyMatch) {
           mapping[header] = fuzzyMatch.name;
         }
       });
       return mapping;
     }
     ```
   - Display dropdowns for each CSV header
   - Show unmapped columns in warning

5. **Step 3: Client-Side Validation**
   - Validation rules:
     ```javascript
     function validateRow(row, fields, columnMapping) {
       const errors = [];
       fields.forEach(field => {
         const csvHeader = Object.keys(columnMapping).find(h => columnMapping[h] === field.name);
         const value = csvHeader ? row[csvHeader] : null;

         // Required field check
         if (field.required && (!value || value.toString().trim() === '')) {
           errors.push(`${field.label} is required`);
         }

         // Type validation
         if (value && value.toString().trim()) {
           if (field.type === 'number' && isNaN(Number(value))) {
             errors.push(`${field.label} must be a number`);
           }
           if (field.type === 'boolean' && !['true', 'false', 'yes', 'no', '1', '0'].includes(value.toString().toLowerCase())) {
             errors.push(`${field.label} must be true/false`);
           }
           if (field.type === 'select' && field.options) {
             const validValues = field.options.map(opt => opt.value);
             if (!validValues.includes(value)) {
               errors.push(`${field.label} must be one of: ${validValues.join(', ')}`);
             }
           }
         }
       });
       return errors;
     }
     ```
   - Display summary: total, valid, invalid counts
   - Show first 5 errors in table

6. **Import API Call**
   ```javascript
   async function handleImport() {
     setLoading(true);
     setError(null);

     try {
       const formData = new FormData();
       formData.append('file', file);
       formData.append('data_table', tableId);
       formData.append('column_mapping', JSON.stringify(columnMapping));
       formData.append('mode', 'create');

       const response = await fetch(`${API_BASE_URL}/carbon-api/datarows/bulk-import/`, {
         method: 'POST',
         headers: {
           'Authorization': `Token ${token}`,
         },
         body: formData,
       });

       if (!response.ok) {
         throw new Error(`Import failed: ${response.statusText}`);
       }

       const result = await response.json();
       onImportComplete(result);
       handleClose();
     } catch (err) {
       setError(err.message);
     } finally {
       setLoading(false);
     }
   }
   ```

**Copy full code from [`TASK-A9-PHASE2.md`](TASK-A9-PHASE2.md:90-443) lines 90-443.**

---

### STEP 4: Verify Build

```bash
cd carbon-frontend && npm run build
```

**Expected:** No build errors.

**If errors:**
- Check all Material-UI imports
- Verify react-dropzone version
- Check papaparse import: `import Papa from 'papaparse';`

---

### STEP 5: Create Test File (Optional)

**File:** `carbon-frontend/src/components/import/BulkImportWizardTest.jsx`

```jsx
import React, { useState } from 'react';
import { Button, Box } from '@mui/material';
import BulkImportWizard from './BulkImportWizard';

export default function BulkImportWizardTest() {
  const [open, setOpen] = useState(false);

  const mockFields = [
    { name: 'date', label: 'Date', type: 'string', required: true },
    { name: 'distance', label: 'Distance (km)', type: 'number', required: false },
    { name: 'fuel_type', label: 'Fuel Type', type: 'select', required: false, options: [
      { value: 'diesel', label: 'Diesel' },
      { value: 'gasoline', label: 'Gasoline' }
    ]}
  ];

  const handleImportComplete = (result) => {
    console.log('Import complete:', result);
    alert(`Import successful!\nCreated: ${result.created}\nFailed: ${result.failed}`);
    setOpen(false);
  };

  return (
    <Box sx={{ padding: 3 }}>
      <Button variant="contained" onClick={() => setOpen(true)}>
        Test Bulk Import Wizard
      </Button>
      <BulkImportWizard
        open={open}
        onClose={() => setOpen(false)}
        tableId={1}
        fields={mockFields}
        token="test-token-replace-with-real"
        onImportComplete={handleImportComplete}
      />
    </Box>
  );
}
```

---

### STEP 6: Manual Browser Testing

#### Test Data Setup

Create test CSV file: `test_import.csv`
```csv
date,distance,fuel_type
2026-01-01,100,diesel
2026-01-02,150,gasoline
2026-01-03,200,diesel
```

Create test CSV with different headers: `test_mapping.csv`
```csv
Date,Dist,Fuel
2026-01-04,50,gasoline
2026-01-05,75,diesel
```

Create test CSV with errors: `test_errors.csv`
```csv
distance,fuel_type
100,diesel
150,invalid_type
```

#### Test Scenarios

**Test 1: Step 1 - File Upload**

1. Open BulkImportWizard
2. Click drag-and-drop zone
3. Select `test_import.csv`
4. **Verify:**
   - File name displayed
   - File size displayed
   - "Next" button enabled

**Test 2: Step 2 - Auto Mapping**

1. Upload `test_import.csv`
2. Click "Next"
3. **Verify:**
   - CSV headers shown: "date", "distance", "fuel_type"
   - Dropdowns pre-selected with matching field names
   - All fields mapped correctly

**Test 3: Step 2 - Manual Mapping**

1. Upload `test_mapping.csv`
2. Click "Next"
3. **Verify:**
   - Auto-mapping: "Date" → "date", "Dist" → "distance", "Fuel" → "fuel_type"
   - Change dropdown manually
   - Mapping updates

**Test 4: Step 3 - Validation Preview**

1. Complete Steps 1-2 with `test_import.csv`
2. Click "Next"
3. **Verify:**
   - Validation summary: 3 total, 3 valid, 0 invalid
   - "Import" button enabled
   - No errors shown

**Test 5: Step 3 - Validation Errors**

1. Upload `test_errors.csv` (missing required "date" field)
2. Map columns
3. Click "Next"
4. **Verify:**
   - Validation summary: 2 total, 0 valid, 2 invalid
   - Error table shows: "Row 2: date is required"
   - "Import" button disabled

**Test 6: Import Execution**

1. Complete Steps 1-3 with valid data
2. Click "Import"
3. **Verify:**
   - Loading spinner appears
   - API call to `/carbon-api/datarows/bulk-import/`
   - onImportComplete callback fires
   - Modal closes

**Test 7: Error Handling**

1. Upload file over 10MB
2. **Verify:** Error message displayed
3. Upload `.txt` file
4. **Verify:** Error message displayed

**Test 8: Navigation**

1. Upload file → Next → Back
2. **Verify:** Step 1 shown, file still selected
3. Map columns → Next → Back
4. **Verify:** Step 2 shown, mappings preserved
5. Validate → Back → Next
6. **Verify:** Validation re-runs

---

### STEP 7: Integration Test with Real Backend

**Prerequisites:**
- Backend server running: `./manage.sh backend`
- Get auth token:
  ```bash
  curl -X POST http://localhost:8009/accounts/login/ \
    -H "Content-Type: application/json" \
    -d '{"username": "admin", "password": "admin"}'
  ```
- Note a valid `tableId` from existing DataTable

**Test Steps:**

1. **Get Table Fields:**
   ```bash
   curl -X GET "http://localhost:8009/carbon-api/data-fields/?data_table={tableId}" \
     -H "Authorization: Token {your_token}"
   ```

2. **Open Wizard in Browser:**
   - Replace `token` and `tableId` in BulkImportWizardTest
   - Open component in browser
   - Upload `test_import.csv`
   - Complete Steps 1-3
   - Click Import

3. **Verify Backend Response:**
   - Check browser Network tab for API call
   - Response should be: `{created: 3, failed: 0, errors: []}`

4. **Verify Data in Database:**
   ```bash
   curl -X GET "http://localhost:8009/carbon-api/datarows/?data_table={tableId}" \
     -H "Authorization: Token {your_token}"
   ```
   - Should show 3 new rows

---

## Acceptance Criteria Checklist

**Component Structure (4):**
- [ ] BulkImportWizard.jsx created in `carbon-frontend/src/components/import/`
- [ ] Component is Modal Dialog with Material-UI Stepper
- [ ] Stepper has 3 steps: Upload, Map Columns, Validate
- [ ] Props: `open`, `onClose`, `tableId`, `fields`, `token`, `onImportComplete`

**Step 1: Upload (4):**
- [ ] react-dropzone drag-and-drop zone
- [ ] Accepts CSV (.csv) and Excel (.xlsx, .xls)
- [ ] File size validation (max 10MB)
- [ ] CSV parsed with papaparse to extract headers

**Step 2: Column Mapping (3):**
- [ ] CSV headers mapped to field dropdowns
- [ ] Auto-mapping: exact match (case-insensitive)
- [ ] Auto-mapping: normalized match (remove spaces/underscores)

**Step 3: Validation (4):**
- [ ] Client-side validation runs
- [ ] Summary shows: total, valid, invalid counts
- [ ] Error table shows first 5 errors
- [ ] Import button disabled if all rows invalid

**API Integration (3):**
- [ ] FormData with file, data_table, column_mapping JSON
- [ ] POST to `/carbon-api/datarows/bulk-import/`
- [ ] onImportComplete called with result

**Error Handling (3):**
- [ ] Network errors caught and displayed
- [ ] Invalid file types rejected
- [ ] Empty files rejected

**UI/UX (4):**
- [ ] Back/Next/Cancel/Import buttons work
- [ ] Loading state during API call
- [ ] Modal closes on success
- [ ] Modal stays open on error

**Total: 25 Acceptance Criteria**

---

## Troubleshooting

### Issue: "Papa is not defined"
**Solution:** Check import: `import Papa from 'papaparse';`

### Issue: "useDropzone is not a function"
**Solution:** 
```bash
npm install react-dropzone@^19.0.2
```

### Issue: Build error "Cannot find module @mui/icons-material"
**Solution:**
```bash
npm install @mui/icons-material
```

### Issue: API call fails with CORS error
**Solution:** Verify backend CORS settings allow frontend origin.

### Issue: Column mapping not working
**Solution:** Check `normalizeString()` function and auto-mapping logic.

### Issue: Validation always fails
**Solution:** Check `validateRow()` logic matches field types in backend serializer.

---

## Deliverables

1. **Component File:**
   - `carbon-frontend/src/components/import/BulkImportWizard.jsx` (~500 lines)

2. **Updated package.json:**
   - `papaparse@^5.4.1` added

3. **Test Results Document:**
   Create `PHASE2_A9_TEST_RESULTS.md`:
   ```markdown
   # Phase 2 - Frontend Import Wizard Test Results

   ## Build Verification
   - ✅ npm install papaparse successful
   - ✅ Component created (500 lines)
   - ✅ npm run build successful
   - ✅ No TypeScript/ESLint errors

   ## Browser Tests (8/8 PASS)
   - ✅ Test 1: File upload works
   - ✅ Test 2: Auto-mapping exact match
   - ✅ Test 3: Manual mapping
   - ✅ Test 4: Validation preview
   - ✅ Test 5: Validation errors
   - ✅ Test 6: Import execution
   - ✅ Test 7: Error handling
   - ✅ Test 8: Navigation

   ## Integration Test (PASS)
   - ✅ Real backend API call successful
   - ✅ Data imported to database
   - ✅ Result callback works

   ## Acceptance Criteria (25/25 ✅)
   [List all 25 with checkmarks]

   ## Known Issues
   [None or list any issues]

   ## Next Steps
   - Proceed to Phase 3: TableDataPage Integration
   ```

4. **Git Commit:**
   ```bash
   git add carbon-frontend/src/components/import/BulkImportWizard.jsx
   git add carbon-frontend/package.json
   git add carbon-frontend/package-lock.json
   git commit -m "feat(A9-P2): Frontend bulk import wizard

   - Create BulkImportWizard component (3-step modal)
   - Step 1: File upload with react-dropzone
   - Step 2: Column mapping with auto-mapping
   - Step 3: Validation preview with error display
   - Install papaparse for CSV parsing
   - Client-side validation before import
   - API integration with backend bulk_import

   Phase 2/5 complete. Next: TableDataPage integration.

   Relates-to: RUN-A9"
   ```

---

## Success Criteria

Phase 2 complete when:

1. ✅ papaparse installed
2. ✅ BulkImportWizard.jsx created (~500 lines)
3. ✅ All 3 steps implemented
4. ✅ Auto-mapping works (exact + normalized)
5. ✅ Client-side validation works
6. ✅ API integration successful
7. ✅ All 25 acceptance criteria met
8. ✅ Browser tests pass (8/8)
9. ✅ Integration test pass
10. ✅ npm run build successful
11. ✅ Git commit completed

---

## Reference Materials

- **Full Component Code:** [`TASK-A9-PHASE2.md`](TASK-A9-PHASE2.md:88-443) lines 88-443
- **Evidence Uploader Pattern (A8):** [`EvidenceUploader.jsx`](carbon-frontend/src/components/evidence/EvidenceUploader.jsx:1)
- **Backend API:** [`bulk_import()`](backend/dataschema/views.py:134)
- **Task Summary:** [`TASK-A9-P2.md`](TASK-A9-P2.md:1)

---

## Next Phase Preview

**Phase 3:** Integrate BulkImportWizard into TableDataPage
- Add "Import" button to TableDataPage header
- Add "Download Template" button
- Wire up wizard to table state
- Test end-to-end user flow

---

**Ready to execute? Let's build the wizard! 🧙‍♂️✨**
