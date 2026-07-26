import React from 'react';
import PropTypes from 'prop-types';
import { Box, Paper, Typography, Button } from '@mui/material';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';

function AlertRow({ title, message, actionLabel, onAction }) {
  return (
    <Paper variant="outlined" sx={{ p: 2, display: 'flex', alignItems: 'center', gap: 2, borderColor: 'warning.main', bgcolor: 'warning.lighter' }}>
      <WarningAmberIcon sx={{ color: 'warning.main' }} />
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Typography sx={{ fontSize: '0.9rem', fontWeight: 700 }}>{title}</Typography>
        <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary' }}>{message}</Typography>
      </Box>
      {onAction && (
        <Button size="small" variant="contained" color="warning" onClick={onAction}>
          {actionLabel}
        </Button>
      )}
    </Paper>
  );
}

AlertRow.propTypes = {
  title: PropTypes.string.isRequired,
  message: PropTypes.string.isRequired,
  actionLabel: PropTypes.string,
  onAction: PropTypes.func,
};

AlertRow.defaultProps = {
  actionLabel: 'Review',
  onAction: undefined,
};

export default React.memo(AlertRow);
