// src/pages/catalog/DataSourcesDetailPage.jsx
// Data Sources: Enhanced CRUD with test functionality and status indicators
import React, { useEffect, useState } from 'react';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import {
  Box, Typography, Button, Table, TableHead, TableRow, TableCell, TableBody,
  IconButton, Dialog, DialogTitle, DialogContent, DialogActions, TextField,
  CircularProgress, Alert, Chip, Paper, Card, CardContent, CardHeader, MenuItem, Select, FormControl, InputLabel
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import AddIcon from '@mui/icons-material/Add';
import StorageIcon from '@mui/icons-material/Storage';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import { fetchDataSources, createDataSource, updateDataSource, deleteDataSource, testDataSource } from '../../api/catalog';

const EMPTY_FORM = { name: '', source_type: 'database', description: '' };
const SOURCE_TYPES = ['excel', 'database', 'api', 'iot', 'mdm', 'manual'];

export default function DataSourcesDetailPage() {
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

  useEffect(() => {
    loadSources();
  }, [token]);

  const loadSources = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchDataSources(token);
      setSources(data || []);
    } catch (err) {
      const msg = err.message || 'Failed to load data sources';
      setError(msg);
      notify({ message: msg, type: 'error' });
    } finally {
      setLoading(false);
    }
  };

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

  const handleDelete = async (source) => {
    if (!window.confirm(`Delete data source "${source.name}"?`)) return;
    try {
      await deleteDataSource(token, source.id);
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

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <StorageIcon sx={{ fontSize: '2rem', color: 'primary.main' }} />
          <Box>
            <Typography variant="h5" fontWeight={700}>Data Sources</Typography>
            <Typography variant="body2" color="text.secondary">Source system connections</Typography>
          </Box>
        </Box>
        <Button variant="contained" startIcon={<AddIcon />} onClick={openCreate}>
          New Source
        </Button>
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <Paper>
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
              sources.map(source => (
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
                    <Button
                      size="small"
                      onClick={() => handleTest(source.id)}
                      disabled={testingId === source.id}
                      sx={{ mr: 1 }}
                    >
                      {testingId === source.id ? 'Testing...' : 'Test'}
                    </Button>
                    <IconButton size="small" onClick={() => openEdit(source)}>
                      <EditIcon fontSize="small" />
                    </IconButton>
                    <IconButton size="small" onClick={() => handleDelete(source)}>
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </Paper>

      <Dialog open={openDialog} onClose={() => setOpenDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editingSource ? 'Edit Data Source' : 'New Data Source'}</DialogTitle>
        <DialogContent sx={{ pt: 2 }}>
          <TextField
            fullWidth
            label="Name"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            margin="normal"
          />
          <FormControl fullWidth margin="normal">
            <InputLabel>Source Type</InputLabel>
            <Select
              value={formData.source_type}
              label="Source Type"
              onChange={(e) => setFormData({ ...formData, source_type: e.target.value })}
            >
              {SOURCE_TYPES.map(type => (
                <MenuItem key={type} value={type}>{type}</MenuItem>
              ))}
            </Select>
          </FormControl>
          <TextField
            fullWidth
            label="Description"
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            margin="normal"
            multiline
            rows={3}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenDialog(false)}>Cancel</Button>
          <Button onClick={handleSave} variant="contained" disabled={saving}>
            {saving ? 'Saving...' : 'Save'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
