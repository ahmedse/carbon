import React, { useEffect, useState } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Drawer,
  Alert,
  Chip,
  TextField,
  MenuItem,
  CircularProgress,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Stack,
  IconButton,
} from '@mui/material';
import useDocumentTitle from '../../hooks/useDocumentTitle';

import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import { useAuth } from '../../auth/AuthContext';
import { fetchEmissionFactors, fetchFactorCategories, createEmissionFactor, updateEmissionFactor, deleteEmissionFactor } from '../../api/emissions-extended';

const ScopeChip = ({ scope }) => {
  const scopeLabels = { 1: 'Scope 1', 2: 'Scope 2', 3: 'Scope 3' };
  const scopeColors = { 1: '#ff6b6b', 2: '#4dabf7', 3: '#69db7c' };
  return (
    <Chip
      label={scopeLabels[scope] || `Scope ${scope}`}
      size="small"
      sx={{ backgroundColor: 'text.disabled', color: 'background.default' }}
    />
  );
};

export default function EmissionFactorsPage() {
  useDocumentTitle("Emission Factors");
  const { user, token } = useAuth();
  const [factors, setFactors] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [currentFactor, setCurrentFactor] = useState(null);
  const [filters, setFilters] = useState({ category: '', scope: '', search: '' });

  const isAdmin = user?.is_staff || user?.is_superuser;

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [factorsData, categoriesData] = await Promise.all([
        fetchEmissionFactors({}, token),
        fetchFactorCategories(token),
      ]);
      setFactors(factorsData);
      setCategories(categoriesData);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = () => {
    setCurrentFactor(null);
    setDrawerOpen(true);
  };

  const handleEdit = (factor) => {
    setCurrentFactor(factor);
    setDrawerOpen(true);
  };

  const handleSave = async (formData) => {
    try {
      if (currentFactor) {
        await updateEmissionFactor(currentFactor.id, formData, token);
      } else {
        await createEmissionFactor(formData, token);
      }
      setDrawerOpen(false);
      setCurrentFactor(null);
      await loadData();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleDelete = async (factorId) => {
    try {
      await deleteEmissionFactor(factorId, token);
      setDeleteConfirm(null);
      await loadData();
    } catch (err) {
      if (err.feedback && err.feedback.code === 'factor_in_use') {
        setError(err.feedback.detail || err.message);
      } else {
        setError(err.message);
      }
    }
  };

  const filteredFactors = factors.filter(factor => {
    if (filters.category && factor.category !== filters.category) return false;
    if (filters.scope && factor.scope !== parseInt(filters.scope)) return false;
    if (filters.search && !factor.name.toLowerCase().includes(filters.search.toLowerCase())) return false;
    return true;
  });

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '400px' }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 3 }}>
        <Typography variant="h5" sx={{ fontWeight: 'bold' }}>
          Emission Factors
        </Typography>
        {isAdmin && (
          <Button variant="contained" startIcon={<AddIcon />} onClick={handleCreate}>
            Add Factor
          </Button>
        )}
      </Stack>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {/* Filters */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
          <TextField
            label="Search"
            size="small"
            sx={{ flex: 1 }}
            value={filters.search}
            onChange={(e) => setFilters({ ...filters, search: e.target.value })}
          />
          <TextField
            label="Category"
            select
            size="small"
            sx={{ flex: 1 }}
            value={filters.category}
            onChange={(e) => setFilters({ ...filters, category: e.target.value })}
          >
            <MenuItem value="">All Categories</MenuItem>
            {categories.map(cat => (
              <MenuItem key={cat} value={cat}>{cat}</MenuItem>
            ))}
          </TextField>
          <TextField
            label="Scope"
            select
            size="small"
            sx={{ flex: 1 }}
            value={filters.scope}
            onChange={(e) => setFilters({ ...filters, scope: e.target.value })}
          >
            <MenuItem value="">All Scopes</MenuItem>
            <MenuItem value="1">Scope 1</MenuItem>
            <MenuItem value="2">Scope 2</MenuItem>
            <MenuItem value="3">Scope 3</MenuItem>
          </TextField>
        </Stack>
      </Paper>

      {/* Table */}
      <TableContainer component={Paper}>
        <Table>
          <TableHead sx={{ backgroundColor: 'background.dark' }}>
            <TableRow>
              <TableCell sx={{ fontWeight: 'bold' }}>Name</TableCell>
              <TableCell sx={{ fontWeight: 'bold' }}>Code</TableCell>
              <TableCell sx={{ fontWeight: 'bold' }}>Category</TableCell>
              <TableCell sx={{ fontWeight: 'bold' }}>Scope</TableCell>
              <TableCell align="right" sx={{ fontWeight: 'bold' }}>Factor Value</TableCell>
              <TableCell sx={{ fontWeight: 'bold' }}>Active</TableCell>
              {isAdmin && <TableCell align="center" sx={{ fontWeight: 'bold' }}>Actions</TableCell>}
            </TableRow>
          </TableHead>
          <TableBody>
            {filteredFactors.length === 0 ? (
              <TableRow>
                <TableCell colSpan={isAdmin ? 7 : 6} align="center" sx={{ py: 3, color: 'text.disabled' }}>
                  No emission factors found
                </TableCell>
              </TableRow>
            ) : (
              filteredFactors.map(factor => (
                <TableRow key={factor.id}>
                  <TableCell>{factor.name}</TableCell>
                  <TableCell>{factor.code}</TableCell>
                  <TableCell>{factor.category}</TableCell>
                  <TableCell><ScopeChip scope={factor.scope} /></TableCell>
                  <TableCell align="right">{factor.factor_value}</TableCell>
                  <TableCell>{factor.is_active ? '✓' : '✗'}</TableCell>
                  {isAdmin && (
                    <TableCell align="center">
                      <IconButton size="small" onClick={() => handleEdit(factor)}>
                        <EditIcon fontSize="small" />
                      </IconButton>
                      <IconButton size="small" onClick={() => setDeleteConfirm(factor.id)} sx={{ color: 'error.main' }}>
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </TableCell>
                  )}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Create/Edit Drawer */}
      <FactorDrawer
        open={drawerOpen}
        factor={currentFactor}
        categories={categories}
        onSave={handleSave}
        onClose={() => setDrawerOpen(false)}
      />

      {/* Delete Confirmation Dialog */}
      <Dialog open={!!deleteConfirm} onClose={() => setDeleteConfirm(null)}>
        <DialogTitle>Delete Factor?</DialogTitle>
        <DialogContent>
          <Typography>This action cannot be undone.</Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteConfirm(null)}>Cancel</Button>
          <Button onClick={() => handleDelete(deleteConfirm)} variant="contained" color="error">
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

function FactorDrawer({ open, factor, categories, onSave, onClose }) {
  const [form, setForm] = useState({
    name: '',
    code: '',
    category: '',
    scope: 1,
    factor_value: '',
    is_active: true,
  });

  useEffect(() => {
    if (factor) {
      setForm(factor);
    } else {
      setForm({
        name: '',
        code: '',
        category: '',
        scope: 1,
        factor_value: '',
        is_active: true,
      });
    }
  }, [factor, open]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm(prev => ({
      ...prev,
      [name]: name === 'is_active' ? e.target.checked : value,
    }));
  };

  const handleSubmit = () => {
    onSave(form);
  };

  return (
    <Drawer anchor="right" open={open} onClose={onClose}>
      <Box sx={{ width: 400, p: 3 }}>
        <Typography variant="h6" sx={{ mb: 3 }}>
          {factor ? 'Edit Factor' : 'Create Factor'}
        </Typography>
        <Stack spacing={2}>
          <TextField
            label="Name"
            name="name"
            value={form.name}
            onChange={handleChange}
            fullWidth
          />
          <TextField
            label="Code"
            name="code"
            value={form.code}
            onChange={handleChange}
            fullWidth
          />
          <TextField
            label="Category"
            select
            name="category"
            value={form.category}
            onChange={handleChange}
            fullWidth
          >
            {categories.map(cat => (
              <MenuItem key={cat} value={cat}>{cat}</MenuItem>
            ))}
          </TextField>
          <TextField
            label="Scope"
            select
            name="scope"
            value={form.scope}
            onChange={handleChange}
            fullWidth
          >
            <MenuItem value={1}>Scope 1</MenuItem>
            <MenuItem value={2}>Scope 2</MenuItem>
            <MenuItem value={3}>Scope 3</MenuItem>
          </TextField>
          <TextField
            label="Factor Value"
            name="factor_value"
            type="number"
            value={form.factor_value}
            onChange={handleChange}
            fullWidth
          />
          <Stack direction="row" spacing={2}>
            <Button variant="outlined" onClick={onClose} sx={{ flex: 1 }}>
              Cancel
            </Button>
            <Button variant="contained" onClick={handleSubmit} sx={{ flex: 1 }}>
              Save
            </Button>
          </Stack>
        </Stack>
      </Box>
    </Drawer>
  );
}
