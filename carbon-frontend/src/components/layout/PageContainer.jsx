// File: src/components/layout/PageContainer.jsx
// Unified page padding wrapper. Use this instead of ad-hoc <Box sx={{ p: 3 }}>
// so every page shares the same content padding.

import React from 'react';
import { Box } from '@mui/material';

export default function PageContainer({ children, sx = {} }) {
  return <Box sx={{ p: 2, ...sx }}>{children}</Box>;
}
