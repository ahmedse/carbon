// File: src/components/HeaderNew.jsx
// Compact 35px header with Gigacast-inspired design (gradient overlay, role badges)

import React, { useState } from 'react';
import { Box, Typography, IconButton, Popover, Tooltip, Divider, Avatar } from '@mui/material';
import { LightMode, DarkMode, SettingsOutlined, LogoutOutlined, KeyboardOutlined } from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { useThemeMode } from '../theme/ThemeContext';
import { useAuth } from '../auth/AuthContext';
import { KeyboardShortcutsHelp } from '../shell/KeyboardShortcutsHelp';
import aastLogo from '../assets/aast_carbon_logo_.jpg';

// Role badge styling
const ROLE_COLOR = {
  admin: { bg: 'rgba(220,38,38,0.1)', text: '#dc2626' },
  org_steward: { bg: 'rgba(37,99,235,0.1)', text: '#2563eb' },
  data_owner: { bg: 'rgba(37,99,235,0.1)', text: '#2563eb' },
  auditor: { bg: 'rgba(245,158,11,0.1)', text: '#d97706' },
};

function RoleBadge({ role }) {
  const displayRole = role === 'org_steward' ? 'steward' : role;
  const style = ROLE_COLOR[role] || { bg: 'rgba(113,113,122,0.1)', text: '#71717a' };
  
  return (
    <Box sx={{ display: 'inline-flex', px: 0.75, py: 0.125, borderRadius: 0.5, bgcolor: style.bg }}>
      <Typography
        sx={{
          fontSize: '0.5625rem',
          fontWeight: 700,
          color: style.text,
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
        }}
      >
        {displayRole}
      </Typography>
    </Box>
  );
}

function MenuRow({ icon: Icon, label, onClick, danger }) {
  return (
    <Box
      onClick={onClick}
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 1,
        px: 1.5,
        py: 0.875,
        cursor: 'pointer',
        borderRadius: 0.75,
        mx: 0.5,
        color: danger ? 'error.main' : 'text.secondary',
        '&:hover': {
          bgcolor: 'action.hover',
          color: danger ? 'error.main' : 'text.primary',
        },
        transition: 'background 120ms',
      }}
    >
      <Icon sx={{ fontSize: 13, flexShrink: 0 }} />
      <Typography sx={{ fontSize: '0.75rem' }}>{label}</Typography>
    </Box>
  );
}

