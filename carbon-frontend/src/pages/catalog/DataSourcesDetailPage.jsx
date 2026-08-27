// src/pages/catalog/DataSourcesDetailPage.jsx
// Data Sources: Enhanced CRUD with test functionality and status indicators
import React, { useEffect, useMemo, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import SystemDialog from '../../components/SystemDialog';
import ConfirmDialog from '../../components/ConfirmDialog';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  FormControl,
  IconButton,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import useDocumentTitle from '../../hooks/useDocumentTitle';

import AddIcon from '@mui/icons-material/Add';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import ErrorIcon from '@mui/icons-material/Error';
import StorageIcon from '@mui/icons-material/Storage';
import { fetchDataSources, createDataSource, updateDataSource, deleteDataSource, testDataSource } from '../../api/catalog';
import BaseDetailPage from '../../components/detail/BaseDetailPage';
import DetailHeader from '../../components/detail/DetailHeader';
import HomeIcon from '@mui/icons-material/Home';
import { useNotes } from '../../notes/NotesContext';
import { registerDataSourceInspectorTabs } from '../../inspector/tabs/collectionTabs';

const EMPTY_FORM = { name: '', source_type: 'database', description: '' };
const SOURCE_TYPES = ['excel', 'database', 'api', 'iot', 'mdm', 'manual'];

export default function DataSourcesDetailPage() {
  useDocumentTitle("Data Sources");
  const { t } = useTranslation('catalog');
  const { token } = useAuth();
  const { notify } = useNotification();
  const { setContexts } = useNotes();

  const [sources, setSources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [openDialog, setOpenDialog] = useState(false);
  const [editingSource, setEditingSource] = useState(null);
  const [formData, setFormData] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [testingId, setTestingId] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);

  const loadSources = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchDataSources(token);
      setSources(Array.isArray(data) ? data : data?.results || []);
    } catch (err) {
      const msg = err.message || t('dataSourcesLoadError');
      setError(msg);
      notify({ message: msg, type: 'error' });
    } finally {
      setLoading(false);
    }
  }, [token, notify, t]);

  useEffect(() => {
    loadSources();
  }, [loadSources]);

  const openCreate = () => {
    setEditingSource(null);
    setFormData(EMPTY_FORM);
    setOpenDialog(true);
  };

  const openEdit = (source) => {
    setEditingSource(source);
    setFormData({
      name: source.name,
      source_type: source.source_type || 'database',
      description: source.description || ''
    });
    setOpenDialog(true);
  };

  const handleSave = async () => {
    if (!formData.name.trim()) {
      notify({ message: t('nameRequired'), type: 'error' });
      return;
    }

    setSaving(true);
    setError(null);
    try {
      if (editingSource) {
        await updateDataSource(token, editingSource.id, formData);
        notify({ message: t('dataSourceUpdated'), type: 'success' });
      } else {
        await createDataSource(token, formData);
        notify({ message: t('dataSourceCreated'), type: 'success' });
      }
      setOpenDialog(false);
      loadSources();
    } catch (err) {
      const msg = err.message || t('saveFailed');
      setError(msg);
      notify({ message: msg, type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setDeleteTarget(null);
    try {
      await deleteDataSource(token, deleteTarget.id);
      notify({ message: t('dataSourceDeleted'), type: 'success' });
      loadSources();
    } catch (err) {
      setError(err.message || t('deleteFailed'));
      notify({ message: err.message || t('deleteFailed'), type: 'error' });
    }
  };

  const handleTest = async (sourceId) => {
    setTestingId(sourceId);
    try {
      await testDataSource(token, sourceId);
      notify({ message: t('connectionTestSuccess'), type: 'success' });
      loadSources();
    } catch (err) {
      notify({ message: t('connectionTestFailed', { message: err.message }), type: 'error' });
    } finally {
      setTestingId(null);
    }
  };

  const getStatusIcon = (status) => {
    if (status === 'active') return <CheckCircleIcon sx={{ color: 'success.main' }} />;
    if (status === 'error') return <ErrorIcon sx={{ color: 'error.main' }} />;
    return <Typography variant="caption">—</Typography>;
  };

  const summaryCards = useMemo(
    () => [
      { title: t('sources'), value: sources.length },
      { title: t('active'), value: sources.filter((source) => source.status === 'active').length },
      { title: t('errorStatus'), value: sources.filter((source) => source.status === 'error').length },
      { title: t('pending'), value: sources.filter((source) => !source.status).length },
    ],
    [sources, t]
  );

  // ── Contextual Inspector (global drawer) ────────────────────────────
  // Collection pages have no single entity; anchor to a stable sentinel id (0)
  // so the summary tab renders and notes stay scoped to this collection.
  useEffect(() => registerDataSourceInspectorTabs(), []);

  const inspectorContext = useMemo(
    () => [{ entityType: 'data-source', entityId: 0, label: t('dataSources'), payload: { summaryCards } }],
    [summaryCards, t],
  );
  useEffect(() => {
    setContexts(inspectorContext);
    return () => setContexts(null);
  }, [inspectorContext, setContexts]);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  const InventoryTab = () => (
    <Box sx={{ p: 3 }}>
      <Box sx={{ mb: 2 }}>
        <Button variant="outlined" startIcon={<AddIcon />} onClick={openCreate}>{t('newSource')}</Button>
      </Box>
      <Paper variant="outlined">
        <Table>
          <TableHead>
            <TableRow sx={{ backgroundColor: 'action.hover' }}>
              <TableCell fontWeight={600}>{t('name')}</TableCell>
              <TableCell fontWeight={600}>{t('type')}</TableCell>
              <TableCell fontWeight={600}>{t('status')}</TableCell>
              <TableCell fontWeight={600}>{t('lastTested')}</TableCell>
              <TableCell fontWeight={600} align="right">{t('actions')}</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {sources.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} align="center" sx={{ py: 3 }}>
                  <Typography color="text.secondary">{t('noDataSources')}</Typography>
                </TableCell>
              </TableRow>
            ) : (
              sources.map((source) => (
                <TableRow key={source.id} hover>
                  <TableCell fontWeight={500}>{source.name}</TableCell>
                  <TableCell>
                    <Chip label={source.source_type} size="small" variant="outlined" />
                  </TableCell>
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      {getStatusIcon(source.status)}
                      <Typography variant="caption">{source.status || t('unknown')}</Typography>
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Typography variant="caption">
                      {source.last_tested_at ? new Date(source.last_tested_at).toLocaleDateString() : '—'}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Button size="small" onClick={() => handleTest(source.id)} disabled={testingId === source.id} sx={{ mr: 1 }}>
                      {testingId === source.id ? t('testing') : t('test')}
                    </Button>
                    <IconButton size="small" onClick={() => openEdit(source)}>
                      <EditIcon fontSize="small" />
                    </IconButton>
                    <IconButton size="small" onClick={() => setDeleteTarget(source)}>
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </Paper>
    </Box>
  );

  const headerComponent = (
    <DetailHeader
      title={t('dataSources')}
      description={t('dataSourcesDescription')}
      icon={StorageIcon}
      onClose={() => window.history.back()}
    />
  );

  return (
    <>
      {error && <Alert severity="error" sx={{ m: 3, mb: 0 }}>{error}</Alert>}
      <BaseDetailPage
        headerComponent={headerComponent}
        mainTabs={[{ label: t('inventory'), component: InventoryTab }]}
        loading={loading}
        error={error}
        onClose={() => window.history.back()}
        storageKey="carbonDataSourcesDetail"
      />

      <SystemDialog
        open={openDialog}
        title={editingSource ? t('editDataSource') : t('newDataSource')}
        onClose={() => setOpenDialog(false)}
        onCancel={() => setOpenDialog(false)}
        cancelLabel={t('common:cancel')}
        width={480}
        height={420}
        minWidth={400}
        minHeight={340}
        maxWidth="calc(100vw - 32px)"
        maxHeight="calc(100vh - 32px)"
        actions={
          <Button onClick={handleSave} variant="contained" size="small" disabled={saving}>
            {saving ? t('saving') : t('common:save')}
          </Button>
        }
      >
        <Box px={2} py={1}>
          <TextField
            fullWidth
            size="small"
            label={t('name')}
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            margin="normal"
          />
          <FormControl fullWidth margin="normal" size="small">
            <InputLabel>{t('sourceType')}</InputLabel>
            <Select
              value={formData.source_type}
              label={t('sourceType')}
              onChange={(e) => setFormData({ ...formData, source_type: e.target.value })}
            >
              {SOURCE_TYPES.map((type) => (
                <MenuItem key={type} value={type}>{type}</MenuItem>
              ))}
            </Select>
          </FormControl>
          <TextField
            fullWidth
            size="small"
            label={t('description')}
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            margin="normal"
            multiline
            rows={3}
          />
        </Box>
      </SystemDialog>

      <ConfirmDialog
        open={!!deleteTarget}
        title={t('deleteDataSourceTitle')}
        message={t('deleteDataSourceMessage', { name: deleteTarget?.name || t('thisSource') })}
        confirmLabel={t('common:delete')}
        destructive
        onConfirm={confirmDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </>
  );
}
