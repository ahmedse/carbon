import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Box,
  Button,
  Chip,
  TextField,
  MenuItem,
  Stack,
  IconButton,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';

import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import { can } from '../../authz';
import { useNotification } from '../../components/NotificationProvider';
import FilteredDataGrid from '../../components/FilteredDataGrid';
import ConfirmDialog from '../../components/ConfirmDialog';
import SystemDialog from '../../components/SystemDialog';
import {
  fetchEmissionFactors,
  fetchFactorCategories,
  createEmissionFactor,
  updateEmissionFactor,
  deleteEmissionFactor,
} from '../../api/emissions-extended';

const ScopeChip = ({ scope }) => {
  const scopeColors = { 1: 'error', 2: 'warning', 3: 'info' };
  const scopeLabels = { 1: 'Scope 1', 2: 'Scope 2', 3: 'Scope 3' };
  return (
    <Chip
      label={scopeLabels[scope] || `Scope ${scope}`}
      color={scopeColors[scope] || 'default'}
      size="small"
      variant="filled"
    />
  );
};

// Numeric display — max 5 decimals (backend gate rounds to 5), trailing zeros stripped
function fmtNum(v) {
  if (v == null || v === '') return '—';
  const n = Number(v);
  if (Number.isNaN(n)) return v;
  return n.toLocaleString(undefined, { maximumFractionDigits: 5 });
}

