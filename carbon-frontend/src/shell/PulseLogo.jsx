import React from 'react';
import { Box, Typography, useTheme } from '@mui/material';

/**
 * Flat monoline Pulse mark — 20px stroked square + waveform.
 * RULE_8: theme tokens only; no gradient squircle, no hex.
 */
export function PulseMark({ size = 20, color, sx }) {
  const theme = useTheme();
  const stroke = color || theme.palette.primary.main;
  return (
    <Box
      component="svg"
      width={size}
      height={size}
      viewBox="0 0 20 20"
      fill="none"
      aria-hidden
      sx={{ display: 'block', flexShrink: 0, ...sx }}
    >
      <rect
        x="1.5"
        y="1.5"
        width="17"
        height="17"
        rx="2"
        stroke={stroke}
        strokeWidth="1.25"
      />
      <polyline
        points="3.5,10 6.5,10 8,6.5 10,13.5 11.5,10 16.5,10"
        stroke={stroke}
        strokeWidth="1.25"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Box>
  );
}

export default function PulseLogo({ size = 20, showWordmark = false, wordmarkSx }) {
  return (
    <Box
      data-testid="pulse-logo"
      aria-label="Pulse logo"
      sx={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 0.75,
        flexShrink: 0,
      }}
    >
      <PulseMark size={size} />
      {showWordmark ? (
        <Typography
          component="span"
          sx={{
            fontSize: size >= 28 ? '1.05rem' : '0.8125rem',
            fontWeight: 600,
            letterSpacing: '-0.02em',
            lineHeight: 1,
            color: 'text.primary',
            ...wordmarkSx,
          }}
        >
          Pulse
        </Typography>
      ) : null}
    </Box>
  );
}
