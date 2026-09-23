// src/apps/people/PayslipPage.jsx
// People & Payroll — payslip lines per payroll run (read-only).

import React, { useEffect, useMemo, useState } from 'react';
import {
  Paper,
  Stack,
  Typography,
} from '@mui/material';
import ReceiptLongIcon from '@mui/icons-material/ReceiptLong';
import { useTranslation } from 'react-i18next';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../components/Page/ErrorAlert';
import { SearchSelect } from '../../components/Form';
import FilteredDataGrid from '../../components/FilteredDataGrid';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import { fetchPayrollRuns, fetchPayslipLines } from '../../api/people';
import { formatAmount, formatDate } from './utils';

export default function PayslipPage() {
  const { t } = useTranslation('people');
  useDocumentTitle(t('payslipTitle'));
  const { token } = useAuth();
  const [runs, setRuns] = useState([]);
  const [lines, setLines] = useState([]);
  const [selectedRun, setSelectedRun] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [linesLoading, setLinesLoading] = useState(false);
  const [linesError, setLinesError] = useState(null);
  const [searchValue, setSearchValue] = useState('');
  const [lineType, setLineType] = useState('');

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetchPayrollRuns(token)
      .then((runData) => {
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

  const lineLabel = (line) => (
    line.employee_no || line.employee_name
      ? `${line.employee_no ?? '—'} — ${line.employee_name ?? ''}`
      : (line.employee ?? '—')
  );

  const lineTypeOptions = useMemo(
    () => [...new Set(lines.map((line) => line.line_type).filter(Boolean))],
    [lines],
  );

  const filteredLines = useMemo(() => {
    const q = searchValue.trim().toLowerCase();
    return lines.filter((line) => {
      if (lineType && line.line_type !== lineType) return false;
      if (!q) return true;
      const hay = [
        lineLabel(line),
        line.line_type,
        formatAmount(line.amount),
        line.rule_id,
        line.rule_version,
      ].join(' ').toLowerCase();
      return hay.includes(q);
    });
  }, [lines, searchValue, lineType]);

  const filterDefs = useMemo(() => [
    {
      key: 'line_type',
      label: t('colLineType'),
      emptyLabel: t('filterAll'),
      options: lineTypeOptions.map((value) => ({ value, label: value })),
    },
  ], [t, lineTypeOptions]);

  const columns = useMemo(() => [
    {
      field: 'employee',
      headerName: t('colEmployee'),
      flex: 1,
      minWidth: 200,
      valueGetter: (_value, row) => lineLabel(row),
    },
    { field: 'line_type', headerName: t('colLineType'), width: 140, valueGetter: (value) => value || '—' },
    {
      field: 'amount',
      headerName: t('colAmount'),
      width: 140,
      valueGetter: (value) => formatAmount(value),
    },
    { field: 'rule_id', headerName: t('colRuleId'), width: 140, valueGetter: (value) => value ?? '—' },
    { field: 'rule_version', headerName: t('colRuleVersion'), width: 140, valueGetter: (value) => value ?? '—' },
  ], [t]);

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
        <SearchSelect
          options={runs}
          valueKey="id"
          labelKey="id"
          getOptionLabel={(run) => `${formatDate(run.period_start)} → ${formatDate(run.period_end)}`}
          label={t('selectPayrollRun')}
          value={selectedRun === '' ? null : Number(selectedRun)}
          clearable
          onChange={(run) => {
            setSelectedRun(run ? String(run.id) : '');
            setSearchValue('');
            setLineType('');
          }}
        />

        <Stack direction="row" spacing={2}>
          <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 2, flex: 1 }}>
            <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase' }}>
              {t('grossTotal')}
            </Typography>
            <Typography variant="subtitle1">{formatAmount(grossTotal)}</Typography>
          </Paper>
          <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 2, flex: 1 }}>
            <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase' }}>
              {t('netTotal')}
            </Typography>
            <Typography variant="subtitle1">{formatAmount(netTotal)}</Typography>
          </Paper>
        </Stack>

        {linesLoading ? (
          <LoadingSkeleton variant="table" />
        ) : linesError ? (
          <ErrorAlert message={linesError} onRetry={() => window.location.reload()} />
        ) : (
          <FilteredDataGrid
            embedded
            rows={filteredLines}
            columns={columns}
            searchValue={searchValue}
            onSearchChange={setSearchValue}
            filterDefs={filterDefs}
            filterValues={{ line_type: lineType }}
            onFilterChange={(key, value) => {
              if (key === 'line_type') setLineType(value || '');
            }}
            onClearFilters={() => {
              setSearchValue('');
              setLineType('');
            }}
            emptyMessage={t('payslipEmpty')}
            emptySubtext={t('payslipEmptyDesc')}
            pageSize={25}
            height={520}
          />
        )}
      </Stack>
    </PageContainer>
  );
}
