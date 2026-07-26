import React from 'react';
import PropTypes from 'prop-types';
import { AppBar, Toolbar, Typography, Box, IconButton } from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';

function TopBar({ title, subtitle, onMenuClick, actions }) {
  return (
    <AppBar position="sticky" color="inherit" elevation={0} sx={{ borderBottom: '1px solid', borderColor: 'divider' }}>
      <Toolbar sx={{ px: { xs: 1.5, sm: 3 }, display: 'flex', gap: 2, flexWrap: 'wrap' }}>
        {onMenuClick && (
          <IconButton edge="start" color="inherit" onClick={onMenuClick} sx={{ mr: 1 }}>
            <MenuIcon />
          </IconButton>
        )}
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography sx={{ fontWeight: 700 }}>{title}</Typography>
          {subtitle && (
            <Typography sx={{ fontSize: '0.85rem', color: 'text.secondary' }}>{subtitle}</Typography>
          )}
        </Box>
        {actions && <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>{actions}</Box>}
      </Toolbar>
    </AppBar>
  );
}

TopBar.propTypes = {
  title: PropTypes.string.isRequired,
  subtitle: PropTypes.string,
  onMenuClick: PropTypes.func,
  actions: PropTypes.node,
};

TopBar.defaultProps = {
  subtitle: '',
  onMenuClick: undefined,
  actions: null,
};

export default React.memo(TopBar);
