// src/pages/catalog/DataProductsPage.jsx
// Catalog Studio: browse Data Products (Modules). A Data Product groups tables,
// is org-owned, and is the governance container. (Code entity = Module.)
// AI-toolkit compliant: FilteredDataGrid shell, SystemDialog form, ConfirmDialog,
// can() manage gate (CB-13), useNotification, 4 data states, CB-09 defensive arrays.
import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import { can } from '../../authz';
import {
  Box, Button, Chip, Stack, IconButton, Tooltip, Alert,
} from '@mui/material';
import useDocumentTitle from '../../hooks/useDocumentTitle';

import VisibilityIcon from '@mui/icons-material/Visibility';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import AddIcon from '@mui/icons-material/Add';
import { fetchDataSchemaTables } from '../../api/dataschema';
import { fetchAssetProfiles } from '../../api/catalog';
import { createModule, updateModule, deleteModule } from '../../api/modules';
import { fetchOrgUnits } from '../../api/orgUnits';
import { DATA_PRODUCTS, DATA_PRODUCT } from '../../constants/terminology';
import FilteredDataGrid from '../../components/FilteredDataGrid';
import ConfirmDialog from '../../components/ConfirmDialog';
import SystemDialog from '../../components/SystemDialog';
import ProductForm from '../../components/dataproducts/ProductForm';

const EMPTY_FORM = { name: '', description: '', org_unit: '' };

