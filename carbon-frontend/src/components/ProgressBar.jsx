// src/components/ProgressBar.jsx
// Layer-2 primitive: the ONE determinate progress bar + value label
// (design-system RULE 2). Replaces the hand-rolled CoverageBar / ReductionBar
// forks.
//
// Domain-neutral: the component knows nothing about coverage or targets. The
// caller owns any threshold logic and passes the resolved semantic `tone`
// (`success` | `warning` | `error` | `info` | `primary`); the value label is
// pre-formatted by the shared formatter at the call site.
import React from 'react';
import PropTypes from 'prop-types';
import { Box, LinearProgress, Typography } from '@mui/material';

function ProgressBar({
  value,
  tone = 'info',
  label,
  minWidth = 140,
  labelWidth = 40,
  height = 0.75,
}) {
  const pct = Number(value);
  const safe = Number.isFinite(pct) ? pct : 0;
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth }}>
      <LinearProgress
        variant="determinate"
        value={Math.min(Math.max(safe, 0), 100)}
        color={tone}
        sx={{ flex: 1, height, borderRadius: 1 }}
      />
      {label != null && (
        <Typography
          variant="caption"
          sx={{ minWidth: labelWidth, textAlign: 'end', fontVariantNumeric: 'tabular-nums' }}
        >
          {label}
        </Typography>
      )}
    </Box>
  );
}

ProgressBar.propTypes = {
  /** 0–100 percent value (already in percent units). */
  value: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
  /** Semantic tone resolved by the caller. */
  tone: PropTypes.oneOf(['primary', 'secondary', 'success', 'warning', 'error', 'info']),
  /** Pre-formatted value label (use the shared number/percent formatter). */
  label: PropTypes.node,
  minWidth: PropTypes.number,
  labelWidth: PropTypes.number,
  height: PropTypes.number,
};

ProgressBar.defaultProps = {
  value: 0,
  tone: 'info',
  label: null,
  minWidth: 140,
  labelWidth: 40,
  height: 0.75,
};

export default React.memo(ProgressBar);
