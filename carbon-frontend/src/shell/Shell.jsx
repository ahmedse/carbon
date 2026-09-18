// File: src/shell/Shell.jsx
// Root IDE shell layout with activity bar, resizable sidebar, editor area, and copilot pane
// ADR-0035: under sm — temporary nav, no ActivityBar rail, Pulse fullscreen overlay

import React, { useEffect, useMemo, useState } from 'react';
import { Box, Dialog, Drawer, IconButton, Tooltip, Typography } from '@mui/material';
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
import CommandPalette from './CommandPalette';
import HeaderEnhanced from '../components/HeaderEnhanced';
import DevelopmentBanner from './DevelopmentBanner';
import ErrorBoundary from './ErrorBoundary';
import { AIWorkspace } from './AIWorkspace';
import { AITaskTransferProvider } from './AITaskTransferContext';
import { NotesProvider, useNotes } from '../notes/NotesContext';
import { NotesDrawer } from '../notes/NotesDrawer';
import { useIsMobile } from '../hooks/useIsMobile';

/** Docked Pulse may grow until traditional still has ~320px (editor min). */
function dockedPulseMaxSize() {
  if (typeof window === 'undefined') return 720;
  return Math.max(400, window.innerWidth - 320);
}

const STUDIO_PATHS = {
  home: '/',
  carbon: '/carbon/dashboard',
  catalog: '/catalog/domains',
  admin: '/admin/users',
  'ai-admin': '/admin/ai',
  settings: '/settings',
  help: '/help',
  apps: '/apps/healthy',
  people: '/people',
  my: '/my',
  team: '/team',
};

function studioFromPath(pathname) {
  if (pathname.startsWith('/carbon')) return 'carbon';
  if (pathname.startsWith('/emissions') || pathname.startsWith('/dataschema')) return 'carbon';
  if (pathname.startsWith('/catalog')) return 'catalog';
  if (pathname.startsWith('/dq')) return 'catalog';
  if (pathname.startsWith('/modules')) return 'catalog';
  if (pathname.startsWith('/scopes')) return 'carbon';
  if (pathname.startsWith('/people')) return 'people';
  if (pathname.startsWith('/my')) return 'my';
  if (pathname.startsWith('/team')) return 'team';
  if (pathname.startsWith('/apps')) return 'apps';
  if (pathname.startsWith('/admin/ai')) return 'ai-admin';
  if (pathname.startsWith('/admin')) return 'admin';
  if (pathname.startsWith('/settings')) return 'settings';
  if (pathname.startsWith('/help') || pathname.startsWith('/feedback')) return 'help';
  return 'home';
}

