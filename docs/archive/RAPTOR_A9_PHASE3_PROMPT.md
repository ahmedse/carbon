# 🤖 RAPTOR EXECUTION: RUN A9 - PHASE 3 - TableDataPage Integration

## Mission Briefing

You are Raptor, the autonomous execution agent. Your mission is to implement Phase 3 of RUN A9: **Integrate BulkImportWizard into TableDataPage**.

**Phase 1 Status:** ✅ Backend API complete  
**Phase 2 Status:** ✅ BulkImportWizard component complete (501 lines, 38/38 tests passed)  
**Phase 3 Goal:** Add Import and Template buttons to TableDataPage toolbar

---

## Task Overview

Modify [`TableDataPage.jsx`](carbon-frontend/src/components/TableDataPage.jsx) to add:

1. **Import Button** - Opens BulkImportWizard modal
2. **Download Template Button** - Downloads CSV template
3. **Import Completion Handler** - Refreshes grid, shows notifications
4. **Template Download Handler** - Triggers browser download

---

## Execution Steps

### STEP 1: Read Current TableDataPage Structure

```bash
# View file to understand current structure
cat carbon-frontend/src/components/TableDataPage.jsx | head -100
```

**What to look for:**
- Existing imports section
- useState declarations
- Evidence button location (from A8)
- notify() function usage
- fetchTable() function

---

### STEP 2: Add Imports

**File:** `carbon-frontend/src/components/TableDataPage.jsx`

**Location:** Top of file, after existing imports

**Add these 3 imports:**

```javascript
import BulkImportWizard from './import/BulkImportWizard';
import UploadIcon from '@mui/icons-material/Upload';
import DownloadIcon from '@mui/icons-material/Download';
```

**Verification:**
- Imports placed after existing Material-UI icon imports
- No duplicate imports

---

### STEP 3: Add State Variable

**Location:** Inside `TableDataPage` function, after existing `useState` declarations

**Add:**

```javascript
const [showImportWizard, setShowImportWizard] = useState(false);
```

**Verification:**
- Placed after `evidenceRefreshKey` state (from A8)
- Before handler functions

---

### STEP 4: Add Import Completion Handler

**Location:** After `handleRowSelection` function (around line 204-211)

**Add complete function:**

```javascript
const handleImportComplete = (result) => {
  const { created, failed, errors } = result;
  
  if (failed === 0) {
    // All rows imported successfully
    notify({
      message: `Import successful: ${created} rows created`,
      type: 'success'
    });
  } else if (created === 0) {
    // All rows failed
    notify({
      message: `Import failed: ${failed} rows had errors`,
      type: 'error'
    });
  } else {
    // Partial success
    notify({
      message: `Import completed with warnings: ${created} created, ${failed} failed`,
      type: 'warning'
    });
  }
  
  // Refresh table to show new rows
  fetchTable();
  
  // Close wizard
  setShowImportWizard(false);
};
```

**Verification:**
- Uses existing `notify()` function
- Calls existing `fetchTable()` function
- Closes wizard on completion

---

### STEP 5: Add Template Download Handler

**Location:** After `handleImportComplete` function

**Add complete function:**

```javascript
const handleDownloadTemplate = async () => {
  try {
    const response = await fetch(
      `${API_BASE_URL}/carbon-api/datarows/download-template/?data_table=${tableId}&include_example=false`,
      {
        method: 'GET',
        headers: {
          'Authorization': `Token ${token}`,
        },
      }
    );
    
    if (!response.ok) {
      throw new Error('Failed to download template');
    }
    
    // Get filename from Content-Disposition header or use default
    const contentDisposition = response.headers.get('Content-Disposition');
    let filename = 'template.csv';
    if (contentDisposition) {
      const filenameMatch = contentDisposition.match(/filename="?(.+)"?/);
      if (filenameMatch) {
        filename = filenameMatch[1];
      }
    }
    
    // Trigger browser download
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
    
    notify({
      message: 'Template downloaded successfully',
      type: 'success'
    });
  } catch (err) {
    notify({
      message: `Failed to download template: ${err.message}`,
      type: 'error'
    });
  }
};
```

**Verification:**
- Uses existing `API_BASE_URL`, `tableId`, `token` variables
- Triggers browser download (not save dialog)
- Error handling with notifications

---

### STEP 6: Add Buttons to Toolbar

**Location:** Find the Evidence button section (from A8)

**Search for this pattern:**

```jsx
<Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
  <Button
    startIcon={<AttachFileIcon />}
    onClick={() => setShowEvidenceModal(true)}
  >
    Evidence
  </Button>
</Box>
```

**Replace entire Box with:**

```jsx
<Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
  <Button
    variant="outlined"
    startIcon={<UploadIcon />}
    onClick={() => setShowImportWizard(true)}
  >
    Import
  </Button>
  <Button
    variant="outlined"
    startIcon={<DownloadIcon />}
    onClick={handleDownloadTemplate}
  >
    Template
  </Button>
  <Button
    startIcon={<AttachFileIcon />}
    onClick={() => setShowEvidenceModal(true)}
  >
    Evidence
  </Button>
</Box>
```

