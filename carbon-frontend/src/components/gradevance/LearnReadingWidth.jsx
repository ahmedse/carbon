// Learn reading-width shell — ADR-0035 / compact-ui §Mobile (no invented CSS).
// Desktop: single-column reading maxWidth md; mobile: full width + larger primary CTAs.

import React from 'react';
import { Box } from '@mui/material';
import useIsMobile from '../../hooks/useIsMobile';

export default function LearnReadingWidth({ children, sx = {} }) {
  const isMobile = useIsMobile();
  return (
    <Box
      sx={{
        width: '100%',
        maxWidth: isMobile ? '100%' : (theme) => theme.breakpoints.values.md,
        mx: 'auto',
        ...sx,
      }}
    >
      {children}
    </Box>
  );
}

/** Primary CTA size under sm per compact-ui §Mobile. */
export function useLearnPrimarySize() {
  const isMobile = useIsMobile();
  return isMobile ? 'medium' : 'small';
}
