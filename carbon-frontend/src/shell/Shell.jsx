// File: src/shell/Shell.jsx
// Root IDE shell layout with activity bar, resizable sidebar, editor area, and copilot pane

import React, { useEffect, useMemo, useState, lazy, Suspense } from 'react';
import { Box, Drawer } from '@mui/material';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
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
import { LoadingSpinner, DialogLoadingSkeleton } from './LoadingFallback';
import useDocumentTitle from '../hooks/useDocumentTitle';

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
  useDocumentTitle("Home");
  const navigate = useNavigate();
  const location = useLocation();

  const [drawerWidth, setDrawerWidth] = useState(() => {
    const stored = Number(localStorage.getItem('carbon-drawer-width'));
    return Number.isFinite(stored) && stored > 0 ? stored : 250;
  });

  const [copilotPaneSize, setCopilotPaneSize] = useState(() => {
    const stored = Number(localStorage.getItem('carbon-copilot-pane-size'));
    return Number.isFinite(stored) && stored >= 300 ? stored : 400;
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
    sidebarVisible,
    toggleSidebar,
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
      // Ctrl+B or Cmd+B - Toggle Sidebar
      if ((e.ctrlKey || e.metaKey) && e.key === 'b') {
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
  }, [toggleSidebar, toggleCopilot]);

  const handleSidebarNavigate = (item) => {
    navigate(item.path);
  };

  // Click on studio icon → auto-navigate to studio's default path
  const handleStudioChange = (studioId) => {
    changeStudio(studioId);
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

        {/* Collapsed-sidebar reopen handle */}
        {!sidebarVisible && (
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

        {/* Left Drawer Sidebar */}
        <Drawer
          anchor="left"
          open={sidebarVisible}
          onClose={toggleSidebar}
          variant="persistent"
          sx={{
            display: sidebarVisible ? 'block' : 'none',
            width: drawerWidthClamped,
            flexShrink: 0,
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
          {/* Resize handle */}
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
          <ShellSidebar
            activeStudio={activeStudio}
            onNavigate={handleSidebarNavigate}
            onCollapse={toggleSidebar}
          />
        </Drawer>

        {/* Resizable Main + Copilot Panes */}
        <Box sx={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
          <Allotment
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
            <Allotment.Pane>
              <EditorArea />
            </Allotment.Pane>

            {/* Right Copilot Pane — superseded by external Pulse */}
            {copilotVisible && (
              <Allotment.Pane minSize={300} preferredSize={copilotPaneSize} maxSize={600}>
                <ErrorBoundary>
                  <Suspense fallback={<LoadingSpinner />}>
                    <Box sx={{ p: 3, textAlign: 'center', color: 'text.secondary' }}>
                      Pulse AI is now external. See STRATEGY_DATA_TRUST_PLATFORM.md
                    </Box>
                  </Suspense>
                </ErrorBoundary>
              </Allotment.Pane>
            )}
          </Allotment>
        </Box>
      </Box>

      {/* Status Bar with integrated Footer */}
      <StatusBar
        sidebarVisible={sidebarVisible}
        copilotVisible={copilotVisible}
        onToggleSidebar={toggleSidebar}
        onToggleCopilot={toggleCopilot}
      />

      {/* Command Palette */}
      <Suspense fallback={<DialogLoadingSkeleton />}>
        <CommandPalette
          open={commandPaletteOpen}
          onClose={() => setCommandPaletteOpen(false)}
        />
      </Suspense>
    </Box>
  );
}
