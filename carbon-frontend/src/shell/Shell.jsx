// File: src/shell/Shell.jsx
// Root IDE shell layout with activity bar, resizable sidebar, editor area, and copilot pane

import React, { lazy, Suspense, useEffect, useMemo, useState } from 'react';
import { Box, Drawer, IconButton, Tooltip, Typography } from '@mui/material';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import PushPinOutlinedIcon from '@mui/icons-material/PushPinOutlined';
import { Allotment } from 'allotment';
import 'allotment/dist/style.css';
import { useNavigate, useLocation } from 'react-router-dom';
import { useShellState } from './useShellState';
import { ActivityBar } from './ActivityBar';
import { ShellSidebar } from './ShellSidebar';
import { EditorArea } from './EditorArea';
import { StatusBar } from './StatusBar';
import HeaderEnhanced from '../components/HeaderEnhanced';
import ErrorBoundary from './ErrorBoundary';
import PulsePane from './PulsePane';
import { LoadingSpinner, DialogLoadingSkeleton } from './LoadingFallback';

// Lazy load heavy components for code splitting
const CommandPalette = lazy(() => import('./CommandPalette'));

// Default path per studio
const STUDIO_PATHS = {
  home:    '/',
  carbon:  '/carbon/dashboard',   // app studio: default to carbon dashboard
  catalog: '/catalog/domains',
  admin:   '/admin/users',
  settings:'/settings',
  help:    '/help',
};

// Infer active studio from current URL
function studioFromPath(pathname) {
  if (pathname.startsWith('/carbon')) return 'carbon';  // app studio — checked first
  if (pathname.startsWith('/emissions') || pathname.startsWith('/dataschema') || pathname.startsWith('/schema-admin')) return 'carbon';
  if (pathname.startsWith('/catalog')) return 'catalog';
  if (pathname.startsWith('/admin')) return 'admin';
  if (pathname.startsWith('/settings')) return 'settings';
  if (pathname.startsWith('/help') || pathname.startsWith('/feedback')) return 'help';
  return 'home';
}

