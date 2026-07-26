import React, { useState, useMemo } from 'react';
import {
  Box,
  Card,
  CardContent,
  Chip,
  Divider,
  Grid,
  List,
  ListItemButton,
  ListItemText,
  Paper,
  Stack,
  Tab,
  Tabs,
  Typography,
  useTheme,
} from '@mui/material';
import ResizableDivider from '../../pages/dataschema/ResizableDivider';

const DEFAULT_PANEL_WIDTH = 350;
const MIN_PANEL_WIDTH = 250;
const MAX_PANEL_WIDTH_PERCENT = 0.5;

/**
 * EntityDetailShell - Flexible entity detail layout
 * 
 * Supports two patterns:
 * 
 * 1. THREE-COLUMN LAYOUT (when metricsPanel is provided):
 * ┌────────────────────────┐
 * │ Header                 │
 * ├────────┬──────┬────────┤
 * │ Main   │Resize│Metrics │
 * │ flex   │Divide│ Panel  │
 * └────────┴──────┴────────┘
 *
 * 2. SIMPLE LAYOUT (legacy, no metrics panel):
 * ┌────────────────────────┐
 * │ Header Paper           │
 * ├────────────────────────┤
 * │ Summary Cards (opt)    │
 * ├────────────────────────┤
 * │ Grid: Main | SidePanel │
 * └────────────────────────┘
 */
