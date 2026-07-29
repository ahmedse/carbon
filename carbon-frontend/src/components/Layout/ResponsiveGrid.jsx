import React from 'react';
import PropTypes from 'prop-types';
import { Grid } from '@mui/material';

function ResponsiveGrid({ children, spacing, columns }) {
  return (
    <Grid container spacing={spacing} columns={columns}>
      {React.Children.map(children, (child) => (
        <Grid size={{ xs: 12, sm: 6, md: 4 }}>
          {child}
        </Grid>
      ))}
    </Grid>
  );
}

ResponsiveGrid.propTypes = {
  children: PropTypes.node,
  spacing: PropTypes.number,
  columns: PropTypes.oneOfType([PropTypes.number, PropTypes.arrayOf(PropTypes.number)]),
};

ResponsiveGrid.defaultProps = {
  children: null,
  spacing: 2,
  columns: 12,
};

export default React.memo(ResponsiveGrid);
