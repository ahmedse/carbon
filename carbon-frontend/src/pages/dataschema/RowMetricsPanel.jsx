// File: src/pages/dataschema/RowMetricsPanel.jsx
// Right-side metrics panel with DQ Metrics, Lineage, Related Records tabs

import React, { useState, useEffect } from 'react';
import {
  Box,
  Tabs,
  Tab,
  CircularProgress,
  Alert,
  Typography,
} from '@mui/material';
import DQMetricsTab from './metrics/DQMetricsTab';
import DataLineageTab from './metrics/DataLineageTab';
import RelatedRecordsTab from './metrics/RelatedRecordsTab';

export default function RowMetricsPanel({
  rowId,
  tableId,
  token,
  metricsTabIndex,
  onMetricsTabChange,
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [dqMetrics, setDQMetrics] = useState(null);
  const [dqMetricsFetched, setDQMetricsFetched] = useState(false);

  // Lazy load DQ metrics only when user clicks the DQ Metrics tab
  useEffect(() => {
    let currentToken = token;
    
    console.log('🟦 RowMetricsPanel: useEffect triggered', {
      metricsTabIndex,
      token: !!currentToken,
      rowId,
      tableId,
      dqMetricsFetched,
      loading,
    });

    const fetchDQMetrics = async () => {
      // If no token, try to recover from localStorage
      if (!currentToken) {
        console.log('🟨 RowMetricsPanel: No token from context, attempting recovery');
        currentToken = localStorage.getItem('access');
        if (currentToken) {
          console.log('✅ RowMetricsPanel: Token recovered from localStorage');
        }
      }

      console.log('� RowMetricsPanel: fetchDQMetrics running', {
        metricsTabIndex,
        dqMetricsFetched,
        token: !!currentToken,
      });

      if (!currentToken || !rowId || !tableId || dqMetricsFetched) {
        console.log('🟨 RowMetricsPanel: Guard 1 returned - missing params or already fetched', {
          token: !!currentToken,
          rowId,
          tableId,
          dqMetricsFetched,
        });
        return;
      }

      if (metricsTabIndex !== 0) {
        console.log('🟨 RowMetricsPanel: Guard 2 returned - not on DQ tab', {
          metricsTabIndex,
        });
        return;
      }

      console.log('🟦 RowMetricsPanel: Starting fetch...');
      setLoading(true);
      setError(null);

      try {
        // For now, fetch from table-level metrics
        // In the future, this will be row-specific
        const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;
        const url1 = `${API_BASE_URL}/carbon-api/dq/metrics/table/${tableId}/?row_id=${rowId}`;
        console.log('🟦 RowMetricsPanel: Trying primary URL:', url1);

        const response = await fetch(url1, {
          headers: {
            Authorization: `Bearer ${currentToken}`,
          },
        });

        console.log('🟦 RowMetricsPanel: Primary response received', {
          status: response.status,
          ok: response.ok,
        });

        // If row-specific endpoint doesn't exist, try generic metrics
        if (!response.ok && response.status === 404) {
          const url2 = `${API_BASE_URL}/carbon-api/dq/metrics/table/${tableId}/`;
          console.log('🟨 RowMetricsPanel: Primary 404, trying fallback URL:', url2);

          const fallbackResponse = await fetch(url2, {
            headers: {
              Authorization: `Bearer ${currentToken}`,
            },
          });

          console.log('🟦 RowMetricsPanel: Fallback response received', {
            status: fallbackResponse.status,
            ok: fallbackResponse.ok,
          });

          if (fallbackResponse.ok) {
            const data = await fallbackResponse.json();
            console.log('🟩 RowMetricsPanel: Fallback fetch successful');
            setDQMetrics(data);
            setDQMetricsFetched(true);
          } else {
            throw new Error('Failed to fetch DQ metrics');
          }
        } else if (response.ok) {
          const data = await response.json();
          console.log('🟩 RowMetricsPanel: Primary fetch successful');
          setDQMetrics(data);
          setDQMetricsFetched(true);
        } else {
          throw new Error(`Failed to fetch DQ metrics: ${response.status}`);
        }
      } catch (err) {
        console.error('🔴 RowMetricsPanel: DQ Metrics fetch error:', err);
        setError(err.message || 'Failed to load DQ metrics');
        setDQMetricsFetched(true);
      } finally {
        setLoading(false);
      }
    };

    fetchDQMetrics();
  }, [token, rowId, tableId, metricsTabIndex, dqMetricsFetched]);

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Metrics tabs */}
      <Box sx={{ borderBottom: 1, borderColor: 'divider', bgcolor: 'white' }}>
        <Tabs
          value={metricsTabIndex}
          onChange={onMetricsTabChange}
          variant="scrollable"
          scrollButtons="auto"
          sx={{
            minHeight: 'auto',
            '& .MuiTab-root': {
              textTransform: 'none',
              fontSize: '0.85rem',
              py: 1,
              minHeight: 'auto',
            },
          }}
        >
          <Tab label="DQ Metrics" />
          <Tab label="Lineage" />
          <Tab label="Related" />
        </Tabs>
      </Box>

      {/* Tab content */}
      <Box sx={{ flex: 1, overflow: 'auto', p: 2 }}>
        {metricsTabIndex === 0 && loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
            <CircularProgress size={24} />
          </Box>
        ) : metricsTabIndex === 0 && error ? (
          <Alert severity="warning" sx={{ fontSize: '0.85rem' }}>
            {error}
          </Alert>
        ) : (
          <>
            {metricsTabIndex === 0 && (
              <DQMetricsTab
                metrics={dqMetrics}
                rowId={rowId}
                tableId={tableId}
                token={token}
              />
            )}
            {metricsTabIndex === 1 && (
              <DataLineageTab rowId={rowId} />
            )}
            {metricsTabIndex === 2 && (
              <RelatedRecordsTab rowId={rowId} />
            )}
          </>
        )}
      </Box>
    </Box>
  );
}