export default function EntityDetailShell({
  // Legacy header props (for simple layout)
  title,
  subtitle,
  icon,
  badges = [],
  headerActions,
  summaryCards = [],
  
  // Content props
  tabs = [],
  initialTab = 0,
  activeTab: controlledActiveTab,
  onTabChange,
  sidePanelSections = [],
  children,
  
  // Three-column mode props
  header, // Custom header component (takes precedence)
  mainTabs,
  activeMainTab,
  onMainTabChange,
  mainContent,
  metricsPanel,
  metricsTabs,
  activeMetricsTab,
  onMetricsTabChange,
  panelWidthKey = 'entityDetail:panelWidth',
}) {
  const theme = useTheme();
  const [panelWidth, setPanelWidth] = useState(() => {
    const stored = localStorage.getItem(panelWidthKey);
    return stored ? parseInt(stored, 10) : DEFAULT_PANEL_WIDTH;
  });

  const [internalActiveTab, setInternalActiveTab] = useState(initialTab);
  const [internalMainTab, setInternalMainTab] = useState(activeMainTab ?? 0);
  const [internalMetricsTab, setInternalMetricsTab] = useState(activeMetricsTab ?? 0);
  const [metricsPanelOpen, setMetricsPanelOpen] = useState(() => {
    const stored = localStorage.getItem(`${panelWidthKey}:open`);
    return stored !== 'false'; // Default to open
  });

  // Determine which layout to use
  const useThreeColumnLayout = !!(header && metricsPanel);
  
  // Use controlled or internal state
  const activeTab = controlledActiveTab ?? internalActiveTab;
  const mainTabIndex = activeMainTab !== undefined ? activeMainTab : internalMainTab;
  const metricsTabIndex = activeMetricsTab !== undefined ? activeMetricsTab : internalMetricsTab;

  const visibleTabs = useMemo(() => tabs.filter(Boolean), [tabs]);
  const visibleSideSections = useMemo(() => sidePanelSections.filter(Boolean), [sidePanelSections]);

  const handleTabChange = (event, nextValue) => {
    if (onTabChange) {
      onTabChange(event, nextValue);
    } else {
      setInternalActiveTab(nextValue);
    }
  };

  const handleMainTabChange = (event, nextValue) => {
    if (onMainTabChange) {
      onMainTabChange(event, nextValue);
    } else {
      setInternalMainTab(nextValue);
    }
  };

  const handleMetricsTabChange = (event, nextValue) => {
    if (onMetricsTabChange) {
      onMetricsTabChange(event, nextValue);
    } else {
      setInternalMetricsTab(nextValue);
    }
  };

  const handlePanelWidthChange = (newWidth) => {
    const maxWidth = MAX_PANEL_WIDTH_PERCENT * window.innerWidth;
    const constrainedWidth = Math.max(
      MIN_PANEL_WIDTH,
      Math.min(newWidth, maxWidth)
    );
    setPanelWidth(constrainedWidth);
    localStorage.setItem(panelWidthKey, constrainedWidth);
  };

  const handleToggleMetricsPanel = () => {
    const newState = !metricsPanelOpen;
    setMetricsPanelOpen(newState);
    localStorage.setItem(`${panelWidthKey}:open`, newState.toString());
  };

  const renderTabContent = () => {
    const activeTabItem = visibleTabs[activeTab];
    if (!activeTabItem) return null;
    if (activeTabItem.render) return activeTabItem.render();
    return children;
  };

  // THREE-COLUMN LAYOUT MODE
  if (useThreeColumnLayout) {
    return (
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          height: '100vh',
          bgcolor: 'background.default',
        }}
      >
        {/* Header */}
        <Box sx={{ bgcolor: 'white' }}>{header}</Box>

        {/* Three-Column Layout */}
        <Box
          sx={{
            display: 'flex',
            flex: 1,
            overflow: 'hidden',
            borderTop: '1px solid #e0e0e0',
          }}
        >
          {/* Main Content Area */}
          <Box
            sx={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
              minWidth: '400px',
            }}
          >
            {/* Main Tabs */}
            {(mainTabs?.length > 0 || visibleTabs.length > 0) && (
              <Box sx={{ borderBottom: 1, borderColor: 'divider', bgcolor: 'white' }}>
                <Tabs
                  value={mainTabIndex}
                  onChange={handleMainTabChange}
                  variant="scrollable"
                  scrollButtons="auto"
                  sx={{
                    '& .MuiTab-root': {
                      textTransform: 'none',
                      fontSize: '0.95rem',
                    },
                  }}
                >
                  {(mainTabs || visibleTabs).map((tab, idx) => (
                    <Tab key={idx} label={tab.label} />
                  ))}
                </Tabs>
              </Box>
            )}

            {/* Main Content */}
            <Box sx={{ flex: 1, overflow: 'auto', bgcolor: 'white' }}>
              {mainContent ? (
                mainContent
              ) : (mainTabs || visibleTabs)[mainTabIndex]?.render?.()}
            </Box>
          </Box>

          {/* Resizable Divider + Metrics Panel */}
          {metricsPanel && (
            <>
              {/* Toggle Button - Always Visible */}
              <Box
                onClick={handleToggleMetricsPanel}
                sx={{
                  width: '32px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  bgcolor: '#f5f5f5',
                  borderLeft: '1px solid #e0e0e0',
                  cursor: 'pointer',
                  transition: 'background-color 0.2s',
                  '&:hover': {
                    bgcolor: '#eeeeee',
                  },
                }}
              >
                <Box
                  sx={{
                    fontSize: '18px',
                    color: '#666',
                    fontWeight: 'bold',
                    transform: metricsPanelOpen ? 'scaleX(1)' : 'scaleX(-1)',
                    transition: 'transform 0.2s',
                  }}
                >
                  ›
                </Box>
              </Box>

              {/* Resizable Divider - Only when panel is open */}
              {metricsPanelOpen && <ResizableDivider onResize={handlePanelWidthChange} />}

              {/* Metrics Panel - Conditionally Rendered */}
              {metricsPanelOpen && (
                <Box
                  sx={{
                    width: `${panelWidth}px`,
                    display: 'flex',
                    flexDirection: 'column',
                    overflow: 'hidden',
                    borderLeft: '1px solid #e0e0e0',
                    bgcolor: '#f9fafb',
                    '@media (max-width: 1024px)': {
                      display: 'none',
                    },
                  }}
                >
                  {/* Metrics Tabs */}
                  {metricsTabs?.length > 0 && (
                    <Box sx={{ borderBottom: 1, borderColor: 'divider', bgcolor: 'white' }}>
                      <Tabs
                        value={metricsTabIndex}
                        onChange={handleMetricsTabChange}
                        variant="scrollable"
                        scrollButtons="auto"
                        sx={{
                          '& .MuiTab-root': {
                            textTransform: 'none',
                            fontSize: '0.9rem',
                          },
                        }}
                      >
                        {metricsTabs.map((tab, idx) => (
                          <Tab key={idx} label={tab.label} />
                        ))}
                      </Tabs>
                    </Box>
                  )}

                  {/* Metrics Content */}
                  <Box sx={{ flex: 1, overflow: 'auto' }}>
                    {metricsTabs?.length > 0
                      ? metricsTabs[metricsTabIndex]?.render?.() ?? metricsPanel
                      : metricsPanel}
                  </Box>
                </Box>
              )}
            </>
          )}
        </Box>
      </Box>
    );
  }

  // SIMPLE LAYOUT MODE (legacy - for pages without three-column needs)
  return (
    <Box sx={{ p: { xs: 2, md: 3 } }}>
      <Paper elevation={0} sx={{ p: { xs: 2, md: 3 }, border: `1px solid ${theme.palette.divider}`, borderRadius: 3, mb: 3 }}>
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} justifyContent="space-between" alignItems={{ xs: 'flex-start', md: 'center' }}>
          <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'flex-start' }}>
            <Box sx={{ mt: 0.5 }}>{icon}</Box>
            <Box>
              <Typography variant="h5" fontWeight={700}>{title}</Typography>
              <Typography variant="body2" color="text.secondary">{subtitle}</Typography>
              {badges.length > 0 && (
                <Stack direction="row" spacing={1} sx={{ mt: 1 }} useFlexGap flexWrap="wrap">
                  {badges.map((badge) => (
                    <Chip key={badge.label} label={badge.label} color={badge.color || 'default'} size="small" variant={badge.variant || 'outlined'} />
                  ))}
                </Stack>
              )}
            </Box>
          </Box>
          {headerActions && <Box>{headerActions}</Box>}
        </Stack>
      </Paper>

      {summaryCards.length > 0 && (
        <Grid container spacing={2} sx={{ mb: 3 }}>
          {summaryCards.map((card) => (
            <Grid item xs={12} sm={6} md={3} key={card.title}>
              <Paper sx={{ p: 2, height: '100%' }}>
                <Typography variant="caption" color="text.secondary" display="block">{card.title}</Typography>
                <Typography variant="h6" fontWeight={700}>{card.value}</Typography>
                {card.subtitle && <Typography variant="caption" color="text.secondary">{card.subtitle}</Typography>}
              </Paper>
            </Grid>
          ))}
        </Grid>
      )}

      <Grid container spacing={3}>
        <Grid item xs={12} lg={9}>
          <Card>
            <CardContent sx={{ pt: 1 }}>
              {visibleTabs.length > 0 && (
                <Tabs value={activeTab} onChange={handleTabChange} variant="scrollable" scrollButtons="auto" sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
                  {visibleTabs.map((tab) => (
                    <Tab key={tab.label} label={tab.label} />
                  ))}
                </Tabs>
              )}
              {visibleTabs.length > 0 ? renderTabContent() : <Box>{children}</Box>}
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} lg={3}>
          <Card>
            <CardContent>
              <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>Quick Access</Typography>
              <List dense disablePadding>
                {visibleSideSections.map((section) => (
                  <ListItemButton key={section.label} onClick={() => handleTabChange(null, section.tabIndex)}>
                    <ListItemText primary={section.label} secondary={section.description} />
                  </ListItemButton>
                ))}
              </List>
              <Divider sx={{ my: 2 }} />
              <Typography variant="caption" color="text.secondary">Entity detail shell with flexible layouts for all entity types.</Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}
