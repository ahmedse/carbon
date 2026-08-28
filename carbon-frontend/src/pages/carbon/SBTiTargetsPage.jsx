// src/pages/carbon/SBTiTargetsPage.jsx
// SBTi Targets admin — CRUD for Science-Based Targets initiative reduction targets
// Canonical shell: FilteredDataGrid + SystemDialog + ConfirmDialog (see EmissionFactorsPage / GWPReferencePage)
// All colours via theme.palette, zero hardcoded hex

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Box,
  Button,
  Chip,
  TextField,
  MenuItem,
  Stack,
  IconButton,
  Typography,
  LinearProgress,
} from '@mui/material';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { FONT } from '../../theme/themeTokens';

import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import RefreshIcon from '@mui/icons-material/Refresh';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import FilteredDataGrid from '../../components/FilteredDataGrid';
import ConfirmDialog from '../../components/ConfirmDialog';
import SystemDialog from '../../components/SystemDialog';
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
      sx={{ height: 2.5, ...FONT.body, fontWeight: 600 }}
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
      sx={{ height: 2.5, ...FONT.body, fontWeight: 600 }}
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
      sx={{ height: 2.5, ...FONT.body, fontWeight: 600 }}
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
        sx={{ flex: 1, height: 0.75, borderRadius: 1 }}
      />
      <Typography variant="caption" sx={{ ...FONT.body, fontWeight: 600, minWidth: 40, textAlign: 'right' }}>
        {pct.toFixed(1)}%
      </Typography>
    </Box>
  );
}

// ── TargetsDialog ──────────────────────────────────────────────────────

function TargetsDialog({ open, target, onSave, onClose }) {
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
    <SystemDialog
      open={open}
      title={target ? 'Edit Target' : 'New Target'}
      onClose={onClose}
      onCancel={onClose}
      cancelLabel="Cancel"
      actions={
        <Button variant="contained" size="small" onClick={handleSubmit}>
          {target ? 'Update' : 'Create'}
        </Button>
      }
      width={520}
      height={660}
      minWidth={420}
      minHeight={460}
      maxWidth="calc(100vw - 32px)"
      maxHeight="calc(100vh - 32px)"
    >
      <Box px={2} py={1}>
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
        </Stack>
      </Box>
    </SystemDialog>
  );
}

// ── Main Component ─────────────────────────────────────────────────────