function NotesShortcutBridge() {
  const { toggleOpen } = useNotes();
  return <NotesShortcutHandler toggleOpen={toggleOpen} />;
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

export function Shell() {
  const { t } = useTranslation('shell');
  const { isRtl } = useLanguage();
  const navigate = useNavigate();
  const location = useLocation();
  const isMobile = useIsMobile();

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
    forceSidebarPeek,
    forceSidebarHidden,
    dismissSidebarPeek,
    pinSidebar,
    copilotVisible,
    copilotExpanded,
    toggleCopilot,
    toggleCopilotExpanded,
    openCopilot,
  } = useShellState();

  // ADR-0035: under sm, ignore pinned — only peek (temporary open) or hidden.
  // Desktop localStorage preference is preserved for md+.
  const effectiveSidebarMode = isMobile
    ? (sidebarMode === 'peek' ? 'peek' : 'hidden')
    : sidebarMode;

  // ADR-0035: pinned is treated as closed on mobile, so peek/dismiss helpers
  // that only act on hidden↔peek never flip the drawer. Force the mode.
  const handleMobileNavToggle = React.useCallback(() => {
    if (effectiveSidebarMode === 'hidden') forceSidebarPeek();
    else forceSidebarHidden();
  }, [effectiveSidebarMode, forceSidebarPeek, forceSidebarHidden]);

  useEffect(() => {
    const inferred = studioFromPath(location.pathname);
    if (inferred !== activeStudio) changeStudio(inferred);
  }, [location.pathname, activeStudio, changeStudio]);

  useEffect(() => {
    try {
      localStorage.setItem('carbon-drawer-width', String(drawerWidthClamped));
    } catch {
      /* ignore */
    }
  }, [drawerWidthClamped]);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && effectiveSidebarMode === 'peek') {
        e.preventDefault();
        if (isMobile) forceSidebarHidden();
        else dismissSidebarPeek();
      } else if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'B') {
        e.preventDefault();
        if (isMobile) {
          handleMobileNavToggle();
        } else if (sidebarMode === 'peek') pinSidebar();
        else if (sidebarMode === 'pinned') dismissSidebarPeek();
        else toggleSidebar();
      } else if ((e.ctrlKey || e.metaKey) && e.key === 'b') {
        e.preventDefault();
        if (isMobile) handleMobileNavToggle();
        else toggleSidebar();
      } else if ((e.ctrlKey || e.metaKey) && (e.key === '\\' || e.code === 'Backslash')) {
        e.preventDefault();
        if (e.shiftKey) toggleCopilotExpanded();
        else toggleCopilot();
      } else if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        setCommandPaletteOpen(true);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [
    toggleSidebar,
    toggleCopilot,
    toggleCopilotExpanded,
    openCopilot,
    sidebarMode,
    effectiveSidebarMode,
    dismissSidebarPeek,
    forceSidebarHidden,
    pinSidebar,
    isMobile,
    openSidebarPeek,
    handleMobileNavToggle,
  ]);

  const handleSidebarNavigate = (item) => {
    navigate(item.path);
    if (isMobile) forceSidebarHidden();
  };

  const handleStudioChange = (studioId) => {
    changeStudio(studioId);
    if (isMobile) forceSidebarPeek();
    else openSidebarPeek();
    const path = STUDIO_PATHS[studioId];
    if (path) navigate(path);
  };

  const DOCKED_PANES = isMobile ? [] : [<NotesDrawer key="notes" />];
  const renderContentPane = () => (
    <Box sx={{ display: 'flex', height: '100%', minWidth: 0, flex: 1, width: '100%' }}>
      <Box sx={{ flex: 1, minWidth: 0, height: '100%' }}>
        <EditorArea />
      </Box>
      {DOCKED_PANES}
    </Box>
  );

  const renderPulseWorkspace = () => (
    <ErrorBoundary>
      <AIWorkspace
        onClose={toggleCopilot}
        expanded={copilotExpanded}
        onToggleExpand={toggleCopilotExpanded}
      />
    </ErrorBoundary>
  );

  const renderCopilotDesktop = () => {
    if (copilotExpanded) {
      return (
        <Box sx={{ display: 'flex', flex: 1, minWidth: 0, height: '100%' }}>
          <Box sx={{ flex: 1, minWidth: 0, height: '100%', display: 'flex', flexDirection: 'column' }}>
            {renderPulseWorkspace()}
          </Box>
          {DOCKED_PANES}
        </Box>
      );
    }

    const pulseMax = dockedPulseMaxSize();
    return (
      <Allotment
        onChange={(sizes) => {
          if (sizes.length >= 2) {
            const w = isRtl ? sizes[0] : sizes[sizes.length - 1];
            setCopilotPaneSize(w);
            try {
              localStorage.setItem('carbon-copilot-pane-size', String(w));
            } catch {
              /* ignore */
            }
          }
        }}
      >
        {isRtl && (
          <Allotment.Pane
            key="copilot"
            minSize={280}
            preferredSize={copilotPaneSize}
            maxSize={pulseMax}
          >
            {renderPulseWorkspace()}
          </Allotment.Pane>
        )}
        <Allotment.Pane key="editor" minSize={320} preferredSize={1}>
          {renderContentPane()}
        </Allotment.Pane>
        {!isRtl && (
          <Allotment.Pane
            key="copilot"
            minSize={280}
            preferredSize={copilotPaneSize}
            maxSize={pulseMax}
          >
            {renderPulseWorkspace()}
          </Allotment.Pane>
        )}
      </Allotment>
    );
  };

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        width: '100%',
        maxWidth: '100vw',
        overflow: 'hidden',
      }}
      role="application"
      aria-label={PLATFORM_TITLE}
    >
      <HeaderEnhanced
        showNavButton={isMobile}
        navOpen={effectiveSidebarMode !== 'hidden'}
        onToggleNav={handleMobileNavToggle}
        studios={isMobile ? studios : undefined}
        activeStudio={activeStudio}
        onStudioChange={isMobile ? handleStudioChange : undefined}
      />

      <DevelopmentBanner />

      <Box sx={{ flex: 1, display: 'flex', overflow: 'hidden', minWidth: 0 }}>
        {!isMobile && (
          <ActivityBar
            studios={studios}
            activeStudio={activeStudio}
            onStudioChange={handleStudioChange}
          />
        )}

        {!isMobile && effectiveSidebarMode === 'hidden' && (
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

        {effectiveSidebarMode !== 'hidden' && (
          <Drawer
            anchor={isRtl ? 'right' : 'left'}
            open
            onClose={isMobile ? forceSidebarHidden : dismissSidebarPeek}
            variant={effectiveSidebarMode === 'peek' || isMobile ? 'temporary' : 'permanent'}
            ModalProps={{ keepMounted: true }}
            sx={{
              width: !isMobile && effectiveSidebarMode === 'pinned' ? drawerWidthClamped : undefined,
              flexShrink: !isMobile && effectiveSidebarMode === 'pinned' ? 0 : undefined,
              '& .MuiDrawer-paper': {
                width: isMobile ? 'min(85vw, 320px)' : drawerWidthClamped,
                boxSizing: 'border-box',
                position: isMobile || effectiveSidebarMode === 'peek' ? 'fixed' : 'relative',
                height: '100%',
                top: isMobile ? 0 : undefined,
                ...(isRtl ? { borderLeft: '1px solid' } : { borderRight: '1px solid' }),
                borderColor: 'divider',
                overflow: 'hidden',
                bgcolor: 'background.paper',
              },
            }}
          >
            {effectiveSidebarMode === 'peek' && !isMobile && (
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

            {!isMobile && effectiveSidebarMode === 'pinned' && (
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
                  '&:hover': { bgcolor: 'action.hover' },
                }}
                onMouseDown={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  const startX = e.clientX;
                  const startWidth = drawerWidthClamped;
                  const onMove = (moveEvent) => {
                    const delta = isRtl ? startX - moveEvent.clientX : moveEvent.clientX - startX;
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
              onCollapse={isMobile ? forceSidebarHidden : toggleSidebar}
            />
          </Drawer>
        )}

        <NotesProvider>
          <NotesShortcutBridge />
          <AITaskTransferProvider onRequestOpen={openCopilot}>
            <Box sx={{ flex: 1, display: 'flex', overflow: 'hidden', minWidth: 0 }}>
              {copilotVisible && !isMobile ? renderCopilotDesktop() : renderContentPane()}
            </Box>

            {isMobile && (
              <Dialog
                fullScreen
                open={copilotVisible}
                onClose={toggleCopilot}
                PaperProps={{ sx: { bgcolor: 'background.paper' } }}
              >
                <ErrorBoundary>
                  <AIWorkspace
                    onClose={toggleCopilot}
                    expanded
                    onToggleExpand={undefined}
                  />
                </ErrorBoundary>
              </Dialog>
            )}

            {isMobile && <NotesDrawer mobileFullscreen />}
          </AITaskTransferProvider>
        </NotesProvider>
      </Box>

      <StatusBar
        sidebarMode={effectiveSidebarMode}
        copilotVisible={copilotVisible}
        onToggleSidebar={isMobile ? handleMobileNavToggle : toggleSidebar}
        onToggleCopilot={toggleCopilot}
        compact={isMobile}
      />

      <ErrorBoundary>
        <CommandPalette
          open={commandPaletteOpen}
          onClose={() => setCommandPaletteOpen(false)}
        />
      </ErrorBoundary>
    </Box>
  );
}
