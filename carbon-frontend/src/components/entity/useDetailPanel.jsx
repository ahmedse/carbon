// src/components/entity/useDetailPanel.js
// Standard right panel hook for EntityDetailShell three-column layout.
// Eliminates 40+ lines of tab boilerplate duplicated across MyDataPage,
// ModuleWorkspacePage, and DataEntryPage.
//
// Usage:
//   const { metricsPanel, metricsTabs, activeMetricsTab, onMetricsTabChange }
//     = useDetailPanel({ tabs, storageKey });
//   <EntityDetailShell {...panelProps} ... />

import { useState, useMemo } from 'react';
import { Box, Tab, Tabs } from '@mui/material';

/**
 * @param {Object} opts
 * @param {Array<{label:string, render:()=>JSX}>} opts.tabs – panel tab definitions
 * @param {string} [opts.storageKey='detailPanel:tab'] – localStorage key for tab persistence
 * @param {number} [opts.defaultTab=0] – default active tab index
 * @returns {{ metricsPanel, metricsTabs, activeMetricsTab, onMetricsTabChange }}
 */
export default function useDetailPanel({
  tabs = [],
  storageKey = 'detailPanel:tab',
  defaultTab = 0,
}) {
  const [activeTab, setActiveTab] = useState(() => {
    try {
      const stored = localStorage.getItem(storageKey);
      const parsed = stored ? parseInt(stored, 10) : defaultTab;
      return Number.isFinite(parsed) && parsed < tabs.length ? parsed : defaultTab;
    } catch {
      return defaultTab;
    }
  });

  const handleTabChange = (_event, next) => {
    setActiveTab(next);
    try { localStorage.setItem(storageKey, String(next)); } catch { /* noop */ }
  };

  const resetTab = () => {
    setActiveTab(defaultTab);
    try { localStorage.setItem(storageKey, String(defaultTab)); } catch { /* noop */ }
  };

  const metricsPanel = useMemo(
    () => (
      <Box sx={{ height: '100%', overflow: 'auto' }}>
        <Box sx={{ borderBottom: 1, borderColor: 'divider', bgcolor: 'white' }}>
          <Tabs
            value={activeTab}
            onChange={handleTabChange}
            variant="fullWidth"
            sx={{
              '& .MuiTab-root': {
                textTransform: 'none',
                fontSize: '0.85rem',
                minHeight: 42,
                py: 0.75,
              },
            }}
          >
            {tabs.map((tab) => (
              <Tab key={tab.label} label={tab.label} />
            ))}
          </Tabs>
        </Box>
        <Box sx={{ p: 2 }}>{tabs[activeTab]?.render()}</Box>
      </Box>
    ),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [activeTab, tabs],
  );

  return {
    metricsPanel,
    metricsTabs: tabs,
    activeMetricsTab: activeTab,
    onMetricsTabChange: handleTabChange,
    resetTab,
  };
}
