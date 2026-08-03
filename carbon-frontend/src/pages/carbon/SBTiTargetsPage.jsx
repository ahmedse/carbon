// src/pages/carbon/SBTiTargetsPage.jsx
// SBTi Targets admin — CRUD for Science-Based Targets initiative reduction targets
// Pattern: GWPReferencePage style — MUI Table with icons, Drawer for create/edit
// All colours via theme.palette, zero hardcoded hex

import React, { useEffect, useState } from 'react';
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
  Tooltip,
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
  LinearProgress,
} from '@mui/material';
import useDocumentTitle from '../../hooks/useDocumentTitle';

import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import RefreshIcon from '@mui/icons-material/Refresh';
import { useAuth } from '../../auth/AuthContext';
import PageHeader from '../../components/Page/PageHeader';
import {
  fetchSBTiTargets,
  createSBTiTarget,
  updateSBTiTarget,
  deleteSBTiTarget,
} from '../../api/emissions-extended';

// ── ScopeChip ──────────────────────────────────────────────────────────

function ScopeChip({ value }) {
  const cfg = {
    '1':      { label: 'Scope 1',     color: 'error' },
    '2':      { label: 'Scope 2',     color: 'warning' },
    '3':      { label: 'Scope 3',     color: 'success' },
    '1+2':    { label: 'Scope 1+2',   color: 'info' },
    '1+2+3':  { label: 'Scope 1+2+3', color: 'primary' },
  };
  const meta = cfg[value] || { label: value, color: 'default' };
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

// ── StatusChip ─────────────────────────────────────────────────────────

function StatusChip({ value }) {
  const cfg = {
    draft:     { label: 'Draft',     color: 'warning' },
    committed: { label: 'Committed', color: 'info' },
    approved:  { label: 'Approved',  color: 'success' },
  };
  const meta = cfg[value] || { label: value, color: 'default' };
  return (
    <Chip
      label={meta.label}
      size="small"
      color={meta.color === 'default' ? undefined : meta.color}
      variant="filled"
      sx={{ height: 20, fontSize: '0.68rem', fontWeight: 600 }}
    />
  );
}

// ── TypeChip ───────────────────────────────────────────────────────────

function TypeChip({ value }) {
  const cfg = {
    absolute:  { label: 'Absolute',  color: 'default' },
    intensity: { label: 'Intensity', color: 'secondary' },
  };
  const meta = cfg[value] || { label: value, color: 'default' };
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

// ── ReductionBar ───────────────────────────────────────────────────────

function ReductionBar({ value }) {
  const pct = Number(value) || 0;
  let color = 'success';
  if (pct < 30) color = 'warning';
  else if (pct < 50) color = 'info';
  else color = 'success';

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 100 }}>
      <LinearProgress
        variant="determinate"
        value={Math.min(pct, 100)}
        color={color}
        sx={{ flex: 1, height: 6, borderRadius: 1 }}
      />
      <Typography variant="caption" sx={{ fontSize: '0.7rem', fontWeight: 600, minWidth: 40, textAlign: 'right' }}>
        {pct.toFixed(1)}%
      </Typography>
    </Box>
  );
}

// ── TargetsDrawer ──────────────────────────────────────────────────────

