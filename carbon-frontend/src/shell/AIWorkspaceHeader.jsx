// src/shell/AIWorkspaceHeader.jsx
import React from 'react';
import PropTypes from 'prop-types';
import { Box, IconButton, Tooltip, Typography } from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import SmartToyIcon from '@mui/icons-material/SmartToy';

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
      <SmartToyIcon sx={{ fontSize: 18, color: 'primary.light', mr: 1 }} />
      <Typography
        variant="subtitle2"
        sx={{ fontWeight: 600, flex: 1, userSelect: 'none' }}
      >
        AI Workspace
      </Typography>
      <Tooltip title="Close AI Workspace (Ctrl+\)">
        <IconButton
          size="small"
          onClick={onClose}
          aria-label="Close AI Workspace"
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
