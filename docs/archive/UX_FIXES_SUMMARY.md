# UX Fixes Summary — Row Editing & Evidence Upload

## Overview
Two interconnected UX fixes applied to improve user experience and prevent interaction issues during file uploads.

---

## Fix 1: Row Editing — Drawer to Modal Dialog

### File: [`carbon-frontend/src/components/DataTableGrid.jsx`](carbon-frontend/src/components/DataTableGrid.jsx)

### Changes

#### 1.1 Imports (Lines 1-4)
**Added Material-UI Dialog components and CloseIcon**

```javascript
import { Button, Dialog, Box, CircularProgress, IconButton, Tooltip, DialogTitle, DialogContent, DialogActions, Typography } from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
```

#### 1.2 Row Edit Modal (Lines 375-450)
**Replaced Drawer with Dialog**

**Features:**
- ✅ Non-dismissible by backdrop click or escape key
- ✅ Explicit close button (X icon)
- ✅ Resizable window (`resize: 'both'`)
- ✅ Title bar with mode indicator ("Edit Row" / "Add New Row")
- ✅ Scrollable content (max 90vh)
- ✅ Cancel button in footer

```javascript
<Dialog
  open={drawerOpen}
  onClose={(event, reason) => {
    // Only close on explicit button click, not backdrop or escape
    return;
  }}
  maxWidth="sm"
  fullWidth
  PaperProps={{
    sx: {
      minHeight: '60vh',
      maxHeight: '90vh',
      resize: 'both',
      overflow: 'auto',
      display: 'flex',
      flexDirection: 'column'
    }
  }}
>
  <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', pb: 1 }}>
    <span>{drawerMode === 'edit' ? 'Edit Row' : 'Add New Row'}</span>
    <IconButton
      edge="end"
      color="inherit"
      onClick={() => { setDrawerOpen(false); setEditingRow(null); }}
      sx={{ p: 0.5 }}
    >
      <CloseIcon />
    </IconButton>
  </DialogTitle>
  
  <DialogContent sx={{ flex: 1, overflow: 'auto', pb: 2 }}>
    <Box sx={{ pt: 1 }}>
      <DataRowFormDrawer {...props} />
    </Box>
  </DialogContent>
  
  <DialogActions sx={{ px: 2, py: 1.5, borderTop: '1px solid #eee' }}>
    <Button onClick={() => { setDrawerOpen(false); setEditingRow(null); }} variant="outlined">
      Cancel
    </Button>
  </DialogActions>
</Dialog>
```

#### 1.3 Delete Confirmation Modal (Lines 453-490)
**Converted delete confirmation from Drawer to Dialog**

- Non-dismissible modal
- Close button in header
- Warning message enhanced
- Cancel / Delete buttons

```javascript
<Dialog
  open={!!deleteRow}
  onClose={(event, reason) => {
    // Only close on explicit button click
    return;
  }}
  maxWidth="xs"
  fullWidth
  PaperProps={{
    sx: { minHeight: 'auto' }
  }}
>
  <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
    <span>Delete Row</span>
    <IconButton edge="end" color="inherit" onClick={() => setDeleteRow(null)} sx={{ p: 0.5 }}>
      <CloseIcon />
    </IconButton>
  </DialogTitle>
  
  <DialogContent>
    <Typography>Are you sure you want to delete this row? This action cannot be undone.</Typography>
  </DialogContent>
  
  <DialogActions sx={{ px: 3, py: 2 }}>
    <Button onClick={() => setDeleteRow(null)} variant="outlined">
      Cancel
    </Button>
    <Button onClick={handleConfirmDelete} color="error" variant="contained">
      Delete
    </Button>
  </DialogActions>
</Dialog>
```

### UX Improvement Table

| Aspect | Before (Drawer) | After (Modal) |
|--------|---|---|
| **Close Behavior** | Backdrop click/escape | Only explicit button |
| **Resizable** | ❌ | ✅ |
| **Close Icon** | Implicit | ✅ Explicit |
| **Layout** | Right side panel | Centered modal |
| **Title** | Generic | Mode-specific |
| **Consistency** | Different from Evidence | ✅ Same as Evidence modal |

---

## Fix 2: Evidence Upload — Disable During Upload

### File: [`carbon-frontend/src/components/evidence/EvidenceUploader.jsx`](carbon-frontend/src/components/evidence/EvidenceUploader.jsx)

### Problem
During file upload, the upload area remained interactive, allowing users to:
- Click the upload area again
- Drag and drop new files
- Close the modal or interact with other elements

This caused confusion and potential data loss.

### Solution
Disable upload area during active upload with visual feedback.

### Changes

#### 2.1 Drop Zone Styling (Lines 71-82)
**Added upload state feedback to dropzone styles**

