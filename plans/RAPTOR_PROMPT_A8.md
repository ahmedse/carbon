the # Raptor Execution Prompt for RUN A8: Evidence & Attachments

**Mode:** Code  
**Priority:** CRITICAL  
**Implementation Plan:** `plans/RUN_A8_EVIDENCE_ATTACHMENTS_v2.md`

---

## Task Summary

Implement evidence file attachment system for the Carbon Data Trust Platform. This enables users to upload supporting documents (invoices, receipts, photos, PDFs) to data rows for audit verification.

**Why Critical:** Platform cannot be used for audited emissions reporting without evidence attachments.

---

## Implementation Instructions

Follow the detailed plan in `plans/RUN_A8_EVIDENCE_ATTACHMENTS_v2.md` which includes:
- Complete backend code (Django models, serializers, views, permissions)
- Complete frontend code (React components with drag-and-drop)
- Integration code for TableDataPage
- Test commands and acceptance criteria

### Phase 1: Backend Setup

**Create the evidence Django app:**

1. Create directory structure:
```bash
mkdir -p backend/evidence
touch backend/evidence/__init__.py
touch backend/evidence/apps.py
touch backend/evidence/models.py
touch backend/evidence/serializers.py
touch backend/evidence/views.py
touch backend/evidence/permissions.py
touch backend/evidence/urls.py
touch backend/evidence/admin.py
```

2. Copy code from plan sections:
   - Evidence model → `backend/evidence/models.py`
   - Serializers → `backend/evidence/serializers.py`
   - ViewSet → `backend/evidence/views.py`
   - Permissions → `backend/evidence/permissions.py`
   - URLs → `backend/evidence/urls.py`
   - Admin → `backend/evidence/admin.py`

3. Create `backend/evidence/apps.py`:
```python
from django.apps import AppConfig

class EvidenceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'evidence'
```

4. Update `backend/config/settings.py`:
```python
INSTALLED_APPS = [
    # ... existing apps ...
    'evidence',
]

# Add media storage config
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'

# File upload settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 52428800  # 50MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 52428800  # 50MB
```

5. Update `backend/config/urls.py`:
```python
urlpatterns = [
    # ... existing patterns ...
    path('carbon-api/', include('evidence.urls')),
]
```

6. Run migrations:
```bash
cd backend
python manage.py makemigrations evidence
python manage.py migrate evidence
```

7. Test backend API:
```bash
# Start server if not running
python manage.py runserver

# Test in another terminal (replace <token> with actual JWT token)
curl -X GET "http://localhost:8000/carbon-api/evidence/" \
  -H "Authorization: Bearer <token>"
```

### Phase 2: Frontend Components

1. Create evidence components directory:
```bash
mkdir -p carbon-frontend/src/components/evidence
```

2. Install react-dropzone dependency:
```bash
cd carbon-frontend
npm install react-dropzone
```

3. Create components:
   - Copy EvidenceUploader code → `carbon-frontend/src/components/evidence/EvidenceUploader.jsx`
   - Copy EvidenceViewer code → `carbon-frontend/src/components/evidence/EvidenceViewer.jsx`

### Phase 3: Integration with TableDataPage

Modify `carbon-frontend/src/components/TableDataPage.jsx`:

1. Add imports at top (around line 5-18):
```jsx
import { Dialog, DialogTitle, DialogContent, DialogActions, Divider, Chip } from '@mui/material';
import AttachFileIcon from '@mui/icons-material/AttachFile';
import EvidenceUploader from './evidence/EvidenceUploader';
import EvidenceViewer from './evidence/EvidenceViewer';
```

2. Add state variables (around line 37-43):
```jsx
const [selectedRowId, setSelectedRowId] = useState(null);
const [showEvidenceModal, setShowEvidenceModal] = useState(false);
const [evidenceRefreshKey, setEvidenceRefreshKey] = useState(0);
```

3. Add row selection handler:
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

4. Find the toolbar section with existing buttons (search for "BulkActionBar" or button group) and add Evidence button:
```jsx
<Button
  startIcon={<AttachFileIcon />}
  onClick={() => setShowEvidenceModal(true)}
  disabled={!selectedRowId || selected.length !== 1}
  variant="outlined"
  size="small"
>
  Evidence
</Button>
```

5. Add modal component at the end (before the closing `</Box>` of the main return statement):
```jsx
<Dialog
  open={showEvidenceModal}
  onClose={(event, reason) => {
    // Prevent closing on backdrop click or ESC
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
      <Typography variant="h6">
        Evidence Attachments
      </Typography>
      <Chip 
        label={`Row ID: ${selectedRowId}`} 
        size="small" 
        color="primary" 
        variant="outlined" 
      />
    </Box>
  </DialogTitle>
  
  <DialogContent dividers>
    <Typography variant="body2" color="text.secondary" gutterBottom>
      Upload supporting documents (invoices, receipts, photos, etc.) for audit verification.
    </Typography>
    
    <Box sx={{ mt: 2 }}>
      <EvidenceUploader
        dataRowId={selectedRowId}
        onUploadComplete={() => {
          setEvidenceRefreshKey(prev => prev + 1);
        }}
      />
    </Box>
    
    <Divider sx={{ my: 3 }} />
    
    <Typography variant="subtitle1" gutterBottom>
      Attached Evidence
    </Typography>
    
    <EvidenceViewer
      dataRowId={selectedRowId}
      key={evidenceRefreshKey}
      onDelete={() => setEvidenceRefreshKey(prev => prev + 1)}
    />
  </DialogContent>
  
  <DialogActions sx={{ px: 3, py: 2 }}>
    <Button 
      onClick={() => setShowEvidenceModal(false)}
      variant="contained"
    >
      Close
    </Button>
  </DialogActions>
</Dialog>
```

