// src/apps/people/LoansPage.jsx
// People & Payroll — Loans (full CRUD) with a read-only installments expander.
// All colours via theme tokens; apiFetch only; SystemDialog for the form.

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Autocomplete,
  Box,
  Button,
  Chip,
  IconButton,
  MenuItem,
  Snackbar,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import AccountBalanceWalletIcon from '@mui/icons-material/AccountBalanceWallet';
import AddIcon from '@mui/icons-material/Add';
import VisibilityRounded from '@mui/icons-material/VisibilityRounded';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../components/Page/ErrorAlert';
import SystemDialog from '../../components/SystemDialog';
import FilteredDataGrid from '../../components/FilteredDataGrid';
import StandardDataGrid from '../../components/StandardDataGrid';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useReferenceOptions } from '../../hooks/useReferenceOptions';
import { useAuth } from '../../auth/AuthContext';
import {
  fetchLoans,
  fetchLoanInstallments,
  createLoan,
  updateLoan,
} from '../../api/people';
import { labelsFromRows, formatAmount, formatDate, refCode, refLabel } from './utils';
import EmployeePicker from './EmployeePicker';

const LOAN_STATUSES = ['active', 'paid_off', 'cancelled'];

const EMPTY_FORM = {
  employee: '',
  loan_type: '',
  principal: '',
  interest_rate: '0',
  term_months: '',
  start_date: '',
  status: 'active',
  notes: '',
};

/** MUI Chip color for a loan status value. */
function loanStatusColor(status) {
  switch (status) {
    case 'active':
      return 'success';
    case 'paid_off':
      return 'info';
    case 'cancelled':
      return 'warning';
    default:
      return 'default';
  }
}

/** MUI Chip color for an installment status value. */
function installmentStatusColor(status) {
  switch (status) {
    case 'paid':
      return 'success';
    case 'scheduled':
      return 'info';
    case 'skipped':
      return 'warning';
    default:
      return 'default';
  }
}

