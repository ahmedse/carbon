// src/pages/catalog/DataProductsPage.jsx
// Catalog Studio: browse Data Products (Modules). A Data Product groups tables,
// is org-owned, and is the governance container. (Code entity = Module.)
import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import {
  Box, Typography, TextField, Card, CardContent, CardHeader, Grid,
  CircularProgress, Alert, Chip, Paper, InputAdornment, IconButton, Tooltip,
  Button, Dialog, DialogTitle, DialogContent, DialogActions, MenuItem,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import RefreshIcon from '@mui/icons-material/Refresh';
import Inventory2Icon from '@mui/icons-material/Inventory2';
import VisibilityIcon from '@mui/icons-material/Visibility';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import AddIcon from '@mui/icons-material/Add';
import { fetchDataSchemaTables } from '../../api/dataschema';
import { fetchAssetProfiles } from '../../api/catalog';
import { createModule, updateModule, deleteModule } from '../../api/modules';
import { fetchOrgUnits } from '../../api/orgUnits';
import { DATA_PRODUCTS, DATA_PRODUCT } from '../../constants/terminology';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/layout/PageHeader';

const SCOPE_LABEL = { 1: 'Scope 1', 2: 'Scope 2', 3: 'Scope 3' };
const SCOPE_OPTIONS = [1, 2, 3];
const EMPTY_FORM = { name: '', description: '', scope: 1, org_unit: '' };

export default function DataProductsPage() {
  const navigate = useNavigate();
  const { token, user, context, selectProject } = useAuth();
  const { notify, notifyFromError } = useNotification();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [tables, setTables] = useState([]);
  const [assets, setAssets] = useState([]);
  const [search, setSearch] = useState('');
  const [orgUnits, setOrgUnits] = useState([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);

  const modules = context?.modules || [];

  const isAdmin = Boolean(
    user?.is_superuser ||
    (user?.roles || []).some((r) => r?.active !== false && (r.role === 'admins_group' || r.role === 'admin'))
  );

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
  const openEdit = (m) => {
    setEditing(m);
    setForm({ name: m.name || '', description: m.description || '', scope: m.scope || 1, org_unit: m.org_unit ?? '' });
    setDialogOpen(true);
  };
  const closeDialog = () => { if (!submitting) { setDialogOpen(false); setEditing(null); } };

  const handleSubmit = async () => {
    if (!form.name.trim()) { notify({ message: 'Name is required', type: 'error' }); return; }
    setSubmitting(true);
    try {
      const payload = {
        name: form.name.trim(),
        description: form.description.trim(),
        scope: Number(form.scope),
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
    const count = statsByModule[m.id]?.count || 0;
    const warn = count > 0
      ? `"${m.name}" has ${count} table${count !== 1 ? 's' : ''}. Deleting it may remove associated data. Continue?`
      : `Delete data product "${m.name}"?`;
    if (!window.confirm(warn)) return;
    try {
      await deleteModule(token, m.id);
      notify({ message: 'Data product deleted', type: 'success' });
      await selectProject();
    } catch (err) {
      notifyFromError(err, 'Delete failed');
    }
  };

  // Group tables + quality by module id.
  const statsByModule = useMemo(() => {
    const assetByTable = {};
    assets.forEach((a) => { if (a.data_table != null && !a.data_field) assetByTable[a.data_table] = a; });
    const map = {};
    tables.forEach((t) => {
      const mid = t.module ?? t.module_id;
      if (mid == null) return;
      if (!map[mid]) map[mid] = { count: 0, failing: 0, warning: 0 };
      map[mid].count += 1;
      const q = assetByTable[t.id]?.quality_status;
      if (q === 'failing') map[mid].failing += 1;
      else if (q === 'warning') map[mid].warning += 1;
    });
    return map;
  }, [tables, assets]);

  const filtered = modules.filter((m) => {
    if (!search) return true;
    const s = search.toLowerCase();
    return (m.name || '').toLowerCase().includes(s) || (m.description || '').toLowerCase().includes(s);
  });

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <PageContainer>
      <PageHeader
        icon={Inventory2Icon}
        title={DATA_PRODUCTS}
        subtitle="Governed, org-owned groupings of tables. Open one to manage its tables."
        actions={isAdmin && (
          <Button variant="contained" startIcon={<AddIcon />} onClick={openCreate}>
            New {DATA_PRODUCT}
          </Button>
        )}
      />

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <Paper sx={{ p: 1.5, mb: 2 }}>
        <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'center' }}>
          <TextField
            fullWidth size="small" placeholder="Search data products..."
            value={search} onChange={(e) => setSearch(e.target.value)}
            InputProps={{ startAdornment: (
              <InputAdornment position="start"><SearchIcon sx={{ color: 'action.disabled' }} /></InputAdornment>
            ) }}
          />
          <Tooltip title="Refresh">
            <IconButton onClick={loadData}><RefreshIcon /></IconButton>
          </Tooltip>
        </Box>
      </Paper>

      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1.5 }}>
        Showing {filtered.length} of {modules.length} data products
      </Typography>

      {filtered.length === 0 ? (
        <Alert severity="info">No data products available.</Alert>
      ) : (
        <Grid container spacing={2}>
          {filtered.map((m) => {
            const stats = statsByModule[m.id] || { count: 0, failing: 0, warning: 0 };
            return (
              <Grid size={{ xs: 12, sm: 6, md: 4 }} key={m.id}>
                <Card
                  sx={{ height: '100%', display: 'flex', flexDirection: 'column',
                    border: '1px solid', borderColor: 'divider', cursor: 'pointer' }}
                  onClick={() => navigate(`/catalog/products/${m.id}`)}
                >
                  <CardHeader
                    avatar={<Inventory2Icon color="primary" />}
                    title={m.name}
                    titleTypographyProps={{ variant: 'subtitle1', fontWeight: 600 }}
                    subheader={m.org_unit_name || '—'}
                    action={
                      <Box sx={{ display: 'flex' }} onClick={(e) => e.stopPropagation()}>
                        <Tooltip title="Open data product">
                          <IconButton size="small" color="primary"
                            onClick={() => navigate(`/catalog/products/${m.id}`)}>
                            <VisibilityIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        {isAdmin && (
                          <>
                            <Tooltip title="Edit">
                              <IconButton size="small" onClick={() => openEdit(m)}>
                                <EditIcon fontSize="small" />
                              </IconButton>
                            </Tooltip>
                            <Tooltip title="Delete">
                              <IconButton size="small" onClick={() => handleDelete(m)}>
                                <DeleteIcon fontSize="small" />
                              </IconButton>
                            </Tooltip>
                          </>
                        )}
                      </Box>
                    }
                  />
                  <CardContent sx={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                      {m.description || 'No description'}
                    </Typography>
                    <Box sx={{ mt: 'auto', display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                      <Chip label={`${stats.count} table${stats.count !== 1 ? 's' : ''}`} size="small" variant="outlined" />
                      {m.scope && <Chip label={SCOPE_LABEL[m.scope] || `Scope ${m.scope}`} size="small" variant="outlined" />}
                      {stats.failing > 0 && <Chip label={`${stats.failing} failing`} size="small" color="error" variant="outlined" />}
                      {stats.warning > 0 && <Chip label={`${stats.warning} warning`} size="small" color="warning" variant="outlined" />}
                    </Box>
                  </CardContent>
                </Card>
              </Grid>
            );
          })}
        </Grid>
      )}

      <Dialog open={dialogOpen} onClose={closeDialog} maxWidth="sm" fullWidth>
        <DialogTitle>{editing ? `Edit ${DATA_PRODUCT}` : `New ${DATA_PRODUCT}`}</DialogTitle>
        <DialogContent>
          <TextField
            fullWidth label="Name" margin="normal" value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })} autoFocus required
          />
          <TextField
            fullWidth label="Description" margin="normal" multiline rows={2} value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
          />
          <TextField
            select fullWidth label="Scope" margin="normal" value={form.scope}
            onChange={(e) => setForm({ ...form, scope: e.target.value })}
            helperText="Default GHG scope for this product's activity data"
          >
            {SCOPE_OPTIONS.map((s) => (
              <MenuItem key={s} value={s}>{SCOPE_LABEL[s]}</MenuItem>
            ))}
          </TextField>
          <TextField
            select fullWidth label="Org Unit" margin="normal" value={form.org_unit}
            onChange={(e) => setForm({ ...form, org_unit: e.target.value })}
            helperText="Owning organizational unit (governs access)"
          >
            <MenuItem value="">— None —</MenuItem>
            {orgUnits.map((ou) => (
              <MenuItem key={ou.id} value={ou.id}>{ou.name}</MenuItem>
            ))}
          </TextField>
        </DialogContent>
        <DialogActions>
          <Button onClick={closeDialog} disabled={submitting}>Cancel</Button>
          <Button onClick={handleSubmit} variant="contained" disabled={submitting}>
            {submitting ? 'Saving…' : 'Save'}
          </Button>
        </DialogActions>
      </Dialog>
    </PageContainer>
  );
}
