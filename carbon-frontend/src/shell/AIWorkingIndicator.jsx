// src/shell/AIWorkingIndicator.jsx
import React from 'react';
import PropTypes from 'prop-types';
import { Box, Collapse, Stack, Typography, keyframes } from '@mui/material';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';

const pulse = keyframes`
  0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
  40% { opacity: 1; transform: scale(1); }
`;

const DOT_COUNT = 3;

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
}) {
  const fallback = TYPE_MESSAGES[conversationType] || TYPE_MESSAGES.chat;
  const label = stage || (done ? 'Thinking' : fallback);
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
        gap: 1.5,
        py: 1.5,
        px: 2,
        cursor: clickable ? 'pointer' : 'default',
        ...(clickable ? { '&:hover': { bgcolor: 'action.hover' } } : {}),
      }}
    >
      {clickable &&
        (expanded ? (
          <ExpandMoreIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
        ) : (
          <ChevronRightIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
        ))}
      <AutoAwesomeIcon
        sx={{
          fontSize: 18,
          color: done ? 'text.disabled' : 'primary.light',
          animation: done ? 'none' : `${pulse} 1.4s ease-in-out infinite`,
        }}
      />
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
      {!done && (
        <Box sx={{ display: 'flex', gap: 0.5 }}>
          {Array.from({ length: DOT_COUNT }).map((_, i) => (
            <Box
              key={i}
              sx={{
                width: 5,
                height: 5,
                borderRadius: '50%',
                bgcolor: 'primary.light',
                animation: `${pulse} 1.4s ease-in-out ${i * 0.2}s infinite`,
              }}
            />
          ))}
        </Box>
      )}
    </Box>
  );

  if (!collapsible) return header;

  const steps = Array.isArray(history) ? history.filter(Boolean) : [];

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
          ) : (
            <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem' }}>
              Working…
            </Typography>
          )}
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
};

export default AIWorkingIndicator;
