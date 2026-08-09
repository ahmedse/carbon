// src/pages/catalog/MDMPage.jsx
// Master Data Management: Reference Sets, Reference Values, and Org Units
// Unified architecture using MUI DataGrid, search/filters, and system theme

import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import {
  fetchReferenceSets,
  deleteReferenceSet,
  createReferenceSet,
  fetchReferenceValues,
  deleteReferenceValue,
  fetchOrgUnits,
  deleteOrgUnit,
  createOrgUnit,
  fetchDataDomains,
} from '../../api/catalog';
import useDocumentTitle from '../../hooks/useDocumentTitle';

import { fetchUsers } from '../../api/users';
import {
  Box,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Tabs,
  Tab,
  TextField,
  InputAdornment,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Chip,
  IconButton,
  Tooltip,
  CircularProgress,
  Alert,
  Typography,
  useTheme,
} from '@mui/material';
import { DataGrid } from '@mui/x-data-grid';
import SearchIcon from '@mui/icons-material/Search';
import ClearIcon from '@mui/icons-material/Clear';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import VisibilityIcon from '@mui/icons-material/Visibility';

function TabPanel({ children, value, index }) {
  return (
    <div role="tabpanel" hidden={value !== index}>
      {value === index && <Box sx={{ pt: 2 }}>{children}</Box>}
    </div>
  );
}