**Verification:**
- Import button: `variant="outlined"` with UploadIcon
- Template button: `variant="outlined"` with DownloadIcon
- Evidence button: unchanged (default variant)
- All buttons in same Box with `gap: 1`

---

### STEP 7: Add BulkImportWizard Component

**Location:** At the end of the JSX return statement, after `<EvidenceModal .../>` component

**Add:**

```jsx
{/* Bulk Import Wizard Modal */}
<BulkImportWizard
  open={showImportWizard}
  onClose={() => setShowImportWizard(false)}
  tableId={tableId}
  fields={fields}
  token={token}
  onImportComplete={handleImportComplete}
/>
```

**Verification:**
- Placed inside the main return statement
- After EvidenceModal component
- Before closing tags
- All props passed correctly

---

### STEP 8: Verify Build

```bash
cd carbon-frontend && npm run build
```

**Expected:** No errors

**If errors:**
- Check all imports are correct
- Verify BulkImportWizard path: `'./import/BulkImportWizard'`
- Check for missing commas or brackets

---

### STEP 9: Manual Browser Testing

#### Test 1: Buttons Render

1. Start dev server: `npm run dev`
2. Navigate to Data Hub → any table
3. **Verify:**
   - Import button visible (Upload icon, outlined)
   - Template button visible (Download icon, outlined)
   - Evidence button visible (AttachFile icon, filled)
   - All 3 buttons aligned horizontally

#### Test 2: Template Download

1. Click "Template" button
2. **Verify:**
   - CSV file downloads automatically
   - Filename: `{table_name}_template.csv`
   - Open file: contains field names as headers
   - Success notification: "Template downloaded successfully"

#### Test 3: Import Wizard Opens

1. Click "Import" button
2. **Verify:**
   - BulkImportWizard modal opens
   - Stepper shows 3 steps: Upload, Map Columns, Validate
   - Step 1 (Upload) is active
   - Close button works

#### Test 4: Complete Import Flow (Success)

**Create test CSV:**
```bash
cat > test_import_success.csv << 'EOF'
date,distance,fuel_type
2026-01-10,100,diesel
2026-01-11,150,gasoline
EOF
```

**Test steps:**
1. Click "Import" button
2. Upload `test_import_success.csv` (Step 1)
3. Click "Next"
4. Verify column mapping auto-mapped (Step 2)
5. Click "Next"
6. Verify validation: 2 total, 2 valid, 0 invalid (Step 3)
7. Click "Import"
8. **Verify:**
   - Success notification: "Import successful: 2 rows created"
   - Wizard closes automatically
   - Table refreshes (shows 2 new rows)

#### Test 5: Import with Validation Errors (Partial Success)

**Create test CSV:**
```bash
cat > test_import_partial.csv << 'EOF'
date,distance,fuel_type
2026-01-12,200,diesel
invalid_date,300,gasoline
EOF
```

**Test steps:**
1. Upload `test_import_partial.csv`
2. Complete Steps 1-2
3. Verify Step 3 shows: 2 total, 1 valid, 1 invalid
4. Click "Import"
5. **Verify:**
   - Warning notification: "Import completed with warnings: 1 created, 1 failed"
   - Wizard closes
   - Table refreshes (shows 1 new row)

#### Test 6: Import All Errors

**Create test CSV:**
```bash
cat > test_import_error.csv << 'EOF'
distance,fuel_type
100,diesel
150,gasoline
EOF
```

**Test steps:**
1. Upload `test_import_error.csv` (missing required "date" field)
2. Complete Steps 1-2
3. Verify Step 3 shows: 2 total, 0 valid, 2 invalid
4. Click "Import"
5. **Verify:**
   - Error notification: "Import failed: 2 rows had errors"
   - Wizard closes
   - Table unchanged (no new rows)

---

## Acceptance Criteria Checklist

**Integration (4):**
- [ ] BulkImportWizard imported from `'./import/BulkImportWizard'`
- [ ] Import button added to toolbar (Upload icon, outlined variant)
- [ ] Template button added to toolbar (Download icon, outlined variant)
- [ ] Buttons placed in same Box as Evidence button

**Import Flow (4):**
- [ ] Import button opens wizard modal
- [ ] Wizard receives props: open, onClose, tableId, fields, token, onImportComplete
- [ ] handleImportComplete calls fetchTable() to refresh
- [ ] Success notification shows created count

**Template Download (2):**
- [ ] Template button calls handleDownloadTemplate
- [ ] Browser download triggered with correct filename

**Notifications (3):**
- [ ] Success: "Import successful: X rows created" (green)
- [ ] Warning: "Import completed with warnings: X created, Y failed" (yellow)
- [ ] Error: "Import failed: X rows had errors" (red)

