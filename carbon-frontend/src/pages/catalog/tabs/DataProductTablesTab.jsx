// src/pages/catalog/tabs/DataProductTablesTab.jsx
// Data Product Tables Tab: compact DataGrid of the product's tables with
// create/edit/delete (admin-gated). Follows ReferenceSetValuesTab + FilteredDataGrid
// conventions (density="compact", ConfirmDialog, useNotification, CB-09 arrays).
import React, { useState, useMemo } from 'react';
import {
  Box, Button, Chip, IconButton, Tooltip, Typography, Alert, TextField,
} from '@mui/material';
import { DataGrid } from '@mui/x-data-grid';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import VisibilityIcon from '@mui/icons-material/Visibility';
import { useNavigate } from 'react-router-dom';
import { DetailTabContent } from '../../../components/detail/DetailMainPanel';
import { useNotification } from '../../../components/NotificationProvider';
import ConfirmDialog from '../../../components/ConfirmDialog';
import SystemDialog from '../../../components/SystemDialog';
import { useAuth } from '../../../auth/AuthContext';
import { createDataSchemaTable, updateDataSchemaTable, deleteDataSchemaTable } from '../../../api/dataschema';

const QUALITY_COLOR = { passing: 'success', warning: 'warning', failing: 'error', unknown: 'default' };