export default function HeaderNew() {
  const { user, logout } = useAuth();
  const { mode, toggleTheme } = useThemeMode();
  const navigate = useNavigate();
  const [anchorEl, setAnchorEl] = useState(null);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);

  const initials = user?.username ? user.username.slice(0, 2).toUpperCase() : 'CB';
  
  // Get primary role from user groups
  const primaryRole = user?.groups?.[0]?.name?.toLowerCase() || null;

  const close = () => setAnchorEl(null);

  return (
    <Box
      component="header"
      sx={{
        height: 35,
        minHeight: 35,
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        px: 1.25,
        bgcolor: 'background.paper',
        borderBottom: '1px solid',
        borderColor: 'divider',
        flexShrink: 0,
        zIndex: (t) => t.zIndex.drawer + 1,
        gap: 1,
        overflow: 'hidden',
        // Gradient overlay for brand identity
        '&::after': {
          content: '""',
          position: 'absolute',
          inset: 0,
          pointerEvents: 'none',
          background: (t) =>
            t.palette.mode === 'light'
              ? 'linear-gradient(90deg, rgba(14,165,233,0.08) 0%, rgba(14,165,233,0.02) 22%, transparent 55%, rgba(15,23,42,0.03) 100%)'
              : 'linear-gradient(90deg, rgba(56,189,248,0.12) 0%, rgba(56,189,248,0.04) 20%, transparent 55%, rgba(148,163,184,0.05) 100%)',
        },
      }}
    >
      {/* Brand pill */}
      <Box
        sx={{
          position: 'relative',
          zIndex: 1,
          display: 'flex',
          alignItems: 'center',
          gap: 0.875,
          px: 0.75,
          py: 0.375,
          borderRadius: 1.25,
          border: '1px solid',
          borderColor: 'divider',
          bgcolor: (t) =>
            t.palette.mode === 'light' ? 'rgba(255,255,255,0.82)' : 'rgba(15,23,42,0.72)',
          boxShadow: (t) =>
            t.palette.mode === 'light'
              ? '0 1px 2px rgba(15,23,42,0.06)'
              : 'inset 0 1px 0 rgba(255,255,255,0.04)',
        }}
      >
        <Box
          sx={{
            width: 20,
            height: 20,
            borderRadius: 0.875,
            bgcolor: 'common.white',
            border: '1px solid',
            borderColor: 'rgba(148,163,184,0.25)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
            boxShadow: '0 1px 2px rgba(15,23,42,0.08)',
          }}
        >
          <img
            src={aastLogo}
            alt=""
            style={{ width: 14, height: 14, borderRadius: 4, objectFit: 'cover' }}
          />
        </Box>
        <Typography
          sx={{
            fontSize: '0.75rem',
            fontWeight: 700,
            letterSpacing: '-0.02em',
            color: 'text.primary',
            userSelect: 'none',
            lineHeight: 1,
          }}
        >
          Carbon
        </Typography>
      </Box>

      <Box sx={{ flex: 1 }} />

      {/* Compact action bar */}
      <Box
        sx={{
          position: 'relative',
          zIndex: 1,
          display: 'flex',
          alignItems: 'center',
          gap: 0.5,
          px: 0.5,
          py: 0.375,
          borderRadius: 999,
          border: '1px solid',
          borderColor: 'divider',
          bgcolor: (t) =>
            t.palette.mode === 'light' ? 'rgba(255,255,255,0.88)' : 'rgba(15,23,42,0.74)',
          boxShadow: (t) =>
            t.palette.mode === 'light'
              ? '0 1px 2px rgba(15,23,42,0.06)'
              : 'inset 0 1px 0 rgba(255,255,255,0.04)',
        }}
      >
        {/* Theme toggle */}
        <Tooltip title={mode === 'light' ? 'Dark mode' : 'Light mode'}>
          <IconButton
            size="small"
            onClick={toggleTheme}
            sx={{
              width: 26,
              height: 26,
              borderRadius: 999,
              color: 'text.secondary',
              '&:hover': { bgcolor: 'action.hover', color: 'text.primary' },
            }}
          >
            {mode === 'light' ? <DarkMode sx={{ fontSize: 14 }} /> : <LightMode sx={{ fontSize: 14 }} />}
          </IconButton>
        </Tooltip>

        <Divider flexItem orientation="vertical" sx={{ my: 0.375 }} />

        {/* User avatar */}
        <Tooltip title={user?.username || 'Account'}>
          <Box
            onClick={(e) => setAnchorEl(e.currentTarget)}
            sx={{
              width: 26,
              height: 26,
              borderRadius: '50%',
              bgcolor: 'primary.main',
              border: '1px solid rgba(255,255,255,0.75)',
              boxShadow: '0 1px 2px rgba(15,23,42,0.18)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              userSelect: 'none',
              fontSize: '0.625rem',
              fontWeight: 700,
              color: '#fff',
              transition: 'transform 120ms ease, box-shadow 120ms ease',
              '&:hover': {
                transform: 'translateY(-1px)',
                boxShadow: '0 3px 8px rgba(15,23,42,0.18)',
              },
            }}
          >
            {initials}
          </Box>
        </Tooltip>
      </Box>

      {/* User popover menu */}
      <Popover
        open={!!anchorEl}
        anchorEl={anchorEl}
        onClose={close}
        anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
        transformOrigin={{ horizontal: 'right', vertical: 'top' }}
        slotProps={{
          paper: {
            sx: {
              width: 220,
              mt: 0.5,
              borderRadius: 1.5,
              border: '1px solid',
              borderColor: 'divider',
              boxShadow: '0 4px 16px rgba(0,0,0,0.12)',
              py: 0.5,
            },
          },
        }}
      >
        {/* Identity block */}
        <Box sx={{ px: 1.5, pt: 1.25, pb: 1 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.625 }}>
            <Box
              sx={{
                width: 30,
                height: 30,
                borderRadius: '50%',
                bgcolor: 'primary.main',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '0.6875rem',
                fontWeight: 700,
                color: '#fff',
                flexShrink: 0,
              }}
            >
              {initials}
            </Box>
            <Box sx={{ minWidth: 0 }}>
              <Typography sx={{ fontSize: '0.75rem', fontWeight: 600, color: 'text.primary', lineHeight: 1.3 }}>
                {user?.username || '—'}
              </Typography>
              {user?.email && (
                <Typography
                  sx={{
                    fontSize: '0.5625rem',
                    color: 'text.disabled',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {user.email}
                </Typography>
              )}
            </Box>
          </Box>
          {primaryRole && <RoleBadge role={primaryRole} />}
        </Box>

        <Divider sx={{ my: 0.5 }} />

        <MenuRow icon={SettingsOutlined} label="Account Settings" onClick={() => { navigate('/settings'); close(); }} />
        <MenuRow icon={KeyboardOutlined} label="Keyboard Shortcuts" onClick={() => { setShortcutsOpen(true); close(); }} />

        <Divider sx={{ my: 0.5 }} />

        <MenuRow icon={LogoutOutlined} label="Sign out" onClick={() => { logout(); close(); }} danger />
      </Popover>

      {/* Keyboard Shortcuts Help Dialog */}
      <KeyboardShortcutsHelp open={shortcutsOpen} onClose={() => setShortcutsOpen(false)} />
    </Box>
  );
}
