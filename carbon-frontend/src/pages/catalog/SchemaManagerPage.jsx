// src/pages/catalog/SchemaManagerPage.jsx
// Schema Manager: Admin panel for full CRUD of tables and fields
import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import {
  Box, Typography, Button, Grid, Card, CardHeader, CardContent,
  IconButton, Dialog, DialogTitle, DialogContent, DialogActions, TextField,
  CircularProgress, Alert, Chip, Tooltip
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import AddIcon from '@mui/icons-material/Add';
import VisibilityIcon from '@mui/icons-material/Visibility';
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

      {/* Schema cards grid */}
      {tables.length === 0 ? (
        <Alert severity="info">No tables yet</Alert>
      ) : (
        <Grid container spacing={2}>
          {tables.map((table) => (
            <Grid item xs={12} sm={6} md={4} key={table.id}>
              <Card
                sx={{
                  height: '100%',
                  display: 'flex',
                  flexDirection: 'column',
                  border: '1px solid',
                  borderColor: 'divider',
                }}
              >
                <CardHeader
                  title={table.title}
                  titleTypographyProps={{ variant: 'subtitle1', fontWeight: 600 }}
                  subheader={`${table.fields_count || 0} fields`}
                  action={
                    <Tooltip title="View schema details">
                      <IconButton
                        size="small"
                        color="primary"
                        onClick={() => navigate(`/catalog/schemas/${table.id}`)}
                      >
                        <VisibilityIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  }
                />
                <CardContent sx={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {table.description || 'No description'}
                  </Typography>
                  <Box sx={{ mt: 'auto', display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                    <Chip label={`${table.fields_count || 0} fields`} size="small" variant="outlined" />
                  </Box>
                </CardContent>
                <Box sx={{ px: 2, pb: 2, pt: 1, display: 'flex', justifyContent: 'flex-end', gap: 1 }}>
                  <Tooltip title="Edit metadata">
                    <IconButton size="small" onClick={() => openEdit(table)}>
                      <EditIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Delete">
                    <IconButton size="small" onClick={() => handleDelete(table)}>
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                </Box>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}

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