function TargetsDrawer({ open, target, onSave, onClose }) {
  const [form, setForm] = useState({
    name: '',
    org_unit: '',
    base_year: '',
    target_year: '',
    target_type: 'absolute',
    scope: '1+2+3',
    reduction_pct: '',
    status: 'draft',
    description: '',
  });

  useEffect(() => {
    if (target) {
      setForm({
        name: target.name || '',
        org_unit: target.org_unit || '',
        base_year: target.base_year ?? '',
        target_year: target.target_year ?? '',
        target_type: target.target_type || 'absolute',
        scope: target.scope || '1+2+3',
        reduction_pct: target.reduction_pct ?? '',
        status: target.status || 'draft',
        description: target.description || '',
      });
    } else {
      setForm({
        name: '',
        org_unit: '',
        base_year: '',
        target_year: '',
        target_type: 'absolute',
        scope: '1+2+3',
        reduction_pct: '',
        status: 'draft',
        description: '',
      });
    }
  }, [target, open]);

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
          {target ? 'Edit Target' : 'New Target'}
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
            label="Org Unit"
            name="org_unit"
            value={form.org_unit}
            onChange={handleChange}
            fullWidth
            size="small"
            placeholder="Org unit slug or ID"
          />
          <Stack direction="row" spacing={2}>
            <TextField
              label="Base Year"
              name="base_year"
              type="number"
              value={form.base_year}
              onChange={handleChange}
              fullWidth
              required
              size="small"
              inputProps={{ min: 2020, max: 2050 }}
            />
            <TextField
              label="Target Year"
              name="target_year"
              type="number"
              value={form.target_year}
              onChange={handleChange}
              fullWidth
              required
              size="small"
              inputProps={{ min: 2020, max: 2100 }}
            />
          </Stack>
          <TextField
            label="Target Type"
            select
            name="target_type"
            value={form.target_type}
            onChange={handleChange}
            fullWidth
            size="small"
          >
            <MenuItem value="absolute">Absolute</MenuItem>
            <MenuItem value="intensity">Intensity</MenuItem>
          </TextField>
          <TextField
            label="Scope"
            select
            name="scope"
            value={form.scope}
            onChange={handleChange}
            fullWidth
            size="small"
          >
            <MenuItem value="1">Scope 1</MenuItem>
            <MenuItem value="2">Scope 2</MenuItem>
            <MenuItem value="3">Scope 3</MenuItem>
            <MenuItem value="1+2">Scope 1+2</MenuItem>
            <MenuItem value="1+2+3">Scope 1+2+3</MenuItem>
          </TextField>
          <TextField
            label="Reduction (%)"
            name="reduction_pct"
            type="number"
            value={form.reduction_pct}
            onChange={handleChange}
            fullWidth
            required
            size="small"
            inputProps={{ min: 0.01, max: 100, step: 0.1 }}
          />
          <TextField
            label="Status"
            select
            name="status"
            value={form.status}
            onChange={handleChange}
            fullWidth
            size="small"
          >
            <MenuItem value="draft">Draft</MenuItem>
            <MenuItem value="committed">Committed</MenuItem>
            <MenuItem value="approved">Approved</MenuItem>
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
          <Stack direction="row" spacing={2} sx={{ pt: 1 }}>
            <Button variant="outlined" onClick={onClose} sx={{ flex: 1 }}>
              Cancel
            </Button>
            <Button variant="contained" onClick={handleSubmit} sx={{ flex: 1 }}>
              {target ? 'Update' : 'Create'}
            </Button>
          </Stack>
        </Stack>
      </Box>
    </Drawer>
  );
}

// ── Main Component ─────────────────────────────────────────────────────

