// src/components/entity/useDetailPanel.js
// Standard right panel hook for EntityDetailShell three-column layout.
// Eliminates 40+ lines of tab boilerplate duplicated across MyDataPage,
// ModuleWorkspacePage, and DataEntryPage.
//
// Usage:
//   const { metricsPanel, metricsTabs, activeMetricsTab, onMetricsTabChange }
//     = useDetailPanel({ tabs, storageKey });
//   <EntityDetailShell {...panelProps} ... />
//
// Configurable panel:
//   When configurable=true, a gear icon appears in the tab header,
//   users can show/hide individual tabs, persisted in localStorage.

import React, { useState, useMemo, useCallback } from 'react';
import { Box, Tab, Tabs, IconButton, Tooltip, Typography } from '@mui/material';
import SettingsIcon from '@mui/icons-material/Settings';
import { PanelConfigDialog } from '../panel';

/**
 * @param {Object} opts
 * @param {Array<{label:string, description?:string, render:()=>JSX}>} opts.tabs – panel tab definitions
 * @param {string} [opts.storageKey='detailPanel:tab'] – localStorage key for tab persistence
 * @param {number} [opts.defaultTab=0] – default active tab index
 * @param {boolean} [opts.configurable=false] – show gear icon to allow users to hide/show tabs
 * @returns {{ metricsPanel, metricsTabs, activeMetricsTab, onMetricsTabChange, visibleTabs, panelConfigOpen, toggleConfigPopup, saveConfig, resetTab }}
 */
export default function useDetailPanel({
  tabs = [],
  storageKey = 'detailPanel:tab',
  defaultTab = 0,
  configurable = false,
}) {
  // ── Active tab state ──
  const [activeTab, setActiveTab] = useState(() => {
    try {
      const stored = localStorage.getItem(storageKey);
      const parsed = stored ? parseInt(stored, 10) : defaultTab;
      return Number.isFinite(parsed) && parsed < tabs.length ? parsed : defaultTab;
    } catch {
      return defaultTab;
    }
  });

  // ── Panel config state ──
  const [panelConfig, setPanelConfig] = useState(() => {
    if (!configurable) return {};
    try {
      const stored = localStorage.getItem(`${storageKey}:config`);
      return stored ? JSON.parse(stored) : {};
    } catch {
      return {};
    }
  });
  const [configOpen, setConfigOpen] = useState(false);

  // ── Visible tabs (filtered by config) ──
  const visibleTabs = useMemo(() => {
    if (!configurable) return tabs;
    return tabs.filter((tab) => panelConfig[tab.label] !== false);
  }, [tabs, configurable, panelConfig]);

  // ── Ensure activeTab stays in bounds after filtering ──
  const safeActiveTab = useMemo(() => {
    return Math.max(0, Math.min(activeTab, visibleTabs.length - 1));
  }, [activeTab, visibleTabs]);

  const handleTabChange = useCallback((_event, next) => {
    if (next >= visibleTabs.length) return;
    setActiveTab(next);
    try { localStorage.setItem(storageKey, String(next)); } catch { /* noop */ }
  }, [storageKey, visibleTabs]);

  const resetTab = useCallback(() => {
    setActiveTab(defaultTab);
    try { localStorage.setItem(storageKey, String(defaultTab)); } catch { /* noop */ }
  }, [defaultTab, storageKey]);

  // ── Config handlers ──
  const toggleConfigPopup = useCallback(() => {
    setConfigOpen((prev) => !prev);
  }, []);

  const saveConfig = useCallback((newConfig) => {
    setPanelConfig(newConfig);
    try { localStorage.setItem(`${storageKey}:config`, JSON.stringify(newConfig)); } catch { /* noop */ }
  }, [storageKey]);

  // ── Tab labels for config dialog (always all tabs) ──
  const allTabLabels = useMemo(() => tabs.map((t) => t.label), [tabs]);

  // ── Build metrics panel JSX ──
  const metricsPanel = useMemo(
    () => (
      <Box sx={{ height: '100%', overflow: 'auto' }}>
        <Box sx={{ borderBottom: 1, borderColor: 'divider', bgcolor: 'white' }}>
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            <Tabs
              value={safeActiveTab}
              onChange={handleTabChange}
              variant={configurable ? 'scrollable' : 'fullWidth'}
              scrollButtons="auto"
              sx={{
                flex: 1,
                '& .MuiTab-root': {
                  textTransform: 'none',
                  fontSize: '0.85rem',
                  minHeight: 42,
                  py: 0.75,
                },
              }}
            >
              {visibleTabs.map((tab) => (
              <Tooltip key={tab.label} title={tab.description || ''} arrow disableHoverListener={!tab.description}>
                <Tab label={tab.label} />
              </Tooltip>
            ))}
            </Tabs>
            {configurable && (
              <Tooltip title="Configure tabs">
                <IconButton
                  size="small"
                  onClick={toggleConfigPopup}
                  sx={{ mr: 0.5 }}
                >
                  <SettingsIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
                </IconButton>
              </Tooltip>
            )}
          </Box>
        </Box>
        <Box sx={{ p: 2 }}>
          {visibleTabs[safeActiveTab]?.render() ?? (
            <Box sx={{ p: 2, textAlign: 'center' }}>
              <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
                No visible tabs configured.
              </Typography>
            </Box>
          )}
        </Box>
        {configurable && (
          <PanelConfigDialog
            open={configOpen}
            onClose={() => setConfigOpen(false)}
            tabs={tabs.map((t) => ({ label: t.label }))}
            config={panelConfig}
            onSave={saveConfig}
          />
        )}
      </Box>
    ),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [safeActiveTab, visibleTabs, configurable, configOpen, panelConfig],
  );

  return {
    metricsPanel,
    metricsTabs: visibleTabs,
    activeMetricsTab: safeActiveTab,
    onMetricsTabChange: handleTabChange,
    visibleTabs,
    panelConfigOpen: configOpen,
    toggleConfigPopup,
    saveConfig,
    resetTab,
    tabStorageKey: storageKey,
  };
}
