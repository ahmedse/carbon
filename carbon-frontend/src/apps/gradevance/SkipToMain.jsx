// Skip link for GradeVance studios (WCAG 2.4.1).

import React from 'react';
import { Link as MuiLink } from '@mui/material';

export default function SkipToMain({ targetId = 'gradevance-main' }) {
  return (
    <MuiLink
      href={`#${targetId}`}
      sx={{
        position: 'absolute',
        left: '-9999px',
        zIndex: 10000,
        bgcolor: 'background.paper',
        color: 'text.primary',
        p: 1,
        '&:focus': { left: 8, top: 8 },
      }}
    >
      Skip to main content
    </MuiLink>
  );
}
