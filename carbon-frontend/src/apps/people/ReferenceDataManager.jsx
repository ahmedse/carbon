// src/apps/people/ReferenceDataManager.jsx
// Generic, registry-driven reference-data CRUD manager.
//
// Renders a dropdown to pick a reference list, then drives its full CRUD from a
// config object (columns + form + API) declared in referenceDataRegistry.js.
// Delete is guarded server-side: when an item is in use, the backend returns a
// structured "why" (code/title/detail) which we surface verbatim here.

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  FormControlLabel,
  IconButton,
  MenuItem,
  Snackbar,
  Stack,
  Switch,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import { useTranslation } from 'react-i18next';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../components/Page/ErrorAlert';
import EmptyState from '../../components/Page/EmptyState';
import SystemDialog from '../../components/SystemDialog';
import ConfirmDialog from '../../components/ConfirmDialog';
import StandardDataGrid from '../../components/StandardDataGrid';
import { useAuth } from '../../auth/AuthContext';
import { REFERENCE_TYPES } from './referenceDataRegistry';

// Renders a DataGrid column header label inside a Tooltip so every column
// explains itself on hover (RULE 11 — know what everything is).
const tipHeader = (tip) => (params) => (
  <Tooltip title={tip} arrow enterDelay={400} placement="top">
    <span>{params.colDef.headerName}</span>
  </Tooltip>
);

// Build the blank form for a definition (switch defaults come from field.default).
function blankForm(def) {
  const form = {};
  (def.form || []).forEach((f) => {
    form[f.name] = f.kind === 'switch' ? Boolean(f.default) : '';
  });
  return form;
}

