// src/pages/catalog/AssetsPage.jsx
// Catalog: Browse and manage asset profiles (metadata for tables/fields)
// Phase 1: Unified list view with DataGrid, filtering, searching, sorting, pagination

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import { 
  fetchAssetProfiles, 
  fetchDataDomains, 
  deleteAssetProfile,
  createAssetProfile,
  fetchGlossaryTerms,
  fetchTags,
} from '../../api/catalog';
import { fetchUsers } from '../../api/users';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import SystemDialog from '../../components/SystemDialog';
import ConfirmDialog from '../../components/ConfirmDialog';

import {
  Autocomplete,
  Box,
  Button,
  TextField,
  Paper,
  IconButton,
  Tooltip,
  CircularProgress,
  Alert,
  Typography,
  MenuItem,
  Chip,
  useTheme,
  useMediaQuery,
  Grid,
  Card,
  CardContent,
  LinearProgress,
} from '@mui/material';
import FilteredDataGrid from '../../components/FilteredDataGrid';
import { DataGrid } from '@mui/x-data-grid';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import AddIcon from '@mui/icons-material/Add';
import VisibilityIcon from '@mui/icons-material/Visibility';
import SearchIcon from '@mui/icons-material/Search';
import StorageIcon from '@mui/icons-material/Storage';
import ViewWeekIcon from '@mui/icons-material/ViewWeek';
import LockIcon from '@mui/icons-material/Lock';

// Quality Status Badge Component
function QualityStatusBadge({ value, score }) {
  const colorMap = {
    passing: '#4caf50',
    warning: '#ff9800',
    failing: '#f44336',
    unknown: '#9e9e9e',
  };

  const _iconMap = {
    passing: '✓',
    warning: '!',
    failing: '✕',
    unknown: '?',
  };

  return (
    <Chip
      label={`${(value || 'unknown').charAt(0).toUpperCase() + (value || 'unknown').slice(1)} ${score ? `(${score}%)` : ''}`}
      size="small"
      sx={{
        backgroundColor: colorMap[value] || colorMap.unknown,
        color: 'white',
        fontWeight: 500,
      }}
    />
  );
}

// Classification Badge Component
function ClassificationBadge({ value }) {
  const iconMap = {
    public: '🟢',
    internal: '🟡',
    confidential: '🔶',
    pii: '🔴',
    sensitive: '🔴',
  };

  const labelMap = {
    public: 'Public',
    internal: 'Internal',
    confidential: 'Confidential',
    pii: 'PII',
    sensitive: 'Sensitive',
  };

  return (
    <Chip
      icon={<LockIcon fontSize="small" />}
      label={`${iconMap[value] || '?'} ${labelMap[value] || value}`}
      size="small"
      variant="outlined"
    />
  );
}

