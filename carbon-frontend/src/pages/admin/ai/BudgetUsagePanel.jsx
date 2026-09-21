// src/pages/admin/ai/BudgetUsagePanel.jsx
// Route /admin/ai/budget-usage — read-only LLM budget & usage panel backed by
// /ai/pulse/usage/. Never fabricated: loading spinner, offline paper, grounded
// empty state, then the real aggregates. RULE_8 tokens only; RULE_10 apiFetch
// only (via src/api/aiPulse.js); RULE_16.
import React, { useEffect, useMemo, useState } from 'react';
import {
  Box,
  Chip,
  CircularProgress,
  LinearProgress,
  Paper,
  Stack,
  Typography,
} from '@mui/material';
import CloudOffIcon from '@mui/icons-material/CloudOff';
import AccountBalanceWalletIcon from '@mui/icons-material/AccountBalanceWallet';
import useDocumentTitle from '../../../hooks/useDocumentTitle';
import { useTranslation } from 'react-i18next';
import PageContainer from '../../../components/layout/PageContainer';
import CarbonDataGrid from '../../../components/DataGrid/CarbonDataGrid';
import { useAuth } from '../../../auth/AuthContext';
import { getUsage } from '../../../api/aiPulse';

/** Format a USD amount, defensively (null/undefined/NaN -> '—'). */
function formatUsd(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
  return `$${Number(value).toFixed(4)}`;
}

/** Format an integer counter defensively. */
function formatInt(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
  return Number(value).toLocaleString();
}