export function Shell() {
  const navigate = useNavigate();
  const location = useLocation();

  const [drawerWidth, setDrawerWidth] = useState(() => {
    const stored = Number(localStorage.getItem('carbon-drawer-width'));
    return Number.isFinite(stored) && stored > 0 ? stored : 200;
  });

  const [copilotPaneSize, setCopilotPaneSize] = useState(() => {
    const stored = Number(localStorage.getItem('carbon-copilot-pane-size'));
    return Number.isFinite(stored) && stored >= 280 ? stored : 360;
  });

  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);

  const drawerWidthClamped = useMemo(() => {
    const min = 160;
    const max = 360;
    return Math.min(max, Math.max(min, drawerWidth));
  }, [drawerWidth]);

  const {
    studios,
    activeStudio,
    changeStudio,
    sidebarMode,
    toggleSidebar,
    openSidebarPeek,
    dismissSidebarPeek,
    pinSidebar,
    copilotVisible,
    toggleCopilot,
  } = useShellState();

  // Sync active studio with current URL
  useEffect(() => {
    const inferred = studioFromPath(location.pathname);
    if (inferred !== activeStudio) changeStudio(inferred);
  }, [location.pathname, activeStudio, changeStudio]);

  // Persist drawer width
  useEffect(() => {
    try {
      localStorage.setItem('carbon-drawer-width', String(drawerWidthClamped));
    } catch {
      // ignore
    }
  }, [drawerWidthClamped]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e) => {
      // Escape — dismiss peek sidebar
      if (e.key === 'Escape' && sidebarMode === 'peek') {
        e.preventDefault();
        dismissSidebarPeek();
      }
      // Ctrl+B or Cmd+B - Cycle sidebar hidden→peek→pinned→hidden
      else if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'B') {
        e.preventDefault();
        // Ctrl+Shift+B: toggle peek ↔ pinned
        if (sidebarMode === 'peek') pinSidebar();
        else if (sidebarMode === 'pinned') dismissSidebarPeek(); // pinned→hidden; then openSidebarPeek set peek
        else toggleSidebar();
      }
      else if ((e.ctrlKey || e.metaKey) && e.key === 'b') {
        e.preventDefault();
        toggleSidebar();
      }
      // Ctrl+\ or Cmd+\ - Toggle Copilot
      else if ((e.ctrlKey || e.metaKey) && e.key === '\\') {
        e.preventDefault();
        toggleCopilot();
      }
      // Ctrl+K or Cmd+K - Command Palette
      else if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        setCommandPaletteOpen(true);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [toggleSidebar, toggleCopilot, sidebarMode, dismissSidebarPeek, pinSidebar]);

  const handleSidebarNavigate = (item) => {
    navigate(item.path);
  };

  // Click on studio icon → auto-navigate to studio's default path, open sidebar peek if hidden
  const handleStudioChange = (studioId) => {
    changeStudio(studioId);
    openSidebarPeek();
    const path = STUDIO_PATHS[studioId];
    if (path) navigate(path);
  };

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        width: '100vw',
        overflow: 'hidden',
      }}
      role="application"
      aria-label="Carbon Data Platform"
    >
      {/* Header */}
      <HeaderEnhanced />

      {/* Main Content Area */}
      <Box sx={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        {/* Activity Bar */}
        <ActivityBar
          studios={studios}
          activeStudio={activeStudio}
          onStudioChange={handleStudioChange}
        />

        {/* Collapsed-sidebar reopen handle — shown only when hidden */}
        {sidebarMode === 'hidden' && (
          <Box
            role="button"
            tabIndex={0}
            onClick={toggleSidebar}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                toggleSidebar();
              }
            }}
            sx={{
              width: 20,
              height: '100%',
              borderRight: 1,
              borderColor: 'divider',
              cursor: 'pointer',
              bgcolor: 'background.paper',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
              '&:hover': {
                bgcolor: 'action.hover',
                '& .expand-chevron': { opacity: 1 },
              },
            }}
            aria-label="Show sidebar"
            title="Show Sidebar (Ctrl+B)"
          >
            <ChevronRightIcon
              className="expand-chevron"
              sx={{
                fontSize: 14,
                opacity: 0.45,
                color: 'text.secondary',
                transition: 'opacity 150ms',
              }}
            />
          </Box>
        )}

        {/* Left Drawer Sidebar — hidden: not rendered, peek: overlay, pinned: persistent */}
        {sidebarMode !== 'hidden' && (
          <Drawer
            anchor="left"
            open
            onClose={dismissSidebarPeek}
            variant={sidebarMode === 'peek' ? 'temporary' : 'persistent'}
            sx={{
              width: sidebarMode === 'pinned' ? drawerWidthClamped : undefined,
              flexShrink: sidebarMode === 'pinned' ? 0 : undefined,
              '& .MuiDrawer-paper': {
                width: drawerWidthClamped,
                boxSizing: 'border-box',
                position: 'relative',
                height: '100%',
                borderRight: '1px solid',
                borderColor: 'divider',
                overflow: 'hidden',
                bgcolor: 'background.paper',
              },
            }}
          >
            {/* Pin/Unpin + Collapse header bar (peek mode) */}
            {sidebarMode === 'peek' && (
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  px: 1,
                  py: 0.25,
                  borderBottom: '1px solid',
                  borderColor: 'divider',
                  bgcolor: 'action.hover',
                }}
              >
                <Typography variant="caption" sx={{ fontSize: '0.6rem', color: 'text.secondary', textTransform: 'uppercase' }}>
                  Peek
                </Typography>
                <Tooltip title="Pin sidebar (Ctrl+Shift+B)">
                  <IconButton size="small" onClick={pinSidebar} sx={{ p: 0.25 }}>
                    <PushPinOutlinedIcon sx={{ fontSize: 14 }} />
                  </IconButton>
                </Tooltip>
              </Box>
            )}

            {/* Resize handle — only in pinned mode */}
            {sidebarMode === 'pinned' && (
              <Box
                sx={{
                  position: 'absolute',
                  top: 0,
                  right: 0,
                  bottom: 0,
                  width: 6,
                  cursor: 'col-resize',
                  zIndex: 2,
                  bgcolor: 'transparent',
                  '&:hover': {
                    bgcolor: 'action.hover',
                  },
                }}
                onMouseDown={(e) => {
                  e.preventDefault();
                  e.stopPropagation();

                  const startX = e.clientX;
                  const startWidth = drawerWidthClamped;

                  const onMove = (moveEvent) => {
                    const delta = moveEvent.clientX - startX;
                    setDrawerWidth(startWidth + delta);
                  };

                  const onUp = () => {
                    window.removeEventListener('mousemove', onMove);
                    window.removeEventListener('mouseup', onUp);
                  };

                  window.addEventListener('mousemove', onMove);
                  window.addEventListener('mouseup', onUp);
                }}
              />
            )}

            <ShellSidebar
              activeStudio={activeStudio}
              onNavigate={handleSidebarNavigate}
              onCollapse={toggleSidebar}
            />
          </Drawer>
        )}

        {/* Resizable Main + Copilot Panes */}
        <Box sx={{ flex: 1, display: 'flex', overflow: 'hidden', minWidth: 0 }}>
          <Allotment
            key={copilotVisible ? '2panes' : '1pane'}
            onChange={(sizes) => {
              if (copilotVisible && sizes.length >= 2) {
                const w = sizes[sizes.length - 1];
                setCopilotPaneSize(w);
                try {
                  localStorage.setItem('carbon-copilot-pane-size', String(w));
                } catch {
                  /* ignore */
                }
              }
            }}
          >
            {/* Main Editor Area */}
            <Allotment.Pane minSize={320} preferredSize={1}>
              <EditorArea />
            </Allotment.Pane>

            {/* Right Copilot Pane — Pulse AI */}
            {copilotVisible && (
              <Allotment.Pane minSize={280} preferredSize={copilotPaneSize} maxSize={520}>
                <ErrorBoundary>
                  <PulsePane />
                </ErrorBoundary>
              </Allotment.Pane>
            )}
          </Allotment>
        </Box>
      </Box>

      {/* Status Bar with integrated Footer */}
      <StatusBar
        sidebarMode={sidebarMode}
        copilotVisible={copilotVisible}
        onToggleSidebar={toggleSidebar}
        onToggleCopilot={toggleCopilot}
      />

      {/* Command Palette — isolated ErrorBoundary so a lazy-load failure doesn't crash the shell */}
      <ErrorBoundary>
        <Suspense fallback={<DialogLoadingSkeleton />}>
          <CommandPalette
            open={commandPaletteOpen}
            onClose={() => setCommandPaletteOpen(false)}
          />
        </Suspense>
      </ErrorBoundary>
    </Box>
  );
}
