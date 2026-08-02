import React, { useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControlLabel,
  IconButton,
  MenuItem,
  Paper,
  Stack,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import useDocumentTitle from '../../hooks/useDocumentTitle';

import {
  Add as AddIcon,
  Delete as DeleteIcon,
  Edit as EditIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { useAuth } from '../../auth/AuthContext';
import { fetchReportingPeriods, createReportingPeriod, updateReportingPeriod, deleteReportingPeriod } from '../../api/emissions-extended';

export default function ReportingPeriodsPage() {
  useDocumentTitle("Reporting Periods");
  const { token } = useAuth();
  const [error, setError] = useState(null);
  const [periods, setPeriods] = useState([]);
  const [loading, setLoading] = useState(true);
  const [openDialog, setOpenDialog] = useState(false);
  const [editingPeriod, setEditingPeriod] = useState(null);
  const [form, setForm] = useState({
    name: '',
    start_date: '',
    end_date: '',
    period_type: 'annual',
    status: 'draft',
    is_baseline: false,
    description: '',
  });

  const loadPeriods = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchReportingPeriods(token);
      setPeriods(data || []);
    } catch (err) {
      setError(err.message || 'Failed to load reporting periods');
      console.error('Error loading periods:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPeriods();
  }, []);

  const handleOpenDialog = (period = null) => {
    if (period) {
      setEditingPeriod(period);
      setForm({
        name: period.name,
        start_date: period.start_date,
        end_date: period.end_date,
        period_type: period.period_type || 'annual',
        status: period.status || 'draft',
        is_baseline: period.is_baseline || false,
        description: period.description || '',
      });
    } else {
      setEditingPeriod(null);
      setForm({
        name: '',
        start_date: '',
        end_date: '',
        period_type: 'annual',
        status: 'draft',
        is_baseline: false,
        description: '',
      });
    }
    setOpenDialog(true);
  };

  const handleCloseDialog = () => {
    setOpenDialog(false);
    setEditingPeriod(null);
  };

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setForm(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value,
    }));
  };

  const handleSave = async () => {
    if (!form.name || !form.start_date || !form.end_date || !form.period_type || !form.status) {
      setError('Please fill in all required fields');
      return;
    }

    try {
      setError(null);
      if (editingPeriod) {
        await updateReportingPeriod(editingPeriod.id, form, token);
      } else {
        await createReportingPeriod(form, token);
      }
      handleCloseDialog();
      await loadPeriods();
    } catch (err) {
      setError(err.message || 'Failed to save reporting period');
      console.error('Error saving period:', err);
    }
  };

  const handleDelete = async (id) => {
    if (window.confirm('Are you sure you want to delete this reporting period?')) {
      try {
        setError(null);
        await deleteReportingPeriod(id, token);
        await loadPeriods();
      } catch (err) {
        setError(err.message || 'Failed to delete reporting period');
        console.error('Error deleting period:', err);
      }
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      {error && (
        <Alert severity="error" onClose={() => setError(null)} sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4" component="h1">
          Reporting Periods
        </Typography>
        <Stack direction="row" gap={1}>
          <Tooltip title="Refresh">
            <IconButton
              onClick={loadPeriods}
              size="small"
              sx={{ color: 'primary.main' }}
            >
              <RefreshIcon />
            </IconButton>
          </Tooltip>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => handleOpenDialog()}
          >
            New Period
          </Button>
        </Stack>
      </Stack>

      <Paper sx={{ overflow: 'auto' }}>
        <TableContainer>
          <Table>
            <TableHead sx={{ backgroundColor: 'action.hover' }}>
              <TableRow>
                <TableCell sx={{ fontWeight: 600 }}>Name</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>Type</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>Start Date</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>End Date</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>Status</TableCell>
                <TableCell sx={{ fontWeight: 600 }} align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={5} align="center" sx={{ py: 3 }}>
                    <Typography color="text.secondary">Loading...</Typography>
                  </TableCell>
                </TableRow>
              ) : periods.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} align="center" sx={{ py: 3 }}>
                    <Typography color="text.secondary">No reporting periods found</Typography>
                  </TableCell>
                </TableRow>
              ) : (
                periods.map((period) => (
                  <TableRow key={period.id} hover>
                    <TableCell>{period.name}</TableCell>
                    <TableCell>
                      <Chip label={period.period_type || 'annual'} size="small" variant="outlined" />
                    </TableCell>
                    <TableCell>{new Date(period.start_date).toLocaleDateString()}</TableCell>
                    <TableCell>{new Date(period.end_date).toLocaleDateString()}</TableCell>
                    <TableCell>
                      <Chip
                        label={period.status || 'draft'}
                        size="small"
                        color={
                          period.status === 'verified' ? 'success' :
                          period.status === 'open' ? 'primary' :
                          period.status === 'closed' ? 'default' :
                          'warning'
                        }
                      />
                    </TableCell>
                    <TableCell align="right">
                      <Tooltip title="Edit">
                        <IconButton
                          size="small"
                          onClick={() => handleOpenDialog(period)}
                          sx={{ color: 'primary.main' }}
                        >
                          <EditIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Delete">
                        <IconButton
                          size="small"
                          onClick={() => handleDelete(period.id)}
                          sx={{ color: 'error.main' }}
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
      </Paper>

      <Dialog open={openDialog} onClose={handleCloseDialog} maxWidth="sm" fullWidth>
        <DialogTitle>
          {editingPeriod ? 'Edit Reporting Period' : 'Create New Reporting Period'}
        </DialogTitle>
        <Divider />
        <DialogContent sx={{ pt: 2 }}>
          <Stack spacing={2}>
            <TextField
              label="Period Name"
              name="name"
              value={form.name}
              onChange={handleChange}
              placeholder="e.g., FY 2024"
              fullWidth
            />
            <TextField
              label="Start Date"
              name="start_date"
              type="date"
              value={form.start_date}
              onChange={handleChange}
              InputLabelProps={{ shrink: true }}
              fullWidth
            />
            <TextField
              label="End Date"
              name="end_date"
              type="date"
              value={form.end_date}
              onChange={handleChange}
              InputLabelProps={{ shrink: true }}
              fullWidth
            />
            <TextField
              select
              label="Period Type"
              name="period_type"
              value={form.period_type}
              onChange={handleChange}
              fullWidth
              margin="normal"
              required
            >
              <MenuItem value="annual">Annual</MenuItem>
              <MenuItem value="quarterly">Quarterly</MenuItem>
              <MenuItem value="monthly">Monthly</MenuItem>
              <MenuItem value="custom">Custom</MenuItem>
            </TextField>
            <TextField
              select
              label="Status"
              name="status"
              value={form.status}
              onChange={handleChange}
              fullWidth
              margin="normal"
              required
            >
              <MenuItem value="draft">Draft</MenuItem>
              <MenuItem value="open">Open for Data Entry</MenuItem>
              <MenuItem value="locked">Locked for Review</MenuItem>
              <MenuItem value="submitted">Submitted</MenuItem>
              <MenuItem value="verified">Verified</MenuItem>
              <MenuItem value="closed">Closed</MenuItem>
            </TextField>
            <TextField
              label="Description"
              name="description"
              value={form.description}
              onChange={handleChange}
              placeholder="Optional description"
              multiline
              rows={3}
              fullWidth
            />
            <FormControlLabel
              control={
                <Switch
                  checked={form.is_baseline}
                  onChange={handleChange}
                  name="is_baseline"
                />
              }
              label="Baseline Period (used for year-over-year comparisons)"
            />
          </Stack>
        </DialogContent>
        <Divider />
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={handleCloseDialog}>Cancel</Button>
          <Button variant="contained" onClick={handleSave}>
            {editingPeriod ? 'Update' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
