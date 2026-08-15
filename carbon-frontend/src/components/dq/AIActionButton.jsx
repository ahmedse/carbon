// src/components/dq/AIActionButton.jsx
// Standard compact "AI" action button reused across DQ workspace pages.
//
// The visible label is always just "AI"; the `title` prop supplies the
// descriptive tooltip (and aria-label) so the UI stays terse and consistent
// while still communicating what each button does on hover/screen readers.
import React from 'react';
import PropTypes from 'prop-types';
import { Box, Button, CircularProgress, Tooltip } from '@mui/material';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';

export default function AIActionButton({
  title,
  onClick,
  disabled = false,
  busy = false,
  variant = 'outlined',
  size = 'small',
  ...rest
}) {
  const button = (
    <Button
      {...rest}
      size={size}
      variant={variant}
      startIcon={busy ? <CircularProgress size={14} color="inherit" /> : <AutoAwesomeIcon />}
      onClick={onClick}
      disabled={disabled || busy}
    >
      AI
    </Button>
  );

  return title ? (
    <Tooltip title={title} arrow>
      {/* Wrapper lets the tooltip fire even when the button is disabled. */}
      <Box component="span" sx={{ display: 'inline-flex' }}>
        {button}
      </Box>
    </Tooltip>
  ) : (
    button
  );
}

AIActionButton.propTypes = {
  title: PropTypes.string,
  onClick: PropTypes.func,
  disabled: PropTypes.bool,
  busy: PropTypes.bool,
  variant: PropTypes.string,
  size: PropTypes.string,
};
