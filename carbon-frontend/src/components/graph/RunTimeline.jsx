// src/components/graph/RunTimeline.jsx
// W3-G — AI Admin run timeline: cross-user run observation for admins, built
// from GET /ai/runs/{id}/timeline/ — an ordered, read-only event log
// {run_id, status, events:[{t, kind, step_id?, detail?}]}. This is the
// OBSERVE surface — resume/replay live in the parent panel (RULE_21 gates).
//
// No @mui/lab (not a dependency) — the timeline is an ordered vertical list
// of theme-token dots (Stack/Paper/Chip/Box). Theme tokens only (RULE_8);
// outcome labels only (RULE_23). Mirrors the PlanDagGraph header pattern.
import React, { useMemo } from 'react';
import PropTypes from 'prop-types';
import { Box, Chip, Paper, Stack, Typography, useTheme } from '@mui/material';
import TimelineOutlinedIcon from '@mui/icons-material/TimelineOutlined';

/**
 * Event kind → {color, label} theme mapping (exported for tests).
 * @param {string} kind - durable event kind (plan_created, step_completed, …)
 * @param {object} theme - MUI theme
 * @returns {{color: string, label: string}}
 */
export function timelineEventMeta(kind, theme) {
  switch (kind) {
    case 'plan_created':
      return { color: theme.palette.primary.main, label: 'Plan created' };
    case 'plan_forked':
      return { color: theme.palette.info.main, label: 'Plan forked' };
    case 'plan_replayed':
      return { color: theme.palette.warning.main, label: 'Replay staged' };
    case 'step_pending':
      return { color: theme.palette.text.disabled, label: 'Step pending' };
    case 'step_running':
      return { color: theme.palette.primary.main, label: 'Step running' };
    case 'step_completed':
      return { color: theme.palette.success.main, label: 'Step completed' };
    case 'step_failed':
      return { color: theme.palette.error.main, label: 'Step failed' };
    case 'step_skipped':
      return { color: theme.palette.text.disabled, label: 'Step skipped' };
    case 'step_awaiting_approval':
      return { color: theme.palette.warning.main, label: 'Step awaits approval' };
    case 'step_edited':
      return { color: theme.palette.info.main, label: 'Step edited' };
    case 'run_running':
      return { color: theme.palette.primary.main, label: 'Run started' };
    case 'run_completed':
      return { color: theme.palette.success.main, label: 'Run completed' };
    case 'run_failed':
      return { color: theme.palette.error.main, label: 'Run failed' };
    case 'run_paused':
      return { color: theme.palette.warning.main, label: 'Run paused' };
    case 'run_cancelled':
      return { color: theme.palette.error.main, label: 'Run cancelled' };
    case 'run_resumed':
      return { color: theme.palette.info.main, label: 'Run resumed' };
    case 'run_replayed':
      return { color: theme.palette.warning.main, label: 'Replay re-staged' };
    default:
      return { color: theme.palette.text.disabled, label: kind || 'Event' };
  }
}

/** Compact human-readable detail line for an event payload (RULE_23 labels). */
export function eventDetailText(detail) {
  if (detail == null) return '';
  if (typeof detail === 'string') return detail;
  if (typeof detail !== 'object') return String(detail);
  const parts = [];
  if (detail.intent) parts.push(`intent: ${detail.intent}`);
  if (detail.from_plan_id) parts.push(`from: ${detail.from_plan_id}`);
  if (detail.of) parts.push(`of: ${detail.of}`);
  if (detail.brief) parts.push(`brief: ${detail.brief}`);
  if (parts.length === 0) {
    try {
      return JSON.stringify(detail);
    } catch {
      return '';
    }
  }
  return parts.join(' · ');
}

/**
 * Ordered run event log.
 * @param {object} props
 * @param {{run_id: string, status: string, events: Array<{t, kind, step_id?, detail?}>}} props.timeline
 * @param {string} [props.testId] - data-testid
 */
