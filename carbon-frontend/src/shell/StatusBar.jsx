// File: src/shell/StatusBar.jsx
// 22px bottom status bar with system state, toggle buttons, and footer links

import React, { useState, useEffect, useMemo } from 'react';
import { Box, Typography, IconButton, Tooltip, Link } from '@mui/material';
import { useLocation } from 'react-router-dom';
import ViewSidebarIcon from '@mui/icons-material/ViewSidebar';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import { useAuth } from '../auth/AuthContext';

export function StatusBar({
  sidebarVisible,
  copilotVisible,
  onToggleSidebar,
  onToggleCopilot,
}) {
  const location = useLocation();
  const { context } = useAuth();
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

  // Extract module/table context from URL
  const contextInfo = useMemo(() => {
    const pathname = location.pathname;
    
    // Check for module page: /modules/:moduleId
    const moduleMatch = pathname.match(/\/modules\/(\d+)/);
    if (moduleMatch) {
      const moduleId = moduleMatch[1];
      const module = context?.modules?.find(m => String(m.id) === moduleId);
      if (module) {
        return `Module: ${module.name}`;
      }
    }

    // Check for data entry page: /dataschema/entry/:moduleId/:tableId
    const entryMatch = pathname.match(/\/dataschema\/entry\/(\d+)\/(\d+)/);
    if (entryMatch) {
      const [, moduleId, tableId] = entryMatch;
      const module = context?.modules?.find(m => String(m.id) === moduleId);
      const table = context?.tablesByModule?.[moduleId]?.find(t => String(t.id) === tableId);
      
      if (table) {
        return `${module?.name || 'Module'} › ${table.title}`;
      }
    }

    // Check for Data Hub quality
    if (pathname === '/dataschema/quality') {
      return 'Data Hub › Quality';
    }

    // Check for Data Hub home
    if (pathname === '/dataschema') {
      return 'Data Hub';
    }

    return null;
  }, [location.pathname, context]);

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

      {/* Context info (module/table) */}
      {contextInfo && (
        <>
          <Box
            sx={{
              width: 1,
              height: 14,
              bgcolor: 'rgba(255,255,255,0.2)',
              mx: 1,
            }}
          />
          <Typography sx={{
            fontSize: '0.6875rem',
            color: 'rgba(255,255,255,0.9)',
            fontWeight: 500,
            userSelect: 'none',
          }}>
            {contextInfo}
          </Typography>
        </>
      )}

      {/* Copyright and footer links */}
      <Typography sx={{
        fontSize: '0.6875rem',
        opacity: 0.7,
        userSelect: 'none',
        ml: contextInfo ? 2 : 1,
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
