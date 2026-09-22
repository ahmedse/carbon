// src/apps/people/PayrollRunsPage.jsx
// People & Payroll — payroll runs (full CRUD + lifecycle: compute / validate / commit).

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  IconButton,
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
import PaymentsIcon from '@mui/icons-material/Payments';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import DownloadIcon from '@mui/icons-material/Download';
import { useTranslation } from 'react-i18next';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../components/Page/ErrorAlert';
import EmptyState from '../../components/Page/EmptyState';
import SystemDialog from '../../components/SystemDialog';
import { SearchSelect } from '../../components/Form';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import {
  fetchPayrollRuns,
  fetchPayrollRunValidations,
  createPayrollRun,
  updatePayrollRun,
  deletePayrollRun,
  computePayrollRun,
  validatePayrollRun,
  commitPayrollRun,
  exportWpsPayrollRun,
} from '../../api/people';
import {
  fetchOrgUnits,
  orgUnitDepth,
  orgUnitOptionLabel,
  prepareOrgUnitsForPicker,
} from '../../api/orgUnits';
import { formatDate, statusColor, statusLabelKey, isSodError, sodErrorCode } from './utils';

const ACTION_FUNCS = {
  compute: computePayrollRun,
  validate: validatePayrollRun,
  commit: commitPayrollRun,
};

const ACTION_ENABLED = {
  compute: (status) => status === 'draft',
  validate: (status) => status === 'computed',
  commit: (status) => status === 'validated',
};

const EMPTY_FORM = {
  org_unit: '',
  period_start: '',
  period_end: '',
};

/** True when compute failed because a verified ledger basic line is missing (NSR-2A). */
function isLedgerMissingError(err) {
  const msg = String(err?.message || err?.detail || err?.feedback?.detail || '').toLowerCase();
  return (
    (msg.includes('verified') && msg.includes('basic') && msg.includes('ledger'))
    || msg.includes('no verified monthly')
    || (msg.includes('compensation ledger') && msg.includes('basic'))
  );
}

/** Map host SoD codes to i18n detail keys (ADR-0045). */
function sodDetailKey(code) {
  if (code === 'sod_same_actor') return 'payrollSodSameActorDetail';
  if (code === 'sod_missing_preparer') return 'payrollSodMissingPreparerDetail';
  if (code === 'sod_missing_actor') return 'payrollSodMissingActorDetail';
  return 'payrollSodGenericDetail';
}

