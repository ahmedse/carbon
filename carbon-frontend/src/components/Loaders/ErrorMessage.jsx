import React from 'react';
import PropTypes from 'prop-types';
import { Alert } from '@mui/material';

function ErrorMessage({ message }) {
  return <Alert severity="error">{message}</Alert>;
}

ErrorMessage.propTypes = {
  message: PropTypes.string.isRequired,
};

export default React.memo(ErrorMessage);
