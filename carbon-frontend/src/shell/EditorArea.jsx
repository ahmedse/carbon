// File: src/shell/EditorArea.jsx
// Main content area (Outlet for React Router)

import React from 'react';
import { Outlet } from 'react-router-dom';
import { Box } from '@mui/material';

export function EditorArea() {
  return (
    <Box
      sx={{
        width: '100%',
        height: '100%',
        overflow: 'auto',
        bgcolor: 'background.default',
      }}
    >
      <Outlet />
    </Box>
  );
}
