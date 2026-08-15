// src/pages/carbon/OrganizationalBoundariesPage.jsx
// GHG Protocol organizational boundaries — admin CRUD
// Pattern: SBTiTargetsPage style — MUI Table, Drawer for create/edit, zero hardcoded hex

import React, { useEffect, useState, useCallback } from 'react';
import {
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Drawer,
  Alert,
  TextField,
  MenuItem,
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
  Switch,
  FormControlLabel,
} from '@mui/material';
import useDocumentTitle from '../../hooks/useDocumentTitle';

import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import RefreshIcon from '@mui/icons-material/Refresh';
import { useAuth } from '../../auth/AuthContext';
import PageHeader from '../../components/Page/PageHeader';
import {
  fetchOrganizationalBoundaries,
  createOrganizationalBoundary,
  updateOrganizationalBoundary,
  deleteOrganizationalBoundary,
} from '../../api/emissions-extended';
import { fetchOrgUnits } from '../../api/orgUnits';

// ── ApproachChip ───────────────────────────────────────────────────────

const APPROACH_CHIP = {
  equity_share: { label: 'Equity Share', color: 'primary' },
  financial_control: { label: 'Financial Control', color: 'info' },
  operational_control: { label: 'Operational Control', color: 'success' },
};

function ApproachChip({ value }) {
  const meta = APPROACH_CHIP[value] || { label: value, color: 'default' };
  return (
    <Chip
      label={meta.label}
      size="small"
      color={meta.color === 'default' ? undefined : meta.color}
      variant="outlined"
      sx={{ height: 20, fontSize: '0.68rem', fontWeight: 600 }}
    />
  );
}

// ── ActiveChip ─────────────────────────────────────────────────────────

function ActiveChip({ value }) {
  return (
    <Chip
      label={value ? 'Active' : 'Inactive'}
      size="small"
      color={value ? 'success' : 'default'}
      variant="filled"
      sx={{ height: 20, fontSize: '0.68rem', fontWeight: 600 }}
    />
  );
}

// ── BoundaryDrawer ─────────────────────────────────────────────────────

