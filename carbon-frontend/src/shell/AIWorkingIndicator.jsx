// src/shell/AIWorkingIndicator.jsx
import React from 'react';
import PropTypes from 'prop-types';
import { Box, Typography, keyframes } from '@mui/material';
import SmartToyIcon from '@mui/icons-material/SmartToy';

const pulse = keyframes`
  0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
  40% { opacity: 1; transform: scale(1); }
`;

const DOT_COUNT = 3;

const TYPE_MESSAGES = {
  dq_suggest: 'AI is analyzing your table profile and generating rule suggestions…',
  nl_query: 'AI is querying your data…',
  anomaly: 'AI is scanning profile history for anomalies…',
  chat: 'AI is thinking…',
};

function AIWorkingIndicator({ conversationType = 'chat' }) {
  const label = TYPE_MESSAGES[conversationType] || TYPE_MESSAGES.chat;

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 1.5,
        py: 1.5,
        px: 2,
      }}
    >
      <SmartToyIcon
        sx={{
          fontSize: 18,
          color: 'primary.light',
          animation: `${pulse} 1.4s ease-in-out infinite`,
        }}
      />
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
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
    </Box>
  );
}

AIWorkingIndicator.propTypes = {
  conversationType: PropTypes.string,
};

export default AIWorkingIndicator;
