import React from 'react';
import PropTypes from 'prop-types';
import { Alert, Button } from '@mui/material';

function ErrorAlert({ message, onRetry }) {
  return (
    <Alert
      severity="error"
      action={
        onRetry ? (
          <Button color="inherit" size="small" onClick={onRetry}>
            Retry
          </Button>
        ) : null
      }
      sx={{ mb: 2 }}
    >
      {message}
    </Alert>
  );
}

ErrorAlert.propTypes = {
  message: PropTypes.string.isRequired,
  onRetry: PropTypes.func,
};

ErrorAlert.defaultProps = {
  onRetry: undefined,
};

export default React.memo(ErrorAlert);