export default function ReferenceDataManager({ definitions = REFERENCE_TYPES }) {
  const { t } = useTranslation('people');
  const { t: tCommon } = useTranslation('common');
  const { token } = useAuth();

  const [selectedKey, setSelectedKey] = useState(definitions[0]?.key ?? '');
  const def = definitions.find((d) => d.key === selectedKey) ?? definitions[0];

  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({});

  const [deleteTarget, setDeleteTarget] = useState(null);
  const [saving, setSaving] = useState(false);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });

  const loadData = useCallback(async () => {
    if (!def) return;
    try {
      setLoading(true);
      setError(null);
      const data = await def.list(token);
      const list = Array.isArray(data) ? data : data?.results || [];
      setRows(list);
    } catch (err) {
      setError(err?.message || t('benefitsLoadError'));
    } finally {
      setLoading(false);
    }
  }, [def, token, t]);

  useEffect(() => { loadData(); }, [loadData]);

  // Reset form/dialog when switching lists.
  useEffect(() => {
    setDialogOpen(false);
    setEditing(null);
    setDeleteTarget(null);
  }, [selectedKey]);

  const showError = (err) => {
    // Prefer the structured "why" (feedback title + detail) over a generic message.
    const fb = err?.feedback;
    const message = fb?.detail || fb?.title || err?.message || err?.detail || t('actionError');
    setSnackbar({ open: true, message, severity: 'error' });
  };

  const openCreate = useCallback(() => {
    setEditing(null);
    setForm(blankForm(def));
    setDialogOpen(true);
  }, [def]);

  const openEdit = useCallback((row) => {
    setEditing(row);
    const next = {};
    (def.form || []).forEach((f) => {
      next[f.name] = f.kind === 'switch' ? Boolean(row[f.name]) : (row[f.name] != null ? String(row[f.name]) : '');
    });
    setForm(next);
    setDialogOpen(true);
  }, [def]);

  const closeDialog = useCallback(() => {
    setDialogOpen(false);
    setEditing(null);
  }, []);

  const handleChange = (event) => {
    const { name, value, checked, type } = event.target;
    setForm((prev) => ({ ...prev, [name]: type === 'checkbox' ? checked : value }));
  };

  const handleSave = async () => {
    const missing = (def.form || []).some(
      (f) => f.required && !String(form[f.name] ?? '').trim(),
    );
    if (missing) {
      setSnackbar({ open: true, message: tCommon('allFieldsRequired'), severity: 'error' });
      return;
    }

    const payload = {};
    (def.form || []).forEach((f) => {
      if (f.kind === 'switch') {
        payload[f.name] = Boolean(form[f.name]);
      } else {
        payload[f.name] = String(form[f.name] ?? '').trim();
      }
    });

    setSaving(true);
    try {
      if (editing) {
        await def.update(editing.id, payload, token);
      } else {
        await def.create(payload, token);
      }
      closeDialog();
      setSnackbar({ open: true, message: t(def.savedKey), severity: 'success' });
      await loadData();
    } catch (err) {
      showError(err);
    } finally {
      setSaving(false);
    }
  };

  const requestDelete = useCallback((row) => setDeleteTarget(row), []);

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    try {
      await def.remove(deleteTarget.id, token);
      setDeleteTarget(null);
      setSnackbar({ open: true, message: t(def.deletedKey), severity: 'success' });
      await loadData();
    } catch (err) {
      setDeleteTarget(null);
      showError(err);
    }
  };

  const closeSnackbar = () => setSnackbar((prev) => ({ ...prev, open: false }));

  // ---- Column + form rendering (driven by the active definition) ----

  const columns = useMemo(() => {
    if (!def) return [];
    const cols = (def.columns || []).map((col) => {
      const base = {
        field: col.field,
        headerName: t(col.headerKey),
        flex: col.flex ?? 1,
        minWidth: col.minWidth ?? 120,
        renderHeader: col.tipKey ? tipHeader(t(col.tipKey)) : undefined,
      };
      if (col.render === 'boolean') {
        base.renderCell = (p) => (
          <Chip size="small" variant="outlined" color={p.value ? 'success' : 'default'} label={p.value ? t('yes') : t('no')} />
        );
      } else if (col.render === 'status') {
        base.renderCell = (p) => (
          <Chip
            size="small"
            color={p.value ? 'success' : 'default'}
            label={p.value ? t('statusActive') : t('statusInactive')}
          />
        );
      } else if (col.render === 'category') {
        base.renderCell = (p) => {
          const key = def.categoryKeys?.[p.value];
          return <Chip size="small" variant="outlined" label={key ? t(key) : (p.value || '—')} />;
        };
      }
      return base;
    });

    cols.push({
      field: 'actions',
      headerName: t('colActions'),
      width: 90,
      sortable: false,
      filterable: false,
      renderHeader: tipHeader(t('colActionsTip')),
      renderCell: (p) => (
        <Box sx={{ display: 'flex', gap: 0.25 }}>
          <Tooltip title={tCommon('edit')}>
            <IconButton size="small" aria-label={tCommon('edit')} onClick={() => openEdit(p.row)} sx={{ color: 'primary.main' }}>
              <EditIcon sx={{ fontSize: 16 }} />
            </IconButton>
          </Tooltip>
          <Tooltip title={tCommon('delete')}>
            <IconButton size="small" aria-label={tCommon('delete')} onClick={() => requestDelete(p.row)} sx={{ color: 'error.main' }}>
              <DeleteIcon sx={{ fontSize: 16 }} />
            </IconButton>
          </Tooltip>
        </Box>
      ),
    });
    return cols;
  }, [def, t, tCommon, openEdit, requestDelete]);

  const renderField = (f) => {
    const label = f.tipKey ? (
      <Tooltip title={t(f.tipKey)} arrow placement="top">
        <span>{t(f.labelKey)}</span>
      </Tooltip>
    ) : t(f.labelKey);

    if (f.kind === 'switch') {
      return (
        <FormControlLabel
          key={f.name}
          control={<Switch checked={Boolean(form[f.name])} onChange={handleChange} name={f.name} color="primary" />}
          label={label}
        />
      );
    }
    if (f.kind === 'select') {
      return (
        <TextField
          key={f.name}
          select
          label={t(f.labelKey)}
          name={f.name}
          value={form[f.name]}
          onChange={handleChange}
          fullWidth
          required={f.required}
        >
          <MenuItem value="" disabled>{t(f.labelKey)}</MenuItem>
          {(f.options || []).map((opt) => {
            const key = f.optionKeys?.[opt];
            return <MenuItem key={opt} value={opt}>{key ? t(key) : opt}</MenuItem>;
          })}
        </TextField>
      );
    }
    if (f.kind === 'date') {
      return (
        <TextField
          key={f.name}
          label={t(f.labelKey)}
          name={f.name}
          value={form[f.name]}
          onChange={handleChange}
          type="date"
          slotProps={{ inputLabel: { shrink: true } }}
          fullWidth
          required={f.required}
        />
      );
    }
    return (
      <TextField
        key={f.name}
        label={t(f.labelKey)}
        name={f.name}
        value={form[f.name]}
        onChange={handleChange}
        fullWidth
        required={f.required}
      />
    );
  };

  const renderDialog = () => (
    <SystemDialog
      open={dialogOpen}
      title={editing ? t(def.editTitleKey) : t(def.createTitleKey)}
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
        {(def.form || []).map(renderField)}
      </Stack>
    </SystemDialog>
  );

  if (!def) {
    return <EmptyState title={t('referenceDataEmpty')} description={t('referenceDataEmptyDesc')} />;
  }

  return (
    <Box>
      {/* Reference-list selector (dropdown) + add action */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1.5, flexWrap: 'wrap' }}>
        <TextField
          select
          size="small"
          label={t('referenceSelectLabel')}
          value={def.key}
          onChange={(e) => setSelectedKey(e.target.value)}
          sx={{ minWidth: 220 }}
        >
          {definitions.map((d) => (
            <MenuItem key={d.key} value={d.key}>{t(d.labelKey)}</MenuItem>
          ))}
        </TextField>
        <Typography sx={{ flex: 1, fontSize: '0.75rem', color: 'text.secondary' }}>
          {t(def.descriptionKey)}
        </Typography>
        <Button variant="contained" size="small" startIcon={<AddIcon />} onClick={openCreate}>
          {t(def.addLabelKey)}
        </Button>
      </Box>

      {loading ? (
        <LoadingSkeleton variant="console" />
      ) : error ? (
        <ErrorAlert message={error} onRetry={loadData} />
      ) : rows.length === 0 ? (
        <EmptyState
          icon={<def.icon />}
          title={t(def.emptyTitleKey)}
          description={t(def.emptyDescKey)}
          actionLabel={t(def.addLabelKey)}
          onAction={openCreate}
        />
      ) : (
        <>
          <Typography
            sx={{ mb: 1, color: 'text.secondary', fontWeight: 700, fontSize: '0.6875rem', textTransform: 'uppercase', letterSpacing: '0.07em' }}
          >
            {t(def.labelKey)} ({rows.length})
          </Typography>
          <StandardDataGrid rows={rows} columns={columns} loading={loading} pageSize={25} sx={{ height: 480 }} />
        </>
      )}

      {renderDialog()}

      <ConfirmDialog
        open={!!deleteTarget}
        message={t(def.deleteConfirmKey)}
        confirmLabel={tCommon('delete')}
        destructive
        onConfirm={confirmDelete}
        onCancel={() => setDeleteTarget(null)}
      />

      <Snackbar
        open={snackbar.open}
        autoHideDuration={5000}
        onClose={closeSnackbar}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert severity={snackbar.severity} variant="filled" sx={{ width: '100%' }}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
}
