# TASK: RUN A9 - PHASE 3 - TableDataPage Integration

## Context

You are executing **Phase 3 of 5** for RUN A9 (Bulk Import/Export).

**Phase 1 Status:** ✅ Complete (Backend API)
**Phase 2 Status:** ✅ Complete (BulkImportWizard component - 501 lines)

**Phase 3 Objective:** Integrate BulkImportWizard into TableDataPage with Import and Template buttons.

---

## Objective

Modify [`TableDataPage.jsx`](carbon-frontend/src/components/TableDataPage.jsx) to add:

1. **Import Button** - Opens BulkImportWizard modal
2. **Download Template Button** - Downloads CSV template for the table
3. **Import Completion Handler** - Refreshes grid and shows notifications
4. **Template Download Handler** - Triggers browser download

---

## Scope - IN

✅ Add Import button to toolbar (next to Evidence button)  
✅ Add Download Template button to toolbar  
✅ Import `BulkImportWizard` component  
✅ Handle import completion (refresh table, notifications)  
✅ Handle template download API call  
✅ Success/warning/error notifications  
✅ Button placement and styling consistent with A8 Evidence button

---

## Scope - OUT

❌ Wizard UI changes (Phase 2 complete)  
❌ Backend API changes (Phase 1 complete)  
❌ Advanced import options  
❌ Import history UI  
❌ Bulk update mode

---

## Prerequisites

1. Phase 1 complete: Backend endpoints working
2. Phase 2 complete: `BulkImportWizard.jsx` exists and tested
3. `TableDataPage.jsx` exists with Evidence button (from A8)
4. Frontend dev server can run

---

## Implementation Steps

### Step 1: Add Imports

**File:** `carbon-frontend/src/components/TableDataPage.jsx`

**Location:** Top of file, after existing imports

**Code to Add:**

```javascript
import BulkImportWizard from './import/BulkImportWizard';
import UploadIcon from '@mui/icons-material/Upload';
import DownloadIcon from '@mui/icons-material/Download';
```

---

### Step 2: Add State for Wizard Visibility

**Location:** Inside `TableDataPage` function, after existing `useState` declarations

**Code to Add:**

```javascript
const [showImportWizard, setShowImportWizard] = useState(false);
```

---

### Step 3: Add Import Completion Handler

**Location:** After `handleRowSelection` function

**Code to Add:**

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

---

### Step 4: Add Template Download Handler

**Location:** After `handleImportComplete` function

**Code to Add:**

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

---

### Step 5: Add Buttons to Toolbar

**Location:** Find the section with Evidence button (from A8), add Import and Template buttons before it

**Code Pattern:** Look for this section in TableDataPage.jsx:

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

**Replace with:**

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

---

### Step 6: Add BulkImportWizard Component

**Location:** At the end of the component, after `EvidenceModal`

**Code to Add:**

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

---

## Verification Steps

### Step 1: Build Verification

```bash
cd carbon-frontend && npm run build
```

**Expected:** No errors

---

### Step 2: Manual Browser Testing

**Test 1: Buttons Render**

1. Navigate to any table in Data Hub
2. **Verify:**
   - Import button visible (Upload icon)
   - Template button visible (Download icon)
   - Evidence button visible (from A8)
   - Buttons aligned horizontally

**Test 2: Template Download**

1. Click "Template" button
2. **Verify:**
   - CSV file downloads
   - Filename: `{table_name}_template.csv`
   - File contains field headers
   - Success notification appears

**Test 3: Import Wizard Opens**

1. Click "Import" button
2. **Verify:**
   - BulkImportWizard modal opens
   - Stepper shows 3 steps
   - File upload UI visible

**Test 4: Complete Import Flow**

1. Click "Import"
2. Upload valid CSV file (Step 1)
3. Verify column mapping (Step 2)
4. Validate preview (Step 3)
5. Click "Import"
6. **Verify:**
   - Success notification: "Import successful: X rows created"
   - Table refreshes automatically
   - New rows visible in grid
   - Wizard closes

