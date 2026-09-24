// src/apps/my/MyPayslips.jsx
// My — read-only payslips by month (route /my/payslips).
// Data: GET people/me/payslips/ (validated/committed runs only).

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Card,
  CardContent,
  Chip,
  IconButton,
  Paper,
  Skeleton,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import ReceiptLongIcon from '@mui/icons-material/ReceiptLong';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import { useTranslation } from 'react-i18next';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import EmptyState from '../../components/Page/EmptyState';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import { fetchMyPayslips } from '../../api/my';

const LINE_I18N = {
  gross: 'payslipLineGross',
  gosi: 'payslipLineGosi',
  loan_installment: 'payslipLineLoan',
  net: 'payslipLineNet',
};

const LINE_ORDER = ['gross', 'gosi', 'loan_installment', 'loan', 'net'];

function lineCode(lineType) {
  if (lineType == null || lineType === '') return '';
  if (typeof lineType === 'object') return String(lineType.code || '').trim().toLowerCase();
  return String(lineType).trim().toLowerCase();
}

function lineLabel(lineType, t) {
  const code = lineCode(lineType);
  const key = LINE_I18N[code];
  if (key) return t(key);
  if (typeof lineType === 'object') {
    const label = String(lineType.label || '').trim();
    if (label) return label;
  }
  return code.replace(/_/g, ' ') || '—';
}

function formatAmount(amount) {
  const value = Number(amount);
  if (Number.isNaN(value)) return '—';
  return value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 3 });
}

function formatPeriod(start, end, locale) {
  if (!start) return null;
  try {
    const s = new Date(`${start}T00:00:00`);
    const opts = { month: 'long', year: 'numeric' };
    if (end && end !== start) {
      const e = new Date(`${end}T00:00:00`);
      if (s.getFullYear() === e.getFullYear() && s.getMonth() === e.getMonth()) {
        return s.toLocaleDateString(locale, opts);
      }
      return `${s.toLocaleDateString(locale, { day: 'numeric', month: 'short', year: 'numeric' })} → ${e.toLocaleDateString(locale, { day: 'numeric', month: 'short', year: 'numeric' })}`;
    }
    return s.toLocaleDateString(locale, opts);
  } catch {
    return start;
  }
}

function monthKey(line) {
  if (line.period_start) return String(line.period_start).slice(0, 7);
  return `run-${line.payroll_run}`;
}

function sortLines(lines) {
  return [...lines].sort((a, b) => {
    const ia = LINE_ORDER.indexOf(lineCode(a.line_type));
    const ib = LINE_ORDER.indexOf(lineCode(b.line_type));
    const oa = ia === -1 ? 99 : ia;
    const ob = ib === -1 ? 99 : ib;
    if (oa !== ob) return oa - ob;
    return (a.id || 0) - (b.id || 0);
  });
}

function amountFor(lines, code) {
  const hit = lines.find((l) => lineCode(l.line_type) === code);
  return hit ? Number(hit.amount) : null;
}

function isDeduction(code) {
  return code === 'gosi' || code === 'loan_installment' || code === 'loan' || code === 'tax' || code === 'wps';
}

/**
 * Group flat payslip lines into months (newest first).
 * @returns {{ key: string, runId: number|string, periodStart: string|null, periodEnd: string|null, status: string|null, lines: object[] }[]}
 */
export function groupPayslipsByMonth(lines) {
  const map = new Map();
  for (const line of lines || []) {
    const key = monthKey(line);
    if (!map.has(key)) {
      map.set(key, {
        key,
        runId: line.payroll_run,
        periodStart: line.period_start || null,
        periodEnd: line.period_end || null,
        status: line.run_status || null,
        lines: [],
      });
    }
    const g = map.get(key);
    g.lines.push(line);
    if (line.period_start && (!g.periodStart || line.period_start < g.periodStart)) {
      g.periodStart = line.period_start;
    }
    if (line.period_end && (!g.periodEnd || line.period_end > g.periodEnd)) {
      g.periodEnd = line.period_end;
    }
    if (line.run_status) g.status = line.run_status;
  }
  return [...map.values()].sort((a, b) => {
    const as = a.periodStart || '';
    const bs = b.periodStart || '';
    if (as !== bs) return bs.localeCompare(as);
    return Number(b.runId) - Number(a.runId);
  });
}

