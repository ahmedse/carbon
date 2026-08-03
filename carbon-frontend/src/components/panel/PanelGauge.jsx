// src/components/panel/PanelGauge.jsx
// Shared circular DQ gauge. Used by TrustTab, ModuleHealthTab, DQMetricsTab.
// Replaces duplicated CircularProgress gauge code everywhere.
//
// Props:
//   score     — 0–100 number
//   size      — circle diameter (default 72)
//   label     — text under gauge (default "DQ Score")
//   status    — 'passing' | 'warning' | 'failing' | 'nodata'

import React from 'react';
import { Box, Typography, CircularProgress, Chip } from '@mui/material';

const STATUS_CONFIG = {
  passing: { color: 'success.main', chipColor: 'success', label: 'Passing' },
  warning: { color: 'warning.main', chipColor: 'warning', label: 'Warning' },
  failing: { color: 'error.main', chipColor: 'error', label: 'Failing' },
  nodata:  { color: 'text.disabled', chipColor: 'default', label: 'No data' },
};

function getStatus(score) {
  if (score == null || score === 0) return 'nodata';
  if (score >= 80) return 'passing';
  if (score >= 60) return 'warning';
  return 'failing';
}

export default function PanelGauge({ score = 0, size = 72, label = 'DQ Score', status: statusOverride }) {
  const status = statusOverride || getStatus(score);
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.nodata;

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
      <Box sx={{ position: 'relative', display: 'inline-flex' }}>
        <CircularProgress
          variant="determinate"
          value={Math.min(score, 100)}
          size={size}
          thickness={5}
          sx={{ color: cfg.color }}
        />
        <Box
          sx={{
            position: 'absolute',
            top: 0,
            left: 0,
            bottom: 0,
            right: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <Typography
            sx={{
              fontWeight: 700,
              fontSize: size >= 72 ? '0.82rem' : '0.7rem',
              color: cfg.color,
            }}
          >
            {score > 0 ? `${Math.round(score)}%` : '—'}
          </Typography>
        </Box>
      </Box>
      <Box>
        <Typography sx={{ fontSize: '0.75rem', fontWeight: 600 }}>{label}</Typography>
        <Chip
          label={cfg.label}
          size="small"
          color={cfg.chipColor}
          variant="outlined"
          sx={{ height: 20, fontSize: '0.68rem', mt: 0.5 }}
        />
      </Box>
    </Box>
  );
}
