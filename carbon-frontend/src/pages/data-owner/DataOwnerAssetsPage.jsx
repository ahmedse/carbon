// src/pages/data-owner/DataOwnerAssetsPage.jsx
// Simplified asset browser for data owners - scoped to their org unit

import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import { fetchOwnerAssets } from '../../api/emissions';
import {
  Box,
  Container,
  Grid,
  Card,
  CardContent,
  CardActions,
  Typography,
  Button,
  Chip,
  CircularProgress,
  Alert,
  Paper,
  TextField,
  Stack,
  Divider,
  InputAdornment,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  useTheme,
  useMediaQuery,
} from '@mui/material';
import {
  Search as SearchIcon,
  Info as InfoIcon,
  CheckCircle as PassIcon,
  Warning as WarningIcon,
  Error as FailIcon,
} from '@mui/icons-material';
import { DataGrid } from '@mui/x-data-grid';

const QualityStatusBadge = ({ value, score, theme }) => {
  const colorMap = {
    passing: { bg: `${theme.palette.success.main}20`, color: theme.palette.success.dark, icon: PassIcon },
    warning: { bg: `${theme.palette.warning.main}20`, color: theme.palette.warning.dark, icon: WarningIcon },
    failing: { bg: `${theme.palette.error.main}20`, color: theme.palette.error.dark, icon: FailIcon },
    unknown: { bg: theme.palette.action.disabledBackground, color: theme.palette.text.secondary, icon: InfoIcon },
  };

  const config = colorMap[value] || colorMap.unknown;
  const Icon = config.icon;

  return (
    <Chip
      icon={<Icon sx={{ fontSize: 16 }} />}
      label={`${(value || 'unknown').charAt(0).toUpperCase() + (value || 'unknown').slice(1)} ${
        score ? `(${score}%)` : ''
      }`}
      size="small"
      sx={{
        backgroundColor: config.bg,
        color: config.color,
        fontWeight: 500,
      }}
    />
  );
};

