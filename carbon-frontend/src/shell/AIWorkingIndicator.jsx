// src/shell/AIWorkingIndicator.jsx
import React from 'react';
import PropTypes from 'prop-types';
import { Box, CircularProgress, Collapse, Stack, Typography } from '@mui/material';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';

const TYPE_MESSAGES = {
  dq_suggest: 'AI is analyzing your data and generating rule suggestions…',
  nl_query: 'AI is querying your data…',
  anomaly: 'AI is scanning your data for anomalies…',
  chat: 'AI is thinking…',
};

function AIWorkingIndicator({
  conversationType = 'chat',
  stage = null,
  collapsible = false,
  expanded = false,
  onToggle = null,
  history = [],
  done = false,
  seconds = null,
}) {
  const fallback = TYPE_MESSAGES[conversationType] || TYPE_MESSAGES.chat;
  // While working: show live stage or fallback. When done: elapsed time, then
  // how many steps it took — the reader sees cost first, detail on expand.
  const steps = Array.isArray(history) ? history.filter(Boolean) : [];
  const took = Number.isFinite(seconds) && seconds > 0 ? `Thought for ${seconds}s` : 'Thought';
  const label = done
    ? `${took} · ${steps.length} step${steps.length !== 1 ? 's' : ''}`
    : (stage || fallback);
  const clickable = collapsible && typeof onToggle === 'function';

  const handleKeyDown = clickable
    ? (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          onToggle();
        }
      }
    : undefined;

  const header = (
    <Box
      onClick={clickable ? onToggle : undefined}
      onKeyDown={handleKeyDown}
      role={clickable ? 'button' : undefined}
      tabIndex={clickable ? 0 : undefined}
      aria-expanded={clickable ? expanded : undefined}
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 1,
        py: 0.75,
        px: 2,
        cursor: clickable ? 'pointer' : 'default',
        userSelect: 'none',
        ...(clickable ? { '&:hover': { bgcolor: 'action.hover', borderRadius: 1 } } : {}),
      }}
    >
      {clickable &&
        (expanded ? (
          <ExpandMoreIcon sx={{ fontSize: 14, color: 'text.disabled' }} />
        ) : (
          <ChevronRightIcon sx={{ fontSize: 14, color: 'text.disabled' }} />
        ))}
      {!done && (
        <CircularProgress size={12} thickness={4} aria-hidden="true" sx={{ color: 'primary.light' }} />
      )}
      <Typography variant="caption" color={done ? 'text.disabled' : 'text.secondary'} sx={{ fontSize: '0.6875rem' }}>
        {label}
      </Typography>
    </Box>
  );

  if (!collapsible) return header;

  return (
    <Box>
      {header}
      <Collapse in={expanded} unmountOnExit>
        <Box sx={{ px: 2, pb: 1, pl: 4.5 }}>
          {steps.length > 0 ? (
            <Stack spacing={0.25}>
              {steps.map((stepLabel, i) => (
                <Box key={`${stepLabel}-${i}`} sx={{ display: 'flex', gap: 1, alignItems: 'baseline' }}>
                  <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.625rem', minWidth: 18, textAlign: 'right' }}>
                    {i + 1}.
                  </Typography>
                  <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem' }}>
                    {stepLabel}
                  </Typography>
                </Box>
              ))}
            </Stack>
          ) : null}
        </Box>
      </Collapse>
    </Box>
  );
}

AIWorkingIndicator.propTypes = {
  conversationType: PropTypes.string,
  stage: PropTypes.string,
  collapsible: PropTypes.bool,
  expanded: PropTypes.bool,
  onToggle: PropTypes.func,
  history: PropTypes.arrayOf(PropTypes.string),
  done: PropTypes.bool,
  seconds: PropTypes.number,
};

export default AIWorkingIndicator;