6. Update the DataGrid component to handle row selection - find the DataTableGrid or DataGrid component and ensure it has:
```jsx
onRowSelectionModelChange={handleRowSelection}
checkboxSelection
```

### Phase 4: Testing

1. Build frontend:
```bash
cd carbon-frontend
npm run build
```

2. Manual testing checklist:
   - [ ] Navigate to data entry page
   - [ ] Select a single row (checkbox)
   - [ ] Click "Evidence" button
   - [ ] Modal opens (does NOT close when clicking outside)
   - [ ] Drag and drop a PDF file
   - [ ] Upload succeeds, file appears in list
   - [ ] Download file works
   - [ ] Delete file works (with confirmation)
   - [ ] Close button closes modal
   - [ ] Test with multiple file types (PDF, JPG, Excel, CSV)
   - [ ] Test file size limit (try 60MB file, should reject)
   - [ ] Test permissions (data owner can access their module's evidence only)

### Phase 5: Documentation

1. Update `docs/RUN_LOG.md` - add A8 entry after A7:
```markdown
### A8: Evidence & Attachments (2026-07-18) ✅

**Objective:** Enable users to attach evidence files to data rows for audit verification

**Changes:**
- Created `backend/evidence/` app with Evidence model
- Implemented file upload API with bulk-upload support
- Created EvidenceUploader component (drag-and-drop)
- Created EvidenceViewer component (list/download/delete)
- Integrated modal into TableDataPage
- Non-dismissible modal (prevents accidental closure)
- Resizable modal dialog
- File types: PDF, JPG, PNG, Excel, CSV, Word, ZIP
- Max file size: 50MB

**Files Created:**
- backend/evidence/*.py (8 files)
- carbon-frontend/src/components/evidence/EvidenceUploader.jsx
- carbon-frontend/src/components/evidence/EvidenceViewer.jsx

**Files Modified:**
- backend/config/settings.py (added evidence app, media config)
- backend/config/urls.py (added evidence URLs)
- carbon-frontend/src/components/TableDataPage.jsx (integrated modal)

**Migrations:**
- 0001_initial (Evidence model)

**Dependencies Added:**
- react-dropzone (frontend)

**Testing:**
- ✅ Upload single file
- ✅ Upload multiple files (bulk)
- ✅ Download evidence
- ✅ Delete evidence (soft delete)
- ✅ Modal prevents backdrop close
- ✅ Permissions enforced (RBAC)
- ✅ File type validation
- ✅ File size limit (50MB)

**Status:** Complete - Platform now supports evidence attachments for audit readiness
```

2. Create `TASK-RESULT-A8.md` with detailed test results and screenshots

---

## Key Requirements

**UX Requirements (User Specified):**
- ✅ Modal (not drawer)
- ✅ Resizable
- ✅ Does NOT close when clicking outside
- ✅ Explicit "Close" button
- ✅ Show Row ID for context

**Technical Requirements:**
- ✅ Drag-and-drop file upload
- ✅ Multiple file upload (bulk)
- ✅ File type restrictions (PDF, images, Office docs)
- ✅ Max file size: 50MB
- ✅ RBAC permissions (users access only their modules' evidence)
- ✅ Soft delete (audit trail)
- ✅ Download support

---

## Acceptance Criteria

All items in "Definition of Done" section of `plans/RUN_A8_EVIDENCE_ATTACHMENTS_v2.md` must pass.

**Critical tests:**
1. Modal does NOT close when clicking backdrop (user requirement)
2. Upload works via drag-and-drop
3. Upload works via browse button
4. File type validation works (reject .exe, .sh, etc.)
5. File size validation works (reject >50MB)
6. Download returns correct file
7. Delete soft-deletes (is_deleted=True, not actual deletion)
8. Permissions: data-owner can only access evidence from their modules

---

## Error Handling

If you encounter errors:

1. **Migration errors:** Check that dataschema app exists and has DataRow model
2. **Import errors:** Verify all imports use correct paths
3. **Auth errors:** Ensure useAuth hook returns token
4. **CORS errors:** Backend should have django-cors-headers configured
5. **File upload errors:** Check MEDIA_ROOT directory exists and is writable

---

## Notes

- All code is provided in the plan document - copy verbatim
- Follow the 5-phase sequence in order
- Test after each phase before moving to next
- Modal approach chosen over drawer per user feedback
- This is CRITICAL priority - required for audit readiness
- Backend uses soft delete (is_deleted flag) to maintain audit trail

---

## Success Metrics

- [ ] Backend API responds to GET/POST/DELETE evidence endpoints
- [ ] Frontend builds without errors
- [ ] Modal opens and displays evidence components
- [ ] File upload works (drag-and-drop and browse)
- [ ] Modal does NOT close on backdrop click
- [ ] Evidence list displays uploaded files
- [ ] Download and delete functions work
- [ ] All acceptance criteria pass

---

**Start with Phase 1 (Backend Setup). Work through each phase sequentially. Report progress after each phase completion.**
