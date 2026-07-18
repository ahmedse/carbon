// File: src/components/FooterNew.jsx
// Compact, professional footer with links

import React from 'react';
import { Box, Typography, Link } from '@mui/material';

export default function FooterNew() {
  return (
    <Box
      sx={{
        py: 1.5,
        px: 2,
        bgcolor: 'background.paper',
        borderTop: '1px solid',
        borderColor: 'divider',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexShrink: 0,
      }}
    >
      <Typography sx={{ fontSize: '0.6875rem', color: 'text.secondary' }}>
        © {new Date().getFullYear()} AASTMT Carbon Data Trust Platform
      </Typography>
      
      <Box sx={{ display: 'flex', gap: 2 }}>
        <Link
          href="/help"
          sx={{
            fontSize: '0.6875rem',
            color: 'text.secondary',
            textDecoration: 'none',
            '&:hover': {
              color: 'primary.main',
              textDecoration: 'underline',
            },
          }}
        >
          Privacy
        </Link>
        <Link
          href="/help"
          sx={{
            fontSize: '0.6875rem',
            color: 'text.secondary',
            textDecoration: 'none',
            '&:hover': {
              color: 'primary.main',
              textDecoration: 'underline',
            },
          }}
        >
          Terms
        </Link>
        <Link
          href="/feedback"
          sx={{
            fontSize: '0.6875rem',
            color: 'text.secondary',
            textDecoration: 'none',
            '&:hover': {
              color: 'primary.main',
              textDecoration: 'underline',
            },
          }}
        >
          Support
        </Link>
      </Box>
    </Box>
  );
}
