import React from 'react';
import { Box, Stack, Typography } from '@mui/material';

/**
 * Flat count row for smoke / reconcile. Not StatCard (shadows).
 */
export default function InboundStatRow({ items = [] }) {
  return (
    <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
      {items.map((item) => (
        <Box
          key={item.key}
          sx={{
            border: '1px solid',
            borderColor: 'divider',
            px: 1.25,
            py: 0.75,
            minWidth: 88,
          }}
        >
          <Typography sx={{ fontSize: '0.6875rem', color: 'text.secondary' }}>
            {item.label}
          </Typography>
          <Typography
            sx={{
              fontSize: '1rem',
              fontWeight: 600,
              fontFamily: 'ui-monospace, monospace',
              color: item.tone === 'error' ? 'error.main' : 'text.primary',
            }}
          >
            {item.value ?? 0}
          </Typography>
        </Box>
      ))}
    </Stack>
  );
}
