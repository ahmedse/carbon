// src/shell/AIUsageTab.jsx
// Phase 21-B — Usage & cost panel: token budget, period totals, tier/model
// breakdown, and per-conversation usage, driven by the usage service API.
import React, { useCallback, useEffect, useState } from 'react';
import {
  Box,
  Button,
  Chip,
  FormControl,
  InputLabel,
  LinearProgress,
  MenuItem,
  Paper,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';
import { useAuth } from '../auth/AuthContext';
import { useNotification } from '../components/NotificationProvider';
import { getUsageSummary, getUsageByConversation } from '../api/aiWorkspace';

dayjs.extend(utc);
dayjs.extend(timezone);

const PROJECT_TIMEZONE = 'Africa/Cairo';

const PERIODS = [
  { value: '7d', label: 'Last 7 days' },
  { value: '30d', label: 'Last 30 days' },
  { value: '90d', label: 'Last 90 days' },
];

/** Humanize a raw token count, e.g. 1_234_500 -> "1.2M". */
// eslint-disable-next-line react-refresh/only-export-components
export function formatTokens(value) {
  const n = Number(value) || 0;
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)}K`;
  return String(n);
}

/** Render a money string ("0.000000") as "$x.xx". */
// eslint-disable-next-line react-refresh/only-export-components
export function formatCost(value) {
  const n = Number(value) || 0;
  return `$${n.toFixed(2)}`;
}

/** Render an ISO timestamp in the project timezone as "MMM D, YYYY". */
// eslint-disable-next-line react-refresh/only-export-components
export function formatResetDate(iso) {
  if (!iso) return '—';
  return dayjs.tz(iso, PROJECT_TIMEZONE).format('MMM D, YYYY');
}

function StatCard({ label, value, sub }) {
  return (
    <Paper variant="outlined" sx={{ flex: 1, minWidth: 0, p: 1.25 }}>
      <Typography variant="caption" color="text.secondary" display="block" noWrap>
        {label}
      </Typography>
      <Typography variant="subtitle1" fontWeight={600} noWrap>
        {value}
      </Typography>
      {sub ? (
        <Typography variant="caption" color="text.secondary" display="block" noWrap>
          {sub}
        </Typography>
      ) : null}
    </Paper>
  );
}

function BreakdownCard({ title, rows, emptyText }) {
  return (
    <Paper variant="outlined" sx={{ flex: 1, minWidth: 0, p: 1.25 }}>
      <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 1 }}>
        {title}
      </Typography>
      {rows.length === 0 ? (
        <Typography variant="caption" color="text.secondary">{emptyText}</Typography>
      ) : (
        <Stack spacing={0.75}>
          {rows.map(([name, bucket]) => (
            <Stack key={name} direction="row" alignItems="center" spacing={1}>
              <Typography variant="body2" noWrap sx={{ flex: 1 }}>
                {name}
              </Typography>
              <Typography variant="caption" color="text.secondary" noWrap>
                {formatTokens(bucket.tokens)} tok · {formatCost(bucket.cost)}
              </Typography>
              <Typography variant="caption" color="text.disabled" noWrap>
                {bucket.generations ?? 0} gen
              </Typography>
            </Stack>
          ))}
        </Stack>
      )}
    </Paper>
  );
}

function AIUsageTab() {
  const { token } = useAuth();
  const { notifyFromError } = useNotification();

  const [period, setPeriod] = useState('30d');
  const [summary, setSummary] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [summaryData, convData] = await Promise.all([
        getUsageSummary(token, { period }),
        getUsageByConversation(token, { period }),
      ]);
      setSummary(summaryData || null);
      setConversations(Array.isArray(convData?.conversations) ? convData.conversations : []);
    } catch (err) {
      setError(err.message || 'Could not load usage data');
      notifyFromError(err, 'Could not load usage data');
    } finally {
      setLoading(false);
    }
  }, [token, period, notifyFromError]);

  useEffect(() => {
    load();
  }, [load]);

  const quota = summary?.quota || null;
  const hasUsage =
    summary &&
    (Number(summary.total_tokens) > 0 || Number(summary.total_generations) > 0 || conversations.length > 0);

  const quotaPct = quota ? Math.max(0, Math.min(100, Number(quota.pct) || 0)) : 0;
  const quotaExceeded = Boolean(quota?.hard_exceeded);
  const quotaWarn = Boolean(quota?.soft_warning) && !quotaExceeded;
  const quotaLabel = quotaExceeded ? 'Limit reached' : quotaWarn ? 'Approaching limit' : 'On track';
  const quotaColor = quotaExceeded ? 'error' : quotaWarn ? 'warning' : 'success';

  const tiers = Object.entries(summary?.by_tier || {}).sort(
    (a, b) => (b[1]?.tokens || 0) - (a[1]?.tokens || 0),
  );
  const models = Object.entries(summary?.by_model || {}).sort(
    (a, b) => (b[1]?.tokens || 0) - (a[1]?.tokens || 0),
  );

  return (
    <Box sx={{ p: 2, height: '100%', overflow: 'auto' }}>
      {/* Toolbar */}
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}>
        <Typography variant="subtitle2" fontWeight={600} sx={{ flex: 1 }}>
          Usage
        </Typography>
        <FormControl size="small" sx={{ minWidth: 120 }}>
          <InputLabel id="usage-period-label">Period</InputLabel>
          <Select
            labelId="usage-period-label"
            id="usage-period"
            label="Period"
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            sx={{ fontSize: '0.8125rem' }}
          >
            {PERIODS.map((p) => (
              <MenuItem key={p.value} value={p.value} sx={{ fontSize: '0.8125rem' }}>
                {p.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <Button size="small" startIcon={<RefreshIcon />} onClick={load} variant="outlined">
          Refresh
        </Button>
      </Stack>

      {/* States */}
      {loading && (
        <Typography variant="caption" color="text.secondary">
          Loading…
        </Typography>
      )}

      {!loading && error && (
        <Stack spacing={1} alignItems="flex-start">
          <Typography variant="caption" color="error.main">{error}</Typography>
          <Button size="small" variant="outlined" onClick={load}>Retry</Button>
        </Stack>
      )}

      {!loading && !error && summary && !hasUsage && (
        <Box sx={{ textAlign: 'center', py: 6 }}>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            No usage recorded in this period.
          </Typography>
          <Typography variant="caption" color="text.disabled">
            Activity will appear here once the assistant is used.
          </Typography>
        </Box>
      )}

      {!loading && !error && summary && hasUsage && (
        <>
          {/* Quota */}
          {quota && (
            <Paper variant="outlined" sx={{ p: 1.5, mb: 1.5 }}>
              <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 0.75 }}>
                <Typography variant="subtitle2" fontWeight={600}>
                  Monthly token budget
                </Typography>
                <Chip size="small" label={quotaLabel} color={quotaColor} variant="outlined" />
              </Stack>
              <LinearProgress
                variant="determinate"
                value={quotaPct}
                color={quotaExceeded ? 'error' : quotaWarn ? 'warning' : 'primary'}
                aria-label="Quota usage"
                sx={{ mb: 0.75, borderRadius: 1 }}
              />
              <Typography variant="caption" color="text.secondary">
                {formatTokens(quota.used)} of {formatTokens(quota.limit)} used ·{' '}
                {formatTokens(quota.remaining)} remaining · resets {formatResetDate(quota.reset_at)}
              </Typography>
            </Paper>
          )}

          {/* Period totals */}
          <Stack direction="row" spacing={1.5} sx={{ mb: 1.5 }}>
            <StatCard label="Tokens used" value={formatTokens(summary.total_tokens)} sub="this period" />
            <StatCard label="Est. cost" value={formatCost(summary.total_cost)} sub="this period" />
            <StatCard
              label="Generations"
              value={String(Number(summary.total_generations) || 0)}
              sub={`${formatTokens(summary.prompt_tokens)} in · ${formatTokens(summary.completion_tokens)} out`}
            />
          </Stack>

          {/* Tier / model breakdown */}
          <Stack direction="row" spacing={1.5} sx={{ mb: 1.5 }} flexWrap="wrap" useFlexGap>
            <BreakdownCard title="By tier" rows={tiers} emptyText="No tier data." />
            <BreakdownCard title="By model" rows={models} emptyText="No model data." />
          </Stack>

          {/* Per-conversation table */}
          <Paper variant="outlined" sx={{ overflow: 'hidden' }}>
            <Typography variant="subtitle2" fontWeight={600} sx={{ p: 1.25, pb: 0.5 }}>
              Most active conversations
            </Typography>
            {conversations.length === 0 ? (
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', p: 1.25 }}>
                No conversation activity in this period.
              </Typography>
            ) : (
              <TableContainer>
                <Table size="small" aria-label="Conversation usage">
                  <TableHead>
                    <TableRow>
                      <TableCell>Conversation</TableCell>
                      <TableCell align="right">Messages</TableCell>
                      <TableCell align="right">Generations</TableCell>
                      <TableCell align="right">Tokens</TableCell>
                      <TableCell align="right">Cost</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {conversations.map((row) => (
                      <TableRow key={row.conversation_id} hover>
                        <TableCell
                          sx={{ maxWidth: 220, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}
                          title={row.title}
                        >
                          {row.title || 'Untitled conversation'}
                        </TableCell>
                        <TableCell align="right">{Number(row.message_count) || 0}</TableCell>
                        <TableCell align="right">{Number(row.generation_count) || 0}</TableCell>
                        <TableCell align="right">{formatTokens(row.total_tokens)}</TableCell>
                        <TableCell align="right">{formatCost(row.total_cost)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </Paper>
        </>
      )}
    </Box>
  );
}

export default AIUsageTab;
