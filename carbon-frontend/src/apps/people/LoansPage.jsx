// src/apps/people/LoansPage.jsx
// People & Payroll — Loans (full CRUD) with a read-only installments expander.
// All colours via theme tokens; apiFetch only; SystemDialog for the form.

import React, { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  Collapse,
  IconButton,
  MenuItem,
  Paper,
  Snackbar,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import AccountBalanceWalletIcon from '@mui/icons-material/AccountBalanceWallet';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import { useTranslation } from 'react-i18next';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../components/Page/ErrorAlert';
import EmptyState from '../../components/Page/EmptyState';
import SystemDialog from '../../components/SystemDialog';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import {
  fetchLoans,
  fetchLoanInstallments,
  fetchEmployees,
  createLoan,
  updateLoan,
  deleteLoan,
} from '../../api/people';
import { buildEmployeeLabels, formatAmount, formatDate } from './utils';

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
  const { t: tCommon } = useTranslation('common');
  useDocumentTitle(t('loansTitle'));
  const { token } = useAuth();

  const [loans, setLoans] = useState([]);
  const [employees, setEmployees] = useState([]);
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

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [loansData, employeesData] = await Promise.all([
        fetchLoans(token),
        fetchEmployees(token),
      ]);
      const loanList = Array.isArray(loansData) ? loansData : loansData?.results || [];
      const employeeList = Array.isArray(employeesData) ? employeesData : employeesData?.results || [];
      setLoans(loanList);
      setEmployees(employeeList);
      setEmployeeLabels(buildEmployeeLabels(employeeList));
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

  const openEdit = (loan) => {
    setEditingLoan(loan);
    setForm({
      employee: loan.employee ?? '',
      loan_type: loan.loan_type ?? '',
      principal: loan.principal != null ? String(loan.principal) : '',
      interest_rate: loan.interest_rate != null ? String(loan.interest_rate) : '0',
      term_months: loan.term_months != null ? String(loan.term_months) : '',
      start_date: loan.start_date ? String(loan.start_date).slice(0, 10) : '',
      status: loan.status ?? 'active',
      notes: loan.notes ?? '',
    });
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
      await loadData();
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

  const handleDelete = async (loan) => {
    if (!window.confirm(t('loanDeleteConfirm'))) return;
    try {
      await deleteLoan(loan.id, token);
      if (expandedLoanId === loan.id) {
        setExpandedLoanId(null);
      }
      setSnackbar({ open: true, message: t('loanDeleted'), severity: 'success' });
      await loadData();
    } catch (err) {
      // DELETE 400 from the backend delete_guard carries { detail } — surface it.
      setSnackbar({
        open: true,
        message: err?.message || err?.feedback?.title || err?.detail || t('loanDeleteBlocked'),
        severity: 'error',
      });
    }
  };

  const toggleExpand = (loanId) => {
    setExpandedLoanId((prev) => (prev === loanId ? null : loanId));
  };

  const closeSnackbar = () => setSnackbar((prev) => ({ ...prev, open: false }));

  const renderInstallments = (loan) => {
    const rows = loanInstallments(loan.id);
    if (installmentsLoading) {
      return (
        <Typography sx={{ color: 'text.secondary', fontSize: '0.8125rem', p: 2 }}>
          {t('loading')}
        </Typography>
      );
    }
    if (installmentsError) {
      return <ErrorAlert message={installmentsError} onRetry={loadInstallments} />;
    }
    if (rows.length === 0) {
      return (
        <Typography sx={{ color: 'text.secondary', fontSize: '0.8125rem', p: 2 }}>
          {t('loanInstallmentsEmpty')}
        </Typography>
      );
    }
    return (
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colInstallmentNo')}</TableCell>
            <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colDueDate')}</TableCell>
            <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colAmount')}</TableCell>
            <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colPrincipalPortion')}</TableCell>
            <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colInterestPortion')}</TableCell>
            <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colStatus')}</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((inst) => (
            <TableRow key={inst.id} hover>
              <TableCell>{inst.installment_no ?? '—'}</TableCell>
              <TableCell>{formatDate(inst.due_date)}</TableCell>
              <TableCell>{formatAmount(inst.amount)}</TableCell>
              <TableCell>{formatAmount(inst.principal_portion)}</TableCell>
              <TableCell>{formatAmount(inst.interest_portion)}</TableCell>
              <TableCell>
                <Chip
                  size="small"
                  variant="outlined"
                  color={installmentStatusColor(inst.status)}
                  label={installmentStatusLabel(inst.status)}
                />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    );
  };

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
      ) : loans.length === 0 ? (
        <EmptyState
          icon={<AccountBalanceWalletIcon />}
          title={t('loansEmpty')}
          description={t('loansEmptyDesc')}
          actionLabel={t('actionAddLoan')}
          onAction={openCreate}
        />
      ) : (
        <TableContainer component={Paper} variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colInstallments')}</TableCell>
                <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colEmployee')}</TableCell>
                <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colLoanType')}</TableCell>
                <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colPrincipal')}</TableCell>
                <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colInterestRate')}</TableCell>
                <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colTermMonths')}</TableCell>
                <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colStartDate')}</TableCell>
                <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colStatus')}</TableCell>
                <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colNotes')}</TableCell>
                <TableCell align="right" sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colActions')}</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {loans.map((loan) => (
                <React.Fragment key={loan.id}>
                  <TableRow hover>
                    <TableCell>
                      <Tooltip title={t('actionViewInstallments')}>
                        <IconButton size="small" onClick={() => toggleExpand(loan.id)} sx={{ color: 'primary.main' }}>
                          {expandedLoanId === loan.id ? <KeyboardArrowUpIcon fontSize="small" /> : <KeyboardArrowDownIcon fontSize="small" />}
                        </IconButton>
                      </Tooltip>
                    </TableCell>
                    <TableCell>{employeeName(loan.employee)}</TableCell>
                    <TableCell>{loan.loan_type ?? '—'}</TableCell>
                    <TableCell>{formatAmount(loan.principal)}</TableCell>
                    <TableCell>{loan.interest_rate != null ? `${loan.interest_rate}%` : '—'}</TableCell>
                    <TableCell>{loan.term_months ?? '—'}</TableCell>
                    <TableCell>{formatDate(loan.start_date)}</TableCell>
                    <TableCell>
                      <Chip
                        size="small"
                        variant="outlined"
                        color={loanStatusColor(loan.status)}
                        label={loanStatusLabel(loan.status)}
                      />
                    </TableCell>
                    <TableCell>{loan.notes || '—'}</TableCell>
                    <TableCell align="right">
                      <Tooltip title={t('actionEditLoan')}>
                        <IconButton size="small" onClick={() => openEdit(loan)} sx={{ color: 'primary.main' }}>
                          <EditIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title={t('actionDeleteLoan')}>
                        <IconButton size="small" onClick={() => handleDelete(loan)} sx={{ color: 'error.main' }}>
                          <DeleteIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell sx={{ p: 0 }} colSpan={10}>
                      <Collapse in={expandedLoanId === loan.id} timeout="auto" unmountOnExit>
                        <Box sx={{ p: 2, bgcolor: 'action.hover' }}>
                          <Typography variant="subtitle2" sx={{ mb: 1, color: 'text.secondary' }}>
                            {t('colInstallments')}
                          </Typography>
                          {renderInstallments(loan)}
                        </Box>
                      </Collapse>
                    </TableCell>
                  </TableRow>
                </React.Fragment>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
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
          <TextField
            select
            label={t('colEmployee')}
            name="employee"
            value={form.employee}
            onChange={handleChange}
            fullWidth
            required
          >
            <MenuItem value="" disabled>{t('colEmployee')}</MenuItem>
            {employees.map((employee) => (
              <MenuItem key={employee.id} value={employee.id}>
                {employee.employee_no ?? '—'} — {employee.full_name ?? ''}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            label={t('colLoanType')}
            name="loan_type"
            value={form.loan_type}
            onChange={handleChange}
            fullWidth
            required
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
