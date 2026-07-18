# TASK A8 - PHASE 3: Integrate Modal into TableDataPage

**Phase:** 3 of 5  
**Objective:** Add evidence modal to data entry page  
**Estimated Time:** 20 minutes

---

## What to Build

Add a modal dialog to TableDataPage that shows evidence uploader and viewer when user selects a row and clicks "Evidence" button.

---

## Step-by-Step Instructions

### Step 1: Open TableDataPage

File: `carbon-frontend/src/components/TableDataPage.jsx`

### Step 2: Add Imports (at top of file, around line 1-20)

Add these imports:
```jsx
import { Dialog, DialogTitle, DialogContent, DialogActions, Divider, Chip } from '@mui/material';
import AttachFileIcon from '@mui/icons-material/AttachFile';
import EvidenceUploader from './evidence/EvidenceUploader';
import EvidenceViewer from './evidence/EvidenceViewer';
```

### Step 3: Add State Variables (around line 40-45, after existing state)

Add these state variables:
```jsx
const [selectedRowId, setSelectedRowId] = useState(null);
const [showEvidenceModal, setShowEvidenceModal] = useState(false);
const [evidenceRefreshKey, setEvidenceRefreshKey] = useState(0);
```

### Step 4: Add Row Selection Handler (around line 100-150, near other handlers)

Add this function:
```jsx
const handleRowSelection = (rowIds) => {
  setSelected(rowIds);
  if (rowIds.length === 1) {
    setSelectedRowId(rowIds[0]);
  } else {
    setSelectedRowId(null);
  }
};
```

### Step 5: Find the BulkActionBar Component

Search for `<BulkActionBar` in the file. You'll see it has props like `selected`, `onDelete`, etc.

### Step 6: Add Evidence Button (right before or after BulkActionBar)

Add this button:
```jsx
<Button
  startIcon={<AttachFileIcon />}
  onClick={() => setShowEvidenceModal(true)}
  disabled={!selectedRowId || selected.length !== 1}
  variant="outlined"
  size="small"
  sx={{ ml: 1 }}
>
  Evidence
</Button>
```

### Step 7: Add Modal Component (at the very end, before the final closing tags)

Find the last `</Box>` in the return statement and add this BEFORE it:

```jsx
      <Dialog
        open={showEvidenceModal}
        onClose={(event, reason) => {
          if (reason === 'backdropClick' || reason === 'escapeKeyDown') {
            return;
          }
          setShowEvidenceModal(false);
        }}
        maxWidth="md"
        fullWidth
        PaperProps={{
          sx: {
            minHeight: '60vh',
            maxHeight: '90vh',
            resize: 'both',
            overflow: 'auto'
          }
        }}
      >
        <DialogTitle>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="h6">Evidence Attachments</Typography>
            <Chip label={`Row ID: ${selectedRowId}`} size="small" color="primary" variant="outlined" />
          </Box>
        </DialogTitle>
        
        <DialogContent dividers>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            Upload supporting documents (invoices, receipts, photos, etc.) for audit verification.
          </Typography>
          
          <Box sx={{ mt: 2 }}>
            <EvidenceUploader
              dataRowId={selectedRowId}
              onUploadComplete={() => setEvidenceRefreshKey(prev => prev + 1)}
            />
          </Box>
          
          <Divider sx={{ my: 3 }} />
          
          <Typography variant="subtitle1" gutterBottom>Attached Evidence</Typography>
          
          <EvidenceViewer
            dataRowId={selectedRowId}
            key={evidenceRefreshKey}
            onDelete={() => setEvidenceRefreshKey(prev => prev + 1)}
          />
        </DialogContent>
        
        <DialogActions sx={{ px: 3, py: 2 }}>
          <Button onClick={() => setShowEvidenceModal(false)} variant="contained">
            Close
          </Button>
        </DialogActions>
      </Dialog>
```

### Step 8: Update DataTableGrid (if needed)

Find the `<DataTableGrid` component. Make sure it has:
```jsx
onRowSelectionModelChange={handleRowSelection}
checkboxSelection
```

If these props are missing, add them.

---

## Visual Guide

Your TableDataPage structure should look like this:

```jsx
export default function TableDataPage({ ... }) {
  // State variables
  const [fields, setFields] = useState([]);
  const [selectedRowId, setSelectedRowId] = useState(null);  // NEW
  const [showEvidenceModal, setShowEvidenceModal] = useState(false);  // NEW
  const [evidenceRefreshKey, setEvidenceRefreshKey] = useState(0);  // NEW
  
  // Handlers
  const handleRowSelection = (rowIds) => { ... };  // NEW
  
  return (
    <Box>
      {/* Toolbar with buttons */}
      <BulkActionBar ... />
      <Button ... >Evidence</Button>  {/* NEW */}
      
      {/* Data grid */}
      <DataTableGrid
        onRowSelectionModelChange={handleRowSelection}  {/* NEW */}
        ...
      />
      
      {/* Modal */}
      <Dialog ... >...</Dialog>  {/* NEW */}
    </Box>
  );
}
```

---

## Test Phase 3

```bash
cd carbon-frontend
npm run build
```

Then manually test:
1. Start backend: `cd backend && python manage.py runserver`
2. Start frontend: `cd carbon-frontend && npm run dev`
3. Login and navigate to data entry page
4. Select a single row (checkbox)
5. Click "Evidence" button
6. Modal should open

---

## Acceptance Criteria

- [ ] Evidence button appears in TableDataPage
- [ ] Button disabled when no row selected
- [ ] Button enabled when 1 row selected
- [ ] Modal opens when button clicked
- [ ] Modal shows Row ID in header
- [ ] Modal does NOT close when clicking outside
- [ ] Close button works
- [ ] Build completes without errors

---

## Next Step

When Phase 3 is complete, report back: "Phase 3 complete. Ready for Phase 4."
