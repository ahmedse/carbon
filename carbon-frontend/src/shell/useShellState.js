// File: src/shell/useShellState.js
// Central state management for Shell layout preferences and studio navigation

import { useState, useEffect, useCallback, useMemo } from 'react';
import { useAuth } from '../auth/AuthContext';
import DashboardIcon from '@mui/icons-material/Dashboard';
import Co2Icon from '@mui/icons-material/Co2';
import CatalogIcon from '@mui/icons-material/LibraryBooks';
import AdminPanelSettingsIcon from '@mui/icons-material/AdminPanelSettings';
import SettingsIcon from '@mui/icons-material/Settings';
import HelpIcon from '@mui/icons-material/Help';
import { APP_REGISTRY } from '../apps/registry';
import { isGlobalAdmin, isCatalogAdmin, hasAppAccess } from '../utils/rbac';
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
  { id: 'settings', label: 'Settings',        icon: SettingsIcon,           path: '/settings',  bottom: true },
  { id: 'help',     label: 'Help',            icon: HelpIcon,               path: '/help',      bottom: true },
];

// Icon lookup for manifest-declared apps.
// Move 3: replace with a full MUI dynamic icon loader.
const MANIFEST_ICON_MAP = {
  Co2:       Co2Icon,
  Dashboard: DashboardIcon,
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
      
      // Hide catalog studio if not catalog admin
      if (s.id === 'catalog') {
        return isCatalogAdmin(user, availablePerspectives);
      }
      
      // For app studios, check if admin has disabled the app AND user has access
      const isAppStudio = APP_REGISTRY.some(app => app.id === s.id);
      if (isAppStudio) {
        if (!isAppEnabled(s.id)) return false;
        return hasAppAccess(s.id, user, context, availablePerspectives, userCapabilities);
      }
      
      // Always show home, settings, help
      return true;
    });
    
    return filtered;
  }, [availablePerspectives, user, context, isAppEnabled, userCapabilities]);

  const [activeStudio, setActiveStudio] = useState('home');
  const [sidebarVisible, setSidebarVisible] = useState(() => getStoredBoolean('carbon-sidebar-visible', true));
  const [panelVisible, setPanelVisible] = useState(() => getStoredBoolean('carbon-panel-visible', false));
  const [copilotVisible, setCopilotVisible] = useState(() => getStoredBoolean('carbon-copilot-visible', false));
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);

  // Persist sidebar visibility
  useEffect(() => {
    setStoredBoolean('carbon-sidebar-visible', sidebarVisible);
  }, [sidebarVisible]);

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

  const toggleSidebar = useCallback(() => {
    setSidebarVisible(prev => !prev);
  }, []);

  const togglePanel = useCallback(() => {
    setPanelVisible(prev => !prev);
  }, []);

  const toggleCopilot = useCallback(() => {
    setCopilotVisible(prev => !prev);
  }, []);

  return {
    studios,
    activeStudio,
    changeStudio,
    sidebarVisible,
    toggleSidebar,
    panelVisible,
    togglePanel,
    copilotVisible,
    toggleCopilot,
    commandPaletteOpen,
    setCommandPaletteOpen,
  };
}
