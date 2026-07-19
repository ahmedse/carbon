// src/pages/catalog/ReferenceDataPage.jsx
// Reference Data: CRUD for reference sets (MDM Tier A)
import React, { useEffect, useState } from 'react';
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
import BookIcon from '@mui/icons-material/Book';
import { fetchReferenceSets, createReferenceSet, updateReferenceSet, deleteReferenceSet } from '../../api/catalog';

const EMPTY_FORM = { name: '', description: '' };

export default function ReferenceDataPage() {
  const { token } = useAuth();
  const { notify } = useNotification();

  const [sets, setSets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [openDialog, setOpenDialog] = useState(false);
  const [editingSet, setEditingSet] = useState(null);
  const [formData, setFormData] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    loadSets();
  }, [token]);

  const loadSets = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchReferenceSets(token);
      setSets(data || []);
    } catch (err) {
      const msg = err.message || 'Failed to load reference sets';
      setError(msg);
      notify({ message: msg, type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const openCreate = () => {
    setEditingSet(null);
    setFormData(EMPTY_FORM);
    setOpenDialog(true);
  };

  const openEdit = (set) => {
    setEditingSet(set);
    setFormData({ name: set.name, description: set.description || '' });
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
      if (editingSet) {
        await updateReferenceSet(token, editingSet.id, formData);
        notify({ message: 'Reference set updated', type: 'success' });
      } else {
        await createReferenceSet(token, formData);
        notify({ message: 'Reference set created', type: 'success' });
      }
      setOpenDialog(false);
      loadSets();
    } catch (err) {
      const msg = err.message || 'Save failed';
      setError(msg);
      notify({ message: msg, type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (set) => {
    if (!window.confirm(`Delete reference set "${set.name}"?`)) return;
    try {
      await deleteReferenceSet(token, set.id);
      notify({ message: 'Reference set deleted', type: 'success' });
      loadSets();
    } catch (err) {
      setError(err.message || 'Delete failed');
      notify({ message: err.message || 'Delete failed', type: 'error' });
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
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <BookIcon sx={{ fontSize: '2rem', color: 'primary.main' }} />
          <Box>
            <Typography variant="h5" fontWeight={700}>Reference Data</Typography>
            <Typography variant="body2" color="text.secondary">Master data reference sets</Typography>
          </Box>
        </Box>
        <Button variant="contained" startIcon={<AddIcon />} onClick={openCreate}>
          New Set
        </Button>
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <Paper>
        <Table>
          <TableHead>
            <TableRow sx={{ backgroundColor: 'action.hover' }}>
              <TableCell fontWeight={600}>Name</TableCell>
              <TableCell fontWeight={600}>Description</TableCell>
              <TableCell fontWeight={600}>Values</TableCell>
              <TableCell fontWeight={600} align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {sets.length === 0 ? (
              <TableRow>
                <TableCell colSpan={4} align="center" sx={{ py: 3 }}>
                  <Typography color="text.secondary">No reference sets yet</Typography>
                </TableCell>
              </TableRow>
            ) : (
              sets.map(set => (
                <TableRow key={set.id} hover>
                  <TableCell fontWeight={500}>{set.name}</TableCell>
                  <TableCell>{set.description || '—'}</TableCell>
                  <TableCell>
                    <Chip label={set.value_count || 0} size="small" variant="outlined" />
                  </TableCell>
                  <TableCell align="right">
                    <IconButton size="small" onClick={() => openEdit(set)}>
                      <EditIcon fontSize="small" />
                    </IconButton>
                    <IconButton size="small" onClick={() => handleDelete(set)}>
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
        <DialogTitle>{editingSet ? 'Edit Reference Set' : 'New Reference Set'}</DialogTitle>
        <DialogContent sx={{ pt: 2 }}>
          <TextField
            fullWidth
            label="Name"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
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
          <Button onClick={handleSave} variant="contained" disabled={saving}>
            {saving ? 'Saving...' : 'Save'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
