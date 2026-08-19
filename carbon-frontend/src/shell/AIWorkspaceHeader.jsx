// src/shell/AIWorkspaceHeader.jsx
import React from 'react';
import PropTypes from 'prop-types';
import { Box, IconButton, Tooltip } from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import PulseLogo from './PulseLogo';
import AIContextMenu from './AIContextMenu';

function AIWorkspaceHeader({ onClose, conversationId, onConversationUpdated, onForked }) {
  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        px: 1.5,
        py: 0.75,
        borderBottom: 1,
        borderColor: 'divider',
        bgcolor: 'background.paper',
        minHeight: 40,
      }}
    >
      <PulseLogo size={20} showWordmark sx={{ flex: 1 }} />
      <AIContextMenu
        conversationId={conversationId}
        onConversationUpdated={onConversationUpdated}
        onForked={onForked}
      />
      <Tooltip title="Close Pulse (Ctrl+\)">
        <IconButton
          size="small"
          onClick={onClose}
          aria-label="Close Pulse"
        >
          <CloseIcon fontSize="small" />
        </IconButton>
      </Tooltip>
    </Box>
  );
}

AIWorkspaceHeader.propTypes = {
  onClose: PropTypes.func.isRequired,
  conversationId: PropTypes.string,
  onConversationUpdated: PropTypes.func,
  onForked: PropTypes.func,
};

export default AIWorkspaceHeader;
