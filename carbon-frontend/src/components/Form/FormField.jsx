import React from 'react';
import PropTypes from 'prop-types';
import { Box, Typography } from '@mui/material';

function FormField({ label, required, helperText, error, children }) {
  return (
    <Box sx={{ mb: 2 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5 }}>
        <Typography sx={{ fontSize: '0.8125rem', fontWeight: 600 }}>{label}</Typography>
        {required && <Typography sx={{ color: 'error.main' }}>*</Typography>}
      </Box>
      {children}
      {helperText && !error && (
        <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary', mt: 0.5 }}>{helperText}</Typography>
      )}
      {error && (
        <Typography sx={{ fontSize: '0.75rem', color: 'error.main', mt: 0.5 }}>{error}</Typography>
      )}
    </Box>
  );
}

FormField.propTypes = {
  label: PropTypes.string.isRequired,
  required: PropTypes.bool,
  helperText: PropTypes.string,
  error: PropTypes.string,
  children: PropTypes.node.isRequired,
};

FormField.defaultProps = {
  required: false,
  helperText: '',
  error: '',
};

export default React.memo(FormField);
