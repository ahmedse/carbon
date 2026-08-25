// File: src/shell/StatusBar.jsx
// 22px bottom status bar with system state, toggle buttons, and footer links

import React, { useState, useEffect, useMemo } from 'react';
import { Box, Typography, IconButton, Tooltip, Link, Badge } from '@mui/material';
import { useLocation } from 'react-router-dom';
import ViewSidebarIcon from '@mui/icons-material/ViewSidebar';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../auth/AuthContext';
import { listWorkspaceSuggestions } from '../api/aiWorkspace';
import { PLATFORM_TITLE } from '../config/branding';

export function StatusBar({
  sidebarMode,
  copilotVisible,
  onToggleSidebar,
  onToggleCopilot,
}) {
  const location = useLocation();
  const { context, token } = useAuth();
  const { t } = useTranslation('shell');
  const [systemStatus, setSystemStatus] = useState('ready');
  const [suggestionCount, setSuggestionCount] = useState(0);

  useEffect(() => {
    // TODO: Poll backend for system status
    // For now, just show ready state
    setSystemStatus('ready');
  }, []);

  // Pending proactive suggestions — drives the AI Workspace badge.
  // Clears on open (the rail already surfaces them) and refreshes on a timer.
  useEffect(() => {
    if (!token) return undefined;
    let cancelled = false;

    const fetchCount = () => {
      listWorkspaceSuggestions(token)
        .then((data) => {
          if (cancelled) return;
          setSuggestionCount((data?.suggestions || []).length);
        })
        .catch(() => {
          // Non-critical surface — ignore failures so the status bar is unaffected.
        });
    };

    fetchCount();
    const interval = setInterval(fetchCount, 60000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [token]);

  const statusColor = systemStatus === 'error' ? '#f87171' :
                      systemStatus === 'processing' ? '#fbbf24' :
                      'rgba(255,255,255,0.7)';
  const statusLabel = systemStatus === 'error' ? t('ui.error') :
                      systemStatus === 'processing' ? t('ui.processing') :
                      t('ui.ready');

  // Extract module/table context from URL
  const contextInfo = useMemo(() => {
    const pathname = location.pathname;
    
    // Check for module page: /modules/:moduleId
    const moduleMatch = pathname.match(/\/modules\/(\d+)/);
    if (moduleMatch) {
      const moduleId = moduleMatch[1];
      const module = context?.modules?.find(m => String(m.id) === moduleId);
      if (module) {
        return t('ui.dataProductLabel', { name: module.name });
      }
    }

    // Check for data entry page: /carbon/data-entry/entry/:moduleId/:tableId or /dataschema/entry/:moduleId/:tableId
    const entryMatch = pathname.match(/\/(?:carbon\/data-entry|dataschema)\/entry\/(\d+)\/(\d+)/);
    if (entryMatch) {
      const [, moduleId, tableId] = entryMatch;
      const module = context?.modules?.find(m => String(m.id) === moduleId);
      const table = context?.tablesByModule?.[moduleId]?.find(t => String(t.id) === tableId);
      
      if (table) {
        return `${module?.name || 'Data Product'} › ${table.title}`;
      }
    }

    // Check for Carbon Data Entry home
    if (pathname === '/dataschema' || pathname === '/carbon/data-entry') {
      return 'Carbon Data Entry';
    }

    return null;
  }, [location.pathname, context, t]);

  return (
    <Box
      component="footer"
      role="contentinfo"
      sx={{
        height: 22,
        minHeight: 22,
        bgcolor: 'primary.main',
        color: 'primary.contrastText',
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
        © {new Date().getFullYear()} {PLATFORM_TITLE}
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
          {t('ui.privacy')}
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
          {t('ui.terms')}
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
          {t('ui.support')}
        </Link>
      </Box>

      <Box sx={{ flex: 1 }} />

      {/* Toggle buttons */}
      <Box sx={{ display: 'flex', gap: 0.25 }}>
        <Tooltip title={sidebarMode === 'pinned' ? t('ui.hideSidebarShortcut') : sidebarMode === 'peek' ? t('ui.pinSidebar') : t('ui.showSidebarShortcut')} placement="top">
          <IconButton
            size="small"
            onClick={onToggleSidebar}
            aria-label={sidebarMode === 'pinned' ? t('ui.hideSidebar') : t('ui.showSidebar')}
            aria-pressed={sidebarMode !== 'hidden'}
            sx={{
              p: 0.25,
              color: 'inherit',
              opacity: sidebarMode !== 'hidden' ? 1 : 0.5,
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

        <Tooltip title={copilotVisible ? t('ui.hidePulseShortcut') : t('ui.showPulseShortcut')} placement="top">
          <Badge
            badgeContent={copilotVisible ? 0 : suggestionCount}
            color="error"
            variant="standard"
            invisible={copilotVisible || suggestionCount === 0}
            overlap="circular"
          >
            <IconButton
              size="small"
              onClick={onToggleCopilot}
              aria-label={copilotVisible ? t('ui.hidePulse') : t('ui.showPulse')}
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
          </Badge>
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
