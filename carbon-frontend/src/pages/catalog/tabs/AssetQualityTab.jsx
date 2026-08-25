import React, { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Grid,
  Stack,
  Typography,
  Alert,
} from '@mui/material';
import { DetailTabContent } from '../../../components/detail/DetailMainPanel';
import { useAuth } from '../../../auth/AuthContext';
import { useNotification } from '../../../components/NotificationProvider';
import { useNavigate } from 'react-router-dom';
import LaunchIcon from '@mui/icons-material/Launch';
import { getTableDQMetrics, getFieldDQMetrics, getDQResults, listDQRules } from '../../../api/dq';

const STATUS_COLOR = {
  passing: 'success',
  warning: 'warning',
  failing: 'error',
  unknown: 'default',
};

function getStatusColor(status) {
  return STATUS_COLOR[status] || 'default';
}

export default function AssetQualityTab({ entityData }) {
  const { t } = useTranslation('catalog');
  const { token } = useAuth();
  const { notify } = useNotification();
  const navigate = useNavigate();
  const [metrics, setMetrics] = useState(null);
  const [rules, setRules] = useState([]);
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadQualityData = useCallback(async () => {
    setLoading(true);
    setError(null);
    setMetrics(null);
    setRules([]);
    setResults([]);

    try {
      const dataTable = entityData?.data_table;
      const dataField = entityData?.data_field;
      const metricsPromise = dataTable
        ? getTableDQMetrics(dataTable, token)
        : dataField
        ? getFieldDQMetrics(dataField, token)
        : Promise.resolve(null);
      const rulesPromise = dataTable ? listDQRules(token, { data_table: dataTable }) : Promise.resolve([]);
      const resultsPromise = dataTable ? getDQResults({ data_table: dataTable, limit: 5, ordering: '-executed_at' }, token) : Promise.resolve([]);

      const [metricsData, rulesData, resultsData] = await Promise.all([metricsPromise, rulesPromise, resultsPromise]);
      setMetrics(metricsData || null);
      setRules(Array.isArray(rulesData) ? rulesData : rulesData?.results || []);
      setResults(Array.isArray(resultsData) ? resultsData : resultsData?.results || []);
    } catch (err) {
      setError(err.message || t('failedToLoadAssetQuality'));
      notify({ message: err.message || t('failedToLoadAssetQuality'), type: 'error' });
    } finally {
      setLoading(false);
    }
  }, [entityData, token, notify, t]);

  useEffect(() => {
    if (!entityData || !token) return;
    loadQualityData();
  }, [entityData, token, loadQualityData]);

  const score = metrics?.quality_score ?? entityData?.quality_score ?? 0;
  const status = metrics?.quality_status ?? entityData?.quality_status ?? 'unknown';
  const lastRun = metrics?.last_run || entityData?.updated_at || null;
  const ruleCount = rules.length;
  const passingCount = rules.filter((rule) => rule.is_active !== false).length;

  if (loading) {
    return (
      <DetailTabContent>
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
          <CircularProgress />
        </Box>
      </DetailTabContent>
    );
  }

  return (
    <DetailTabContent>
      {error && <Alert severity="warning" sx={{ mb: 2 }}>{error}</Alert>}
      <Grid container spacing={2}>
        <Grid size={{ xs: 12, md: 4 }}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                {t('qualityScore')}
              </Typography>
              <Typography variant="h3" fontWeight={700} color="text.primary">
                {score != null ? `${score}/100` : t('na')}
              </Typography>
              <Chip label={status} color={getStatusColor(status)} sx={{ mt: 2 }} />
              <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
                {lastRun ? `${t('lastEvaluated')} ${new Date(lastRun).toLocaleString()}` : t('noRecentEvaluation')}
              </Typography>
              {entityData?.data_table && (
                <Button
                  variant="outlined"
                  fullWidth
                  startIcon={<LaunchIcon />}
                  sx={{ mt: 3 }}
                  onClick={() => navigate(`/dq?table=${entityData.data_table}`)}
                >
                  {t('manageInDqWorkspace')}
                </Button>
              )}
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                {t('ruleCoverage')}
              </Typography>
              <Typography variant="h4" fontWeight={700}>
                {ruleCount}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                {t('activeDqRulesForAsset')}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                {passingCount} {passingCount === 1 ? t('activeRule') : t('activeRules')}.
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                {t('latestResults')}
              </Typography>
              <Stack spacing={1} sx={{ mt: 1 }}>
                {results.length === 0 ? (
                  <Typography variant="body2" color="text.secondary">
                    {t('noRecentValidationResults')}
                  </Typography>
                ) : (
                  results.slice(0, 3).map((result) => (
                    <Box key={result.id || result.rule || result.executed_at}>
                      <Typography variant="body2" fontWeight={600}>
                        {result.rule_name || result.rule || t('rule')}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {result.passed ? t('passed') : t('failed')} • {result.executed_at ? new Date(result.executed_at).toLocaleString() : t('unknown')}
                      </Typography>
                    </Box>
                  ))
                )}
              </Stack>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {entityData?.data_table && (
        <Box sx={{ mt: 3 }}>
          <Button
            variant="outlined"
            startIcon={<LaunchIcon />}
            onClick={() => navigate(`/dq?table=${entityData.data_table}`)}
          >
            {t('viewRulesInDqWorkspace')}
          </Button>
        </Box>
      )}
    </DetailTabContent>
  );
}
