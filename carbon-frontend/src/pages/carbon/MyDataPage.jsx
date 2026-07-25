// src/pages/carbon/MyDataPage.jsx
// Unified "My Data" page — merges Data Entry module browser + Emission Sources asset overview
// into a single cohesive experience for carbon data owners.
//
// Architecture:
//   Tab 1 "Data Entry"     → Module cards with quality scores, scope filters, drill-down to tables
//   Tab 2 "Emission Sources" → Asset DataGrid with quality badges, domain filters, direct entry actions
//
// Reuses: StatCard pattern (CarbonConsolePage), QualityStatusBadge (DataOwnerAssetsPage),
//         ScopeFilterTabs pattern (DataHubHome), WorkflowCard pattern (CarbonConsolePage)

import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import { fetchOwnerSummary, fetchOwnerAssets } from '../../api/emissions';
import { isGlobalAdmin } from '../../utils/rbac';
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
  Tabs,
  Tab,
  useTheme,
  useMediaQuery,
} from '@mui/material';
import {
  Search as SearchIcon,
  Info as InfoIcon,
  CheckCircle as PassIcon,
  Warning as WarningIcon,
  Error as FailIcon,
  AddCircleOutline as DataEntryIcon,
  Storage as StorageIcon,
  FilterList as FilterIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import {
  NatureRounded,
  BoltRounded,
  LocalShippingRounded,
} from '@mui/icons-material';
import { DataGrid } from '@mui/x-data-grid';

// ── Constants ──────────────────────────────────────────────────────────────

const SCOPE_META = {
  1: { bg: '#e8f5e9', color: '#2e7d32', label: 'Scope 1', icon: NatureRounded },
  2: { bg: '#e3f2fd', color: '#1565c0', label: 'Scope 2', icon: BoltRounded },
  3: { bg: '#fff3e0', color: '#e65100', label: 'Scope 3', icon: LocalShippingRounded },
};

const QUALITY_CONFIG = {
  passing: { bg: 'success', color: 'success.dark', icon: PassIcon, label: 'Passing' },
  warning: { bg: 'warning', color: 'warning.dark', icon: WarningIcon, label: 'Warning' },
  failing: { bg: 'error', color: 'error.dark', icon: FailIcon, label: 'Failing' },
  unknown: { bg: 'default', color: 'text.secondary', icon: InfoIcon, label: 'Unknown' },
};

// ── Sub-components ─────────────────────────────────────────────────────────

/** Color-coded quality status chip — reused from DataOwnerAssetsPage */
function QualityBadge({ status, score, theme }) {
  const config = QUALITY_CONFIG[status] || QUALITY_CONFIG.unknown;
  const Icon = config.icon;
  const bgColor = config.bg === 'default'
    ? theme.palette.action.disabledBackground
    : theme.palette[config.bg]?.[`${theme.palette.mode === 'dark' ? 'dark' : 'light'}`] || `${theme.palette[config.bg]?.main}20`;

  return (
    <Chip
      icon={<Icon sx={{ fontSize: 16 }} />}
      label={`${config.label}${score != null ? ` (${Math.round(score)}%)` : ''}`}
      size="small"
      sx={{
        backgroundColor: bgColor,
        color: config.color === 'text.secondary'
          ? theme.palette.text.secondary
          : theme.palette[config.bg]?.dark || theme.palette[config.bg]?.main,
        fontWeight: 500,
        fontSize: '0.75rem',
      }}
    />
  );
}

/** Quick stat card — reused pattern from CarbonConsolePage */
function StatCard({ label, value, color, icon: Icon }) {
  return (
    <Paper
      sx={{
        p: 2,
        textAlign: 'center',
        bgcolor: `${color}10`,
        borderLeft: `4px solid ${color}`,
        height: '100%',
      }}
    >
      <Stack direction="row" spacing={1} alignItems="center" justifyContent="center" sx={{ mb: 0.5 }}>
        <Icon sx={{ fontSize: 20, color }} />
        <Typography variant="h5" sx={{ fontWeight: 600, color }}>
          {value}
        </Typography>
      </Stack>
      <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 500 }}>
        {label}
      </Typography>
    </Paper>
  );
}

