// src/pages/catalog/MDMPage.jsx
// Catalog: Master Data Management - Reference sets, values, and org units

import React, { useState, useEffect } from 'react';
import { useAuth } from '../../auth/AuthContext';
import {
  fetchReferenceSets,
  createReferenceSet,
  updateReferenceSet,
  deleteReferenceSet,
  fetchReferenceValues,
  createReferenceValue,
  updateReferenceValue,
  deleteReferenceValue,
  fetchOrgUnits,
  createOrgUnit,
  updateOrgUnit,
  deleteOrgUnit,
} from '../../api/catalog';
import {
  Box,
  Button,
  Card,
  CardContent,
  CardHeader,
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
  Tabs,
  Tab,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import AddIcon from '@mui/icons-material/Add';

function TabPanel(props) {
  const { children, value, index, ...other } = props;
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`mdm-tabpanel-${index}`}
      aria-labelledby={`mdm-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ pt: 2 }}>{children}</Box>}
    </div>
  );
}

export default function MDMPage() {
  const { token } = useAuth();
  const [tabValue, setTabValue] = useState(0);
  
  // Reference sets state
  const [refSets, setRefSets] = useState([]);
  const [refValues, setRefValues] = useState([]);
  const [selectedRefSet, setSelectedRefSet] = useState(null);
  
  // Org units state
  const [orgUnits, setOrgUnits] = useState([]);
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [openDialog, setOpenDialog] = useState(false);
  const [dialogType, setDialogType] = useState(''); // 'refset', 'refvalue', 'orgunit'
  const [editingItem, setEditingItem] = useState(null);
  const [formData, setFormData] = useState({});

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [sets, units] = await Promise.all([
        fetchReferenceSets(token),
        fetchOrgUnits(token),
      ]);
      setRefSets(Array.isArray(sets) ? sets : sets.results || []);
      setOrgUnits(Array.isArray(units) ? units : units.results || []);
      
      // Load values for first ref set if available
      if ((Array.isArray(sets) ? sets : sets.results || [])[0]) {
        const firstSet = (Array.isArray(sets) ? sets : sets.results || [])[0];
        setSelectedRefSet(firstSet.id);
        const vals = await fetchReferenceValues(token, firstSet.id);
        setRefValues(Array.isArray(vals) ? vals : vals.results || []);
      }
    } catch (err) {
      setError(err.message || 'Failed to load MDM data');
    } finally {
      setLoading(false);
    }
  };

  const handleOpenDialog = (type, item = null) => {
    setDialogType(type);
    if (item) {
      setEditingItem(item);
      if (type === 'refset') {
        setFormData({ name: item.name, description: item.description || '' });
      } else if (type === 'refvalue') {
        setFormData({ code: item.code, label: item.label, description: item.description || '' });
      } else if (type === 'orgunit') {
        setFormData({ name: item.name, parent: item.parent || '', description: item.description || '' });
      }
    } else {
      setEditingItem(null);
      setFormData({});
    }
    setOpenDialog(true);
  };

  const handleCloseDialog = () => {
    setOpenDialog(false);
    setEditingItem(null);
    setFormData({});
  };

  const handleSave = async () => {
    try {
      if (dialogType === 'refset') {
        if (editingItem) {
          await updateReferenceSet(token, editingItem.id, formData);
        } else {
          await createReferenceSet(token, formData);
        }
        await loadData();
      } else if (dialogType === 'refvalue') {
        const data = { ...formData, reference_set: selectedRefSet };
        if (editingItem) {
          await updateReferenceValue(token, editingItem.id, data);
        } else {
          await createReferenceValue(token, data);
        }
        if (selectedRefSet) {
          const vals = await fetchReferenceValues(token, selectedRefSet);
          setRefValues(Array.isArray(vals) ? vals : vals.results || []);
        }
      } else if (dialogType === 'orgunit') {
        if (editingItem) {
          await updateOrgUnit(token, editingItem.id, formData);
        } else {
          await createOrgUnit(token, formData);
        }
        const units = await fetchOrgUnits(token);
        setOrgUnits(Array.isArray(units) ? units : units.results || []);
      }
      handleCloseDialog();
    } catch (err) {
      setError(err.message || 'Failed to save');
    }
  };

  const handleDelete = async (type, id) => {
    if (!window.confirm('Are you sure?')) return;
    try {
      if (type === 'refset') {
        await deleteReferenceSet(token, id);
        await loadData();
      } else if (type === 'refvalue') {
        await deleteReferenceValue(token, id);
        if (selectedRefSet) {
          const vals = await fetchReferenceValues(token, selectedRefSet);
          setRefValues(Array.isArray(vals) ? vals : vals.results || []);
        }
      } else if (type === 'orgunit') {
        await deleteOrgUnit(token, id);
        const units = await fetchOrgUnits(token);
        setOrgUnits(Array.isArray(units) ? units : units.results || []);
      }
    } catch (err) {
      setError(err.message || 'Failed to delete');
    }
  };

  if (loading) {
    return <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}><CircularProgress /></Box>;
  }

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h5" sx={{ mb: 2 }}>Master Data Management</Typography>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Tabs value={tabValue} onChange={(e, val) => setTabValue(val)}>
          <Tab label="Reference Sets" />
          <Tab label="Reference Values" />
          <Tab label="Org Units" />
        </Tabs>
      </Box>

      {/* Reference Sets Tab */}
      <TabPanel value={tabValue} index={0}>
        <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 2 }}>
          <Button startIcon={<AddIcon />} variant="contained" onClick={() => handleOpenDialog('refset')}>
            New Set
          </Button>
        </Box>
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow sx={{ bgcolor: 'background.alt' }}>
                <TableCell>Name</TableCell>
                <TableCell>Description</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {refSets.map((set) => (
                <TableRow key={set.id} hover>
                  <TableCell>{set.name}</TableCell>
                  <TableCell>{set.description || '-'}</TableCell>
                  <TableCell align="right">
                    <IconButton size="small" onClick={() => handleOpenDialog('refset', set)}>
                      <EditIcon fontSize="small" />
                    </IconButton>
                    <IconButton size="small" color="error" onClick={() => handleDelete('refset', set.id)}>
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </TabPanel>

      {/* Reference Values Tab */}
      <TabPanel value={tabValue} index={1}>
        <Box sx={{ display: 'flex', gap: 2, mb: 2, alignItems: 'center' }}>
          <FormControl sx={{ minWidth: 250 }}>
            <InputLabel>Select Reference Set</InputLabel>
            <Select
              value={selectedRefSet || ''}
              onChange={async (e) => {
                setSelectedRefSet(e.target.value);
                const vals = await fetchReferenceValues(token, e.target.value);
                setRefValues(Array.isArray(vals) ? vals : vals.results || []);
              }}
              label="Select Reference Set"
            >
              {refSets.map((set) => (
                <MenuItem key={set.id} value={set.id}>{set.name}</MenuItem>
              ))}
            </Select>
          </FormControl>
          <Button startIcon={<AddIcon />} variant="contained" onClick={() => handleOpenDialog('refvalue')}>
            New Value
          </Button>
        </Box>
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow sx={{ bgcolor: 'background.alt' }}>
                <TableCell>Code</TableCell>
                <TableCell>Label</TableCell>
                <TableCell>Description</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {refValues.map((val) => (
                <TableRow key={val.id} hover>
                  <TableCell>{val.code}</TableCell>
                  <TableCell>{val.label}</TableCell>
                  <TableCell>{val.description || '-'}</TableCell>
                  <TableCell align="right">
                    <IconButton size="small" onClick={() => handleOpenDialog('refvalue', val)}>
                      <EditIcon fontSize="small" />
                    </IconButton>
                    <IconButton size="small" color="error" onClick={() => handleDelete('refvalue', val.id)}>
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </TabPanel>

      {/* Org Units Tab */}
      <TabPanel value={tabValue} index={2}>
        <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 2 }}>
          <Button startIcon={<AddIcon />} variant="contained" onClick={() => handleOpenDialog('orgunit')}>
            New Unit
          </Button>
        </Box>
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow sx={{ bgcolor: 'background.alt' }}>
                <TableCell>Name</TableCell>
                <TableCell>Parent</TableCell>
                <TableCell>Description</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {orgUnits.map((unit) => (
                <TableRow key={unit.id} hover>
                  <TableCell>{unit.name}</TableCell>
                  <TableCell>{unit.parent_name || '-'}</TableCell>
                  <TableCell>{unit.description || '-'}</TableCell>
                  <TableCell align="right">
                    <IconButton size="small" onClick={() => handleOpenDialog('orgunit', unit)}>
                      <EditIcon fontSize="small" />
                    </IconButton>
                    <IconButton size="small" color="error" onClick={() => handleDelete('orgunit', unit.id)}>
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </TabPanel>

      {/* Dialog */}
      <Dialog open={openDialog} onClose={handleCloseDialog} maxWidth="sm" fullWidth>
        <DialogTitle>
          {editingItem ? `Edit ${dialogType}` : `New ${dialogType}`}
        </DialogTitle>
        <DialogContent sx={{ pt: 2 }}>
          {dialogType === 'refset' && (
            <>
              <TextField
                label="Name"
                fullWidth
                value={formData.name || ''}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                margin="normal"
                autoFocus
              />
              <TextField
                label="Description"
                fullWidth
                multiline
                rows={2}
                value={formData.description || ''}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                margin="normal"
              />
            </>
          )}
          {dialogType === 'refvalue' && (
            <>
              <TextField
                label="Code"
                fullWidth
                value={formData.code || ''}
                onChange={(e) => setFormData({ ...formData, code: e.target.value })}
                margin="normal"
                autoFocus
              />
              <TextField
                label="Label"
                fullWidth
                value={formData.label || ''}
                onChange={(e) => setFormData({ ...formData, label: e.target.value })}
                margin="normal"
              />
              <TextField
                label="Description"
                fullWidth
                multiline
                rows={2}
                value={formData.description || ''}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                margin="normal"
              />
            </>
          )}
          {dialogType === 'orgunit' && (
            <>
              <TextField
                label="Name"
                fullWidth
                value={formData.name || ''}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                margin="normal"
                autoFocus
              />
              <TextField
                label="Parent ID"
                fullWidth
                value={formData.parent || ''}
                onChange={(e) => setFormData({ ...formData, parent: e.target.value })}
                margin="normal"
              />
              <TextField
                label="Description"
                fullWidth
                multiline
                rows={2}
                value={formData.description || ''}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                margin="normal"
              />
            </>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>Cancel</Button>
          <Button onClick={handleSave} variant="contained">
            Save
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
