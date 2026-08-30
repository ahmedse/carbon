// File: src/shell/useShellState.js
// Central state management for Shell layout preferences and studio navigation

import { useState, useEffect, useCallback, useMemo } from 'react';
import { useAuth } from '../auth/AuthContext';
import DashboardIcon from '@mui/icons-material/Dashboard';
import Co2Icon from '@mui/icons-material/Co2';
import MonitorHeartIcon from '@mui/icons-material/MonitorHeart';
import CatalogIcon from '@mui/icons-material/LibraryBooks';
import AdminPanelSettingsIcon from '@mui/icons-material/AdminPanelSettings';
import PsychologyIcon from '@mui/icons-material/Psychology';
import SettingsIcon from '@mui/icons-material/Settings';
import HelpIcon from '@mui/icons-material/Help';
import { APP_REGISTRY } from '../apps/registry';
import { isGlobalAdmin, isCatalogAdmin, hasAppAccess, hasCap, expandCapabilities } from '../authz';
import { AI_VIEW_CONSOLE } from '../capabilities';
import { useEnabledApps } from '../hooks/useEnabledApps';

// Platform studios — shell-owned, NOT app-manifest-driven.
// App studios are injected dynamically from APP_REGISTRY below.
// NOTE: 'emissions' and 'dataschema' are removed — their functionality lives inside
//       the Carbon Footprint domain app (carbon studio).
const PLATFORM_STUDIOS = [
  { id: 'home',     label: 'Home',            icon: DashboardIcon,          path: '/'               },
  // ── App studios injected here at runtime ──
  { id: 'catalog',  label: 'Catalog Studio', icon: CatalogIcon,            path: '/catalog/domains' },
  { id: 'admin',    label: 'Platform Admin', icon: AdminPanelSettingsIcon, path: '/admin/users'     },
  { id: 'ai-admin', label: 'AI Admin',       icon: PsychologyIcon,          path: '/admin/ai'         },
  { id: 'settings', label: 'Settings',        icon: SettingsIcon,           path: '/settings',  bottom: true },
  { id: 'help',     label: 'Help',            icon: HelpIcon,               path: '/help',      bottom: true },
];

// Icon lookup for manifest-declared apps.
// Move 3: replace with a full MUI dynamic icon loader.
const MANIFEST_ICON_MAP = {
  Co2:          Co2Icon,
  Dashboard:    DashboardIcon,
  MonitorHeart: MonitorHeartIcon,
};

function getStoredBoolean(key, defaultValue) {
  try {
    const stored = localStorage.getItem(key);
    return stored !== null ? stored === 'true' : defaultValue;
  } catch {
    return defaultValue;
  }
}

function setStoredBoolean(key, value) {
  try {
    localStorage.setItem(key, String(value));
  } catch {
    // ignore storage errors
  }
}

function getStoredString(key, defaultValue) {
  try {
    const stored = localStorage.getItem(key);
    return stored && ['hidden','peek','pinned'].includes(stored) ? stored : defaultValue;
  } catch {
    return defaultValue;
  }
}

