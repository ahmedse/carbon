// src/apps/people/tabs/EmployeePayTab.jsx
// Per-employee pay view: lazy-fetches payroll runs + payslip lines on first mount.
// Shows latest payslip grouped as Earnings / Deductions / Totals, plus a
// 6-run history list with run selector.

import React, { useEffect, useRef, useState } from 'react';
import {
  Alert, Box, Chip, CircularProgress, Divider, MenuItem, Paper, Select,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Typography,
} from '@mui/material';
import ReceiptLongIcon from '@mui/icons-material/ReceiptLong';
import { useTranslation } from 'react-i18next';
import EmptyState from '../../../components/Page/EmptyState';
import { fetchPayrollRuns, fetchPayslipLines } from '../../../api/people';
import { formatAmount, formatDate, statusColor, statusLabelKey } from '../utils';

const EARNING_TYPES = new Set(['basic', 'gross', 'overtime', 'accommodation', 'allowance', 'tickets', 'transport']);
const DEDUCTION_TYPES = new Set(['gosi', 'deduction', 'loan', 'tax', 'wps']);

function isEarning(lineType) {
  const t = (lineType || '').toLowerCase();
  return EARNING_TYPES.has(t) || (!DEDUCTION_TYPES.has(t) && t !== 'net');
}

function PaylineRow({ line, secondary }) {
  return (
    <TableRow hover>
      <TableCell sx={{ fontSize: '0.75rem', textTransform: 'capitalize', color: secondary ? 'text.secondary' : 'text.primary', py: 0.5 }}>
        {(line.line_type || '').replace(/_/g, ' ')}
      </TableCell>
      <TableCell align="right" sx={{ fontSize: '0.75rem', fontVariantNumeric: 'tabular-nums', py: 0.5 }}>
        {secondary ? `(${formatAmount(line.amount)})` : formatAmount(line.amount)}
      </TableCell>
      {line.rule_id && (
        <TableCell sx={{ fontSize: '0.5625rem', color: 'text.disabled', py: 0.5 }}>
          {line.rule_id} v{line.rule_version}
        </TableCell>
      )}
    </TableRow>
  );
}

