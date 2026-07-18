// File: src/shell/useShellState.js
// Central state management for Shell layout preferences and studio navigation

import { useState, useEffect, useCallback, useMemo } from 'react';
import { useAuth } from '../auth/AuthContext';
import DashboardIcon from '@mui/icons-material/Dashboard';
import Co2Icon from '@mui/icons-material/Co2';
import StorageIcon from '@mui/icons-material/Storage';
import AdminPanelSettingsIcon from '@mui/icons-material/AdminPanelSettings';
import SettingsIcon from '@mui/icons-material/Settings';
import HelpIcon from '@mui/icons-material/Help';

// Studio definitions (can be extended per user role)
const DEFAULT_STUDIOS = [
  { 
    id: 'home', 
    label: 'Dashboard', 
    icon: DashboardIcon, 
    path: '/dashboard' 
  },
  { 
    id: 'emissions', 
    label: 'Emissions', 
    icon: Co2Icon, 
    path: '/emissions' 
  },
  { 
    id: 'dataschema', 
    label: 'Data Hub', 
    icon: StorageIcon, 
    path: '/dataschema' 
  },
  { 
    id: 'admin', 
    label: 'Admin', 
    icon: AdminPanelSettingsIcon, 
    path: '/admin/users' 
  },
  { 
    id: 'settings', 
    label: 'Settings', 
    icon: SettingsIcon, 
    path: '/settings', 
    bottom: true 
  },
  { 
    id: 'help', 
    label: 'Help', 
    icon: HelpIcon, 
    path: '/help', 
    bottom: true 
  },
];

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
  const { availablePerspectives } = useAuth();
  const studios = useMemo(() => {
    if (!availablePerspectives?.includes('admin')) {
      return DEFAULT_STUDIOS.filter((studio) => studio.id !== 'admin');
    }
    return DEFAULT_STUDIOS;
  }, [availablePerspectives]);

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
