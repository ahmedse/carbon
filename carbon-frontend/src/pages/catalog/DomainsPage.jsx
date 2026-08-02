// src/pages/catalog/DomainsPage.jsx
// Catalog: Browse and manage data domains with governance metadata

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import { fetchDataDomains, createDataDomain, updateDataDomain, deleteDataDomain } from '../../api/catalog';
import {
  Box,
  Button,
  Card,
  CardContent,
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
} from '@mui/material';
import useDocumentTitle from '../../hooks/useDocumentTitle';

import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import AddIcon from '@mui/icons-material/Add';
import VisibilityIcon from '@mui/icons-material/Visibility';

export default function DomainsPage() {
  useDocumentTitle("Domains");
  const navigate = useNavigate();
  const { token } = useAuth();
  const [domains, setDomains] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [openDialog, setOpenDialog] = useState(false);
  const [editingDomain, setEditingDomain] = useState(null);
  const [formData, setFormData] = useState({ name: '', description: '' });

  // Load domains on mount
  useEffect(() => {
    loadDomains();
  }, []);

  const loadDomains = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchDataDomains(token);
      setDomains(Array.isArray(data) ? data : data.results || []);
    } catch (err) {
      setError(err.message || 'Failed to load domains');
    } finally {
      setLoading(false);
    }
  };

  const handleOpenDialog = (domain = null) => {
    if (domain) {
      setEditingDomain(domain);
      setFormData({ name: domain.name, description: domain.description || '' });
    } else {
      setEditingDomain(null);
      setFormData({ name: '', description: '' });
    }
    setOpenDialog(true);
  };

  const handleCloseDialog = () => {
    setOpenDialog(false);
    setEditingDomain(null);
    setFormData({ name: '', description: '' });
  };

  const handleSave = async () => {
    try {
      if (editingDomain) {
        await updateDataDomain(token, editingDomain.id, formData);
      } else {
        await createDataDomain(token, formData);
      }
      await loadDomains();
      handleCloseDialog();
    } catch (err) {
      setError(err.message || 'Failed to save domain');
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Are you sure?')) return;
    try {
      await deleteDataDomain(token, id);
      await loadDomains();
    } catch (err) {
      setError(err.message || 'Failed to delete domain');
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h5">Data Domains</Typography>
        <Button startIcon={<AddIcon />} variant="contained" onClick={() => handleOpenDialog()}>
          New Domain
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
                <TableCell>Description</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {domains.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={3} align="center" sx={{ py: 4 }}>
                    No domains found
                  </TableCell>
                </TableRow>
              ) : (
                domains.map((domain) => (
                  <TableRow key={domain.id} hover>
                    <TableCell sx={{ fontWeight: 500 }}>{domain.name}</TableCell>
                    <TableCell>{domain.description || '-'}</TableCell>
                    <TableCell align="right">
                      <Tooltip title="View">
                        <IconButton
                          size="small"
                          onClick={() => navigate(`/catalog/domains/${domain.id}`)}
                          color="primary"
                        >
                          <VisibilityIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Edit">
                        <IconButton
                          size="small"
                          onClick={() => handleOpenDialog(domain)}
                        >
                          <EditIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Delete">
                        <IconButton
                          size="small"
                          onClick={() => handleDelete(domain.id)}
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
          {editingDomain ? 'Edit Domain' : 'New Domain'}
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
          <TextField
            label="Description"
            fullWidth
            multiline
            rows={3}
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            margin="normal"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>Cancel</Button>
          <Button onClick={handleSave} variant="contained">
            {editingDomain ? 'Update' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
