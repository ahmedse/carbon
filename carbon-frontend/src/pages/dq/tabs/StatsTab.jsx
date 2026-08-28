// carbon-frontend/src/pages/dq/tabs/StatsTab.jsx
import React, { useEffect, useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import { Alert, Box, Chip, Paper, Stack, Typography } from '@mui/material';
import Grid from '@mui/material/Grid';
import { TrendingDown, TrendingUp, TrendingFlat } from '@mui/icons-material';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip as ChartTooltip,
  Legend,
  Filler,
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import { useAuth } from '../../../auth/AuthContext';
import { useTranslation } from 'react-i18next';
import { useNotification } from '../../../components/NotificationProvider';
import { getDQRuleHistory, getDQResults } from '../../../api/dq';
import { RESULT_STATUS_COLORS } from '../constants';
import AIActionButton from '../../../components/dq/AIActionButton';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  ChartTooltip,
  Legend,
  Filler
);

function unwrap(data) {
  if (Array.isArray(data)) return data;
  if (data?.results) return data.results;
  return [];
}

function trendChip(trend, t) {
  if (trend === 'improving') {
    return <Chip size="small" color="success" icon={<TrendingUp />} label={t('stats.improving')} />;
  }
  if (trend === 'degrading') {
    return <Chip size="small" color="error" icon={<TrendingDown />} label={t('stats.degrading')} />;
  }
  return <Chip size="small" color="info" icon={<TrendingFlat />} label={t('stats.stable')} />;
}

function StatsTab({ rule, onAnalyzeAI }) {
  const { token } = useAuth();
  const { notifyFromError } = useNotification();
  const { t } = useTranslation('dq');
  const [history, setHistory] = useState(null);
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    Promise.all([
      getDQRuleHistory(token, rule.id),
      getDQResults({ rule: rule.id, ordering: '-run_at', limit: 50 }, token),
    ])
      .then(([historyPayload, resultsPayload]) => {
        if (!active) return;
        setHistory(historyPayload || null);
        setResults(unwrap(resultsPayload));
      })
      .catch((err) => notifyFromError(err, t('stats.loadError')))
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [token, rule?.id, notifyFromError, t]);

  const runs = useMemo(() => history?.runs || [], [history]);

  // Merge history runs with result-level checked/failed counts for the chart.
  const chart = useMemo(() => {
    const byKey = new Map();
    results.forEach((r) => byKey.set(r.run_at, r));
    const rows = [...runs]
      .map((run) => ({ ...run, result: byKey.get(run.run_at) }))
      .sort((a, b) => new Date(a.run_at) - new Date(b.run_at))
      .slice(-20);
    return {
      labels: rows.map((r) => (r.run_at ? new Date(r.run_at).toLocaleDateString() : '—')),
      score: rows.map((r) => (r.score != null ? Number(r.score) : null)),
      failed: rows.map((r) => r.result?.failed_count ?? null),
    };
  }, [runs, results]);

  const lastRun = useMemo(() => {
    const sorted = [...runs].sort((a, b) => new Date(b.run_at) - new Date(a.run_at));
    return sorted[0] || null;
  }, [runs]);

  const chartData = {
    labels: chart.labels,
    datasets: [
      {
        label: t('stats.chartScore'),
        data: chart.score,
        borderColor: 'rgb(99, 102, 241)',
        backgroundColor: 'rgba(99, 102, 241, 0.15)',
        fill: true,
        tension: 0.3,
        spanGaps: true,
        yAxisID: 'y',
      },
      {
        label: t('stats.chartFailedRows'),
        data: chart.failed,
        borderColor: 'rgb(239, 68, 68)',
        backgroundColor: 'rgba(239, 68, 68, 0.15)',
        fill: false,
        tension: 0.3,
        spanGaps: true,
        yAxisID: 'y1',
      },
    ],
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    scales: {
      y: {
        beginAtZero: true,
        max: 100,
        title: { display: true, text: t('stats.chartScorePct') },
      },
      y1: {
        position: 'right',
        beginAtZero: true,
        grid: { drawOnChartArea: false },
        title: { display: true, text: t('stats.chartFailedRows') },
      },
    },
  };

  return (
    <Box sx={{ p: 3 }}>
      <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" sx={{ mb: 2 }}>
        <Typography sx={{ fontSize: '0.8125rem', fontWeight: 700 }}>{t('stats.trend')}</Typography>
        {history ? trendChip(history.trend, t) : <Chip size="small" label="—" />}
        <Typography sx={{ color: 'text.secondary' }}>
          {runs.length === 1
            ? t('stats.recordedRun', { count: runs.length })
            : t('stats.recordedRuns', { count: runs.length })}
        </Typography>
        <Box sx={{ flexGrow: 1 }} />
        <AIActionButton title={t('stats.analyzeWithAi')} onClick={onAnalyzeAI} />
      </Stack>

      <Grid container spacing={2} sx={{ mb: 2 }}>
        <Grid size={{ xs: 12, md: 8 }}>
          <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
            <Typography sx={{ fontSize: '0.8125rem', fontWeight: 700, mb: 1.5 }}>
              {t('stats.chartTitle')}
            </Typography>
            {loading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
                <Typography sx={{ color: 'text.secondary' }}>{t('stats.loading')}</Typography>
              </Box>
            ) : chart.labels.length === 0 ? (
              <Alert severity="info">{t('stats.noRuns')}</Alert>
            ) : (
              <Box sx={{ height: 280 }}>
                <Line data={chartData} options={chartOptions} />
              </Box>
            )}
          </Paper>
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
            <Typography sx={{ fontSize: '0.8125rem', fontWeight: 700, mb: 1.5 }}>{t('stats.lastRun')}</Typography>
            {!lastRun ? (
              <Typography sx={{ color: 'text.secondary' }}>{t('stats.noRunsShort')}</Typography>
            ) : (
              <Stack spacing={1}>
                <Box>
                  <Typography sx={{ color: 'text.secondary', textTransform: 'uppercase' }}>
                    {t('stats.runAt')}
                  </Typography>
                  <Typography>
                    {lastRun.run_at ? new Date(lastRun.run_at).toLocaleString() : '—'}
                  </Typography>
                </Box>
                <Box>
                  <Typography sx={{ color: 'text.secondary', textTransform: 'uppercase' }}>
                    {t('stats.status')}
                  </Typography>
                  <Chip
                    size="small"
                    color={RESULT_STATUS_COLORS[lastRun.status] || (lastRun.passed ? 'success' : 'error')}
                    label={
                      lastRun.status === 'skipped_unavailable'
                        ? t('status.skippedUnavailable')
                        : lastRun.status === 'passed'
                          ? t('status.passed')
                          : lastRun.status === 'failed'
                            ? t('status.failed')
                            : lastRun.status || (lastRun.passed ? t('status.passed') : t('status.failed'))
                    }
                  />
                </Box>
                <Box>
                  <Typography sx={{ color: 'text.secondary', textTransform: 'uppercase' }}>
                    {t('stats.score')}
                  </Typography>
                  <Typography sx={{ fontSize: '1rem', fontWeight: 700 }}>
                    {lastRun.score != null ? `${Number(lastRun.score).toFixed(1)}%` : '—'}
                  </Typography>
                </Box>
              </Stack>
            )}
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
}

StatsTab.propTypes = {
  rule: PropTypes.object,
  onAnalyzeAI: PropTypes.func,
};

export default StatsTab;
