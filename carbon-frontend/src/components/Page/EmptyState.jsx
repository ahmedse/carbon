import React from 'react';
import PropTypes from 'prop-types';
import { Box, Paper, Typography, Button } from '@mui/material';

function EmptyState({ icon, title, description, actionLabel, onAction }) {
  return (
    <Paper variant="outlined" sx={{ p: 6, textAlign: 'center', borderRadius: 2 }}>
      {icon && <Box sx={{ mb: 2, color: 'text.secondary' }}>{React.cloneElement(icon, { sx: { fontSize: 56 } })}</Box>}
      <Typography sx={{ fontSize: '1rem', fontWeight: 600, mb: 1 }}>{title}</Typography>
      {description && <Typography sx={{ fontSize: '0.8125rem', color: 'text.secondary', mb: 2 }}>{description}</Typography>}
      {actionLabel && onAction && (
        <Button variant="outlined" size="small" onClick={onAction}>{actionLabel}</Button>
      )}
    </Paper>
  );
}

EmptyState.propTypes = {
  icon: PropTypes.element,
  title: PropTypes.string.isRequired,
  description: PropTypes.string,
  actionLabel: PropTypes.string,
  onAction: PropTypes.func,
};

EmptyState.defaultProps = {
  icon: null,
  description: '',
  actionLabel: '',
  onAction: undefined,
};

export default React.memo(EmptyState);
