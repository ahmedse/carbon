// src/shell/PlanningHeader.jsx
// Wave F3-F — a collapsible "Considered: …" planning pill shown above
// multi-step assistant answers. Outcome language only (RULE_23 — the step's
// human-readable step_label + formatted duration, never tool_id or raw JSON).
// Theme tokens only (RULE_8). Keyboard-complete via a real <button> (MUI
// Button — Enter/Space toggle), aria-expanded on the trigger. Expanded state
// is persisted to localStorage (`pulse.planningHeader.expanded`).
import { useState } from 'react';
import PropTypes from 'prop-types';
import { Box, Button, Paper, Stack, Typography } from '@mui/material';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';

const STORAGE_KEY = 'pulse.planningHeader.expanded';
const SUMMARY_MAX = 48;

function readInitialExpanded() {
  try {
    return localStorage.getItem(STORAGE_KEY) === '1';
  } catch {
    return false;
  }
}

function readReducedMotion() {
  try {
    return (
      typeof window !== 'undefined' &&
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
    );
  } catch {
    return false;
  }
}

function truncate(text) {
  const value = String(text || '');
  return value.length > SUMMARY_MAX ? `${value.slice(0, SUMMARY_MAX)}…` : value;
}

function formatDuration(ms) {
  if (typeof ms !== 'number' || Number.isNaN(ms)) return '';
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

function PlanningHeader({ trace }) {
  const [expanded, setExpanded] = useState(readInitialExpanded);
  const [reducedMotion] = useState(readReducedMotion);

  if (!Array.isArray(trace) || trace.length === 0) return null;

  const toggle = () => {
    const next = !expanded;
    setExpanded(next);
    try {
      localStorage.setItem(STORAGE_KEY, next ? '1' : '0');
    } catch {
      // ignore — SSR / storage-disabled environments
    }
  };

  const firstLabel = trace[0]?.step_label || '';
  const summary = truncate(firstLabel);
  const more = trace.length > 1 ? ` · +${trace.length - 1} more` : '';
  const label = `Considered: ${summary}${more}`;

  return (
    <Box sx={{ mb: 0.5 }}>
      <Button
        size="small"
        variant="outlined"
        color="inherit"
        onClick={toggle}
        aria-expanded={expanded}
        aria-label={expanded ? 'Hide planning steps' : 'Show planning steps'}
        startIcon={
          expanded ? (
            <ExpandLessIcon sx={{ fontSize: 16 }} />
          ) : (
            <ExpandMoreIcon sx={{ fontSize: 16 }} />
          )
        }
        sx={{
          textTransform: 'none',
          py: 0.25,
          px: 1,
          lineHeight: 1.4,
          fontSize: '0.75rem',
          ...(reducedMotion ? {} : { transition: 'background-color 150ms ease' }),
        }}
      >
        {label}
      </Button>

      {expanded && (
        <Paper variant="outlined" sx={{ mt: 0.5, p: 1, bgcolor: 'background.paper' }}>
          <Stack spacing={0.5}>
            {trace.map((step, idx) => (
              <Stack
                key={`${step?.step_label ?? 'step'}-${idx}`}
                direction="row"
                justifyContent="space-between"
                alignItems="baseline"
                spacing={1}
              >
                <Typography variant="caption" sx={{ color: 'text.primary' }}>
                  {step?.step_label}
                </Typography>
                <Typography variant="caption" sx={{ color: 'text.secondary', whiteSpace: 'nowrap' }}>
                  {formatDuration(step?.duration_ms)}
                </Typography>
              </Stack>
            ))}
          </Stack>
        </Paper>
      )}
    </Box>
  );
}

PlanningHeader.propTypes = {
  trace: PropTypes.arrayOf(
    PropTypes.shape({
      step_label: PropTypes.string,
      tool_id: PropTypes.string,
      duration_ms: PropTypes.number,
    }),
  ),
};

export default PlanningHeader;
