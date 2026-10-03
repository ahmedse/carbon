// src/components/NumericText.jsx
// Layer-2 primitive: a tabular / monospace numeric run (design-system RULE 3).
//
// Numbers, IDs and timestamps are monospace for scannability. Tabular figures
// stop digit columns from shifting between rows. The value itself is formatted
// by the shared formatter at the call site — this component only owns the
// typographic treatment, so no page-local font styling is needed.
import React from 'react';
import PropTypes from 'prop-types';
import { Typography } from '@mui/material';

function NumericText({ children, variant = 'body2', align = 'right', component = 'span', sx }) {
  return (
    <Typography
      component={component}
      variant={variant}
      dir="ltr"
      sx={{ fontVariantNumeric: 'tabular-nums', textAlign: align, ...sx }}
    >
      {children}
    </Typography>
  );
}

NumericText.propTypes = {
  children: PropTypes.node,
  variant: PropTypes.string,
  align: PropTypes.oneOf(['left', 'right', 'center']),
  component: PropTypes.elementType,
  sx: PropTypes.oneOfType([PropTypes.object, PropTypes.array, PropTypes.func]),
};

NumericText.defaultProps = {
  children: null,
  variant: 'body2',
  align: 'right',
  component: 'span',
  sx: undefined,
};

export default React.memo(NumericText);
