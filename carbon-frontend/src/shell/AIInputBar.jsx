// src/shell/AIInputBar.jsx
import React, { useCallback, useRef } from 'react';
import PropTypes from 'prop-types';
import { Box, IconButton, TextField, Tooltip } from '@mui/material';
import SendIcon from '@mui/icons-material/Send';

const PLACEHOLDER_MAP = {
  working: 'AI is thinking…',
  needs_input: 'Respond to AI\'s question…',
  default: 'Ask a question or give directions…',
};

function AIInputBar({ onSend, disabled, conversationStatus }) {
  const inputRef = useRef(null);

  const handleKeyDown = useCallback(
    (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        const val = inputRef.current?.value?.trim();
        if (val && !disabled) {
          onSend(val);
          if (inputRef.current) inputRef.current.value = '';
        }
      }
    },
    [onSend, disabled],
  );

  const handleClick = useCallback(() => {
    const val = inputRef.current?.value?.trim();
    if (val && !disabled) {
      onSend(val);
      if (inputRef.current) inputRef.current.value = '';
    }
  }, [onSend, disabled]);

  const placeholder =
    disabled && conversationStatus === 'working'
      ? PLACEHOLDER_MAP.working
      : conversationStatus === 'needs_input'
        ? PLACEHOLDER_MAP.needs_input
        : PLACEHOLDER_MAP.default;

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'flex-end',
        gap: 0.5,
        px: 1.5,
        py: 1,
        borderTop: 1,
        borderColor: 'divider',
        bgcolor: 'background.paper',
      }}
    >
      <TextField
        inputRef={inputRef}
        fullWidth
        multiline
        minRows={1}
        maxRows={4}
        size="small"
        placeholder={placeholder}
        disabled={disabled}
        onKeyDown={handleKeyDown}
        sx={{
          '& .MuiOutlinedInput-root': {
            fontSize: '0.8125rem',
            bgcolor: 'action.hover',
          },
        }}
        inputProps={{ 'aria-label': 'Message input' }}
      />
      <Tooltip title="Send message (Enter)">
        <span>
          <IconButton
            size="small"
            color="primary"
            onClick={handleClick}
            disabled={disabled}
            aria-label="Send message"
          >
            <SendIcon fontSize="small" />
          </IconButton>
        </span>
      </Tooltip>
    </Box>
  );
}

AIInputBar.propTypes = {
  onSend: PropTypes.func.isRequired,
  disabled: PropTypes.bool,
  conversationStatus: PropTypes.string,
};

export default AIInputBar;
