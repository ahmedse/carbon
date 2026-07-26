import React from 'react';
import PropTypes from 'prop-types';
import { Paper, Box } from '@mui/material';

function SectionCard({ title, children, footer, fullWidth }) {
  return (
    <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, width: fullWidth ? '100%' : 'auto', minWidth: 0 }}>
      {title && (
        <Box sx={{ mb: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          {title}
        </Box>
      )}
      <Box>{children}</Box>
      {footer && <Box sx={{ mt: 2 }}>{footer}</Box>}
    </Paper>
  );
}

SectionCard.propTypes = {
  title: PropTypes.node,
  children: PropTypes.node.isRequired,
  footer: PropTypes.node,
  fullWidth: PropTypes.bool,
};

SectionCard.defaultProps = {
  title: null,
  footer: null,
  fullWidth: false,
};

export default React.memo(SectionCard);