export default function BudgetUsagePanel() {
  const { t } = useTranslation('ai');
  useDocumentTitle(t('control.budgetUsage.title'));
  const { token } = useAuth();

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const payload = await getUsage(token);
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

  const budgetUsd = Number(data?.budget_usd ?? 0);
  const spentToday = Number(data?.spent_today_usd ?? 0);
  const budgetPct = budgetUsd > 0 ? Math.min(100, (spentToday / budgetUsd) * 100) : 0;
  const exceeded = Boolean(data?.budget_exceeded);

  const modelRows = useMemo(() => (data?.by_model ?? []).map((row) => ({
    ...row,
    id: row.model || String(Math.random()),
  })), [data]);

  const dayRows = useMemo(() => (data?.by_day ?? []).map((row) => ({
    ...row,
    id: row.date || String(Math.random()),
  })), [data]);

  const modelColumns = useMemo(
    () => [
      { field: 'model', headerName: t('control.budgetUsage.colModel'), minWidth: 240, flex: 1 },
      { field: 'cost_usd', headerName: t('control.budgetUsage.colCostUsd'), width: 140, valueFormatter: ({ value }) => formatUsd(value) },
      { field: 'total_tokens', headerName: t('control.budgetUsage.colTokens'), width: 140, valueFormatter: ({ value }) => formatInt(value) },
      { field: 'calls', headerName: t('control.budgetUsage.colCalls'), width: 120, valueFormatter: ({ value }) => formatInt(value) },
    ],
    [t]
  );

  const dayColumns = useMemo(
    () => [
      { field: 'date', headerName: t('control.budgetUsage.colDate'), minWidth: 160, flex: 1 },
      { field: 'cost_usd', headerName: t('control.budgetUsage.colCostUsd'), width: 140, valueFormatter: ({ value }) => formatUsd(value) },
      { field: 'total_tokens', headerName: t('control.budgetUsage.colTokens'), width: 140, valueFormatter: ({ value }) => formatInt(value) },
      { field: 'calls', headerName: t('control.budgetUsage.colCalls'), width: 120, valueFormatter: ({ value }) => formatInt(value) },
    ],
    [t]
  );

  return (
    <PageContainer>
      <Stack spacing={1.5} sx={{ flex: 1, minHeight: 0 }}>
        <Stack direction="row" spacing={1} alignItems="center">
          <Typography variant="h5" fontWeight={700} sx={{ flex: 1 }}>{t('control.budgetUsage.title')}</Typography>
          {data && !offline && (
            <Chip
              size="small"
              color={exceeded ? 'error' : 'success'}
              label={exceeded ? t('control.budgetUsage.budgetExceeded') : t('control.budgetUsage.withinBudget')}
            />
          )}
        </Stack>
        <Typography variant="body2" color="text.secondary">
          {t('control.budgetUsage.subtitle')}
        </Typography>

        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
            <CircularProgress size={24} />
          </Box>
        ) : offline || !data ? (
          <Paper variant="outlined" sx={{ p: 4, textAlign: 'center' }}>
            <CloudOffIcon fontSize="large" sx={{ color: 'text.secondary' }} />
            <Typography variant="subtitle1" sx={{ mt: 1 }} fontWeight={600}>
              {t('control.budgetUsage.dataUnavailable')}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              {t('control.budgetUsage.offline')}
            </Typography>
          </Paper>
        ) : (
          <>
            {/* ── Budget summary ── */}
            <Paper variant="outlined" sx={{ p: 2 }}>
              <Stack spacing={1.5}>
                <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap">
                  <AccountBalanceWalletIcon color="primary" />
                  <Box>
                    <Typography variant="body2" color="text.secondary">{t('control.budgetUsage.dailyBudget')}</Typography>
                    <Typography variant="h6" fontWeight={700}>{formatUsd(budgetUsd)}</Typography>
                  </Box>
                  <Box>
                    <Typography variant="body2" color="text.secondary">{t('control.budgetUsage.spentToday')}</Typography>
                    <Typography variant="h6" fontWeight={700} color={exceeded ? 'error.main' : 'text.primary'}>
                      {formatUsd(spentToday)}
                    </Typography>
                  </Box>
                  <Box>
                    <Typography variant="body2" color="text.secondary">{t('control.budgetUsage.remaining')}</Typography>
                    <Typography variant="h6" fontWeight={700}>{formatUsd(data?.remaining_usd)}</Typography>
                  </Box>
                  <Box>
                    <Typography variant="body2" color="text.secondary">{t('control.budgetUsage.callsToday')}</Typography>
                    <Typography variant="h6" fontWeight={700}>{formatInt(data?.calls_today)}</Typography>
                  </Box>
                  <Box>
                    <Typography variant="body2" color="text.secondary">{t('control.budgetUsage.tokensToday')}</Typography>
                    <Typography variant="h6" fontWeight={700}>{formatInt(data?.tokens_today)}</Typography>
                  </Box>
                </Stack>
                <Box>
                  <LinearProgress
                    variant="determinate"
                    value={budgetPct}
                    color={exceeded ? 'error' : 'primary'}
                    sx={{ borderRadius: 1, height: 8 }}
                  />
                  <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
                    {t('control.budgetUsage.budgetConsumed', { pct: budgetPct.toFixed(1) })}
                  </Typography>
                </Box>
              </Stack>
            </Paper>

            {/* ── Lifetime totals ── */}
            <Paper variant="outlined" sx={{ p: 2 }}>
              <Typography variant="overline" color="text.secondary">{t('control.budgetUsage.lifetimeTotals')}</Typography>
              <Stack direction="row" spacing={4} sx={{ mt: 0.5 }} flexWrap="wrap">
                <Box>
                  <Typography variant="body2" color="text.secondary">{t('control.budgetUsage.calls')}</Typography>
                  <Typography variant="h6" fontWeight={700}>{formatInt(data?.calls_total)}</Typography>
                </Box>
                <Box>
                  <Typography variant="body2" color="text.secondary">{t('control.budgetUsage.tokens')}</Typography>
                  <Typography variant="h6" fontWeight={700}>{formatInt(data?.tokens_total)}</Typography>
                </Box>
                <Box>
                  <Typography variant="body2" color="text.secondary">{t('control.budgetUsage.cost')}</Typography>
                  <Typography variant="h6" fontWeight={700}>{formatUsd(data?.cost_total)}</Typography>
                </Box>
              </Stack>
            </Paper>

            {/* ── Per-model breakdown ── */}
            <Paper variant="outlined" sx={{ p: 2 }}>
              <Typography variant="overline" color="text.secondary">{t('control.budgetUsage.perModel')}</Typography>
              <Box sx={{ mt: 1 }}>
                <CarbonDataGrid
                  columns={modelColumns}
                  rows={modelRows}
                  loading={false}
                  getRowId={(row) => row.id}
                  emptyMessage={t('control.budgetUsage.emptyModels')}
                />
              </Box>
            </Paper>

            {/* ── 7-day breakdown ── */}
            <Paper variant="outlined" sx={{ p: 2 }}>
              <Typography variant="overline" color="text.secondary">{t('control.budgetUsage.last7Days')}</Typography>
              <Box sx={{ mt: 1 }}>
                <CarbonDataGrid
                  columns={dayColumns}
                  rows={dayRows}
                  loading={false}
                  getRowId={(row) => row.id}
                  emptyMessage={t('control.budgetUsage.emptyDays')}
                />
              </Box>
            </Paper>
          </>
        )}
      </Stack>
    </PageContainer>
  );
}
