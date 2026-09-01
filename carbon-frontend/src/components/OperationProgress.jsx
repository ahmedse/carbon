import React from 'react';
import PropTypes from 'prop-types';
import { Box, LinearProgress, Typography } from '@mui/material';

/**
 * Narrated long-operation progress (Pulse 0.2 Wave D1).
 *
 * Renders a progress bar PLUS a human-narrated step message — never a bare
 * spinner. The message is announced to screen readers (``aria-live``) so the
 * UI literally "thinks out loud" (Beat 2 made real). Consumes OUTCOME-shaped
 * frames (RULE_23): ``{ status, message, percent }``.
 *
 * Theme tokens only (RULE_8) — no raw colors/spacing.
 */
export default function OperationProgress({ status, message, percent }) {
  if (!status) return null;

  const isQueued = status === 'queued';
  const isRunning = status === 'running';
  const isDone = status === 'done';
  const isFailed = status === 'failed';

  let bar = null;
  if (isQueued) {
    bar = <LinearProgress sx={{ width: '100%' }} />;
  } else if (isRunning) {
    const determinate = Number.isFinite(Number(percent)) && Number(percent) >= 0;
    bar = (
      <LinearProgress
        variant={determinate ? 'determinate' : 'indeterminate'}
        value={determinate ? Number(percent) : undefined}
        sx={{ width: '100%' }}
      />
    );
  }

  const terminalText =
    isDone ? '100%' : isFailed || status === 'canceled' ? '–' : null;

  return (
    <Box sx={{ width: '100%', minWidth: 0 }}>
      {bar}
      {terminalText ? (
        <Typography variant="caption" sx={{ color: 'text.secondary' }}>
          {terminalText}
        </Typography>
      ) : null}
      {message ? (
        <Typography
          variant="caption"
          noWrap
          title={message}
          aria-live="polite"
          sx={{
            color: isFailed ? 'error.main' : 'text.secondary',
            display: 'block',
            mt: 0.5,
          }}
        >
          {message}
        </Typography>
      ) : null}
    </Box>
  );
}

OperationProgress.propTypes = {
  status: PropTypes.string,
  message: PropTypes.string,
  percent: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
};
