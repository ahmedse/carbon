// src/pages/catalog/SchemaCatalogPage.jsx
// Schema Catalog: Browsable registry with filters and search
import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import {
  Box, Typography, TextField, Button, Card, CardContent, CardHeader, Grid,
  CircularProgress, Alert, Chip, MenuItem, Paper, FormControl, InputLabel, Select, InputAdornment,
  IconButton, Tooltip, Dialog, DialogTitle, DialogContent, DialogActions,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import RefreshIcon from '@mui/icons-material/Refresh';
import StorageIcon from '@mui/icons-material/Storage';
import VisibilityIcon from '@mui/icons-material/Visibility';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import { createDataSchemaTable, deleteDataSchemaTable, fetchDataSchemaTables, updateDataSchemaTable } from '../../api/dataschema';
import { fetchDataDomains, fetchAssetProfiles } from '../../api/catalog';

export default function SchemaCatalogPage() {
  const navigate = useNavigate();
  const { token, user, context } = useAuth();
  const { notify, notifyFromError } = useNotification();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [tables, setTables] = useState([]);
  const [domains, setDomains] = useState([]);
  const [assets, setAssets] = useState({});
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedDomain, setSelectedDomain] = useState('');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState('create');
  const [editingTable, setEditingTable] = useState(null);
  const [formData, setFormData] = useState({ title: '', description: '', module: '' });
  const [submitting, setSubmitting] = useState(false);

  const isAdmin = Boolean(
    user?.is_superuser ||
    (user?.roles || []).some((role) => role?.active !== false && (role.role === 'admins_group' || role.role === 'admin'))
  );

  useEffect(() => {
    loadData();
  }, [token]);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [tablesData, domainsData, assetsData] = await Promise.all([
        fetchDataSchemaTables(token, null, null),
        fetchDataDomains(token),
        fetchAssetProfiles(token).catch(() => []),
      ]);

      setTables(tablesData || []);
      setDomains(domainsData || []);

      const assetMap = {};
      (assetsData || []).forEach((asset) => {
        if (asset.data_table != null) assetMap[asset.data_table] = asset;
      });
      setAssets(assetMap);
    } catch (err) {
      const msg = err.message || 'Failed to load schema catalog';
      setError(msg);
      notify({ message: msg, type: 'error' });
    } finally {
      setLoading(false);
    }
  }, [token, notify]);

  const filteredTables = tables.filter((table) => {
    const matchesSearch = !searchTerm ||
      table.title?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      table.description?.toLowerCase().includes(searchTerm.toLowerCase());

    const matchesDomain = !selectedDomain || assets[table.id]?.domain === parseInt(selectedDomain, 10);

    return matchesSearch && matchesDomain;
  });

  const getAssetProfile = (tableId) => assets[tableId] || {};

  const closeDialog = () => {
    setDialogOpen(false);
    setEditingTable(null);
    setFormData({ title: '', description: '', module: context?.modules?.[0]?.id || '' });
  };

  const openCreateDialog = () => {
    setDialogMode('create');
    setEditingTable(null);
    setFormData({ title: '', description: '', module: context?.modules?.[0]?.id || '' });
    setDialogOpen(true);
  };

  const openEditDialog = (table) => {
    setDialogMode('edit');
    setEditingTable(table);
    setFormData({
      title: table.title || '',
      description: table.description || '',
      module: table.module || table.module_id || '',
    });
    setDialogOpen(true);
  };

  const handleSubmit = async () => {
    if (!formData.title.trim()) {
      notify({ message: 'Title is required', type: 'error' });
      return;
    }
    if (!formData.module) {
      notify({ message: 'Please choose a module', type: 'error' });
      return;
    }

    setSubmitting(true);
    try {
      const payload = {
        title: formData.title.trim(),
        description: formData.description.trim(),
        module: Number(formData.module),
      };
      const moduleId = Number(formData.module);

      if (dialogMode === 'edit' && editingTable) {
        await updateDataSchemaTable(token, editingTable.id, payload, context?.project_id || null, moduleId);
        notify({ message: 'Table updated', type: 'success' });
      } else {
        const created = await createDataSchemaTable(token, payload, context?.project_id || null, moduleId);
        notify({ message: 'Table created', type: 'success' });
        if (created?.id) {
          navigate(`/catalog/schemas/${created.id}`);
          return;
        }
      }
      closeDialog();
      await loadData();
    } catch (err) {
      notify({ message: err.message || 'Failed to save table', type: 'error' });
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteTable = async (table) => {
    if (!window.confirm(`Delete table "${table.title}"?`)) return;
    try {
      await deleteDataSchemaTable(token, table.id, context?.project_id || null, table.module || table.module_id || null);
      notify({ message: 'Table deleted', type: 'success' });
      await loadData();
    } catch (err) {
      notifyFromError(err, 'Failed to delete table');
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1.5, mb: 2, flexWrap: 'wrap' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <StorageIcon sx={{ fontSize: '2rem', color: 'primary.main' }} />
            <Box>
              <Typography variant="h5" fontWeight={700}>Schema Catalog</Typography>
              <Typography variant="body2" color="text.secondary">
                Browse all registered data tables and their metadata
              </Typography>
            </Box>
          </Box>
          {isAdmin && (
            <Button variant="contained" startIcon={<AddIcon />} onClick={openCreateDialog}>
              New Table
            </Button>
          )}
        </Box>
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <Paper sx={{ p: 2, mb: 3 }}>
        <Grid container spacing={2} alignItems="flex-end">
          <Grid item xs={12} sm={6}>
            <TextField
              fullWidth
              size="small"
              placeholder="Search tables..."
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon sx={{ color: 'action.disabled' }} />
                  </InputAdornment>
                ),
              }}
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
              variant="outlined"
            />
          </Grid>
          <Grid item xs={12} sm={4}>
            <FormControl fullWidth size="small">
              <InputLabel>Domain</InputLabel>
              <Select
                value={selectedDomain}
                label="Domain"
                onChange={(event) => setSelectedDomain(event.target.value)}
              >
                <MenuItem value="">All Domains</MenuItem>
                {domains.map((domain) => (
                  <MenuItem key={domain.id} value={domain.id}>{domain.name}</MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} sm={2}>
            <Button
              fullWidth
              size="small"
              variant="outlined"
              startIcon={<RefreshIcon />}
              onClick={loadData}
            >
              Refresh
            </Button>
          </Grid>
        </Grid>
      </Paper>

      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Showing {filteredTables.length} of {tables.length} tables
      </Typography>

      {filteredTables.length === 0 ? (
        <Alert severity="info">No tables match your filters</Alert>
      ) : (
        <Grid container spacing={2}>
          {filteredTables.map((table) => {
            const asset = getAssetProfile(table.id);
            const fieldCount = table.fields_count ?? table.field_count;
            const showFieldCount = fieldCount != null && fieldCount !== '' && Number(fieldCount) > 0;
            return (
              <Grid item xs={12} sm={6} md={4} key={table.id}>
                <Card
                  sx={{
                    height: '100%',
                    display: 'flex',
                    flexDirection: 'column',
                    border: '1px solid',
                    borderColor: 'divider',
                  }}
                >
                  <CardHeader
                    avatar={<StorageIcon sx={{ color: 'primary.main' }} />}
                    action={
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                        <Tooltip title="View schema details">
                          <IconButton onClick={() => navigate(`/catalog/schemas/${table.id}`)}>
                            <VisibilityIcon />
                          </IconButton>
                        </Tooltip>
                        {isAdmin && (
                          <>
                            <Tooltip title="Edit table">
                              <IconButton onClick={() => openEditDialog(table)}>
                                <EditIcon />
                              </IconButton>
                            </Tooltip>
                            <Tooltip title="Delete table">
                              <IconButton color="error" onClick={() => handleDeleteTable(table)}>
                                <DeleteIcon />
                              </IconButton>
                            </Tooltip>
                          </>
                        )}
                      </Box>
                    }
                    title={table.title}
                    titleTypographyProps={{ variant: 'subtitle1', fontWeight: 600 }}
                    subheader={asset?.domain ? <Chip label={asset.domain} size="small" variant="outlined" /> : null}
                    sx={{ pb: 1 }}
                  />
                  <CardContent sx={{ pt: 0, flex: 1, display: 'flex', flexDirection: 'column' }}>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 2, flex: 1 }}>
                      {table.description || 'No description'}
                    </Typography>

                    <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                      {showFieldCount && (
                        <Chip label={`${fieldCount} fields`} size="small" variant="outlined" />
                      )}
                      {asset?.classification && (
                        <Chip label={asset.classification} size="small" color="primary" variant="outlined" />
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
        <DialogTitle>{dialogMode === 'edit' ? 'Edit Table' : 'Create Table'}</DialogTitle>
        <DialogContent dividers>
          <TextField
            fullWidth
            label="Title"
            value={formData.title}
            onChange={(event) => setFormData((current) => ({ ...current, title: event.target.value }))}
            margin="normal"
          />
          <TextField
            fullWidth
            label="Description"
            value={formData.description}
            onChange={(event) => setFormData((current) => ({ ...current, description: event.target.value }))}
            margin="normal"
            multiline
            rows={3}
          />
          <TextField
            fullWidth
            select
            label="Module"
            value={formData.module}
            onChange={(event) => setFormData((current) => ({ ...current, module: event.target.value }))}
            margin="normal"
          >
            {context?.modules?.map((module) => (
              <MenuItem key={module.id} value={module.id}>
                {module.name}
              </MenuItem>
            ))}
          </TextField>
        </DialogContent>
        <DialogActions>
          <Button onClick={closeDialog}>Cancel</Button>
          <Button onClick={handleSubmit} variant="contained" disabled={submitting}>
            {submitting ? 'Saving...' : dialogMode === 'edit' ? 'Save Changes' : 'Create Table'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