export default function MyPayslips() {
  const { t, i18n } = useTranslation('my');
  const { token } = useAuth();
  useDocumentTitle(t('payslipsPageTitle'));

  const [lines, setLines] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [index, setIndex] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchMyPayslips(token);
      setLines(Array.isArray(data) ? data : []);
      setIndex(0);
    } catch (err) {
      setError(err?.message || t('error'));
      setLines([]);
    } finally {
      setLoading(false);
    }
  }, [token, t]);

  useEffect(() => {
    load();
  }, [load]);

  const months = useMemo(() => groupPayslipsByMonth(lines), [lines]);
  const current = months[index] || null;
  const sorted = useMemo(
    () => (current ? sortLines(current.lines) : []),
    [current],
  );

  const gross = current ? amountFor(current.lines, 'gross') : null;
  const net = current ? amountFor(current.lines, 'net') : null;
  const gosi = current ? amountFor(current.lines, 'gosi') : null;
  const locale = i18n.language?.startsWith('ar') ? 'ar' : 'en';
  const periodLabel = current
    ? (formatPeriod(current.periodStart, current.periodEnd, locale)
      || t('payslipRunLabel', { id: current.runId }))
    : '';

  const canPrev = index < months.length - 1;
  const canNext = index > 0;

  return (
    <Box
      component="main"
      sx={{ width: '100%', flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}
      data-testid="my-payslips"
    >
      <PageContainer>
        <PageHeader
          icon={ReceiptLongIcon}
          title={t('payslipsPageTitle')}
          subtitle={t('payslipsPageSubtitle')}
        />

        {loading ? (
          <Stack spacing={1.5}>
            <Skeleton variant="rounded" height={48} />
            <Skeleton variant="rounded" height={100} />
            <Skeleton variant="rounded" height={220} />
          </Stack>
        ) : error ? (
          <Alert
            severity="error"
            action={(
              <Typography
                component="button"
                variant="body2"
                onClick={load}
                sx={{ border: 0, bgcolor: 'transparent', cursor: 'pointer', color: 'inherit', textDecoration: 'underline' }}
              >
                {t('retry')}
              </Typography>
            )}
          >
            {error}
          </Alert>
        ) : months.length === 0 ? (
          <EmptyState title={t('payslipsEmpty')} description={t('payslipsHonesty')} />
        ) : (
          <Stack spacing={1.5}>
            <Paper
              variant="outlined"
              sx={{
                px: 1,
                py: 0.75,
                display: 'flex',
                alignItems: 'center',
                gap: 1,
                borderRadius: 2,
              }}
              data-testid="payslip-month-nav"
            >
              <IconButton
                size="small"
                aria-label={t('payslipPrevMonth')}
                disabled={!canPrev}
                onClick={() => setIndex((i) => Math.min(months.length - 1, i + 1))}
                data-testid="payslip-month-prev"
              >
                <ChevronLeftIcon />
              </IconButton>
              <Box sx={{ flex: 1, textAlign: 'center', minWidth: 0 }}>
                <Typography variant="subtitle1" sx={{ fontWeight: 700, lineHeight: 1.2 }} data-testid="payslip-period-label">
                  {periodLabel}
                </Typography>
                <Stack direction="row" spacing={0.75} justifyContent="center" alignItems="center" sx={{ mt: 0.25, flexWrap: 'wrap' }}>
                  {current.periodStart ? (
                    <Typography variant="caption" color="text.secondary">
                      {t('payslipRunLabel', { id: current.runId })}
                      {current.periodStart && current.periodEnd
                        ? ` · ${current.periodStart} → ${current.periodEnd}`
                        : ''}
                    </Typography>
                  ) : (
                    <Typography variant="caption" color="text.secondary">
                      {t('payslipRunLabel', { id: current.runId })}
                    </Typography>
                  )}
                  {current.status ? (
                    <Chip size="small" label={current.status} variant="outlined" sx={{ height: 20, fontSize: '0.625rem', textTransform: 'capitalize' }} />
                  ) : null}
                  <Typography variant="caption" color="text.secondary">
                    {t('payslipMonthOf', { current: index + 1, total: months.length })}
                  </Typography>
                </Stack>
              </Box>
              <IconButton
                size="small"
                aria-label={t('payslipNextMonth')}
                disabled={!canNext}
                onClick={() => setIndex((i) => Math.max(0, i - 1))}
                data-testid="payslip-month-next"
              >
                <ChevronRightIcon />
              </IconButton>
            </Paper>

            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', px: 0.25 }}>
              {t('payslipsHonesty')}
            </Typography>

            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
              <Card variant="outlined" sx={{ flex: 1 }}>
                <CardContent sx={{ py: 1.25, '&:last-child': { pb: 1.25 } }}>
                  <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    {t('payslipLineGross')}
                  </Typography>
                  <Typography variant="h6" sx={{ fontVariantNumeric: 'tabular-nums' }} dir="ltr">
                    {gross == null ? '—' : formatAmount(gross)}
                  </Typography>
                </CardContent>
              </Card>
              <Card variant="outlined" sx={{ flex: 1 }}>
                <CardContent sx={{ py: 1.25, '&:last-child': { pb: 1.25 } }}>
                  <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    {t('payslipLineGosi')}
                  </Typography>
                  <Typography variant="h6" sx={{ fontVariantNumeric: 'tabular-nums' }} dir="ltr">
                    {gosi == null ? '—' : formatAmount(gosi)}
                  </Typography>
                </CardContent>
              </Card>
              <Card variant="outlined" sx={{ flex: 1, borderColor: 'primary.main' }}>
                <CardContent sx={{ py: 1.25, '&:last-child': { pb: 1.25 } }}>
                  <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    {t('payslipLineNet')}
                  </Typography>
                  <Typography variant="h6" color="primary.main" sx={{ fontWeight: 700, fontVariantNumeric: 'tabular-nums' }} dir="ltr">
                    {net == null ? '—' : formatAmount(net)}
                  </Typography>
                </CardContent>
              </Card>
            </Stack>

            <Paper variant="outlined" sx={{ borderRadius: 2, overflow: 'hidden' }}>
              <TableContainer>
                <Table size="small" aria-label={t('payslipsPageTitle')} data-testid="payslip-lines-table">
                  <TableHead>
                    <TableRow>
                      <TableCell>{t('payslipLineType')}</TableCell>
                      <TableCell align="right">{t('payslipAmount')}</TableCell>
                      <TableCell sx={{ display: { xs: 'none', sm: 'table-cell' } }}>{t('payslipRule')}</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {sorted.map((line) => {
                      const code = lineCode(line.line_type);
                      const deduction = isDeduction(code);
                      return (
                        <TableRow key={line.id} hover>
                          <TableCell>
                            <Typography variant="body2" sx={{ fontWeight: code === 'net' || code === 'gross' ? 600 : 400 }}>
                              {lineLabel(line.line_type, t)}
                            </Typography>
                          </TableCell>
                          <TableCell
                            align="right"
                            sx={{
                              fontVariantNumeric: 'tabular-nums',
                              color: deduction ? 'error.main' : code === 'net' ? 'primary.main' : 'text.primary',
                              fontWeight: code === 'net' ? 700 : 400,
                            }}
                            dir="ltr"
                          >
                            {deduction ? `(${formatAmount(line.amount)})` : formatAmount(line.amount)}
                          </TableCell>
                          <TableCell sx={{ display: { xs: 'none', sm: 'table-cell' } }}>
                            <Typography variant="caption" color="text.disabled">
                              {line.rule_id ? `${line.rule_id}${line.rule_version != null ? ` v${line.rule_version}` : ''}` : '—'}
                            </Typography>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>
          </Stack>
        )}
      </PageContainer>
    </Box>
  );
}
