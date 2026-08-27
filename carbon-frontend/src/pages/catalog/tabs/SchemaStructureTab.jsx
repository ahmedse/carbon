import React, { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
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
import ConfirmDialog from '../../../components/ConfirmDialog';
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
  const { t } = useTranslation('catalog');
  const navigate = useNavigate();
  const { token, user, context } = useAuth();
  const { notify } = useNotification();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingField, setEditingField] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null); // { kind: 'field' | 'table', item }
  const [working, setWorking] = useState(false);

  const effectiveIsAdmin = Boolean(
    isAdmin !== undefined
      ? isAdmin
      : user?.is_superuser ||
        (user?.roles || []).some((role) => role?.active !== false && (role.role === 'admins_group' || role.role === 'admin'))
  );

  // Parity with legacy Schema Manager: block schema edits once a table has data
  const hasData = Number(table?.row_count ?? 0) > 0;

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
        notify({ message: t('fieldUpdated'), type: 'success' });
      } else {
        await createDataSchemaField(token, payload, context?.project_id || null, table?.module || table?.module_id || null);
        notify({ message: t('fieldCreated'), type: 'success' });
      }
      setDialogOpen(false);
      setEditingField(null);
      if (onChanged) await onChanged();
    } catch (err) {
      notify({ message: err.message || t('failedToSaveField'), type: 'error' });
    } finally {
      setWorking(false);
    }
  };

  const handleDeleteField = (field) => setDeleteTarget({ kind: 'field', item: field });

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setWorking(true);
    try {
      if (deleteTarget.kind === 'field') {
        const field = deleteTarget.item;
        await deleteDataSchemaField(token, field.id, context?.project_id || null, table?.module || table?.module_id || null);
        notify({ message: t('fieldDeleted'), type: 'success' });
      } else {
        await deleteDataSchemaTable(token, tableId, context?.project_id || null, table?.module || table?.module_id || null);
        notify({ message: t('tableDeleted'), type: 'success' });
        navigate('/catalog/products');
        return;
      }
      if (onChanged) await onChanged();
    } catch (err) {
      notify({ message: err.message || t('failedToDelete'), type: 'error' });
    } finally {
      setWorking(false);
      setDeleteTarget(null);
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
      notify({ message: t('fieldOrderUpdated'), type: 'success' });
      if (onChanged) await onChanged();
    } catch (err) {
      notify({ message: err.message || t('failedToUpdateFieldOrder'), type: 'error' });
    } finally {
      setWorking(false);
    }
  };

  const handleDeleteTable = () => setDeleteTarget({ kind: 'table', item: null });

  return (
    <DetailTabContent>
      <Stack spacing={2}>
        <Paper variant="outlined" sx={{ p: 2.5 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 1.5 }}>
            <Box>
              <Typography variant="h6">{table?.title || t('table')}</Typography>
              <Typography variant="body2" color="text.secondary">
                {table?.description || t('noDescriptionProvided')}
              </Typography>
            </Box>
            {effectiveIsAdmin && (
              <Stack direction="row" spacing={1}>
                <Button variant="outlined" onClick={onEditMetadata} disabled={working}>
                  {t('editMetadata')}
                </Button>
                <Tooltip title={hasData ? t('tableHasData') : ''}>
                  <span>
                    <Button variant="contained" color="error" onClick={handleDeleteTable} disabled={working || hasData}>
                      {t('deleteTable')}
                    </Button>
                  </span>
                </Tooltip>
              </Stack>
            )}
          </Box>
        </Paper>

        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="subtitle1" fontWeight={600}>{t('fields')}</Typography>
          {effectiveIsAdmin && (
            <Tooltip title={hasData ? t('tableHasData') : ''}>
              <span>
                <Button variant="contained" startIcon={<AddIcon />} onClick={handleOpenCreate} disabled={working || hasData}>
                  {t('addField')}
                </Button>
              </span>
            </Tooltip>
          )}
        </Box>

        {visibleFields.length === 0 ? (
          <Alert severity="info">
            {effectiveIsAdmin ? t('noFieldsYet') : t('noFieldsDefined')}
          </Alert>
        ) : (
          <Paper variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow sx={{ bgcolor: 'action.hover' }}>
                  <TableCell sx={{ fontWeight: 600 }}>{t('order')}</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>{t('name')}</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>{t('label')}</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>{t('type')}</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>{t('required')}</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>{t('description')}</TableCell>
                  {effectiveIsAdmin && <TableCell sx={{ fontWeight: 600 }}>{t('actions')}</TableCell>}
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
                    <TableCell>{field.required ? t('yes') : t('no')}</TableCell>
                    <TableCell>{field.description || '—'}</TableCell>
                    {effectiveIsAdmin && (
                      <TableCell>
                        <Stack direction="row" spacing={0.5}>
                          <Tooltip title={hasData ? t('tableHasData') : t('moveUp')}>
                            <span>
                              <IconButton size="small" onClick={() => handleReorder(field, 'up')} disabled={working || hasData}>
                                <ArrowUpwardIcon fontSize="small" />
                              </IconButton>
                            </span>
                          </Tooltip>
                          <Tooltip title={hasData ? t('tableHasData') : t('moveDown')}>
                            <span>
                              <IconButton size="small" onClick={() => handleReorder(field, 'down')} disabled={working || hasData}>
                                <ArrowDownwardIcon fontSize="small" />
                              </IconButton>
                            </span>
                          </Tooltip>
                          <Tooltip title={hasData ? t('tableHasData') : t('edit')}>
                            <span>
                              <IconButton size="small" onClick={() => handleOpenEdit(field)} disabled={working || hasData}>
                                <EditIcon fontSize="small" />
                              </IconButton>
                            </span>
                          </Tooltip>
                          <Tooltip title={hasData ? t('tableHasData') : t('delete')}>
                            <span>
                              <IconButton size="small" color="error" onClick={() => handleDeleteField(field)} disabled={working || hasData}>
                                <DeleteIcon fontSize="small" />
                              </IconButton>
                            </span>
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

      <ConfirmDialog
        open={!!deleteTarget}
        title={deleteTarget?.kind === 'table' ? t('deleteTableTitle') : t('deleteFieldTitle')}
        message={
          deleteTarget?.kind === 'table'
            ? t('deleteTableMessage', { name: table?.title || t('thisTable') })
            : t('deleteFieldMessage', { name: deleteTarget?.item?.label || deleteTarget?.item?.name })
        }
        confirmLabel={t('delete')}
        destructive
        onConfirm={confirmDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </DetailTabContent>
  );
}
