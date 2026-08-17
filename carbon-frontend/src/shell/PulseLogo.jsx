// src/shell/PulseLogo.jsx
// Enterprise Pulse brand mark — a heartbeat waveform set in a gradient
// squircle, with an optional "Pulse" wordmark. Conveys a fast, connected,
// self-serve AI product that plugs into the wider Carbon platform.
//
// RULE_8: colors derive from the MUI theme only — no hardcoded hex/px.

import React, { useId } from 'react';
import PropTypes from 'prop-types';
import { Box, Typography } from '@mui/material';
import { useTheme } from '@mui/material/styles';

/**
 * @param {object} props
 * @param {number} [props.size=20]    Size of the badge in px.
 * @param {boolean} [props.showWordmark=false] Render the "Pulse" wordmark.
 * @param {object} [props.wordmarkSx] Extra sx for the wordmark Typography.
 * @param {object} [props.sx]         Extra sx for the wrapper Box.
 */
function PulseLogo({ size = 20, showWordmark = false, wordmarkSx, sx }) {
  const theme = useTheme();
  const primary = theme.palette.primary.main;
  const accent = theme.palette.info.main;
  const onBrand = theme.palette.primary.contrastText || '#ffffff';

  // Unique gradient id per instance so multiple logos don't collide.
  const gradientId = useId().replace(/:/g, 'pulse');

  return (
    <Box
      sx={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 0.75,
        userSelect: 'none',
        ...sx,
      }}
    >
      <svg
        width={size}
        height={size}
        viewBox="0 0 24 24"
        fill="none"
        role="img"
        aria-label="Pulse logo"
      >
        <defs>
          <linearGradient
            id={gradientId}
            x1="2"
            y1="2"
            x2="22"
            y2="22"
            gradientUnits="userSpaceOnUse"
          >
            <stop stopColor={primary} />
            <stop offset="1" stopColor={accent} />
          </linearGradient>
        </defs>
        {/* Gradient squircle badge */}
        <rect
          x="0.9"
          y="0.9"
          width="22.2"
          height="22.2"
          rx="6.5"
          fill={`url(#${gradientId})`}
        />
        {/* Heartbeat / pulse waveform */}
        <path
          d="M4.6 12h2.7l1.35-5 2.3 10 2.1-7 1.75 2h4.3"
          stroke={onBrand}
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>

      {showWordmark && (
        <Typography
          variant="subtitle2"
          sx={{
            fontWeight: 700,
            letterSpacing: '-0.01em',
            lineHeight: 1,
            color: 'text.primary',
            ...wordmarkSx,
          }}
        >
          Pulse
        </Typography>
      )}
    </Box>
  );
}

PulseLogo.propTypes = {
  size: PropTypes.number,
  showWordmark: PropTypes.bool,
  wordmarkSx: PropTypes.object,
  sx: PropTypes.object,
};

export default PulseLogo;
