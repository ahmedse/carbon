// src/pages/catalog/DataProductDetailPage.jsx
// Catalog Studio: a single Data Product (Module) and its tables.
import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import {
  Box, Typography, TextField, Button, Card, CardContent, CardHeader, Grid,
  CircularProgress, Alert, Chip, Paper, IconButton, Tooltip,
  Dialog, DialogTitle, DialogContent, DialogActions,
} from '@mui/material';
import Inventory2Icon from '@mui/icons-material/Inventory2';
import TableChartIcon from '@mui/icons-material/TableChart';
import VisibilityIcon from '@mui/icons-material/Visibility';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import AddIcon from '@mui/icons-material/Add';
import MenuItem from '@mui/material/MenuItem';
import {
  fetchDataSchemaTables, createDataSchemaTable, updateDataSchemaTable, deleteDataSchemaTable,
} from '../../api/dataschema';
import { fetchAssetProfiles } from '../../api/catalog';
import { updateModule, deleteModule } from '../../api/modules';
import { fetchOrgUnits } from '../../api/orgUnits';
import { DATA_PRODUCTS, DATA_PRODUCT } from '../../constants/terminology';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/layout/PageHeader';

const QUALITY_COLOR = { passing: 'success', warning: 'warning', failing: 'error', unknown: 'default' };
const SCOPE_LABEL = { 1: 'Scope 1', 2: 'Scope 2', 3: 'Scope 3' };
const SCOPE_OPTIONS = [1, 2, 3];

