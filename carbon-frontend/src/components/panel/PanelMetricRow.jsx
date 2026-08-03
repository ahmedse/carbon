// src/components/panel/PanelMetricRow.jsx
// Key-value detail row for right-panel metrics.
// Replaces scattered ad-hoc grid DisplayRow/DetailRow patterns.
//
// Props:
//   label      — metric label (12 chars max recommended)
//   value      — metric value
//   mono       — use monospace for value (numbers, IDs)
//   divider    — show bottom border (default true)

import React from 'react';
import { Box, Typography } from '@mui/material';

export default function PanelMetricRow({ label, value, mono = false, divider = true }) {
  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        py: 1,
        borderBottom: divider ? '1px solid' : 'none',
        borderColor: 'divider',
      }}
    >
      <Typography
        variant="body2"
        color="text.secondary"
        sx={{ fontSize: '0.75rem', flexShrink: 0, mr: 1 }}
      >
        {label}
      </Typography>
      <Typography
        variant="body2"
        sx={{
          fontWeight: 600,
          fontSize: '0.82rem',
          color: 'text.primary',
          fontFamily: mono ? 'monospace' : undefined,
          textAlign: 'right',
          wordBreak: 'break-word',
        }}
      >
        {value ?? '—'}
      </Typography>
    </Box>
  );
}
