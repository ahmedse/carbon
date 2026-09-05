// File: src/shell/Shell.jsx
// Root IDE shell layout with activity bar, resizable sidebar, editor area, and copilot pane

import React, { lazy, Suspense, useEffect, useMemo, useState } from 'react';
import { Box, Drawer, IconButton, Tooltip, Typography } from '@mui/material';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import PushPinOutlinedIcon from '@mui/icons-material/PushPinOutlined';
import { Allotment } from 'allotment';
import 'allotment/dist/style.css';
import { useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useLanguage } from '../i18n/useLanguage';
import { PLATFORM_TITLE } from '../config/branding';
import { useShellState } from './useShellState';
import { ActivityBar } from './ActivityBar';
import { ShellSidebar } from './ShellSidebar';
import { EditorArea } from './EditorArea';
import { StatusBar } from './StatusBar';
import HeaderEnhanced from '../components/HeaderEnhanced';
import DevelopmentBanner from './DevelopmentBanner';
import ErrorBoundary from './ErrorBoundary';
import { AIWorkspace } from './AIWorkspace';
import { AITaskTransferProvider } from './AITaskTransferContext';
import { NotesProvider, useNotes } from '../notes/NotesContext';
import { NotesDrawer } from '../notes/NotesDrawer';
import { LoadingSpinner, DialogLoadingSkeleton } from './LoadingFallback';

// Lazy load heavy components for code splitting
const CommandPalette = lazy(() => import('./CommandPalette'));

// Default path per studio
const STUDIO_PATHS = {
  home:    '/',
  carbon:  '/carbon/dashboard',   // app studio: default to carbon dashboard
  catalog: '/catalog/domains',
  admin:   '/admin/users',
  'ai-admin': '/admin/ai',
  settings:'/settings',
  help:    '/help',
  apps:    '/apps/healthy',
  people:  '/people',
};

// Infer active studio from current URL
function studioFromPath(pathname) {
  if (pathname.startsWith('/carbon')) return 'carbon';  // app studio — checked first
  if (pathname.startsWith('/emissions') || pathname.startsWith('/dataschema')) return 'carbon';
  if (pathname.startsWith('/catalog')) return 'catalog';
  // DQ Workspace lives under Catalog Studio in the sidebar (Governance section)
  if (pathname.startsWith('/dq')) return 'catalog';
  // Module landing is part of Catalog (Data Products)
  if (pathname.startsWith('/modules')) return 'catalog';
  // Scopes belong to Carbon app
  if (pathname.startsWith('/scopes')) return 'carbon';
  // People app (Nibras HR & payroll)
  if (pathname.startsWith('/people')) return 'people';
  // Apps namespace (Healthy Foods Factory + future domain apps)
  if (pathname.startsWith('/apps')) return 'apps';
  // AI admin (Pulse console) — checked before generic /admin
  if (pathname.startsWith('/admin/ai')) return 'ai-admin';
  if (pathname.startsWith('/admin')) return 'admin';
  if (pathname.startsWith('/settings')) return 'settings';
  if (pathname.startsWith('/help') || pathname.startsWith('/feedback')) return 'help';
  return 'home';
}

