// src/shell/AIWorkspaceHeader.jsx
import React from 'react';
import PropTypes from 'prop-types';
import { Box, IconButton, Tooltip } from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import PulseLogo from './PulseLogo';

function AIWorkspaceHeader({ onClose }) {
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
};

export default AIWorkspaceHeader;