/** Enhanced module card for the Data Entry tab */
function ModuleCard({ module, onEnter, theme }) {
  const scope = module.scope || 1;
  const meta = SCOPE_META[scope] || SCOPE_META[1];
  const ScopeIcon = meta.icon;
  const tableCount = module.tableCount || 0;
  const rowCount = module.rowCount || 0;
  const qualityStatus = module.qualityStatus || 'unknown';
  const qualityScore = module.qualityScore;

  return (
    <Card
      variant="outlined"
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        transition: 'all 0.2s ease',
        cursor: 'pointer',
        borderTop: `4px solid ${meta.color}`,
        '&:hover': {
          boxShadow: '0 8px 24px rgba(0, 0, 0, 0.12)',
          transform: 'translateY(-2px)',
          borderColor: meta.color,
        },
      }}
      onClick={onEnter}
    >
      <CardContent sx={{ flexGrow: 1, pb: 1 }}>
        {/* Header row: scope icon + name + scope chip */}
        <Stack direction="row" spacing={1.5} alignItems="flex-start" sx={{ mb: 1.5 }}>
          <Box
            sx={{
              bgcolor: `${meta.color}15`,
              borderRadius: 1.5,
              p: 1,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
            }}
          >
            <ScopeIcon sx={{ fontSize: 24, color: meta.color }} />
          </Box>
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 600, lineHeight: 1.3 }}>
              {module.name}
            </Typography>
            <Chip
              label={meta.label}
              size="small"
              sx={{
                mt: 0.5,
                height: 20,
                fontSize: '0.65rem',
                fontWeight: 600,
                bgcolor: meta.bg,
                color: meta.color,
              }}
            />
          </Box>
        </Stack>

        {/* Description */}
        <Typography
          variant="body2"
          color="text.secondary"
          sx={{ mb: 1.5, lineHeight: 1.5, minHeight: 40 }}
        >
          {module.description || 'No description available'}
        </Typography>

        {/* Stats row */}
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
          <Chip
            icon={<StorageIcon sx={{ fontSize: 14 }} />}
            label={`${tableCount} ${tableCount === 1 ? 'table' : 'tables'}`}
            size="small"
            variant="outlined"
            sx={{ fontSize: '0.7rem' }}
          />
          {rowCount > 0 && (
            <Chip
              label={`${rowCount} rows`}
              size="small"
              variant="outlined"
              sx={{ fontSize: '0.7rem' }}
            />
          )}
          <QualityBadge status={qualityStatus} score={qualityScore} theme={theme} />
        </Stack>
      </CardContent>

      <Divider />
      <CardActions sx={{ justifyContent: 'flex-end', px: 2, py: 1 }}>
        <Button
          size="small"
          sx={{ color: meta.color, fontWeight: 600, fontSize: '0.75rem' }}
        >
          Enter Data →
        </Button>
      </CardActions>
    </Card>
  );
}

// ── Main Page ───────────────────────────────────────────────────────────────

