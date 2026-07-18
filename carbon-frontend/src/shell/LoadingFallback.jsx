// File: src/shell/LoadingFallback.jsx
// Loading skeleton components for lazy-loaded modules

import React from 'react';
import { Box, Skeleton, CircularProgress } from '@mui/material';

// Simple centered spinner
export function LoadingSpinner() {
  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '200px',
        width: '100%',
      }}
    >
      <CircularProgress size={40} />
    </Box>
  );
}

// Full page loading skeleton
export function PageLoadingSkeleton() {
  return (
    <Box sx={{ p: 3 }}>
      <Skeleton variant="rectangular" height={40} sx={{ mb: 2 }} />
      <Skeleton variant="rectangular" height={200} sx={{ mb: 2 }} />
      <Skeleton variant="rectangular" height={300} />
    </Box>
  );
}

// Dialog loading skeleton (for Command Palette, etc.)
export function DialogLoadingSkeleton() {
  return (
    <Box sx={{ p: 2 }}>
      <Skeleton variant="rectangular" height={50} sx={{ mb: 1 }} />
      <Skeleton variant="rectangular" height={300} />
    </Box>
  );
}

// Sidebar loading skeleton
export function SidebarLoadingSkeleton() {
  return (
    <Box sx={{ p: 2 }}>
      {[1, 2, 3, 4, 5].map((i) => (
        <Skeleton
          key={i}
          variant="rectangular"
          height={36}
          sx={{ mb: 1, borderRadius: 1 }}
        />
      ))}
    </Box>
  );
}
