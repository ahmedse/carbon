// src/pages/admin/ai/WatchesPanel.jsx
// Route /admin/ai/watches — H3-F anomaly watches (KPI thresholds on host data).
// Server-paginated MUI Table + SystemDialog create/edit form + ConfirmDialog
// delete. Write affordances (create/edit/delete) require ai:manage_console; the
// list renders under ai:view_console. RULE_10 apiFetch only (via aiPulse);
// RULE_8 theme tokens only; RULE_16 PageContainer; RULE_29 full state matrix.
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Autocomplete,
  Box,
  Button,
  Chip,
  CircularProgress,
  FormControl,
  FormControlLabel,
  FormHelperText,
  IconButton,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import CloudOffIcon from '@mui/icons-material/CloudOff';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import { useTranslation } from 'react-i18next';
import useDocumentTitle from '../../../hooks/useDocumentTitle';
import PageContainer from '../../../components/layout/PageContainer';
import PageHeader from '../../../components/Page/PageHeader';
import SystemDialog from '../../../components/SystemDialog';
import ConfirmDialog from '../../../components/ConfirmDialog';
import { useAuth } from '../../../auth/AuthContext';
import { useNotification } from '../../../components/NotificationProvider';
import { listWatches, createWatch, updateWatch, deleteWatch } from '../../../api/aiPulse';
import { fetchUsers } from '../../../api/users';
import {
  AI_VIEW_CONSOLE,
  AI_MANAGE_CONSOLE,
  expandCapabilities,
  hasCap,
} from '../../../capabilities';

const OPERATORS = ['<', '<=', '>', '>=', '==', '!='];
const AGGREGATIONS = ['latest', 'avg', 'max', 'min', 'count'];

const EMPTY_FORM = {
  name: '',
  kpi_expression: '',
  conditionTable: '',
  conditionColumn: '',
  operator: '',
  aggregation: '',
  threshold: '',
  comparison_window_days: '',
  recipients: [],
  enabled: true,
};

/** Format an ISO timestamp defensively (em-dash when missing/invalid). */
function formatTimestamp(value) {
  if (!value) return '—';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString();
}

/** Map a DRF 400 payload back onto per-field form errors. */
function extractFieldErrors(err) {
  const data = err?.data;
  if (!data || typeof data !== 'object') return {};
  const known = ['name', 'kpi_expression', 'condition', 'threshold', 'comparison_window_days', 'recipients', 'enabled'];
  const out = {};
  for (const key of known) {
    if (data[key] !== undefined) {
      const val = data[key];
      out[key] = Array.isArray(val) ? val.join(' ') : String(val);
    }
  }
  if (data.non_field_errors) {
    out.general = Array.isArray(data.non_field_errors) ? data.non_field_errors.join(' ') : String(data.non_field_errors);
  } else if (typeof data.detail === 'string' && !known.some((k) => k in data)) {
    out.general = data.detail;
  }
  return out;
}

/** Client-side validation — returns a field→message map (empty when valid). */
function validate(form, t) {
  const errors = {};
  if (!form.name || !String(form.name).trim()) errors.name = t('watches.nameRequired');
  if (form.threshold === '' || form.threshold === null || form.threshold === undefined) {
    errors.threshold = t('watches.thresholdRequired');
  } else if (Number.isNaN(Number(form.threshold))) {
    errors.threshold = t('watches.thresholdNumber');
  }
  if (form.comparison_window_days === '' || form.comparison_window_days === null || form.comparison_window_days === undefined) {
    errors.comparison_window_days = t('watches.windowRequired');
  } else if (Number.isNaN(Number(form.comparison_window_days))) {
    errors.comparison_window_days = t('watches.windowNumber');
  }
  return errors;
}

/** Build the POST/PATCH payload, collapsing an empty condition to null. */
function buildPayload(form) {
  const condition = {};
  if (form.conditionTable) condition.table = form.conditionTable;
  if (form.conditionColumn) condition.column = form.conditionColumn;
  if (form.operator) condition.operator = form.operator;
  if (form.aggregation) condition.aggregation = form.aggregation;
  return {
    name: String(form.name).trim(),
    kpi_expression: form.kpi_expression,
    condition: Object.keys(condition).length ? condition : null,
    threshold: Number(form.threshold),
    comparison_window_days: Number(form.comparison_window_days),
    recipients: form.recipients,
    enabled: Boolean(form.enabled),
  };
}