export default function MDMPage() {
  useDocumentTitle("Master Data");
  const { token } = useAuth();
  const { notify } = useNotification();
  const navigate = useNavigate();
  const theme = useTheme();

  const [tabValue, setTabValue] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Reference Sets state
  const [refSets, setRefSets] = useState([]);
  const [searchRefSets, setSearchRefSets] = useState('');
  const [filterDomain, setFilterDomain] = useState('');
  const [filterSteward, setFilterSteward] = useState('');

  // Reference Values state
  const [selectedRefSet, setSelectedRefSet] = useState(null);
  const [refValues, setRefValues] = useState([]);
  const [searchRefValues, setSearchRefValues] = useState('');

  // Org Units state
  const [orgUnits, setOrgUnits] = useState([]);
  const [searchOrgUnits, setSearchOrgUnits] = useState('');
  const [filterOrgType, setFilterOrgType] = useState('');

  // Select options
  const [domains, setDomains] = useState([]);
  const [users, setUsers] = useState([]);

  // Create Reference Set dialog
  const [refSetDialogOpen, setRefSetDialogOpen] = useState(false);
  const [refSetForm, setRefSetForm] = useState({ name: '', description: '', domain: '' });
  const [refSetSaving, setRefSetSaving] = useState(false);
  const [refSetError, setRefSetError] = useState(null);

  // Create Org Unit dialog
  const [orgUnitDialogOpen, setOrgUnitDialogOpen] = useState(false);
  const [orgUnitForm, setOrgUnitForm] = useState({ name: '', code: '', org_type: '', parent: '', description: '' });
  const [orgUnitSaving, setOrgUnitSaving] = useState(false);
  const [orgUnitError, setOrgUnitError] = useState(null);

  useEffect(() => {
    loadData();
  }, [token]);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [setsData, domainsData, usersData, unitsData] = await Promise.all([
        fetchReferenceSets(token).catch(() => []),
        fetchDataDomains(token).catch(() => []),
        fetchUsers(token).catch(() => []),
        fetchOrgUnits(token).catch(() => []),
      ]);

      setRefSets(Array.isArray(setsData) ? setsData : setsData.results || []);
      setDomains(Array.isArray(domainsData) ? domainsData : domainsData.results || []);
      setUsers(Array.isArray(usersData) ? usersData : usersData.results || []);
      setOrgUnits(Array.isArray(unitsData) ? unitsData : unitsData.results || []);

      // Auto-select first reference set
      const firstSet = (Array.isArray(setsData) ? setsData : setsData.results || [])[0];
      if (firstSet) {
        setSelectedRefSet(firstSet.id);
        loadRefValues(firstSet.id);
      }
    } catch (_err) {
      const msg = _err.message || 'Failed to load MDM data';
      setError(msg);
      notify({ message: msg, type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const loadRefValues = async (setId) => {
    if (!setId) return;
    try {
      const valsData = await fetchReferenceValues(token, setId);
      setRefValues(Array.isArray(valsData) ? valsData : valsData.results || []);
    } catch (_err) {
      notify({ message: 'Failed to load reference values', type: 'error' });
    }
  };

  const handleDeleteRefSet = async (id) => {
    if (!window.confirm('Delete this reference set? This will also delete all its values.')) return;
    try {
      await deleteReferenceSet(token, id);
      notify({ message: 'Reference set deleted', type: 'success' });
      loadData();
    } catch (err) {
      notify({ message: err.message || 'Failed to delete reference set', type: 'error' });
    }
  };

  const handleDeleteRefValue = async (id) => {
    if (!window.confirm('Delete this reference value?')) return;
    try {
      await deleteReferenceValue(token, id);
      notify({ message: 'Reference value deleted', type: 'success' });
      if (selectedRefSet) loadRefValues(selectedRefSet);
    } catch (err) {
      notify({ message: err.message || 'Failed to delete reference value', type: 'error' });
    }
  };

  const handleDeleteOrgUnit = async (id) => {
    if (!window.confirm('Delete this organizational unit?')) return;
    try {
      await deleteOrgUnit(token, id);
      notify({ message: 'Org unit deleted', type: 'success' });
      const unitsData = await fetchOrgUnits(token);
      setOrgUnits(Array.isArray(unitsData) ? unitsData : unitsData.results || []);
    } catch (err) {
      notify({ message: err.message || 'Failed to delete org unit', type: 'error' });
    }
  };

  const handleClearRefSetsFilters = () => {
    setSearchRefSets('');
    setFilterDomain('');
    setFilterSteward('');
  };

  const handleClearRefValuesFilters = () => {
    setSearchRefValues('');
  };

  const handleClearOrgUnitsFilters = () => {
    setSearchOrgUnits('');
    setFilterOrgType('');
  };

  // --- Create Reference Set dialog handlers ---
  const handleOpenRefSetDialog = () => {
    setRefSetError(null);
    setRefSetForm({ name: '', description: '', domain: '' });
    setRefSetDialogOpen(true);
  };

  const handleCloseRefSetDialog = () => {
    if (refSetSaving) return;
    setRefSetDialogOpen(false);
  };

  const handleSaveRefSet = async () => {
    if (!refSetForm.name.trim()) {
      setRefSetError('Name is required.');
      return;
    }
    setRefSetSaving(true);
    setRefSetError(null);
    try {
      await createReferenceSet(token, {
        name: refSetForm.name.trim(),
        description: refSetForm.description.trim(),
        domain: refSetForm.domain || null,
      });
      notify({ message: 'Reference set created', type: 'success' });
      setRefSetDialogOpen(false);
      await loadData();
    } catch (err) {
      setRefSetError(err.message || 'Failed to create reference set.');
    } finally {
      setRefSetSaving(false);
    }
  };

  // --- Create Org Unit dialog handlers ---
  const handleOpenOrgUnitDialog = () => {
    setOrgUnitError(null);
    setOrgUnitForm({ name: '', code: '', org_type: '', parent: '', description: '' });
    setOrgUnitDialogOpen(true);
  };

  const handleCloseOrgUnitDialog = () => {
    if (orgUnitSaving) return;
    setOrgUnitDialogOpen(false);
  };

  const handleSaveOrgUnit = async () => {
    if (!orgUnitForm.name.trim()) {
      setOrgUnitError('Name is required.');
      return;
    }
    setOrgUnitSaving(true);
    setOrgUnitError(null);
    try {
      await createOrgUnit(token, {
        name: orgUnitForm.name.trim(),
        code: orgUnitForm.code.trim() || null,
        org_type: orgUnitForm.org_type || null,
        parent: orgUnitForm.parent ? parseInt(orgUnitForm.parent) : null,
        description: orgUnitForm.description.trim() || null,
      });
      notify({ message: 'Org unit created', type: 'success' });
      setOrgUnitDialogOpen(false);
      const unitsData = await fetchOrgUnits(token);
      setOrgUnits(Array.isArray(unitsData) ? unitsData : unitsData.results || []);
    } catch (err) {
      setOrgUnitError(err.message || 'Failed to create org unit.');
    } finally {
      setOrgUnitSaving(false);
    }
  };

  // Filtered Reference Sets
  const filteredRefSets = useMemo(() => {
    let filtered = refSets;

    if (searchRefSets.trim()) {
      const query = searchRefSets.toLowerCase();
      filtered = filtered.filter(
        (s) =>
          (s.name && s.name.toLowerCase().includes(query)) ||
          (s.description && s.description.toLowerCase().includes(query))
      );
    }

    if (filterDomain) {
      filtered = filtered.filter((s) => s.domain === filterDomain);
    }

    if (filterSteward) {
      filtered = filtered.filter((s) => s.steward === filterSteward);
    }

    return filtered;
  }, [refSets, searchRefSets, filterDomain, filterSteward]);

  // Filtered Reference Values
  const filteredRefValues = useMemo(() => {
    if (!searchRefValues.trim()) return refValues;
    const query = searchRefValues.toLowerCase();
    return refValues.filter(
      (v) =>
        (v.code && v.code.toLowerCase().includes(query)) ||
        (v.label && v.label.toLowerCase().includes(query)) ||
        (v.description && v.description.toLowerCase().includes(query))
    );
  }, [refValues, searchRefValues]);

  // Filtered Org Units
  const filteredOrgUnits = useMemo(() => {
    let filtered = orgUnits;

    if (searchOrgUnits.trim()) {
      const query = searchOrgUnits.toLowerCase();
      filtered = filtered.filter(
        (u) =>
          (u.name && u.name.toLowerCase().includes(query)) ||
          (u.code && u.code.toLowerCase().includes(query)) ||
          (u.description && u.description.toLowerCase().includes(query))
      );
    }

    if (filterOrgType) {
      filtered = filtered.filter((u) => u.org_type === filterOrgType);
    }

    return filtered;
  }, [orgUnits, searchOrgUnits, filterOrgType]);

  // Reference Sets Columns
  const refSetsColumns = [
    {
      field: 'name',
      headerName: 'Name',
      flex: 1,
      minWidth: 200,
      renderCell: (params) => (
        <Typography variant="body2" sx={{ fontWeight: 500 }}>
          {params.value}
        </Typography>
      ),
    },
    {
      field: 'description',
      headerName: 'Description',
      flex: 2,
      minWidth: 250,
      renderCell: (params) => (
        <Typography variant="body2" color="text.secondary">
          {params.value || '—'}
        </Typography>
      ),
    },
    {
      field: 'domain_name',
      headerName: 'Domain',
      width: 160,
      renderCell: (params) => params.value || '—',
    },
    {
      field: 'steward_name',
      headerName: 'Steward',
      width: 140,
      renderCell: (params) => params.value || '—',
    },
    {
      field: 'value_count',
      headerName: 'Values',
      width: 100,
      renderCell: (params) => <Chip label={params.value || 0} size="small" />,
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 160,
      sortable: false,
      renderCell: (params) => (
        <Box sx={{ display: 'flex', gap: 0.5 }}>
          <Tooltip title="View Details">
            <IconButton
              size="small"
              onClick={() => navigate(`/catalog/mdm/reference-sets/${params.row.id}`)}
            >
              <VisibilityIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Delete">
            <IconButton
              size="small"
              color="error"
              onClick={() => handleDeleteRefSet(params.row.id)}
            >
              <DeleteIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      ),
    },
  ];

  // Reference Values Columns
  const refValuesColumns = [
    { field: 'code', headerName: 'Code', flex: 1, minWidth: 140 },
    { field: 'label', headerName: 'Label', flex: 2, minWidth: 200 },
    {
      field: 'description',
      headerName: 'Description',
      flex: 2,
      minWidth: 220,
      renderCell: (params) => params.value || '—',
    },
    {
      field: 'is_active',
      headerName: 'Active',
      width: 100,
      renderCell: (params) => (
        <Chip
          label={params.value ? 'Active' : 'Inactive'}
          size="small"
          color={params.value ? 'success' : 'default'}
          variant="outlined"
        />
      ),
    },
    {
      field: 'valid_from',
      headerName: 'Valid From',
      width: 120,
      renderCell: (params) =>
        params.value ? new Date(params.value).toLocaleDateString() : '—',
    },
    {
      field: 'valid_to',
      headerName: 'Valid To',
      width: 120,
      renderCell: (params) =>
        params.value ? new Date(params.value).toLocaleDateString() : '—',
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 120,
      sortable: false,
      renderCell: (params) => (
        <Box sx={{ display: 'flex', gap: 0.5 }}>
          <Tooltip title="Delete">
            <IconButton
              size="small"
              color="error"
              onClick={() => handleDeleteRefValue(params.row.id)}
            >
              <DeleteIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      ),
    },
  ];

  // Org Units Columns
  const orgUnitsColumns = [
    {
      field: 'name',
      headerName: 'Name',
      flex: 1,
      minWidth: 200,
      renderCell: (params) => (
        <Typography variant="body2" sx={{ fontWeight: 500 }}>
          {params.value}
        </Typography>
      ),
    },
    {
      field: 'org_type',
      headerName: 'Type',
      width: 140,
      renderCell: (params) => (
        <Chip label={params.value || 'other'} size="small" variant="outlined" />
      ),
    },
    {
      field: 'code',
      headerName: 'Code',
      width: 120,
      renderCell: (params) => params.value || '—',
    },
    {
      field: 'parent_name',
      headerName: 'Parent',
      width: 160,
      renderCell: (params) => params.value || '—',
    },
    {
      field: 'children_count',
      headerName: 'Children',
      width: 100,
      renderCell: (params) => <Chip label={params.value || 0} size="small" />,
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 160,
      sortable: false,
      renderCell: (params) => (
        <Box sx={{ display: 'flex', gap: 0.5 }}>
          <Tooltip title="View Details">
            <IconButton
              size="small"
              onClick={() => navigate(`/catalog/mdm/org-units/${params.row.id}`)}
            >
              <AccountTreeIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Delete">
            <IconButton
              size="small"
              color="error"
              onClick={() => handleDeleteOrgUnit(params.row.id)}
            >
              <DeleteIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      ),
    },
  ];

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" gutterBottom>
          Master Data Management
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Manage reference sets, reference values, and organizational units for controlled vocabularies and governance
        </Typography>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {/* Tabs */}
      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
        <Tabs value={tabValue} onChange={(e, val) => setTabValue(val)}>
          <Tab label={`Reference Sets (${refSets.length})`} />
          <Tab label={`Reference Values (${refValues.length})`} />
          <Tab label={`Org Units (${orgUnits.length})`} />
        </Tabs>
      </Box>

      {/* Tab 1: Reference Sets */}
      <TabPanel value={tabValue} index={0}>
        {/* Filters Bar */}
        <Box
          sx={{
            display: 'flex',
            gap: 2,
            mb: 2,
            flexWrap: 'wrap',
            alignItems: 'center',
            p: 2,
            bgcolor: 'background.alt',
            borderRadius: 1,
          }}
        >
          <TextField
            size="small"
            placeholder="Search reference sets..."
            value={searchRefSets}
            onChange={(e) => setSearchRefSets(e.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon fontSize="small" />
                </InputAdornment>
              ),
            }}
            sx={{ flex: '1 1 250px', minWidth: 200 }}
          />

          <FormControl size="small" sx={{ minWidth: 150 }}>
            <InputLabel>Domain</InputLabel>
            <Select
              value={filterDomain}
              onChange={(e) => setFilterDomain(e.target.value)}
              label="Domain"
            >
              <MenuItem value="">All Domains</MenuItem>
              {domains.map((d) => (
                <MenuItem key={d.id} value={d.id}>
                  {d.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <FormControl size="small" sx={{ minWidth: 150 }}>
            <InputLabel>Steward</InputLabel>
            <Select
              value={filterSteward}
              onChange={(e) => setFilterSteward(e.target.value)}
              label="Steward"
            >
              <MenuItem value="">All Stewards</MenuItem>
              {users.map((u) => (
                <MenuItem key={u.id} value={u.id}>
                  {u.username}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <Button
            size="small"
            startIcon={<ClearIcon />}
            onClick={handleClearRefSetsFilters}
            disabled={!searchRefSets && !filterDomain && !filterSteward}
          >
            Clear Filters
          </Button>

          <Box sx={{ flex: 1 }} />

          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={handleOpenRefSetDialog}
          >
            New Reference Set
          </Button>
        </Box>

        {/* DataGrid */}
        <Box sx={{ height: 500, width: '100%' }}>
          <DataGrid
            rows={filteredRefSets}
            columns={refSetsColumns}
            pageSizeOptions={[10, 25, 50, 100]}
            initialState={{
              pagination: { paginationModel: { pageSize: 25 } },
            }}
            disableRowSelectionOnClick
            sx={{
              '& .MuiDataGrid-columnHeader': {
                backgroundColor: theme.palette.background.alt,
                fontWeight: 600,
              },
            }}
          />
        </Box>
      </TabPanel>

      {/* Tab 2: Reference Values */}
      <TabPanel value={tabValue} index={1}>
        {/* Reference Set Selector + Filters */}
        <Box
          sx={{
            display: 'flex',
            gap: 2,
            mb: 2,
            flexWrap: 'wrap',
            alignItems: 'center',
            p: 2,
            bgcolor: 'background.alt',
            borderRadius: 1,
          }}
        >
          <FormControl size="small" sx={{ minWidth: 240, flex: '1 1 300px' }}>
            <InputLabel>Select Reference Set</InputLabel>
            <Select
              value={selectedRefSet || ''}
              onChange={(e) => {
                setSelectedRefSet(e.target.value);
                loadRefValues(e.target.value);
              }}
              label="Select Reference Set"
            >
              {refSets.map((set) => (
                <MenuItem key={set.id} value={set.id}>
                  {set.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <TextField
            size="small"
            placeholder="Search values..."
            value={searchRefValues}
            onChange={(e) => setSearchRefValues(e.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon fontSize="small" />
                </InputAdornment>
              ),
            }}
            sx={{ flex: '1 1 200px' }}
          />

          <Button
            size="small"
            startIcon={<ClearIcon />}
            onClick={handleClearRefValuesFilters}
            disabled={!searchRefValues}
          >
            Clear
          </Button>

          <Box sx={{ flex: 1 }} />

          <Button
            variant="contained"
            startIcon={<AddIcon />}
            disabled={!selectedRefSet}
            onClick={() => notify({ message: 'Use detail page to add values', type: 'info' })}
          >
            New Value
          </Button>
        </Box>

        {/* DataGrid */}
        <Box sx={{ height: 500, width: '100%' }}>
          <DataGrid
            rows={filteredRefValues}
            columns={refValuesColumns}
            pageSizeOptions={[10, 25, 50, 100]}
            initialState={{
              pagination: { paginationModel: { pageSize: 25 } },
            }}
            disableRowSelectionOnClick
            sx={{
              '& .MuiDataGrid-columnHeader': {
                backgroundColor: theme.palette.background.alt,
                fontWeight: 600,
              },
            }}
          />
        </Box>
      </TabPanel>

      {/* Tab 3: Org Units */}
      <TabPanel value={tabValue} index={2}>
        {/* Filters Bar */}
        <Box
          sx={{
            display: 'flex',
            gap: 2,
            mb: 2,
            flexWrap: 'wrap',
            alignItems: 'center',
            p: 2,
            bgcolor: 'background.alt',
            borderRadius: 1,
          }}
        >
          <TextField
            size="small"
            placeholder="Search org units..."
            value={searchOrgUnits}
            onChange={(e) => setSearchOrgUnits(e.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon fontSize="small" />
                </InputAdornment>
              ),
            }}
            sx={{ flex: '1 1 250px', minWidth: 200 }}
          />

          <FormControl size="small" sx={{ minWidth: 150 }}>
            <InputLabel>Type</InputLabel>
            <Select
              value={filterOrgType}
              onChange={(e) => setFilterOrgType(e.target.value)}
              label="Type"
            >
              <MenuItem value="">All Types</MenuItem>
              <MenuItem value="university">University</MenuItem>
              <MenuItem value="campus">Campus</MenuItem>
              <MenuItem value="college">College</MenuItem>
              <MenuItem value="department">Department</MenuItem>
              <MenuItem value="division">Division</MenuItem>
              <MenuItem value="team">Team</MenuItem>
              <MenuItem value="facility">Facility</MenuItem>
              <MenuItem value="other">Other</MenuItem>
            </Select>
          </FormControl>

          <Button
            size="small"
            startIcon={<ClearIcon />}
            onClick={handleClearOrgUnitsFilters}
            disabled={!searchOrgUnits && !filterOrgType}
          >
            Clear Filters
          </Button>

          <Box sx={{ flex: 1 }} />

          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={handleOpenOrgUnitDialog}
          >
            New Org Unit
          </Button>
        </Box>

        {/* DataGrid */}
        <Box sx={{ height: 500, width: '100%' }}>
          <DataGrid
            rows={filteredOrgUnits}
            columns={orgUnitsColumns}
            pageSizeOptions={[10, 25, 50, 100]}
            initialState={{
              pagination: { paginationModel: { pageSize: 25 } },
            }}
            disableRowSelectionOnClick
            sx={{
              '& .MuiDataGrid-columnHeader': {
                backgroundColor: theme.palette.background.alt,
                fontWeight: 600,
              },
            }}
          />
        </Box>
      </TabPanel>

      {/* Create Reference Set Dialog */}
      <Dialog open={refSetDialogOpen} onClose={handleCloseRefSetDialog} maxWidth="sm" fullWidth>
        <DialogTitle>New Reference Set</DialogTitle>
        <DialogContent>
          {refSetError && <Alert severity="error" sx={{ mb: 2 }}>{refSetError}</Alert>}
          <TextField
            fullWidth
            label="Name"
            margin="normal"
            required
            value={refSetForm.name}
            onChange={(e) => setRefSetForm({ ...refSetForm, name: e.target.value })}
            autoFocus
          />
          <TextField
            fullWidth
            label="Description"
            margin="normal"
            multiline
            rows={2}
            value={refSetForm.description}
            onChange={(e) => setRefSetForm({ ...refSetForm, description: e.target.value })}
          />
          <FormControl fullWidth margin="normal">
            <InputLabel>Domain</InputLabel>
            <Select
              value={refSetForm.domain}
              label="Domain"
              onChange={(e) => setRefSetForm({ ...refSetForm, domain: e.target.value })}
            >
              <MenuItem value="">— None —</MenuItem>
              {domains.map((d) => (
                <MenuItem key={d.id} value={d.id}>{d.name}</MenuItem>
              ))}
            </Select>
          </FormControl>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseRefSetDialog} disabled={refSetSaving}>Cancel</Button>
          <Button onClick={handleSaveRefSet} variant="contained" disabled={refSetSaving} startIcon={refSetSaving ? <CircularProgress size={16} /> : null}>
            {refSetSaving ? 'Creating…' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Create Org Unit Dialog */}
      <Dialog open={orgUnitDialogOpen} onClose={handleCloseOrgUnitDialog} maxWidth="sm" fullWidth>
        <DialogTitle>New Org Unit</DialogTitle>
        <DialogContent>
          {orgUnitError && <Alert severity="error" sx={{ mb: 2 }}>{orgUnitError}</Alert>}
          <TextField
            fullWidth
            label="Name"
            margin="normal"
            required
            value={orgUnitForm.name}
            onChange={(e) => setOrgUnitForm({ ...orgUnitForm, name: e.target.value })}
            autoFocus
          />
          <TextField
            fullWidth
            label="Code"
            margin="normal"
            value={orgUnitForm.code}
            onChange={(e) => setOrgUnitForm({ ...orgUnitForm, code: e.target.value })}
          />
          <FormControl fullWidth margin="normal">
            <InputLabel>Type</InputLabel>
            <Select
              value={orgUnitForm.org_type}
              label="Type"
              onChange={(e) => setOrgUnitForm({ ...orgUnitForm, org_type: e.target.value })}
            >
              <MenuItem value="">— None —</MenuItem>
              <MenuItem value="university">University</MenuItem>
              <MenuItem value="campus">Campus</MenuItem>
              <MenuItem value="college">College</MenuItem>
              <MenuItem value="department">Department</MenuItem>
              <MenuItem value="division">Division</MenuItem>
              <MenuItem value="team">Team</MenuItem>
              <MenuItem value="facility">Facility</MenuItem>
              <MenuItem value="other">Other</MenuItem>
            </Select>
          </FormControl>
          <FormControl fullWidth margin="normal">
            <InputLabel>Parent</InputLabel>
            <Select
              value={orgUnitForm.parent}
              label="Parent"
              onChange={(e) => setOrgUnitForm({ ...orgUnitForm, parent: e.target.value })}
            >
              <MenuItem value="">— None —</MenuItem>
              {orgUnits.map((ou) => (
                <MenuItem key={ou.id} value={ou.id}>{ou.name}</MenuItem>
              ))}
            </Select>
          </FormControl>
          <TextField
            fullWidth
            label="Description"
            margin="normal"
            multiline
            rows={2}
            value={orgUnitForm.description}
            onChange={(e) => setOrgUnitForm({ ...orgUnitForm, description: e.target.value })}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseOrgUnitDialog} disabled={orgUnitSaving}>Cancel</Button>
          <Button onClick={handleSaveOrgUnit} variant="contained" disabled={orgUnitSaving} startIcon={orgUnitSaving ? <CircularProgress size={16} /> : null}>
            {orgUnitSaving ? 'Creating…' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
