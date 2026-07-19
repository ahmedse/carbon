// File: src/pages/dataschema/ResizableDivider.jsx
// Resizable divider between main content and metrics panel

import React, { useState, useRef } from 'react';
import { Box } from '@mui/material';

const MIN_WIDTH = 250;
const MAX_WIDTH_PERCENT = 0.5;

export default function ResizableDivider({ onResize }) {
  const [isDragging, setIsDragging] = useState(false);
  const dividerRef = useRef(null);

  const handleMouseDown = () => {
    setIsDragging(true);
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const handleMouseMove = (e) => {
    if (!isDragging) return;

    // Calculate new panel width based on mouse position
    const maxWidth = MAX_WIDTH_PERCENT * window.innerWidth;
    const newWidth = window.innerWidth - e.clientX;

    // Apply constraints
    if (newWidth >= MIN_WIDTH && newWidth <= maxWidth) {
      onResize(newWidth);
    }
  };

  // Attach/detach mouse events
  React.useEffect(() => {
    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      document.body.style.userSelect = 'none';
      document.body.style.cursor = 'col-resize';

      return () => {
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
        document.body.style.userSelect = 'auto';
        document.body.style.cursor = 'auto';
      };
    }
  }, [isDragging]);

  return (
    <Box
      ref={dividerRef}
      onMouseDown={handleMouseDown}
      sx={{
        width: '4px',
        bgcolor: '#e0e0e0',
        cursor: 'col-resize',
        transition: isDragging ? 'none' : 'background-color 0.2s',
        '&:hover': {
          bgcolor: '#1976d2',
        },
      }}
    />
  );
}
