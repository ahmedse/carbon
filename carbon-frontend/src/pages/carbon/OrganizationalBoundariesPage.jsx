// src/pages/carbon/OrganizationalBoundariesPage.jsx
// GHG Protocol organizational boundaries — admin CRUD
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
  Switch,
  FormControlLabel,
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
      sx={{ height: 2.5, ...FONT.body, fontWeight: 600 }}
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
      sx={{ height: 2.5, ...FONT.body, fontWeight: 600 }}
    />
  );
}

// ── BoundaryDialog ─────────────────────────────────────────────────────

function BoundaryDialog({ open, boundary, orgUnits, onSave, onClose }) {
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
    <SystemDialog
      open={open}
      title={boundary ? 'Edit Boundary' : 'New Boundary'}
      onClose={onClose}
      onCancel={onClose}
      cancelLabel="Cancel"
      actions={
        <Button variant="contained" size="small" onClick={handleSubmit}>
          {boundary ? 'Update' : 'Create'}
        </Button>
      }
      width={540}
      height={560}
      minWidth={420}
      minHeight={420}
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
        </Stack>
      </Box>
    </SystemDialog>
  );
}

// ── Main Component ─────────────────────────────────────────────────────

export default function OrganizationalBoundariesPage() {
  useDocumentTitle('Organizational Boundaries');
  const { user, token, availablePerspectives } = useAuth();
  const { notify, notifyFromError } = useNotification();

  const [boundaries, setBoundaries] = useState([]);
  const [orgUnits, setOrgUnits] = useState([]);
  const [loading, setLoading] = useState(true);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [current, setCurrent] = useState(null);
  const [searchText, setSearchText] = useState('');

  const isAdmin = user?.is_staff || user?.is_superuser || (availablePerspectives || []).includes('carbon-admin');

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [bData, ouData] = await Promise.all([
        fetchOrganizationalBoundaries(token),
        fetchOrgUnits(token),
      ]);
      setBoundaries(Array.isArray(bData) ? bData : bData?.results || []);
      setOrgUnits(Array.isArray(ouData) ? ouData : ouData?.results || []);
    } catch (err) {
      notifyFromError(err, 'Failed to load organizational boundaries');
      setBoundaries([]);
      setOrgUnits([]);
    } finally {
      setLoading(false);
    }
  }, [token, notifyFromError]);

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
        notify({ message: 'Boundary updated', type: 'success' });
      } else {
        await createOrganizationalBoundary(payload, token);
        notify({ message: 'Boundary created', type: 'success' });
      }
      setDrawerOpen(false);
      setCurrent(null);
      await loadData();
    } catch (err) {
      notifyFromError(err, 'Failed to save boundary');
    }
  };

  const handleDelete = async (id) => {
    try {
      await deleteOrganizationalBoundary(id, token);
      notify({ message: 'Boundary deleted', type: 'success' });
      setDeleteConfirm(null);
      await loadData();
    } catch (err) {
      notifyFromError(err, 'Failed to delete boundary');
    }
  };

  const fmtDate = (d) => {
    if (!d) return '—';
    try { return new Date(d).toLocaleDateString(); } catch { return '—'; }
  };

  const filteredBoundaries = useMemo(() => {
    let filtered = boundaries;
    if (searchText.trim()) {
      const query = searchText.toLowerCase();
      filtered = filtered.filter(
        (b) =>
          (b.name && b.name.toLowerCase().includes(query)) ||
          (Array.isArray(b.included_org_units_names) &&
            b.included_org_units_names.some((n) => n && n.toLowerCase().includes(query)))
      );
    }
    return filtered;
  }, [boundaries, searchText]);

  const columns = [
    { field: 'id', headerName: 'ID', width: 70 },
    { field: 'name', headerName: 'Name', flex: 1, minWidth: 180 },
    {
      field: 'consolidation_approach',
      headerName: 'Approach',
      width: 170,
      renderCell: (params) => <ApproachChip value={params.value} />,
    },
    {
      field: 'included_org_units_names',
      headerName: 'Included Org Units',
      flex: 1,
      minWidth: 220,
      valueGetter: (value, row) =>
        Array.isArray(row.included_org_units_names) && row.included_org_units_names.length
          ? row.included_org_units_names.join(', ')
          : '—',
    },
    {
      field: 'is_active',
      headerName: 'Status',
      width: 100,
      renderCell: (params) => <ActiveChip value={params.value} />,
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
        title="Organizational Boundaries"
        subtitle={`${filteredBoundaries.length} of ${boundaries.length} boundaries`}
        description="GHG Protocol organizational boundaries define which entities, assets, and operations are included in the GHG inventory and under which consolidation approach."
        actions={
          <Stack direction="row" spacing={1}>
            <IconButton onClick={loadData} size="small" aria-label="Refresh boundaries">
              <RefreshIcon />
            </IconButton>
            {isAdmin && (
              <Button variant="contained" size="small" startIcon={<AddIcon />} onClick={handleCreate}>
                New Boundary
              </Button>
            )}
          </Stack>
        }
        rows={filteredBoundaries}
        loading={loading}
        columns={columns}
        countLabel={`${filteredBoundaries.length} of ${boundaries.length} boundaries`}
        searchValue={searchText}
        onSearchChange={setSearchText}
        filterDefs={[]}
        onClearFilters={() => setSearchText('')}
        emptyMessage="No organizational boundaries found"
        emptySubtext="Try adjusting your search"
      />

      {/* Create/Edit Dialog (modal — design system primitive) */}
      <BoundaryDialog
        open={drawerOpen}
        boundary={current}
        orgUnits={orgUnits}
        onSave={handleSave}
        onClose={() => setDrawerOpen(false)}
      />

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        open={!!deleteConfirm}
        title="Delete Boundary?"
        message="This action cannot be undone."
        confirmLabel="Delete"
        destructive
        onConfirm={() => handleDelete(deleteConfirm)}
        onCancel={() => setDeleteConfirm(null)}
      />
    </>
  );
}
