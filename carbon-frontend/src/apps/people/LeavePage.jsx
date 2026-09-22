// src/apps/people/LeavePage.jsx
// People & Payroll — Leave records + entitlements.
// People Leave is HR ops (records + entitlements). Approve/reject is Team /
// Correspondence only (NSR leave spine) — no parallel status PATCH here.

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  IconButton,
  Snackbar,
  Stack,
  Tab,
  Tabs,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import { useTranslation } from 'react-i18next';
import FilteredDataGrid from '../../components/FilteredDataGrid';
import SystemDialog from '../../components/SystemDialog';
import ConfirmDialog from '../../components/ConfirmDialog';
import { SearchSelect } from '../../components/Form';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useReferenceOptions } from '../../hooks/useReferenceOptions';
import { useAuth } from '../../auth/AuthContext';
import {
  fetchEmployees,
  fetchLeaveRecords,
  fetchLeaveEntitlements,
  createLeaveRecord,
  updateLeaveRecord,
  deleteLeaveRecord,
  createLeaveEntitlement,
  updateLeaveEntitlement,
  deleteLeaveEntitlement,
} from '../../api/people';
import { formatDate, statusColor, statusLabelKey } from './utils';

const EMPTY_RECORD = {
  employee: '',
  leave_type: '',
  start_date: '',
  end_date: '',
  days: '',
  status: 'draft',
};

const EMPTY_ENT = {
  employee: '',
  year: String(new Date().getFullYear()),
  leave_type: '',
  entitled_days: '',
  used_days: '0',
  carried_forward: '0',
  notes: '',
};

const LEAVE_STATUSES = ['draft', 'submitted', 'approved', 'rejected', 'cancelled'];

function employeeLabel(row) {
  if (!row) return '—';
  const name = row.employee_name || row.full_name;
  const no = row.employee_no;
  if (name && no) return `${name} (${no})`;
  return name || no || String(row.employee ?? row.id ?? '—');
}

