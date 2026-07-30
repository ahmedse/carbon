import React, { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  Chip,
  IconButton,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward';
import { useAuth } from '../../../auth/AuthContext';
import { useNotification } from '../../../components/NotificationProvider';
import { DetailTabContent } from '../../../components/detail/DetailMainPanel';
import {
  createDataSchemaField,
  deleteDataSchemaField,
  deleteDataSchemaTable,
  updateDataSchemaField,
  updateDataSchemaFieldOrder,
} from '../../../api/dataschema';
import FieldEditorDialog from './FieldEditorDialog';

function sortFields(fields = []) {
  return [...fields].sort((a, b) => (Number(a.order ?? 0) - Number(b.order ?? 0)) || (Number(a.id ?? 0) - Number(b.id ?? 0)));
}

export default function SchemaStructureTab({ _entityData, tableId, table, fields = [], onChanged, isAdmin, onEditMetadata }) {
  const navigate = useNavigate();
  const { token, user, context } = useAuth();
  const { notify } = useNotification();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingField, setEditingField] = useState(null);
  const [working, setWorking] = useState(false);

  const effectiveIsAdmin = Boolean(
    isAdmin !== undefined
      ? isAdmin
      : user?.is_superuser ||
        (user?.roles || []).some((role) => role?.active !== false && (role.role === 'admins_group' || role.role === 'admin'))
  );

  const visibleFields = useMemo(() => sortFields(fields), [fields]);

  const handleOpenCreate = () => {
    setEditingField(null);
    setDialogOpen(true);
  };

  const handleOpenEdit = (field) => {
    setEditingField(field);
    setDialogOpen(true);
  };

  const handleSaveField = async (payload) => {
    setWorking(true);
    try {
      if (editingField) {
        await updateDataSchemaField(token, editingField.id, payload, context?.project_id || null, table?.module || table?.module_id || null);
        notify({ message: 'Field updated', type: 'success' });
      } else {
        await createDataSchemaField(token, payload, context?.project_id || null, table?.module || table?.module_id || null);
        notify({ message: 'Field created', type: 'success' });
      }
      setDialogOpen(false);
      setEditingField(null);
      if (onChanged) await onChanged();
    } catch (err) {
      notify({ message: err.message || 'Failed to save field', type: 'error' });
    } finally {
      setWorking(false);
    }
  };

  const handleDeleteField = async (field) => {
    if (!window.confirm(`Delete field "${field.label || field.name}"?`)) return;
    setWorking(true);
    try {
      await deleteDataSchemaField(token, field.id, context?.project_id || null, table?.module || table?.module_id || null);
      notify({ message: 'Field deleted', type: 'success' });
      if (onChanged) await onChanged();
    } catch (err) {
      notify({ message: err.message || 'Failed to delete field', type: 'error' });
    } finally {
      setWorking(false);
    }
  };

  const handleReorder = async (field, direction) => {
    const index = visibleFields.findIndex((item) => item.id === field.id);
    if (index < 0) return;
    const targetIndex = direction === 'up' ? index - 1 : index + 1;
    if (targetIndex < 0 || targetIndex >= visibleFields.length) return;

    const reordered = [...visibleFields];
    const [moved] = reordered.splice(index, 1);
    reordered.splice(targetIndex, 0, moved);
    const normalized = reordered.map((item, idx) => ({ ...item, order: idx + 1 }));

    setWorking(true);
    try {
      await updateDataSchemaFieldOrder(token, tableId, normalized, context?.project_id || null, table?.module || table?.module_id || null);
      notify({ message: 'Field order updated', type: 'success' });
      if (onChanged) await onChanged();
    } catch (err) {
      notify({ message: err.message || 'Failed to update field order', type: 'error' });
    } finally {
      setWorking(false);
    }
  };

  const handleDeleteTable = async () => {
    if (!window.confirm(`Delete table "${table?.title || 'this table'}"?`)) return;
    setWorking(true);
    try {
      await deleteDataSchemaTable(token, tableId, context?.project_id || null, table?.module || table?.module_id || null);
      notify({ message: 'Table deleted', type: 'success' });
      navigate('/catalog/products');
    } catch (err) {
      notify({ message: err.message || 'Failed to delete table', type: 'error' });
    } finally {
      setWorking(false);
    }
  };

  return (
    <DetailTabContent>
      <Stack spacing={2}>
        <Paper variant="outlined" sx={{ p: 2.5 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 1.5 }}>
            <Box>
              <Typography variant="h6">{table?.title || 'Table'}</Typography>
              <Typography variant="body2" color="text.secondary">
                {table?.description || 'No description provided.'}
              </Typography>
            </Box>
            {effectiveIsAdmin && (
              <Stack direction="row" spacing={1}>
                <Button variant="outlined" onClick={onEditMetadata} disabled={working}>
                  Edit Metadata
                </Button>
                <Button variant="contained" color="error" onClick={handleDeleteTable} disabled={working}>
                  Delete Table
                </Button>
              </Stack>
            )}
          </Box>
        </Paper>

        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="subtitle1" fontWeight={600}>Fields</Typography>
          {effectiveIsAdmin && (
            <Button variant="contained" startIcon={<AddIcon />} onClick={handleOpenCreate} disabled={working}>
              Add Field
            </Button>
          )}
        </Box>

        {visibleFields.length === 0 ? (
          <Alert severity="info">
            {effectiveIsAdmin ? 'No fields yet — add the first field.' : 'No fields defined.'}
          </Alert>
        ) : (
          <Paper variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow sx={{ bgcolor: 'action.hover' }}>
                  <TableCell sx={{ fontWeight: 600 }}>Order</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>Name</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>Label</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>Type</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>Required</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>Description</TableCell>
                  {effectiveIsAdmin && <TableCell sx={{ fontWeight: 600 }}>Actions</TableCell>}
                </TableRow>
              </TableHead>
              <TableBody>
                {visibleFields.map((field) => (
                  <TableRow key={field.id} hover>
                    <TableCell>{field.order ?? 1}</TableCell>
                    <TableCell>{field.name}</TableCell>
                    <TableCell>{field.label || field.name}</TableCell>
                    <TableCell>
                      <Chip label={field.type || 'string'} size="small" variant="outlined" />
                    </TableCell>
                    <TableCell>{field.required ? 'Yes' : 'No'}</TableCell>
                    <TableCell>{field.description || '—'}</TableCell>
                    {effectiveIsAdmin && (
                      <TableCell>
                        <Stack direction="row" spacing={0.5}>
                          <Tooltip title="Move up">
                            <span>
                              <IconButton size="small" onClick={() => handleReorder(field, 'up')} disabled={working}>
                                <ArrowUpwardIcon fontSize="small" />
                              </IconButton>
                            </span>
                          </Tooltip>
                          <Tooltip title="Move down">
                            <span>
                              <IconButton size="small" onClick={() => handleReorder(field, 'down')} disabled={working}>
                                <ArrowDownwardIcon fontSize="small" />
                              </IconButton>
                            </span>
                          </Tooltip>
                          <Tooltip title="Edit">
                            <IconButton size="small" onClick={() => handleOpenEdit(field)} disabled={working}>
                              <EditIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                          <Tooltip title="Delete">
                            <IconButton size="small" color="error" onClick={() => handleDeleteField(field)} disabled={working}>
                              <DeleteIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        </Stack>
                      </TableCell>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Paper>
        )}
      </Stack>

      <FieldEditorDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        onSave={handleSaveField}
        field={editingField}
        tableId={tableId}
      />
    </DetailTabContent>
  );
}
