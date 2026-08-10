// File: src/components/layout/PageContainer.jsx
// Unified page padding wrapper. Use this instead of ad-hoc <Box sx={{ p: 3 }}>
// so every page shares the same content padding.

import React from 'react';
import { Box } from '@mui/material';

export default function PageContainer({ children, sx = {} }) {
  return (
    <Box
      sx={{
        px: 1,
        py: 0.75,
        width: '100%',
        flex: 1,
        minHeight: 0,
        display: 'flex',
        flexDirection: 'column',
        ...sx,
      }}
    >
      {children}
    </Box>
  );
}
