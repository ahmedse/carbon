import React, { useCallback, useEffect, useState } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  IconButton,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from '@mui/material';
import useDocumentTitle from '../../hooks/useDocumentTitle';

import {
  Delete as DeleteIcon,
  Edit as EditIcon,
  PlayArrow as PlayIcon,
  Download as DownloadIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
} from '@mui/icons-material';
import { useAuth } from '../../auth/AuthContext';
import { fetchReportConfigs, runReportConfig, deleteReportConfig, downloadReportCsv } from '../../api/emissions-extended';

const formatRelativeTime = (dateString) => {
  if (!dateString) return 'Never';
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now - date;
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins} minute${diffMins > 1 ? 's' : ''} ago`;
  if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
  if (diffDays < 30) return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
  return date.toLocaleDateString();
};

const ScopeChip = ({ scope }) => {
  const scopeLabels = { 1: 'Scope 1', 2: 'Scope 2', 3: 'Scope 3' };
  const scopeColors = { 1: 'error.light', 2: 'info.light', 3: 'success.light' };
  return (
    <Chip
      label={scopeLabels[scope] || `Scope ${scope}`}
      size="small"
      sx={{ backgroundColor: scopeColors[scope] || 'action.disabledBackground', color: 'common.white' }}
    />
  );
};

const ReportResultPanel = ({ report, loading }) => {
  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
        <CircularProgress size={24} />
      </Box>
    );
  }

  if (!report) return null;

  return (
    <Paper sx={{ p: 2, backgroundColor: 'background.dark' }}>
      <Stack spacing={2}>
        <Box>
          <Typography variant="subtitle2" sx={{ fontWeight: 'bold' }}>
            Total Emissions: {report.total_co2e_tonnes?.toFixed(2) || 0} tonnes CO₂e
          </Typography>
        </Box>

        {report.scope_breakdown && Object.keys(report.scope_breakdown).length > 0 && (
          <Box>
            <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 1 }}>
              Scope Breakdown
            </Typography>
            <Stack spacing={1}>
              {Object.entries(report.scope_breakdown).map(([scope, data]) => (
                <Box key={scope} sx={{ display: 'flex', justifyContent: 'space-between', pl: 2 }}>
                  <Typography variant="body2">
                    <ScopeChip scope={parseInt(scope)} />
                  </Typography>
                  <Typography variant="body2">
                    {data.total_co2e_tonnes?.toFixed(2) || 0} tonnes ({data.count || 0} records)
                  </Typography>
                </Box>
              ))}
            </Stack>
          </Box>
        )}
      </Stack>
    </Paper>
  );
};

export default function SavedReportsPage() {
  useDocumentTitle("Saved Reports");
  const { user: _user, token } = useAuth();
  const [configs, setConfigs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState({});
  const [results, setResults] = useState({});
  const [expandedId, setExpandedId] = useState(null);
  const [deleteConfirmId, setDeleteConfirmId] = useState(null);

  const loadConfigs = useCallback(async () => {
    try {
      setLoading(true);
      const data = await fetchReportConfigs(token);
      setConfigs(data);
    } catch (error) {
      console.error('Error loading configs:', error);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadConfigs();
  }, [loadConfigs]);

  const handleRun = async (configId) => {
    try {
      setRunning(prev => ({ ...prev, [configId]: true }));
      const result = await runReportConfig(configId, token);
      setResults(prev => ({ ...prev, [configId]: result }));
      setExpandedId(configId);
    } catch (error) {
      console.error('Error running report:', error);
    } finally {
      setRunning(prev => ({ ...prev, [configId]: false }));
    }
  };

  const handleDownload = async (configId) => {
    try {
      const config = configs.find(c => c.id === configId);
      if (!config) return;

      const params = {
        reporting_period_id: config.reporting_period_id,
        custom_start: config.custom_start,
        custom_end: config.custom_end,
        org_unit_id: config.org_unit_id,
        ghg_scopes: config.ghg_scopes || [],
        categories: config.categories || [],
        grouping: config.grouping || 'scope',
      };

      const blob = await downloadReportCsv(params, token);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${config.name}.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error('Error downloading report:', error);
    }
  };

  const handleDelete = async (configId) => {
    try {
      await deleteReportConfig(configId, token);
      setConfigs(configs.filter(c => c.id !== configId));
      setDeleteConfirmId(null);
      setResults(prev => {
        const newResults = { ...prev };
        delete newResults[configId];
        return newResults;
      });
    } catch (error) {
      console.error('Error deleting config:', error);
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 400 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (configs.length === 0) {
    return (
      <Box sx={{ p: 3 }}>
        <Card sx={{ textAlign: 'center', py: 6 }}>
          <CardContent>
            <Typography variant="h6" sx={{ mb: 2, color: 'text.secondary' }}>
              No Saved Reports Yet
            </Typography>
            <Typography variant="body2" sx={{ color: 'text.disabled', mb: 3 }}>
              Generate your first report to save and reuse configurations.
            </Typography>
            <Button variant="contained" href="/data-owner/reports/generate">
              Generate Report
            </Button>
          </CardContent>
        </Card>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h5" sx={{ mb: 3, fontWeight: 'bold' }}>
        Saved Report Configurations
      </Typography>

      <TableContainer component={Paper}>
        <Table>
          <TableHead sx={{ backgroundColor: 'background.dark' }}>
            <TableRow>
              <TableCell sx={{ fontWeight: 'bold' }}>Configuration Name</TableCell>
              <TableCell sx={{ fontWeight: 'bold' }}>Created By</TableCell>
              <TableCell sx={{ fontWeight: 'bold' }}>Last Run</TableCell>
              <TableCell sx={{ fontWeight: 'bold' }}>Reporting Period</TableCell>
              <TableCell sx={{ fontWeight: 'bold' }}>Org Unit</TableCell>
              <TableCell align="center" sx={{ fontWeight: 'bold' }}>Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {configs.map(config => (
              <React.Fragment key={config.id}>
                <TableRow>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontWeight: 500 }}>
                      {config.name}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">{config.created_by_username}</Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                      {formatRelativeTime(config.last_run_at)}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">{config.reporting_period_name || '-'}</Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">{config.org_unit_name || 'All'}</Typography>
                  </TableCell>
                  <TableCell align="center">
                    <Stack direction="row" spacing={0.5} justifyContent="center">
                      <Tooltip title="Run Report">
                        <IconButton
                          size="small"
                          onClick={() => handleRun(config.id)}
                          disabled={running[config.id]}
                        >
                          {running[config.id] ? <CircularProgress size={20} /> : <PlayIcon fontSize="small" />}
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Download CSV">
                        <IconButton
                          size="small"
                          onClick={() => handleDownload(config.id)}
                          disabled={!results[config.id]}
                        >
                          <DownloadIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Edit">
                        <IconButton size="small">
                          <EditIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Delete">
                        <IconButton
                          size="small"
                          onClick={() => setDeleteConfirmId(config.id)}
                          sx={{ color: 'error.main' }}
                        >
                          <DeleteIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title={expandedId === config.id ? 'Collapse' : 'Expand'}>
                        <IconButton
                          size="small"
                          onClick={() => setExpandedId(expandedId === config.id ? null : config.id)}
                        >
                          {expandedId === config.id ? (
                            <ExpandLessIcon fontSize="small" />
                          ) : (
                            <ExpandMoreIcon fontSize="small" />
                          )}
                        </IconButton>
                      </Tooltip>
                    </Stack>
                  </TableCell>
                </TableRow>

                {expandedId === config.id && (
                  <TableRow>
                    <TableCell colSpan={6} sx={{ backgroundColor: 'background.paper', p: 2 }}>
                      <ReportResultPanel
                        report={results[config.id]}
                        loading={running[config.id]}
                      />
                    </TableCell>
                  </TableRow>
                )}
              </React.Fragment>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Delete Confirmation Dialog */}
      <Dialog open={!!deleteConfirmId} onClose={() => setDeleteConfirmId(null)}>
        <DialogTitle>Delete Report Configuration?</DialogTitle>
        <DialogContent>
          <Typography>
            This action cannot be undone. The configuration will be permanently deleted.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteConfirmId(null)}>Cancel</Button>
          <Button
            onClick={() => handleDelete(deleteConfirmId)}
            variant="contained"
            color="error"
          >
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
