// src/pages/catalog/DataProductsPage.jsx
// Catalog Studio: browse Data Products (Modules). A Data Product groups tables,
// is org-owned, and is the governance container. (Code entity = Module.)
// AI-toolkit compliant: FilteredDataGrid shell, SystemDialog form, ConfirmDialog,
// can() manage gate (CB-13), useNotification, 4 data states, CB-09 defensive arrays.
import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
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
  const { t } = useTranslation('catalog');
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
      const msg = err.message || t('dataProductsLoadError');
      setError(msg);
      notify({ message: msg, type: 'error' });
    } finally {
      setLoading(false);
    }
  }, [token, notify, t]);

  useEffect(() => { loadData(); }, [loadData]);

  const openCreate = () => { setEditing(null); setForm(EMPTY_FORM); setDialogOpen(true); };
  const openEdit = useCallback((m) => {
    setEditing(m);
    setForm({ name: m.name || '', description: m.description || '', org_unit: m.org_unit ?? '' });
    setDialogOpen(true);
  }, []);
  const closeDialog = () => { if (!submitting) { setDialogOpen(false); setEditing(null); } };

  const handleSubmit = async () => {
    if (!form.name.trim()) { notify({ message: t('nameRequired'), type: 'error' }); return; }
    setSubmitting(true);
    try {
      const payload = {
        name: form.name.trim(),
        description: form.description.trim(),
        org_unit: form.org_unit === '' ? null : Number(form.org_unit),
      };
      if (editing) {
        await updateModule(token, editing.id, payload);
        notify({ message: t('dataProductUpdated'), type: 'success' });
      } else {
        await createModule(token, payload);
        notify({ message: t('dataProductCreated'), type: 'success' });
      }
      setDialogOpen(false);
      setEditing(null);
      await selectProject();
    } catch (err) {
      notify({ message: err.message || t('saveFailed'), type: 'error' });
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (m) => {
    try {
      await deleteModule(token, m.id);
      notify({ message: t('dataProductDeleted'), type: 'success' });
      setDeleteConfirm(null);
      await selectProject();
    } catch (err) {
      notifyFromError(err, t('deleteFailed'));
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
      headerName: t('name'),
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
      headerName: t('orgUnit'),
      width: 170,
      valueGetter: (value, row) => row.org_unit_name || '—',
    },
    {
      field: 'description',
      headerName: t('description'),
      flex: 1.4,
      minWidth: 200,
      valueGetter: (value, row) => row.description || '—',
    },
    {
      field: 'table_count',
      headerName: t('tables'),
      width: 90,
      align: 'right',
      headerAlign: 'right',
      valueGetter: (value, row) => statsByModule[row.id]?.count || 0,
    },
    {
      field: 'quality',
      headerName: t('quality'),
      width: 150,
      sortable: false,
      renderCell: (params) => {
        const s = statsByModule[params.row.id] || { count: 0, failing: 0, warning: 0 };
        return (
          <Stack direction="row" spacing={0.5}>
            {s.failing > 0 && <Chip label={t('failingCount', { count: s.failing })} size="small" color="error" variant="outlined" />}
            {s.warning > 0 && <Chip label={t('warningCount', { count: s.warning })} size="small" color="warning" variant="outlined" />}
          </Stack>
        );
      },
    },
    {
      field: 'modified',
      headerName: t('modified'),
      width: 170,
      valueGetter: (value, row) => statsByModule[row.id]?.updated || null,
      valueFormatter: (value) => formatModified(value),
    },
    ...(canManage
      ? [
          {
            field: 'actions',
            headerName: t('actions'),
            width: 120,
            sortable: false,
            renderCell: (params) => (
              <Box sx={{ display: 'flex', gap: 0.5 }}>
                <Tooltip title={t('openDataProduct')}>
                  <IconButton size="small" onClick={() => navigate(`/catalog/products/${params.row.id}`)}>
                    <VisibilityIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
                <Tooltip title={t('common:edit')}>
                  <IconButton size="small" onClick={() => openEdit(params.row)}>
                    <EditIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
                <Tooltip title={t('common:delete')}>
                  <IconButton size="small" onClick={() => setDeleteConfirm(params.row)} sx={{ color: 'error.main' }}>
                    <DeleteIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              </Box>
            ),
          },
        ]
      : []),
  ], [navigate, statsByModule, canManage, openEdit, t]);

  // Delete confirmation message — table-count warning when tables exist
  const deleteMessage = useMemo(() => {
    if (!deleteConfirm) return '';
    const count = statsByModule[deleteConfirm.id]?.count || 0;
    return count > 0
      ? t('deleteDataProductWithTables', { name: deleteConfirm.name, count })
      : t('deleteDataProductMessage', { name: deleteConfirm.name });
  }, [deleteConfirm, statsByModule, t]);

  return (
    <Box sx={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {error && <Alert severity="error" sx={{ mx: 2, mt: 2, flexShrink: 0 }}>{error}</Alert>}

      <FilteredDataGrid
        title={t('dataProducts')}
        subtitle={t('dataProductsCount', { shown: filtered.length, total: modules.length })}
        description={t('dataProductsDescription')}
        actions={
          canManage ? (
            <Button variant="contained" size="small" startIcon={<AddIcon />} onClick={openCreate}>
              {t('newDataProduct')}
            </Button>
          ) : null
        }
        rows={filtered}
        loading={loading}
        columns={columns}
        countLabel={t('dataProductsCount', { shown: filtered.length, total: modules.length })}
        searchValue={searchText}
        onSearchChange={setSearchText}
        filterDefs={[
          {
            key: 'org_unit',
            label: t('orgUnit'),
            emptyLabel: t('allOrgUnits'),
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
        emptyMessage={t('noDataProducts')}
        emptySubtext={hasFilters ? t('tryAdjustingFilters') : t('createDataProductHint')}
      />

      {/* Create/Edit Dialog (modal — design system primitive) */}
      <SystemDialog
        open={dialogOpen}
        title={editing ? t('editDataProduct') : t('newDataProduct')}
        onClose={closeDialog}
        onCancel={closeDialog}
        cancelLabel={t('common:cancel')}
        actions={
          <Button variant="contained" size="small" onClick={handleSubmit} disabled={submitting}>
            {submitting ? t('saving') : t('common:save')}
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
        title={t('deleteDataProductTitle')}
        message={deleteMessage}
        confirmLabel={t('common:delete')}
        destructive
        onConfirm={() => handleDelete(deleteConfirm)}
        onCancel={() => setDeleteConfirm(null)}
      />
    </Box>
  );
}
