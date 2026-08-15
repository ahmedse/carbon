// src/pages/catalog/DataSourcesDetailPage.jsx
// Data Sources: Enhanced CRUD with test functionality and status indicators
import React, { useEffect, useMemo, useState, useCallback } from 'react';
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

const EMPTY_FORM = { name: '', source_type: 'database', description: '' };
const SOURCE_TYPES = ['excel', 'database', 'api', 'iot', 'mdm', 'manual'];

export default function DataSourcesDetailPage() {
  useDocumentTitle("Data Sources");
  const { token } = useAuth();
  const { notify } = useNotification();

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
      const msg = err.message || 'Failed to load data sources';
      setError(msg);
      notify({ message: msg, type: 'error' });
    } finally {
      setLoading(false);
    }
  }, [token, notify]);

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
      notify({ message: 'Name is required', type: 'error' });
      return;
    }

    setSaving(true);
    setError(null);
    try {
      if (editingSource) {
        await updateDataSource(token, editingSource.id, formData);
        notify({ message: 'Data source updated', type: 'success' });
      } else {
        await createDataSource(token, formData);
        notify({ message: 'Data source created', type: 'success' });
      }
      setOpenDialog(false);
      loadSources();
    } catch (err) {
      const msg = err.message || 'Save failed';
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
      notify({ message: 'Data source deleted', type: 'success' });
      loadSources();
    } catch (err) {
      setError(err.message || 'Delete failed');
      notify({ message: err.message || 'Delete failed', type: 'error' });
    }
  };

  const handleTest = async (sourceId) => {
    setTestingId(sourceId);
    try {
      await testDataSource(token, sourceId);
      notify({ message: 'Connection test successful', type: 'success' });
      loadSources();
    } catch (err) {
      notify({ message: `Connection test failed: ${err.message}`, type: 'error' });
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
      { title: 'Sources', value: sources.length },
      { title: 'Active', value: sources.filter((source) => source.status === 'active').length },
      { title: 'Error', value: sources.filter((source) => source.status === 'error').length },
      { title: 'Pending', value: sources.filter((source) => !source.status).length },
    ],
    [sources]
  );

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
        <Button variant="outlined" startIcon={<AddIcon />} onClick={openCreate}>New Source</Button>
      </Box>
      <Paper variant="outlined">
        <Table>
          <TableHead>
            <TableRow sx={{ backgroundColor: 'action.hover' }}>
              <TableCell fontWeight={600}>Name</TableCell>
              <TableCell fontWeight={600}>Type</TableCell>
              <TableCell fontWeight={600}>Status</TableCell>
              <TableCell fontWeight={600}>Last Tested</TableCell>
              <TableCell fontWeight={600} align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {sources.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} align="center" sx={{ py: 3 }}>
                  <Typography color="text.secondary">No data sources yet</Typography>
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
                      <Typography variant="caption">{source.status || 'unknown'}</Typography>
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Typography variant="caption">
                      {source.last_tested_at ? new Date(source.last_tested_at).toLocaleDateString() : '—'}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Button size="small" onClick={() => handleTest(source.id)} disabled={testingId === source.id} sx={{ mr: 1 }}>
                      {testingId === source.id ? 'Testing...' : 'Test'}
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
      title="Data Sources"
      description="Source system connections"
      icon={StorageIcon}
      onClose={() => window.history.back()}
    />
  );

  return (
    <>
      {error && <Alert severity="error" sx={{ m: 3, mb: 0 }}>{error}</Alert>}
      <BaseDetailPage
        headerComponent={headerComponent}
        mainTabs={[{ label: 'Inventory', component: InventoryTab }]}
        metricsTabs={[{ label: 'Summary', component: () => <Box sx={{ p: 2 }}>{summaryCards.map((card) => <Box key={card.title} sx={{ p: 2, mb: 1, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}><Typography variant="caption" color="text.secondary">{card.title}</Typography><Typography variant="h6">{card.value}</Typography></Box>)}</Box> }]}
        loading={loading}
        error={error}
        onClose={() => window.history.back()}
        storageKey="carbonDataSourcesDetail"
        entityData={{ sources }}
      />

      <SystemDialog
        open={openDialog}
        title={editingSource ? 'Edit Data Source' : 'New Data Source'}
        onClose={() => setOpenDialog(false)}
        onCancel={() => setOpenDialog(false)}
        cancelLabel="Cancel"
        width={480}
        height={420}
        minWidth={400}
        minHeight={340}
        maxWidth="calc(100vw - 32px)"
        maxHeight="calc(100vh - 32px)"
        actions={
          <Button onClick={handleSave} variant="contained" size="small" disabled={saving}>
            {saving ? 'Saving...' : 'Save'}
          </Button>
        }
      >
        <Box px={2} py={1}>
          <TextField
            fullWidth
            size="small"
            label="Name"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            margin="normal"
          />
          <FormControl fullWidth margin="normal" size="small">
            <InputLabel>Source Type</InputLabel>
            <Select
              value={formData.source_type}
              label="Source Type"
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
            label="Description"
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
        title="Delete data source?"
        message={`Delete data source "${deleteTarget?.name || 'this source'}"? This action cannot be undone.`}
        confirmLabel="Delete"
        destructive
        onConfirm={confirmDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </>
  );
}
