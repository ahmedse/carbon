// src/pages/catalog/AssetsPage.jsx
// Catalog: Browse and manage asset profiles (metadata for tables/fields)

import React, { useState, useEffect } from 'react';
import { useAuth } from '../../auth/AuthContext';
import { fetchAssetProfiles, createAssetProfile, updateAssetProfile, deleteAssetProfile } from '../../api/catalog';
import {
  Box,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  IconButton,
  Tooltip,
  CircularProgress,
  Alert,
  Typography,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import AddIcon from '@mui/icons-material/Add';

export default function AssetsPage() {
  const { token } = useAuth();
  const [assets, setAssets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [openDialog, setOpenDialog] = useState(false);
  const [editingAsset, setEditingAsset] = useState(null);
  const [formData, setFormData] = useState({
    name: '',
    asset_type: 'table',
    description: '',
    owner: '',
  });

  const assetTypes = [
    { value: 'table', label: 'Table' },
    { value: 'field', label: 'Field' },
    { value: 'report', label: 'Report' },
    { value: 'dashboard', label: 'Dashboard' },
  ];

  useEffect(() => {
    loadAssets();
  }, []);

  const loadAssets = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchAssetProfiles(token);
      setAssets(Array.isArray(data) ? data : data.results || []);
    } catch (err) {
      setError(err.message || 'Failed to load assets');
    } finally {
      setLoading(false);
    }
  };

  const handleOpenDialog = (asset = null) => {
    if (asset) {
      setEditingAsset(asset);
      setFormData({
        name: asset.name,
        asset_type: asset.asset_type || 'table',
        description: asset.description || '',
        owner: asset.owner || '',
      });
    } else {
      setEditingAsset(null);
      setFormData({ name: '', asset_type: 'table', description: '', owner: '' });
    }
    setOpenDialog(true);
  };

  const handleCloseDialog = () => {
    setOpenDialog(false);
    setEditingAsset(null);
    setFormData({ name: '', asset_type: 'table', description: '', owner: '' });
  };

  const handleSave = async () => {
    try {
      if (editingAsset) {
        await updateAssetProfile(token, editingAsset.id, formData);
      } else {
        await createAssetProfile(token, formData);
      }
      await loadAssets();
      handleCloseDialog();
    } catch (err) {
      setError(err.message || 'Failed to save asset');
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Are you sure?')) return;
    try {
      await deleteAssetProfile(token, id);
      await loadAssets();
    } catch (err) {
      setError(err.message || 'Failed to delete asset');
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h5">Asset Profiles</Typography>
        <Button startIcon={<AddIcon />} variant="contained" onClick={() => handleOpenDialog()}>
          New Asset
        </Button>
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      ) : (
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow sx={{ bgcolor: 'background.alt' }}>
                <TableCell>Name</TableCell>
                <TableCell>Type</TableCell>
                <TableCell>Description</TableCell>
                <TableCell>Owner</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {assets.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} align="center" sx={{ py: 4 }}>
                    No assets found
                  </TableCell>
                </TableRow>
              ) : (
                assets.map((asset) => (
                  <TableRow key={asset.id} hover>
                    <TableCell sx={{ fontWeight: 500 }}>{asset.name}</TableCell>
                    <TableCell>{asset.asset_type}</TableCell>
                    <TableCell sx={{ maxWidth: 250, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {asset.description || '-'}
                    </TableCell>
                    <TableCell>{asset.owner_name || asset.owner || '-'}</TableCell>
                    <TableCell align="right">
                      <Tooltip title="Edit">
                        <IconButton
                          size="small"
                          onClick={() => handleOpenDialog(asset)}
                        >
                          <EditIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Delete">
                        <IconButton
                          size="small"
                          onClick={() => handleDelete(asset.id)}
                          color="error"
                        >
                          <DeleteIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {/* Create/Edit Dialog */}
      <Dialog open={openDialog} onClose={handleCloseDialog} maxWidth="sm" fullWidth>
        <DialogTitle>
          {editingAsset ? 'Edit Asset Profile' : 'New Asset Profile'}
        </DialogTitle>
        <DialogContent sx={{ pt: 2 }}>
          <TextField
            label="Name"
            fullWidth
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            margin="normal"
            autoFocus
          />
          <FormControl fullWidth margin="normal">
            <InputLabel>Asset Type</InputLabel>
            <Select
              value={formData.asset_type}
              onChange={(e) => setFormData({ ...formData, asset_type: e.target.value })}
              label="Asset Type"
            >
              {assetTypes.map((type) => (
                <MenuItem key={type.value} value={type.value}>
                  {type.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <TextField
            label="Description"
            fullWidth
            multiline
            rows={3}
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            margin="normal"
          />
          <TextField
            label="Owner"
            fullWidth
            value={formData.owner}
            onChange={(e) => setFormData({ ...formData, owner: e.target.value })}
            margin="normal"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>Cancel</Button>
          <Button onClick={handleSave} variant="contained">
            {editingAsset ? 'Update' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
