import React from 'react';
import PropTypes from 'prop-types';
import { Box, Typography } from '@mui/material';

const STATUS_COLOR = {
  active: 'success.main',
  paused: 'warning.main',
  draft: 'text.secondary',
  warning: 'warning.main',
  error: 'error.main',
};

function StatusBubble({ status, label }) {
  const color = STATUS_COLOR[status] || 'text.secondary';

  return (
    <Box sx={{ display: 'inline-flex', alignItems: 'center', borderRadius: 999, bgcolor: `${color}20`, px: 1.5, py: 0.5 }}>
      <Box sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: color, mr: 1 }} />
      <Typography sx={{ fontSize: '0.75rem', color }}>{label || status}</Typography>
    </Box>
  );
}

StatusBubble.propTypes = {
  status: PropTypes.string,
  label: PropTypes.string,
};

StatusBubble.defaultProps = {
  status: 'draft',
  label: '',
};

export default React.memo(StatusBubble);
