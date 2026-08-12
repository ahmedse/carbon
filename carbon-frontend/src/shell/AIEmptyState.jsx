// src/shell/AIEmptyState.jsx
import React from 'react';
import PropTypes from 'prop-types';
import { Box, Button, Typography } from '@mui/material';
import ChatIcon from '@mui/icons-material/Chat';
import SmartToyIcon from '@mui/icons-material/SmartToy';

const ILLUSTRATION_SIZE = 56;

function AIEmptyState({ onStartChat }) {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100%',
        px: 3,
        textAlign: 'center',
        gap: 2,
        color: 'text.secondary',
      }}
    >
      <Box sx={{ position: 'relative', display: 'inline-flex' }}>
        <SmartToyIcon
          sx={{ fontSize: ILLUSTRATION_SIZE, color: 'primary.light', opacity: 0.5 }}
        />
        <ChatIcon
          sx={{
            fontSize: 22,
            color: 'primary.main',
            position: 'absolute',
            bottom: -2,
            right: -6,
          }}
        />
      </Box>

      <Box>
        <Typography variant="subtitle2" color="text.primary" gutterBottom>
          AI Workspace Ready
        </Typography>
        <Typography variant="caption" color="text.disabled">
          Start a chat or transfer a task from the main workspace.
        </Typography>
      </Box>

      {onStartChat && (
        <Button
          variant="outlined"
          size="small"
          startIcon={<ChatIcon />}
          onClick={onStartChat}
        >
          Start a Chat
        </Button>
      )}
    </Box>
  );
}

AIEmptyState.propTypes = {
  onStartChat: PropTypes.func,
};

export default AIEmptyState;
