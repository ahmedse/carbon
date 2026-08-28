import React, { useState, useEffect, useCallback } from 'react';
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
import { useTranslation } from 'react-i18next';
import useDocumentTitle from '../../hooks/useDocumentTitle';

import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import { useAuth } from '../../auth/AuthContext';
import { useAITaskTransfer } from '../../shell/useAITaskTransfer';
import { fetchReportingPeriods, generateReport, downloadReportCsv, createReportConfig } from '../../api/emissions-extended';

export default function ReportGeneratorPage() {
  const { t } = useTranslation('emissions');
  useDocumentTitle(t('reportGeneratorTitle'));
  const { user: _user, token } = useAuth();
  const { transferTask } = useAITaskTransfer();
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

  const loadPeriods = useCallback(async () => {
    try {
      const res = await fetchReportingPeriods(token);
      setPeriods(Array.isArray(res) ? res : res.results || []);
    } catch (err) {
      setError(err.message);
    }
  }, [token]);

  useEffect(() => {
    loadPeriods();
  }, [loadPeriods]);

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
      setError(t('configNameRequired'));
      return;
    }

    try {
      setLoading(true);
      await createReportConfig({
        ...state,
        name: configName,
      }, token);
      setSnackbar({ message: t('configSaved'), severity: 'success' });
      setConfigName('');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleAskAI = async () => {
    const periodName = periods.find(
      (p) => String(p.id) === String(state.reporting_period_id),
    )?.name ?? null;
    await transferTask(
      'chat',
      {
        prompt: 'Help me configure and generate a greenhouse gas emissions report.',
        reporting_period_id: state.reporting_period_id || null,
        ghg_scopes: state.ghg_scopes,
      },
      {
        title: 'Emissions Report Help',
        source_page: 'emissions-report-generator',
        workspaceContext: {
          workspace: 'emissions',
          current_view: 'report_generator',
          entity_type: 'report',
          entity_id: state.reporting_period_id || null,
          entity_name: periodName,
          intent_signal: 'explore',
          recent_actions: [],
        },
      },
    );
  };

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 3 }}>
        <Typography variant="h5" sx={{ fontWeight: 'bold' }}>
          {t('reportGenerator')}
        </Typography>
        <Button
          size="small"
          variant="outlined"
          startIcon={<AutoAwesomeIcon />}
          onClick={handleAskAI}
        >
          {t('askAi')}
        </Button>
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <Stack spacing={3}>
        {/* Configuration Section */}
        <Card>
          <CardContent>
            <Typography variant="h6" sx={{ fontWeight: 'bold', mb: 2 }}>
              {t('reportConfiguration')}
            </Typography>

            <Stack spacing={2}>
              {/* Period Selection */}
              <TextField
                label={t('reportingPeriod')}
                select
                value={state.reporting_period_id}
                onChange={(e) => handleStateChange('reporting_period_id', e.target.value)}
                fullWidth
              >
                <MenuItem value="">{t('selectPeriod')}</MenuItem>
                {periods.map(period => (
                  <MenuItem key={period.id} value={period.id}>
                    {period.name}
                  </MenuItem>
                ))}
              </TextField>

              {/* Custom Date Range */}
              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
                <TextField
                  label={t('customStartDate')}
                  type="date"
                  value={state.custom_start}
                  onChange={(e) => handleStateChange('custom_start', e.target.value)}
                  InputLabelProps={{ shrink: true }}
                  sx={{ flex: 1 }}
                />
                <TextField
                  label={t('customEndDate')}
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
                  {t('ghgScopes')}
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
                      label={t('scopeChip', { scope })}
                    />
                  ))}
                </FormGroup>
              </Box>

              {/* Grouping */}
              <TextField
                label={t('grouping')}
                select
                value={state.grouping}
                onChange={(e) => handleStateChange('grouping', e.target.value)}
                fullWidth
              >
                <MenuItem value="scope">{t('byScope')}</MenuItem>
                <MenuItem value="category">{t('byCategory')}</MenuItem>
                <MenuItem value="module">{t('byModule')}</MenuItem>
              </TextField>

              <Button
                variant="contained"
                onClick={handleGenerateReport}
                disabled={loading}
              >
                {loading ? <CircularProgress size={24} /> : t('generateReport')}
              </Button>
            </Stack>
          </CardContent>
        </Card>

        {/* Preview Section */}
        {showPreview && reportData && (
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ fontWeight: 'bold', mb: 2 }}>
                {t('reportPreview')}
              </Typography>

              <Box sx={{ mb: 2, p: 2, bgcolor: 'background.dark', borderRadius: 1 }}>
                <Typography variant="body2">
                  <strong>{t('totalEmissions')}</strong> {reportData.total_co2e_tonnes?.toFixed(2) || 0} {t('tonnesCo2e')}
                </Typography>
              </Box>

              {/* Scope Breakdown Table */}
              {reportData.scope_breakdown && (
                <TableContainer component={Paper} sx={{ mb: 2 }}>
                  <Table size="small">
                    <TableHead sx={{ bgcolor: 'background.dark' }}>
                      <TableRow>
                        <TableCell sx={{ fontWeight: 'bold' }}>{t('scope')}</TableCell>
                        <TableCell align="right" sx={{ fontWeight: 'bold' }}>{t('co2eTonnes')}</TableCell>
                        <TableCell align="right" sx={{ fontWeight: 'bold' }}>{t('records')}</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {Object.entries(reportData.scope_breakdown).map(([scope, data]) => (
                        <TableRow key={scope}>
                          <TableCell>{t('scopeChip', { scope })}</TableCell>
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
                  {t('downloadCsv')}
                </Button>
                <Button variant="outlined" onClick={() => setShowPreview(false)}>
                  {t('backToConfig')}
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
                {t('saveConfigForReuse')}
              </Typography>

              <Stack spacing={2}>
                <TextField
                  label={t('configName')}
                  value={configName}
                  onChange={(e) => setConfigName(e.target.value)}
                  placeholder={t('configNamePlaceholder')}
                  fullWidth
                />
                <Button
                  variant="contained"
                  onClick={handleSaveConfig}
                  disabled={loading || !configName.trim()}
                >
                  {loading ? <CircularProgress size={24} /> : t('saveConfiguration')}
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
