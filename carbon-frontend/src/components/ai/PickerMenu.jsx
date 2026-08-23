// src/components/ai/PickerMenu.jsx
// Reusable picker primitives (W8-A). A positioned, scrollable listbox with
// dense, keyboard-navigable option rows. Shared by the Pulse composer (slash
// commands + `#` mentions) and any future picker surface.
// UI + font match ShellSidebar (theme tokens only — no raw hex/px): 0.65rem
// label, 14px icon, left-bar active indicator, action.hover/selected states.
import PropTypes from 'prop-types';
import { Box, List, ListItemButton, Paper, Typography } from '@mui/material';

// Single listbox option row. `ariaLabel` pins the accessible name so tests
// (and screen readers) keep a stable name regardless of badge/description.
export function PickerOption({
  active,
  ariaLabel,
  icon,
  badge,
  title,
  description,
  onClick,
  onHover,
}) {
  return (
    <ListItemButton
      role="option"
      aria-label={ariaLabel}
      aria-selected={active}
      onClick={onClick}
      onMouseEnter={onHover}
      selected={active}
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 0.75,
        minHeight: 28,
        px: 0.75,
        py: 0.125,
        borderRadius: '5px',
        position: 'relative',
        color: active ? 'primary.main' : 'text.secondary',
        transition: 'all 0.12s ease',
        '&:hover': {
          bgcolor: 'action.hover',
          color: active ? 'primary.main' : 'text.primary',
        },
        '&.Mui-selected': {
          bgcolor: (t) => (t.palette.mode === 'light' ? 'rgba(14,165,233,0.07)' : 'rgba(56,189,248,0.1)'),
          color: 'primary.main',
        },
        '&.Mui-selected:hover': {
          bgcolor: (t) => (t.palette.mode === 'light' ? 'rgba(14,165,233,0.07)' : 'rgba(56,189,248,0.1)'),
        },
        // Left-bar active indicator (matches ShellSidebar)
        ...(active && {
          '&::before': {
            content: '""',
            position: 'absolute',
            left: 0,
            top: 6,
            bottom: 6,
            width: 2.5,
            borderRadius: '0 3px 3px 0',
            bgcolor: 'primary.main',
          },
        }),
      }}
    >
      {icon ? (
        <Box
          component="span"
          sx={{
            fontSize: 14,
            flexShrink: 0,
            opacity: active ? 1 : 0.6,
            display: 'inline-flex',
            alignItems: 'center',
          }}
        >
          {icon}
        </Box>
      ) : badge ? (
        <Typography
          component="span"
          noWrap
          sx={{ fontSize: '0.65rem', fontWeight: 500, lineHeight: 1, flexShrink: 0 }}
        >
          {badge}
        </Typography>
      ) : null}
      <Box sx={{ minWidth: 0, flex: 1 }}>
        <Typography noWrap sx={{ fontSize: '0.65rem', lineHeight: 1, fontWeight: active ? 600 : 400 }}>
          {title}
        </Typography>
        {description ? (
          <Typography
            noWrap
            color="text.secondary"
            sx={{ fontSize: '0.575rem', fontWeight: 500, lineHeight: 1, display: 'block', mt: 0.25 }}
          >
            {description}
          </Typography>
        ) : null}
      </Box>
    </ListItemButton>
  );
}

PickerOption.propTypes = {
  active: PropTypes.bool,
  ariaLabel: PropTypes.string.isRequired,
  icon: PropTypes.node,
  badge: PropTypes.string,
  title: PropTypes.node.isRequired,
  description: PropTypes.node,
  onClick: PropTypes.func,
  onHover: PropTypes.func,
};

// Positioned, scrollable listbox that pops up above the composer.
export function PickerMenu({ label, minWidth, maxHeight, children }) {
  return (
    <Paper
      elevation={3}
      role="listbox"
      aria-label={label}
      sx={{
        position: 'absolute',
        bottom: '100%',
        left: 0,
        mb: 0.5,
        zIndex: 10,
        minWidth,
        maxHeight,
        overflowY: 'auto',
        py: 0.25,
      }}
    >
      <List dense disablePadding>{children}</List>
    </Paper>
  );
}

PickerMenu.propTypes = {
  label: PropTypes.string.isRequired,
  minWidth: PropTypes.number,
  maxHeight: PropTypes.number,
  children: PropTypes.node,
};
