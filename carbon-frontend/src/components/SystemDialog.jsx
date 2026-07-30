// src/components/SystemDialog.jsx
// Standard system-wide dialog with drag, resize, explicit close, and modal focus.

import React, { useState, useEffect, useRef } from 'react';
import { Box, Dialog, DialogTitle, DialogContent, DialogActions, Paper, IconButton, Button } from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';

const MIN_WIDTH = 420;
const MIN_HEIGHT = 320;
const DEFAULT_WIDTH = 720;
const DEFAULT_HEIGHT = 520;

export default function SystemDialog({
  open,
  title,
  onClose,
  onCancel,
  children,
  actions,
  width = DEFAULT_WIDTH,
  height = DEFAULT_HEIGHT,
  minWidth = MIN_WIDTH,
  minHeight = MIN_HEIGHT,
  maxWidth = 'calc(100vw - 48px)',
  maxHeight = 'calc(100vh - 48px)',
  _closeLabel = 'Close',
  cancelLabel = 'Cancel',
  showCancel = true,
  fullWidth = false,
  ...props
}) {
  const [size, setSize] = useState({ width, height });
  const [position, setPosition] = useState({ top: 80, left: 0 });
  const [dragging, setDragging] = useState(false);
  const [resizing, setResizing] = useState(false);
  const dragStartRef = useRef(null);
  const resizeStartRef = useRef(null);
  const contentRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    const viewportWidth = window.innerWidth;
    const initialLeft = Math.max(24, Math.round((viewportWidth - size.width) / 2));
    setPosition((prev) => ({ top: 80, left: prev.left || initialLeft }));
  }, [open, size.width]);

  useEffect(() => {
    const handleMove = (event) => {
      if (dragging && dragStartRef.current) {
        event.preventDefault();
        const { startX, startY, startLeft, startTop } = dragStartRef.current;
        setPosition({
          left: Math.max(24, Math.min(window.innerWidth - size.width - 24, startLeft + event.clientX - startX)),
          top: Math.max(24, Math.min(window.innerHeight - size.height - 24, startTop + event.clientY - startY)),
        });
      }
      if (resizing && resizeStartRef.current) {
        event.preventDefault();
        const { startX, startY, startWidth, startHeight } = resizeStartRef.current;
        const newWidth = Math.max(minWidth, Math.min(window.innerWidth - position.left - 24, startWidth + event.clientX - startX));
        const newHeight = Math.max(minHeight, Math.min(window.innerHeight - position.top - 24, startHeight + event.clientY - startY));
        setSize({ width: Math.min(parseInt(maxWidth, 10) || newWidth, newWidth), height: Math.min(parseInt(maxHeight, 10) || newHeight, newHeight) });
      }
    };

    const handleUp = () => {
      setDragging(false);
      setResizing(false);
      dragStartRef.current = null;
      resizeStartRef.current = null;
    };

    if (dragging || resizing) {
      document.addEventListener('mousemove', handleMove);
      document.addEventListener('mouseup', handleUp);
      return () => {
        document.removeEventListener('mousemove', handleMove);
        document.removeEventListener('mouseup', handleUp);
      };
    }

    return undefined;
  }, [dragging, resizing, minWidth, minHeight, maxWidth, maxHeight, position.left, position.top, size.height, size.width]);

  const handleDragStart = (event) => {
    if (event.button !== 0) return;
    event.preventDefault();
    dragStartRef.current = {
      startX: event.clientX,
      startY: event.clientY,
      startLeft: position.left,
      startTop: position.top,
    };
    setDragging(true);
  };

  const handleResizeStart = (event) => {
    if (event.button !== 0) return;
    event.preventDefault();
    resizeStartRef.current = {
      startX: event.clientX,
      startY: event.clientY,
      startWidth: size.width,
      startHeight: size.height,
    };
    setResizing(true);
  };

  const handleCloseRequest = (event, reason) => {
    if (reason === 'backdropClick' || reason === 'escapeKeyDown') {
      return;
    }
    if (onClose) onClose(event, reason);
  };

  const handleCancel = () => {
    if (onCancel) onCancel();
    else if (onClose) onClose();
  };

  return (
    <Dialog
      open={open}
      onClose={handleCloseRequest}
      fullWidth={fullWidth}
      maxWidth={false}
      PaperProps={{
        sx: {
          position: 'absolute',
          top: position.top,
          left: position.left,
          width: size.width,
          height: size.height,
          minWidth,
          minHeight,
          maxWidth,
          maxHeight,
          m: 0,
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
        },
      }}
      BackdropProps={{
        sx: {
          bgcolor: 'rgba(0,0,0,0.32)',
        },
      }}
      disableEscapeKeyDown
      {...props}
    >
      <DialogTitle
        onMouseDown={handleDragStart}
        sx={{
          cursor: 'move',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          userSelect: 'none',
          mb: 0,
          pr: 1,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 0 }}>
          <Box component='span' sx={{ fontWeight: 700, lineHeight: 1.2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {title}
          </Box>
        </Box>
        <IconButton size='small' onClick={handleCancel} aria-label='Close dialog'>
          <CloseIcon fontSize='small' />
        </IconButton>
      </DialogTitle>

      <DialogContent ref={contentRef} sx={{ flex: 1, overflow: 'auto', pb: 2 }}>
        {children}
      </DialogContent>

      <DialogActions sx={{ px: 2, py: 1.5, borderTop: '1px solid', borderColor: 'divider' }}>
        {showCancel && (
          <Button onClick={handleCancel} color='inherit'>
            {cancelLabel}
          </Button>
        )}
        {actions}
      </DialogActions>

      <Box
        onMouseDown={handleResizeStart}
        sx={{
          position: 'absolute',
          right: 6,
          bottom: 6,
          width: 18,
          height: 18,
          cursor: 'nwse-resize',
          zIndex: 10,
        }}
      />
    </Dialog>
  );
}
