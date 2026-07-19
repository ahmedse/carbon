// File: src/components/dq/DQMetricsDrawer.jsx
import React, { useState, useEffect } from 'react';
import {
  Drawer,
  Box,
  Typography,
  Tabs,
  Tab,
  CircularProgress,
  Alert,
  IconButton,
} from '@mui/material';
import { Close as CloseIcon } from '@mui/icons-material';
import DataQualityCard from './DataQualityCard';
import DQRulesList from './DQRulesList';
import { getTableDQMetrics, getDQResults, getDQRules } from '../../api/dq';

function TabPanel({ children, value, index }) {
  return (
    <div hidden={value !== index} style={{ width: '100%' }}>
      {value === index && (
        <Box sx={{ p: 2 }}>
          {children}
        </Box>
      )}
    </div>
  );
}

export default function DQMetricsDrawer({ open, onClose, tableId, token }) {
  const [tabValue, setTabValue] = useState(0);
  const [metrics, setMetrics] = useState(null);
  const [results, setResults] = useState(null);
  const [rules, setRules] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (open && tableId && token) {
      fetchData();
    }
  }, [open, tableId, token]);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [metricsData, resultsData, rulesData] = await Promise.all([
        getTableDQMetrics(token, tableId),
        getDQResults(token, { data_table: tableId, limit: 100 }),
        getDQRules(token, { data_table: tableId }),
      ]);
      setMetrics(metricsData);
      setResults(resultsData);
      setRules(rulesData);
    } catch (err) {
      setError(`Failed to load DQ metrics: ${err.message}`);
      console.error('DQ Metrics error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleTabChange = (event, newValue) => {
    setTabValue(newValue);
  };

  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={onClose}
      PaperProps={{
        sx: {
          width: { xs: '100%', sm: 500, md: 600 },
          maxWidth: '90vw',
          display: 'flex',
          flexDirection: 'column',
        },
      }}
    >
      {/* Header */}
      <Box sx={{ p: 2, borderBottom: '1px solid #e0e0e0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="h6">Data Quality Metrics</Typography>
        <IconButton size="small" onClick={onClose}>
          <CloseIcon />
        </IconButton>
      </Box>

      {/* Loading / Error State */}
      {loading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', p: 4, minHeight: 300 }}>
          <CircularProgress />
        </Box>
      )}

      {error && !loading && (
        <Box sx={{ p: 2 }}>
          <Alert severity="error">{error}</Alert>
        </Box>
      )}

      {/* Content */}
      {!loading && !error && (
        <>
          {/* Tabs */}
          <Box sx={{ borderBottom: 1, borderColor: 'divider', px: 2 }}>
            <Tabs value={tabValue} onChange={handleTabChange} variant="fullWidth">
              <Tab label="Overview" />
              <Tab label="Rules" />
              <Tab label="Results" />
            </Tabs>
          </Box>

          {/* Tab Content */}
          <Box sx={{ flex: 1, overflowY: 'auto' }}>
            {/* Overview Tab */}
            <TabPanel value={tabValue} index={0}>
              {metrics ? (
                <DataQualityCard metrics={metrics} />
              ) : (
                <Typography color="text.secondary">No metrics available</Typography>
              )}
            </TabPanel>

            {/* Rules Tab */}
            <TabPanel value={tabValue} index={1}>
              {rules && rules.length > 0 ? (
                <DQRulesList rules={rules} />
              ) : (
                <Typography color="text.secondary">No rules configured</Typography>
              )}
            </TabPanel>

            {/* Results Tab */}
            <TabPanel value={tabValue} index={2}>
              {results && results.length > 0 ? (
                <Box>
                  <Typography variant="subtitle2" sx={{ mb: 2 }}>
                    Recent Validation Results ({results.length})
                  </Typography>
                  {results.map((result) => (
                    <Box
                      key={result.id}
                      sx={{
                        p: 2,
                        mb: 1,
                        border: '1px solid #e0e0e0',
                        borderRadius: 1,
                        backgroundColor: result.passed ? '#e8f5e9' : '#ffebee',
                      }}
                    >
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                        <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                          {result.rule_name || 'Rule'}
                        </Typography>
                        <Typography
                          variant="caption"
                          sx={{
                            backgroundColor: result.passed ? '#4caf50' : '#f44336',
                            color: 'white',
                            px: 1,
                            py: 0.5,
                            borderRadius: 0.5,
                          }}
                        >
                          {result.passed ? 'PASSED' : 'FAILED'}
                        </Typography>
                      </Box>
                      <Typography variant="caption" color="text.secondary">
                        {new Date(result.executed_at).toLocaleString()}
                      </Typography>
                      {result.error_message && (
                        <Typography variant="caption" sx={{ display: 'block', mt: 1, color: '#f44336' }}>
                          {result.error_message}
                        </Typography>
                      )}
                    </Box>
                  ))}
                </Box>
              ) : (
                <Typography color="text.secondary">No validation results</Typography>
              )}
            </TabPanel>
          </Box>
        </>
      )}
    </Drawer>
  );
}