export default function PayrollRunsPage() {
  const { t } = useTranslation('people');
  const { t: tCommon } = useTranslation('common');
  useDocumentTitle(t('payrollTitle'));
  const { token } = useAuth();
  const [runs, setRuns] = useState([]);
  const [orgUnits, setOrgUnits] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const [snackbar, setSnackbar] = useState({ open: false, severity: 'error', message: '' });
  const [selectedId, setSelectedId] = useState(null);
  const [validations, setValidations] = useState([]);
  const [validationsLoading, setValidationsLoading] = useState(false);
  const [validationsError, setValidationsError] = useState(null);
  const [validationsKey, setValidationsKey] = useState(0);
  const [openDialog, setOpenDialog] = useState(false);
  const [editingRun, setEditingRun] = useState(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [actionError, setActionError] = useState(null);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [runsData, orgUnitsData] = await Promise.all([
        fetchPayrollRuns(token),
        fetchOrgUnits(token),
      ]);
      setRuns(Array.isArray(runsData?.results) ? runsData.results : []);
      setOrgUnits(Array.isArray(orgUnitsData) ? orgUnitsData : []);
    } catch (err) {
      setError(err?.message || t('payrollLoadError'));
    } finally {
      setLoading(false);
    }
  }, [token, t]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    if (selectedId == null) {
      setValidations([]);
      return;
    }
    setValidationsLoading(true);
    setValidationsError(null);
    fetchPayrollRunValidations(selectedId, token)
      .then((data) => setValidations(Array.isArray(data?.results) ? data.results : []))
      .catch((err) => setValidationsError(err?.message || t('validationsLoadError')))
      .finally(() => setValidationsLoading(false));
  }, [selectedId, token, t, validationsKey]);

  const orgUnitsForPicker = useMemo(
    () => prepareOrgUnitsForPicker(orgUnits),
    [orgUnits],
  );
  const orgUnitById = useMemo(() => {
    const map = new Map();
    for (const u of orgUnitsForPicker) map.set(u.id, u);
    return map;
  }, [orgUnitsForPicker]);

  const orgUnitName = (id) => {
    const unit = orgUnitById.get(id) || orgUnits.find((u) => u.id === id);
    return unit?.full_path || unit?.name || unit?.code || '—';
  };

  const openCreate = () => {
    setEditingRun(null);
    setForm({ ...EMPTY_FORM });
    setOpenDialog(true);
  };

  const openEdit = (run) => {
    setEditingRun(run);
    setForm({
      org_unit: run.org_unit ?? '',
      period_start: run.period_start ?? '',
      period_end: run.period_end ?? '',
    });
    setOpenDialog(true);
  };

  const closeDialog = () => {
    setOpenDialog(false);
    setEditingRun(null);
  };

  const handleChange = (event) => {
    const { name, value } = event.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleSave = async () => {
    if (!form.org_unit || !form.period_start || !form.period_end) {
      setSnackbar({ open: true, message: tCommon('allFieldsRequired'), severity: 'error' });
      return;
    }
    const payload = {
      org_unit: Number(form.org_unit),
      period_start: form.period_start,
      period_end: form.period_end,
    };
    setSaving(true);
    try {
      if (editingRun) {
        await updatePayrollRun(editingRun.id, payload, token);
      } else {
        await createPayrollRun(payload, token);
      }
      closeDialog();
      setSnackbar({ open: true, message: t('payrollRunSaved'), severity: 'success' });
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

  const handleDelete = async (run) => {
    if (!window.confirm(t('payrollRunDeleteConfirm'))) return;
    try {
      await deletePayrollRun(run.id, token);
      setSnackbar({ open: true, message: t('payrollRunDeleted'), severity: 'success' });
      await loadData();
    } catch (err) {
      setSnackbar({
        open: true,
        message: err?.message || err?.feedback?.title || err?.detail || t('actionError'),
        severity: 'error',
      });
    }
  };

  const handleAction = useCallback(
    (run, action) => {
      setBusyId(run.id);
      ACTION_FUNCS[action](run.id, token)
        .then(() => loadData())
        .catch((err) => {
          const apiMsg = err?.message || err?.feedback?.title || err?.detail || t('actionError');
          if (isSodError(err)) {
            setActionError({
              title: t('payrollSodTitle'),
              detail: t(sodDetailKey(sodErrorCode(err))),
              apiMsg,
            });
          } else if (action === 'compute' && isLedgerMissingError(err)) {
            setActionError({
              title: t('payrollLedgerMissingTitle'),
              detail: t('payrollLedgerMissingDetail'),
              apiMsg,
            });
          } else {
            setActionError({
              title: t('payrollActionErrorTitle'),
              detail: apiMsg,
              apiMsg,
            });
          }
        })
        .finally(() => setBusyId(null));
    },
    [token, t, loadData],
  );

  const handleWpsExport = async (run) => {
    setBusyId(run.id);
    try {
      const csv = await exportWpsPayrollRun(run.id, token);
      const blob = new Blob([csv], { type: 'text/csv' });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `wps_run_${run.id}.csv`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      setSnackbar({ open: true, message: t('wpsExportSuccess'), severity: 'success' });
    } catch (err) {
      setSnackbar({
        open: true,
        message: err?.message || err?.feedback?.title || err?.detail || t('actionError'),
        severity: 'error',
      });
    } finally {
      setBusyId(null);
    }
  };

  if (loading) {
    return (
      <PageContainer>
        <PageHeader icon={PaymentsIcon} title={t('payrollTitle')} subtitle={t('payrollSubtitle')} />
        <LoadingSkeleton variant="console" />
      </PageContainer>
    );
  }

  if (error) {
    return (
      <PageContainer>
        <PageHeader icon={PaymentsIcon} title={t('payrollTitle')} subtitle={t('payrollSubtitle')} />
        <ErrorAlert message={error} onRetry={loadData} />
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <PageHeader
        icon={PaymentsIcon}
        title={t('payrollTitle')}
        subtitle={t('payrollSubtitle')}
        actions={
          runs.length > 0 ? (
            <Button variant="contained" size="small" startIcon={<AddIcon />} onClick={openCreate}>
              {t('actionAddPayrollRun')}
            </Button>
          ) : undefined
        }
      />

      {runs.length === 0 ? (
        <EmptyState
          icon={<PaymentsIcon />}
          title={t('payrollEmpty')}
          description={t('payrollEmptyDesc')}
          actionLabel={t('actionAddPayrollRun')}
          onAction={openCreate}
        />
      ) : (
      <Stack spacing={2}>
        <TableContainer component={Paper} variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colPeriodStart')}</TableCell>
                <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colPeriodEnd')}</TableCell>
                <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colOrgUnit')}</TableCell>
                <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colStatus')}</TableCell>
                <TableCell align="right" sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colActions')}</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {runs.map((run) => {
                const statusKey = statusLabelKey(run.status);
                return (
                  <TableRow
                    key={run.id}
                    hover
                    selected={run.id === selectedId}
                    onClick={() => setSelectedId(run.id)}
                    sx={{ cursor: 'pointer' }}
                  >
                    <TableCell>{formatDate(run.period_start)}</TableCell>
                    <TableCell>{formatDate(run.period_end)}</TableCell>
                    <TableCell>{orgUnitName(run.org_unit)}</TableCell>
                    <TableCell>
                      <Chip
                        size="small"
                        variant="outlined"
                        color={statusColor(run.status)}
                        label={statusKey ? t(statusKey) : run.status}
                      />
                    </TableCell>
                    <TableCell align="right">
                      <Stack direction="row" spacing={0.5} justifyContent="flex-end" alignItems="center">
                        {['compute', 'validate', 'commit'].map((action) => (
                          <Button
                            key={action}
                            size="small"
                            variant="outlined"
                            disabled={!ACTION_ENABLED[action](run.status) || busyId === run.id}
                            onClick={(event) => {
                              event.stopPropagation();
                              handleAction(run, action);
                            }}
                          >
                            {t(`action${action.charAt(0).toUpperCase()}${action.slice(1)}`)}
                          </Button>
                        ))}
                        {run.status === 'committed' && (
                          <Button
                            size="small"
                            variant="outlined"
                            color="info"
                            startIcon={<DownloadIcon />}
                            disabled={busyId === run.id}
                            onClick={(event) => {
                              event.stopPropagation();
                              handleWpsExport(run);
                            }}
                          >
                            {t('actionExportWps')}
                          </Button>
                        )}
                        <Tooltip title={t('actionEditPayrollRun')}>
                          <IconButton
                            size="small"
                            onClick={(event) => {
                              event.stopPropagation();
                              openEdit(run);
                            }}
                            sx={{ color: 'primary.main' }}
                          >
                            <EditIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title={t('actionDeletePayrollRun')}>
                          <IconButton
                            size="small"
                            onClick={(event) => {
                              event.stopPropagation();
                              handleDelete(run);
                            }}
                            sx={{ color: 'error.main' }}
                          >
                            <DeleteIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      </Stack>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>

        <Box>
          <Typography sx={{ fontSize: '0.8125rem', fontWeight: 600, mb: 1 }}>{t('validationsTitle')}</Typography>
          {selectedId == null ? (
            <Paper variant="outlined" sx={{ p: 2, fontSize: '0.8125rem', color: 'text.secondary' }}>
              {t('selectRunPrompt')}
            </Paper>
          ) : validationsLoading ? (
            <LoadingSkeleton variant="table" />
          ) : validationsError ? (
            <ErrorAlert message={validationsError} onRetry={() => setValidationsKey((k) => k + 1)} />
          ) : validations.length === 0 ? (
            <EmptyState
              icon={<PaymentsIcon />}
              title={t('noValidations')}
              description={t('noValidationsDesc')}
            />
          ) : (
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colRuleKey')}</TableCell>
                    <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colPassed')}</TableCell>
                    <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colChecked')}</TableCell>
                    <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colFailed')}</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {validations.map((validation) => (
                    <TableRow key={validation.id} hover>
                      <TableCell>{validation.rule_key ?? '—'}</TableCell>
                      <TableCell>
                        <Chip
                          size="small"
                          variant="outlined"
                          color={validation.passed ? 'success' : 'error'}
                          label={validation.passed ? '✓' : '✗'}
                        />
                      </TableCell>
                      <TableCell>{validation.checked ?? 0}</TableCell>
                      <TableCell>{validation.failed ?? 0}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </Box>
      </Stack>
      )}

      <SystemDialog
        open={openDialog}
        title={editingRun ? t('payrollRunEditTitle') : t('payrollRunCreateTitle')}
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
          <SearchSelect
            options={orgUnitsForPicker}
            valueKey="id"
            labelKey="name"
            getOptionLabel={(o) =>
              orgUnitOptionLabel(o, {
                depth: orgUnitDepth(o, orgUnitById),
                preferPath: Boolean(o?.full_path),
              })
            }
            label={t('formOrgUnit')}
            value={form.org_unit}
            onChange={(v) => setForm((prev) => ({ ...prev, org_unit: v ? v.id : '' }))}
            required
            noOptionsText={t('noOrgUnits') || 'No org units available'}
          />
          <TextField
            type="date"
            label={t('colPeriodStart')}
            name="period_start"
            value={form.period_start}
            onChange={handleChange}
            InputLabelProps={{ shrink: true }}
            fullWidth
            required
          />
          <TextField
            type="date"
            label={t('colPeriodEnd')}
            name="period_end"
            value={form.period_end}
            onChange={handleChange}
            InputLabelProps={{ shrink: true }}
            fullWidth
            required
          />
        </Stack>
      </SystemDialog>

      <SystemDialog
        open={Boolean(actionError)}
        title={actionError?.title || t('payrollActionErrorTitle')}
        onClose={() => setActionError(null)}
        onCancel={() => setActionError(null)}
        cancelLabel={tCommon('close')}
        showCancel={false}
        actions={
          <Button variant="contained" onClick={() => setActionError(null)}>
            {tCommon('close')}
          </Button>
        }
      >
        <Stack spacing={1.5}>
          <Alert severity="error" role="alert">
            {actionError?.detail}
          </Alert>
          {actionError?.apiMsg && actionError.apiMsg !== actionError.detail && (
            <Typography variant="body2" color="text.secondary" dir="ltr">
              {actionError.apiMsg}
            </Typography>
          )}
        </Stack>
      </SystemDialog>

      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={() => setSnackbar((s) => ({ ...s, open: false }))}
      >
        <Alert
          severity={snackbar.severity}
          variant="filled"
          onClose={() => setSnackbar((s) => ({ ...s, open: false }))}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </PageContainer>
  );
}
