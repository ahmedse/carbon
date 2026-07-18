// File: src/shell/EditorArea.jsx
// Main content area (Outlet for React Router)

import React from 'react';
import { Outlet } from 'react-router-dom';
import { Box } from '@mui/material';
import { Breadcrumbs } from './Breadcrumbs';

export function EditorArea() {
  return (
    <Box
      sx={{
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        bgcolor: 'background.default',
      }}
    >
      {/* Breadcrumbs navigation */}
      <Breadcrumbs />
      
      {/* Main content area */}
      <Box
        sx={{
          flex: 1,
          overflow: 'auto',
        }}
      >
        <Outlet />
      </Box>
    </Box>
  );
}
