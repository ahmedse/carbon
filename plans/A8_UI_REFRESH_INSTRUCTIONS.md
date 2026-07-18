# RUN A8: Evidence Button - UI Refresh Instructions

## Current Status
✅ **Code Implementation: COMPLETE** (Phase 4 passed 29/29 tests)  
❌ **UI Visibility: NOT VISIBLE** (dev server needs restart)

## Problem
The Evidence button is implemented in [`TableDataPage.jsx`](../carbon-frontend/src/components/TableDataPage.jsx:225-234) but not visible in the running application because the frontend dev server hasn't reloaded the changes.

## Solution: Restart Frontend Dev Server

### Step 1: Stop Current Dev Server
```bash
# Find the terminal running the frontend dev server
# Press Ctrl+C to stop it
```

### Step 2: Restart Frontend
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npm run dev
```

### Step 3: Hard Refresh Browser
- **Windows/Linux**: `Ctrl + Shift + R`
- **Mac**: `Cmd + Shift + R`
- **Alternative**: Open DevTools (F12) → Right-click refresh button → "Empty Cache and Hard Reload"

### Step 4: Verify Evidence Button Appears

1. Navigate to Data Hub → Data Entry
2. Select a module and table
3. **Select a single row** using the checkbox (critical!)
4. Look for "Evidence" button next to Bulk Action Bar
5. Button should be:
   - **Enabled** when 1 row selected
   - **Disabled** when 0 or >1 rows selected

## Evidence Button Location

```jsx
// carbon-frontend/src/components/TableDataPage.jsx:225-234
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

**Location**: Appears immediately after [`BulkActionBar`](../carbon-frontend/src/components/TableDataPage.jsx:219-223), before [`DataTableGrid`](../carbon-frontend/src/components/TableDataPage.jsx:236)

## Expected Behavior

### When Button is Clicked:
1. Non-dismissible modal opens (can't close via backdrop/ESC)
2. Modal shows:
   - Row ID chip (context)
   - Evidence uploader (drag-and-drop)
   - Evidence viewer (list of attachments)
3. Modal is resizable (grab corners)
4. Close only via "X" button or Cancel

### Test Workflow:
1. Select single row → Evidence button enabled
2. Click Evidence → Modal opens
3. Drag file to upload zone → File uploads
4. See uploaded file in list below
5. Download or delete evidence
6. Click X to close modal

## Backend Verification

Ensure backend is running and evidence endpoints are available:

```bash
# Check Django dev server is running
# Should see evidence app endpoints registered

# Test evidence endpoint
curl -H "Authorization: Token <your-token>" \
  http://localhost:8000/carbon-api/evidence/
```

## Troubleshooting

### Issue: Button still not visible after restart
**Solution**: Check if [`TableDataPage.jsx`](../carbon-frontend/src/components/TableDataPage.jsx:225-234) changes are saved. Re-read the file to confirm Evidence button code is present.

### Issue: Button visible but disabled
**Solution**: You must select **exactly 1 row** using checkboxes. Button is disabled for 0 or >1 rows.

### Issue: Button visible but clicking does nothing
**Solution**: Check browser console for errors. Verify [`EvidenceUploader`](../carbon-frontend/src/components/evidence/EvidenceUploader.jsx) and [`EvidenceViewer`](../carbon-frontend/src/components/evidence/EvidenceViewer.jsx) components exist.

### Issue: Modal opens but shows errors
**Solution**: 
- Verify backend evidence endpoints: `http://localhost:8000/carbon-api/evidence/`
- Check authentication token is being passed
- Check browser console for API errors

### Issue: File upload fails
**Solution**:
- Check file size (max 50MB)
- Check file type (PDF, images, Office docs allowed)
- Check `MEDIA_ROOT` setting in Django settings
- Check `backend/mediafiles/evidence/` directory exists and is writable

## Next Step: Phase 5 Documentation

Once UI is confirmed working:
1. Update [`RUN_LOG.md`](../docs/RUN_LOG.md) with completion status
2. Create [`TASK-RESULT-A8.md`](../TASK-RESULT-A8.md) with deliverables
3. Request Architect validation

## References

- Implementation: [`TableDataPage.jsx:225-234`](../carbon-frontend/src/components/TableDataPage.jsx:225-234)
- Modal: [`TableDataPage.jsx:259-313`](../carbon-frontend/src/components/TableDataPage.jsx:259-313)
- Uploader: [`EvidenceUploader.jsx`](../carbon-frontend/src/components/evidence/EvidenceUploader.jsx)
- Viewer: [`EvidenceViewer.jsx`](../carbon-frontend/src/components/evidence/EvidenceViewer.jsx)
- Backend: [`backend/evidence/views.py`](../backend/evidence/views.py)
- Tests: [`PHASE4_TEST_RESULTS.md`](../PHASE4_TEST_RESULTS.md) - 29/29 PASS
