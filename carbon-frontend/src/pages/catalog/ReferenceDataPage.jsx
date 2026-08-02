// src/pages/catalog/ReferenceDataPage.jsx
// Reference Data: CRUD for reference sets (MDM Tier A)
import React, { useEffect, useState } from 'react';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import {
  Box, Button, IconButton, Dialog, DialogTitle, DialogContent,
  DialogActions, TextField, CircularProgress, Alert, Chip, Tooltip,
} from '@mui/material';
import useDocumentTitle from '../../hooks/useDocumentTitle';

import PageContainer from '../../components/layout/PageContainer';
import FilteredDataGrid from '../../components/FilteredDataGrid';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import AddIcon from '@mui/icons-material/Add';
import { fetchReferenceSets, createReferenceSet, updateReferenceSet, deleteReferenceSet } from '../../api/catalog';

const EMPTY_FORM = { name: '', description: '' };

export default function ReferenceDataPage() {
  useDocumentTitle("Reference Data");
  const { token } = useAuth();
  const { notify } = useNotification();

  const [sets, setSets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [_error, setError] = useState(null);
  const [openDialog, setOpenDialog] = useState(false);
  const [editingSet, setEditingSet] = useState(null);
  const [formData, setFormData] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [filterDomain, setFilterDomain] = useState('');

  useEffect(() => {
    loadSets();
  }, [token]);

  const loadSets = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchReferenceSets(token);
      setSets(data || []);
    } catch (err) {
      const msg = err.message || 'Failed to load reference sets';
      setError(msg);
      notify({ message: msg, type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const handleClearFilters = () => {
    setSearchText('');
    setFilterDomain('');
  };

  const openCreate = () => {
    setEditingSet(null);
    setFormData(EMPTY_FORM);
    setOpenDialog(true);
  };

  const openEdit = (set) => {
    setEditingSet(set);
    setFormData({ name: set.name, description: set.description || '' });
    setOpenDialog(true);
  };

  const handleSave = async () => {
    if (!formData.name.trim()) {
      notify({ message: 'Name is required', type: 'error' });
      return;
    }

    setSaving(true);
    setError(null);
    try {
      if (editingSet) {
        await updateReferenceSet(token, editingSet.id, formData);
        notify({ message: 'Reference set updated', type: 'success' });
      } else {
        await createReferenceSet(token, formData);
        notify({ message: 'Reference set created', type: 'success' });
      }
      setOpenDialog(false);
      loadSets();
    } catch (err) {
      const msg = err.message || 'Save failed';
      setError(msg);
      notify({ message: msg, type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (set) => {
    if (!window.confirm(`Delete reference set "${set.name}"?`)) return;
    try {
      await deleteReferenceSet(token, set.id);
      notify({ message: 'Reference set deleted', type: 'success' });
      loadSets();
    } catch (err) {
      setError(err.message || 'Delete failed');
      notify({ message: err.message || 'Delete failed', type: 'error' });
    }
  };

  if (loading) {
    return (
      <PageContainer>
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
          <CircularProgress />
        </Box>
      </PageContainer>
    );
  }

  return (
    <>
      <FilteredDataGrid
        title="Reference Data"
        subtitle="Manage master data reference sets used across the platform."
        actions={(
          <Button variant="contained" startIcon={<AddIcon />} onClick={openCreate}>
            New Set
          </Button>
        )}
        rows={sets}
        loading={loading}
        columns={[
          { field: 'name', headerName: 'Name', flex: 1, minWidth: 220 },
          { field: 'description', headerName: 'Description', flex: 2, minWidth: 260, renderCell: (params) => params.value || '—' },
          { field: 'value_count', headerName: 'Values', width: 110, renderCell: (params) => <Chip label={params.value || 0} size="small" /> },
          { field: 'domain_name', headerName: 'Domain', width: 160, renderCell: (params) => params.value || '—' },
          {
            field: 'actions',
            headerName: 'Actions',
            width: 150,
            sortable: false,
            renderCell: (params) => (
              <Box sx={{ display: 'flex', gap: 1 }}>
                <Tooltip title="Edit reference set">
                  <IconButton size="small" onClick={() => openEdit(params.row)}>
                    <EditIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
                <Tooltip title="Delete reference set">
                  <IconButton size="small" color="error" onClick={() => handleDelete(params.row)}>
                    <DeleteIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              </Box>
            ),
          },
        ]}
        pageSize={25}
        rowsPerPageOptions={[25, 50, 100]}
        hideFooterSelectedRowCount
        toolbar
        searchValue={searchText}
        onSearchChange={setSearchText}
        filterDefs={[
          {
            key: 'domain',
            label: 'Domain',
            emptyLabel: 'All Domains',
            options: [],
          },
        ]}
        filterValues={{ domain: filterDomain }}
        onFilterChange={(key, value) => {
          if (key === 'domain') setFilterDomain(value);
        }}
        onClearFilters={handleClearFilters}
        emptyMessage="No reference sets found"
        emptySubtext={searchText || filterDomain ? 'Try adjusting your filters' : 'Reference sets will appear here once created.'}
      />

      <Dialog open={openDialog} onClose={() => setOpenDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editingSet ? 'Edit Reference Set' : 'New Reference Set'}</DialogTitle>
        <DialogContent sx={{ pt: 2 }}>
          <TextField
            fullWidth
            label="Name"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            margin="normal"
          />
          <TextField
            fullWidth
            label="Description"
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            margin="normal"
            multiline
            rows={3}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenDialog(false)}>Cancel</Button>
          <Button onClick={handleSave} variant="contained" disabled={saving}>
            {saving ? 'Saving...' : 'Save'}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
    