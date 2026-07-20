// File: src/components/detail/DetailMetricsPanel.jsx
// Generic metrics panel for displaying summary information on detail pages

import React from 'react';
import { Box, Card, CardContent, Typography, Chip, Divider, Alert, CircularProgress } from '@mui/material';

/**
 * DetailMetricsPanel - Wrapper for metrics panel content
 * Provides consistent styling for summary cards and metrics
 */
export default function DetailMetricsPanel({
  loading = false,
  error = null,
  children = null,
}) {
  if (loading) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', p: 3 }}>
        <CircularProgress size={32} />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 2 }}>
        <Alert severity="warning" variant="outlined" sx={{ fontSize: '0.85rem' }}>
          {error}
        </Alert>
      </Box>
    );
  }

  return <>{children}</>;
}

/**
 * MetricCard - Individual metric display card
 */
export function MetricCard({
  label = '',
  value = '',
  icon: Icon = null,
  color = 'default',
  variant = 'outlined',
}) {
  return (
    <Card variant={variant} sx={{ mb: 2 }}>
      <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
        <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
          {Icon && (
            <Icon
              sx={{
                color: `${color}.main`,
                fontSize: '1.5rem',
                mt: 0.5,
                flexShrink: 0,
              }}
            />
          )}
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Typography variant="caption" sx={{ textTransform: 'uppercase', color: 'text.secondary' }}>
              {label}
            </Typography>
            <Typography
              variant="body2"
              sx={{
                mt: 0.5,
                fontWeight: 600,
                fontSize: '1.1rem',
                wordBreak: 'break-word',
              }}
            >
              {value}
            </Typography>
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
}

/**
 * MetricsGrid - Grid layout for multiple metric cards
 */
export function MetricsGrid({ children, sx = {} }) {
  return (
    <Box
      sx={{
        display: 'grid',
        gridTemplateColumns: 'repeat(2, 1fr)',
        gap: 1.5,
        p: 2,
        ...sx,
      }}
    >
      {children}
    </Box>
  );
}

/**
 * MetricsSection - Section header with cards
 */
export function MetricsSection({
  title = '',
  children = null,
  divider = true,
}) {
  return (
    <Box sx={{ p: 2 }}>
      {title && (
        <Typography
          variant="subtitle2"
          sx={{
            fontWeight: 600,
            mb: 2,
            textTransform: 'uppercase',
            fontSize: '0.75rem',
            letterSpacing: '0.5px',
            color: 'text.secondary',
          }}
        >
          {title}
        </Typography>
      )}
      {children}
      {divider && <Divider sx={{ mt: 2 }} />}
    </Box>
  );
}

/**
 * MetricsChip - Chip for tags, statuses, etc.
 */
export function MetricsChip({ label = '', icon: Icon = null, color = 'default', size = 'small' }) {
  return (
    <Chip
      label={label}
      icon={Icon}
      color={color}
      size={size}
      variant="outlined"
      sx={{ m: 0.5 }}
    />
  );
}
