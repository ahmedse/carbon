// src/apps/people/PayslipPage.jsx
// People & Payroll — payslip lines per payroll run (read-only).

import React, { useEffect, useState } from 'react';
import {
  FormControl,
  InputLabel,
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
import ReceiptLongIcon from '@mui/icons-material/ReceiptLong';
import { useTranslation } from 'react-i18next';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../components/Page/ErrorAlert';
import EmptyState from '../../components/Page/EmptyState';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import { fetchEmployees, fetchPayrollRuns, fetchPayslipLines } from '../../api/people';
import { buildEmployeeLabels, formatAmount, formatDate } from './utils';

export default function PayslipPage() {
  const { t } = useTranslation('people');
  useDocumentTitle(t('payslipTitle'));
  const { token } = useAuth();
  const [runs, setRuns] = useState([]);
  const [employeeLabels, setEmployeeLabels] = useState({});
  const [lines, setLines] = useState([]);
  const [selectedRun, setSelectedRun] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [linesLoading, setLinesLoading] = useState(false);
  const [linesError, setLinesError] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([fetchEmployees(token), fetchPayrollRuns(token)])
      .then(([employees, runData]) => {
        setEmployeeLabels(buildEmployeeLabels(Array.isArray(employees?.results) ? employees.results : []));
        setRuns(Array.isArray(runData?.results) ? runData.results : []);
      })
      .catch((err) => setError(err?.message || t('payslipLoadError')))
      .finally(() => setLoading(false));
  }, [token, t]);

  useEffect(() => {
    setLinesLoading(true);
    setLinesError(null);
    fetchPayslipLines(selectedRun ? { payrollRun: selectedRun } : {}, token)
      .then((data) => setLines(Array.isArray(data?.results) ? data.results : []))
      .catch((err) => setLinesError(err?.message || t('payslipLoadError')))
      .finally(() => setLinesLoading(false));
  }, [selectedRun, token, t]);

  if (loading) {
    return (
      <PageContainer>
        <PageHeader icon={ReceiptLongIcon} title={t('payslipTitle')} subtitle={t('payslipSubtitle')} />
        <LoadingSkeleton variant="console" />
      </PageContainer>
    );
  }

  if (error) {
    return (
      <PageContainer>
        <PageHeader icon={ReceiptLongIcon} title={t('payslipTitle')} subtitle={t('payslipSubtitle')} />
        <ErrorAlert message={error} onRetry={() => window.location.reload()} />
      </PageContainer>
    );
  }

  const grossTotal = lines.reduce(
    (sum, line) => (line.line_type === 'gross' ? sum + Number(line.amount || 0) : sum),
    0,
  );
  const netTotal = lines.reduce(
    (sum, line) => (line.line_type === 'net' ? sum + Number(line.amount || 0) : sum),
    0,
  );

  return (
    <PageContainer>
      <PageHeader icon={ReceiptLongIcon} title={t('payslipTitle')} subtitle={t('payslipSubtitle')} />

      <Stack spacing={2}>
        <FormControl size="small" sx={{ minWidth: 240 }}>
          <InputLabel id="payslip-run-label">{t('selectPayrollRun')}</InputLabel>
          <Select
            labelId="payslip-run-label"
            label={t('selectPayrollRun')}
            value={selectedRun}
            onChange={(event) => setSelectedRun(event.target.value)}
          >
            <MenuItem value="">{t('selectAllRuns')}</MenuItem>
            {runs.map((run) => (
              <MenuItem key={run.id} value={String(run.id)}>
                {`${formatDate(run.period_start)} → ${formatDate(run.period_end)}`}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        <Stack direction="row" spacing={2}>
          <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 2, flex: 1 }}>
            <Typography sx={{ fontSize: '0.6875rem', color: 'text.secondary', textTransform: 'uppercase' }}>
              {t('grossTotal')}
            </Typography>
            <Typography sx={{ fontSize: '0.875rem', fontWeight: 600 }}>{formatAmount(grossTotal)}</Typography>
          </Paper>
          <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 2, flex: 1 }}>
            <Typography sx={{ fontSize: '0.6875rem', color: 'text.secondary', textTransform: 'uppercase' }}>
              {t('netTotal')}
            </Typography>
            <Typography sx={{ fontSize: '0.875rem', fontWeight: 600 }}>{formatAmount(netTotal)}</Typography>
          </Paper>
        </Stack>

        {linesLoading ? (
          <LoadingSkeleton variant="table" />
        ) : linesError ? (
          <ErrorAlert message={linesError} onRetry={() => window.location.reload()} />
        ) : lines.length === 0 ? (
          <EmptyState
            icon={<ReceiptLongIcon />}
            title={t('payslipEmpty')}
            description={t('payslipEmptyDesc')}
          />
        ) : (
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colEmployee')}</TableCell>
                  <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colLineType')}</TableCell>
                  <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colAmount')}</TableCell>
                  <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colRuleId')}</TableCell>
                  <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colRuleVersion')}</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {lines.map((line) => (
                  <TableRow key={line.id} hover>
                    <TableCell>{employeeLabels[line.employee] ?? line.employee ?? '—'}</TableCell>
                    <TableCell>{line.line_type ?? '—'}</TableCell>
                    <TableCell>{formatAmount(line.amount)}</TableCell>
                    <TableCell>{line.rule_id ?? '—'}</TableCell>
                    <TableCell>{line.rule_version ?? '—'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Stack>
    </PageContainer>
  );
}
