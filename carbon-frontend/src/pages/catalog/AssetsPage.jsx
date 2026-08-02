// src/pages/catalog/AssetsPage.jsx
// Catalog: Browse and manage asset profiles (metadata for tables/fields)
// Phase 1: Unified list view with DataGrid, filtering, searching, sorting, pagination

import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import { 
  fetchAssetProfiles, 
  fetchDataDomains, 
  deleteAssetProfile
} from '../../api/catalog';
import useDocumentTitle from '../../hooks/useDocumentTitle';

import {
  Box,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
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
  Chip,
  Stack,
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
  const [_deleteConfirm, setDeleteConfirm] = useState(null);

  // Grid state
  const [_paginationModel, _setPaginationModel] = useState({ pageSize: 25, page: 0 });
  const [_sortModel, _setSortModel] = useState([]);

  // Filter state
  const [searchText, setSearchText] = useState('');
  const [filterDomain, setFilterDomain] = useState('');
  const [filterClassification, setFilterClassification] = useState('');
  const [filterQuality, setFilterQuality] = useState('');
  const [filterAssetType, setFilterAssetType] = useState('');

  // Load assets and domains on mount
  useEffect(() => {
    loadData();
  }, [token]);

  const loadData = async () => {
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
  };

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
  const _handleDelete = async (id) => {
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

  const hasActiveFilters = 
    searchText || filterDomain || filterClassification || filterQuality || filterAssetType;

  return (
    <Box sx={{ p: 0 }}>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <FilteredDataGrid
        title="Asset Profiles"
        subtitle={`${filteredAssets.length} of ${assets.length} assets`}
        actions={(
          <Button
            startIcon={<AddIcon />}
            variant="contained"
            onClick={() => navigate('/catalog/assets/new')}
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
    </Box>
  );
}