export default function AssetsPage() {
  useDocumentTitle("Assets");
  const navigate = useNavigate();
  const { token } = useAuth();
  const { notify } = useNotification();
  const theme = useTheme();
  const _isMobile = useMediaQuery(theme.breakpoints.down('md'));

  // State
  const [assets, setAssets] = useState([]);
  const [domains, setDomains] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [deleteConfirm, setDeleteConfirm] = useState(null);

  // Create dialog state
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [createSaving, setCreateSaving] = useState(false);
  const [createError, setCreateError] = useState(null);
  const [createForm, setCreateForm] = useState({
    description: '',
    domain: '',
    owner: '',
    steward: '',
    classification: '',
    semantic_type: '',
    glossary_term: '',
  });
  const [createFormUsers, setCreateFormUsers] = useState([]);
  const [createFormGlossary, setCreateFormGlossary] = useState([]);
  const [createFormTags, setCreateFormTags] = useState([]);
  const [createFormAllTags, setCreateFormAllTags] = useState([]);

  // Grid state
  const [_paginationModel, _setPaginationModel] = useState({ pageSize: 25, page: 0 });
  const [_sortModel, _setSortModel] = useState([]);

  // Filter state
  const [searchText, setSearchText] = useState('');
  const [filterDomain, setFilterDomain] = useState('');
  const [filterClassification, setFilterClassification] = useState('');
  const [filterQuality, setFilterQuality] = useState('');
  const [filterAssetType, setFilterAssetType] = useState('');

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [assetsData, domainsData] = await Promise.all([
        fetchAssetProfiles(token),
        fetchDataDomains(token),
      ]);
      setAssets(Array.isArray(assetsData) ? assetsData : assetsData.results || []);
      setDomains(Array.isArray(domainsData) ? domainsData : domainsData.results || []);
    } catch (err) {
      const msg = err.message || 'Failed to load assets';
      setError(msg);
      notify({ message: msg, type: 'error' });
    } finally {
      setLoading(false);
    }
  }, [token, notify]);

  // Load assets and domains on mount
  useEffect(() => {
    loadData();
  }, [loadData]);

  // Filter and sort assets
  const filteredAssets = useMemo(() => {
    let filtered = assets;

    // Text search
    if (searchText.trim()) {
      const query = searchText.toLowerCase();
      filtered = filtered.filter(
        a =>
          (a.title && a.title.toLowerCase().includes(query)) ||
          (a.description && a.description.toLowerCase().includes(query))
      );
    }

    // Domain filter
    if (filterDomain) {
      filtered = filtered.filter(a => a.domain === parseInt(filterDomain));
    }

    // Classification filter
    if (filterClassification) {
      filtered = filtered.filter(a => a.classification === filterClassification);
    }

    // Quality filter
    if (filterQuality) {
      filtered = filtered.filter(a => a.quality_status === filterQuality);
    }

    // Asset type filter
    if (filterAssetType) {
      filtered = filtered.filter(a => a.asset_type === filterAssetType);
    }

    return filtered;
  }, [assets, searchText, filterDomain, filterClassification, filterQuality, filterAssetType]);

  // Handle delete
  const confirmDelete = async () => {
    if (deleteConfirm == null) return;
    const id = deleteConfirm;
    setDeleteConfirm(null);
    try {
      await deleteAssetProfile(token, id);
      notify({ message: 'Asset deleted', type: 'success' });
      await loadData();
    } catch (err) {
      const msg = err.message || 'Failed to delete asset';
      setError(msg);
      notify({ message: msg, type: 'error' });
    }
  };

  // DataGrid columns
  const columns = [
    {
      field: 'title',
      headerName: 'Asset Name',
      flex: 1.5,
      minWidth: 200,
      sortable: true,
      renderCell: (params) => {
        const icon = params.row.asset_type === 'table' ? <StorageIcon fontSize="small" /> : <ViewWeekIcon fontSize="small" />;
        return (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            {icon}
            <Typography variant="body2" sx={{ fontWeight: 500 }}>
              {params.value || '—'}
            </Typography>
          </Box>
        );
      },
    },
    {
      field: 'asset_type',
      headerName: 'Type',
      width: 90,
      sortable: true,
      renderCell: (params) => (
        <Chip
          label={params.value === 'table' ? '🏠 Table' : '📄 Field'}
          size="small"
          variant="filled"
        />
      ),
    },
    {
      field: 'domain_name',
      headerName: 'Domain',
      flex: 1,
      minWidth: 120,
      sortable: true,
      renderCell: (params) => (
        <Typography variant="body2">{params.value || '—'}</Typography>
      ),
    },
    {
      field: 'classification',
      headerName: 'Classification',
      flex: 1,
      minWidth: 140,
      sortable: true,
      renderCell: (params) => (
        <ClassificationBadge value={params.value} />
      ),
    },
    {
      field: 'quality_status',
      headerName: 'Quality',
      flex: 1,
      minWidth: 140,
      sortable: true,
      renderCell: (params) => (
        <QualityStatusBadge value={params.value} score={params.row.quality_score} />
      ),
    },
    {
      field: 'steward_name',
      headerName: 'Steward',
      flex: 1,
      minWidth: 120,
      sortable: true,
      renderCell: (params) => (
        <Typography variant="body2">{params.value || '—'}</Typography>
      ),
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 120,
      sortable: false,
      renderCell: (params) => (
        <Box sx={{ display: 'flex', gap: 0.5 }}>
          <Tooltip title="View Details">
            <IconButton
              size="small"
              onClick={() => navigate(`/catalog/assets/${params.row.id}`)}
            >
              <VisibilityIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Edit">
            <IconButton
              size="small"
              onClick={() => navigate(`/catalog/assets/${params.row.id}`)}
            >
              <EditIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Delete">
            <IconButton
              size="small"
              color="error"
              onClick={() => setDeleteConfirm(params.row.id)}
            >
              <DeleteIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      ),
    },
  ];

  // Clear filters
  const handleClearFilters = () => {
    setSearchText('');
    setFilterDomain('');
    setFilterClassification('');
    setFilterQuality('');
    setFilterAssetType('');
  };

  // --- Create dialog handlers ---
  const handleOpenCreate = async () => {
    setCreateError(null);
    setCreateSaving(false);
    setCreateForm({
      description: '',
      domain: '',
      owner: '',
      steward: '',
      classification: '',
      semantic_type: '',
      glossary_term: '',
    });
    setCreateFormTags([]);
    try {
      const [users, glossary, allTags] = await Promise.all([
        fetchUsers(token),
        fetchGlossaryTerms(token),
        fetchTags(token),
      ]);
      setCreateFormUsers(Array.isArray(users) ? users : users?.results || []);
      setCreateFormGlossary(Array.isArray(glossary) ? glossary : glossary?.results || []);
      setCreateFormAllTags(Array.isArray(allTags) ? allTags : allTags?.results || []);
    } catch (_e) {
      // Non-critical — dialog opens anyway with empty dropdowns
    }
    setCreateDialogOpen(true);
  };

  const handleCloseCreate = () => {
    if (createSaving) return;
    setCreateDialogOpen(false);
  };

  const handleCreateSave = async () => {
    if (!createForm.description.trim()) {
      setCreateError('Description is required.');
      return;
    }
    setCreateSaving(true);
    setCreateError(null);
    try {
      const payload = {
        description: createForm.description.trim(),
        domain: createForm.domain ? parseInt(createForm.domain) : null,
        owner: createForm.owner ? parseInt(createForm.owner) : null,
        steward: createForm.steward ? parseInt(createForm.steward) : null,
        classification: createForm.classification || null,
        semantic_type: createForm.semantic_type.trim() || null,
        glossary_term: createForm.glossary_term ? parseInt(createForm.glossary_term) : null,
        tags: createFormTags,
      };
      await createAssetProfile(token, payload);
      notify({ message: 'Asset profile created', type: 'success' });
      setCreateDialogOpen(false);
      await loadData();
    } catch (err) {
      setCreateError(err.message || 'Failed to create asset profile.');
    } finally {
      setCreateSaving(false);
    }
  };

  const hasActiveFilters = 
    searchText || filterDomain || filterClassification || filterQuality || filterAssetType;

  return (
    <Box sx={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {error && <Alert severity="error" sx={{ mx: 2, mt: 2, flexShrink: 0 }}>{error}</Alert>}

      <FilteredDataGrid
        title="Asset Profiles"
        subtitle={`${filteredAssets.length} of ${assets.length} assets`}
        description="Asset profiles define metadata for tables and fields — classification, quality scores, lineage, and ownership. Browse, create, and manage governed data assets."
        actions={(
          <Button
            startIcon={<AddIcon />}
            variant="contained"
            onClick={handleOpenCreate}
          >
            New Asset
          </Button>
        )}
        rows={filteredAssets}
        loading={loading}
        columns={columns}
        countLabel={`${filteredAssets.length} of ${assets.length} assets`}
        searchValue={searchText}
        onSearchChange={setSearchText}
        filterDefs={[
          {
            key: 'domain',
            label: 'Domain',
            emptyLabel: 'All Domains',
            options: domains.map((d) => ({ value: d.id, label: d.name })),
          },
          {
            key: 'classification',
            label: 'Classification',
            emptyLabel: 'All Levels',
            options: [
              { value: 'public', label: 'Public' },
              { value: 'internal', label: 'Internal' },
              { value: 'confidential', label: 'Confidential' },
              { value: 'pii', label: 'PII' },
              { value: 'sensitive', label: 'Sensitive' },
            ],
          },
          {
            key: 'quality',
            label: 'Quality',
            emptyLabel: 'All Status',
            options: [
              { value: 'passing', label: 'Passing' },
              { value: 'warning', label: 'Warning' },
              { value: 'failing', label: 'Failing' },
              { value: 'unknown', label: 'Unknown' },
            ],
          },
          {
            key: 'assetType',
            label: 'Asset Type',
            emptyLabel: 'All Types',
            options: [
              { value: 'table', label: 'Table' },
              { value: 'field', label: 'Field' },
            ],
          },
        ]}
        filterValues={{
          domain: filterDomain,
          classification: filterClassification,
          quality: filterQuality,
          assetType: filterAssetType,
        }}
        onFilterChange={(key, value) => {
          if (key === 'domain') setFilterDomain(value);
          if (key === 'classification') setFilterClassification(value);
          if (key === 'quality') setFilterQuality(value);
          if (key === 'assetType') setFilterAssetType(value);
        }}
        onClearFilters={handleClearFilters}
        pageSize={25}
        rowsPerPageOptions={[25, 50, 100]}
        emptyMessage="No assets found"
        emptySubtext={hasActiveFilters ? 'Try adjusting your filters' : 'Assets are auto-created for all tables and fields'}
      />

      {/* Create Asset Dialog (SystemDialog — design system primitive) */}
      <SystemDialog
        open={createDialogOpen}
        title="New Asset Profile"
        onClose={handleCloseCreate}
        onCancel={handleCloseCreate}
        cancelLabel="Cancel"
        width={560}
        height={640}
        minWidth={480}
        minHeight={440}
        maxWidth="calc(100vw - 32px)"
        maxHeight="calc(100vh - 32px)"
        actions={
          <Button
            onClick={handleCreateSave}
            variant="contained"
            size="small"
            disabled={createSaving}
            startIcon={createSaving ? <CircularProgress size={16} /> : null}
          >
            {createSaving ? 'Creating…' : 'Create'}
          </Button>
        }
      >
        <Box px={2} py={1}>
          {createError && <Alert severity="error" sx={{ mb: 2 }}>{createError}</Alert>}
          <TextField
            fullWidth
            size="small"
            label="Description"
            margin="normal"
            required
            multiline
            rows={2}
            value={createForm.description}
            onChange={(e) => setCreateForm({ ...createForm, description: e.target.value })}
            autoFocus
          />
          <Autocomplete
            value={domains.find((d) => d.id === createForm.domain) || null}
            options={domains}
            getOptionLabel={(d) => d.name}
            isOptionEqualToValue={(opt, val) => opt.id === val.id}
            onChange={(e, val) => setCreateForm({ ...createForm, domain: val?.id || '' })}
            renderInput={(params) => <TextField {...params} label="Domain" margin="normal" />}
          />
          <TextField
            select
            fullWidth
            label="Classification"
            margin="normal"
            value={createForm.classification}
            onChange={(e) => setCreateForm({ ...createForm, classification: e.target.value })}
          >
            <MenuItem value="">— None —</MenuItem>
            <MenuItem value="public">Public</MenuItem>
            <MenuItem value="internal">Internal</MenuItem>
            <MenuItem value="confidential">Confidential</MenuItem>
            <MenuItem value="pii">PII</MenuItem>
            <MenuItem value="sensitive">Sensitive</MenuItem>
          </TextField>
          <Autocomplete
            value={createFormUsers.find((u) => u.id === createForm.owner) || null}
            options={createFormUsers}
            getOptionLabel={(u) => u.username || u.email || String(u.id)}
            isOptionEqualToValue={(opt, val) => opt.id === val.id}
            onChange={(e, val) => setCreateForm({ ...createForm, owner: val?.id || '' })}
            renderInput={(params) => <TextField {...params} label="Owner" margin="normal" />}
          />
          <Autocomplete
            value={createFormUsers.find((u) => u.id === createForm.steward) || null}
            options={createFormUsers}
            getOptionLabel={(u) => u.username || u.email || String(u.id)}
            isOptionEqualToValue={(opt, val) => opt.id === val.id}
            onChange={(e, val) => setCreateForm({ ...createForm, steward: val?.id || '' })}
            renderInput={(params) => <TextField {...params} label="Steward" margin="normal" />}
          />
          <TextField
            fullWidth
            label="Semantic Type"
            margin="normal"
            value={createForm.semantic_type}
            onChange={(e) => setCreateForm({ ...createForm, semantic_type: e.target.value })}
          />
          <Autocomplete
            value={createFormGlossary.find((g) => g.id === createForm.glossary_term) || null}
            options={createFormGlossary}
            getOptionLabel={(g) => g.term || g.name || String(g.id)}
            isOptionEqualToValue={(opt, val) => opt.id === val.id}
            onChange={(e, val) => setCreateForm({ ...createForm, glossary_term: val?.id || '' })}
            renderInput={(params) => <TextField {...params} label="Glossary Term" margin="normal" />}
          />
          <Autocomplete
            multiple
            value={createFormAllTags.filter((t) => createFormTags.includes(t.id))}
            options={createFormAllTags}
            getOptionLabel={(t) => t.name}
            isOptionEqualToValue={(opt, val) => opt.id === val.id}
            onChange={(e, val) => setCreateFormTags(val.map((t) => t.id))}
            renderInput={(params) => <TextField {...params} label="Tags" margin="normal" />}
            renderTags={(value, getTagProps) =>
              value.map((option, index) => (
                <Chip key={option.id} label={option.name} size="small" {...getTagProps({ index })} />
              ))
            }
          />
        </Box>
      </SystemDialog>

      <ConfirmDialog
        open={deleteConfirm != null}
        title="Delete asset?"
        message={`Delete asset "${filteredAssets.find((a) => a.id === deleteConfirm)?.title || 'this asset'}"? This action cannot be undone.`}
        confirmLabel="Delete"
        destructive
        onConfirm={confirmDelete}
        onCancel={() => setDeleteConfirm(null)}
      />
    </Box>
  );
}
