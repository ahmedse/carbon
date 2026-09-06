// src/shell/PlanningHeader.jsx
// Wave F3-F + S-TRACE-01 — a collapsible "Considered: …" planning pill shown
// above assistant answers. Outcome language only (RULE_23 — the step's
// human-readable step_label, never raw result JSON). S-TRACE-01 enriches each
// step with the tool name, a sanitized input summary, and a sanitized output
// summary — the "why this answer" payload is rendered without lossy remap
// (S-TRACE-04). Theme tokens only (RULE_8). Keyboard-complete via a real
// <button> (MUI Button — Enter/Space toggle), aria-expanded on the trigger.
// Expanded state is persisted to localStorage (`pulse.planningHeader.expanded`).
import { useState } from 'react';
import PropTypes from 'prop-types';
import { Box, Button, Chip, Paper, Stack, Typography } from '@mui/material';
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

// S-TRACE-01 — build the outcome-language detail line for a single step:
// the tool name, the sanitized input, and the sanitized output, joined with a
// " → " so input→output provenance is visible at a glance. Falls back
// gracefully for pre-S-TRACE-01 steps that only carry step_label/tool_id.
function buildDetail(step) {
  if (!step || typeof step !== 'object') return '';
  const tool = typeof step.tool === 'string' ? step.tool.trim() : '';
  const input = typeof step.input === 'string' ? step.input.trim() : '';
  const output = typeof step.output === 'string' ? step.output.trim() : '';
  const parts = [];
  if (input || output) {
    parts.push(input && output ? `${input} → ${output}` : input || output);
  }
  if (tool) parts.unshift(tool);
  return parts.join(' · ');
}

function confidenceColor(confidence) {
  return confidence === 'high' ? 'success' : confidence === 'low' ? 'warning' : 'default';
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

  const firstLabel = trace[0]?.step_label || trace[0]?.tool || '';
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
          <Stack spacing={1}>
            {trace.map((step, idx) => {
              const stepLabel = step?.step_label || step?.tool || '';
              const detail = buildDetail(step);
              const confidence =
                typeof step?.confidence === 'string' ? step.confidence : '';
              return (
                <Stack
                  key={`${stepLabel || 'step'}-${idx}`}
                  spacing={0.25}
                >
                  <Stack
                    direction="row"
                    justifyContent="space-between"
                    alignItems="baseline"
                    spacing={1}
                  >
                    <Typography variant="caption" sx={{ color: 'text.primary', fontWeight: 500 }}>
                      {stepLabel}
                    </Typography>
                    <Typography variant="caption" sx={{ color: 'text.secondary', whiteSpace: 'nowrap' }}>
                      {formatDuration(step?.duration_ms)}
                    </Typography>
                  </Stack>
                  {(detail || confidence) && (
                    <Stack direction="row" spacing={0.5} alignItems="center" flexWrap="wrap">
                      {confidence && (
                        <Chip
                          size="small"
                          variant="outlined"
                          color={confidenceColor(confidence)}
                          label={confidence}
                          sx={{ height: 16, '& .MuiChip-label': { px: 0.75, fontSize: '0.62rem' } }}
                        />
                      )}
                      {detail && (
                        <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                          {detail}
                        </Typography>
                      )}
                    </Stack>
                  )}
                </Stack>
              );
            })}
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
      tool: PropTypes.string,
      input: PropTypes.string,
      output: PropTypes.string,
      confidence: PropTypes.string,
      duration_ms: PropTypes.number,
    }),
  ),
};

export default PlanningHeader;