export default function DataProductDetailPage() {
  const { moduleId } = useParams();
  const navigate = useNavigate();
  const { token, user, context, selectProject } = useAuth();
  const { notify, notifyFromError } = useNotification();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [tables, setTables] = useState([]);
  const [assets, setAssets] = useState({});
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingTable, setEditingTable] = useState(null);
  const [formData, setFormData] = useState({ title: '', description: '' });
  const [submitting, setSubmitting] = useState(false);
  const [orgUnits, setOrgUnits] = useState([]);
  const [productDialogOpen, setProductDialogOpen] = useState(false);
  const [productForm, setProductForm] = useState({ name: '', description: '', scope: 1, org_unit: '' });
  const [productSubmitting, setProductSubmitting] = useState(false);

  const module = (context?.modules || []).find((m) => String(m.id) === String(moduleId));

  const isAdmin = Boolean(
    user?.is_superuser ||
    (user?.roles || []).some((r) => r?.active !== false && (r.role === 'admins_group' || r.role === 'admin'))
  );

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [tablesData, assetsData, orgUnitsData] = await Promise.all([
        fetchDataSchemaTables(token, null, moduleId),
        fetchAssetProfiles(token).catch(() => []),
        fetchOrgUnits(token).catch(() => []),
      ]);
      setTables(Array.isArray(tablesData) ? tablesData : tablesData?.results || []);
      setOrgUnits(Array.isArray(orgUnitsData) ? orgUnitsData : orgUnitsData?.results || []);
      const map = {};
      (Array.isArray(assetsData) ? assetsData : assetsData?.results || []).forEach((a) => {
        if (a.data_table != null && !a.data_field) map[a.data_table] = a;
      });
      setAssets(map);
    } catch (err) {
      const msg = err.message || 'Failed to load data product';
      setError(msg);
      notify({ message: msg, type: 'error' });
    } finally {
      setLoading(false);
    }
  }, [token, moduleId, notify]);

  useEffect(() => { loadData(); }, [loadData]);

  const openCreate = () => { setEditingTable(null); setFormData({ title: '', description: '' }); setDialogOpen(true); };
  const openEdit = (t) => { setEditingTable(t); setFormData({ title: t.title || '', description: t.description || '' }); setDialogOpen(true); };
  const closeDialog = () => { setDialogOpen(false); setEditingTable(null); };

  const openProductEdit = () => {
    setProductForm({
      name: module?.name || '',
      description: module?.description || '',
      scope: module?.scope || 1,
      org_unit: module?.org_unit ?? '',
    });
    setProductDialogOpen(true);
  };
  const closeProductDialog = () => { if (!productSubmitting) setProductDialogOpen(false); };

  const handleProductSave = async () => {
    if (!productForm.name.trim()) { notify({ message: 'Name is required', type: 'error' }); return; }
    setProductSubmitting(true);
    try {
      await updateModule(token, moduleId, {
        name: productForm.name.trim(),
        description: productForm.description.trim(),
        scope: Number(productForm.scope),
        org_unit: productForm.org_unit === '' ? null : Number(productForm.org_unit),
      });
      notify({ message: `${DATA_PRODUCT} updated`, type: 'success' });
      setProductDialogOpen(false);
      await selectProject();
    } catch (err) {
      notify({ message: err.message || 'Save failed', type: 'error' });
    } finally {
      setProductSubmitting(false);
    }
  };

  const handleProductDelete = async () => {
    const count = tables.length;
    const warn = count > 0
      ? `"${module?.name}" has ${count} table${count !== 1 ? 's' : ''}. Deleting it may remove associated data. Continue?`
      : `Delete ${DATA_PRODUCT} "${module?.name}"?`;
    if (!window.confirm(warn)) return;
    try {
      await deleteModule(token, moduleId);
      notify({ message: `${DATA_PRODUCT} deleted`, type: 'success' });
      await selectProject();
      navigate('/catalog/products');
    } catch (err) {
      notifyFromError(err, 'Delete failed');
    }
  };

  const handleSubmit = async () => {
    if (!formData.title.trim()) { notify({ message: 'Title is required', type: 'error' }); return; }
    setSubmitting(true);
    try {
      const payload = { title: formData.title.trim(), description: formData.description.trim(), module: Number(moduleId) };
      if (editingTable) {
        await updateDataSchemaTable(token, editingTable.id, payload, null, Number(moduleId));
        notify({ message: 'Table updated', type: 'success' });
        closeDialog();
        await loadData();
      } else {
        const created = await createDataSchemaTable(token, payload, null, Number(moduleId));
        notify({ message: 'Table created', type: 'success' });
        closeDialog();
        if (created?.id) { navigate(`/catalog/tables/${created.id}`); return; }
        await loadData();
      }
    } catch (err) {
      notify({ message: err.message || 'Save failed', type: 'error' });
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (t) => {
    if (!window.confirm(`Delete table "${t.title}"?`)) return;
    try {
      await deleteDataSchemaTable(token, t.id, null, Number(moduleId));
      notify({ message: 'Table deleted', type: 'success' });
      await loadData();
    } catch (err) {
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

  if (!module) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error">Data product not found.</Alert>
      </Box>
    );
  }

  return (
    <PageContainer>
      <PageHeader
        icon={Inventory2Icon}
        title={module.name}
        subtitle={`${module.description || 'Data product'}${module.org_unit_name ? ` · ${module.org_unit_name}` : ''}`}
        actions={isAdmin && (
          <>
            <Button variant="outlined" startIcon={<EditIcon />} onClick={openProductEdit}>Edit</Button>
            <Button variant="outlined" color="error" startIcon={<DeleteIcon />} onClick={handleProductDelete}>Delete</Button>
            <Button variant="contained" startIcon={<AddIcon />} onClick={openCreate}>New Table</Button>
          </>
        )}
      />

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {tables.length === 0 ? (
        <Alert severity="info">No tables in this data product yet.</Alert>
      ) : (
        <Grid container spacing={2}>
          {tables.map((t) => {
            const q = assets[t.id]?.quality_status || 'unknown';
            return (
              <Grid size={{ xs: 12, sm: 6, md: 4 }} key={t.id}>
                <Card
                  sx={{ height: '100%', display: 'flex', flexDirection: 'column',
                    border: '1px solid', borderColor: 'divider', cursor: 'pointer' }}
                  onClick={() => navigate(`/catalog/tables/${t.id}`)}
                >
                  <CardHeader
                    avatar={<TableChartIcon color="primary" />}
                    title={t.title}
                    titleTypographyProps={{ variant: 'subtitle1', fontWeight: 600 }}
                    action={
                      <Tooltip title="Open table">
                        <IconButton size="small" color="primary"
                          onClick={(e) => { e.stopPropagation(); navigate(`/catalog/tables/${t.id}`); }}>
                          <VisibilityIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    }
                  />
                  <CardContent sx={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                      {t.description || 'No description'}
                    </Typography>
                    <Box sx={{ mt: 'auto', display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                      <Chip label={q} size="small" color={QUALITY_COLOR[q] || 'default'} variant="outlined" />
                      {isAdmin && (
                        <Box sx={{ ml: 'auto', display: 'flex', gap: 0.5 }}>
                          <Tooltip title="Edit metadata">
                            <IconButton size="small" onClick={(e) => { e.stopPropagation(); openEdit(t); }}>
                              <EditIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                          <Tooltip title="Delete">
                            <IconButton size="small" onClick={(e) => { e.stopPropagation(); handleDelete(t); }}>
                              <DeleteIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        </Box>
                      )}
                    </Box>
                  </CardContent>
                </Card>
              </Grid>
            );
          })}
        </Grid>
      )}

      <Dialog open={dialogOpen} onClose={closeDialog} maxWidth="sm" fullWidth>
        <DialogTitle>{editingTable ? 'Edit Table' : 'New Table'}</DialogTitle>
        <DialogContent sx={{ pt: 2 }}>
          <TextField fullWidth label="Title" margin="normal" value={formData.title}
            onChange={(e) => setFormData({ ...formData, title: e.target.value })} />
          <TextField fullWidth label="Description" margin="normal" multiline rows={3} value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })} />
        </DialogContent>
        <DialogActions>
          <Button onClick={closeDialog}>Cancel</Button>
          <Button onClick={handleSubmit} variant="contained" disabled={submitting}>
            {submitting ? 'Saving…' : 'Save'}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={productDialogOpen} onClose={closeProductDialog} maxWidth="sm" fullWidth>
        <DialogTitle>Edit {DATA_PRODUCT}</DialogTitle>
        <DialogContent>
          <TextField
            fullWidth label="Name" margin="normal" value={productForm.name}
            onChange={(e) => setProductForm({ ...productForm, name: e.target.value })} autoFocus required
          />
          <TextField
            fullWidth label="Description" margin="normal" multiline rows={2} value={productForm.description}
            onChange={(e) => setProductForm({ ...productForm, description: e.target.value })}
          />
          <TextField
            select fullWidth label="Scope" margin="normal" value={productForm.scope}
            onChange={(e) => setProductForm({ ...productForm, scope: e.target.value })}
            helperText="Default GHG scope for this product's activity data"
          >
            {SCOPE_OPTIONS.map((s) => (
              <MenuItem key={s} value={s}>{SCOPE_LABEL[s]}</MenuItem>
            ))}
          </TextField>
          <TextField
            select fullWidth label="Org Unit" margin="normal" value={productForm.org_unit}
            onChange={(e) => setProductForm({ ...productForm, org_unit: e.target.value })}
            helperText="Owning organizational unit (governs access)"
          >
            <MenuItem value="">— None —</MenuItem>
            {orgUnits.map((ou) => (
              <MenuItem key={ou.id} value={ou.id}>{ou.name}</MenuItem>
            ))}
          </TextField>
        </DialogContent>
        <DialogActions>
          <Button onClick={closeProductDialog} disabled={productSubmitting}>Cancel</Button>
          <Button onClick={handleProductSave} variant="contained" disabled={productSubmitting}>
            {productSubmitting ? 'Saving…' : 'Save'}
          </Button>
        </DialogActions>
      </Dialog>
    </PageContainer>
  );
}
