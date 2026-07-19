// src/pages/catalog/SchemaManagerPage.jsx
// Schema Manager: Admin panel for full CRUD of tables and fields
import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import {
  Box, Typography, Button, Table, TableHead, TableRow, TableCell, TableBody,
  IconButton, Dialog, DialogTitle, DialogContent, DialogActions, TextField,
  CircularProgress, Alert, Chip, Paper
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import AddIcon from '@mui/icons-material/Add';
import StorageIcon from '@mui/icons-material/Storage';
import { fetchDataSchemaTables, createDataSchemaTable, updateDataSchemaTable, deleteDataSchemaTable } from '../../api/dataschema';

const EMPTY_FORM = { title: '', description: '' };

export default function SchemaManagerPage() {
  const navigate = useNavigate();
  const { token } = useAuth();
  const { notify } = useNotification();

  const [tables, setTables] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [openDialog, setOpenDialog] = useState(false);
  const [editingTable, setEditingTable] = useState(null);
  const [formData, setFormData] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    loadTables();
  }, [token]);

  const loadTables = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchDataSchemaTables(token, null, null);
      setTables(data || []);
    } catch (err) {
      const msg = err.message || 'Failed to load tables';
      setError(msg);
      notify({ message: msg, type: 'error' });
    } finally {
      setLoading(false);
    }
  }, [token, notify]);

  const openCreate = () => {
    setEditingTable(null);
    setFormData(EMPTY_FORM);
    setOpenDialog(true);
  };

  const openEdit = (table) => {
    setEditingTable(table);
    setFormData({ title: table.title, description: table.description || '' });
    setOpenDialog(true);
  };

  const handleSave = async () => {
    if (!formData.title.trim()) {
      notify({ message: 'Title is required', type: 'error' });
      return;
    }

    setSaving(true);
    setError(null);
    try {
      if (editingTable) {
        await updateDataSchemaTable(token, editingTable.id, formData, null, null);
        notify({ message: 'Table updated', type: 'success' });
      } else {
        await createDataSchemaTable(token, formData, null, null);
        notify({ message: 'Table created', type: 'success' });
      }
      setOpenDialog(false);
      loadTables();
    } catch (err) {
      const msg = err.message || 'Save failed';
      setError(msg);
      notify({ message: msg, type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (table) => {
    if (!window.confirm(`Delete table "${table.title}"? This cannot be undone.`)) return;

    try {
      await deleteDataSchemaTable(token, table.id, null, null);
      notify({ message: 'Table deleted', type: 'success' });
      loadTables();
    } catch (err) {
      const msg = err.message || 'Delete failed';
      setError(msg);
      notify({ message: msg, type: 'error' });
    }
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
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <StorageIcon sx={{ fontSize: '2rem', color: 'primary.main' }} />
          <Box>
            <Typography variant="h5" fontWeight={700}>Schema Manager</Typography>
            <Typography variant="body2" color="text.secondary">
              Create and manage data tables. Admin-only access.
            </Typography>
          </Box>
        </Box>
        <Button variant="contained" startIcon={<AddIcon />} onClick={openCreate}>
          New Table
        </Button>
      </Box>

      {/* Error Alert */}
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {/* Tables Table */}
      <Paper>
        <Table>
          <TableHead>
            <TableRow sx={{ backgroundColor: 'action.hover' }}>
              <TableCell fontWeight={600}>Title</TableCell>
              <TableCell fontWeight={600}>Description</TableCell>
              <TableCell fontWeight={600}>Fields</TableCell>
              <TableCell fontWeight={600} align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {tables.length === 0 ? (
              <TableRow>
                <TableCell colSpan={4} align="center" sx={{ py: 3 }}>
                  <Typography color="text.secondary">No tables yet</Typography>
                </TableCell>
              </TableRow>
            ) : (
              tables.map(table => (
                <TableRow key={table.id} hover>
                  <TableCell>{table.title}</TableCell>
                  <TableCell>{table.description || '—'}</TableCell>
                  <TableCell>{table.fields_count || 0}</TableCell>
                  <TableCell align="right">
                    <IconButton
                      size="small"
                      onClick={() => navigate(`/catalog/schema-manager/${table.id}`)}
                      title="Edit fields"
                    >
                      <EditIcon fontSize="small" />
                    </IconButton>
                    <IconButton
                      size="small"
                      onClick={() => openEdit(table)}
                      title="Edit metadata"
                    >
                      <EditIcon fontSize="small" />
                    </IconButton>
                    <IconButton
                      size="small"
                      onClick={() => handleDelete(table)}
                      title="Delete"
                    >
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </Paper>

      {/* Create/Edit Dialog */}
      <Dialog open={openDialog} onClose={() => setOpenDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editingTable ? 'Edit Table' : 'New Table'}</DialogTitle>
        <DialogContent sx={{ pt: 2 }}>
          <TextField
            fullWidth
            label="Title"
            value={formData.title}
            onChange={(e) => setFormData({ ...formData, title: e.target.value })}
            margin="normal"
          />
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
          <Button
            onClick={handleSave}
            variant="contained"
            disabled={saving}
          >
            {saving ? 'Saving...' : 'Save'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
