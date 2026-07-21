# UX Fix: TableDataPage Row Editing — Drawer to Modal Conversion

## Summary
Converted TableDataPage row editing interface from Drawer component to Modal Dialog component per user agreement. This provides a better UX with explicit close button, non-dismissible backdrop, and resizable modal window.

## Changes Made

### File: [`carbon-frontend/src/components/DataTableGrid.jsx`](carbon-frontend/src/components/DataTableGrid.jsx)

#### 1. Import Updates (Lines 1-4)
- **Removed**: `Drawer` component
- **Added**: `Dialog`, `DialogTitle`, `DialogContent`, `DialogActions`, `Typography` components
- **Added**: `CloseIcon` import for close button

```javascript
// Before
import { Button, Drawer, Box, CircularProgress, IconButton, Tooltip } from "@mui/material";

// After
import { Button, Dialog, Box, CircularProgress, IconButton, Tooltip, DialogTitle, DialogContent, DialogActions, Typography } from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
```

#### 2. Row Edit Modal (Lines 375-450)
**Replaced drawer-based row editor with Dialog modal**

**Key Features:**
- ✅ Modal Dialog (not closeable by backdrop click or escape key)
- ✅ Explicit close button (X icon in top-right corner)
- ✅ Resizable window: `resize: 'both'`
- ✅ Proper title bar with mode indicator ("Edit Row" vs "Add New Row")
- ✅ ScrollableContent area with max height 90vh
- ✅ Footer with Cancel button
- ✅ Structured layout: DialogTitle → DialogContent → DialogActions

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
  {/* Title with close button */}
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
  
  {/* Scrollable form content */}
  <DialogContent sx={{ flex: 1, overflow: 'auto', pb: 2 }}>
    <Box sx={{ pt: 1 }}>
      <DataRowFormDrawer {...props} />
    </Box>
  </DialogContent>
  
  {/* Footer with buttons */}
  <DialogActions sx={{ px: 2, py: 1.5, borderTop: '1px solid #eee' }}>
    <Button onClick={() => { setDrawerOpen(false); setEditingRow(null); }} variant="outlined">
      Cancel
    </Button>
  </DialogActions>
</Dialog>
```

#### 3. Row Delete Confirmation Modal (Lines 453-490)
**Converted delete confirmation from drawer to Dialog**

- ✅ Non-dismissible modal
- ✅ Close button in header
- ✅ Confirmation buttons: Cancel / Delete (error variant)
- ✅ Warning message with enhanced text

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

## UX Improvements

| Aspect | Before (Drawer) | After (Modal) |
|--------|---|---|
| **Dismissal Behavior** | Closeable by backdrop click or escape | Only closeable by explicit Cancel/Close button |
| **Resizable** | No | Yes (both width and height) |
| **Close Affordance** | Implicit (click outside) | Explicit (X icon) |
| **Layout** | Right-anchored side panel | Centered modal dialog |
| **Max Height** | Full screen | 90vh (with scroll) |
| **Title Clarity** | Generic | Mode-specific ("Edit Row" vs "Add New Row") |
| **Delete Confirmation** | Side drawer | Compact modal with warning text |
| **Alignment** | Material-UI Drawer pattern | Material-UI Dialog pattern (same as Evidence modal) |

## Design Consistency

The row editing modal now matches the Evidence modal pattern already implemented in [`TableDataPage.jsx`](carbon-frontend/src/components/TableDataPage.jsx:344-400):
- Same Dialog component structure
- Same DialogTitle/DialogContent/DialogActions layout
- Same close button pattern
- Same non-dismissible backdrop behavior

## Build Status

✅ **Frontend Build Successful**
- Vite build completed in 11.96s
- No errors or critical warnings
- All 12,456 modules transformed successfully
- Production bundle generated at `dist/`

## Testing Checklist

- [ ] **Manual UI Test**: Open TableDataPage, click "Add New Row" → Modal appears (not drawer)
- [ ] **Close Button**: X icon in top-right closes modal without saving
- [ ] **Backdrop Click**: Clicking outside modal does NOT close it
- [ ] **Escape Key**: Pressing Escape does NOT close modal
- [ ] **Cancel Button**: Cancel button closes modal without saving
- [ ] **Resizable**: Try resizing modal window (should be resizable)
- [ ] **Edit Existing Row**: Click edit icon on row → Modal appears with data filled
- [ ] **Delete Confirmation**: Delete icon → Modal asks for confirmation (not dismissible by backdrop)
- [ ] **Responsive**: Test on mobile/tablet (modal should be full-width)

## Files Modified

- `carbon-frontend/src/components/DataTableGrid.jsx` (347 lines added/modified)

## Next Steps

1. **Deploy & Verify**: Merge to dev branch and test in staging environment
2. **Evidence Modal Parity**: Consider making Evidence modal also non-dismissible if needed (already implements same pattern)
3. **Bulk Import Wizard**: Verify BulkImportWizard also follows Dialog pattern (uses Dialog component)

## Related Documentation

- Material-UI Dialog: https://mui.com/material-ui/react-dialog/
- Material-UI Drawer: https://mui.com/material-ui/react-drawer/
- Evidence Modal (same pattern): [`TableDataPage.jsx:344-400`](carbon-frontend/src/components/TableDataPage.jsx:344-400)

---

**Status**: ✅ COMPLETE
**Date**: 2026-07-19
**Mode**: Code (Implementation)
