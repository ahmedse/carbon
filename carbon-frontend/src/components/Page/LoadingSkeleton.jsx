import React from 'react';
import PropTypes from 'prop-types';
import { Box, Skeleton, Paper } from '@mui/material';

function LoadingSkeleton({ variant }) {
  if (variant === 'card') {
    return (
      <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, borderColor: 'divider' }}>
        <Skeleton variant="rounded" width="40%" height={24} sx={{ mb: 1 }} />
        <Skeleton variant="rounded" width="100%" height={40} />
      </Paper>
    );
  }
  if (variant === 'table') {
    return (
      <Box sx={{ width: '100%' }}>
        <Skeleton variant="rounded" width="40%" height={24} sx={{ mb: 2 }} />
        {[...Array(10)].map((_, index) => (
          <Skeleton key={index} variant="rounded" width="100%" height={32} sx={{ mb: 1 }} />
        ))}
      </Box>
    );
  }
  if (variant === 'detail') {
    return (
      <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', md: '2fr 1fr' } }}>
        <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, borderColor: 'divider' }}>
          <Skeleton variant="rounded" width="30%" height={24} sx={{ mb: 2 }} />
          <Skeleton variant="rounded" width="100%" height={200} />
        </Paper>
        <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, borderColor: 'divider' }}>
          <Skeleton variant="rounded" width="70%" height={24} sx={{ mb: 2 }} />
          <Skeleton variant="rounded" width="100%" height={150} />
        </Paper>
      </Box>
    );
  }
  return (
    <Box sx={{ display: 'grid', gap: 2 }}>
      <Skeleton variant="rounded" width="40%" height={28} sx={{ mb: 1 }} />
      <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', md: 'repeat(5, minmax(0, 1fr))' } }}>
        {[...Array(5)].map((_, index) => (
          <Skeleton key={index} variant="rounded" width="100%" height={104} />
        ))}
      </Box>
      <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', md: 'repeat(3, minmax(0, 1fr))' } }}>
        {[...Array(3)].map((_, index) => (
          <Skeleton key={index} variant="rounded" width="100%" height={120} />
        ))}
      </Box>
    </Box>
  );
}

LoadingSkeleton.propTypes = {
  variant: PropTypes.oneOf(['console', 'table', 'detail', 'card']),
};

LoadingSkeleton.defaultProps = {
  variant: 'console',
};

export default React.memo(LoadingSkeleton);
