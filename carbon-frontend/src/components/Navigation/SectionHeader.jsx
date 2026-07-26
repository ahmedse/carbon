import React from 'react';
import PropTypes from 'prop-types';
import { Box, Typography } from '@mui/material';

function SectionHeader({ title, subtitle, trailing }) {
  return (
    <Box sx={{ display: 'flex', flexDirection: { xs: 'column', sm: 'row' }, alignItems: { xs: 'flex-start', sm: 'center' }, justifyContent: 'space-between', gap: 1, mb: 2 }}>
      <Box>
        <Typography sx={{ fontSize: '1.1rem', fontWeight: 700 }}>{title}</Typography>
        {subtitle && (
          <Typography sx={{ fontSize: '0.85rem', color: 'text.secondary', mt: 0.5 }}>{subtitle}</Typography>
        )}
      </Box>
      {trailing && <Box>{trailing}</Box>}
    </Box>
  );
}

SectionHeader.propTypes = {
  title: PropTypes.string.isRequired,
  subtitle: PropTypes.string,
  trailing: PropTypes.node,
};

SectionHeader.defaultProps = {
  subtitle: '',
  trailing: null,
};

export default React.memo(SectionHeader);