export default function MyDataPage() {
  const navigate = useNavigate();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const { user, context, tablesByModule, token, availablePerspectives } = useAuth();
  const { showNotification } = useNotification();
  const [searchParams, setSearchParams] = useSearchParams();

  // ── State ──
  const [activeTab, setActiveTab] = useState(searchParams.get('tab') === 'sources' ? 1 : 0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [summary, setSummary] = useState(null);
  const [assets, setAssets] = useState([]);

  // Data Entry tab filters
  const [scopeFilter, setScopeFilter] = useState('all');
  const [moduleSearch, setModuleSearch] = useState('');

  // Emission Sources tab filters
  const [assetSearch, setAssetSearch] = useState('');
  const [domainFilter, setDomainFilter] = useState('');
  const [qualityFilter, setQualityFilter] = useState('');
  const [paginationModel, setPaginationModel] = useState({ pageSize: 25, page: 0 });

  // ── Data Loading ──
  const modules = context?.modules || [];
  const userIsGlobalAdmin = isGlobalAdmin(user, availablePerspectives);
  const isDataOwner = userIsGlobalAdmin || (context?.org_units && context.org_units.length > 0);

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        const [summaryRes, assetsRes] = await Promise.all([
          fetchOwnerSummary(token).catch(() => null),
          fetchOwnerAssets({}, token).catch(() => []),
        ]);
        setSummary(summaryRes);
        setAssets(Array.isArray(assetsRes) ? assetsRes : []);
        setError(null);
      } catch (err) {
        console.error('Error loading My Data:', err);
        setError('load-failed');
        showNotification({ message: 'Failed to load data', type: 'error' });
      } finally {
        setLoading(false);
      }
    };

    if (token && context) {
      loadData();
    }
  }, [token, context, showNotification]);

  // ── Derived Data ──

  // Enrich modules with asset quality data
  const enrichedModules = useMemo(() => {
    return modules.map(mod => {
      const modAssets = assets.filter(a =>
        String(a.module_id || a.module?.id) === String(mod.id)
      );
      const tableList = tablesByModule?.[String(mod.id)] || [];
      const totalRows = tableList.reduce((sum, t) => sum + (t.row_count || 0), 0);

      // Compute aggregate quality from module's assets
      const scores = modAssets.map(a => a.quality_score).filter(s => s != null);
      const avgScore = scores.length > 0 ? scores.reduce((a, b) => a + b, 0) / scores.length : null;

      // Determine worst status among assets
      const statuses = modAssets.map(a => a.quality_status).filter(Boolean);
      let worstStatus = 'unknown';
      if (statuses.includes('failing')) worstStatus = 'failing';
      else if (statuses.includes('warning')) worstStatus = 'warning';
      else if (statuses.includes('passing')) worstStatus = 'passing';

      return {
        ...mod,
        tableCount: tableList.length,
        rowCount: totalRows,
        assetCount: modAssets.length,
        qualityScore: avgScore,
        qualityStatus: worstStatus,
      };
    });
  }, [modules, assets, tablesByModule]);

  // Scope counts for filter tabs
  const scopeCounts = useMemo(() => {
    const counts = { 1: 0, 2: 0, 3: 0 };
    enrichedModules.forEach(m => {
      const s = m.scope || 1;
      if (counts[s] !== undefined) counts[s]++;
    });
    return counts;
  }, [enrichedModules]);

  // Filtered modules for Data Entry tab
  const filteredModules = useMemo(() => {
    let result = enrichedModules;
    if (scopeFilter !== 'all') {
      result = result.filter(m => String(m.scope || 1) === scopeFilter);
    }
    if (moduleSearch) {
      const q = moduleSearch.toLowerCase();
      result = result.filter(m =>
        (m.name && m.name.toLowerCase().includes(q)) ||
        (m.description && m.description.toLowerCase().includes(q))
      );
    }
    return result;
  }, [enrichedModules, scopeFilter, moduleSearch]);

  // Domain list for filter dropdown
  const domains = useMemo(() => {
    return assets.reduce((acc, asset) => {
      const domain = asset.domain;
      if (domain && !acc.some(d => d.id === domain.id)) {
        acc.push({ id: domain.id, name: domain.name || 'Unassigned' });
      }
      return acc;
    }, []);
  }, [assets]);

  // Filtered assets for Emission Sources tab
  const filteredAssets = useMemo(() => {
    let result = assets;
    if (domainFilter) {
      result = result.filter(a => String(a.domain?.id) === domainFilter);
    }
    if (qualityFilter) {
      result = result.filter(a => a.quality_status === qualityFilter);
    }
    if (assetSearch) {
      const q = assetSearch.toLowerCase();
      result = result.filter(a =>
        (a.name && a.name.toLowerCase().includes(q)) ||
        (a.description && a.description.toLowerCase().includes(q)) ||
        (a.data_table?.name && a.data_table.name.toLowerCase().includes(q))
      );
    }
    return result;
  }, [assets, domainFilter, qualityFilter, assetSearch]);

  // ── Tab Sync ──
  const handleTabChange = (_, newValue) => {
    setActiveTab(newValue);
    setSearchParams(newValue === 1 ? { tab: 'sources' } : {});
  };

  // ── Loading State ──
  if (loading) {
    return (
      <Container maxWidth="xl" sx={{ py: 4 }}>
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh' }}>
          <CircularProgress />
        </Box>
      </Container>
    );
  }

  // ── Error State ──
  if (error === 'load-failed') {
    return (
      <Container maxWidth="xl" sx={{ py: 4 }}>
        <Alert
          severity="error"
          action={
            <Button color="inherit" size="small" onClick={() => window.location.reload()}>
              Retry
            </Button>
          }
        >
          Failed to load your data. Please try again.
        </Alert>
      </Container>
    );
  }

  // ── No Scope State ──
  if (!isDataOwner) {
    return (
      <Container maxWidth="xl" sx={{ py: 4 }}>
        <Paper sx={{ p: 6, textAlign: 'center' }}>
          <StorageIcon sx={{ fontSize: 64, color: 'text.disabled', mb: 2 }} />
          <Typography variant="h5" sx={{ fontWeight: 600, mb: 1 }}>
            No Organizational Unit Assigned
          </Typography>
          <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
            You need to be assigned to an organizational unit to manage emission data.
            Contact your platform administrator to get set up.
          </Typography>
        </Paper>
      </Container>
    );
  }

  // ── DataGrid Columns (Emission Sources tab) ──
  const assetColumns = [
    {
      field: 'name',
      headerName: 'Asset',
      flex: 1.5,
      minWidth: 180,
      renderCell: (params) => (
        <Box>
          <Typography variant="body2" sx={{ fontWeight: 500 }}>
            {params.row.name}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {params.row.data_table?.name || params.row.data_field?.name || '—'}
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
        <Chip
          label={params.row.domain?.name || 'Unassigned'}
          size="small"
          variant="outlined"
          sx={{ fontSize: '0.7rem' }}
        />
      ),
    },
    {
      field: 'quality_status',
      headerName: 'Quality',
      flex: 0.9,
      minWidth: 150,
      renderCell: (params) => (
        <QualityBadge
          status={params.row.quality_status}
          score={params.row.quality_score}
          theme={theme}
        />
      ),
    },
    {
      field: 'row_count',
      headerName: 'Rows',
      flex: 0.4,
      minWidth: 70,
      renderCell: (params) => (
        <Typography variant="body2">{params.row.row_count ?? '—'}</Typography>
      ),
    },
    {
      field: 'owner',
      headerName: 'Owner',
      flex: 0.7,
      minWidth: 100,
      renderCell: (params) => (
        <Typography variant="caption">
          {params.row.owner?.first_name || params.row.owner?.username || '—'}
        </Typography>
      ),
    },
    {
      field: 'actions',
      headerName: '',
      flex: 0.5,
      minWidth: 100,
      sortable: false,
      filterable: false,
      renderCell: (params) => {
        const moduleId = params.row.module_id || params.row.module?.id;
        if (!moduleId) return null;
        return (
          <Button
            size="small"
            variant="outlined"
            onClick={(e) => {
              e.stopPropagation();
              navigate(`/modules/${moduleId}`);
            }}
            sx={{
              fontSize: '0.7rem',
              py: 0.25,
              minWidth: 'auto',
            }}
          >
            Enter Data
          </Button>
        );
      },
    },
  ];

  const displayColumns = isMobile
    ? assetColumns.filter(c => !['owner', 'row_count'].includes(c.field))
    : assetColumns;

  // ── Render ──
  return (
    <Container maxWidth="xl" sx={{ py: { xs: 2, sm: 3 } }}>
      {/* ── Header ── */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" sx={{ fontWeight: 700, mb: 0.5 }}>
          My Data
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Manage your organizational unit's emission sources and activity data
        </Typography>
      </Box>

      {/* ── Quick Stats ── */}
      {summary && (
        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid item xs={6} sm={3}>
            <StatCard
              label="Emission Sources"
              value={enrichedModules.length}
              color={theme.palette.primary.main}
              icon={StorageIcon}
            />
          </Grid>
          <Grid item xs={6} sm={3}>
            <StatCard
              label="Data Tables"
              value={summary.total_tables || 0}
              color={theme.palette.success.main}
              icon={DataEntryIcon}
            />
          </Grid>
          <Grid item xs={6} sm={3}>
            <StatCard
              label="Data Quality"
              value={summary.avg_quality ? `${Math.round(summary.avg_quality)}%` : 'N/A'}
              color={theme.palette.warning.main}
              icon={PassIcon}
            />
          </Grid>
          <Grid item xs={6} sm={3}>
            <StatCard
              label="Total Assets"
              value={assets.length}
              color={theme.palette.info.main}
              icon={InfoIcon}
            />
          </Grid>
        </Grid>
      )}

      {/* ── Tabs ── */}
      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 3 }}>
        <Tabs
          value={activeTab}
          onChange={handleTabChange}
          sx={{
            minHeight: 44,
            '& .MuiTab-root': {
              minHeight: 44,
              py: 1,
              textTransform: 'none',
              fontWeight: 600,
              fontSize: '0.875rem',
            },
          }}
        >
          <Tab
            icon={<DataEntryIcon sx={{ fontSize: 20 }} />}
            iconPosition="start"
            label={`Data Entry (${enrichedModules.length})`}
          />
          <Tab
            icon={<StorageIcon sx={{ fontSize: 20 }} />}
            iconPosition="start"
            label={`Emission Sources (${assets.length})`}
          />
        </Tabs>
      </Box>

      {/* ── Tab 1: Data Entry ── */}
      {activeTab === 0 && (
        <>
          {/* Scope filter tabs */}
          {enrichedModules.length > 0 && (
            <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
              <Tabs
                value={scopeFilter}
                onChange={(_, val) => setScopeFilter(val)}
                sx={{
                  minHeight: 36,
                  '& .MuiTab-root': {
                    minHeight: 36,
                    py: 0.5,
                    textTransform: 'none',
                    fontWeight: 500,
                    fontSize: '0.75rem',
                  },
                }}
              >
                <Tab value="all" label={`All (${enrichedModules.length})`} />
                {scopeCounts[1] > 0 && (
                  <Tab
                    value="1"
                    label={
                      <Stack direction="row" spacing={0.5} alignItems="center">
                        <NatureRounded sx={{ fontSize: 14, color: SCOPE_META[1].color }} />
                        <span>Scope 1 ({scopeCounts[1]})</span>
                      </Stack>
                    }
                  />
                )}
                {scopeCounts[2] > 0 && (
                  <Tab
                    value="2"
                    label={
                      <Stack direction="row" spacing={0.5} alignItems="center">
                        <BoltRounded sx={{ fontSize: 14, color: SCOPE_META[2].color }} />
                        <span>Scope 2 ({scopeCounts[2]})</span>
                      </Stack>
                    }
                  />
                )}
                {scopeCounts[3] > 0 && (
                  <Tab
                    value="3"
                    label={
                      <Stack direction="row" spacing={0.5} alignItems="center">
                        <LocalShippingRounded sx={{ fontSize: 14, color: SCOPE_META[3].color }} />
                        <span>Scope 3 ({scopeCounts[3]})</span>
                      </Stack>
                    }
                  />
                )}
              </Tabs>
            </Box>
          )}

          {/* Search */}
          <TextField
            fullWidth
            size="small"
            placeholder="Search emission sources..."
            value={moduleSearch}
            onChange={(e) => setModuleSearch(e.target.value)}
            sx={{ mb: 2 }}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon fontSize="small" />
                </InputAdornment>
              ),
            }}
          />

          {/* Module Cards Grid */}
          {filteredModules.length === 0 ? (
            <Paper sx={{ p: 6, textAlign: 'center' }}>
              <DataEntryIcon sx={{ fontSize: 48, color: 'text.disabled', mb: 2 }} />
              <Typography variant="h6" color="text.secondary" sx={{ mb: 1 }}>
                {enrichedModules.length === 0
                  ? 'No Emission Sources Assigned'
                  : 'No sources match your filters'}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {enrichedModules.length === 0
                  ? 'Your administrator has not assigned any emission source modules to your organizational unit.'
                  : 'Try adjusting your scope filter or search terms.'}
              </Typography>
            </Paper>
          ) : (
            <Grid container spacing={2}>
              {filteredModules.map((mod) => (
                <Grid item xs={12} sm={6} md={4} key={mod.id}>
                  <ModuleCard
                    module={mod}
                    theme={theme}
                    onEnter={() => navigate(`/modules/${mod.id}`)}
                  />
                </Grid>
              ))}
            </Grid>
          )}
        </>
      )}

      {/* ── Tab 2: Emission Sources ── */}
      {activeTab === 1 && (
        <>
          {/* Filters */}
          <Paper sx={{ p: 2, mb: 2 }}>
            <Stack
              direction={{ xs: 'column', sm: 'row' }}
              spacing={2}
              alignItems={{ sm: 'center' }}
            >
              <TextField
                size="small"
                placeholder="Search assets..."
                value={assetSearch}
                onChange={(e) => setAssetSearch(e.target.value)}
                sx={{ minWidth: 220 }}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchIcon fontSize="small" />
                    </InputAdornment>
                  ),
                }}
              />
              <FormControl size="small" sx={{ minWidth: 160 }}>
                <InputLabel>Domain</InputLabel>
                <Select
                  value={domainFilter}
                  onChange={(e) => setDomainFilter(e.target.value)}
                  label="Domain"
                >
                  <MenuItem value="">All Domains</MenuItem>
                  {domains.map(d => (
                    <MenuItem key={d.id} value={String(d.id)}>{d.name}</MenuItem>
                  ))}
                </Select>
              </FormControl>
              <FormControl size="small" sx={{ minWidth: 140 }}>
                <InputLabel>Quality</InputLabel>
                <Select
                  value={qualityFilter}
                  onChange={(e) => setQualityFilter(e.target.value)}
                  label="Quality"
                >
                  <MenuItem value="">All Statuses</MenuItem>
                  <MenuItem value="passing">Passing</MenuItem>
                  <MenuItem value="warning">Warning</MenuItem>
                  <MenuItem value="failing">Failing</MenuItem>
                </Select>
              </FormControl>
              {(assetSearch || domainFilter || qualityFilter) && (
                <Button
                  variant="outlined"
                  size="small"
                  onClick={() => {
                    setAssetSearch('');
                    setDomainFilter('');
                    setQualityFilter('');
                  }}
                  startIcon={<FilterIcon />}
                >
                  Clear Filters
                </Button>
              )}
            </Stack>
          </Paper>

          {/* DataGrid */}
          {filteredAssets.length === 0 ? (
            <Paper sx={{ p: 6, textAlign: 'center' }}>
              <StorageIcon sx={{ fontSize: 48, color: 'text.disabled', mb: 2 }} />
              <Typography variant="h6" color="text.secondary" sx={{ mb: 1 }}>
                {assets.length === 0
                  ? 'No Emission Source Assets'
                  : 'No assets match your filters'}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {assets.length === 0
                  ? 'No emission source assets have been registered for your organizational unit.'
                  : 'Try adjusting your search or filter criteria.'}
              </Typography>
            </Paper>
          ) : (
            <Paper sx={{ width: '100%', overflow: 'hidden' }}>
              <DataGrid
                rows={filteredAssets}
                columns={displayColumns}
                paginationModel={paginationModel}
                onPaginationModelChange={setPaginationModel}
                pageSizeOptions={[10, 25, 50, 100]}
                disableRowSelectionOnClick
                density="compact"
                autoHeight
                sx={{
                  border: 'none',
                  '& .MuiDataGrid-cell': {
                    borderColor: theme.palette.divider,
                    py: 1,
                  },
                  '& .MuiDataGrid-columnHeaders': {
                    bgcolor: theme.palette.action.hover,
                    borderBottom: `2px solid ${theme.palette.divider}`,
                  },
                  '& .MuiDataGrid-row:hover': {
                    bgcolor: theme.palette.action.hover,
                  },
                }}
              />
            </Paper>
          )}
        </>
      )}
    </Container>
  );
}