export default function SBTiTargetsPage() {
  useDocumentTitle("SBTi Targets");
  const { user, token, availablePerspectives } = useAuth();
  const { notify, notifyFromError } = useNotification();

  const [targets, setTargets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [currentTarget, setCurrentTarget] = useState(null);
  const [searchText, setSearchText] = useState('');

  const isAdmin = user?.is_staff || user?.is_superuser || (availablePerspectives || []).includes('carbon-admin');

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const data = await fetchSBTiTargets(token);
      setTargets(Array.isArray(data) ? data : data?.results || []);
    } catch (err) {
      notifyFromError(err, 'Failed to load SBTi targets');
      setTargets([]);
    } finally {
      setLoading(false);
    }
  }, [token, notifyFromError]);

  useEffect(() => {
    loadData();
  }, [loadData]);

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
        notify({ message: 'Target updated', type: 'success' });
      } else {
        await createSBTiTarget(payload, token);
        notify({ message: 'Target created', type: 'success' });
      }
      setDrawerOpen(false);
      setCurrentTarget(null);
      await loadData();
    } catch (err) {
      notifyFromError(err, 'Failed to save target');
    }
  };

  const handleDelete = async (targetId) => {
    try {
      await deleteSBTiTarget(targetId, token);
      notify({ message: 'Target deleted', type: 'success' });
      setDeleteConfirm(null);
      await loadData();
    } catch (err) {
      notifyFromError(err, 'Failed to delete target');
    }
  };

  const fmtDate = (d) => {
    if (!d) return '—';
    try { return new Date(d).toLocaleDateString(); } catch { return '—'; }
  };

  const filteredTargets = useMemo(() => {
    let filtered = targets;
    if (searchText.trim()) {
      const query = searchText.toLowerCase();
      filtered = filtered.filter(
        (t) =>
          (t.name && t.name.toLowerCase().includes(query)) ||
          (t.org_unit_name && t.org_unit_name.toLowerCase().includes(query)) ||
          (t.org_unit && String(t.org_unit).toLowerCase().includes(query))
      );
    }
    return filtered;
  }, [targets, searchText]);

  const columns = [
    { field: 'id', headerName: 'ID', width: 70 },
    { field: 'name', headerName: 'Name', flex: 1, minWidth: 180 },
    {
      field: 'org_unit',
      headerName: 'Org Unit',
      flex: 1,
      minWidth: 140,
      valueGetter: (value, row) => row.org_unit_name || row.org_unit || '—',
    },
    {
      field: 'base_year',
      headerName: 'Base Year',
      width: 100,
      align: 'center',
      headerAlign: 'center',
      valueFormatter: (value) => value ?? '—',
    },
    {
      field: 'target_year',
      headerName: 'Target Year',
      width: 110,
      align: 'center',
      headerAlign: 'center',
      valueFormatter: (value) => value ?? '—',
    },
    {
      field: 'target_type',
      headerName: 'Type',
      width: 110,
      renderCell: (params) => <TypeChip value={params.value} />,
    },
    {
      field: 'scope',
      headerName: 'Scope',
      width: 130,
      renderCell: (params) => <ScopeChip value={params.value} />,
    },
    {
      field: 'reduction_pct',
      headerName: 'Reduction',
      width: 160,
      renderCell: (params) => <ReductionBar value={params.row.reduction_pct} />,
    },
    {
      field: 'status',
      headerName: 'Status',
      width: 120,
      renderCell: (params) => <StatusChip value={params.value} />,
    },
    {
      field: 'created_at',
      headerName: 'Created',
      width: 120,
      valueFormatter: (value) => fmtDate(value),
    },
    ...(isAdmin
      ? [
          {
            field: 'actions',
            headerName: 'Actions',
            width: 100,
            sortable: false,
            renderCell: (params) => (
              <Box sx={{ display: 'flex', gap: 0.5 }}>
                <IconButton size="small" onClick={() => handleEdit(params.row)}>
                  <EditIcon fontSize="small" />
                </IconButton>
                <IconButton
                  size="small"
                  onClick={() => setDeleteConfirm(params.row.id)}
                  sx={{ color: 'error.main' }}
                >
                  <DeleteIcon fontSize="small" />
                </IconButton>
              </Box>
            ),
          },
        ]
      : []),
  ];

  return (
    <>
      <FilteredDataGrid
        title="SBTi Targets"
        subtitle={`${filteredTargets.length} of ${targets.length} targets`}
        description="Science-Based Targets initiative (SBTi) reduction goals. Define absolute or intensity targets per scope, set base/target years, and track progress toward Paris-aligned decarbonization."
        actions={
          <Stack direction="row" spacing={1}>
            <IconButton onClick={loadData} size="small" aria-label="Refresh targets">
              <RefreshIcon />
            </IconButton>
            {isAdmin && (
              <Button variant="contained" size="small" startIcon={<AddIcon />} onClick={handleCreate}>
                New Target
              </Button>
            )}
          </Stack>
        }
        rows={filteredTargets}
        loading={loading}
        columns={columns}
        countLabel={`${filteredTargets.length} of ${targets.length} targets`}
        searchValue={searchText}
        onSearchChange={setSearchText}
        filterDefs={[]}
        onClearFilters={() => setSearchText('')}
        emptyMessage="No SBTi targets found"
        emptySubtext="Try adjusting your search"
      />

      {/* Create/Edit Dialog (modal — design system primitive) */}
      <TargetsDialog
        open={drawerOpen}
        target={currentTarget}
        onSave={handleSave}
        onClose={() => setDrawerOpen(false)}
      />

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        open={!!deleteConfirm}
        title="Delete Target?"
        message="This action cannot be undone."
        confirmLabel="Delete"
        destructive
        onConfirm={() => handleDelete(deleteConfirm)}
        onCancel={() => setDeleteConfirm(null)}
      />
    </>
  );
}