// ISO → compact date+time, '—' for missing/invalid (codebase convention)
function formatModified(value) {
  if (!value) return '—';
  const d = new Date(value);
  return Number.isNaN(d.getTime())
    ? '—'
    : d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

export default function DataProductsPage() {
  useDocumentTitle("Data Products");
  const navigate = useNavigate();
  const { token, user, context, selectProject, availablePerspectives, isGlobalAdminFlag, userCapabilities } = useAuth();
  const { notify, notifyFromError } = useNotification();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [tables, setTables] = useState([]);
  const [assets, setAssets] = useState([]);
  const [searchText, setSearchText] = useState('');
  const [filterOrgUnit, setFilterOrgUnit] = useState('');
  const [orgUnits, setOrgUnits] = useState([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(null);

  const modules = useMemo(() => context?.modules || [], [context?.modules]);

  // manage gate → CATALOG_MANAGE_PRODUCTS (CB-13 — not access_route for admin actions)
  const canManage = can(user, 'manage', 'catalog', {
    perspectives: availablePerspectives,
    isGlobalAdminFlag,
    capabilities: userCapabilities,
    modules,
  });

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [tablesData, assetsData, orgUnitsData] = await Promise.all([
        fetchDataSchemaTables(token, null, null),
        fetchAssetProfiles(token).catch(() => []),
        fetchOrgUnits(token).catch(() => []),
      ]);
      setTables(Array.isArray(tablesData) ? tablesData : tablesData?.results || []);
      setAssets(Array.isArray(assetsData) ? assetsData : assetsData?.results || []);
      setOrgUnits(Array.isArray(orgUnitsData) ? orgUnitsData : orgUnitsData?.results || []);
    } catch (err) {
      const msg = err.message || 'Failed to load data products';
      setError(msg);
      notify({ message: msg, type: 'error' });
    } finally {
      setLoading(false);
    }
  }, [token, notify]);

  useEffect(() => { loadData(); }, [loadData]);

  const openCreate = () => { setEditing(null); setForm(EMPTY_FORM); setDialogOpen(true); };
  const openEdit = useCallback((m) => {
    setEditing(m);
    setForm({ name: m.name || '', description: m.description || '', org_unit: m.org_unit ?? '' });
    setDialogOpen(true);
  }, []);
  const closeDialog = () => { if (!submitting) { setDialogOpen(false); setEditing(null); } };

  const handleSubmit = async () => {
    if (!form.name.trim()) { notify({ message: 'Name is required', type: 'error' }); return; }
    setSubmitting(true);
    try {
      const payload = {
        name: form.name.trim(),
        description: form.description.trim(),
        org_unit: form.org_unit === '' ? null : Number(form.org_unit),
      };
      if (editing) {
        await updateModule(token, editing.id, payload);
        notify({ message: 'Data product updated', type: 'success' });
      } else {
        await createModule(token, payload);
        notify({ message: 'Data product created', type: 'success' });
      }
      setDialogOpen(false);
      setEditing(null);
      await selectProject();
    } catch (err) {
      notify({ message: err.message || 'Save failed', type: 'error' });
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (m) => {
    try {
      await deleteModule(token, m.id);
      notify({ message: 'Data product deleted', type: 'success' });
      setDeleteConfirm(null);
      await selectProject();
    } catch (err) {
      notifyFromError(err, 'Delete failed');
    }
  };

  // Group tables + quality + last-modified by module id.
  const statsByModule = useMemo(() => {
    const assetByTable = {};
    assets.forEach((a) => { if (a.data_table != null && !a.data_field) assetByTable[a.data_table] = a; });
    const map = {};
    tables.forEach((t) => {
      const mid = t.module ?? t.module_id;
      if (mid == null) return;
      if (!map[mid]) map[mid] = { count: 0, failing: 0, warning: 0, updated: null };
      map[mid].count += 1;
      const q = assetByTable[t.id]?.quality_status;
      if (q === 'failing') map[mid].failing += 1;
      else if (q === 'warning') map[mid].warning += 1;
      const ts = t.updated_at ? Date.parse(t.updated_at) : NaN;
      if (!Number.isNaN(ts) && (map[mid].updated == null || ts > map[mid].updated)) {
        map[mid].updated = ts;
      }
    });
    return map;
  }, [tables, assets]);

  const hasFilters = Boolean(searchText || filterOrgUnit);

  const filtered = useMemo(() => {
    let f = modules;
    if (searchText.trim()) {
      const s = searchText.toLowerCase();
      f = f.filter((m) =>
        (m.name || '').toLowerCase().includes(s) || (m.description || '').toLowerCase().includes(s)
      );
    }
    if (filterOrgUnit) {
      f = f.filter((m) => String(m.org_unit ?? '') === filterOrgUnit);
    }
    return f;
  }, [modules, searchText, filterOrgUnit]);

  const handleClearFilters = () => { setSearchText(''); setFilterOrgUnit(''); };

  const columns = useMemo(() => [
    {
      field: 'name',
      headerName: 'Name',
      flex: 1,
      minWidth: 180,
      renderCell: (params) => (
        <Button
          size="small"
          sx={{ textTransform: 'none', justifyContent: 'flex-start', p: 0, minWidth: 0 }}
          onClick={() => navigate(`/catalog/products/${params.row.id}`)}
        >
          {params.row.name}
        </Button>
      ),
    },
    {
      field: 'org_unit_name',
      headerName: 'Org Unit',
      width: 170,
      valueGetter: (value, row) => row.org_unit_name || '—',
    },
    {
      field: 'description',
      headerName: 'Description',
      flex: 1.4,
      minWidth: 200,
      valueGetter: (value, row) => row.description || '—',
    },
    {
      field: 'table_count',
      headerName: 'Tables',
      width: 90,
      align: 'right',
      headerAlign: 'right',
      valueGetter: (value, row) => statsByModule[row.id]?.count || 0,
    },
    {
      field: 'quality',
      headerName: 'Quality',
      width: 150,
      sortable: false,
      renderCell: (params) => {
        const s = statsByModule[params.row.id] || { count: 0, failing: 0, warning: 0 };
        return (
          <Stack direction="row" spacing={0.5}>
            {s.failing > 0 && <Chip label={`${s.failing} failing`} size="small" color="error" variant="outlined" />}
            {s.warning > 0 && <Chip label={`${s.warning} warning`} size="small" color="warning" variant="outlined" />}
          </Stack>
        );
      },
    },
    {
      field: 'modified',
      headerName: 'Modified',
      width: 170,
      valueGetter: (value, row) => statsByModule[row.id]?.updated || null,
      valueFormatter: (value) => formatModified(value),
    },
    ...(canManage
      ? [
          {
            field: 'actions',
            headerName: 'Actions',
            width: 120,
            sortable: false,
            renderCell: (params) => (
              <Box sx={{ display: 'flex', gap: 0.5 }}>
                <Tooltip title="Open data product">
                  <IconButton size="small" onClick={() => navigate(`/catalog/products/${params.row.id}`)}>
                    <VisibilityIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
                <Tooltip title="Edit">
                  <IconButton size="small" onClick={() => openEdit(params.row)}>
                    <EditIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
                <Tooltip title="Delete">
                  <IconButton size="small" onClick={() => setDeleteConfirm(params.row)} sx={{ color: 'error.main' }}>
                    <DeleteIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              </Box>
            ),
          },
        ]
      : []),
  ], [navigate, statsByModule, canManage, openEdit]);

  // Delete confirmation message — table-count warning when tables exist
  const deleteMessage = useMemo(() => {
    if (!deleteConfirm) return '';
    const count = statsByModule[deleteConfirm.id]?.count || 0;
    return count > 0
      ? `"${deleteConfirm.name}" has ${count} table${count !== 1 ? 's' : ''}. Deleting it may remove associated data. This action cannot be undone.`
      : `Delete data product "${deleteConfirm.name}"? This action cannot be undone.`;
  }, [deleteConfirm, statsByModule]);

  return (
    <Box sx={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {error && <Alert severity="error" sx={{ mx: 2, mt: 2, flexShrink: 0 }}>{error}</Alert>}

      <FilteredDataGrid
        title={DATA_PRODUCTS}
        subtitle={`${filtered.length} of ${modules.length} data products`}
        description="Data products bundle related tables under a single governance policy with version tracking, access control, and lineage metadata."
        actions={
          canManage ? (
            <Button variant="contained" size="small" startIcon={<AddIcon />} onClick={openCreate}>
              New {DATA_PRODUCT}
            </Button>
          ) : null
        }
        rows={filtered}
        loading={loading}
        columns={columns}
        countLabel={`${filtered.length} of ${modules.length} data products`}
        searchValue={searchText}
        onSearchChange={setSearchText}
        filterDefs={[
          {
            key: 'org_unit',
            label: 'Org Unit',
            emptyLabel: 'All Org Units',
            options: orgUnits.map((ou) => ({ value: String(ou.id), label: ou.name })),
          },
        ]}
        filterValues={{ org_unit: filterOrgUnit }}
        onFilterChange={(key, value) => {
          if (key === 'org_unit') setFilterOrgUnit(value);
        }}
        onClearFilters={handleClearFilters}
        pageSize={25}
        rowsPerPageOptions={[25, 50, 100]}
        emptyMessage="No data products available"
        emptySubtext={hasFilters ? 'Try adjusting your filters' : 'Create a data product to group related tables'}
      />

      {/* Create/Edit Dialog (modal — design system primitive) */}
      <SystemDialog
        open={dialogOpen}
        title={editing ? `Edit ${DATA_PRODUCT}` : `New ${DATA_PRODUCT}`}
        onClose={closeDialog}
        onCancel={closeDialog}
        cancelLabel="Cancel"
        actions={
          <Button variant="contained" size="small" onClick={handleSubmit} disabled={submitting}>
            {submitting ? 'Saving…' : 'Save'}
          </Button>
        }
        width={520}
        height={560}
        minWidth={420}
        minHeight={460}
        maxWidth="calc(100vw - 32px)"
        maxHeight="calc(100vh - 32px)"
      >
        <ProductForm
          form={form}
          onChange={setForm}
          orgUnits={orgUnits}
          readOnly={false}
        />
      </SystemDialog>

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        open={!!deleteConfirm}
        title={`Delete ${DATA_PRODUCT}?`}
        message={deleteMessage}
        confirmLabel="Delete"
        destructive
        onConfirm={() => handleDelete(deleteConfirm)}
        onCancel={() => setDeleteConfirm(null)}
      />
    </Box>
  );
}
