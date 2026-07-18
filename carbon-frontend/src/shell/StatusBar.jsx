// File: src/shell/StatusBar.jsx
// 22px bottom status bar with system state, toggle buttons, and footer links

import React, { useState, useEffect } from 'react';
import { Box, Typography, IconButton, Tooltip, Link } from '@mui/material';
import ViewSidebarIcon from '@mui/icons-material/ViewSidebar';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';

export function StatusBar({
  sidebarVisible,
  copilotVisible,
  onToggleSidebar,
  onToggleCopilot,
}) {
  const [systemStatus, setSystemStatus] = useState('ready');

  useEffect(() => {
    // TODO: Poll backend for system status
    // For now, just show ready state
    setSystemStatus('ready');
  }, []);

  const statusColor = systemStatus === 'error' ? '#f87171' :
                      systemStatus === 'processing' ? '#fbbf24' :
                      'rgba(255,255,255,0.7)';
  const statusLabel = systemStatus === 'error' ? 'Error' :
                      systemStatus === 'processing' ? 'Processing' :
                      'Ready';

  return (
    <Box
      component="footer"
      role="contentinfo"
      sx={{
        height: 22,
        minHeight: 22,
        bgcolor: 'primary.main',
        color: '#fff',
        display: 'flex',
        alignItems: 'center',
        px: 1.5,
        flexShrink: 0,
        gap: 1,
      }}
    >
      {/* System status indicator */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
        <Box
          sx={{
            width: 7,
            height: 7,
            borderRadius: '50%',
            bgcolor: statusColor,
            transition: 'background-color 0.3s'
          }}
        />
        <Typography sx={{
          fontSize: '0.6875rem',
          fontWeight: 500,
          color: 'rgba(255,255,255,0.9)',
          userSelect: 'none'
        }}>
          {statusLabel}
        </Typography>
      </Box>

      {/* Copyright and footer links */}
      <Typography sx={{
        fontSize: '0.6875rem',
        opacity: 0.7,
        userSelect: 'none',
        ml: 1,
      }}>
        © {new Date().getFullYear()} AASTMT Carbon Data Trust Platform
      </Typography>

      <Box sx={{ display: 'flex', gap: 1, ml: 1 }}>
        <Link
          href="/help"
          sx={{
            fontSize: '0.6875rem',
            color: 'rgba(255,255,255,0.8)',
            textDecoration: 'none',
            '&:hover': { color: '#fff', textDecoration: 'underline' }
          }}
        >
          Privacy
        </Link>
        <Link
          href="/help"
          sx={{
            fontSize: '0.6875rem',
            color: 'rgba(255,255,255,0.8)',
            textDecoration: 'none',
            '&:hover': { color: '#fff', textDecoration: 'underline' }
          }}
        >
          Terms
        </Link>
        <Link
          href="/feedback"
          sx={{
            fontSize: '0.6875rem',
            color: 'rgba(255,255,255,0.8)',
            textDecoration: 'none',
            '&:hover': { color: '#fff', textDecoration: 'underline' }
          }}
        >
          Support
        </Link>
      </Box>

      <Box sx={{ flex: 1 }} />

      {/* Toggle buttons */}
      <Box sx={{ display: 'flex', gap: 0.25 }}>
        <Tooltip title={`${sidebarVisible ? 'Hide' : 'Show'} Sidebar (Ctrl+B)`} placement="top">
          <IconButton
            size="small"
            onClick={onToggleSidebar}
            aria-label={`${sidebarVisible ? 'Hide' : 'Show'} Sidebar`}
            aria-pressed={sidebarVisible}
            sx={{
              p: 0.25,
              color: 'inherit',
              opacity: sidebarVisible ? 1 : 0.5,
              borderRadius: 0.5,
              '&:hover': {
                opacity: 1,
                bgcolor: 'rgba(255,255,255,0.15)',
              },
              '&:focus-visible': {
                outline: '2px solid',
                outlineColor: '#fff',
                outlineOffset: '2px',
              },
            }}
          >
            <ViewSidebarIcon sx={{ fontSize: 13 }} aria-hidden="true" />
          </IconButton>
        </Tooltip>

        <Tooltip title={`${copilotVisible ? 'Hide' : 'Show'} Pulse (Ctrl+\\)`} placement="top">
          <IconButton
            size="small"
            onClick={onToggleCopilot}
            aria-label={`${copilotVisible ? 'Hide' : 'Show'} Pulse Copilot`}
            aria-pressed={copilotVisible}
            sx={{
              p: 0.25,
              color: 'inherit',
              opacity: copilotVisible ? 1 : 0.5,
              borderRadius: 0.5,
              '&:hover': {
                opacity: 1,
                bgcolor: 'rgba(255,255,255,0.15)',
              },
              '&:focus-visible': {
                outline: '2px solid',
                outlineColor: '#fff',
                outlineOffset: '2px',
              },
            }}
          >
            <AutoAwesomeIcon sx={{ fontSize: 13 }} aria-hidden="true" />
          </IconButton>
        </Tooltip>
      </Box>

      {/* Version */}
      <Typography sx={{
        fontSize: '0.6875rem',
        opacity: 0.6,
        userSelect: 'none',
        ml: 0.5
      }}>
        v1.0
      </Typography>
    </Box>
  );
}