export default function LeavePage() {
  const { t } = useTranslation('people');
  const { t: tCommon } = useTranslation('common');
  useDocumentTitle(t('leaveTitle'));
  const { token } = useAuth();
  const leaveTypes = useReferenceOptions('leave_type');

  const [tab, setTab] = useState(0);
  const [records, setRecords] = useState([]);
  const [entitlements, setEntitlements] = useState([]);
  const [employeeOptions, setEmployeeOptions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [recordDialogOpen, setRecordDialogOpen] = useState(false);
  const [editingRecord, setEditingRecord] = useState(null);
  const [recordForm, setRecordForm] = useState({ ...EMPTY_RECORD });

  const [entDialogOpen, setEntDialogOpen] = useState(false);
  const [editingEnt, setEditingEnt] = useState(null);
  const [entForm, setEntForm] = useState({ ...EMPTY_ENT });

  const [saving, setSaving] = useState(false);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });
  const [deleteTarget, setDeleteTarget] = useState(null);

  const [recordSearch, setRecordSearch] = useState('');
  const [recordFilters, setRecordFilters] = useState({ status: '' });
  const [entSearch, setEntSearch] = useState('');
  const [entFilters, setEntFilters] = useState({
    year: String(new Date().getFullYear()),
    leave_type: '',
  });

  const loadPickerEmployees = useCallback(async () => {
    if (!token) return;
    try {
      // One page is enough for SearchSelect local filter; avoids walking 555+.
      const data = await fetchEmployees(token, { page: 1, page_size: 200 });
      const list = Array.isArray(data) ? data : data?.results || [];
      setEmployeeOptions(
        list.map((e) => ({
          value: e.id,
          label: employeeLabel(e),
        })),
      );
    } catch {
      /* picker failure is non-fatal — grid still works via embedded names */
    }
  }, [token]);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const year = entFilters.year ? Number(entFilters.year) : new Date().getFullYear();
      const [recordsData, entitlementsData] = await Promise.all([
        fetchLeaveRecords(token),
        fetchLeaveEntitlements(token, { year }),
      ]);
      setRecords(Array.isArray(recordsData) ? recordsData : recordsData?.results || []);
      setEntitlements(
        Array.isArray(entitlementsData) ? entitlementsData : entitlementsData?.results || [],
      );
    } catch (err) {
      setError(err?.message || t('leaveLoadError'));
    } finally {
      setLoading(false);
    }
  }, [token, t, entFilters.year]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    loadPickerEmployees();
  }, [loadPickerEmployees]);

  const showError = (err) => {
    setSnackbar({
      open: true,
      message: err?.message || err?.feedback?.title || err?.detail || t('actionError'),
      severity: 'error',
    });
  };

  const openCreateRecord = () => {
    setEditingRecord(null);
    setRecordForm({ ...EMPTY_RECORD });
    setRecordDialogOpen(true);
  };

  const openEditRecord = (record) => {
    setEditingRecord(record);
    setRecordForm({
      employee: record.employee ?? '',
      leave_type: record.leave_type ?? '',
      start_date: record.start_date ? String(record.start_date).slice(0, 10) : '',
      end_date: record.end_date ? String(record.end_date).slice(0, 10) : '',
      days: record.days != null ? String(record.days) : '',
      status: record.status ?? 'draft',
    });
    setRecordDialogOpen(true);
  };

  const closeRecordDialog = () => {
    setRecordDialogOpen(false);
    setEditingRecord(null);
  };

  const handleSaveRecord = async () => {
    if (
      !recordForm.employee ||
      !recordForm.leave_type ||
      !recordForm.start_date ||
      !recordForm.end_date ||
      !String(recordForm.days).trim()
    ) {
      setSnackbar({ open: true, message: tCommon('allFieldsRequired'), severity: 'error' });
      return;
    }
    const payload = {
      employee: Number(recordForm.employee),
      leave_type: recordForm.leave_type,
      start_date: recordForm.start_date,
      end_date: recordForm.end_date,
      days: String(recordForm.days).trim(),
    };
    // Create as draft only — terminal statuses come from Correspondence.
    if (!editingRecord) {
      payload.status = 'draft';
    }
    setSaving(true);
    try {
      if (editingRecord) {
        await updateLeaveRecord(editingRecord.id, payload, token);
      } else {
        await createLeaveRecord(payload, token);
      }
      closeRecordDialog();
      setSnackbar({ open: true, message: t('leaveRecordSaved'), severity: 'success' });
      await loadData();
    } catch (err) {
      showError(err);
    } finally {
      setSaving(false);
    }
  };

  const openCreateEnt = () => {
    setEditingEnt(null);
    setEntForm({ ...EMPTY_ENT, year: entFilters.year || String(new Date().getFullYear()) });
    setEntDialogOpen(true);
  };

  const openEditEnt = (entitlement) => {
    setEditingEnt(entitlement);
    setEntForm({
      employee: entitlement.employee ?? '',
      year: entitlement.year != null ? String(entitlement.year) : '',
      leave_type: entitlement.leave_type ?? '',
      entitled_days: entitlement.entitled_days != null ? String(entitlement.entitled_days) : '',
      used_days: entitlement.used_days != null ? String(entitlement.used_days) : '0',
      carried_forward: entitlement.carried_forward != null ? String(entitlement.carried_forward) : '0',
      notes: entitlement.notes ?? '',
    });
    setEntDialogOpen(true);
  };

  const closeEntDialog = () => {
    setEntDialogOpen(false);
    setEditingEnt(null);
  };

  const handleSaveEnt = async () => {
    if (
      !entForm.employee ||
      !entForm.year ||
      !entForm.leave_type ||
      !String(entForm.entitled_days).trim()
    ) {
      setSnackbar({ open: true, message: tCommon('allFieldsRequired'), severity: 'error' });
      return;
    }
    const payload = {
      employee: Number(entForm.employee),
      year: Number(entForm.year),
      leave_type: entForm.leave_type,
      entitled_days: String(entForm.entitled_days).trim(),
      used_days: String(entForm.used_days || '0').trim(),
      carried_forward: String(entForm.carried_forward || '0').trim(),
      notes: entForm.notes || '',
    };
    setSaving(true);
    try {
      if (editingEnt) {
        await updateLeaveEntitlement(editingEnt.id, payload, token);
      } else {
        await createLeaveEntitlement(payload, token);
      }
      closeEntDialog();
      setSnackbar({ open: true, message: t('leaveEntitlementSaved'), severity: 'success' });
      await loadData();
    } catch (err) {
      showError(err);
    } finally {
      setSaving(false);
    }
  };

  const confirmDelete = async () => {
    const { kind, item } = deleteTarget;
    setDeleteTarget(null);
    try {
      if (kind === 'ent') {
        await deleteLeaveEntitlement(item.id, token);
        setSnackbar({ open: true, message: t('leaveEntitlementDeleted'), severity: 'success' });
      } else {
        await deleteLeaveRecord(item.id, token);
        setSnackbar({ open: true, message: t('leaveRecordDeleted'), severity: 'success' });
      }
      await loadData();
    } catch (err) {
      showError(err);
    }
  };

  const recordFilterDefs = useMemo(
    () => [
      {
        key: 'status',
        label: t('colStatus'),
        options: LEAVE_STATUSES.map((s) => ({
          value: s,
          label: t(statusLabelKey(s)),
        })),
      },
    ],
    [t],
  );

  const yearOptions = useMemo(() => {
    const y = new Date().getFullYear();
    return [y, y - 1, y - 2, y + 1].map((n) => ({ value: String(n), label: String(n) }));
  }, []);

  const entFilterDefs = useMemo(
    () => [
      {
        key: 'year',
        label: t('colYear'),
        options: yearOptions,
      },
      {
        key: 'leave_type',
        label: t('colLeaveType'),
        options: leaveTypes.options,
      },
    ],
    [t, yearOptions, leaveTypes.options],
  );

  const filteredRecords = useMemo(() => {
    const q = recordSearch.trim().toLowerCase();
    return records.filter((row) => {
      if (recordFilters.status && row.status !== recordFilters.status) return false;
      if (q) {
        const hay = [
          row.employee_name,
          row.employee_no,
          row.leave_type,
          row.leave_type_label,
          row.status,
        ]
          .filter(Boolean)
          .join(' ')
          .toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [records, recordSearch, recordFilters]);

  const filteredEntitlements = useMemo(() => {
    const q = entSearch.trim().toLowerCase();
    return entitlements.filter((row) => {
      if (entFilters.leave_type && row.leave_type !== entFilters.leave_type) return false;
      if (q) {
        const hay = [
          row.employee_name,
          row.employee_no,
          row.leave_type,
          row.leave_type_label,
          row.year,
          row.notes,
        ]
          .filter(Boolean)
          .join(' ')
          .toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [entitlements, entSearch, entFilters.leave_type]);

  const recordColumns = useMemo(
    () => [
      {
        field: 'employee_name',
        headerName: t('colEmployee'),
        flex: 1.2,
        minWidth: 180,
        valueGetter: (value, row) => employeeLabel(row),
      },
      {
        field: 'leave_type',
        headerName: t('colLeaveType'),
        flex: 1,
        minWidth: 120,
        valueGetter: (value, row) => row.leave_type_label || row.leave_type || '—',
      },
      {
        field: 'start_date',
        headerName: t('colStartDate'),
        width: 120,
        valueGetter: (value, row) => formatDate(row.start_date),
      },
      {
        field: 'end_date',
        headerName: t('colEndDate'),
        width: 120,
        valueGetter: (value, row) => formatDate(row.end_date),
      },
      {
        field: 'days',
        headerName: t('colDays'),
        width: 90,
        valueGetter: (value, row) => (row.days != null ? row.days : '—'),
      },
      {
        field: 'status',
        headerName: t('colStatus'),
        width: 130,
        renderCell: (params) => {
          const statusKey = statusLabelKey(params.row.status);
          return (
            <Chip
              size="small"
              variant="outlined"
              color={statusColor(params.row.status)}
              label={statusKey ? t(statusKey) : params.row.status}
            />
          );
        },
      },
      {
        field: 'actions',
        headerName: t('colActions'),
        width: 100,
        sortable: false,
        filterable: false,
        renderCell: (params) => {
          const record = params.row;
          return (
            <Box>
              <Tooltip title={tCommon('edit')}>
                <IconButton
                  size="small"
                  aria-label={tCommon('edit')}
                  onClick={(e) => {
                    e.stopPropagation();
                    openEditRecord(record);
                  }}
                >
                  <EditIcon fontSize="small" />
                </IconButton>
              </Tooltip>
              <Tooltip title={tCommon('delete')}>
                <IconButton
                  size="small"
                  aria-label={tCommon('delete')}
                  sx={{ color: 'error.main' }}
                  onClick={(e) => {
                    e.stopPropagation();
                    setDeleteTarget({ kind: 'record', item: record });
                  }}
                >
                  <DeleteIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            </Box>
          );
        },
      },
    ],
    [t, tCommon],
  );

  const entColumns = useMemo(
    () => [
      {
        field: 'employee_name',
        headerName: t('colEmployee'),
        flex: 1.2,
        minWidth: 180,
        valueGetter: (value, row) => employeeLabel(row),
      },
      {
        field: 'year',
        headerName: t('colYear'),
        width: 90,
      },
      {
        field: 'leave_type',
        headerName: t('colLeaveType'),
        flex: 1,
        minWidth: 120,
        valueGetter: (value, row) => row.leave_type_label || row.leave_type || '—',
      },
      {
        field: 'entitled_days',
        headerName: t('colEntitledDays'),
        width: 110,
      },
      {
        field: 'used_days',
        headerName: t('colUsedDays'),
        width: 100,
      },
      {
        field: 'carried_forward',
        headerName: t('formCarriedForward'),
        width: 120,
      },
      {
        field: 'actions',
        headerName: t('colActions'),
        width: 100,
        sortable: false,
        filterable: false,
        renderCell: (params) => (
          <Box>
            <Tooltip title={tCommon('edit')}>
              <IconButton
                size="small"
                onClick={(e) => {
                  e.stopPropagation();
                  openEditEnt(params.row);
                }}
              >
                <EditIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            <Tooltip title={tCommon('delete')}>
              <IconButton
                size="small"
                sx={{ color: 'error.main' }}
                onClick={(e) => {
                  e.stopPropagation();
                  setDeleteTarget({ kind: 'ent', item: params.row });
                }}
              >
                <DeleteIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Box>
        ),
      },
    ],
    [t, tCommon],
  );

  const selectedEmployeeOption = (id) =>
    employeeOptions.find((o) => String(o.value) === String(id)) || null;

  const selectedLeaveTypeOption = (code) =>
    leaveTypes.options.find((o) => o.value === code) || (code ? { value: code, label: code } : null);

  return (
    <>
      {error && (
        <Alert severity="error" sx={{ mx: 1, mt: 1 }} onClose={() => setError(null)} action={
          <Button color="inherit" size="small" onClick={loadData}>{tCommon('retry')}</Button>
        }>
          {error}
        </Alert>
      )}

      <Box sx={{ px: 1, pt: 1 }}>
        <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 1 }}>
          <Tab label={t('leaveRecordsTitle')} />
          <Tab label={t('leaveEntitlementsTitle')} />
        </Tabs>
      </Box>

      {tab === 0 ? (
        <FilteredDataGrid
          title={t('leaveTitle')}
          subtitle={t('leaveSubtitle')}
          actions={
            <Button variant="contained" size="small" startIcon={<AddIcon />} onClick={openCreateRecord}>
              {t('actionAddLeaveRecord')}
            </Button>
          }
          rows={filteredRecords}
          columns={recordColumns}
          loading={loading}
          getRowId={(row) => row.id}
          countLabel={`${filteredRecords.length} of ${records.length}`}
          searchValue={recordSearch}
          onSearchChange={setRecordSearch}
          searchPlaceholder={t('leaveSearchPlaceholder')}
          filterDefs={recordFilterDefs}
          filterValues={recordFilters}
          onFilterChange={(key, value) => setRecordFilters((prev) => ({ ...prev, [key]: value }))}
          onClearFilters={() => {
            setRecordSearch('');
            setRecordFilters({ status: '' });
          }}
          emptyMessage={t('leaveEmpty')}
          emptySubtext={t('leaveEmptyDesc')}
          height={520}
        />
      ) : (
        <FilteredDataGrid
          title={t('leaveEntitlementsTitle')}
          subtitle={t('leaveSubtitle')}
          actions={
            <Button variant="contained" size="small" startIcon={<AddIcon />} onClick={openCreateEnt}>
              {t('actionAddLeaveEntitlement')}
            </Button>
          }
          rows={filteredEntitlements}
          columns={entColumns}
          loading={loading}
          getRowId={(row) => row.id}
          countLabel={`${filteredEntitlements.length} of ${entitlements.length}`}
          searchValue={entSearch}
          onSearchChange={setEntSearch}
          searchPlaceholder={t('leaveSearchPlaceholder')}
          filterDefs={entFilterDefs}
          filterValues={entFilters}
          onFilterChange={(key, value) => setEntFilters((prev) => ({ ...prev, [key]: value }))}
          onClearFilters={() => {
            setEntSearch('');
            setEntFilters({ year: String(new Date().getFullYear()), leave_type: '' });
          }}
          emptyMessage={t('leaveEmpty')}
          emptySubtext={t('leaveEmptyDesc')}
          height={520}
        />
      )}

      <SystemDialog
        open={recordDialogOpen}
        title={editingRecord ? t('leaveRecordEditTitle') : t('leaveRecordCreateTitle')}
        onClose={closeRecordDialog}
        onCancel={closeRecordDialog}
        cancelLabel={tCommon('cancel')}
        actions={
          <Button variant="contained" onClick={handleSaveRecord} disabled={saving}>
            {tCommon('save')}
          </Button>
        }
      >
        <Stack spacing={2}>
          <Alert severity="info" variant="outlined">
            {t('leaveApproveViaTeamHint')}
          </Alert>
          <SearchSelect
            label={t('colEmployee')}
            options={employeeOptions}
            valueKey="value"
            labelKey="label"
            value={selectedEmployeeOption(recordForm.employee)}
            onChange={(opt) => setRecordForm((prev) => ({ ...prev, employee: opt?.value ?? '' }))}
            required
            size="small"
          />
          <SearchSelect
            label={t('colLeaveType')}
            options={leaveTypes.options}
            valueKey="value"
            labelKey="label"
            value={selectedLeaveTypeOption(recordForm.leave_type)}
            onChange={(opt) => setRecordForm((prev) => ({ ...prev, leave_type: opt?.value ?? '' }))}
            loading={leaveTypes.loading}
            error={leaveTypes.error}
            onRetry={leaveTypes.refetch}
            required
            size="small"
          />
          <TextField
            label={t('colStartDate')}
            value={recordForm.start_date}
            onChange={(e) => setRecordForm((prev) => ({ ...prev, start_date: e.target.value }))}
            type="date"
            slotProps={{ inputLabel: { shrink: true } }}
            fullWidth
            required
            size="small"
          />
          <TextField
            label={t('colEndDate')}
            value={recordForm.end_date}
            onChange={(e) => setRecordForm((prev) => ({ ...prev, end_date: e.target.value }))}
            type="date"
            slotProps={{ inputLabel: { shrink: true } }}
            fullWidth
            required
            size="small"
          />
          <TextField
            label={t('colDays')}
            value={recordForm.days}
            onChange={(e) => setRecordForm((prev) => ({ ...prev, days: e.target.value }))}
            type="number"
            fullWidth
            required
            size="small"
          />
          {editingRecord && (
            <Box>
              <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 0.5 }}>
                {t('colStatus')}
              </Typography>
              <Chip
                size="small"
                variant="outlined"
                color={statusColor(recordForm.status)}
                label={statusLabelKey(recordForm.status) ? t(statusLabelKey(recordForm.status)) : recordForm.status}
              />
            </Box>
          )}
        </Stack>
      </SystemDialog>

      <SystemDialog
        open={entDialogOpen}
        title={editingEnt ? t('leaveEntitlementEditTitle') : t('leaveEntitlementCreateTitle')}
        onClose={closeEntDialog}
        onCancel={closeEntDialog}
        cancelLabel={tCommon('cancel')}
        actions={
          <Button variant="contained" onClick={handleSaveEnt} disabled={saving}>
            {tCommon('save')}
          </Button>
        }
      >
        <Stack spacing={2}>
          <SearchSelect
            label={t('colEmployee')}
            options={employeeOptions}
            valueKey="value"
            labelKey="label"
            value={selectedEmployeeOption(entForm.employee)}
            onChange={(opt) => setEntForm((prev) => ({ ...prev, employee: opt?.value ?? '' }))}
            required
            size="small"
          />
          <TextField
            label={t('colYear')}
            value={entForm.year}
            onChange={(e) => setEntForm((prev) => ({ ...prev, year: e.target.value }))}
            type="number"
            fullWidth
            required
            size="small"
          />
          <SearchSelect
            label={t('colLeaveType')}
            options={leaveTypes.options}
            valueKey="value"
            labelKey="label"
            value={selectedLeaveTypeOption(entForm.leave_type)}
            onChange={(opt) => setEntForm((prev) => ({ ...prev, leave_type: opt?.value ?? '' }))}
            loading={leaveTypes.loading}
            error={leaveTypes.error}
            onRetry={leaveTypes.refetch}
            required
            size="small"
          />
          <TextField
            label={t('colEntitledDays')}
            value={entForm.entitled_days}
            onChange={(e) => setEntForm((prev) => ({ ...prev, entitled_days: e.target.value }))}
            type="number"
            fullWidth
            required
            size="small"
          />
          <TextField
            label={t('colUsedDays')}
            value={entForm.used_days}
            onChange={(e) => setEntForm((prev) => ({ ...prev, used_days: e.target.value }))}
            type="number"
            fullWidth
            size="small"
          />
          <TextField
            label={t('formCarriedForward')}
            value={entForm.carried_forward}
            onChange={(e) => setEntForm((prev) => ({ ...prev, carried_forward: e.target.value }))}
            type="number"
            fullWidth
            size="small"
          />
          <TextField
            label={t('formNotes')}
            value={entForm.notes}
            onChange={(e) => setEntForm((prev) => ({ ...prev, notes: e.target.value }))}
            multiline
            minRows={2}
            fullWidth
            size="small"
          />
        </Stack>
      </SystemDialog>

      <ConfirmDialog
        open={!!deleteTarget}
        message={
          deleteTarget?.kind === 'ent'
            ? t('leaveEntitlementDeleteConfirm')
            : t('leaveRecordDeleteConfirm')
        }
        confirmLabel={tCommon('delete')}
        destructive
        onConfirm={confirmDelete}
        onCancel={() => setDeleteTarget(null)}
      />

      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={() => setSnackbar((prev) => ({ ...prev, open: false }))}
        message={snackbar.message}
      />
    </>
  );
}
