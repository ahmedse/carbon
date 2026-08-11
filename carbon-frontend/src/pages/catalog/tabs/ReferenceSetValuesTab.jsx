// src/pages/catalog/tabs/ReferenceSetValuesTab.jsx
// Reference Set Values Tab: CRUD management of reference values with temporal validity

import React, { useState } from 'react';
import { 
  Box, Button, TextField,
  IconButton, Tooltip, Chip, Typography, Alert
} from '@mui/material';
import SystemDialog from '../../../components/SystemDialog';
import { DataGrid } from '@mui/x-data-grid';
import { DetailTabContent } from '../../../components/detail/DetailMainPanel';
import { useAuth } from '../../../auth/AuthContext';
import { useNotification } from '../../../components/NotificationProvider';
import { createReferenceValue, updateReferenceValue, deleteReferenceValue } from '../../../api/catalog';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import dayjs from 'dayjs';
import ConfirmDialog from '../../../components/ConfirmDialog';

const EMPTY_FORM = {
  code: '',
  label: '',
  description: '',
  is_active: true,
  sort_order: 0,
  valid_from: null,
  valid_to: null,
};

// Map DRF field-error payload ({field: [msg]}) to {field: msg} for per-field display.
function mapFieldErrors(err) {
  const data = err?.data;
  if (!data || typeof data !== 'object' || Array.isArray(data)) return null;
  const fieldErrors = {};
  Object.entries(data).forEach(([key, value]) => {
    if (key === 'non_field_errors') return;
    if (Array.isArray(value)) fieldErrors[key] = value[0];
    else if (typeof value === 'string') fieldErrors[key] = value;
  });
  return Object.keys(fieldErrors).length ? fieldErrors : null;
}