export default function LoansPage() {
  const { t } = useTranslation('people');
  const navigate = useNavigate();
  const { t: tCommon } = useTranslation('common');
  useDocumentTitle(t('loansTitle'));
  const { token } = useAuth();
  const loanTypeRef = useReferenceOptions('loan_type');

  const [loans, setLoans] = useState([]);
  const [employeeLabels, setEmployeeLabels] = useState({});
  const [installments, setInstallments] = useState([]);
  const [installmentsLoading, setInstallmentsLoading] = useState(true);
  const [installmentsError, setInstallmentsError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [openDialog, setOpenDialog] = useState(false);
  const [editingLoan, setEditingLoan] = useState(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [expandedLoanId, setExpandedLoanId] = useState(null);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });
  const [searchValue, setSearchValue] = useState('');
  const [gridFilters, setGridFilters] = useState({ status: '' });

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const loansData = await fetchLoans(token);
      const loanList = Array.isArray(loansData) ? loansData : loansData?.results || [];
      setLoans(loanList);
      setEmployeeLabels(labelsFromRows(loanList));
    } catch (err) {
      setError(err?.message || t('loansLoadError'));
    } finally {
      setLoading(false);
    }
  }, [token, t]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const loadInstallments = useCallback(async () => {
    try {
      setInstallmentsLoading(true);
      setInstallmentsError(null);
      const data = await fetchLoanInstallments(token);
      setInstallments(Array.isArray(data) ? data : data?.results || []);
    } catch (err) {
      setInstallmentsError(err?.message || t('loanInstallmentsLoadError'));
    } finally {
      setInstallmentsLoading(false);
    }
  }, [token, t]);

  useEffect(() => {
    loadInstallments();
  }, [loadInstallments]);

  const employeeName = (id) => employeeLabels[id] ?? id ?? '—';

  const loanStatusLabel = (status) => {
    switch (status) {
      case 'active':
        return t('statusActive');
      case 'paid_off':
        return t('statusPaidOff');
      case 'cancelled':
        return t('statusCancelled');
      default:
        return status ?? '—';
    }
  };

  const installmentStatusLabel = (status) => {
    switch (status) {
      case 'scheduled':
        return t('statusScheduled');
      case 'paid':
        return t('statusPaid');
      case 'skipped':
        return t('statusSkipped');
      default:
        return status ?? '—';
    }
  };

  const loanInstallments = (loanId) => installments.filter((inst) => inst.loan === loanId);

  const openCreate = () => {
    setEditingLoan(null);
    setForm({ ...EMPTY_FORM });
    setOpenDialog(true);
  };

  const closeDialog = () => {
    setOpenDialog(false);
    setEditingLoan(null);
  };

  const handleChange = (event) => {
    const { name, value } = event.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleSave = async () => {
    if (
      !form.employee ||
      !form.loan_type.trim() ||
      !String(form.principal).trim() ||
      !String(form.term_months).trim() ||
      !form.start_date
    ) {
      setSnackbar({ open: true, message: tCommon('allFieldsRequired'), severity: 'error' });
      return;
    }

    const payload = {
      employee: Number(form.employee),
      loan_type: form.loan_type.trim(),
      principal: String(form.principal).trim(),
      interest_rate: String(form.interest_rate).trim() || '0',
      term_months: Number(form.term_months),
      start_date: form.start_date,
      status: form.status || 'active',
    };
    if (form.notes && form.notes.trim()) {
      payload.notes = form.notes.trim();
    }

    setSaving(true);
    try {
      if (editingLoan) {
        await updateLoan(editingLoan.id, payload, token);
      } else {
        await createLoan(payload, token);
      }
      closeDialog();
      setSnackbar({ open: true, message: t('loanSaved'), severity: 'success' });
      // Reload loans + installments — approve→active materializes schedule (NSR-3A).
      await Promise.all([loadData(), loadInstallments()]);
    } catch (err) {
      setSnackbar({
        open: true,
        message: err?.message || err?.feedback?.title || err?.detail || t('actionError'),
        severity: 'error',
      });
    } finally {
      setSaving(false);
    }
  };

  const closeSnackbar = () => setSnackbar((prev) => ({ ...prev, open: false }));

  const filteredLoans = useMemo(() => {
    const q = searchValue.trim().toLowerCase();
    return loans.filter((loan) => {
      if (gridFilters.status && loan.status !== gridFilters.status) return false;
      if (!q) return true;
      const hay = [
        employeeName(loan.employee),
        refLabel(loan.loan_type),
        refCode(loan.loan_type),
        formatAmount(loan.principal),
        loan.interest_rate,
        loan.term_months,
        formatDate(loan.start_date),
        loanStatusLabel(loan.status),
        loan.notes,
      ].join(' ').toLowerCase();
      return hay.includes(q);
    });
  }, [loans, searchValue, gridFilters, employeeLabels, t]);

  const filterDefs = useMemo(() => [
    {
      key: 'status',
      label: t('filterStatus'),
      emptyLabel: t('filterAll'),
      options: LOAN_STATUSES.map((value) => ({ value, label: loanStatusLabel(value) })),
    },
  ], [t]);

  const loanColumns = useMemo(() => [
    {
      field: 'employee',
      headerName: t('colEmployee'),
      flex: 1,
      minWidth: 160,
      valueGetter: (value) => employeeName(value),
    },
    {
      field: 'loan_type',
      headerName: t('colLoanType'),
      width: 150,
      valueGetter: (value) => refLabel(value) || refCode(value) || '—',
    },
    { field: 'principal', headerName: t('colPrincipal'), width: 130, valueGetter: (value) => formatAmount(value) },
    {
      field: 'interest_rate',
      headerName: t('colInterestRate'),
      width: 120,
      valueGetter: (value) => (value != null ? `${value}%` : '—'),
    },
    { field: 'term_months', headerName: t('colTermMonths'), width: 120, valueGetter: (value) => value ?? '—' },
    { field: 'start_date', headerName: t('colStartDate'), width: 130, valueGetter: (value) => formatDate(value) },
    {
      field: 'status',
      headerName: t('colStatus'),
      width: 130,
      valueGetter: (value) => loanStatusLabel(value),
      renderCell: (params) => (
        <Chip size="small" variant="outlined" color={loanStatusColor(params.row.status)} label={params.value} />
      ),
    },
    { field: 'notes', headerName: t('colNotes'), flex: 1, minWidth: 140, valueGetter: (value) => value || '—' },
    {
      field: 'actions',
      headerName: t('colActions'),
      width: 110,
      sortable: false,
      filterable: false,
      renderCell: (params) => {
        const loan = params.row;
        const label = t('requestView');
        return (
          <Tooltip title={label}>
            <IconButton
              size="small"
              color="primary"
              aria-label={label}
              onClick={(event) => {
                event.stopPropagation();
                if (loan.correspondence_id) {
                  navigate(`/team/${loan.correspondence_id}`, { state: { from: 'people-loans' } });
                } else {
                  navigate(`/people/loans/${loan.id}`);
                }
              }}
            >
              <VisibilityRounded fontSize="small" />
            </IconButton>
          </Tooltip>
        );
      },
    },
  ], [t, employeeLabels, navigate]);

  const installmentColumns = useMemo(() => [
    { field: 'installment_no', headerName: t('colInstallmentNo'), width: 130, valueGetter: (value) => value ?? '—' },
    { field: 'due_date', headerName: t('colDueDate'), width: 140, valueGetter: (value) => formatDate(value) },
    { field: 'amount', headerName: t('colAmount'), width: 130, valueGetter: (value) => formatAmount(value) },
    { field: 'principal_portion', headerName: t('colPrincipalPortion'), width: 150, valueGetter: (value) => formatAmount(value) },
    { field: 'interest_portion', headerName: t('colInterestPortion'), width: 150, valueGetter: (value) => formatAmount(value) },
    {
      field: 'status',
      headerName: t('colStatus'),
      width: 130,
      valueGetter: (value) => installmentStatusLabel(value),
      renderCell: (params) => (
        <Chip size="small" variant="outlined" color={installmentStatusColor(params.row.status)} label={params.value} />
      ),
    },
  ], [t]);

  return (
    <PageContainer>
      <PageHeader
        icon={AccountBalanceWalletIcon}
        title={t('loansTitle')}
        subtitle={t('loansSubtitle')}
        description={t('loansDescription')}
        actions={
          <Button variant="contained" size="small" startIcon={<AddIcon />} onClick={openCreate}>
            {t('actionAddLoan')}
          </Button>
        }
      />

      {loading ? (
        <LoadingSkeleton variant="console" />
      ) : error ? (
        <ErrorAlert message={error} onRetry={loadData} />
      ) : (
        <Stack spacing={2}>
          <FilteredDataGrid
            embedded
            rows={filteredLoans}
            columns={loanColumns}
            searchValue={searchValue}
            onSearchChange={setSearchValue}
            filterDefs={filterDefs}
            filterValues={gridFilters}
            onFilterChange={(key, value) => setGridFilters((prev) => ({ ...prev, [key]: value }))}
            onClearFilters={() => {
              setSearchValue('');
              setGridFilters({ status: '' });
            }}
            emptyMessage={t('loansEmpty')}
            emptySubtext={t('loansEmptyDesc')}
            pageSize={25}
            height={520}
            onRowClick={(params) => setExpandedLoanId((prev) => (prev === params.row.id ? null : params.row.id))}
            highlightRow={(row) => row.id === expandedLoanId}
          />
          {expandedLoanId != null && (
            <Box>
              <Typography variant="subtitle2" sx={{ mb: 1 }}>{t('colInstallments')}</Typography>
              {installmentsLoading ? (
                <LoadingSkeleton variant="table" />
              ) : installmentsError ? (
                <ErrorAlert message={installmentsError} onRetry={loadInstallments} />
              ) : loanInstallments(expandedLoanId).length === 0 ? (
                <Typography variant="body2" color="text.secondary">{t('loanInstallmentsEmpty')}</Typography>
              ) : (
                <StandardDataGrid
                  rows={loanInstallments(expandedLoanId)}
                  columns={installmentColumns}
                  pageSize={10}
                  rowsPerPageOptions={[10, 25]}
                  height={280}
                  getRowId={(row) => row.id}
                />
              )}
            </Box>
          )}
        </Stack>
      )}

      <SystemDialog
        open={openDialog}
        title={editingLoan ? t('loanEditTitle') : t('loanCreateTitle')}
        onClose={closeDialog}
        onCancel={closeDialog}
        cancelLabel={tCommon('cancel')}
        actions={
          <Button variant="contained" onClick={handleSave} disabled={saving}>
            {tCommon('save')}
          </Button>
        }
      >
        <Stack spacing={2}>
          <EmployeePicker
            token={token}
            label={t('colEmployee')}
            value={form.employee}
            initialLabel={employeeLabels[form.employee]}
            required
            onChange={(id) => setForm((prev) => ({ ...prev, employee: id || '' }))}
          />
          <Autocomplete
            size="small"
            options={loanTypeRef.options}
            value={loanTypeRef.options.find((o) => o.value === form.loan_type) || null}
            onChange={(e, v) => setForm((prev) => ({ ...prev, loan_type: v ? v.value : '' }))}
            getOptionLabel={(o) => o.label}
            isOptionEqualToValue={(a, b) => a.value === b.value}
            renderInput={(params) => (
              <TextField {...params} label={t('colLoanType')} required />
            )}
          />
          <TextField
            label={t('colPrincipal')}
            name="principal"
            value={form.principal}
            onChange={handleChange}
            fullWidth
            required
            type="number"
            inputProps={{ step: '0.01', min: '0' }}
          />
          <TextField
            label={t('colInterestRate')}
            name="interest_rate"
            value={form.interest_rate}
            onChange={handleChange}
            fullWidth
            type="number"
            inputProps={{ step: '0.01', min: '0' }}
          />
          <TextField
            label={t('colTermMonths')}
            name="term_months"
            value={form.term_months}
            onChange={handleChange}
            fullWidth
            required
            type="number"
            inputProps={{ step: '1', min: '1' }}
          />
          <TextField
            label={t('colStartDate')}
            name="start_date"
            value={form.start_date}
            onChange={handleChange}
            fullWidth
            required
            type="date"
            InputLabelProps={{ shrink: true }}
          />
          <TextField
            select
            label={t('formStatus')}
            name="status"
            value={form.status}
            onChange={handleChange}
            fullWidth
          >
            {LOAN_STATUSES.map((status) => (
              <MenuItem key={status} value={status}>{loanStatusLabel(status)}</MenuItem>
            ))}
          </TextField>
          <TextField
            label={t('colNotes')}
            name="notes"
            value={form.notes}
            onChange={handleChange}
            fullWidth
            multiline
            minRows={2}
          />
        </Stack>
      </SystemDialog>

      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={closeSnackbar}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert severity={snackbar.severity} variant="filled" sx={{ width: '100%' }}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </PageContainer>
  );
}