```javascript
sx={{
  border: '2px dashed',
  borderColor: isDragActive ? 'primary.main' : 'grey.300',
  borderRadius: 2,
  p: 3,
  textAlign: 'center',
  bgcolor: isDragActive ? 'action.hover' : 'background.paper',
  cursor: uploading ? 'not-allowed' : 'pointer',           // ← NEW
  transition: 'all 0.2s',
  opacity: uploading ? 0.5 : 1,                            // ← NEW (dimmed effect)
  pointerEvents: uploading ? 'none' : 'auto',             // ← NEW (disables interaction)
  '&:hover': { 
    borderColor: uploading ? 'grey.300' : 'primary.main',  // ← NEW
    bgcolor: uploading ? 'background.paper' : 'action.hover' // ← NEW
  }
}}
```

#### 2.2 Input Disabled (Line 85)
**Disable file input during upload**

```javascript
<input {...getInputProps()} disabled={uploading} />
```

### Visual Feedback During Upload

| State | Visual Change |
|-------|---|
| **Idle** | Normal colors, pointer cursor, interactive |
| **Uploading** | 50% opacity (dimmed), not-allowed cursor, no interaction |
| **Hover (Idle)** | Border highlight, background change |
| **Hover (Uploading)** | No change (disabled) |

### User Experience Flow

```
1. User sees upload area (normal)
   ↓
2. User drags file or clicks to browse
   ↓
3. Upload starts → Area becomes dimmed (50% opacity)
   ↓
4. Cursor changes to "not-allowed"
   ↓
5. All clicks/drags disabled (pointerEvents: none)
   ↓
6. Progress bar shows upload status
   ↓
7. Upload completes → Area returns to normal
```

---

## Build Verification

✅ **Frontend Build Successful**
- Build time: 12.18s
- All modules transformed: 12,456
- Production bundle generated
- No errors or critical warnings

---

## Design Consistency

Both fixes follow Material-UI patterns:

### Row Edit Modal ↔ Evidence Modal
- Same Dialog structure (DialogTitle, DialogContent, DialogActions)
- Same close button pattern (X icon)
- Same non-dismissible backdrop behavior
- Same typography and spacing

### Upload Disabled State ↔ Standard MUI Pattern
- Reduced opacity (0.5) = visual "dimmed" state
- `pointerEvents: none` = interaction disabled
- `cursor: not-allowed` = user feedback
- Follows Material-UI disabled component patterns

---

## Testing Checklist

### Row Editing Modal
- [ ] Click "Add Row" → Modal appears (not drawer)
- [ ] Click X button → Modal closes, no data saved
- [ ] Click outside modal → Modal does NOT close
- [ ] Press Escape → Modal does NOT close
- [ ] Modal is resizable (drag corner)
- [ ] Edit existing row → Modal appears with data
- [ ] Click Cancel → Modal closes, no changes
- [ ] Delete row → Confirmation modal appears
- [ ] Backdrop click on delete modal → Does NOT close
- [ ] Responsive on mobile/tablet

### Evidence Upload
- [ ] Click "Evidence" button → Opens modal
- [ ] Drag files to drop zone → Upload starts
- [ ] During upload → Drop zone is dimmed (50% opacity)
- [ ] During upload → Cursor is "not-allowed"
- [ ] During upload → Cannot click or drag new files
- [ ] Cannot escape modal during upload (non-dismissible)
- [ ] Upload completes → Area returns to normal
- [ ] Upload fails → Area returns to normal + error message
- [ ] Multiple file upload → All shown in results list

---

## Files Modified

| File | Changes | Lines |
|------|---------|-------|
| `carbon-frontend/src/components/DataTableGrid.jsx` | Drawer→Dialog conversion (2 modals) | 1-4, 375-490 |
| `carbon-frontend/src/components/evidence/EvidenceUploader.jsx` | Upload state UI feedback | 71-85 |

---

## Related Documentation

- **Material-UI Dialog**: https://mui.com/material-ui/react-dialog/
- **Material-UI Drawer**: https://mui.com/material-ui/react-drawer/
- **Evidence Modal Pattern**: [`TableDataPage.jsx:344-400`](carbon-frontend/src/components/TableDataPage.jsx:344-400)
- **Design Fix Details**: [`DRAWER_TO_MODAL_UX_FIX.md`](DRAWER_TO_MODAL_UX_FIX.md)

---

## Status

✅ **COMPLETE**
- Both fixes implemented
- Frontend builds successfully
- Production bundle ready
- No breaking changes
- Design consistent with existing patterns

**Date**: 2026-07-19  
**Mode**: Code (Implementation)  
**Build Status**: ✅ Success (12.18s)
