// src/pages/admin/ai/OutputQualityPanel.jsx
// Route /admin/ai/output-quality — read-only Output Quality drift dashboard.
// Backed by /ai/pulse/quality-trend/ (daily average quality score across the
// KG + DQ feedback ledgers, plus deterministic day-over-day drift flags).
// Never fabricated: loading spinner, offline paper, grounded empty state.
// RULE_8 tokens only; RULE_10 apiFetch only (via src/api/aiPulse.js).
import React, { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Chip,
  CircularProgress,
  Paper,
  Stack,
  Typography,
} from '@mui/material';
import CloudOffIcon from '@mui/icons-material/CloudOff';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
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
import useDocumentTitle from '../../../hooks/useDocumentTitle';
import PageContainer from '../../../components/layout/PageContainer';
import { useAuth } from '../../../auth/AuthContext';
import { getQualityTrend } from '../../../api/aiPulse';

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

/** Format a float average defensively (0..1 → 0–100%). */
function formatAvg(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
  return `${Math.round(Number(value) * 100)}%`;
}

function formatCount(value) {
  if (value === null || value === undefined) return '—';
  return Number(value).toLocaleString();
}

export default function OutputQualityPanel() {
  useDocumentTitle('Output Quality');
  const { token } = useAuth();

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const payload = await getQualityTrend(token);
        if (!cancelled) {
          setData(payload);
          setOffline(false);
        }
      } catch {
        if (!cancelled) {
          setData(null);
          setOffline(true);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  const chartData = useMemo(() => {
    const days = data?.by_day ?? [];
    return {
      labels: days.map((d) => d.date),
      datasets: [
        {
          label: 'Quality score',
          data: days.map((d) => d.avg),
          borderColor: '#2e7d32',
          backgroundColor: 'rgba(46, 125, 50, 0.15)',
          fill: true,
          tension: 0.25,
          pointRadius: 3,
        },
      ],
    };
  }, [data]);

  const chartOptions = useMemo(
    () => ({
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: { min: 0, max: 1, ticks: { callback: (v) => `${Math.round(v * 100)}%` } },
      },
      plugins: {
        legend: { display: false },
      },
    }),
    []
  );

  const hasSeries = (data?.by_day ?? []).length > 0;

  return (
    <PageContainer>
      <Stack spacing={1.5} sx={{ flex: 1, minHeight: 0 }}>
        <Stack direction="row" spacing={1} alignItems="center">
          <Typography variant="h5" fontWeight={700} sx={{ flex: 1 }}>
            Output Quality
          </Typography>
          {data && !offline && (
            <Chip
              size="small"
              color={data?.drift?.length ? 'warning' : 'success'}
              label={data?.drift?.length ? `${data.drift.length} drift flag(s)` : 'Stable'}
            />
          )}
        </Stack>
        <Typography variant="body2" color="text.secondary">
          Output-quality drift across the KG and DQ feedback ledgers. A drift flag fires when a
          day&#39;s average score drops 15% or more below the prior day — operators use this to
          spot regression before it reaches users.
        </Typography>

        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
            <CircularProgress size={24} />
          </Box>
        ) : offline || !data ? (
          <Paper variant="outlined" sx={{ p: 4, textAlign: 'center' }}>
            <CloudOffIcon fontSize="large" sx={{ color: 'text.secondary' }} />
            <Typography variant="subtitle1" sx={{ mt: 1 }} fontWeight={600}>
              Data unavailable
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              Data unavailable — the output-quality API is offline
            </Typography>
          </Paper>
        ) : (
          <>
            {/* ── Current summary ── */}
            <Paper variant="outlined" sx={{ p: 2 }}>
              <Typography variant="overline" color="text.secondary">
                Current quality
              </Typography>
              <Stack direction="row" spacing={4} sx={{ mt: 0.5 }} flexWrap="wrap">
                <Box>
                  <Typography variant="body2" color="text.secondary">
                    Average
                  </Typography>
                  <Typography variant="h6" fontWeight={700}>
                    {formatAvg(data?.current?.avg)}
                  </Typography>
                </Box>
                <Box>
                  <Typography variant="body2" color="text.secondary">
                    Signals
                  </Typography>
                  <Typography variant="h6" fontWeight={700}>
                    {formatCount(data?.current?.count)}
                  </Typography>
                </Box>
                <Box>
                  <Typography variant="body2" color="text.secondary">
                    Drift flags
                  </Typography>
                  <Typography variant="h6" fontWeight={700}>
                    {formatCount(data?.drift?.length)}
                  </Typography>
                </Box>
              </Stack>

              {/* Signal breakdown */}
              {(data?.by_signal ?? []).length > 0 && (
                <Stack direction="row" spacing={1} sx={{ mt: 1.5 }} flexWrap="wrap">
                  {(data?.by_signal ?? []).map((s) => (
                    <Chip
                      key={s.signal}
                      size="small"
                      variant="outlined"
                      label={`${s.signal}: ${formatAvg(s.avg)} (${s.count})`}
                    />
                  ))}
                </Stack>
              )}
            </Paper>

            {/* ── Trend chart ── */}
            {hasSeries ? (
              <Paper variant="outlined" sx={{ p: 2 }}>
                <Typography variant="overline" color="text.secondary">
                  Daily trend
                </Typography>
                <Box sx={{ height: 280, mt: 1 }}>
                  <Line data={chartData} options={chartOptions} />
                </Box>
              </Paper>
            ) : (
              <Alert severity="info" sx={{ fontSize: '0.75rem' }}>
                No quality signals recorded yet — output quality will appear here as feedback is
                captured.
              </Alert>
            )}

            {/* ── Drift flags ── */}
            {(data?.drift ?? []).length > 0 && (
              <Paper variant="outlined" sx={{ p: 2 }}>
                <Typography variant="overline" color="text.secondary">
                  Drift flags
                </Typography>
                <Stack spacing={1} sx={{ mt: 1 }}>
                  {(data?.drift ?? []).map((d) => (
                    <Stack key={d.date} direction="row" spacing={1} alignItems="center">
                      <TrendingDownIcon sx={{ fontSize: 18, color: 'warning.main' }} />
                      <Typography variant="body2" sx={{ fontSize: '0.8125rem' }}>
                        <strong>{d.date}</strong> — dropped {formatAvg(Math.abs(d.delta))} to{' '}
                        {formatAvg(d.avg)}
                      </Typography>
                    </Stack>
                  ))}
                </Stack>
              </Paper>
            )}
          </>
        )}
      </Stack>
    </PageContainer>
  );
}