export function useShellState() {
  const { availablePerspectives, user, context, userCapabilities } = useAuth();
  const { isAppEnabled } = useEnabledApps();
  const studios = useMemo(() => {
    // Derive app studios from the manifest registry.
    const appStudios = APP_REGISTRY.map(m => ({
      id:   m.id,
      label: m.name,
      icon: MANIFEST_ICON_MAP[m.icon] || DashboardIcon,   // fallback to DashboardIcon
      path: m.navigation.items.find(i => i.role === '*')?.path
            || m.navigation.items[0]?.path
            || `/${m.id}`,
    }));

    // Splice app studios in after 'home' (before 'emissions').
    const homeIdx = PLATFORM_STUDIOS.findIndex(s => s.id === 'home');
    const combined = [
      ...PLATFORM_STUDIOS.slice(0, homeIdx + 1),
      ...appStudios,
      ...PLATFORM_STUDIOS.slice(homeIdx + 1),
    ];

    // Filter based on user permissions AND admin enable/disable
    const filtered = combined.filter((s) => {
      // Hide admin studio if not admin
      if (s.id === 'admin') {
        return isGlobalAdmin(user, availablePerspectives);
      }
      
      // Hide AI admin studio if not admin or AI console capability holder
      if (s.id === 'ai-admin') {
        if (isGlobalAdmin(user, availablePerspectives)) return true;
        const caps = (userCapabilities || []).map(
          (c) => (typeof c === 'string' ? c : (c?.key || c?.capability))
        );
        return hasCap(expandCapabilities(caps), AI_VIEW_CONSOLE);
      }
      
      // Hide catalog studio if not catalog admin
      if (s.id === 'catalog') {
        return isCatalogAdmin(user, { perspectives: availablePerspectives, capabilities: userCapabilities });
      }
      
      // For app studios, check if admin has disabled the app AND user has access
      const isAppStudio = APP_REGISTRY.some(app => app.id === s.id);
      if (isAppStudio) {
        if (!isAppEnabled(s.id)) return false;
        return hasAppAccess(s.id, user, { perspectives: availablePerspectives, capabilities: userCapabilities, modules: context?.modules });
      }
      
      // Always show home, settings, help
      return true;
    });
    
    return filtered;
  }, [availablePerspectives, user, context, isAppEnabled, userCapabilities]);

  const [activeStudio, setActiveStudio] = useState('home');
  const [sidebarMode, setSidebarModeRaw] = useState(() => getStoredString('carbon-sidebar-mode', 'pinned'));
  const [panelVisible, setPanelVisible] = useState(() => getStoredBoolean('carbon-panel-visible', false));
  const [copilotVisible, setCopilotVisible] = useState(() => getStoredBoolean('carbon-copilot-visible', false));
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);

  // Persist sidebar mode
  const setSidebarMode = useCallback((mode) => {
    setSidebarModeRaw(mode);
    try { localStorage.setItem('carbon-sidebar-mode', mode); } catch { /* ignore */ }
  }, []);

  // Persist panel visibility
  useEffect(() => {
    setStoredBoolean('carbon-panel-visible', panelVisible);
  }, [panelVisible]);

  // Persist copilot visibility
  useEffect(() => {
    setStoredBoolean('carbon-copilot-visible', copilotVisible);
  }, [copilotVisible]);

  const changeStudio = useCallback((studioId) => {
    setActiveStudio(studioId);
  }, []);

  // Cycle: hidden → peek → pinned → hidden
  const toggleSidebar = useCallback(() => {
    setSidebarMode(prev => {
      if (prev === 'hidden') return 'peek';
      if (prev === 'peek') return 'pinned';
      return 'hidden';
    });
  }, [setSidebarMode]);

  // Open sidebar as peek (from studio click when hidden)
  const openSidebarPeek = useCallback(() => {
    setSidebarModeRaw(prev => {
      if (prev === 'hidden') {
        try { localStorage.setItem('carbon-sidebar-mode', 'peek'); } catch { /* ignore */ }
        return 'peek';
      }
      return prev;
    });
  }, []);

  // Dismiss peek back to hidden
  const dismissSidebarPeek = useCallback(() => {
    setSidebarModeRaw(prev => {
      if (prev === 'peek') {
        try { localStorage.setItem('carbon-sidebar-mode', 'hidden'); } catch { /* ignore */ }
        return 'hidden';
      }
      return prev;
    });
  }, []);

  // Pin current peek → pinned
  const pinSidebar = useCallback(() => {
    setSidebarMode('pinned');
  }, [setSidebarMode]);

  const togglePanel = useCallback(() => {
    setPanelVisible(prev => !prev);
  }, []);

  const toggleCopilot = useCallback(() => {
    setCopilotVisible(prev => !prev);
  }, []);

  // Explicitly OPEN the copilot pane (used by task transfer to auto-open when hidden).
  // Unlike toggleCopilot, this never closes an already-open pane.
  const openCopilot = useCallback(() => {
    setCopilotVisible(true);
  }, []);

  return {
    studios,
    activeStudio,
    changeStudio,
    sidebarMode,
    toggleSidebar,
    openSidebarPeek,
    dismissSidebarPeek,
    pinSidebar,
    panelVisible,
    togglePanel,
    copilotVisible,
    toggleCopilot,
    openCopilot,
    commandPaletteOpen,
    setCommandPaletteOpen,
  };
}
