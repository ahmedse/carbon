// src/shell/ConfidenceIndicator.jsx
// Wave C2 — surface calibrated confidence (Faculty 7).
// Renders a subtle, outcome-shaped confidence signal off the REAL backend
// field `confidence_label` (`high|medium|low|uncertain`) + the boolean
// `honest_uncertainty` flag (RULE_23 — outcome copy only, no raw floats,
// no critic internals). Theme tokens only (RULE_8 — never hardcoded hex).
import PropTypes from 'prop-types';
import { Box, Tooltip, Typography } from '@mui/material';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';

// label → progress color (theme token) + representative screen-reader value.
const BAR_COLOR = { high: 'success.main', medium: 'warning.main', low: 'error.main' };
const BAR_VALUE = { high: 92, medium: 60, low: 35 };
const BAR_TITLE = { high: 'High confidence', medium: 'Medium confidence', low: 'Low confidence' };

// Canonical honest-uncertainty copy (PULSE-UX §6.3 — "Confident uncertainty").
const UNCERTAIN_COPY = 'Best available — some gaps remain';

function ConfidenceIndicator({ label, honest = false }) {
  // Honest "I don't know" and a low-confidence turn both render as the same
  // calm first-class state — NOT an error. Distinct styling, no error color.
  if (honest || label === 'uncertain') {
    return (
      <Box sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5 }}>
        <HelpOutlineIcon sx={{ fontSize: 14, color: 'warning.main' }} aria-hidden="true" />
        <Typography
          variant="caption"
          sx={{ fontSize: '0.68rem', color: 'text.secondary', fontStyle: 'italic' }}
        >
          {UNCERTAIN_COPY}
        </Typography>
      </Box>
    );
  }

  const color = BAR_COLOR[label];
  const value = BAR_VALUE[label];
  if (!color || value == null) return null; // unknown label → render nothing (defensive)

  return (
    <Tooltip title={BAR_TITLE[label] || 'Confidence'} arrow>
      <Box
        role="meter"
        aria-label={`Answer confidence: ${label}`}
        aria-valuenow={value}
        aria-valuemin={0}
        aria-valuemax={100}
        sx={{
          width: 48,
          height: 3,
          borderRadius: 4,
          bgcolor: 'action.hover',
          overflow: 'hidden',
          display: 'inline-flex',
          flexShrink: 0,
          cursor: 'help',
        }}
      >
        <Box sx={{ width: `${value}%`, height: '100%', bgcolor: color, borderRadius: 4 }} />
      </Box>
    </Tooltip>
  );
}

ConfidenceIndicator.propTypes = {
  label: PropTypes.string,
  honest: PropTypes.bool,
};

export default ConfidenceIndicator;
