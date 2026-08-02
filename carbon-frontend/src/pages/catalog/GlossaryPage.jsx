// src/pages/catalog/GlossaryPage.jsx
// Catalog: Manage glossary terms (business definitions, metadata)

import React, { useState, useEffect } from 'react';
import { useAuth } from '../../auth/AuthContext';
import { fetchGlossaryTerms, createGlossaryTerm, updateGlossaryTerm, deleteGlossaryTerm, fetchDataDomains } from '../../api/catalog';
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
import useDocumentTitle from '../../hooks/useDocumentTitle';

import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import AddIcon from '@mui/icons-material/Add';

export default function GlossaryPage() {
  useDocumentTitle("Glossary");
  const { token } = useAuth();
  const [terms, setTerms] = useState([]);
  const [domains, setDomains] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [openDialog, setOpenDialog] = useState(false);
  const [editingTerm, setEditingTerm] = useState(null);
  const [formData, setFormData] = useState({ name: '', definition: '', domain: '' });

  // Load terms and domains on mount
  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [termsData, domainsData] = await Promise.all([
        fetchGlossaryTerms(token),
        fetchDataDomains(token),
      ]);
      setTerms(Array.isArray(termsData) ? termsData : termsData.results || []);
      setDomains(Array.isArray(domainsData) ? domainsData : domainsData.results || []);
    } catch (err) {
      setError(err.message || 'Failed to load glossary terms');
    } finally {
      setLoading(false);
    }
  };

  const handleOpenDialog = (term = null) => {
    if (term) {
      setEditingTerm(term);
      setFormData({ 
        name: term.name, 
        definition: term.definition || '',
        domain: term.domain || '',
      });
    } else {
      setEditingTerm(null);
      setFormData({ name: '', definition: '', domain: '' });
    }
    setOpenDialog(true);
  };

  const handleCloseDialog = () => {
    setOpenDialog(false);
    setEditingTerm(null);
    setFormData({ name: '', definition: '', domain: '' });
  };

  const handleSave = async () => {
    try {
      if (editingTerm) {
        await updateGlossaryTerm(token, editingTerm.id, formData);
      } else {
        await createGlossaryTerm(token, formData);
      }
      await loadData();
      handleCloseDialog();
    } catch (err) {
      setError(err.message || 'Failed to save glossary term');
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Are you sure?')) return;
    try {
      await deleteGlossaryTerm(token, id);
      await loadData();
    } catch (err) {
      setError(err.message || 'Failed to delete glossary term');
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h5">Glossary Terms</Typography>
        <Button startIcon={<AddIcon />} variant="contained" onClick={() => handleOpenDialog()}>
          New Term
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
                <TableCell>Definition</TableCell>
                <TableCell>Domain</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {terms.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={4} align="center" sx={{ py: 4 }}>
                    No glossary terms found
                  </TableCell>
                </TableRow>
              ) : (
                terms.map((term) => (
                  <TableRow key={term.id} hover>
                    <TableCell sx={{ fontWeight: 500 }}>{term.name}</TableCell>
                    <TableCell sx={{ maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {term.definition || '-'}
                    </TableCell>
                    <TableCell>{term.domain_name || '-'}</TableCell>
                    <TableCell align="right">
                      <Tooltip title="Edit">
                        <IconButton
                          size="small"
                          onClick={() => handleOpenDialog(term)}
                        >
                          <EditIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Delete">
                        <IconButton
                          size="small"
                          onClick={() => handleDelete(term.id)}
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
          {editingTerm ? 'Edit Glossary Term' : 'New Glossary Term'}
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
            label="Definition"
            fullWidth
            multiline
            rows={4}
            value={formData.definition}
            onChange={(e) => setFormData({ ...formData, definition: e.target.value })}
            margin="normal"
          />
          <FormControl fullWidth margin="normal">
            <InputLabel>Domain</InputLabel>
            <Select
              value={formData.domain}
              onChange={(e) => setFormData({ ...formData, domain: e.target.value })}
              label="Domain"
            >
              <MenuItem value="">None</MenuItem>
              {domains.map((domain) => (
                <MenuItem key={domain.id} value={domain.id}>
                  {domain.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>Cancel</Button>
          <Button onClick={handleSave} variant="contained">
            {editingTerm ? 'Update' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
