// src/pages/emissions/GWPReferencePage.jsx
// GWP Reference Values admin — CRUD for IPCC Global Warming Potential values
// Pattern: EmissionFactorsPage style — MUI Table with icons, dialogs for create/edit
// All colours via theme.palette, zero hardcoded hex

import React, { useEffect, useState } from 'react';
import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Drawer,
  Alert,
  TextField,
  CircularProgress,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Stack,
  IconButton,
  Snackbar,
} from '@mui/material';
import useDocumentTitle from '../../hooks/useDocumentTitle';

import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import RefreshIcon from '@mui/icons-material/Refresh';
import InboxIcon from '@mui/icons-material/Inbox';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import {
  fetchGWPValues,
  createGWPValue,
  updateGWPValue,
  deleteGWPValue,
} from '../../api/emissions-extended';

// ── GwpDrawer ──────────────────────────────────────────────────────────

function GwpDrawer({ open, gwpValue, onSave, onClose }) {
  const [form, setForm] = useState({
    gas_name: '',
    gas_formula: '',
    gwp_ar5_100yr: '',
    gwp_ar6_100yr: '',
    gwp_ar5_20yr: '',
    gwp_ar6_20yr: '',
    cas_number: '',
    notes: '',
  });

  useEffect(() => {
    if (gwpValue) {
      setForm({
        gas_name: gwpValue.gas_name || '',
        gas_formula: gwpValue.gas_formula || '',
        gwp_ar5_100yr: gwpValue.gwp_ar5_100yr ?? '',
        gwp_ar6_100yr: gwpValue.gwp_ar6_100yr ?? '',
        gwp_ar5_20yr: gwpValue.gwp_ar5_20yr ?? '',
        gwp_ar6_20yr: gwpValue.gwp_ar6_20yr ?? '',
        cas_number: gwpValue.cas_number || '',
        notes: gwpValue.notes || '',
      });
    } else {
      setForm({
        gas_name: '',
        gas_formula: '',
        gwp_ar5_100yr: '',
        gwp_ar6_100yr: '',
        gwp_ar5_20yr: '',
        gwp_ar6_20yr: '',
        cas_number: '',
        notes: '',
      });
    }
  }, [gwpValue, open]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = () => {
    onSave(form);
  };

  return (
    <Drawer anchor="right" open={open} onClose={onClose}>
      <Box sx={{ width: 420, p: 3 }}>
        <Typography variant="h6" sx={{ mb: 3, fontSize: '1rem', fontWeight: 600 }}>
          {gwpValue ? 'Edit GWP Value' : 'Create GWP Value'}
        </Typography>
        <Stack spacing={2}>
          <TextField
            label="Gas Name"
            name="gas_name"
            value={form.gas_name}
            onChange={handleChange}
            fullWidth
            required
            size="small"
          />
          <TextField
            label="Gas Formula"
            name="gas_formula"
            value={form.gas_formula}
            onChange={handleChange}
            fullWidth
            size="small"
            placeholder="e.g. CH₄, N₂O"
          />
          <TextField
            label="AR5 100yr GWP"
            name="gwp_ar5_100yr"
            type="number"
            value={form.gwp_ar5_100yr}
            onChange={handleChange}
            fullWidth
            size="small"
            inputProps={{ step: 0.1 }}
          />
          <TextField
            label="AR6 100yr GWP"
            name="gwp_ar6_100yr"
            type="number"
            value={form.gwp_ar6_100yr}
            onChange={handleChange}
            fullWidth
            size="small"
            inputProps={{ step: 0.1 }}
          />
          <TextField
            label="AR5 20yr GWP"
            name="gwp_ar5_20yr"
            type="number"
            value={form.gwp_ar5_20yr}
            onChange={handleChange}
            fullWidth
            size="small"
            inputProps={{ step: 0.1 }}
          />
          <TextField
            label="AR6 20yr GWP"
            name="gwp_ar6_20yr"
            type="number"
            value={form.gwp_ar6_20yr}
            onChange={handleChange}
            fullWidth
            size="small"
            inputProps={{ step: 0.1 }}
          />
          <TextField
            label="CAS Number"
            name="cas_number"
            value={form.cas_number}
            onChange={handleChange}
            fullWidth
            size="small"
            placeholder="e.g. 74-82-8"
          />
          <TextField
            label="Notes"
            name="notes"
            value={form.notes}
            onChange={handleChange}
            fullWidth
            multiline
            rows={2}
            size="small"
          />
          <Stack direction="row" spacing={2} sx={{ pt: 1 }}>
            <Button variant="outlined" onClick={onClose} sx={{ flex: 1 }}>
              Cancel
            </Button>
            <Button variant="contained" onClick={handleSubmit} sx={{ flex: 1 }}>
              {gwpValue ? 'Update' : 'Create'}
            </Button>
          </Stack>
        </Stack>
      </Box>
    </Drawer>
  );
}

// ── Main Component ─────────────────────────────────────────────────────

export default function GWPReferencePage() {
  useDocumentTitle("GWP Reference");
  const { user, token } = useAuth();
  const [gwpValues, setGwpValues] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [currentGwp, setCurrentGwp] = useState(null);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });

  const { notifyFromError } = useNotification();
  const isAdmin = user?.is_superuser || user?.groups?.includes('admins_group');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchGWPValues(token);
      setGwpValues(Array.isArray(data) ? data : data?.results || []);
    } catch (err) {
      notifyFromError(err, 'Failed to load GWP values');
      setError(err.message || 'Failed to load GWP values');
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = () => {
    setCurrentGwp(null);
    setDrawerOpen(true);
  };

  const handleEdit = (gwp) => {
    setCurrentGwp(gwp);
    setDrawerOpen(true);
  };

  const handleSave = async (formData) => {
    // Convert numeric fields
    const payload = {
      ...formData,
      gwp_ar5_100yr: formData.gwp_ar5_100yr ? Number(formData.gwp_ar5_100yr) : null,
      gwp_ar6_100yr: formData.gwp_ar6_100yr ? Number(formData.gwp_ar6_100yr) : null,
      gwp_ar5_20yr: formData.gwp_ar5_20yr ? Number(formData.gwp_ar5_20yr) : null,
      gwp_ar6_20yr: formData.gwp_ar6_20yr ? Number(formData.gwp_ar6_20yr) : null,
    };
    try {
      if (currentGwp) {
        await updateGWPValue(currentGwp.id, payload, token);
      } else {
        await createGWPValue(payload, token);
      }
      setDrawerOpen(false);
      setCurrentGwp(null);
      await loadData();
    } catch (err) {
      notifyFromError(err, 'Failed to save GWP value');
      setError(err.message || 'Failed to save GWP value');
    }
  };

  const handleDelete = async (gwpId) => {
    try {
      await deleteGWPValue(gwpId, token);
      setDeleteConfirm(null);
      await loadData();
    } catch (err) {
      notifyFromError(err, 'Failed to delete GWP value');
      setError(err.message || 'Failed to delete GWP value');
    }
  };

  // Format GWP value for display
  const fmtGwp = (val) => {
    if (val == null || val === '') return '—';
    return Number(val).toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 2 });
  };

  // ── Loading state ────────────────────────────────────────────────────

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '400px' }}>
        <CircularProgress />
      </Box>
    );
  }

  // ── Render ───────────────────────────────────────────────────────────

  return (
    <Box sx={{ p: 3 }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 3 }}>
        <Typography variant="h5" sx={{ fontWeight: 'bold' }}>
          GWP Reference Values
        </Typography>
        <Stack direction="row" spacing={1}>
          <IconButton onClick={loadData} size="small">
            <RefreshIcon />
          </IconButton>
          {isAdmin && (
            <Button variant="contained" startIcon={<AddIcon />} onClick={handleCreate}>
              New GWP
            </Button>
          )}
        </Stack>
      </Stack>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {(!gwpValues || gwpValues.length === 0) && (
        <Box sx={{ textAlign: 'center', py: 8 }}>
          <InboxIcon sx={{ fontSize: 64, color: 'text.disabled', mb: 2 }} />
          <Typography variant="h6" color="text.secondary">No GWP values found</Typography>
          <Typography variant="body2" color="text.disabled">
            {isAdmin ? 'Click "New GWP" to create one.' : 'Contact an administrator to add items.'}
          </Typography>
        </Box>
      )}

      {gwpValues && gwpValues.length > 0 && (
      /* Table */
      <TableContainer component={Paper}>
        <Table>
          <TableHead sx={{ bgcolor: 'action.hover' }}>
            <TableRow>
              <TableCell sx={{ fontWeight: 'bold', fontSize: '0.78rem' }}>ID</TableCell>
              <TableCell sx={{ fontWeight: 'bold', fontSize: '0.78rem' }}>Gas Name</TableCell>
              <TableCell sx={{ fontWeight: 'bold', fontSize: '0.78rem' }}>Formula</TableCell>
              <TableCell align="right" sx={{ fontWeight: 'bold', fontSize: '0.78rem' }}>AR5 100yr</TableCell>
              <TableCell align="right" sx={{ fontWeight: 'bold', fontSize: '0.78rem' }}>AR6 100yr</TableCell>
              <TableCell align="right" sx={{ fontWeight: 'bold', fontSize: '0.78rem' }}>AR5 20yr</TableCell>
              <TableCell align="right" sx={{ fontWeight: 'bold', fontSize: '0.78rem' }}>AR6 20yr</TableCell>
              <TableCell sx={{ fontWeight: 'bold', fontSize: '0.78rem' }}>CAS #</TableCell>
              <TableCell sx={{ fontWeight: 'bold', fontSize: '0.78rem' }}>Notes</TableCell>
              {isAdmin && <TableCell align="center" sx={{ fontWeight: 'bold', fontSize: '0.78rem' }}>Actions</TableCell>}
            </TableRow>
          </TableHead>
          <TableBody>
            {gwpValues.map((gwp) => (
                <TableRow key={gwp.id} sx={{ '&:hover': { bgcolor: 'action.hover' } }}>
                  <TableCell sx={{ fontSize: '0.75rem', color: 'text.secondary' }}>{gwp.id}</TableCell>
                  <TableCell sx={{ fontSize: '0.82rem', fontWeight: 500 }}>{gwp.gas_name}</TableCell>
                  <TableCell sx={{ fontSize: '0.78rem', fontFamily: 'monospace' }}>{gwp.gas_formula || '—'}</TableCell>
                  <TableCell align="right" sx={{ fontSize: '0.78rem', fontFamily: 'monospace' }}>{fmtGwp(gwp.gwp_ar5_100yr)}</TableCell>
                  <TableCell align="right" sx={{ fontSize: '0.78rem', fontFamily: 'monospace' }}>{fmtGwp(gwp.gwp_ar6_100yr)}</TableCell>
                  <TableCell align="right" sx={{ fontSize: '0.78rem', fontFamily: 'monospace' }}>{fmtGwp(gwp.gwp_ar5_20yr)}</TableCell>
                  <TableCell align="right" sx={{ fontSize: '0.78rem', fontFamily: 'monospace' }}>{fmtGwp(gwp.gwp_ar6_20yr)}</TableCell>
                  <TableCell sx={{ fontSize: '0.75rem', fontFamily: 'monospace' }}>{gwp.cas_number || '—'}</TableCell>
                  <TableCell sx={{ fontSize: '0.72rem', color: 'text.secondary', maxWidth: 150, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {gwp.notes || '—'}
                  </TableCell>
                  {isAdmin && (
                    <TableCell align="center">
                      <IconButton size="small" onClick={() => handleEdit(gwp)} title="Edit">
                        <EditIcon fontSize="small" />
                      </IconButton>
                      <IconButton
                        size="small"
                        onClick={() => setDeleteConfirm(gwp.id)}
                        sx={{ color: 'error.main' }}
                        title="Delete"
                      >
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </TableCell>
                  )}
                </TableRow>
              ))}
          </TableBody>
        </Table>
      </TableContainer>
      )}

      {/* Create/Edit Drawer */}
      <GwpDrawer
        open={drawerOpen}
        gwpValue={currentGwp}
        onSave={handleSave}
        onClose={() => setDrawerOpen(false)}
      />

      {/* Delete Confirmation Dialog */}
      <Dialog open={!!deleteConfirm} onClose={() => setDeleteConfirm(null)}>
        <DialogTitle>Delete GWP Value?</DialogTitle>
        <DialogContent>
          <Typography sx={{ fontSize: '0.85rem' }}>This action cannot be undone.</Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteConfirm(null)}>Cancel</Button>
          <Button onClick={() => handleDelete(deleteConfirm)} variant="contained" color="error">
            Delete
          </Button>
        </DialogActions>
      </Dialog>

      {/* Snackbar */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={() => setSnackbar((prev) => ({ ...prev, open: false }))}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert severity={snackbar.severity} variant="filled" sx={{ width: '100%' }}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
}
