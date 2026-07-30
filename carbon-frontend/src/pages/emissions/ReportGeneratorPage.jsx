import React, { useState, useEffect } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  TextField,
  Checkbox,
  FormControlLabel,
  FormGroup,
  CircularProgress,
  Alert,
  Snackbar,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Stack,
  Typography,
  MenuItem,
} from '@mui/material';
import { useAuth } from '../../auth/AuthContext';
import { fetchReportingPeriods, generateReport, downloadReportCsv, createReportConfig } from '../../api/emissions-extended';

export default function ReportGeneratorPage() {
  const { user: _user, token } = useAuth();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [snackbar, setSnackbar] = useState(null);
  const [periods, setPeriods] = useState([]);
  const [reportData, setReportData] = useState(null);
  const [showPreview, setShowPreview] = useState(false);
  const [configName, setConfigName] = useState('');
  const [state, setState] = useState({
    reporting_period_id: '',
    custom_start: '',
    custom_end: '',
    org_unit_id: '',
    ghg_scopes: [1, 2, 3],
    categories: [],
    grouping: 'scope',
    output_format: 'json',
  });

  useEffect(() => {
    loadPeriods();
  }, []);

  const loadPeriods = async () => {
    try {
      const res = await fetchReportingPeriods(token);
      setPeriods(Array.isArray(res) ? res : res.results || []);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleStateChange = (key, value) => {
    setState(prev => ({
      ...prev,
      [key]: value,
    }));
  };

  const handleScopeToggle = (scope) => {
    setState(prev => ({
      ...prev,
      ghg_scopes: prev.ghg_scopes.includes(scope)
        ? prev.ghg_scopes.filter(s => s !== scope)
        : [...prev.ghg_scopes, scope],
    }));
  };

  const handleGenerateReport = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await generateReport(state, token);
      setReportData(data);
      setShowPreview(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadCsv = async () => {
    try {
      const blob = await downloadReportCsv(state, token);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `report-${new Date().toISOString().split('T')[0]}.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleSaveConfig = async () => {
    if (!configName.trim()) {
      setError('Please enter a configuration name');
      return;
    }

    try {
      setLoading(true);
      await createReportConfig({
        ...state,
        name: configName,
      }, token);
      setSnackbar({ message: 'Configuration saved successfully', severity: 'success' });
      setConfigName('');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h5" sx={{ fontWeight: 'bold', mb: 3 }}>
        Report Generator
      </Typography>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <Stack spacing={3}>
        {/* Configuration Section */}
        <Card>
          <CardContent>
            <Typography variant="h6" sx={{ fontWeight: 'bold', mb: 2 }}>
              Report Configuration
            </Typography>

            <Stack spacing={2}>
              {/* Period Selection */}
              <TextField
                label="Reporting Period"
                select
                value={state.reporting_period_id}
                onChange={(e) => handleStateChange('reporting_period_id', e.target.value)}
                fullWidth
              >
                <MenuItem value="">Select Period</MenuItem>
                {periods.map(period => (
                  <MenuItem key={period.id} value={period.id}>
                    {period.name}
                  </MenuItem>
                ))}
              </TextField>

              {/* Custom Date Range */}
              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
                <TextField
                  label="Custom Start Date (YYYY-MM-DD)"
                  type="date"
                  value={state.custom_start}
                  onChange={(e) => handleStateChange('custom_start', e.target.value)}
                  InputLabelProps={{ shrink: true }}
                  sx={{ flex: 1 }}
                />
                <TextField
                  label="Custom End Date (YYYY-MM-DD)"
                  type="date"
                  value={state.custom_end}
                  onChange={(e) => handleStateChange('custom_end', e.target.value)}
                  InputLabelProps={{ shrink: true }}
                  sx={{ flex: 1 }}
                />
              </Stack>

              {/* Scopes */}
              <Box>
                <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 1 }}>
                  GHG Scopes
                </Typography>
                <FormGroup row>
                  {[1, 2, 3].map(scope => (
                    <FormControlLabel
                      key={scope}
                      control={
                        <Checkbox
                          checked={state.ghg_scopes.includes(scope)}
                          onChange={() => handleScopeToggle(scope)}
                        />
                      }
                      label={`Scope ${scope}`}
                    />
                  ))}
                </FormGroup>
              </Box>

              {/* Grouping */}
              <TextField
                label="Grouping"
                select
                value={state.grouping}
                onChange={(e) => handleStateChange('grouping', e.target.value)}
                fullWidth
              >
                <MenuItem value="scope">By Scope</MenuItem>
                <MenuItem value="category">By Category</MenuItem>
                <MenuItem value="module">By Module</MenuItem>
              </TextField>

              <Button
                variant="contained"
                onClick={handleGenerateReport}
                disabled={loading}
              >
                {loading ? <CircularProgress size={24} /> : 'Generate Report'}
              </Button>
            </Stack>
          </CardContent>
        </Card>

        {/* Preview Section */}
        {showPreview && reportData && (
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ fontWeight: 'bold', mb: 2 }}>
                Report Preview
              </Typography>

              <Box sx={{ mb: 2, p: 2, backgroundColor: '#f5f5f5', borderRadius: 1 }}>
                <Typography variant="body2">
                  <strong>Total Emissions:</strong> {reportData.total_co2e_tonnes?.toFixed(2) || 0} tonnes CO₂e
                </Typography>
              </Box>

              {/* Scope Breakdown Table */}
              {reportData.scope_breakdown && (
                <TableContainer component={Paper} sx={{ mb: 2 }}>
                  <Table size="small">
                    <TableHead sx={{ backgroundColor: '#f5f5f5' }}>
                      <TableRow>
                        <TableCell sx={{ fontWeight: 'bold' }}>Scope</TableCell>
                        <TableCell align="right" sx={{ fontWeight: 'bold' }}>CO₂e (tonnes)</TableCell>
                        <TableCell align="right" sx={{ fontWeight: 'bold' }}>Records</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {Object.entries(reportData.scope_breakdown).map(([scope, data]) => (
                        <TableRow key={scope}>
                          <TableCell>Scope {scope}</TableCell>
                          <TableCell align="right">{data.total_co2e_tonnes?.toFixed(2) || 0}</TableCell>
                          <TableCell align="right">{data.count || 0}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}

              <Stack direction="row" spacing={2}>
                <Button variant="contained" onClick={handleDownloadCsv}>
                  Download CSV
                </Button>
                <Button variant="outlined" onClick={() => setShowPreview(false)}>
                  Back to Config
                </Button>
              </Stack>
            </CardContent>
          </Card>
        )}

        {/* Save Configuration Section */}
        {showPreview && reportData && (
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ fontWeight: 'bold', mb: 2 }}>
                Save Configuration for Reuse
              </Typography>

              <Stack spacing={2}>
                <TextField
                  label="Configuration Name"
                  value={configName}
                  onChange={(e) => setConfigName(e.target.value)}
                  placeholder="e.g., Q3 2024 Scope 1&2 Report"
                  fullWidth
                />
                <Button
                  variant="contained"
                  onClick={handleSaveConfig}
                  disabled={loading || !configName.trim()}
                >
                  {loading ? <CircularProgress size={24} /> : 'Save Configuration'}
                </Button>
              </Stack>
            </CardContent>
          </Card>
        )}
      </Stack>

      {/* Snackbar */}
      <Snackbar
        open={!!snackbar}
        autoHideDuration={4000}
        onClose={() => setSnackbar(null)}
        message={snackbar?.message}
      />
    </Box>
  );
}
