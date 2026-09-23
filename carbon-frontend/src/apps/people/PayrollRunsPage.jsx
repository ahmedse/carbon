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
import SystemDialog from '../../components/SystemDialog';
import { SearchSelect } from '../../components/Form';
import FilteredDataGrid from '../../components/FilteredDataGrid';
import StandardDataGrid from '../../components/StandardDataGrid';
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
  const { token, user } = useAuth();
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
  const [searchValue, setSearchValue] = useState('');
  const [gridFilters, setGridFilters] = useState({ status: '', org_unit: '' });

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

  const filteredRuns = useMemo(() => {
    const q = searchValue.trim().toLowerCase();
    return runs.filter((run) => {
      if (gridFilters.status && run.status !== gridFilters.status) return false;
      if (gridFilters.org_unit && String(run.org_unit) !== String(gridFilters.org_unit)) return false;
      if (!q) return true;
      const statusKey = statusLabelKey(run.status);
      const hay = [
        run.id,
        run.period_start,
        run.period_end,
        formatDate(run.period_start),
        formatDate(run.period_end),
        orgUnitName(run.org_unit),
        run.preparer_username,
        run.status,
        statusKey ? t(statusKey) : '',
      ].join(' ').toLowerCase();
      return hay.includes(q);
    });
  }, [runs, searchValue, gridFilters, t, orgUnitById, orgUnits]);

  const filterDefs = useMemo(() => [
    {
      key: 'status',
      label: t('filterStatus'),
      emptyLabel: t('filterAll'),
      options: ['draft', 'computed', 'validated', 'committed', 'failed'].map((value) => ({
        value,
        label: t(statusLabelKey(value)),
      })),
    },
    {
      key: 'org_unit',
      label: t('colOrgUnit'),
      emptyLabel: t('filterAll'),
      options: orgUnitsForPicker.map((unit) => ({
        value: String(unit.id),
        label: unit.full_path || unit.name || unit.code || String(unit.id),
      })),
    },
  ], [t, orgUnitsForPicker]);

  const runColumns = useMemo(() => [
    { field: 'period_start', headerName: t('colPeriodStart'), width: 130, valueFormatter: (value) => formatDate(value) },
    { field: 'period_end', headerName: t('colPeriodEnd'), width: 130, valueFormatter: (value) => formatDate(value) },
    {
      field: 'org_unit',
      headerName: t('colOrgUnit'),
      flex: 1,
      minWidth: 180,
      valueGetter: (value) => orgUnitName(value),
    },
    {
      field: 'status',
      headerName: t('colStatus'),
      width: 140,
      valueGetter: (value) => {
        const key = statusLabelKey(value);
        return key ? t(key) : value;
      },
      renderCell: (params) => (
        <Chip
          size="small"
          variant="outlined"
          color={statusColor(params.row.status)}
          label={params.value}
        />
      ),
    },
    {
      field: 'preparer_username',
      headerName: t('colPreparer'),
      width: 160,
      valueGetter: (value) => value || '',
      renderCell: (params) => (
        params.row.preparer_username ? params.row.preparer_username : (
          <Tooltip title={t('payrollPreparerNotRecorded')}>
            <span>—</span>
          </Tooltip>
        )
      ),
    },
    {
      field: 'actions',
      headerName: t('colActions'),
      width: 460,
      sortable: false,
      filterable: false,
      renderCell: (params) => {
        const run = params.row;
        return (
          <Stack direction="row" spacing={0.5} alignItems="center">
            {['compute', 'validate', 'commit'].map((action) => (
              <Button
                key={action}
                size="small"
                variant="outlined"
                disabled={
                  !ACTION_ENABLED[action](run.status)
                  || busyId === run.id
                  || (
                    action === 'commit'
                    && (
                      !run.preparer_username
                      || run.preparer_username === user?.username
                    )
                  )
                }
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
              <IconButton size="small" onClick={(event) => { event.stopPropagation(); openEdit(run); }}>
                <EditIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            <Tooltip title={t('actionDeletePayrollRun')}>
              <IconButton size="small" onClick={(event) => { event.stopPropagation(); handleDelete(run); }} sx={{ color: 'error.main' }}>
                <DeleteIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Stack>
        );
      },
    },
  ], [t, user, busyId, orgUnitById, orgUnits]);

  const validationColumns = useMemo(() => [
    { field: 'rule_key', headerName: t('colRuleKey'), flex: 1, minWidth: 160, valueGetter: (value) => value || '—' },
    {
      field: 'passed',
      headerName: t('colPassed'),
      width: 120,
      renderCell: (params) => (
        <Chip
          size="small"
          variant="outlined"
          color={params.row.passed ? 'success' : 'error'}
          label={params.row.passed ? '✓' : '✗'}
        />
      ),
    },
    { field: 'checked', headerName: t('colChecked'), width: 120, valueGetter: (value) => value ?? 0 },
    { field: 'failed', headerName: t('colFailed'), width: 120, valueGetter: (value) => value ?? 0 },
  ], [t]);

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
          <Button variant="contained" size="small" startIcon={<AddIcon />} onClick={openCreate}>
            {t('actionAddPayrollRun')}
          </Button>
        }
      />

      <Stack spacing={2}>
        <Alert severity="info">{t('payrollSodBanner')}</Alert>
        {runs.some((run) => run.status === 'committed') && (
          <Alert severity="warning">{t('wpsExportHonesty')}</Alert>
        )}
        <FilteredDataGrid
          embedded
          rows={filteredRuns}
          columns={runColumns}
          loading={false}
          searchValue={searchValue}
          onSearchChange={setSearchValue}
          filterDefs={filterDefs}
          filterValues={gridFilters}
          onFilterChange={(key, value) => setGridFilters((prev) => ({ ...prev, [key]: value }))}
          onClearFilters={() => {
            setSearchValue('');
            setGridFilters({ status: '', org_unit: '' });
          }}
          emptyMessage={t('payrollEmpty')}
          emptySubtext={t('payrollEmptyDesc')}
          pageSize={25}
          height={520}
          onRowClick={(params) => setSelectedId(params.row.id)}
          highlightRow={(row) => row.id === selectedId}
        />

        <Box>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>{t('validationsTitle')}</Typography>
          {selectedId == null ? (
            <Paper variant="outlined" sx={{ p: 2 }}>
              <Typography variant="body2" color="text.secondary">{t('selectRunPrompt')}</Typography>
            </Paper>
          ) : validationsLoading ? (
            <LoadingSkeleton variant="table" />
          ) : validationsError ? (
            <ErrorAlert message={validationsError} onRetry={() => setValidationsKey((k) => k + 1)} />
          ) : (
            <StandardDataGrid
              rows={validations}
              columns={validationColumns}
              loading={false}
              pageSize={10}
              rowsPerPageOptions={[10, 25]}
              height={280}
              getRowId={(row) => row.id}
            />
          )}
        </Box>
      </Stack>

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
