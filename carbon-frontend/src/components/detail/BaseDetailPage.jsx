// File: src/components/detail/BaseDetailPage.jsx
// Unified base component for all detail pages with three-column layout pattern

import React, { useState, useEffect } from 'react';
import {
  Box,
  CircularProgress,
  Alert,
  Tabs,
  Tab,
  IconButton,
  useTheme,
  useMediaQuery,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';

const DEFAULT_PANEL_WIDTH = 350;
const MIN_PANEL_WIDTH = 250;
const MAX_PANEL_WIDTH_PERCENT = 0.5;

/**
 * BaseDetailPage - Unified template for all entity detail pages
 * 
 * Props:
 * - headerComponent: React element for header (with breadcrumbs)
 * - mainTabs: Array of {label, component} for main content tabs
 * - metricsTabs: Array of {label, component} for metrics panel tabs (optional)
 * - metricsPanel: Component to render in metrics panel (optional)
 * - loading: Boolean indicating loading state
 * - error: Error message or null
 * - onClose: Callback when close button clicked
 * - storageKey: Base key for localStorage persistence (e.g., 'carbonRowDetail')
 */
export default function BaseDetailPage({
  headerComponent,
  mainTabs = [],
  metricsTabs = [],
  metricsPanel: MetricsPanelComponent,
  loading = false,
  error = null,
  onClose = () => {},
  storageKey = 'detailPage',
  entityData = null,
}) {
  const hasMetricsPanel = metricsTabs.length > 0 || Boolean(MetricsPanelComponent);
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));

  // Tab state management
  const [mainTabIndex, setMainTabIndex] = useState(() => {
    const stored = localStorage.getItem(`${storageKey}:mainTab`);
    return stored ? parseInt(stored, 10) : 0;
  });

  const [metricsTabIndex, setMetricsTabIndex] = useState(() => {
    const stored = localStorage.getItem(`${storageKey}:metricsTab`);
    return stored ? parseInt(stored, 10) : 0;
  });

  // Panel state management
  const [panelWidth, setPanelWidth] = useState(() => {
    const stored = localStorage.getItem(`${storageKey}:panelWidth`);
    return stored ? parseInt(stored, 10) : DEFAULT_PANEL_WIDTH;
  });

  const [metricsPanelOpen, setMetricsPanelOpen] = useState(() => {
    const stored = localStorage.getItem(`${storageKey}:metricsPanelOpen`);
    return stored !== 'false'; // Default to open
  });

  const [isDragging, setIsDragging] = useState(false);

  const handleMainTabChange = (event, newValue) => {
    setMainTabIndex(newValue);
    localStorage.setItem(`${storageKey}:mainTab`, newValue);
  };

  const handleMetricsTabChange = (event, newValue) => {
    setMetricsTabIndex(newValue);
    localStorage.setItem(`${storageKey}:metricsTab`, newValue);
  };

  const handlePanelWidthChange = (newWidth) => {
    const maxWidth = MAX_PANEL_WIDTH_PERCENT * window.innerWidth;
    const constrainedWidth = Math.max(
      MIN_PANEL_WIDTH,
      Math.min(newWidth, maxWidth)
    );
    setPanelWidth(constrainedWidth);
    localStorage.setItem(`${storageKey}:panelWidth`, constrainedWidth);
  };

  const handleToggleMetricsPanel = () => {
    const newState = !metricsPanelOpen;
    setMetricsPanelOpen(newState);
    localStorage.setItem(`${storageKey}:metricsPanelOpen`, newState.toString());
  };

  // Resizable divider mouse event handlers
  useEffect(() => {
    const handleMouseMove = (e) => {
      if (!isDragging) return;
      const newWidth = window.innerWidth - e.clientX;
      handlePanelWidthChange(newWidth);
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      return () => {
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
      };
    }
  }, [isDragging]);

  // Loading state
  if (loading) {
    return (
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100vh',
          bgcolor: 'background.default',
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  // Error state
  if (error) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error">
          <strong>Error:</strong> {error}
        </Alert>
        <Box sx={{ mt: 2 }}>
          <button onClick={onClose}>← Back</button>
        </Box>
      </Box>
    );
  }

  // Main render
  const MainTabComponent = mainTabs[mainTabIndex]?.component;
  const MetricsTabComponent = metricsTabs[metricsTabIndex]?.component;

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        bgcolor: 'background.default',
      }}
    >
      {/* Header */}
      {headerComponent}

      {/* Main content area */}
      <Box
        sx={{
          display: 'flex',
          flex: 1,
          overflow: 'hidden',
        }}
      >
        {/* Main panel */}
        <Box
          sx={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            minWidth: isMobile ? '100%' : '400px',
          }}
        >
          {/* Main tabs */}
          {mainTabs.length > 0 && (
            <Box sx={{ borderBottom: 1, borderColor: 'divider', bgcolor: 'background.paper' }}>
              <Tabs
                value={mainTabIndex}
                onChange={handleMainTabChange}
                variant="scrollable"
                scrollButtons="auto"
              >
                {mainTabs.map((tab, idx) => (
                  <Tab key={idx} label={tab.label} />
                ))}
              </Tabs>
            </Box>
          )}

          {/* Main content */}
          <Box sx={{ flex: 1, overflow: 'auto', bgcolor: 'background.paper' }}>
            {MainTabComponent && <MainTabComponent entityData={entityData} />}
          </Box>
        </Box>

        {/* Resizable divider */}
        {!isMobile && metricsPanelOpen && hasMetricsPanel && (
          <Box
            onMouseDown={() => setIsDragging(true)}
            sx={{
              width: '4px',
              backgroundColor: isDragging ? theme.palette.primary.main : 'transparent',
              cursor: isDragging ? 'col-resize' : 'col-resize',
              '&:hover': {
                backgroundColor: theme.palette.primary.main,
              },
              transition: isDragging ? 'none' : 'background-color 0.2s',
              userSelect: 'none',
            }}
          />
        )}

        {/* Metrics panel */}
        {!isMobile && hasMetricsPanel && (
          <Box
            sx={{
              width: metricsPanelOpen ? panelWidth : '0',
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
              borderLeft: metricsPanelOpen ? 1 : 0,
              borderColor: 'divider',
              transition: metricsPanelOpen ? 'width 0.3s ease' : 'none',
              bgcolor: 'background.paper',
            }}
          >
            {/* Metrics toggle button */}
            {metricsPanelOpen && (
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  p: 1,
                  borderBottom: 1,
                  borderColor: 'divider',
                  bgcolor: 'background.paper',
                }}
              >
                <IconButton
                  onClick={handleToggleMetricsPanel}
                  size="small"
                  sx={{
                    transform: 'scaleX(-1)',
                    '&:hover': { bgcolor: 'action.hover' },
                  }}
                >
                  <ChevronRightIcon fontSize="small" />
                </IconButton>
              </Box>
            )}

            {/* Metrics tabs */}
            {metricsTabs.length > 0 && metricsPanelOpen && (
              <Box sx={{ borderBottom: 1, borderColor: 'divider', bgcolor: 'background.paper' }}>
                <Tabs
                  value={metricsTabIndex}
                  onChange={handleMetricsTabChange}
                  variant="fullWidth"
                >
                  {metricsTabs.map((tab, idx) => (
                    <Tab key={idx} label={tab.label} />
                  ))}
                </Tabs>
              </Box>
            )}

            {/* Metrics content */}
            {metricsPanelOpen && (
              <Box sx={{ flex: 1, overflow: 'auto', bgcolor: 'background.paper' }}>
                {MetricsTabComponent && <MetricsTabComponent entityData={entityData} />}
              </Box>
            )}
          </Box>
        )}

        {/* Collapsed metrics toggle button */}
        {!isMobile && hasMetricsPanel && !metricsPanelOpen && (
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              borderLeft: 1,
              borderColor: 'divider',
              bgcolor: 'background.paper',
            }}
          >
            <IconButton
              onClick={handleToggleMetricsPanel}
              size="small"
              sx={{
                m: 1,
                '&:hover': { bgcolor: 'action.hover' },
              }}
              title="Expand metrics panel"
            >
              <ChevronRightIcon fontSize="small" />
            </IconButton>
          </Box>
        )}
      </Box>
    </Box>
  );
}
