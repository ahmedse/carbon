import React from 'react';
import PropTypes from 'prop-types';
import { Box, Paper, Typography } from '@mui/material';

function StatCard({ label, value, unit, delta, description, highlight }) {
  return (
    <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, bgcolor: highlight ? 'action.selected' : 'background.paper', borderColor: 'divider', minWidth: 0 }}> 
      <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary', mb: 0.5 }}>{label}</Typography>
      <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1, flexWrap: 'wrap' }}>
        <Typography sx={{ fontSize: '1.5rem', fontWeight: 700 }}>{value}</Typography>
        {unit && <Typography sx={{ fontSize: '0.95rem', color: 'text.secondary' }}>{unit}</Typography>}
      </Box>
      {delta != null && (
        <Typography sx={{ fontSize: '0.75rem', color: delta >= 0 ? 'success.main' : 'error.main', mt: 1 }}>
          {delta >= 0 ? '+' : ''}{delta}%
        </Typography>
      )}
      {description && (
        <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary', mt: 1 }}>{description}</Typography>
      )}
    </Paper>
  );
}

StatCard.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
  unit: PropTypes.string,
  delta: PropTypes.number,
  description: PropTypes.string,
  highlight: PropTypes.bool,
};

StatCard.defaultProps = {
  unit: '',
  delta: null,
  description: '',
  highlight: false,
};

export default React.memo(StatCard);