function formatDate(value) {
  if (!value) return '—';
  const d = new Date(value);
  return Number.isNaN(d.getTime())
    ? '—'
    : d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

export default function DataProductTablesTab({ entityData, additionalProps = {} }) {
  const navigate = useNavigate();
  const { token } = useAuth();
  const { notify } = useNotification();
  const {
    tables = [],
    assets = {},
    isAdmin = false,
    onDataChanged = null,
  } = additionalProps;

  const [searchText, setSearchText] = useState('');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingTable, setEditingTable] = useState(null);
  const [formData, setFormData] = useState({ title: '', description: '' });
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);

  const rows = useMemo(() => tables.map((t) => ({ ...t, quality: assets[t.id]?.quality_status || 'unknown' })), [tables, assets]);

  const filteredRows = useMemo(() => {
    const s = searchText.trim().toLowerCase();
    if (!s) return rows;
    return rows.filter((r) =>
      (r.title || '').toLowerCase().includes(s) ||
      (r.description || '').toLowerCase().includes(s) ||
      (r.module_name || '').toLowerCase().includes(s)
    );
  }, [rows, searchText]);

  const columns = useMemo(() => [
    {
      field: 'title',
      headerName: 'Title',
      flex: 1.4,
      minWidth: 180,
      renderCell: (params) => (
        <Button
          size="small"
          sx={{ textTransform: 'none', justifyContent: 'flex-start', p: 0, minWidth: 0 }}
          onClick={() => navigate(`/catalog/tables/${params.row.id}`)}
        >
          {params.row.title}
        </Button>
      ),
    },
    {
      field: 'description',
      headerName: 'Description',
      flex: 1.6,
      minWidth: 200,
      valueGetter: (value, row) => row.description || '—',
    },
    {
      field: 'row_count',
      headerName: 'Rows',
      width: 90,
      align: 'right',
      headerAlign: 'right',
      valueGetter: (value, row) => row.row_count ?? 0,
    },
    {
      field: 'quality',
      headerName: 'Quality',
      width: 120,
      renderCell: (params) => (
        <Chip label={params.value} size="small" color={QUALITY_COLOR[params.value] || 'default'} variant="outlined" />
      ),
    },
    {
      field: 'updated_at',
      headerName: 'Modified',
      width: 160,
      valueGetter: (value, row) => row.updated_at || null,
      valueFormatter: (value) => formatDate(value),
    },
    ...(isAdmin
      ? [{
          field: 'actions',
          headerName: 'Actions',
          width: 130,
          sortable: false,
          renderCell: (params) => (
            <Box sx={{ display: 'flex', gap: 0.5 }}>
              <Tooltip title="Open table">
                <IconButton size="small" onClick={() => navigate(`/catalog/tables/${params.row.id}`)}>
                  <VisibilityIcon fontSize="small" />
                </IconButton>
              </Tooltip>
              <Tooltip title="Edit metadata">
                <IconButton size="small" onClick={() => openEdit(params.row)}>
                  <EditIcon fontSize="small" />
                </IconButton>
              </Tooltip>
              <Tooltip title="Delete">
                <IconButton size="small" onClick={() => setDeleteTarget(params.row)} sx={{ color: 'error.main' }}>
                  <DeleteIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            </Box>
          ),
        }]
      : []),
  ], [navigate, isAdmin]);

  if (!entityData) {
    return (
      <DetailTabContent>
        <Typography variant="body2" color="text.secondary">No data available</Typography>
      </DetailTabContent>
    );
  }

  const openCreate = () => {
    setEditingTable(null);
    setFormData({ title: '', description: '' });
    setFormError(null);
    setDialogOpen(true);
  };

  const openEdit = (t) => {
    setEditingTable(t);
    setFormData({ title: t.title || '', description: t.description || '' });
    setFormError(null);
    setDialogOpen(true);
  };

  const closeDialog = () => {
    if (!submitting) { setDialogOpen(false); setEditingTable(null); setFormError(null); }
  };

  const handleSave = async () => {
    if (!formData.title.trim()) { setFormError('Title is required'); return; }
    setSubmitting(true);
    setFormError(null);
    try {
      const payload = {
        title: formData.title.trim(),
        description: formData.description.trim(),
        module: Number(entityData.id),
      };
      if (editingTable) {
        await updateDataSchemaTable(token, editingTable.id, payload, null, Number(entityData.id));
        notify({ message: 'Table updated', type: 'success' });
      } else {
        const created = await createDataSchemaTable(token, payload, null, Number(entityData.id));
        notify({ message: 'Table created', type: 'success' });
        closeDialog();
        if (created?.id) { navigate(`/catalog/tables/${created.id}`); return; }
      }
      closeDialog();
      if (onDataChanged) await onDataChanged();
    } catch (err) {
      setFormError(err.message || 'Save failed');
      notify({ message: err.message || 'Save failed', type: 'error' });
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      await deleteDataSchemaTable(token, deleteTarget.id, null, Number(entityData.id));
      notify({ message: 'Table deleted', type: 'success' });
      setDeleteTarget(null);
      if (onDataChanged) await onDataChanged();
    } catch (err) {
      notify({ message: err.message || 'Delete failed', type: 'error' });
    }
  };

  return (
    <DetailTabContent>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2, gap: 2, flexWrap: 'wrap' }}>
        <Typography variant="subtitle2" fontWeight={600}>
          Tables ({tables.length})
        </Typography>
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
          <TextField
            size="small"
            placeholder="Search tables…"
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            sx={{ width: 240 }}
          />
          {isAdmin && (
            <Button variant="contained" size="small" startIcon={<AddIcon />} onClick={openCreate}>
              New Table
            </Button>
          )}
        </Box>
      </Box>

      {tables.length === 0 ? (
        <Alert severity="info" sx={{ mb: 2 }}>No tables in this data product yet.</Alert>
      ) : (
        <Box sx={{ height: 420, width: '100%' }}>
          <DataGrid
            rows={filteredRows}
            columns={columns}
            density="compact"
            pageSizeOptions={[10, 25, 50]}
            initialState={{ pagination: { paginationModel: { pageSize: 10 } } }}
            disableRowSelectionOnClick
          />
        </Box>
      )}

      {/* Create/Edit table dialog (SystemDialog — CB-14) */}
      <SystemDialog
        open={dialogOpen}
        title={editingTable ? 'Edit Table' : 'New Table'}
        onClose={closeDialog}
        onCancel={closeDialog}
        cancelLabel="Cancel"
        width={480}
        height={320}
        minWidth={400}
        minHeight={280}
        maxWidth="calc(100vw - 32px)"
        maxHeight="calc(100vh - 32px)"
        actions={
          <Button variant="contained" size="small" onClick={handleSave} disabled={submitting}>
            {submitting ? 'Saving…' : 'Save'}
          </Button>
        }
      >
        <Box px={2} py={1}>
          {formError && <Alert severity="error" sx={{ mb: 2 }}>{formError}</Alert>}
          <TextField
            fullWidth label="Title" size="small" autoFocus required
            value={formData.title}
            onChange={(e) => setFormData({ ...formData, title: e.target.value })}
            sx={{ mb: 2 }}
          />
          <TextField
            fullWidth label="Description" size="small" multiline rows={3}
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
          />
        </Box>
      </SystemDialog>

      {/* Delete confirmation */}
      <ConfirmDialog
        open={!!deleteTarget}
        title="Delete table?"
        message={`Delete table "${deleteTarget?.title}"? This action cannot be undone.`}
        confirmLabel="Delete"
        destructive
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </DetailTabContent>
  );
}
