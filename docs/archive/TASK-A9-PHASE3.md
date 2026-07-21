# TASK A9 - PHASE 3: TableDataPage Integration

**Phase:** 3 of 5  
**Focus:** Frontend Integration - Add Import/Template Buttons  
**Duration:** Step-by-step execution

---

## Objective

Integrate the `BulkImportWizard` component into [`TableDataPage.jsx`](carbon-frontend/src/components/TableDataPage.jsx) by adding Import and Template buttons to the toolbar. Handle import completion with table refresh and user notifications.

---

## Scope - IN

✅ Add Import button to TableDataPage toolbar  
✅ Add Download Template button to TableDataPage toolbar  
✅ Integrate `BulkImportWizard` component  
✅ Handle import completion (refresh table, show summary)  
✅ Handle template download (API call, trigger browser download)  
✅ Success/error notifications  
✅ Button placement near Evidence button

---

## Scope - OUT

❌ Bulk import wizard UI (Phase 2 complete)  
❌ Backend API (Phase 1 complete)  
❌ Advanced import options (update mode, scheduled imports)  
❌ Import history UI

---

## Preconditions

1. Phase 1 complete (backend API)
2. Phase 2 complete (`BulkImportWizard` component)
3. [`TableDataPage.jsx`](carbon-frontend/src/components/TableDataPage.jsx) exists
4. Evidence button already integrated (A8)

---

## Implementation Steps

### Step 1: Import BulkImportWizard Component

**File:** `carbon-frontend/src/components/TableDataPage.jsx`

**Task:** Add import statements at the top

**Code to Add:**

```javascript
// Add these imports (after existing imports, around line 15-20)
import { BulkImportWizard } from './import';
import UploadIcon from '@mui/icons-material/Upload';
import DownloadIcon from '@mui/icons-material/Download';
```

**Location:** After existing imports (after `AttachFileIcon`, before component definition)

---

### Step 2: Add State for Import Wizard

**File:** `carbon-frontend/src/components/TableDataPage.jsx`

**Task:** Add state variable for wizard visibility

**Code to Add:**

```javascript
// Add this state variable (around line 48, after evidenceRefreshKey state)
const [showImportWizard, setShowImportWizard] = useState(false);
```

**Location:** Inside `TableDataPage` function, after other `useState` declarations

---

### Step 3: Add Import Completion Handler

**File:** `carbon-frontend/src/components/TableDataPage.jsx`

**Task:** Add handler for import completion callback

**Code to Add:**

```javascript
// Add this handler (after handleRowSelection, around line 212)
const handleImportComplete = (result) => {
  const { created, failed, errors } = result;
  
  if (failed === 0) {
    notify({
      message: `Import successful: ${created} rows created`,
      type: 'success'
    });
  } else if (created === 0) {
    notify({
      message: `Import failed: ${failed} rows had errors`,
      type: 'error'
    });
  } else {
    notify({
      message: `Import partial: ${created} created, ${failed} failed`,
      type: 'warning'
    });
  }
  
  // Refresh table data
  fetchRows();
};
```

**Location:** After `handleRowSelection` function, before `return` statement

---

### Step 4: Add Template Download Handler

**File:** `carbon-frontend/src/components/TableDataPage.jsx`

**Task:** Add handler for template download

**Code to Add:**

```javascript
// Add this handler (after handleImportComplete)
const handleDownloadTemplate = async () => {
  try {
    const response = await fetch(
      `${API_BASE_URL}/carbon-api/datarows/download-template/?data_table=${tableId}`,
      {
        method: 'GET',
        headers: {
          'Authorization': `Token ${token}`
        }
      }
    );
    
    if (!response.ok) {
      throw new Error('Failed to download template');
    }
    
    // Get filename from response headers or use default
    const contentDisposition = response.headers.get('Content-Disposition');
    let filename = 'template.csv';
    if (contentDisposition) {
      const filenameMatch = contentDisposition.match(/filename="?([^"]+)"?/);
      if (filenameMatch) {
        filename = filenameMatch[1];
      }
    }
    
    // Download file
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
    
    notify({
      message: 'Template downloaded successfully',
      type: 'success'
    });
  } catch (err) {
    handleError(err, 'Failed to download template');
  }
};
```

**Location:** After `handleImportComplete` function

---

### Step 5: Add Import and Template Buttons to UI

**File:** `carbon-frontend/src/components/TableDataPage.jsx`

**Task:** Add buttons to toolbar (before Evidence button)

**Find this code (around line 225-234):**

```jsx
<Button
  startIcon={<AttachFileIcon />}
  onClick={() => setShowEvidenceModal(true)}
  disabled={!selectedRowId || selected.length !== 1}
  variant="outlined"
  size="small"
  sx={{ ml: 1, mb: 2 }}
>
  Evidence
</Button>
```

**Replace with:**

```jsx
<Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
  <Button
    startIcon={<UploadIcon />}
    onClick={() => setShowImportWizard(true)}
    variant="outlined"
    size="small"
  >
    Import
  </Button>

  <Button
    startIcon={<DownloadIcon />}
    onClick={handleDownloadTemplate}
    variant="outlined"
    size="small"
  >
    Template
  </Button>

  <Button
    startIcon={<AttachFileIcon />}
    onClick={() => setShowEvidenceModal(true)}
    disabled={!selectedRowId || selected.length !== 1}
    variant="outlined"
    size="small"
  >
    Evidence
  </Button>
</Box>
```

**Location:** After `BulkActionBar`, before `DataTableGrid` (around line 224-234)

