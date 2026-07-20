// File: src/components/detail/DetailMainPanel.jsx
// Generic main panel wrapper for detail page content tabs

import React from 'react';
import { Box, CircularProgress, Alert, Typography } from '@mui/material';

/**
 * DetailMainPanel - Wrapper for main panel content
 * Provides consistent styling and loading/error states
 */
export default function DetailMainPanel({
  loading = false,
  error = null,
  children = null,
}) {
  if (loading) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error">{error}</Alert>
      </Box>
    );
  }

  return <>{children}</>;
}

/**
 * DetailTabContent - Wrapper for individual tab content
 */
export function DetailTabContent({ children, sx = {} }) {
  return (
    <Box sx={{ p: 3, ...sx }}>
      {children}
    </Box>
  );
}

/**
 * DetailMetadataGrid - Standard grid layout for metadata display
 */
export function DetailMetadataGrid({ items = [] }) {
  return (
    <Box
      sx={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
        gap: 3,
      }}
    >
      {items.map((item, idx) => (
        <Box key={idx}>
          <Typography variant="caption" sx={{ textTransform: 'uppercase', color: 'text.secondary' }}>
            {item.label}
          </Typography>
          <Typography variant="body2" sx={{ mt: 0.5, fontWeight: 500 }}>
            {item.value}
          </Typography>
        </Box>
      ))}
    </Box>
  );
}
