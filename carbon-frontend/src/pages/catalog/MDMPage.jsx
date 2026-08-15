// src/pages/catalog/MDMPage.jsx
// Master Data Management: Reference Sets and Org Units
// Standard grids with quick-filter toolbar, full CRUD dialogs, all four data states

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import dayjs from 'dayjs';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import {
  fetchReferenceSets,
  createReferenceSet,
  updateReferenceSet,
  deleteReferenceSet,
  fetchOrgUnits,
  createOrgUnit,
  updateOrgUnit,
  deleteOrgUnit,
  fetchDataDomains,
} from '../../api/catalog';
import { fetchUsers } from '../../api/users';
import useDocumentTitle from '../../hooks/useDocumentTitle';

import {
  Box,
  Button,
  Paper,
  Tabs,
  Tab,
  TextField,
  InputAdornment,
  Select,
  MenuItem,
  Autocomplete,
  FormControl,
  InputLabel,
  Chip,
  IconButton,
  Tooltip,
  Typography,
  Stack,
  Grid,
  Alert,
  CircularProgress,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import ClearIcon from '@mui/icons-material/Clear';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import VisibilityIcon from '@mui/icons-material/Visibility';
import CategoryIcon from '@mui/icons-material/Category';

import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import EmptyState from '../../components/Page/EmptyState';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../components/Page/ErrorAlert';
import StandardDataGrid from '../../components/StandardDataGrid';
import SystemDialog from '../../components/SystemDialog';
import ConfirmDialog from '../../components/ConfirmDialog';
import {
  LIFECYCLE_COLORS,
  LIFECYCLE_LABELS,
  LIFECYCLE_STATES,
} from '../../constants/referenceSetLifecycle';

const ORG_TYPES = [
  { value: 'university', label: 'University' },
  { value: 'campus', label: 'Campus' },
  { value: 'college', label: 'College' },
  { value: 'department', label: 'Department' },
  { value: 'division', label: 'Division' },
  { value: 'team', label: 'Team' },
  { value: 'facility', label: 'Facility' },
  { value: 'other', label: 'Other' },
];

// Map DRF field-error payload ({field: [msg]}) to {field: msg} for per-field display.
function mapFieldErrors(err) {
  const data = err?.data;
  if (!data || typeof data !== 'object' || Array.isArray(data)) return null;
  const fieldErrors = {};
  Object.entries(data).forEach(([key, value]) => {
    if (key === 'non_field_errors') return;
    if (Array.isArray(value)) fieldErrors[key] = value[0];
    else if (typeof value === 'string') fieldErrors[key] = value;
  });
  return Object.keys(fieldErrors).length ? fieldErrors : null;
}

function TabPanel({ children, value, index }) {
  return (
    <div role="tabpanel" hidden={value !== index} style={{ display: value === index ? 'flex' : 'none', flexDirection: 'column', flex: 1, minHeight: 0 }}>
      {value === index && <Box sx={{ pt: 2, flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>{children}</Box>}
    </div>
  );
}

export default function MDMPage() {
  useDocumentTitle("Master Data");
  const { token } = useAuth();
  const { notify } = useNotification();
  const navigate = useNavigate();

  const [tabValue, setTabValue] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Reference Sets state
  const [refSets, setRefSets] = useState([]);
  const [searchRefSets, setSearchRefSets] = useState('');
  const [filterDomain, setFilterDomain] = useState('');
  const [filterSteward, setFilterSteward] = useState('');
  const [filterLifecycle, setFilterLifecycle] = useState('');

  // Org Units state
  const [orgUnits, setOrgUnits] = useState([]);
  const [searchOrgUnits, setSearchOrgUnits] = useState('');
  const [filterOrgType, setFilterOrgType] = useState('');

  // Select options
  const [domains, setDomains] = useState([]);
  const [users, setUsers] = useState([]);

  // Reference Set create/edit dialog
  const [refSetDialogOpen, setRefSetDialogOpen] = useState(false);
  const [refSetEditing, setRefSetEditing] = useState(null); // null = create
  const [refSetForm, setRefSetForm] = useState({ name: '', description: '', domain: '', steward: '' });
  const [refSetFieldErrors, setRefSetFieldErrors] = useState({});
  const [refSetSaving, setRefSetSaving] = useState(false);

  // Org Unit create/edit dialog
  const [orgUnitDialogOpen, setOrgUnitDialogOpen] = useState(false);
  const [orgUnitEditing, setOrgUnitEditing] = useState(null); // null = create
  const [orgUnitForm, setOrgUnitForm] = useState({ name: '', code: '', org_type: '', parent: '', description: '' });
  const [orgUnitFieldErrors, setOrgUnitFieldErrors] = useState({});
  const [orgUnitSaving, setOrgUnitSaving] = useState(false);

  // Confirm delete dialog
  const [confirmState, setConfirmState] = useState(null);

  const loadData = useCallback(async () => {
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
    } catch (_err) {
      const msg = _err.message || 'Failed to load MDM data';
      setError(msg);
      notify({ message: msg, type: 'error' });
    } finally {
      setLoading(false);
    }
  }, [token, notify]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // ---- Reference Set dialog handlers ----
  const openRefSetDialog = (row = null) => {
    setRefSetFieldErrors({});
    setRefSetEditing(row);
    setRefSetForm(row
      ? {
          name: row.name || '',
          description: row.description || '',
          domain: row.domain || '',
          steward: row.steward || '',
        }
      : { name: '', description: '', domain: '', steward: '' });
    setRefSetDialogOpen(true);
  };

  const closeRefSetDialog = () => {
    if (refSetSaving) return;
    setRefSetDialogOpen(false);
    setRefSetEditing(null);
    setRefSetFieldErrors({});
  };

  const handleSaveRefSet = async () => {
    // Client-side validation
    const errors = {};
    if (!refSetForm.name.trim()) errors.name = 'Name is required.';
    setRefSetFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    setRefSetSaving(true);
    try {
      const payload = {
        name: refSetForm.name.trim(),
        description: refSetForm.description.trim(),
        domain: refSetForm.domain || null,
        steward: refSetForm.steward || null,
        is_active: refSetEditing ? refSetEditing.is_active : true,
      };
      if (refSetEditing) {
        await updateReferenceSet(token, refSetEditing.id, payload);
        notify({ message: 'Reference set updated', type: 'success' });
      } else {
        await createReferenceSet(token, payload);
        notify({ message: 'Reference set created', type: 'success' });
      }
      closeRefSetDialog();
      await loadData();
    } catch (err) {
      const fieldErrors = mapFieldErrors(err);
      if (fieldErrors) {
        setRefSetFieldErrors(fieldErrors);
      } else {
        notify({ message: err.message || 'Failed to save reference set', type: 'error' });
      }
    } finally {
      setRefSetSaving(false);
    }
  };

  // ---- Org Unit dialog handlers ----
  const openOrgUnitDialog = (row = null) => {
    setOrgUnitFieldErrors({});
    setOrgUnitEditing(row);
    setOrgUnitForm(row
      ? {
          name: row.name || '',
          code: row.code || '',
          org_type: row.org_type || '',
          parent: row.parent || '',
          description: row.description || '',
        }
      : { name: '', code: '', org_type: '', parent: '', description: '' });
    setOrgUnitDialogOpen(true);
  };

  const closeOrgUnitDialog = () => {
    if (orgUnitSaving) return;
    setOrgUnitDialogOpen(false);
    setOrgUnitEditing(null);
    setOrgUnitFieldErrors({});
  };

  const handleSaveOrgUnit = async () => {
    // Client-side validation
    const errors = {};
    if (!orgUnitForm.name.trim()) errors.name = 'Name is required.';
    if (orgUnitForm.parent && orgUnitEditing && String(orgUnitForm.parent) === String(orgUnitEditing.id)) {
      errors.parent = 'A unit cannot be its own parent.';
    }
    setOrgUnitFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    setOrgUnitSaving(true);
    try {
      const payload = {
        name: orgUnitForm.name.trim(),
        code: orgUnitForm.code.trim() || null,
        org_type: orgUnitForm.org_type || null,
        parent: orgUnitForm.parent ? parseInt(orgUnitForm.parent, 10) : null,
        description: orgUnitForm.description.trim() || null,
        is_active: orgUnitEditing ? orgUnitEditing.is_active : true,
      };
      if (orgUnitEditing) {
        await updateOrgUnit(token, orgUnitEditing.id, payload);
        notify({ message: 'Org unit updated', type: 'success' });
      } else {
        await createOrgUnit(token, payload);
        notify({ message: 'Org unit created', type: 'success' });
      }
      closeOrgUnitDialog();
      await loadData();
    } catch (err) {
      const fieldErrors = mapFieldErrors(err);
      if (fieldErrors) {
        setOrgUnitFieldErrors(fieldErrors);
      } else {
        notify({ message: err.message || 'Failed to save org unit', type: 'error' });
      }
    } finally {
      setOrgUnitSaving(false);
    }
  };

  // ---- Delete handlers (ConfirmDialog) ----
  const handleDeleteRefSet = (row) => {
    setConfirmState({
      title: 'Delete reference set',
      message: `Delete "${row.name}"?\nThis will also delete all of its values. This action cannot be undone.`,
      destructive: true,
      confirmLabel: 'Delete',
      onConfirm: async () => {
        try {
          await deleteReferenceSet(token, row.id);
          notify({ message: 'Reference set deleted', type: 'success' });
          await loadData();
        } catch (err) {
          notify({ message: err.message || 'Failed to delete reference set', type: 'error' });
        }
      },
    });
  };

  const handleDeleteOrgUnit = (row) => {
    setConfirmState({
      title: 'Delete org unit',
      message: `Delete "${row.name}"?\nChild units will be detached (set to no parent). This action cannot be undone.`,
      destructive: true,
      confirmLabel: 'Delete',
      onConfirm: async () => {
        try {
          await deleteOrgUnit(token, row.id);
          notify({ message: 'Org unit deleted', type: 'success' });
          await loadData();
        } catch (err) {
          notify({ message: err.message || 'Failed to delete org unit', type: 'error' });
        }
      },
    });
  };

  const handleClearRefSetsFilters = () => {
    setSearchRefSets('');
    setFilterDomain('');
    setFilterSteward('');
    setFilterLifecycle('');
  };

  const handleClearOrgUnitsFilters = () => {
    setSearchOrgUnits('');
    setFilterOrgType('');
  };

  // Filtered Reference Sets
  const filteredRefSets = useMemo(() => {
    let filtered = refSets;

    if (searchRefSets.trim()) {
      const query = searchRefSets.toLowerCase();
      filtered = filtered.filter(
        (s) =>
          (s.name && s.name.toLowerCase().includes(query)) ||
          (s.description && s.description.toLowerCase().includes(query)) ||
          (s.steward_name && s.steward_name.toLowerCase().includes(query))
      );
    }

    if (filterDomain) {
      filtered = filtered.filter((s) => s.domain === filterDomain);
    }

    if (filterSteward) {
      filtered = filtered.filter((s) => s.steward === filterSteward);
    }

    if (filterLifecycle) {
      filtered = filtered.filter((s) => s.lifecycle_state === filterLifecycle);
    }

    return filtered;
  }, [refSets, searchRefSets, filterDomain, filterSteward, filterLifecycle]);

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
        <Typography
          variant="body2"
          sx={{ fontWeight: 500, cursor: 'pointer', color: 'primary.main', '&:hover': { textDecoration: 'underline' } }}
          onClick={() => navigate(`/catalog/mdm/reference-sets/${params.row.id}`)}
        >
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
      width: 150,
      renderCell: (params) => params.value || '—',
    },
    {
      field: 'steward_name',
      headerName: 'Steward',
      width: 130,
      renderCell: (params) => params.value || '—',
    },
    {
      field: 'lifecycle_state',
      headerName: 'Lifecycle',
      width: 120,
      type: 'singleSelect',
      valueOptions: ['draft', 'active', 'deprecated', 'archived'],
      renderCell: (params) => (
        <Chip
          label={LIFECYCLE_LABELS[params.value] || params.value || '—'}
          size="small"
          color={LIFECYCLE_COLORS[params.value] || 'default'}
          variant="filled"
        />
      ),
    },
    {
      field: 'value_count',
      headerName: 'Values',
      width: 90,
      renderCell: (params) => (
        <Tooltip title="View values">
          <Chip
            label={params.value || 0}
            size="small"
            color="primary"
            variant="outlined"
            clickable
            onClick={() => navigate(`/catalog/mdm/reference-sets/${params.row.id}`)}
          />
        </Tooltip>
      ),
    },
    {
      field: 'updated_at',
      headerName: 'Modified',
      width: 130,
      renderCell: (params) => (
        <Typography variant="body2" color="text.secondary">
          {params.value ? dayjs(params.value).format('MMM D, YYYY') : '—'}
        </Typography>
      ),
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 150,
      sortable: false,
      filterable: false,
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
          <Tooltip title="Edit">
            <IconButton size="small" onClick={() => openRefSetDialog(params.row)}>
              <EditIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Delete">
            <IconButton
              size="small"
              color="error"
              onClick={() => handleDeleteRefSet(params.row)}
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
      width: 130,
      renderCell: (params) => (
        <Chip label={params.value || 'other'} size="small" variant="outlined" />
      ),
    },
    {
      field: 'code',
      headerName: 'Code',
      width: 110,
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
      field: 'updated_at',
      headerName: 'Modified',
      width: 130,
      renderCell: (params) => (
        <Typography variant="body2" color="text.secondary">
          {params.value ? dayjs(params.value).format('MMM D, YYYY') : '—'}
        </Typography>
      ),
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 120,
      sortable: false,
      filterable: false,
      renderCell: (params) => (
        <Box sx={{ display: 'flex', gap: 0.5 }}>
          <Tooltip title="Edit">
            <IconButton size="small" onClick={() => openOrgUnitDialog(params.row)}>
              <EditIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Delete">
            <IconButton
              size="small"
              color="error"
              onClick={() => handleDeleteOrgUnit(params.row)}
            >
              <DeleteIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      ),
    },
  ];

  // Parent options for the org unit dialog (exclude self to prevent cycles)
  const parentOptions = useMemo(() => {
    if (!orgUnitEditing) return orgUnits;
    return orgUnits.filter((u) => u.id !== orgUnitEditing.id);
  }, [orgUnits, orgUnitEditing]);

  return (
    <PageContainer>
      <PageHeader
        icon={AccountTreeIcon}
        title="Master Data Management"
        subtitle="Controlled vocabularies and organizational hierarchy"
        description="Manage reference sets (values live on the set's detail page) and the organizational unit tree that anchors RBAC and governance."
        actions={
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => (tabValue === 0 ? openRefSetDialog() : openOrgUnitDialog())}
          >
            {tabValue === 0 ? 'New Reference Set' : 'New Org Unit'}
          </Button>
        }
      />

      {/* Tabs */}
      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 0.75 }}>
        <Tabs value={tabValue} onChange={(e, val) => setTabValue(val)} sx={{ minHeight: 32, '& .MuiTab-root': { minHeight: 32, py: 0.5, fontSize: '0.6875rem' } }}>
          <Tab label={`Reference Sets (${refSets.length})`} />
          <Tab label={`Org Units (${orgUnits.length})`} />
        </Tabs>
      </Box>

      {/* Tab 0: Reference Sets */}
      <TabPanel value={tabValue} index={0}>
        <Paper sx={{ p: 0.75, mb: 1, bgcolor: 'background.dark' }}>
          <Grid container spacing={0.75} alignItems="center">
            <Grid size={{ xs: 12, md: 4 }}>
              <TextField
                fullWidth
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
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <FormControl fullWidth size="small">
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
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <FormControl fullWidth size="small">
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
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 2 }}>
              <FormControl fullWidth size="small">
                <InputLabel>Lifecycle</InputLabel>
                <Select
                  value={filterLifecycle}
                  onChange={(e) => setFilterLifecycle(e.target.value)}
                  label="Lifecycle"
                >
                  <MenuItem value="">All</MenuItem>
                  {(LIFECYCLE_STATES || []).map((state) => (
                    <MenuItem key={state.value} value={state.value}>
                      {state.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid size={{ xs: 12, md: 1.5 }}>
              <Button
                fullWidth
                size="small"
                startIcon={<ClearIcon />}
                onClick={handleClearRefSetsFilters}
                disabled={!searchRefSets && !filterDomain && !filterSteward && !filterLifecycle}
              >
                Clear
              </Button>
            </Grid>
          </Grid>
        </Paper>

        {loading ? (
          <LoadingSkeleton variant="table" />
        ) : error ? (
          <ErrorAlert message={error} onRetry={loadData} />
        ) : filteredRefSets.length === 0 ? (
          <EmptyState
            icon={<CategoryIcon />}
            title="No reference sets found"
            description={
              refSets.length === 0
                ? 'Create your first reference set to start building controlled vocabularies.'
                : 'No reference sets match the current filters.'
            }
            actionLabel={refSets.length === 0 ? 'New Reference Set' : undefined}
            onAction={refSets.length === 0 ? () => openRefSetDialog() : undefined}
          />
        ) : (
          <StandardDataGrid rows={filteredRefSets} columns={refSetsColumns} toolbar pageSize={25} />
        )}
      </TabPanel>

      {/* Tab 1: Org Units */}
      <TabPanel value={tabValue} index={1}>
        <Paper sx={{ p: 2, mb: 2, bgcolor: 'background.dark' }}>
          <Grid container spacing={2} alignItems="center">
            <Grid size={{ xs: 12, md: 6 }}>
              <TextField
                fullWidth
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
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 4 }}>
              <FormControl fullWidth size="small">
                <InputLabel>Type</InputLabel>
                <Select
                  value={filterOrgType}
                  onChange={(e) => setFilterOrgType(e.target.value)}
                  label="Type"
                >
                  <MenuItem value="">All Types</MenuItem>
                  {ORG_TYPES.map((t) => (
                    <MenuItem key={t.value} value={t.value}>
                      {t.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid size={{ xs: 12, md: 2 }}>
              <Button
                fullWidth
                size="small"
                startIcon={<ClearIcon />}
                onClick={handleClearOrgUnitsFilters}
                disabled={!searchOrgUnits && !filterOrgType}
              >
                Clear
              </Button>
            </Grid>
          </Grid>
        </Paper>

        {loading ? (
          <LoadingSkeleton variant="table" />
        ) : error ? (
          <ErrorAlert message={error} onRetry={loadData} />
        ) : filteredOrgUnits.length === 0 ? (
          <EmptyState
            icon={<AccountTreeIcon />}
            title="No org units found"
            description={
              orgUnits.length === 0
                ? 'Create your first org unit to start building the organizational tree.'
                : 'No org units match the current filters.'
            }
            actionLabel={orgUnits.length === 0 ? 'New Org Unit' : undefined}
            onAction={orgUnits.length === 0 ? () => openOrgUnitDialog() : undefined}
          />
        ) : (
          <StandardDataGrid rows={filteredOrgUnits} columns={orgUnitsColumns} toolbar pageSize={25} />
        )}
      </TabPanel>

      {/* Reference Set create/edit dialog */}
      <SystemDialog
        open={refSetDialogOpen}
        title={refSetEditing ? 'Edit Reference Set' : 'New Reference Set'}
        width={520}
        height={560}
        onClose={closeRefSetDialog}
        showCancel={false}
        actions={
          <Button
            onClick={handleSaveRefSet}
            variant="contained"
            disabled={refSetSaving}
            startIcon={refSetSaving ? <CircularProgress size={16} /> : null}
          >
            {refSetSaving ? 'Saving…' : refSetEditing ? 'Save Changes' : 'Create'}
          </Button>
        }
      >
        <Stack spacing={2} sx={{ pt: 1 }}>
          {refSetFieldErrors.non_field_errors && (
            <Alert severity="error">{refSetFieldErrors.non_field_errors}</Alert>
          )}
          <TextField
            fullWidth
            label="Name"
            required
            value={refSetForm.name}
            onChange={(e) => setRefSetForm({ ...refSetForm, name: e.target.value })}
            error={Boolean(refSetFieldErrors.name)}
            helperText={refSetFieldErrors.name}
            autoFocus
          />
          <TextField
            fullWidth
            label="Description"
            multiline
            rows={2}
            value={refSetForm.description}
            onChange={(e) => setRefSetForm({ ...refSetForm, description: e.target.value })}
            error={Boolean(refSetFieldErrors.description)}
            helperText={refSetFieldErrors.description}
          />
          <Autocomplete
            value={domains.find((d) => d.id === refSetForm.domain) || null}
            options={domains}
            getOptionLabel={(o) => o.name || ''}
            isOptionEqualToValue={(o, v) => o.id === v.id}
            onChange={(_, v) => setRefSetForm({ ...refSetForm, domain: v ? v.id : '' })}
            renderInput={(params) => (
              <TextField {...params} label="Domain" error={Boolean(refSetFieldErrors.domain)} helperText={refSetFieldErrors.domain} />
            )}
          />
          <Autocomplete
            value={users.find((u) => u.id === refSetForm.steward) || null}
            options={users}
            getOptionLabel={(o) => o.username || ''}
            isOptionEqualToValue={(o, v) => o.id === v.id}
            onChange={(_, v) => setRefSetForm({ ...refSetForm, steward: v ? v.id : '' })}
            renderInput={(params) => (
              <TextField {...params} label="Steward" error={Boolean(refSetFieldErrors.steward)} helperText={refSetFieldErrors.steward} />
            )}
          />
        </Stack>
      </SystemDialog>

      {/* Org Unit create/edit dialog */}
      <SystemDialog
        open={orgUnitDialogOpen}
        title={orgUnitEditing ? 'Edit Org Unit' : 'New Org Unit'}
        width={520}
        height={620}
        onClose={closeOrgUnitDialog}
        showCancel={false}
        actions={
          <Button
            onClick={handleSaveOrgUnit}
            variant="contained"
            disabled={orgUnitSaving}
            startIcon={orgUnitSaving ? <CircularProgress size={16} /> : null}
          >
            {orgUnitSaving ? 'Saving…' : orgUnitEditing ? 'Save Changes' : 'Create'}
          </Button>
        }
      >
        <Stack spacing={2} sx={{ pt: 1 }}>
          {orgUnitFieldErrors.non_field_errors && (
            <Alert severity="error">{orgUnitFieldErrors.non_field_errors}</Alert>
          )}
          <TextField
            fullWidth
            label="Name"
            required
            value={orgUnitForm.name}
            onChange={(e) => setOrgUnitForm({ ...orgUnitForm, name: e.target.value })}
            error={Boolean(orgUnitFieldErrors.name)}
            helperText={orgUnitFieldErrors.name}
            autoFocus
          />
          <TextField
            fullWidth
            label="Code"
            value={orgUnitForm.code}
            onChange={(e) => setOrgUnitForm({ ...orgUnitForm, code: e.target.value })}
            error={Boolean(orgUnitFieldErrors.code)}
            helperText={orgUnitFieldErrors.code}
          />
          <FormControl fullWidth error={Boolean(orgUnitFieldErrors.org_type)}>
            <InputLabel>Type</InputLabel>
            <Select
              value={orgUnitForm.org_type}
              label="Type"
              onChange={(e) => setOrgUnitForm({ ...orgUnitForm, org_type: e.target.value })}
            >
              <MenuItem value="">— None —</MenuItem>
              {ORG_TYPES.map((t) => (
                <MenuItem key={t.value} value={t.value}>
                  {t.label}
                </MenuItem>
              ))}
            </Select>
            {orgUnitFieldErrors.org_type && (
              <Typography variant="caption" color="error">
                {orgUnitFieldErrors.org_type}
              </Typography>
            )}
          </FormControl>
          <Autocomplete
            value={parentOptions.find((o) => o.id === orgUnitForm.parent) || null}
            options={parentOptions}
            getOptionLabel={(o) => o.full_path || o.name || ''}
            isOptionEqualToValue={(o, v) => o.id === v.id}
            onChange={(_, v) => setOrgUnitForm({ ...orgUnitForm, parent: v ? v.id : '' })}
            renderInput={(params) => (
              <TextField {...params} label="Parent" error={Boolean(orgUnitFieldErrors.parent)} helperText={orgUnitFieldErrors.parent} />
            )}
          />
          <TextField
            fullWidth
            label="Description"
            multiline
            rows={2}
            value={orgUnitForm.description}
            onChange={(e) => setOrgUnitForm({ ...orgUnitForm, description: e.target.value })}
            error={Boolean(orgUnitFieldErrors.description)}
            helperText={orgUnitFieldErrors.description}
          />
        </Stack>
      </SystemDialog>

      {/* Confirm delete dialog */}
      <ConfirmDialog
        open={Boolean(confirmState)}
        title={confirmState?.title || 'Confirm'}
        message={confirmState?.message || ''}
        destructive={confirmState?.destructive}
        confirmLabel={confirmState?.confirmLabel || 'Confirm'}
        onCancel={() => setConfirmState(null)}
        onConfirm={async () => {
          const { onConfirm } = confirmState || {};
          setConfirmState(null);
          if (onConfirm) await onConfirm();
        }}
      />
    </PageContainer>
  );
}
