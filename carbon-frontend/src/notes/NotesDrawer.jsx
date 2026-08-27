// src/notes/NotesDrawer.jsx
// Docked INSIDE the content (editor) pane at its right edge:
//   collapsed → slim rail; expanded → resizable panel.
// Pulse (copilot) stays the outermost right pane when open.
// In RTL the flex order flips the drawer to the content's left edge (mirror).

import React from 'react';
import { Box } from '@mui/material';
import { useNotes } from './NotesContext';
import { NotesRail } from './NotesRail';
import { NotesPanel } from './NotesPanel';
import { useLanguage } from '../i18n/useLanguage';

const WIDTH_MIN = () => Math.min(240, Math.floor(window.innerWidth * 0.35));
const WIDTH_MAX = () => Math.max(WIDTH_MIN(), Math.floor(window.innerWidth * 0.5));

export function NotesDrawer() {
  const { open, width, setWidth, setOpen } = useNotes();
  const { isRtl } = useLanguage();

  if (!open) {
    return <NotesRail onOpen={() => setOpen(true)} />;
  }

  return (
    <Box
      sx={{
        position: 'relative',
        width,
        maxWidth: WIDTH_MAX(),
        minWidth: WIDTH_MIN(),
        flexShrink: 0,
        height: '100%',
        display: 'flex',
      }}
    >
      {/* Resize handle — between content and panel; side flips with RTL */}
      <Box
        role="separator"
        aria-orientation="vertical"
        aria-label="Resize notes panel"
        sx={{
          position: 'absolute',
          top: 0,
          bottom: 0,
          width: 4,
          cursor: 'col-resize',
          zIndex: 2,
          bgcolor: 'transparent',
          '&:hover': { bgcolor: 'action.hover' },
          ...(isRtl ? { right: 0 } : { left: 0 }),
        }}
        onMouseDown={(e) => {
          e.preventDefault();
          e.stopPropagation();
          const startX = e.clientX;
          const startWidth = width;
          const onMove = (moveEvent) => {
            // Direct manipulation: the drawer edge follows the cursor.
            //   LTR (docked right, handle on left edge): drag LEFT  → wider  (left/content becomes smaller)
            //   RTL (docked left,  handle on right edge): drag RIGHT → wider
            const delta = isRtl ? (moveEvent.clientX - startX) : (startX - moveEvent.clientX);
            setWidth(startWidth + delta);
          };
          const onUp = () => {
            window.removeEventListener('mousemove', onMove);
            window.removeEventListener('mouseup', onUp);
          };
          window.addEventListener('mousemove', onMove);
          window.addEventListener('mouseup', onUp);
        }}
      />
      <Box sx={{ flex: 1, minWidth: 0, height: '100%' }}>
        <NotesPanel />
      </Box>
    </Box>
  );
}
