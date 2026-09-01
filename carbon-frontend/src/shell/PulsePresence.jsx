// src/shell/PulsePresence.jsx
//
// Tiny presence indicator for the AI workspace footer. A status dot plus
// screen-reader-only text (never color-only). Reuses the existing insight SSE
// heartbeat via `usePresence`.

import React from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import { usePresence } from '../hooks/usePresence';

const STATE_MAP = {
  online: { color: 'success.main', label: 'Pulse connected' },
  stale: { color: 'warning.main', label: 'Pulse connection degraded' },
  offline: { color: 'error.main', label: 'Pulse offline' },
};

const SR_ONLY_SX = {
  position: 'absolute',
  width: 1,
  height: 1,
  padding: 0,
  margin: -1,
  overflow: 'hidden',
  clip: 'rect(0 0 0 0)',
  whiteSpace: 'nowrap',
  border: 0,
};

function PulsePresence() {
  const { online, stale } = usePresence();
  const state = online ? 'online' : stale ? 'stale' : 'offline';
  const { color, label } = STATE_MAP[state];

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }} aria-live="polite">
      <Box
        aria-hidden="true"
        sx={{
          width: 7,
          height: 7,
          borderRadius: '50%',
          bgcolor: color,
          flexShrink: 0,
        }}
      />
      <Typography component="span" variant="caption" sx={SR_ONLY_SX}>
        {label}
      </Typography>
    </Box>
  );
}

export default PulsePresence;