**Error Handling (2):**
- [ ] Template download errors caught and displayed
- [ ] Import completion errors from wizard handled

**UI/UX (3):**
- [ ] Buttons styled consistently (Import/Template outlined, Evidence filled)
- [ ] Wizard closes after successful import
- [ ] Table automatically refreshes after import

**Total: 18 Acceptance Criteria**

---

## Troubleshooting

### Issue: "Cannot find module './import/BulkImportWizard'"
**Solution:** Check file exists:
```bash
ls -la carbon-frontend/src/components/import/BulkImportWizard.jsx
```

### Issue: "UploadIcon is not defined"
**Solution:** Add import:
```javascript
import UploadIcon from '@mui/icons-material/Upload';
```

### Issue: Template download doesn't work
**Solution:** Check backend server is running and endpoint is accessible:
```bash
curl -X GET "http://localhost:8009/carbon-api/datarows/download-template/?data_table=1" \
  -H "Authorization: Token YOUR_TOKEN"
```

### Issue: Import doesn't refresh table
**Solution:** Verify `fetchTable()` function exists and is called in `handleImportComplete`.

### Issue: Buttons not showing
**Solution:** Check Box placement in JSX - should be before DataTableGrid component.

---

## Deliverables

1. **Modified File:**
   - `carbon-frontend/src/components/TableDataPage.jsx` (add ~100 lines)

2. **Test Results Document:**
   Create `PHASE3_A9_TEST_RESULTS.md`:
   ```markdown
   # Phase 3 - TableDataPage Integration Test Results

   ## Build Verification
   - ✅ Imports added (BulkImportWizard, UploadIcon, DownloadIcon)
   - ✅ State variable added (showImportWizard)
   - ✅ Handlers added (handleImportComplete, handleDownloadTemplate)
   - ✅ Buttons added to toolbar
   - ✅ BulkImportWizard component integrated
   - ✅ npm run build successful (0 errors)

   ## Browser Tests (6/6 PASS)
   - ✅ Test 1: Buttons render correctly
   - ✅ Test 2: Template download works
   - ✅ Test 3: Import wizard opens
   - ✅ Test 4: Complete import flow (success)
   - ✅ Test 5: Partial import (warnings)
   - ✅ Test 6: Import all errors

   ## Acceptance Criteria (18/18 ✅)
   - ✅ Integration: 4/4
   - ✅ Import Flow: 4/4
   - ✅ Template Download: 2/2
   - ✅ Notifications: 3/3
   - ✅ Error Handling: 2/2
   - ✅ UI/UX: 3/3

   ## Known Issues
   [None or list any issues]

   ## Next Steps
   - Proceed to Phase 4: Comprehensive Testing
   ```

3. **Git Commit:**
   ```bash
   git add carbon-frontend/src/components/TableDataPage.jsx
   git commit -m "feat(A9-P3): Integrate bulk import into TableDataPage

   - Add Import button with BulkImportWizard modal
   - Add Download Template button with API call
   - Handle import completion (refresh + notifications)
   - Success/warning/error notification logic
   - Buttons placed near Evidence button (consistent UX)

   Phase 3/5 complete. Next: Comprehensive testing.

   Relates-to: RUN-A9"
   ```

---

## Success Criteria

Phase 3 complete when:

1. ✅ All imports added
2. ✅ State variable added
3. ✅ handleImportComplete function added
4. ✅ handleDownloadTemplate function added
5. ✅ Buttons added to toolbar
6. ✅ BulkImportWizard component integrated
7. ✅ npm run build succeeds
8. ✅ All 6 browser tests pass
9. ✅ All 18 acceptance criteria met
10. ✅ Git commit completed

---

## Reference Materials

- **Task Summary:** [`TASK-A9-P3.md`](TASK-A9-P3.md:1)
- **Full Phase 3 Details:** [`TASK-A9-PHASE3.md`](TASK-A9-PHASE3.md:1) (464 lines)
- **BulkImportWizard Component:** [`carbon-frontend/src/components/import/BulkImportWizard.jsx`](carbon-frontend/src/components/import/BulkImportWizard.jsx:1)
- **Evidence Integration Pattern (A8):** [`TASK-RESULT-A8.md`](TASK-RESULT-A8.md:117) for reference
- **Backend API:** [`backend/dataschema/views.py`](backend/dataschema/views.py:134)

---

## Next Phase Preview

**Phase 4:** Comprehensive Testing
- Backend API tests (automated if possible, manual otherwise)
- Frontend component tests
- Integration tests (end-to-end flow)
- Browser testing (all scenarios)
- Performance testing
- Test results documentation

**Phase 5:** Documentation & Completion
- Update RUN_LOG.md
- Create TASK-RESULT-A9.md
- Git tag for release
- Architect validation

---

**Ready to execute Phase 3! Let's integrate the wizard! 🔗✨**