export default function RunTimeline({ timeline, testId = 'run-timeline' }) {
  const theme = useTheme();

  const events = useMemo(
    () => (Array.isArray(timeline?.events) ? timeline.events : []),
    [timeline],
  );

  const statusMeta = useMemo(() => {
    if (!timeline?.status) return null;
    const map = {
      running: { color: theme.palette.primary.main, label: 'running' },
      completed: { color: theme.palette.success.main, label: 'completed' },
      failed: { color: theme.palette.error.main, label: 'failed' },
      paused: { color: theme.palette.warning.main, label: 'paused' },
      cancelled: { color: theme.palette.error.main, label: 'cancelled' },
      approved: { color: theme.palette.success.main, label: 'approved' },
      pending_approval: { color: theme.palette.warning.main, label: 'pending approval' },
      replaying: { color: theme.palette.warning.main, label: 'replay staged' },
    };
    return map[timeline.status] || { color: theme.palette.text.disabled, label: timeline.status };
  }, [timeline, theme]);

  const formatTime = (t) => {
    if (!t) return '—';
    const d = new Date(t);
    if (Number.isNaN(d.getTime())) return String(t);
    return d.toLocaleString();
  };

  return (
    <Paper variant="outlined" sx={{ bgcolor: 'background.paper', overflow: 'hidden' }} data-testid={testId}>
      <Stack
        direction="row"
        alignItems="center"
        spacing={1}
        sx={{ px: 1.25, py: 0.625, borderBottom: 1, borderColor: 'divider' }}
      >
        <TimelineOutlinedIcon sx={{ fontSize: 15, color: 'text.secondary' }} />
        <Typography variant="body2" sx={{ flex: 1, minWidth: 0, fontWeight: 600, fontSize: '0.75rem' }}>
          Run timeline
        </Typography>
        {statusMeta && (
          <Chip
            size="small"
            label={statusMeta.label}
            sx={{
              height: 16,
              fontSize: '0.5625rem',
              color: statusMeta.color,
              borderColor: statusMeta.color,
              bgcolor: 'transparent',
              '& .MuiChip-label': { px: 0.75 },
            }}
            variant="outlined"
          />
        )}
        <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.625rem', whiteSpace: 'nowrap' }}>
          {events.length} event{events.length !== 1 ? 's' : ''}
        </Typography>
      </Stack>

      {events.length === 0 ? (
        <Box sx={{ px: 1.25, py: 2 }}>
          <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
            No timeline events recorded for this run.
          </Typography>
        </Box>
      ) : (
        <Box sx={{ px: 1.25, py: 1 }}>
          <Stack direction="column" spacing={0} divider={<Box sx={{ borderLeft: 1, borderColor: 'divider', ml: 0.5, alignSelf: 'stretch' }} />}>
            {events.map((ev, i) => {
              const meta = timelineEventMeta(ev.kind, theme);
              const detail = eventDetailText(ev.detail);
              return (
                <Stack key={`${ev.kind}-${i}`} direction="row" spacing={1} sx={{ py: 0.5 }}>
                  <Box
                    sx={{
                      width: 9,
                      height: 9,
                      mt: 0.75,
                      borderRadius: '50%',
                      bgcolor: meta.color,
                      flexShrink: 0,
                    }}
                  />
                  <Stack direction="column" spacing={0} sx={{ minWidth: 0 }}>
                    <Stack direction="row" alignItems="center" spacing={1} sx={{ flexWrap: 'wrap', rowGap: 0.25 }}>
                      <Typography variant="body2" sx={{ fontSize: '0.75rem', fontWeight: 600, color: meta.color }}>
                        {meta.label}
                      </Typography>
                      {ev.step_id !== undefined && ev.step_id !== null && (
                        <Chip
                          size="small"
                          label={`step ${ev.step_id}`}
                          sx={{ height: 15, fontSize: '0.5625rem', color: 'text.secondary' }}
                          variant="outlined"
                        />
                      )}
                      <Typography variant="caption" color="text.disabled" sx={{ fontSize: '0.625rem', whiteSpace: 'nowrap' }}>
                        {formatTime(ev.t)}
                      </Typography>
                    </Stack>
                    {detail && (
                      <Typography
                        variant="caption"
                        color="text.secondary"
                        sx={{ fontSize: '0.6875rem', overflowWrap: 'anywhere' }}
                      >
                        {detail}
                      </Typography>
                    )}
                  </Stack>
                </Stack>
              );
            })}
          </Stack>
        </Box>
      )}
    </Paper>
  );
}

RunTimeline.propTypes = {
  timeline: PropTypes.shape({
    run_id: PropTypes.string,
    status: PropTypes.string,
    events: PropTypes.array,
  }),
  testId: PropTypes.string,
};
