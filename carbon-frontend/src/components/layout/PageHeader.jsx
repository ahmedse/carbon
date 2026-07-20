// File: src/components/layout/PageHeader.jsx
// Unified compact page header used by all list/index pages.
// Do NOT re-implement headers inline in pages — use this component so spacing,
// font sizes and icon sizing stay consistent across the whole app.

import React from 'react';
import { Box, Typography } from '@mui/material';

/**
 * PageHeader — standard compact page title block.
 *
 * Props:
 * - icon: MUI icon component (optional)
 * - title: string heading
 * - subtitle: string description (optional)
 * - actions: React node rendered on the right (buttons, etc.)
 */
export default function PageHeader({ icon: Icon = null, title, subtitle, actions = null }) {
  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 1.5,
        mb: 2,
        flexWrap: 'wrap',
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 0 }}>
        {Icon && <Icon sx={{ fontSize: '1.25rem', color: 'primary.main' }} />}
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="h6" sx={{ fontWeight: 700, lineHeight: 1.3 }} noWrap>
            {title}
          </Typography>
          {subtitle && (
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
              {subtitle}
            </Typography>
          )}
        </Box>
      </Box>
      {actions && <Box sx={{ display: 'flex', gap: 1, flexShrink: 0 }}>{actions}</Box>}
    </Box>
  );
}
