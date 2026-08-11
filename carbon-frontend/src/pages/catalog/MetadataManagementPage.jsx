// src/pages/catalog/MetadataManagementPage.jsx
// Consolidated metadata management: Domains, Glossary, Tags in one place

import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import SystemDialog from '../../components/SystemDialog';
import ConfirmDialog from '../../components/ConfirmDialog';
import {
  Autocomplete,
  Box,
  Button,
  Card,
  Chip,
  CircularProgress,
  IconButton,
  Paper,
  Select,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Tabs,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import useDocumentTitle from '../../hooks/useDocumentTitle';

import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import LabelIcon from '@mui/icons-material/Label';
import LocationOnIcon from '@mui/icons-material/LocationOn';
import MenuBookIcon from '@mui/icons-material/MenuBook';
import {
  fetchDataDomains,
  createDataDomain,
  updateDataDomain,
  deleteDataDomain,
  fetchGlossaryTerms,
  createGlossaryTerm,
  updateGlossaryTerm,
  deleteGlossaryTerm,
  fetchTags,
  createTag,
  updateTag,
  deleteTag,
} from '../../api/catalog';

export default function MetadataManagementPage() {
  useDocumentTitle("Metadata");
  const location = useLocation();
  const navigate = useNavigate();
  const { token } = useAuth();
  const { notify } = useNotification();

  // Determine initial tab from URL hash or default to 0
  const getInitialTab = () => {
    const hash = location.hash.slice(1); // Remove '#'
    if (hash === 'glossary') return 1;
    if (hash === 'tags') return 2;
    return 0; // domains
  };

  const [tabIndex, setTabIndex] = useState(getInitialTab);
  const [loading, setLoading] = useState(true);
  const [domains, setDomains] = useState([]);
  const [glossaryTerms, setGlossaryTerms] = useState([]);
  const [tags, setTags] = useState([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingItem, setEditingItem] = useState(null);
  const [formData, setFormData] = useState({});
  const [saving, setSaving] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(null);

  useEffect(() => {
    loadData();
  }, [token]);

  // Sync URL hash with tab
  useEffect(() => {
    const tabNames = ['domains', 'glossary', 'tags'];
    const newHash = `#${tabNames[tabIndex]}`;
    if (location.hash !== newHash) {
      navigate(location.pathname + newHash, { replace: true });
    }
  }, [tabIndex, location.hash, location.pathname, navigate]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [domainsData, glossaryData, tagsData] = await Promise.all([
        fetchDataDomains(token).catch(() => []),
        fetchGlossaryTerms(token).catch(() => []),
        fetchTags(token).catch(() => []),
      ]);
      setDomains(Array.isArray(domainsData) ? domainsData : domainsData?.results || []);
      setGlossaryTerms(Array.isArray(glossaryData) ? glossaryData : glossaryData?.results || []);
      setTags(Array.isArray(tagsData) ? tagsData : tagsData?.results || []);
    } catch (err) {
      notify({ message: err.message || 'Failed to load metadata', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const handleTabChange = (event, newValue) => {
    setTabIndex(newValue);
  };

  const openCreateDialog = () => {
    setEditingItem(null);
    if (tabIndex === 0) {
      // Domains
      setFormData({ name: '', description: '' });
    } else if (tabIndex === 1) {
      // Glossary
      setFormData({ name: '', definition: '', domain: '' });
    } else {
      // Tags
      setFormData({ name: '', color: '#2563eb' });
    }
    setDialogOpen(true);
  };

  const openEditDialog = (item) => {
    setEditingItem(item);
    if (tabIndex === 0) {
      setFormData({ name: item.name, description: item.description || '' });
    } else if (tabIndex === 1) {
      setFormData({ name: item.name, definition: item.definition || '', domain: item.domain || '' });
    } else {
      setFormData({ name: item.name, color: item.color || '#2563eb' });
    }
    setDialogOpen(true);
  };

  const handleSave = async () => {
    if (!formData.name?.trim()) {
      notify({ message: 'Name is required', type: 'error' });
      return;
    }

    setSaving(true);
    try {
      if (tabIndex === 0) {
        // Domains
        if (editingItem) {
          await updateDataDomain(token, editingItem.id, formData);
          notify({ message: 'Domain updated', type: 'success' });
        } else {
          await createDataDomain(token, formData);
          notify({ message: 'Domain created', type: 'success' });
        }
      } else if (tabIndex === 1) {
        // Glossary
        if (editingItem) {
          await updateGlossaryTerm(token, editingItem.id, formData);
          notify({ message: 'Term updated', type: 'success' });
        } else {
          await createGlossaryTerm(token, formData);
          notify({ message: 'Term created', type: 'success' });
        }
      } else {
        // Tags
        if (editingItem) {
          await updateTag(token, editingItem.id, formData);
          notify({ message: 'Tag updated', type: 'success' });
        } else {
          await createTag(token, formData);
          notify({ message: 'Tag created', type: 'success' });
        }
      }
      setDialogOpen(false);
      await loadData();
    } catch (err) {
      notify({ message: err.message || 'Save failed', type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (item) => {
    const itemType = tabIndex === 0 ? 'domain' : tabIndex === 1 ? 'term' : 'tag';
    try {
      if (tabIndex === 0) {
        await deleteDataDomain(token, item.id);
      } else if (tabIndex === 1) {
        await deleteGlossaryTerm(token, item.id);
      } else {
        await deleteTag(token, item.id);
      }
      notify({ message: `${itemType.charAt(0).toUpperCase() + itemType.slice(1)} deleted`, type: 'success' });
      setDeleteConfirm(null);
      await loadData();
    } catch (err) {
      if (err.status === 405 && err.data && err.data.detail) {
        notify({
          message: err.data.detail,
          type: 'warning',
        });
      } else {
        notify({ message: err.message || 'Delete failed', type: 'error' });
      }
    }
  };

  const renderDomainsTab = () => (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h6">Data Domains</Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={openCreateDialog}>
          New Domain
        </Button>
      </Box>
      <Paper variant="outlined">
        <Table>
          <TableHead>
            <TableRow sx={{ bgcolor: 'action.hover' }}>
              <TableCell sx={{ fontWeight: 600 }}>Name</TableCell>
              <TableCell sx={{ fontWeight: 600 }}>Description</TableCell>
              <TableCell sx={{ fontWeight: 600 }} align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {domains.length === 0 ? (
              <TableRow>
                <TableCell colSpan={3} align="center">
                  <Typography color="text.secondary" sx={{ py: 2 }}>No domains defined</Typography>
                </TableCell>
              </TableRow>
            ) : (
              domains.map((domain) => (
                <TableRow key={domain.id} hover>
                  <TableCell>{domain.name}</TableCell>
                  <TableCell>{domain.description || '—'}</TableCell>
                  <TableCell align="right">
                    <Tooltip title="Edit">
                      <IconButton size="small" onClick={() => openEditDialog(domain)}>
                        <EditIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Delete">
                      <IconButton size="small" color="error" onClick={() => setDeleteConfirm(domain)}>
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </Paper>
    </Box>
  );

  const renderGlossaryTab = () => (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h6">Glossary Terms</Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={openCreateDialog}>
          New Term
        </Button>
      </Box>
      <Paper variant="outlined">
        <Table>
          <TableHead>
            <TableRow sx={{ bgcolor: 'action.hover' }}>
              <TableCell sx={{ fontWeight: 600 }}>Term</TableCell>
              <TableCell sx={{ fontWeight: 600 }}>Definition</TableCell>
              <TableCell sx={{ fontWeight: 600 }}>Domain</TableCell>
              <TableCell sx={{ fontWeight: 600 }} align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {glossaryTerms.length === 0 ? (
              <TableRow>
                <TableCell colSpan={4} align="center">
                  <Typography color="text.secondary" sx={{ py: 2 }}>No terms defined</Typography>
                </TableCell>
              </TableRow>
            ) : (
              glossaryTerms.map((term) => (
                <TableRow key={term.id} hover>
                  <TableCell>{term.name}</TableCell>
                  <TableCell>{term.definition || '—'}</TableCell>
                  <TableCell>
                    {term.domain ? (
                      domains.find((d) => d.id === term.domain)?.name || term.domain
                    ) : (
                      '—'
                    )}
                  </TableCell>
                  <TableCell align="right">
                    <Tooltip title="Edit">
                      <IconButton size="small" onClick={() => openEditDialog(term)}>
                        <EditIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Delete">
                      <IconButton size="small" color="error" onClick={() => setDeleteConfirm(term)}>
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </Paper>
    </Box>
  );

  const renderTagsTab = () => (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h6">Tags</Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={openCreateDialog}>
          New Tag
        </Button>
      </Box>
      <Paper variant="outlined">
        <Table>
          <TableHead>
            <TableRow sx={{ bgcolor: 'action.hover' }}>
              <TableCell sx={{ fontWeight: 600 }}>Name</TableCell>
              <TableCell sx={{ fontWeight: 600 }}>Preview</TableCell>
              <TableCell sx={{ fontWeight: 600 }} align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {tags.length === 0 ? (
              <TableRow>
                <TableCell colSpan={3} align="center">
                  <Typography color="text.secondary" sx={{ py: 2 }}>No tags defined</Typography>
                </TableCell>
              </TableRow>
            ) : (
              tags.map((tag) => (
                <TableRow key={tag.id} hover>
                  <TableCell>{tag.name}</TableCell>
                  <TableCell>
                    <Chip
                      label={tag.name}
                      size="small"
                      sx={{
                        bgcolor: tag.color || '#2563eb',
                        color: '#fff',
                      }}
                    />
                  </TableCell>
                  <TableCell align="right">
                    <Tooltip title="Edit">
                      <IconButton size="small" onClick={() => openEditDialog(tag)}>
                        <EditIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Delete">
                      <IconButton size="small" color="error" onClick={() => setDeleteConfirm(tag)}>
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </Paper>
    </Box>
  );

  const renderDialog = () => {
    const isEdit = Boolean(editingItem);
    const titles = ['Domain', 'Glossary Term', 'Tag'];
    const title = `${isEdit ? 'Edit' : 'New'} ${titles[tabIndex]}`;

    return (
      <SystemDialog
        open={dialogOpen}
        title={title}
        onClose={() => setDialogOpen(false)}
        onCancel={() => setDialogOpen(false)}
        cancelLabel="Cancel"
        width={480}
        height={400}
        minWidth={400}
        minHeight={320}
        maxWidth="calc(100vw - 32px)"
        maxHeight="calc(100vh - 32px)"
        actions={
          <Button variant="contained" size="small" onClick={handleSave} disabled={saving}>
            {saving ? 'Saving...' : 'Save'}
          </Button>
        }
      >
        <Box px={2} py={1}>
          <TextField
            fullWidth
            size="small"
            label="Name"
            value={formData.name || ''}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            margin="normal"
            required
          />
          {tabIndex === 0 && (
            <TextField
              fullWidth
              size="small"
              label="Description"
              value={formData.description || ''}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              margin="normal"
              multiline
              rows={3}
            />
          )}
          {tabIndex === 1 && (
            <>
              <TextField
                fullWidth
                size="small"
                label="Definition"
                value={formData.definition || ''}
                onChange={(e) => setFormData({ ...formData, definition: e.target.value })}
                margin="normal"
                multiline
                rows={3}
              />
              <Autocomplete
                value={domains.find((d) => d.id === (formData.domain || null)) || null}
                options={domains}
                getOptionLabel={(d) => d.name}
                isOptionEqualToValue={(opt, val) => opt.id === val.id}
                onChange={(e, val) => setFormData({ ...formData, domain: val?.id || '' })}
                renderInput={(params) => <TextField {...params} label="Domain" size="small" margin="normal" />}
              />
            </>
          )}
          {tabIndex === 2 && (
            <TextField
              fullWidth
              size="small"
              label="Color"
              type="color"
              value={formData.color || '#2563eb'}
              onChange={(e) => setFormData({ ...formData, color: e.target.value })}
              margin="normal"
            />
          )}
        </Box>
      </SystemDialog>
    );
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
        <Typography variant="h5" fontWeight={700} gutterBottom>
          Metadata Management
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Manage domains, glossary terms, and tags for organizing your data catalog
        </Typography>
      </Box>

      <Paper sx={{ borderBottom: 1, borderColor: 'divider', mb: 3 }}>
        <Tabs value={tabIndex} onChange={handleTabChange}>
          <Tab
            icon={<LocationOnIcon />}
            iconPosition="start"
            label="Domains"
            sx={{ textTransform: 'none', minHeight: 48 }}
          />
          <Tab
            icon={<MenuBookIcon />}
            iconPosition="start"
            label="Glossary"
            sx={{ textTransform: 'none', minHeight: 48 }}
          />
          <Tab
            icon={<LabelIcon />}
            iconPosition="start"
            label="Tags"
            sx={{ textTransform: 'none', minHeight: 48 }}
          />
        </Tabs>
      </Paper>

      {tabIndex === 0 && renderDomainsTab()}
      {tabIndex === 1 && renderGlossaryTab()}
      {tabIndex === 2 && renderTagsTab()}

      {renderDialog()}

      {/* Delete confirmation (ConfirmDialog — no window.confirm) */}
      <ConfirmDialog
        open={!!deleteConfirm}
        title="Delete item?"
        message={`Delete "${deleteConfirm?.name || deleteConfirm?.term || 'item'}"? This action cannot be undone.`}
        confirmLabel="Delete"
        destructive
        onConfirm={() => handleDelete(deleteConfirm)}
        onCancel={() => setDeleteConfirm(null)}
      />
    </Box>
  );
}
