// File: src/pages/dataschema/RowDetailPage.jsx
// Row detail page with three-column layout: header + main content + metrics panel

import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  CircularProgress,
  Alert,
  Tabs,
  Tab,
} from '@mui/material';
import { useAuth } from '../../auth/AuthContext';
import { API_BASE_URL, API_ROUTES } from '../../config';
import RowDetailHeader from './RowDetailHeader';
import RowDetailMainPanel from './RowDetailMainPanel';
import RowMetricsPanel from './RowMetricsPanel';
import ResizableDivider from './ResizableDivider';

function notify(message, type = 'info') {
  const event = new CustomEvent('notify', { detail: { message, type } });
  window.dispatchEvent(event);
}

const DEFAULT_PANEL_WIDTH = 350;
const MIN_PANEL_WIDTH = 250;
const MAX_PANEL_WIDTH_PERCENT = 0.5;

export default function RowDetailPage() {
  const { tableId, rowId } = useParams();
  const { user, token } = useAuth();
  const navigate = useNavigate();

  const [rowData, setRowData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [mainTabIndex, setMainTabIndex] = useState(0);
  const [metricsTabIndex, setMetricsTabIndex] = useState(0);
  const [panelWidth, setPanelWidth] = useState(() => {
    const stored = localStorage.getItem('carbonRowDetail:panelWidth');
    return stored ? parseInt(stored, 10) : DEFAULT_PANEL_WIDTH;
  });
  const [metricsPanelOpen, setMetricsPanelOpen] = useState(() => {
    const stored = localStorage.getItem('carbonRowDetail:metricsPanelOpen');
    return stored !== 'false'; // Default to open
  });

  useEffect(() => {
    const savedMainTab = localStorage.getItem('carbonRowDetail:mainTab');
    const savedMetricsTab = localStorage.getItem('carbonRowDetail:metricsTab');
    if (savedMainTab) setMainTabIndex(parseInt(savedMainTab, 10));
    if (savedMetricsTab) setMetricsTabIndex(parseInt(savedMetricsTab, 10));
  }, []);

  const handleMainTabChange = (event, newValue) => {
    setMainTabIndex(newValue);
    localStorage.setItem('carbonRowDetail:mainTab', newValue);
  };

  const handleMetricsTabChange = (event, newValue) => {
    setMetricsTabIndex(newValue);
    localStorage.setItem('carbonRowDetail:metricsTab', newValue);
  };

  useEffect(() => {
    const fetchRowData = async () => {
      let currentToken = token;

      if (!currentToken) {
        currentToken = localStorage.getItem('access');
      }

      if (!currentToken || !rowId || !tableId) {
        setError('Authentication required. Please log in.');
        setLoading(false);
        return;
      }

      setLoading(true);
      setError(null);

      try {
        const url = `${API_BASE_URL}${API_ROUTES.rows}${rowId}/?data_table=${tableId}`;
        const response = await fetch(url, {
          headers: {
            Authorization: `Bearer ${currentToken}`,
          },
        });

        if (!response.ok) {
          throw new Error(`Failed to fetch row: ${response.status} ${response.statusText}`);
        }

        const data = await response.json();
        setRowData(data);
      } catch (err) {
        setError(err.message || 'Failed to load row data');
        notify(`Error: ${err.message}`, 'error');
      } finally {
        setLoading(false);
      }
    };

    fetchRowData();
  }, [token, rowId, tableId]);

  const handlePanelWidthChange = (newWidth) => {
    const maxWidth = MAX_PANEL_WIDTH_PERCENT * window.innerWidth;
    const constrainedWidth = Math.max(
      MIN_PANEL_WIDTH,
      Math.min(newWidth, maxWidth)
    );
    setPanelWidth(constrainedWidth);
    localStorage.setItem('carbonRowDetail:panelWidth', constrainedWidth);
  };

  const handleToggleMetricsPanel = () => {
    const newState = !metricsPanelOpen;
    setMetricsPanelOpen(newState);
    localStorage.setItem('carbonRowDetail:metricsPanelOpen', newState.toString());
  };

  const handleClose = () => {
    navigate(-1);
  };

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

  if (error) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error">
          <strong>Error loading row:</strong> {error}
        </Alert>
        <Box sx={{ mt: 2 }}>
          <button onClick={handleClose}>← Back to list</button>
        </Box>
      </Box>
    );
  }

  if (!rowData) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="warning">Row not found</Alert>
        <Box sx={{ mt: 2 }}>
          <button onClick={handleClose}>← Back to list</button>
        </Box>
      </Box>
    );
  }

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        bgcolor: 'background.default',
      }}
    >
      <RowDetailHeader rowData={rowData} onClose={handleClose} />

      <Box
        sx={{
          display: 'flex',
          flex: 1,
          overflow: 'hidden',
          borderTop: '1px solid #e0e0e0',
        }}
      >
        <Box
          sx={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            minWidth: '400px',
          }}
        >
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
              <Tab label="Overview" />
              <Tab label="Edit" />
              <Tab label="Evidence" />
            </Tabs>
          </Box>

          <Box sx={{ flex: 1, overflow: 'auto', bgcolor: 'white' }}>
            <RowDetailMainPanel
              mainTabIndex={mainTabIndex}
              rowData={rowData}
              setRowData={setRowData}
              tableId={tableId}
              rowId={rowId}
              token={token}
              onClose={handleClose}
            />
          </Box>
        </Box>

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
              <RowMetricsPanel
                rowId={rowId}
                tableId={tableId}
                token={token}
                metricsTabIndex={metricsTabIndex}
                onMetricsTabChange={handleMetricsTabChange}
              />
            </Box>
          )}
        </>
      </Box>
    </Box>
  );
}