**Test 5: Import with Errors**

1. Upload CSV with validation errors
2. Complete wizard to Step 3
3. Click "Import"
4. **Verify:**
   - Warning notification: "X created, Y failed"
   - Table refreshes (only valid rows added)
   - Wizard closes

**Test 6: Import All Errors**

1. Upload CSV missing required fields
2. Complete wizard
3. **Verify:**
   - Error notification: "Import failed: X rows had errors"
   - Table unchanged
   - Wizard closes

---

## Acceptance Criteria

### Integration (4 criteria)
- [ ] BulkImportWizard imported correctly
- [ ] Import button added to toolbar
- [ ] Template button added to toolbar
- [ ] Buttons placed near Evidence button (consistent with A8)

### Import Flow (4 criteria)
- [ ] Import button opens BulkImportWizard modal
- [ ] Wizard receives correct props (tableId, fields, token)
- [ ] Import completion handler refreshes table
- [ ] Success notification shows created count

### Template Download (2 criteria)
- [ ] Template button calls download API
- [ ] Browser download triggered with correct filename

### Notifications (3 criteria)
- [ ] Success: All rows imported (green)
- [ ] Warning: Partial import (yellow)
- [ ] Error: No rows imported (red)

### Error Handling (2 criteria)
- [ ] Template download errors caught
- [ ] Import errors passed from wizard

### UI/UX (3 criteria)
- [ ] Buttons styled consistently
- [ ] Loading states during operations
- [ ] Modal closes after successful import

**Total: 18 Acceptance Criteria**

---

## Deliverables

1. **Modified File:**
   - `carbon-frontend/src/components/TableDataPage.jsx` (add ~100 lines)

2. **Test Results:**
   - 6 browser tests passed
   - 18 acceptance criteria met

3. **Git Commit:**
   ```bash
   git add carbon-frontend/src/components/TableDataPage.jsx
   git commit -m "feat(A9-P3): Integrate bulk import into TableDataPage

   - Add Import button with BulkImportWizard modal
   - Add Download Template button with API call
   - Handle import completion (refresh + notifications)
   - Success/warning/error notification logic
   - Buttons placed near Evidence button (consistent UX)

   Phase 3/5 complete. Next: Testing & validation.

   Relates-to: RUN-A9"
   ```

---

## Next Phase

After Phase 3 completion:
- **Phase 4:** Comprehensive Testing (backend + frontend + integration + browser)
- **Phase 5:** Documentation (RUN_LOG update, TASK-RESULT-A9)

---

## Reference Files

- **Phase 3 Full Details:** [`TASK-A9-PHASE3.md`](TASK-A9-PHASE3.md:1) (464 lines with detailed code)
- **BulkImportWizard Component:** [`carbon-frontend/src/components/import/BulkImportWizard.jsx`](carbon-frontend/src/components/import/BulkImportWizard.jsx:1)
- **Backend API:** [`backend/dataschema/views.py`](backend/dataschema/views.py:134) (bulk_import, download_template)
- **Evidence Integration Pattern (A8):** [`TASK-RESULT-A8.md`](TASK-RESULT-A8.md:117) for button placement reference

---

## Success Criteria

Phase 3 is complete when:

1. ✅ All imports added
2. ✅ State variables added
3. ✅ Handler functions implemented
4. ✅ Buttons added to toolbar
5. ✅ BulkImportWizard integrated
6. ✅ npm run build succeeds
7. ✅ All 6 browser tests pass
8. ✅ All 18 acceptance criteria met
9. ✅ Git commit completed

---

## Notes

- Follow A8 Evidence button pattern for consistent UX
- Import and Template buttons use `variant="outlined"` to differentiate from primary Evidence button
- Template download uses browser download (not save dialog)
- Table refresh via existing `fetchTable()` function
- Notifications via existing `notify()` function
- Error handling matches A8 patterns

**Ready for Phase 3 integration! 🔗**