function BoundaryDrawer({ open, boundary, orgUnits, onSave, onClose }) {
  const [form, setForm] = useState({
    name: '',
    consolidation_approach: 'operational_control',
    description: '',
    included_org_units: [],
    is_active: true,
  });

  useEffect(() => {
    if (boundary) {
      setForm({
        name: boundary.name || '',
        consolidation_approach: boundary.consolidation_approach || 'operational_control',
        description: boundary.description || '',
        included_org_units: boundary.included_org_units || [],
        is_active: boundary.is_active ?? true,
      });
    } else {
      setForm({
        name: '',
        consolidation_approach: 'operational_control',
        description: '',
        included_org_units: [],
        is_active: true,
      });
    }
  }, [boundary, open]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = () => onSave(form);

  return (
    <Drawer anchor="right" open={open} onClose={onClose}>
      <Box sx={{ width: 440, p: 3 }}>
        <Typography variant="h6" sx={{ mb: 3, fontSize: '1rem', fontWeight: 600 }}>
          {boundary ? 'Edit Boundary' : 'New Boundary'}
        </Typography>
        <Stack spacing={2}>
          <TextField
            label="Name"
            name="name"
            value={form.name}
            onChange={handleChange}
            fullWidth
            required
            size="small"
          />
          <TextField
            label="Consolidation Approach"
            select
            name="consolidation_approach"
            value={form.consolidation_approach}
            onChange={handleChange}
            fullWidth
            size="small"
          >
            <MenuItem value="equity_share">Equity Share</MenuItem>
            <MenuItem value="financial_control">Financial Control</MenuItem>
            <MenuItem value="operational_control">Operational Control</MenuItem>
          </TextField>
          <TextField
            label="Included Org Units"
            select
            name="included_org_units"
            value={form.included_org_units}
            onChange={handleChange}
            fullWidth
            size="small"
            SelectProps={{ multiple: true }}
          >
            {orgUnits.map((ou) => (
              <MenuItem key={ou.id} value={ou.id}>{ou.name}</MenuItem>
            ))}
          </TextField>
          <TextField
            label="Description"
            name="description"
            value={form.description}
            onChange={handleChange}
            fullWidth
            multiline
            rows={3}
            size="small"
          />
          <FormControlLabel
            control={
              <Switch
                checked={form.is_active}
                onChange={(e) => setForm((p) => ({ ...p, is_active: e.target.checked }))}
              />
            }
            label="Active"
          />
          <Stack direction="row" spacing={2} sx={{ pt: 1 }}>
            <Button variant="outlined" onClick={onClose} sx={{ flex: 1 }}>
              Cancel
            </Button>
            <Button variant="contained" onClick={handleSubmit} sx={{ flex: 1 }}>
              {boundary ? 'Update' : 'Create'}
            </Button>
          </Stack>
        </Stack>
      </Box>
    </Drawer>
  );
}

// ── Main Component ─────────────────────────────────────────────────────

export default function OrganizationalBoundariesPage() {
  useDocumentTitle('Organizational Boundaries');
  const { user, token, availablePerspectives } = useAuth();
  const [boundaries, setBoundaries] = useState([]);
  const [orgUnits, setOrgUnits] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [current, setCurrent] = useState(null);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });

  const isAdmin = user?.is_staff || user?.is_superuser || (availablePerspectives || []).includes('carbon-admin');

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [bData, ouData] = await Promise.all([
        fetchOrganizationalBoundaries(token),
        fetchOrgUnits(token),
      ]);
      setBoundaries(Array.isArray(bData) ? bData : bData?.results || []);
      setOrgUnits(Array.isArray(ouData) ? ouData : ouData?.results || []);
    } catch (err) {
      setError(err.message || 'Failed to load organizational boundaries');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleCreate = () => {
    setCurrent(null);
    setDrawerOpen(true);
  };

  const handleEdit = (boundary) => {
    setCurrent(boundary);
    setDrawerOpen(true);
  };

  const handleSave = async (formData) => {
    const payload = { ...formData, included_org_units: formData.included_org_units || [] };
    try {
      if (current) {
        await updateOrganizationalBoundary(current.id, payload, token);
      } else {
        await createOrganizationalBoundary(payload, token);
      }
      setDrawerOpen(false);
      setCurrent(null);
      setSnackbar({ open: true, message: 'Organizational boundary saved', severity: 'success' });
      await loadData();
    } catch (err) {
      setError(err.message || 'Failed to save boundary');
    }
  };

  const handleDelete = async (id) => {
    try {
      await deleteOrganizationalBoundary(id, token);
      setDeleteConfirm(null);
      setSnackbar({ open: true, message: 'Organizational boundary deleted', severity: 'success' });
      await loadData();
    } catch (err) {
      setError(err.message || 'Failed to delete boundary');
    }
  };

  const fmtDate = (d) => {
    if (!d) return '—';
    try { return new Date(d).toLocaleDateString(); } catch { return '—'; }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '400px' }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      <PageHeader
        title="Organizational Boundaries"
        description="GHG Protocol organizational boundaries define which entities, assets, and operations are included in the GHG inventory and under which consolidation approach."
        actions={
          <Stack direction="row" spacing={1}>
            <IconButton onClick={loadData} size="small" sx={{ mr: 0.5 }}>
              <RefreshIcon />
            </IconButton>
            {isAdmin && (
              <Button variant="contained" startIcon={<AddIcon />} onClick={handleCreate}>
                New Boundary
              </Button>
            )}
          </Stack>
        }
      />

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <TableContainer component={Paper}>
        <Table>
          <TableHead sx={{ bgcolor: 'action.hover' }}>
            <TableRow>
              <TableCell sx={{ fontWeight: 'bold', fontSize: '0.78rem' }}>ID</TableCell>
              <TableCell sx={{ fontWeight: 'bold', fontSize: '0.78rem' }}>Name</TableCell>
              <TableCell sx={{ fontWeight: 'bold', fontSize: '0.78rem' }}>Approach</TableCell>
              <TableCell sx={{ fontWeight: 'bold', fontSize: '0.78rem' }}>Included Org Units</TableCell>
              <TableCell sx={{ fontWeight: 'bold', fontSize: '0.78rem' }}>Status</TableCell>
              <TableCell sx={{ fontWeight: 'bold', fontSize: '0.78rem' }}>Created</TableCell>
              {isAdmin && <TableCell align="center" sx={{ fontWeight: 'bold', fontSize: '0.78rem' }}>Actions</TableCell>}
            </TableRow>
          </TableHead>
          <TableBody>
            {boundaries.length === 0 ? (
              <TableRow>
                <TableCell colSpan={isAdmin ? 7 : 6} align="center" sx={{ py: 3, color: 'text.secondary' }}>
                  No organizational boundaries found. Click "New Boundary" to create one.
                </TableCell>
              </TableRow>
            ) : (
              boundaries.map((b) => (
                <TableRow key={b.id} sx={{ '&:hover': { bgcolor: 'action.hover' } }}>
                  <TableCell sx={{ fontSize: '0.75rem', color: 'text.secondary' }}>{b.id}</TableCell>
                  <TableCell sx={{ fontSize: '0.82rem', fontWeight: 500 }}>{b.name}</TableCell>
                  <TableCell><ApproachChip value={b.consolidation_approach} /></TableCell>
                  <TableCell sx={{ fontSize: '0.78rem' }}>
                    {b.included_org_units_names?.length ? b.included_org_units_names.join(', ') : '—'}
                  </TableCell>
                  <TableCell><ActiveChip value={b.is_active} /></TableCell>
                  <TableCell sx={{ fontSize: '0.72rem', color: 'text.secondary' }}>{fmtDate(b.created_at)}</TableCell>
                  {isAdmin && (
                    <TableCell align="center">
                      <IconButton size="small" onClick={() => handleEdit(b)} title="Edit">
                        <EditIcon fontSize="small" />
                      </IconButton>
                      <IconButton
                        size="small"
                        onClick={() => setDeleteConfirm(b.id)}
                        sx={{ color: 'error.main' }}
                        title="Delete"
                      >
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </TableCell>
                  )}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>

      <BoundaryDrawer
        open={drawerOpen}
        boundary={current}
        orgUnits={orgUnits}
        onSave={handleSave}
        onClose={() => setDrawerOpen(false)}
      />

      <Dialog open={!!deleteConfirm} onClose={() => setDeleteConfirm(null)}>
        <DialogTitle>Delete Boundary?</DialogTitle>
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