/** WatchDialog — create/edit form rendered inside SystemDialog. */
function WatchDialog({
  open,
  mode,
  form,
  errors,
  users,
  usersLoading,
  saving,
  onChange,
  onRecipientsChange,
  onSave,
  onClose,
}) {
  const { t } = useTranslation('ai');
  const { t: tc } = useTranslation('common');

  const selectedRecipients = useMemo(
    () => (users || []).filter((u) => (form.recipients || []).includes(u.id)),
    [users, form.recipients]
  );

  return (
    <SystemDialog
      open={open}
      title={mode === 'create' ? t('watches.newWatch') : t('watches.editWatch')}
      onClose={onClose}
      onCancel={onClose}
      cancelLabel={tc('cancel')}
      showCancel
      width={680}
      height={680}
      actions={
        <Button
          variant="contained"
          onClick={onSave}
          disabled={saving}
          startIcon={saving ? <CircularProgress size={16} color="inherit" /> : null}
        >
          {tc('save')}
        </Button>
      }
    >
      <Stack spacing={1.5} sx={{ mt: 0.5 }}>
        {errors.general ? (
          <Alert severity="error" role="alert">{errors.general}</Alert>
        ) : null}
        <TextField
          label={t('watches.name')}
          value={form.name}
          onChange={onChange('name')}
          error={Boolean(errors.name)}
          helperText={errors.name}
          size="small"
          fullWidth
          required
        />
        <TextField
          label={t('watches.kpiExpression')}
          value={form.kpi_expression}
          onChange={onChange('kpi_expression')}
          error={Boolean(errors.kpi_expression)}
          helperText={errors.kpi_expression}
          size="small"
          fullWidth
          multiline
          minRows={2}
        />
        <Typography variant="subtitle2" color="text.secondary">{t('watches.condition')}</Typography>
        <Stack direction="row" spacing={1}>
          <TextField
            label={t('watches.conditionTable')}
            value={form.conditionTable}
            onChange={onChange('conditionTable')}
            size="small"
            fullWidth
          />
          <TextField
            label={t('watches.conditionColumn')}
            value={form.conditionColumn}
            onChange={onChange('conditionColumn')}
            size="small"
            fullWidth
          />
        </Stack>
        <Stack direction="row" spacing={1}>
          <FormControl size="small" fullWidth>
            <InputLabel id="watch-operator-label">{t('watches.operator')}</InputLabel>
            <Select
              labelId="watch-operator-label"
              label={t('watches.operator')}
              value={form.operator}
              onChange={onChange('operator')}
            >
              <MenuItem value="">—</MenuItem>
              {OPERATORS.map((op) => (
                <MenuItem key={op} value={op}>
                  <Box component="span" dir="ltr">{op}</Box>
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl size="small" fullWidth>
            <InputLabel id="watch-aggregation-label">{t('watches.aggregation')}</InputLabel>
            <Select
              labelId="watch-aggregation-label"
              label={t('watches.aggregation')}
              value={form.aggregation}
              onChange={onChange('aggregation')}
            >
              <MenuItem value="">—</MenuItem>
              {AGGREGATIONS.map((a) => (
                <MenuItem key={a} value={a}>{a}</MenuItem>
              ))}
            </Select>
          </FormControl>
        </Stack>
        {errors.condition ? (
          <FormHelperText error>{errors.condition}</FormHelperText>
        ) : null}
        <Stack direction="row" spacing={1}>
          <TextField
            label={t('watches.threshold')}
            value={form.threshold}
            onChange={onChange('threshold')}
            error={Boolean(errors.threshold)}
            helperText={errors.threshold}
            size="small"
            fullWidth
            inputProps={{ inputMode: 'decimal' }}
          />
          <TextField
            label={t('watches.comparisonWindowDays')}
            value={form.comparison_window_days}
            onChange={onChange('comparison_window_days')}
            error={Boolean(errors.comparison_window_days)}
            helperText={errors.comparison_window_days}
            size="small"
            fullWidth
            inputProps={{ inputMode: 'numeric' }}
          />
        </Stack>
        <Autocomplete
          multiple
          options={users || []}
          loading={usersLoading}
          value={selectedRecipients}
          onChange={onRecipientsChange}
          getOptionLabel={(option) => option.username ?? String(option.id)}
          isOptionEqualToValue={(option, value) => option.id === value.id}
          renderInput={(params) => (
            <TextField
              {...params}
              label={t('watches.recipients')}
              size="small"
              error={Boolean(errors.recipients)}
              helperText={errors.recipients}
            />
          )}
        />
        <FormControlLabel
          control={<Switch checked={Boolean(form.enabled)} onChange={onChange('enabled')} />}
          label={form.enabled ? t('watches.enabled') : t('watches.disabled')}
        />
      </Stack>
    </SystemDialog>
  );
}

export default function WatchesPanel() {
  useDocumentTitle('Anomaly Watches');
  const { t } = useTranslation('ai');
  const { t: tc } = useTranslation('common');
  const { token, userCapabilities } = useAuth();
  const { notify, notifyFromError } = useNotification();

  const [rows, setRows] = useState([]);
  const [count, setCount] = useState(0);
  const [page, setPage] = useState(0); // 0-based (TablePagination)
  const [pageSize, setPageSize] = useState(20);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);

  const [users, setUsers] = useState([]);
  const [usersLoading, setUsersLoading] = useState(false);
  const [usersLoaded, setUsersLoaded] = useState(false);

  const [dialog, setDialog] = useState(null); // 'create' | 'edit' | 'delete' | null
  const [form, setForm] = useState(EMPTY_FORM);
  const [formErrors, setFormErrors] = useState({});
  const [saving, setSaving] = useState(false);
  const [selected, setSelected] = useState(null);

  const caps = useMemo(
    () => (userCapabilities || []).map((c) => (typeof c === 'string' ? c : c?.key || c?.capability)),
    [userCapabilities]
  );
  const canView = useMemo(() => hasCap(expandCapabilities(caps), AI_VIEW_CONSOLE), [caps]);
  const canManage = useMemo(() => hasCap(expandCapabilities(caps), AI_MANAGE_CONSOLE), [caps]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const payload = await listWatches(token, { page: page + 1, pageSize });
      setRows(payload?.results ?? []);
      setCount(payload?.count ?? 0);
      setOffline(false);
    } catch {
      setRows([]);
      setCount(0);
      setOffline(true);
    } finally {
      setLoading(false);
    }
  }, [token, page, pageSize]);

  useEffect(() => {
    if (!canView) return undefined;
    load();
  }, [load, canView]);

  const loadUsers = useCallback(async () => {
    if (usersLoaded) return;
    setUsersLoading(true);
    try {
      const list = await fetchUsers(token);
      setUsers(Array.isArray(list) ? list : []);
    } catch {
      setUsers([]);
    } finally {
      setUsersLoading(false);
      setUsersLoaded(true);
    }
  }, [token, usersLoaded]);

  const handleChange = (field) => (event) => {
    const target = event?.target;
    // Distinguish the Switch (checkbox) from text/number/select inputs by type,
    // NOT by `typeof checked === 'boolean'` — every HTMLInputElement reports a
    // boolean `checked` (false for text inputs), so the old check corrupted all
    // text fields to `false`.
    const next = target?.type === 'checkbox' ? target.checked : target.value;
    setForm((prev) => ({ ...prev, [field]: next }));
  };

  const handleRecipientsChange = (event, value) => {
    setForm((prev) => ({ ...prev, recipients: (value || []).map((u) => u.id) }));
  };

  const openCreate = () => {
    setSelected(null);
    setForm(EMPTY_FORM);
    setFormErrors({});
    setDialog('create');
    loadUsers();
  };

  const openEdit = (row) => {
    const cond = row.condition && typeof row.condition === 'object' ? row.condition : {};
    setSelected(row);
    setForm({
      name: row.name ?? '',
      kpi_expression: row.kpi_expression ?? '',
      conditionTable: cond.table ?? '',
      conditionColumn: cond.column ?? '',
      operator: cond.operator ?? '',
      aggregation: cond.aggregation ?? '',
      threshold: row.threshold ?? '',
      comparison_window_days: row.comparison_window_days ?? '',
      recipients: Array.isArray(row.recipients) ? row.recipients : [],
      enabled: row.enabled !== false,
    });
    setFormErrors({});
    setDialog('edit');
    loadUsers();
  };

  const openDelete = (row) => {
    setSelected(row);
    setDialog('delete');
  };

  const closeDialog = () => {
    if (saving) return;
    setDialog(null);
    setSelected(null);
    setFormErrors({});
  };

  const onSave = async () => {
    if (!canManage || !dialog) return;
    const clientErrors = validate(form, t);
    if (Object.keys(clientErrors).length) {
      setFormErrors(clientErrors);
      return;
    }
    setSaving(true);
    setFormErrors({});
    try {
      const payload = buildPayload(form);
      if (dialog === 'create') {
        await createWatch(token, payload);
      } else {
        await updateWatch(token, selected.id, payload);
      }
      notify({ message: t('watches.saved'), type: 'success' });
      setDialog(null);
      setSelected(null);
      await load();
    } catch (err) {
      const fieldErrors = extractFieldErrors(err);
      if (Object.keys(fieldErrors).length) {
        setFormErrors(fieldErrors);
      } else {
        notifyFromError(err, t('watches.saveFailed'));
      }
    } finally {
      setSaving(false);
    }
  };

  const onDelete = async () => {
    if (!selected || !canManage || saving) return;
    setSaving(true);
    try {
      await deleteWatch(token, selected.id);
      notify({ message: t('watches.deleted'), type: 'success' });
      setDialog(null);
      setSelected(null);
      await load();
    } catch (err) {
      notifyFromError(err, t('watches.deleteFailed'));
    } finally {
      setSaving(false);
    }
  };

  if (!canView) {
    return (
      <PageContainer>
        <Typography color="text.secondary">{t('watches.requiresViewConsole')}</Typography>
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <Stack spacing={1.5} sx={{ flex: 1, minHeight: 0 }}>
        <PageHeader
          title={t('watches.title')}
          subtitle={t('watches.subtitle')}
          actions={
            canManage ? (
              <Button variant="contained" startIcon={<AddIcon />} onClick={openCreate} size="small">
                {t('watches.newWatch')}
              </Button>
            ) : undefined
          }
        />

        {canView && !canManage ? (
          <Alert severity="info">{t('watches.requiresManageConsole')}</Alert>
        ) : null}

        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
            <CircularProgress size={24} />
          </Box>
        ) : offline ? (
          <Paper variant="outlined" sx={{ p: 4, textAlign: 'center' }}>
            <CloudOffIcon fontSize="large" sx={{ color: 'text.secondary' }} />
            <Typography variant="subtitle1" sx={{ mt: 1 }} fontWeight={600}>
              {t('watches.offlineTitle')}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              {t('watches.offlineBody')}
            </Typography>
            <Button onClick={load} sx={{ mt: 1 }} size="small">{tc('retry')}</Button>
          </Paper>
        ) : rows.length === 0 ? (
          <Paper variant="outlined" sx={{ p: 4, textAlign: 'center' }}>
            <Typography color="text.secondary">{t('watches.noWatches')}</Typography>
            {canManage ? (
              <Button
                variant="contained"
                startIcon={<AddIcon />}
                onClick={openCreate}
                sx={{ mt: 1.5 }}
                size="small"
              >
                {t('watches.createFirstWatch')}
              </Button>
            ) : null}
          </Paper>
        ) : (
          <>
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>{t('watches.name')}</TableCell>
                    <TableCell>{t('watches.threshold')}</TableCell>
                    <TableCell>{t('watches.comparisonWindowDays')}</TableCell>
                    <TableCell>{t('watches.enabled')}</TableCell>
                    <TableCell>{t('watches.lastFiredAt')}</TableCell>
                    <TableCell>{t('watches.fireCount')}</TableCell>
                    {canManage ? <TableCell align="right">{tc('actions')}</TableCell> : null}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {rows.map((row) => (
                    <TableRow key={row.id} hover>
                      <TableCell>
                        <Typography variant="body2" fontWeight={600}>{row.name}</Typography>
                        {row.kpi_expression ? (
                          <Typography variant="caption" color="text.secondary">{row.kpi_expression}</Typography>
                        ) : null}
                      </TableCell>
                      <TableCell dir="ltr">{row.threshold}</TableCell>
                      <TableCell dir="ltr">{row.comparison_window_days}</TableCell>
                      <TableCell>
                        <Chip
                          size="small"
                          variant="outlined"
                          color={row.enabled ? 'success' : 'default'}
                          label={row.enabled ? t('watches.enabled') : t('watches.disabled')}
                        />
                      </TableCell>
                      <TableCell dir="ltr">{formatTimestamp(row.last_fired_at)}</TableCell>
                      <TableCell dir="ltr">{row.fire_count ?? 0}</TableCell>
                      {canManage ? (
                        <TableCell align="right">
                          <IconButton
                            size="small"
                            aria-label={t('watches.editAction', { name: row.name })}
                            onClick={() => openEdit(row)}
                          >
                            <EditOutlinedIcon fontSize="small" />
                          </IconButton>
                          <IconButton
                            size="small"
                            aria-label={t('watches.deleteAction', { name: row.name })}
                            onClick={() => openDelete(row)}
                          >
                            <DeleteOutlineIcon fontSize="small" />
                          </IconButton>
                        </TableCell>
                      ) : null}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
            <TablePagination
              component="div"
              count={count}
              page={page}
              onPageChange={(event, newPage) => setPage(newPage)}
              rowsPerPage={pageSize}
              onRowsPerPageChange={(event) => {
                setPageSize(parseInt(event.target.value, 10));
                setPage(0);
              }}
              rowsPerPageOptions={[20, 50, 100]}
            />
          </>
        )}
      </Stack>

      <WatchDialog
        open={dialog === 'create' || dialog === 'edit'}
        mode={dialog}
        form={form}
        errors={formErrors}
        users={users}
        usersLoading={usersLoading}
        saving={saving}
        onChange={handleChange}
        onRecipientsChange={handleRecipientsChange}
        onSave={onSave}
        onClose={closeDialog}
      />

      <ConfirmDialog
        open={dialog === 'delete'}
        title={t('watches.deleteConfirmTitle')}
        message={t('watches.deleteConfirmBody', { name: selected?.name ?? '' })}
        destructive
        confirmLabel={tc('delete')}
        onConfirm={onDelete}
        onCancel={closeDialog}
      />
    </PageContainer>
  );
}