export function Shell() {
  const { t } = useTranslation('shell');
  const { isRtl } = useLanguage();
  const navigate = useNavigate();
  const location = useLocation();

  const [drawerWidth, setDrawerWidth] = useState(() => {
    const stored = Number(localStorage.getItem('carbon-drawer-width'));
    return Number.isFinite(stored) && stored > 0 ? stored : 200;
  });

  const [copilotPaneSize, setCopilotPaneSize] = useState(() => {
    const stored = Number(localStorage.getItem('carbon-copilot-pane-size'));
    return Number.isFinite(stored) && stored >= 280 ? stored : 400;
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
    openCopilot,
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

// Notes drawer shortcut bridge (provider is mounted inside the content area)
function NotesShortcutBridge() {
  const { toggleOpen } = useNotes();
  return (
    <NotesShortcutHandler toggleOpen={toggleOpen} />
  );
}

function NotesShortcutHandler({ toggleOpen }) {
  const toggleRef = React.useRef(toggleOpen);
  toggleRef.current = toggleOpen;

  React.useEffect(() => {
    const onKey = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && (e.key === 'N' || e.key === 'n')) {
        e.preventDefault();
        toggleRef.current();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  return null;
}

  // Content pane = EditorArea + docked side panes.
  // Notes drawer today; future panes (e.g. governance info tabs) can be appended
  // to DOCKED_PANES in order — each pane renders as a fixed-width, flexShrink:0
  // column (see NotesDrawer) and the editor absorbs the remaining width.
  // NOTE: the wrapper MUST fill the available width (flex: 1 + width: '100%').
  // When Pulse is closed this Box is a direct flex child of the content row and
  // without flex:1 it collapses to its content width (~344px), breaking the layout.
  const DOCKED_PANES = [
    <NotesDrawer key="notes" />,
    // Future panes — e.g. <GovernanceInfoDrawer key="governance" />, <DataQualityTabs key="dq" />
  ];
  const renderContentPane = () => (
    <Box sx={{ display: 'flex', height: '100%', minWidth: 0, flex: 1, width: '100%' }}>
      <Box sx={{ flex: 1, minWidth: 0, height: '100%' }}>
        <EditorArea />
      </Box>
      {DOCKED_PANES}
    </Box>
  );

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
      aria-label={PLATFORM_TITLE}
    >
      {/* Header */}
      <HeaderEnhanced />

      {/* Early-access notice — dismissible, appears once; see DevelopmentBanner */}
      <DevelopmentBanner />

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
              ...(isRtl ? { borderLeft: 1 } : { borderRight: 1 }),
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
            aria-label={t('ui.showSidebar')}
            title={t('ui.showSidebarShortcut')}
          >
            <ChevronRightIcon
              className="expand-chevron"
              sx={{
                fontSize: 14,
                opacity: 0.45,
                color: 'text.secondary',
                transition: 'opacity 150ms',
                ...(isRtl && { transform: 'scaleX(-1)' }),
              }}
            />
          </Box>
        )}

        {/* Drawer Sidebar — hidden: not rendered, peek: overlay, pinned: persistent */}
        {sidebarMode !== 'hidden' && (
          <Drawer
            anchor={isRtl ? 'right' : 'left'}
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
                ...(isRtl ? { borderLeft: '1px solid' } : { borderRight: '1px solid' }),
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
                  {t('ui.peek')}
                </Typography>
                <Tooltip title={t('ui.pinSidebarTooltip')}>
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
                  ...(isRtl ? { left: 0 } : { right: 0 }),
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
                    const delta = isRtl ? (startX - moveEvent.clientX) : (moveEvent.clientX - startX);
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
        <NotesProvider>
          <NotesShortcutBridge />
          <AITaskTransferProvider onRequestOpen={openCopilot}>
            <Box sx={{ flex: 1, display: 'flex', overflow: 'hidden', minWidth: 0 }}>
              {copilotVisible ? (
                <Allotment
                  onChange={(sizes) => {
                    if (sizes.length >= 2) {
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
                  {/* In RTL mode, render copilot pane first (left side), editor second (right side) */}
                  {isRtl && (
                    <Allotment.Pane
                      key="copilot"
                      minSize={280}
                      preferredSize={copilotPaneSize}
                      maxSize={Math.floor(window.innerWidth / 2)}
                    >
                      <ErrorBoundary>
                        <AIWorkspace onClose={toggleCopilot} />
                      </ErrorBoundary>
                    </Allotment.Pane>
                  )}

                  {/* Main Editor Area — content + notes drawer docked at its right edge */}
                  <Allotment.Pane key="editor" minSize={320} preferredSize={1}>
                    {renderContentPane()}
                  </Allotment.Pane>

                  {/* In LTR mode, render copilot pane second (right side) */}
                  {!isRtl && (
                    <Allotment.Pane
                      key="copilot"
                      minSize={280}
                      preferredSize={copilotPaneSize}
                      maxSize={Math.floor(window.innerWidth / 2)}
                    >
                      <ErrorBoundary>
                        <AIWorkspace onClose={toggleCopilot} />
                      </ErrorBoundary>
                    </Allotment.Pane>
                  )}
                </Allotment>
              ) : (
                /* When copilot is closed, just render editor without Allotment wrapper */
                renderContentPane()
              )}
            </Box>
          </AITaskTransferProvider>
        </NotesProvider>
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