export default function ReferenceSetValuesTab({ entityData, additionalProps = {} }) {
  const { token } = useAuth();
  const { notify } = useNotification();
  const { values = [], onValuesUpdated = null } = additionalProps;

  const [openDialog, setOpenDialog] = useState(false);
  const [editingValue, setEditingValue] = useState(null);
  const [formData, setFormData] = useState(EMPTY_FORM);
  const [fieldErrors, setFieldErrors] = useState({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [confirmState, setConfirmState] = useState(null);

  const handleOpenCreate = () => {
    setEditingValue(null);
    setFormData(EMPTY_FORM);
    setFieldErrors({});
    setOpenDialog(true);
  };

  const handleOpenEdit = (value) => {
    setEditingValue(value);
    setFormData({
      code: value.code || '',
      label: value.label || '',
      description: value.description || '',
      is_active: value.is_active !== undefined ? value.is_active : true,
      sort_order: value.sort_order || 0,
      valid_from: value.valid_from ? dayjs(value.valid_from) : null,
      valid_to: value.valid_to ? dayjs(value.valid_to) : null,
    });
    setFieldErrors({});
    setOpenDialog(true);
  };

  const handleCloseDialog = () => {
    setOpenDialog(false);
    setEditingValue(null);
    setFormData(EMPTY_FORM);
    setFieldErrors({});
    setError(null);
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleDateChange = (name, value) => {
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSave = async () => {
    // Client-side validation
    const errors = {};
    if (!formData.code.trim()) errors.code = 'Code is required.';
    if (!formData.label.trim()) errors.label = 'Label is required.';
    if (
      formData.valid_from &&
      formData.valid_to &&
      formData.valid_from.isAfter(formData.valid_to, 'day')
    ) {
      errors.valid_to = 'Valid To must be on or after Valid From.';
    }
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    setSaving(true);
    setError(null);

    try {
      const payload = {
        ...(editingValue ? {} : { reference_set: entityData.id }),
        code: formData.code,
        label: formData.label,
        description: formData.description,
        is_active: formData.is_active,
        sort_order: parseInt(formData.sort_order) || 0,
        valid_from: formData.valid_from ? formData.valid_from.format('YYYY-MM-DD') : null,
        valid_to: formData.valid_to ? formData.valid_to.format('YYYY-MM-DD') : null,
      };

      if (editingValue) {
        await updateReferenceValue(token, editingValue.id, payload);
        notify({ message: 'Reference value updated', type: 'success' });
      } else {
        await createReferenceValue(token, payload);
        notify({ message: 'Reference value created', type: 'success' });
      }

      handleCloseDialog();
      if (onValuesUpdated) {
        onValuesUpdated();
      }
    } catch (err) {
      const mapped = mapFieldErrors(err);
      if (mapped) {
        setFieldErrors(mapped);
      } else {
        const message = err.message || 'Failed to save reference value';
        setError(message);
        notify({ message, type: 'error' });
      }
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = (row) => {
    setConfirmState({
      title: 'Delete reference value',
      message: `Delete value "${row.code}" (${row.label})?\nThis action cannot be undone.`,
      destructive: true,
      confirmLabel: 'Delete',
      onConfirm: async () => {
        try {
          await deleteReferenceValue(token, row.id);
          notify({ message: 'Reference value deleted', type: 'success' });
          if (onValuesUpdated) {
            onValuesUpdated();
          }
        } catch (err) {
          notify({ message: err.message || 'Failed to delete', type: 'error' });
        }
      },
    });
  };

  const columns = [
    { 
      field: 'code', 
      headerName: 'Code', 
      flex: 1, 
      minWidth: 140,
      renderCell: (params) => (
        <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
          {params.value}
        </Typography>
      ),
    },
    { field: 'label', headerName: 'Label', flex: 2, minWidth: 200 },
    { 
      field: 'description', 
      headerName: 'Description', 
      flex: 2, 
      minWidth: 220,
      renderCell: (params) => params.value || '—',
    },
    {
      field: 'is_active',
      headerName: 'Status',
      width: 100,
      renderCell: (params) => (
        <Chip
          label={params.value ? 'Active' : 'Inactive'}
          size="small"
          color={params.value ? 'success' : 'default'}
          variant="outlined"
        />
      ),
    },
    {
      field: 'sort_order',
      headerName: 'Order',
      width: 80,
    },
    {
      field: 'valid_from',
      headerName: 'Valid From',
      width: 120,
      renderCell: (params) =>
        params.value ? new Date(params.value).toLocaleDateString() : '—',
    },
    {
      field: 'valid_to',
      headerName: 'Valid To',
      width: 120,
      renderCell: (params) =>
        params.value ? new Date(params.value).toLocaleDateString() : '—',
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 120,
      sortable: false,
      renderCell: (params) => (
        <Box sx={{ display: 'flex', gap: 0.5 }}>
          <Tooltip title="Edit">
            <IconButton size="small" onClick={() => handleOpenEdit(params.row)}>
              <EditIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Delete">
            <IconButton
              size="small"
              color="error"
              onClick={() => handleDelete(params.row)}
            >
              <DeleteIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      ),
    },
  ];

  return (
    <DetailTabContent>
      <Box sx={{ mb: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="subtitle2" fontWeight={600}>
          Reference Values ({values.length})
        </Typography>
        <Button
          variant="contained"
          size="small"
          startIcon={<AddIcon />}
          onClick={handleOpenCreate}
        >
          Add Value
        </Button>
      </Box>

      <Box sx={{ height: 500, width: '100%' }}>
        <DataGrid
          rows={values}
          columns={columns}
          pageSizeOptions={[10, 25, 50]}
          initialState={{
            pagination: { paginationModel: { pageSize: 25 } },
          }}
          disableRowSelectionOnClick
        />
      </Box>

      {/* Create/Edit dialog (SystemDialog — design system primitive) */}
      <SystemDialog
        open={openDialog}
        title={editingValue ? 'Edit Reference Value' : 'Create Reference Value'}
        onClose={handleCloseDialog}
        onCancel={handleCloseDialog}
        cancelLabel="Cancel"
        width={520}
        height={560}
        minWidth={440}
        minHeight={440}
        maxWidth="calc(100vw - 32px)"
        maxHeight="calc(100vh - 32px)"
        actions={
          <Button onClick={handleSave} variant="contained" size="small" disabled={saving}>
            {saving ? 'Saving...' : 'Save'}
          </Button>
        }
      >
        <Box px={2} py={1}>
          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

          <TextField
            fullWidth
            size="small"
            label="Code"
            name="code"
            value={formData.code}
            onChange={handleChange}
            margin="normal"
            required
            error={Boolean(fieldErrors.code)}
            helperText={fieldErrors.code || 'Alphanumeric identifier (e.g., SCOPE_1)'}
          />

          <TextField
            fullWidth
            size="small"
            label="Label"
            name="label"
            value={formData.label}
            onChange={handleChange}
            margin="normal"
            required
            error={Boolean(fieldErrors.label)}
            helperText={fieldErrors.label || 'Human-readable display name'}
          />

          <TextField
            fullWidth
            size="small"
            label="Description"
            name="description"
            value={formData.description}
            onChange={handleChange}
            margin="normal"
            multiline
            rows={2}
            error={Boolean(fieldErrors.description)}
            helperText={fieldErrors.description}
          />

          <TextField
            fullWidth
            size="small"
            label="Sort Order"
            name="sort_order"
            type="number"
            value={formData.sort_order}
            onChange={handleChange}
            margin="normal"
            error={Boolean(fieldErrors.sort_order)}
            helperText={fieldErrors.sort_order || 'Display order (lower numbers appear first)'}
          />

          <Box sx={{ mt: 2, display: 'flex', gap: 2 }}>
            <DatePicker
              label="Valid From"
              value={formData.valid_from}
              onChange={(value) => handleDateChange('valid_from', value)}
              slotProps={{ textField: { error: Boolean(fieldErrors.valid_from), helperText: fieldErrors.valid_from, size: 'small', fullWidth: true } }}
              sx={{ flex: 1 }}
            />
            <DatePicker
              label="Valid To"
              value={formData.valid_to}
              onChange={(value) => handleDateChange('valid_to', value)}
              slotProps={{ textField: { error: Boolean(fieldErrors.valid_to), helperText: fieldErrors.valid_to, size: 'small', fullWidth: true } }}
              sx={{ flex: 1 }}
            />
          </Box>
          <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
            Leave dates blank for values that are always valid
          </Typography>
        </Box>
      </SystemDialog>

      {/* Confirm delete dialog */}
      <ConfirmDialog
        open={Boolean(confirmState)}
        title={confirmState?.title || 'Confirm'}
        message={confirmState?.message || ''}
        destructive={confirmState?.destructive}
        confirmLabel={confirmState?.confirmLabel || 'Confirm'}
        onCancel={() => setConfirmState(null)}
        onConfirm={async () => {
          const { onConfirm } = confirmState || {};
          setConfirmState(null);
          if (onConfirm) await onConfirm();
        }}
      />
    </DetailTabContent>
  );
}