export default function EmployeePayTab({ entityData, additionalProps }) {
  const { t } = useTranslation('people');
  const token = additionalProps?.token;
  const emp = entityData || {};
  const empId = emp.empId ?? emp.id;

  const [runs, setRuns] = useState(null);
  const [allLines, setAllLines] = useState([]);
  const [selectedRunId, setSelectedRunId] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const loadedRef = useRef(false);

  // Lazy load on first mount
  useEffect(() => {
    if (loadedRef.current || !empId || !token) return;
    loadedRef.current = true;
    setLoading(true);
    setError(null);
    Promise.all([fetchPayrollRuns(token), fetchPayslipLines({}, token)])
      .then(([runsData, linesData]) => {
        const allRuns = Array.isArray(runsData?.results) ? runsData.results : (Array.isArray(runsData) ? runsData : []);
        const empLines = (Array.isArray(linesData?.results) ? linesData.results : (Array.isArray(linesData) ? linesData : []))
          .filter(l => l.employee === empId);
        setAllLines(empLines);
        setRuns(allRuns);
        // Auto-select most recent run that has lines for this employee
        const myRunIds = new Set(empLines.map(l => l.payroll_run));
        const latest = allRuns.find(r => myRunIds.has(r.id));
        if (latest) setSelectedRunId(String(latest.id));
      })
      .catch(err => setError(err?.message || t('payslipLoadError')))
      .finally(() => setLoading(false));
  }, [empId, token, t]);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', py: 6 }}>
        <CircularProgress size={28} />
      </Box>
    );
  }

  if (error) {
    return <Box sx={{ p: 2 }}><Alert severity="error">{error}</Alert></Box>;
  }

  if (!runs) return null;

  const myRunIds = new Set(allLines.map(l => l.payroll_run));
  const myRuns = runs.filter(r => myRunIds.has(r.id)).slice(0, 6);

  if (myRuns.length === 0) {
    return (
      <Box sx={{ p: 2 }}>
        <EmptyState title={t('payTabNoData')} description={t('payslipEmptyDesc')} />
      </Box>
    );
  }

  const currentLines = allLines.filter(l => l.payroll_run === Number(selectedRunId));
  const selectedRun = runs.find(r => r.id === Number(selectedRunId));

  const earnings = currentLines.filter(l => isEarning(l.line_type) && l.line_type !== 'gross' && l.line_type !== 'net');
  const deductions = currentLines.filter(l => DEDUCTION_TYPES.has((l.line_type || '').toLowerCase()));
  const grossLine = currentLines.find(l => l.line_type === 'gross');
  const netLine = currentLines.find(l => l.line_type === 'net');

  const grossTotal = grossLine
    ? Number(grossLine.amount)
    : earnings.reduce((s, l) => s + Number(l.amount), 0);
  const netTotal = netLine
    ? Number(netLine.amount)
    : grossTotal - deductions.reduce((s, l) => s + Number(l.amount), 0);

  return (
    <Box sx={{ p: 2 }}>

      {/* Run selector */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5 }}>
        <Typography sx={{ fontSize: '0.875rem', fontWeight: 600 }}>{t('payTabLatestSlip')}</Typography>
        <Select
          size="small"
          value={selectedRunId}
          onChange={e => setSelectedRunId(e.target.value)}
          sx={{ fontSize: '0.75rem', minWidth: 200, height: 28 }}
        >
          {myRuns.map(r => (
            <MenuItem key={r.id} value={String(r.id)} sx={{ fontSize: '0.75rem' }}>
              {formatDate(r.period_start)} → {formatDate(r.period_end)}
            </MenuItem>
          ))}
        </Select>
      </Box>

      {selectedRun && (
        <Box sx={{ display: 'flex', gap: 1, mb: 1.5, flexWrap: 'wrap' }}>
          <Chip
            size="small"
            variant="outlined"
            color={statusColor(selectedRun.status)}
            label={statusLabelKey(selectedRun.status) ? t(statusLabelKey(selectedRun.status)) : selectedRun.status}
            sx={{ height: 18, fontSize: '0.5625rem' }}
          />
          {selectedRun.committed_at && (
            <Typography sx={{ fontSize: '0.6875rem', color: 'text.secondary' }}>
              Committed {formatDate(selectedRun.committed_at)}
            </Typography>
          )}
        </Box>
      )}

      {currentLines.length === 0 ? (
        <Box sx={{ py: 2, textAlign: 'center' }}>
          <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary' }}>{t('payslipEmpty')}</Typography>
        </Box>
      ) : (
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 1.5, mb: 2 }}>

          {/* Earnings */}
          <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 2 }}>
            <Typography sx={{ fontSize: '0.625rem', fontWeight: 700, color: 'text.secondary', textTransform: 'uppercase', letterSpacing: '0.07em', mb: 1 }}>
              {t('payTabEarnings')}
            </Typography>
            <TableContainer>
              <Table size="small" sx={{ '& td': { border: 0 } }}>
                <TableBody>
                  {earnings.map(l => <PaylineRow key={l.id} line={l} />)}
                  {!earnings.length && (
                    <TableRow><TableCell sx={{ fontSize: '0.75rem', color: 'text.disabled' }}>—</TableCell></TableRow>
                  )}
                </TableBody>
              </Table>
            </TableContainer>
            <Divider sx={{ my: 0.75 }} />
            <Box sx={{ display: 'flex', justifyContent: 'space-between', px: 0.5 }}>
              <Typography sx={{ fontSize: '0.75rem', fontWeight: 700 }}>{t('grossTotal')}</Typography>
              <Typography sx={{ fontSize: '0.875rem', fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>
                {formatAmount(grossTotal)}
              </Typography>
            </Box>
          </Paper>

          {/* Deductions + Net */}
          <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 2 }}>
            <Typography sx={{ fontSize: '0.625rem', fontWeight: 700, color: 'text.secondary', textTransform: 'uppercase', letterSpacing: '0.07em', mb: 1 }}>
              {t('payTabDeductions')}
            </Typography>
            <TableContainer>
              <Table size="small" sx={{ '& td': { border: 0 } }}>
                <TableBody>
                  {deductions.map(l => <PaylineRow key={l.id} line={l} secondary />)}
                  {!deductions.length && (
                    <TableRow><TableCell sx={{ fontSize: '0.75rem', color: 'text.disabled' }}>—</TableCell></TableRow>
                  )}
                </TableBody>
              </Table>
            </TableContainer>
            <Divider sx={{ my: 0.75 }} />
            <Box sx={{ display: 'flex', justifyContent: 'space-between', px: 0.5 }}>
              <Typography sx={{ fontSize: '0.75rem', fontWeight: 700 }}>{t('netTotal')}</Typography>
              <Typography sx={{ fontSize: '0.875rem', fontWeight: 700, color: 'primary.main', fontVariantNumeric: 'tabular-nums' }}>
                {formatAmount(netTotal)}
              </Typography>
            </Box>
          </Paper>

        </Box>
      )}

      {/* Payroll history mini-table */}
      {myRuns.length > 1 && (
        <>
          <Typography sx={{ fontSize: '0.875rem', fontWeight: 600, mb: 0.75 }}>{t('payTabHistory')}</Typography>
          <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 2 }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  {[t('colPeriodStart'), t('colPeriodEnd'), t('colStatus')].map(h => (
                    <TableCell key={h} sx={{ fontWeight: 700, fontSize: '0.625rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'text.secondary', py: 0.75 }}>
                      {h}
                    </TableCell>
                  ))}
                </TableRow>
              </TableHead>
              <TableBody>
                {myRuns.map(r => (
                  <TableRow
                    key={r.id}
                    hover
                    selected={String(r.id) === selectedRunId}
                    onClick={() => setSelectedRunId(String(r.id))}
                    sx={{ cursor: 'pointer' }}
                  >
                    <TableCell sx={{ fontSize: '0.75rem', fontVariantNumeric: 'tabular-nums', py: 0.5 }}>{formatDate(r.period_start)}</TableCell>
                    <TableCell sx={{ fontSize: '0.75rem', fontVariantNumeric: 'tabular-nums', py: 0.5 }}>{formatDate(r.period_end)}</TableCell>
                    <TableCell sx={{ py: 0.5 }}>
                      <Chip
                        size="small"
                        label={statusLabelKey(r.status) ? t(statusLabelKey(r.status)) : r.status}
                        color={statusColor(r.status)}
                        variant="outlined"
                        sx={{ height: 16, fontSize: '0.5625rem' }}
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </>
      )}

    </Box>
  );
}