function fmtDate(v) {
  if (!v) return '—';
  const d = new Date(v);
  return Number.isNaN(d.getTime())
    ? '—'
    : d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

export default function EmissionFactorsPage() {
  useDocumentTitle("Emission Factors");
  const { user, token, availablePerspectives, isGlobalAdminFlag, userCapabilities, context } = useAuth();
  const { notify, notifyFromError } = useNotification();

  const [factors, setFactors] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [currentFactor, setCurrentFactor] = useState(null);
  const [searchText, setSearchText] = useState('');
  const [filterCategory, setFilterCategory] = useState('');
  const [filterScope, setFilterScope] = useState('');

  // Can this user manage emission factors? Same gate as AdminRoute for this route.
  const isAdmin = can(user, 'manage', 'carbon', {
    perspectives: availablePerspectives,
    isGlobalAdminFlag,
    capabilities: userCapabilities,
    modules: context?.modules || [],
  });

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [factorsData, categoriesData] = await Promise.all([
        fetchEmissionFactors({}, token),
        fetchFactorCategories(token),
      ]);
      // Defensive: always ensure arrays (CB-09 pattern)
      setFactors(Array.isArray(factorsData) ? factorsData : []);
      setCategories(Array.isArray(categoriesData) ? categoriesData : []);
    } catch (err) {
      notifyFromError(err, 'Failed to load emission factors');
      // Reset to empty arrays so .filter() calls don't break
      setFactors([]);
      setCategories([]);
    } finally {
      setLoading(false);
    }
  }, [token, notifyFromError]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleCreate = () => {
    setCurrentFactor(null);
    setDrawerOpen(true);
  };

  const handleEdit = (factor) => {
    setCurrentFactor(factor);
    setDrawerOpen(true);
  };

  const handleSave = async (formData) => {
    try {
      if (currentFactor) {
        await updateEmissionFactor(currentFactor.id, formData, token);
        notify({ message: 'Factor updated', type: 'success' });
      } else {
        await createEmissionFactor(formData, token);
        notify({ message: 'Factor created', type: 'success' });
      }
      setDrawerOpen(false);
      setCurrentFactor(null);
      await loadData();
    } catch (err) {
      notifyFromError(err, 'Failed to save factor');
    }
  };

  const handleDelete = async (factorId) => {
    try {
      await deleteEmissionFactor(factorId, token);
      notify({ message: 'Factor deleted', type: 'success' });
      setDeleteConfirm(null);
      await loadData();
    } catch (err) {
      notifyFromError(err, 'Failed to delete factor');
    }
  };

  const filteredFactors = useMemo(() => {
    let filtered = factors;

    if (searchText.trim()) {
      const query = searchText.toLowerCase();
      filtered = filtered.filter(
        (f) =>
          (f.name && f.name.toLowerCase().includes(query)) ||
          (f.code && f.code.toLowerCase().includes(query))
      );
    }

    if (filterCategory) {
      filtered = filtered.filter((f) => f.category === filterCategory);
    }

    if (filterScope) {
      filtered = filtered.filter((f) => f.scope === parseInt(filterScope));
    }

    return filtered;
  }, [factors, searchText, filterCategory, filterScope]);

  const handleClearFilters = () => {
    setSearchText('');
    setFilterCategory('');
    setFilterScope('');
  };

  const columns = [
    { field: 'name', headerName: 'Name', flex: 1, minWidth: 200 },
    { field: 'code', headerName: 'Code', width: 150 },
    { field: 'category', headerName: 'Category', width: 180 },
    {
      field: 'scope',
      headerName: 'Scope',
      width: 110,
      renderCell: (params) => <ScopeChip scope={params.value} />,
    },
    {
      field: 'factor_value',
      headerName: 'Value',
      width: 120,
      align: 'right',
      headerAlign: 'right',
      valueFormatter: (value) => fmtNum(value),
    },
    {
      field: 'activity_unit',
      headerName: 'Unit',
      width: 90,
    },
    {
      field: 'is_active',
      headerName: 'Active',
      width: 80,
      renderCell: (params) => (
        <Chip
          label={params.value ? 'Yes' : 'No'}
          color={params.value ? 'success' : 'default'}
          size="small"
          variant={params.value ? 'filled' : 'outlined'}
        />
      ),
    },
    {
      field: 'updated_at',
      headerName: 'Last Modified',
      width: 170,
      sortable: true,
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
    <Box sx={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <FilteredDataGrid
        title="Emission Factors"
        subtitle={`${filteredFactors.length} of ${factors.length} factors`}
        description="Manage emission conversion factors for carbon accounting — browse, create, edit, and deactivate factors used in emissions calculations."
        actions={
          isAdmin ? (
            <Button variant="contained" size="small" startIcon={<AddIcon />} onClick={handleCreate}>
              Add Factor
            </Button>
          ) : null
        }
        rows={filteredFactors}
        loading={loading}
        columns={columns}
        countLabel={`${filteredFactors.length} of ${factors.length} factors`}
        searchValue={searchText}
        onSearchChange={setSearchText}
        filterDefs={[
          {
            key: 'category',
            label: 'Category',
            emptyLabel: 'All Categories',
            options: categories,
          },
          {
            key: 'scope',
            label: 'Scope',
            emptyLabel: 'All Scopes',
            options: [
              { value: '1', label: 'Scope 1' },
              { value: '2', label: 'Scope 2' },
              { value: '3', label: 'Scope 3' },
            ],
          },
        ]}
        filterValues={{ category: filterCategory, scope: filterScope }}
        onFilterChange={(key, value) => {
          if (key === 'category') setFilterCategory(value);
          if (key === 'scope') setFilterScope(value);
        }}
        onClearFilters={handleClearFilters}
        emptyMessage="No factors found"
        emptySubtext="Try adjusting your filters"
      />

      {/* Create/Edit Dialog (modal — design system primitive) */}
      <FactorDialog
        open={drawerOpen}
        factor={currentFactor}
        categories={categories}
        onSave={handleSave}
        onClose={() => setDrawerOpen(false)}
      />

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        open={!!deleteConfirm}
        title="Delete Factor?"
        message="This action cannot be undone. Calculations using this factor may be affected."
        confirmLabel="Delete"
        destructive
        onConfirm={() => handleDelete(deleteConfirm)}
        onCancel={() => setDeleteConfirm(null)}
      />
    </Box>
  );
}

function FactorDialog({ open, factor, categories, onSave, onClose }) {
  const [form, setForm] = useState({
    name: '',
    code: '',
    category: '',
    scope: 1,
    factor_value: '',
    activity_unit: '',
    source: '',
    valid_from: '',
    valid_to: '',
    tags: '',
    is_active: true,
  });

  useEffect(() => {
    if (factor) {
      setForm({
        name: factor.name || '',
        code: factor.code || '',
        category: factor.category || '',
        scope: factor.scope || 1,
        factor_value: factor.factor_value || '',
        activity_unit: factor.activity_unit || '',
        source: factor.source || '',
        valid_from: factor.valid_from || '',
        valid_to: factor.valid_to || '',
        tags: Array.isArray(factor.tags) ? factor.tags.join(', ') : '',
        is_active: factor.is_active ?? true,
      });
    } else {
      setForm({
        name: '',
        code: '',
        category: '',
        scope: 1,
        factor_value: '',
        activity_unit: '',
        source: '',
        valid_from: '',
        valid_to: '',
        tags: '',
        is_active: true,
      });
    }
  }, [factor, open]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleSubmit = () => {
    const payload = {
      ...form,
      // Convert comma-separated tag string to array for the backend
      tags: form.tags ? form.tags.split(',').map((t) => t.trim()).filter(Boolean) : [],
    };
    onSave(payload);
  };

  return (
    <SystemDialog
      open={open}
      title={factor ? 'Edit Factor' : 'Create Factor'}
      onClose={onClose}
      onCancel={onClose}
      cancelLabel="Cancel"
      actions={
        <Button variant="contained" size="small" onClick={handleSubmit}>
          Save
        </Button>
      }
      width={560}
      height={680}
      minWidth={420}
      minHeight={400}
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
            size="small"
          />
          <TextField
            label="Code"
            name="code"
            value={form.code}
            onChange={handleChange}
            fullWidth
            size="small"
          />
          <TextField
            label="Category"
            select
            name="category"
            value={form.category}
            onChange={handleChange}
            fullWidth
            size="small"
          >
            {categories.map((cat) => (
              <MenuItem key={cat.value} value={cat.value}>
                {cat.label}
              </MenuItem>
            ))}
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
            <MenuItem value={1}>Scope 1 - Direct</MenuItem>
            <MenuItem value={2}>Scope 2 - Indirect (Energy)</MenuItem>
            <MenuItem value={3}>Scope 3 - Value Chain</MenuItem>
          </TextField>
          <TextField
            label="Factor Value"
            name="factor_value"
            type="number"
            value={form.factor_value}
            onChange={handleChange}
            fullWidth
            size="small"
            inputProps={{ step: '0.0001' }}
          />
          <TextField
            label="Activity Unit"
            name="activity_unit"
            value={form.activity_unit}
            onChange={handleChange}
            fullWidth
            size="small"
            placeholder="e.g., kWh, liter, km"
          />
          <TextField
            label="Source *"
            name="source"
            value={form.source}
            onChange={handleChange}
            fullWidth
            size="small"
            placeholder="e.g., EPA eGRID 2024"
          />
          <Stack direction="row" spacing={2}>
            <TextField
              label="Valid From *"
              name="valid_from"
              type="date"
              value={form.valid_from}
              onChange={handleChange}
              fullWidth
              size="small"
              InputLabelProps={{ shrink: true }}
            />
            <TextField
              label="Valid To"
              name="valid_to"
              type="date"
              value={form.valid_to}
              onChange={handleChange}
              fullWidth
              size="small"
              InputLabelProps={{ shrink: true }}
            />
          </Stack>
          <TextField
            label="Tags"
            name="tags"
            value={form.tags}
            onChange={handleChange}
            fullWidth
            size="small"
            placeholder="comma-separated, e.g., electricity, grid, kwh"
          />
        </Stack>
      </Box>
    </SystemDialog>
  );
}
