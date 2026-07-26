import React from 'react';
import PropTypes from 'prop-types';
import { Box, CircularProgress, Typography } from '@mui/material';

function LoadingScreen({ message }) {
  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', px: 3, py: 6 }}>
      <CircularProgress />
      <Typography sx={{ mt: 2, color: 'text.secondary' }}>{message}</Typography>
    </Box>
  );
}

LoadingScreen.propTypes = {
  message: PropTypes.string,
};

LoadingScreen.defaultProps = {
  message: 'Loading…',
};

export default React.memo(LoadingScreen);