export default function SBTiTargetsPage() {
  useDocumentTitle("SBTi Targets");
  const { user, token } = useAuth();
  const [targets, setTargets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [currentTarget, setCurrentTarget] = useState(null);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });

  const isAdmin = user?.is_staff || user?.is_superuser;

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchSBTiTargets(token);
      setTargets(Array.isArray(data) ? data : data?.results || []);
    } catch (err) {
      setError(err.message || 'Failed to load SBTi targets');
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = () => {
    setCurrentTarget(null);
    setDrawerOpen(true);
  };

  const handleEdit = (target) => {
    setCurrentTarget(target);
    setDrawerOpen(true);
  };

  const handleSave = async (formData) => {
    const payload = {
      ...formData,
      base_year: formData.base_year ? Number(formData.base_year) : null,
      target_year: formData.target_year ? Number(formData.target_year) : null,
      reduction_pct: formData.reduction_pct ? Number(formData.reduction_pct) : null,
    };
    try {
      if (currentTarget) {
        await updateSBTiTarget(currentTarget.id, payload, token);
      } else {
        await createSBTiTarget(payload, token);
      }
      setDrawerOpen(false);
      setCurrentTarget(null);
      await loadData();
    } catch (err) {
      setError(err.message || 'Failed to save target');
    }
  };

  const handleDelete = async (targetId) => {
    try {
      await deleteSBTiTarget(targetId, token);
      setDeleteConfirm(null);
      await loadData();
    } catch (err) {
      setError(err.message || 'Failed to delete target');
    }
  };

  const fmtDate = (d) => {
    if (!d) return '—';
    try { return new Date(d).toLocaleDateString(); } catch { return '—'; }
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
      <PageHeader
        title="SBTi Targets"
        description="Science-Based Targets initiative (SBTi) reduction goals. Define absolute or intensity targets per scope, set base/target years, and track progress toward Paris-aligned decarbonization."
        actions={
          <Stack direction="row" spacing={1}>
            <IconButton onClick={loadData} size="small" sx={{ mr: 0.5 }}>
              <RefreshIcon />
            </IconButton>
            {isAdmin && (
              <Button variant="contained" startIcon={<AddIcon />} onClick={handleCreate}>
                New Target
              </Button>
            )}
          </Stack>
        }
      />

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {/* Table */}
      <TableContainer component={Paper}>
        <Table>
          <TableHead sx={{ bgcolor: 'action.hover' }}>
            <TableRow>
              <TableCell sx={{ fontWeight: 'bold', fontSize: '0.78rem' }}>ID</TableCell>
              <TableCell sx={{ fontWeight: 'bold', fontSize: '0.78rem' }}>Name</TableCell>
              <TableCell sx={{ fontWeight: 'bold', fontSize: '0.78rem' }}>
                <Tooltip title="The organisational unit responsible for meeting this target." arrow>
                  <Typography component="span" sx={{ fontSize: 'inherit', fontWeight: 'inherit' }}>Org Unit</Typography>
                </Tooltip>
              </TableCell>
              <TableCell align="center" sx={{ fontWeight: 'bold', fontSize: '0.78rem' }}>
                <Tooltip title="The baseline year against which emission reductions are measured." arrow>
                  <Typography component="span" sx={{ fontSize: 'inherit', fontWeight: 'inherit' }}>Base Year</Typography>
                </Tooltip>
              </TableCell>
              <TableCell align="center" sx={{ fontWeight: 'bold', fontSize: '0.78rem' }}>
                <Tooltip title="The deadline year by which the target must be achieved." arrow>
                  <Typography component="span" sx={{ fontSize: 'inherit', fontWeight: 'inherit' }}>Target Year</Typography>
                </Tooltip>
              </TableCell>
              <TableCell sx={{ fontWeight: 'bold', fontSize: '0.78rem' }}>
                <Tooltip title="Absolute = total tCO₂e reduction. Intensity = per-unit reduction (e.g., tCO₂e / MWh)." arrow>
                  <Typography component="span" sx={{ fontSize: 'inherit', fontWeight: 'inherit' }}>Type</Typography>
                </Tooltip>
              </TableCell>
              <TableCell sx={{ fontWeight: 'bold', fontSize: '0.78rem' }}>
                <Tooltip title="Which GHG Protocol scope(s) this target covers." arrow>
                  <Typography component="span" sx={{ fontSize: 'inherit', fontWeight: 'inherit' }}>Scope</Typography>
                </Tooltip>
              </TableCell>
              <TableCell sx={{ fontWeight: 'bold', fontSize: '0.78rem' }}>
                <Tooltip title="Targeted reduction as a percentage from base year emissions." arrow>
                  <Typography component="span" sx={{ fontSize: 'inherit', fontWeight: 'inherit' }}>Reduction</Typography>
                </Tooltip>
              </TableCell>
              <TableCell sx={{ fontWeight: 'bold', fontSize: '0.78rem' }}>
                <Tooltip title="Draft = planning, Committed = pledged, Approved = officially validated." arrow>
                  <Typography component="span" sx={{ fontSize: 'inherit', fontWeight: 'inherit' }}>Status</Typography>
                </Tooltip>
              </TableCell>
              <TableCell sx={{ fontWeight: 'bold', fontSize: '0.78rem' }}>Created</TableCell>
              {isAdmin && <TableCell align="center" sx={{ fontWeight: 'bold', fontSize: '0.78rem' }}>Actions</TableCell>}
            </TableRow>
          </TableHead>
          <TableBody>
            {targets.length === 0 ? (
              <TableRow>
                <TableCell colSpan={isAdmin ? 11 : 10} align="center" sx={{ py: 3, color: 'text.secondary' }}>
                  No SBTi targets found. Click "New Target" to create one.
                </TableCell>
              </TableRow>
            ) : (
              targets.map((t) => (
                <TableRow key={t.id} sx={{ '&:hover': { bgcolor: 'action.hover' } }}>
                  <TableCell sx={{ fontSize: '0.75rem', color: 'text.secondary' }}>{t.id}</TableCell>
                  <TableCell sx={{ fontSize: '0.82rem', fontWeight: 500 }}>{t.name}</TableCell>
                  <TableCell sx={{ fontSize: '0.78rem' }}>{t.org_unit_name || t.org_unit || '—'}</TableCell>
                  <TableCell align="center" sx={{ fontSize: '0.78rem' }}>{t.base_year || '—'}</TableCell>
                  <TableCell align="center" sx={{ fontSize: '0.78rem' }}>{t.target_year || '—'}</TableCell>
                  <TableCell><TypeChip value={t.target_type} /></TableCell>
                  <TableCell><ScopeChip value={t.scope} /></TableCell>
                  <TableCell><ReductionBar value={t.reduction_pct} /></TableCell>
                  <TableCell><StatusChip value={t.status} /></TableCell>
                  <TableCell sx={{ fontSize: '0.72rem', color: 'text.secondary' }}>{fmtDate(t.created_at)}</TableCell>
                  {isAdmin && (
                    <TableCell align="center">
                      <IconButton size="small" onClick={() => handleEdit(t)} title="Edit">
                        <EditIcon fontSize="small" />
                      </IconButton>
                      <IconButton
                        size="small"
                        onClick={() => setDeleteConfirm(t.id)}
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

      {/* Create/Edit Drawer */}
      <TargetsDrawer
        open={drawerOpen}
        target={currentTarget}
        onSave={handleSave}
        onClose={() => setDrawerOpen(false)}
      />

      {/* Delete Confirmation Dialog */}
      <Dialog open={!!deleteConfirm} onClose={() => setDeleteConfirm(null)}>
        <DialogTitle>Delete Target?</DialogTitle>
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
