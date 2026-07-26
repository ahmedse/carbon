import React from 'react';
import PropTypes from 'prop-types';
import { Drawer, Box, IconButton, Typography, useTheme } from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';

function RightPanel({ open, onClose, title, width, children }) {
  const theme = useTheme();
  const isMobile = typeof window !== 'undefined' ? window.innerWidth < 768 : false;

  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={onClose}
      variant={isMobile ? 'temporary' : 'persistent'}
      PaperProps={{
        sx: {
          width: width || 320,
          borderLeft: '1px solid',
          borderColor: 'divider',
          bgcolor: 'background.paper',
        },
      }}
    >
      <Box sx={{ p: 2, borderBottom: '1px solid', borderColor: 'divider', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Typography sx={{ fontSize: '0.95rem', fontWeight: 600 }}>{title}</Typography>
        <IconButton size="small" onClick={onClose}>
          <CloseIcon fontSize="small" />
        </IconButton>
      </Box>
      <Box sx={{ p: 2, overflowY: 'auto', height: '100%' }}>{children}</Box>
    </Drawer>
  );
}

RightPanel.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  title: PropTypes.string.isRequired,
  width: PropTypes.number,
  children: PropTypes.node,
};

RightPanel.defaultProps = {
  width: 320,
  children: null,
};

export default React.memo(RightPanel);