---

### Step 6: Add BulkImportWizard Component

**File:** `carbon-frontend/src/components/TableDataPage.jsx`

**Task:** Add wizard component at end of component (before closing `</Box>`)

**Find this code (around line 313-318, end of component):**

```jsx
      </Dialog>
    </Box>
  );
}
```

**Add before the closing `</Box>` tag:**

```jsx
      </Dialog>

      <BulkImportWizard
        open={showImportWizard}
        onClose={() => setShowImportWizard(false)}
        tableId={tableId}
        fields={fields}
        token={token}
        onImportComplete={handleImportComplete}
      />
    </Box>
  );
}
```

**Location:** After Evidence `Dialog` component, before final closing `</Box>`

---

### Step 7: Add API_BASE_URL Import

**File:** `carbon-frontend/src/components/TableDataPage.jsx`

**Task:** Ensure API_BASE_URL is imported (if not already)

**Check for this at the top:**

```javascript
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8009';
```

**If not present, add after imports (around line 20-25):**

```javascript
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8009';
```

---

### Step 8: Verify File Structure

**Task:** Confirm component structure is correct

**Expected Structure:**

```jsx
export default function TableDataPage({ ... }) {
  // State declarations
  const [showEvidenceModal, setShowEvidenceModal] = useState(false);
  const [showImportWizard, setShowImportWizard] = useState(false);
  
  // Handlers
  const handleImportComplete = (result) => { ... };
  const handleDownloadTemplate = async () => { ... };
  
  return (
    <Box>
      <Typography variant="h5">...</Typography>
      
      <BulkActionBar ... />
      
      {/* Import, Template, Evidence Buttons */}
      <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
        <Button startIcon={<UploadIcon />} ...>Import</Button>
        <Button startIcon={<DownloadIcon />} ...>Template</Button>
        <Button startIcon={<AttachFileIcon />} ...>Evidence</Button>
      </Box>
      
      <DataTableGrid ... />
      
      {/* Evidence Modal */}
      <Dialog open={showEvidenceModal} ...>
        ...
      </Dialog>
      
      {/* Import Wizard */}
      <BulkImportWizard
        open={showImportWizard}
        onClose={() => setShowImportWizard(false)}
        tableId={tableId}
        fields={fields}
        token={token}
        onImportComplete={handleImportComplete}
      />
    </Box>
  );
}
```

---

### Step 9: Test Integration

**Task:** Manual browser testing

**Test Steps:**

1. **Start Dev Server:**
   ```bash
   cd carbon-frontend
   npm run dev
   ```

2. **Navigate to Data Entry:**
   - Login to application
   - Go to Data Hub → Data Entry
   - Select a module and table

3. **Test Template Download:**
   - Click "Template" button
   - Verify CSV file downloads
   - Open CSV, verify headers match table fields

4. **Test Import Button:**
   - Click "Import" button
   - Verify wizard modal opens
   - Verify 3-step stepper visible
   - Click Cancel, verify modal closes

5. **Test Import Flow (if Phase 2 complete):**
   - Click "Import" button
   - Upload CSV file (use downloaded template)
   - Verify Step 2 shows column mapping
   - Verify Step 3 shows validation
   - Click Import
   - Verify success notification
   - Verify table refreshes with new rows

6. **Check Console:**
   - Open DevTools (F12)
   - Verify no errors in Console
   - Verify no errors in Network tab

---

## Acceptance Criteria

- [ ] Import button added to TableDataPage toolbar
- [ ] Template button added to TableDataPage toolbar
- [ ] Buttons appear before Evidence button
- [ ] Import button opens `BulkImportWizard` modal
- [ ] Template button downloads CSV file
- [ ] Import completion refreshes table data
- [ ] Import completion shows notification (success/warning/error)
- [ ] Notification message includes row counts
- [ ] Template download triggers browser download
- [ ] Template filename is correct (table_name_template.csv)
- [ ] No console errors
- [ ] Frontend builds without errors

**Total: 12 Acceptance Criteria**

---

## Verification Checklist

Before proceeding to Phase 4:

- [ ] Code added to `TableDataPage.jsx`:
  - [ ] Imports added
  - [ ] State variable added
  - [ ] Handlers added (2 functions)
  - [ ] Buttons added to UI
  - [ ] BulkImportWizard component added
- [ ] Frontend builds: `npm run build` (no errors)
- [ ] Dev server runs: `npm run dev` (no errors)
- [ ] Browser testing:
  - [ ] Import button visible
  - [ ] Template button visible
  - [ ] Import button opens modal
  - [ ] Template button downloads file
  - [ ] Modal closes correctly
- [ ] No console errors in DevTools
- [ ] Table refresh works after import

---

## Common Issues & Fixes

### Issue 1: "BulkImportWizard is not defined"
**Fix:** Verify import statement uses correct path:
```javascript
import { BulkImportWizard } from './import';
```

### Issue 2: Template download fails (404)
**Fix:** Verify backend Phase 1 complete and server running on correct port (8009)

### Issue 3: Import button doesn't open modal
**Fix:** Check `showImportWizard` state and `onClick` handler:
```javascript
onClick={() => setShowImportWizard(true)}
```

### Issue 4: Table doesn't refresh after import
**Fix:** Verify `handleImportComplete` calls `fetchRows()`

---

## Next Phase

✅ Phase 3 Complete → Proceed to **Phase 4: Testing & Validation**

Phase 4 will add comprehensive tests (backend API, frontend components, integration) and perform end-to-end validation.