export default function DataOwnerAssetsPage() {
  const { user: _user, context, token } = useAuth();
  const navigate = useNavigate();
  const { showNotification } = useNotification();
  const [searchParams] = useSearchParams();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

  const [assets, setAssets] = useState([]);
  const [domains, setDomains] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchText, setSearchText] = useState('');
  const [selectedDomain, setSelectedDomain] = useState(searchParams.get('domain') || '');
  const [paginationModel, setPaginationModel] = useState({ pageSize: 25, page: 0 });

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);

        if (!context?.org_units || context.org_units.length === 0) {
          setError('no-scope');
          setLoading(false);
          return;
        }

        const assetsRes = await fetchOwnerAssets({}, token);
        const assetsList = Array.isArray(assetsRes) ? assetsRes : [];
        const domainList = assetsList.reduce((acc, asset) => {
          const domain = asset.domain;
          if (domain && !acc.some(item => item.id === domain.id)) {
            acc.push({ id: domain.id, name: domain.name || 'Unassigned' });
          }
          return acc;
        }, []);

        setDomains(domainList);
        setAssets(assetsList);
        setError(null);
      } catch (err) {
        console.error('Error loading assets:', err);
        setError('load-failed');
        showNotification({
          message: 'Failed to load assets',
          type: 'error',
        });
      } finally {
        setLoading(false);
      }
    };

    if (token && context) {
      loadData();
    }
  }, [token, context, showNotification]);

  // Filter assets
  const filteredAssets = useMemo(() => {
    let filtered = assets;

    // Domain filter
    if (selectedDomain) {
      filtered = filtered.filter(a => String(a.domain?.id) === selectedDomain);
    }

    // Search filter
    if (searchText) {
      const query = searchText.toLowerCase();
      filtered = filtered.filter(
        a =>
          (a.name && a.name.toLowerCase().includes(query)) ||
          (a.description && a.description.toLowerCase().includes(query)) ||
          (a.data_table?.name && a.data_table.name.toLowerCase().includes(query)) ||
          (a.data_field?.name && a.data_field.name.toLowerCase().includes(query))
      );
    }

    return filtered;
  }, [assets, selectedDomain, searchText]);

  if (loading) {
    return (
      <Container>
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
          <CircularProgress />
        </Box>
      </Container>
    );
  }

  if (error === 'no-scope') {
    return (
      <Container>
        <Box sx={{ textAlign: 'center', py: 8 }}>
          <Alert severity="info">No data scope assigned. Contact your administrator.</Alert>
        </Box>
      </Container>
    );
  }

  // DataGrid columns
  const columns = [
    {
      field: 'name',
      headerName: 'Asset',
      flex: 1,
      minWidth: 180,
      renderCell: (params) => (
        <Box>
          <Typography variant="body2" sx={{ fontWeight: 500 }}>
            {params.row.name}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {params.row.data_table?.name || params.row.data_field?.name || 'N/A'}
          </Typography>
        </Box>
      ),
    },
    {
      field: 'domain',
      headerName: 'Domain',
      flex: 0.8,
      minWidth: 120,
      renderCell: (params) => (
        <Chip label={params.row.domain?.name || 'Unassigned'} size="small" variant="outlined" />
      ),
    },
    {
      field: 'quality_status',
      headerName: 'Quality',
      flex: 0.8,
      minWidth: 150,
      renderCell: (params) => (
        <QualityStatusBadge value={params.row.quality_status} score={params.row.quality_score} theme={theme} />
      ),
    },
    {
      field: 'owner',
      headerName: 'Owner',
      flex: 0.7,
      minWidth: 120,
      renderCell: (params) => (
        <Typography variant="caption">{params.row.owner?.first_name || params.row.owner?.username || '—'}</Typography>
      ),
    },
    {
      field: 'id',
      headerName: 'Actions',
      flex: 0.5,
      minWidth: 100,
      sortable: false,
      filterable: false,
      renderCell: (params) => {
        const moduleId = params.row.module_id || params.row.module?.id || params.row.id;
        return (
          <Button
            size="small"
            onClick={() => navigate(`/modules/${moduleId}`)}
            sx={{ color: theme.palette.success.main }}
          >
            View
          </Button>
        );
      },
    },
  ];

  // Filter out columns for mobile
  const displayColumns = isMobile ? columns.filter(c => !['owner'].includes(c.field)) : columns;

  return (
    <Container maxWidth="lg" sx={{ py: { xs: 2, sm: 4 } }}>
      {/* Header */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" sx={{ fontWeight: 700, mb: 2 }}>
          My Assets ({filteredAssets.length})
        </Typography>
        <Typography color="text.secondary">
          Browse and explore all assets in your scope. Click "View" for details.
        </Typography>
      </Box>

      {/* Filters */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Stack spacing={2} direction={{ xs: 'column', sm: 'row' }}>
          <TextField
            fullWidth
            size="small"
            placeholder="Search assets..."
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon />
                </InputAdornment>
              ),
            }}
          />
          <FormControl sx={{ minWidth: 200 }} size="small">
            <InputLabel>Domain</InputLabel>
            <Select value={selectedDomain} onChange={(e) => setSelectedDomain(e.target.value)} label="Domain">
              <MenuItem value="">All Domains</MenuItem>
              {domains.map(d => (
                <MenuItem key={d.id} value={String(d.id)}>
                  {d.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          {(searchText || selectedDomain) && (
            <Button
              variant="outlined"
              onClick={() => {
                setSearchText('');
                setSelectedDomain('');
              }}
            >
              Reset Filters
            </Button>
          )}
        </Stack>
      </Paper>

      {/* Results */}
      {filteredAssets.length === 0 ? (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <InfoIcon sx={{ fontSize: 48, color: '#ccc', mb: 2 }} />
          <Typography variant="h6" color="text.secondary">
            No assets found
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            {assets.length === 0
              ? 'No assets in your scope yet'
              : 'Try adjusting your search filters'}
          </Typography>
        </Paper>
      ) : (
        <Box sx={{ height: 'auto', width: '100%' }}>
          <DataGrid
            rows={filteredAssets}
            columns={displayColumns}
            paginationModel={paginationModel}
            onPaginationModelChange={setPaginationModel}
            pageSizeOptions={[10, 25, 50, 100]}
            disableSelectionOnClick
            density="compact"
            sx={{
              border: '1px solid #e5e7eb',
              borderRadius: 1,
              '& .MuiDataGrid-cell': {
                borderColor: '#e5e7eb',
              },
            }}
          />
        </Box>
      )}
    </Container>
  );
}
