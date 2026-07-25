// src/pages/carbon/MyDataPage.jsx
// Unified "My Data" page — compact, enterprise-grade, full-width
// Uses shared carbonDesign.js tokens for consistent typography, spacing, and components.

import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import { fetchOwnerSummary, fetchOwnerAssets } from '../../api/emissions';
import { isGlobalAdmin } from '../../utils/rbac';
import {
  Box,
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
  AddCircleOutline as DataEntryIcon,
  Storage as StorageIcon,
  FilterList as FilterIcon,
} from '@mui/icons-material';
import { DataGrid } from '@mui/x-data-grid';
import {
  PageWrapper,
  PageHeader,
  SectionHeader,
  StatCard,
  EmptyState,
  FONT,
  SPACING,
  BORDER,
  SCOPE_META,
  QUALITY_CONFIG,
} from '../../theme/carbonDesign.jsx';

// ── Quality Badge ───────────────────────────────────────────────────────────
function QualityBadge({ status, score, theme }) {
  const config = QUALITY_CONFIG[status] || QUALITY_CONFIG.unknown;
  const Icon = config.icon;
  const colorMain = config.color === 'default'
    ? theme.palette.text.secondary
    : theme.palette[config.color]?.main;
  const colorBg = config.color === 'default'
    ? theme.palette.action.disabledBackground
    : `${colorMain}18`;

  return (
    <Chip
      icon={<Icon sx={{ fontSize: 14 }} />}
      label={`${config.label}${score != null ? ` ${Math.round(score)}%` : ''}`}
      size="small"
      sx={{
        ...FONT.chip,
        height: 22,
        bgcolor: colorBg,
        color: colorMain,
        '& .MuiChip-icon': { ml: 0.5, mr: -0.25 },
      }}
    />
  );
}

// ── Module Card ─────────────────────────────────────────────────────────────
function ModuleCard({ module: mod, onEnter, theme }) {
  const scope = mod.scope || 1;
  const meta = SCOPE_META[scope] || SCOPE_META[1];
  const ScopeIcon = meta.icon;

  return (
    <Card
      variant="outlined"
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        cursor: 'pointer',
        borderLeft: `3px solid ${meta.color}`,
        borderRadius: BORDER.radius,
        transition: 'box-shadow 0.15s ease, border-color 0.15s ease',
        '&:hover': {
          borderColor: meta.color,
          boxShadow: '0 2px 12px rgba(0,0,0,0.08)',
        },
      }}
      onClick={onEnter}
    >
      <CardContent sx={{ flexGrow: 1, p: SPACING.md, pb: `${SPACING.sm}px !important` }}>
        <Stack direction="row" spacing={SPACING.sm} alignItems="flex-start">
          <Box
            sx={{
              bgcolor: `${meta.color}14`,
              borderRadius: 1,
              p: 0.75,
              display: 'flex',
              flexShrink: 0,
            }}
          >
            <ScopeIcon sx={{ fontSize: 20, color: meta.color }} />
          </Box>
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Typography sx={{ ...FONT.cardTitle, mb: 0.25 }}>
              {mod.name}
            </Typography>
            <Chip
              label={meta.label}
              size="small"
              sx={{
                ...FONT.chip,
                height: 18,
                bgcolor: meta.bg,
                color: meta.color,
              }}
            />
          </Box>
        </Stack>

        {mod.description && (
          <Typography sx={{ ...FONT.bodySmall, color: 'text.secondary', mt: SPACING.sm, mb: SPACING.sm }}>
            {mod.description}
          </Typography>
        )}

        <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap>
          <Chip
            icon={<StorageIcon sx={{ fontSize: 12 }} />}
            label={`${mod.tableCount || 0} ${(mod.tableCount || 0) === 1 ? 'table' : 'tables'}`}
            size="small"
            variant="outlined"
            sx={{ ...FONT.chip, height: 20 }}
          />
          {(mod.rowCount || 0) > 0 && (
            <Chip
              label={`${mod.rowCount} rows`}
              size="small"
              variant="outlined"
              sx={{ ...FONT.chip, height: 20 }}
            />
          )}
          <QualityBadge status={mod.qualityStatus} score={mod.qualityScore} theme={theme} />
        </Stack>
      </CardContent>
      <Divider />
      <CardActions sx={{ justifyContent: 'flex-end', px: SPACING.md, py: 0.75 }}>
        <Button size="small" sx={{ ...FONT.chip, color: meta.color, fontWeight: 600 }}>
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

  const [activeTab, setActiveTab] = useState(searchParams.get('tab') === 'sources' ? 1 : 0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [summary, setSummary] = useState(null);
  const [assets, setAssets] = useState([]);
  const [scopeFilter, setScopeFilter] = useState('all');
  const [moduleSearch, setModuleSearch] = useState('');
  const [assetSearch, setAssetSearch] = useState('');
  const [domainFilter, setDomainFilter] = useState('');
  const [qualityFilter, setQualityFilter] = useState('');
  const [paginationModel, setPaginationModel] = useState({ pageSize: 25, page: 0 });

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
        setError('load-failed');
        showNotification({ message: 'Failed to load data', type: 'error' });
      } finally {
        setLoading(false);
      }
    };
    if (token && context) loadData();
  }, [token, context, showNotification]);

  const enrichedModules = useMemo(() => {
    return modules.map(mod => {
      const modAssets = assets.filter(a => String(a.module_id || a.module?.id) === String(mod.id));
      const tableList = tablesByModule?.[String(mod.id)] || [];
      const totalRows = tableList.reduce((sum, t) => sum + (t.row_count || 0), 0);
      const scores = modAssets.map(a => a.quality_score).filter(s => s != null);
      const avgScore = scores.length > 0 ? scores.reduce((a, b) => a + b, 0) / scores.length : null;
      const statuses = modAssets.map(a => a.quality_status).filter(Boolean);
      let worstStatus = 'unknown';
      if (statuses.includes('failing')) worstStatus = 'failing';
      else if (statuses.includes('warning')) worstStatus = 'warning';
      else if (statuses.includes('passing')) worstStatus = 'passing';
      return { ...mod, tableCount: tableList.length, rowCount: totalRows, assetCount: modAssets.length, qualityScore: avgScore, qualityStatus: worstStatus };
    });
  }, [modules, assets, tablesByModule]);

  const scopeCounts = useMemo(() => {
    const c = { 1: 0, 2: 0, 3: 0 };
    enrichedModules.forEach(m => { const s = m.scope || 1; if (c[s] !== undefined) c[s]++; });
    return c;
  }, [enrichedModules]);

  const filteredModules = useMemo(() => {
    let r = enrichedModules;
    if (scopeFilter !== 'all') r = r.filter(m => String(m.scope || 1) === scopeFilter);
    if (moduleSearch) {
      const q = moduleSearch.toLowerCase();
      r = r.filter(m => (m.name && m.name.toLowerCase().includes(q)) || (m.description && m.description.toLowerCase().includes(q)));
    }
    return r;
  }, [enrichedModules, scopeFilter, moduleSearch]);

  const domains = useMemo(() => assets.reduce((acc, a) => {
    if (a.domain && !acc.some(d => d.id === a.domain.id)) acc.push({ id: a.domain.id, name: a.domain.name || 'Unassigned' });
    return acc;
  }, []), [assets]);

  const filteredAssets = useMemo(() => {
    let r = assets;
    if (domainFilter) r = r.filter(a => String(a.domain?.id) === domainFilter);
    if (qualityFilter) r = r.filter(a => a.quality_status === qualityFilter);
    if (assetSearch) {
      const q = assetSearch.toLowerCase();
      r = r.filter(a => (a.name && a.name.toLowerCase().includes(q)) || (a.description && a.description.toLowerCase().includes(q)) || (a.data_table?.name && a.data_table.name.toLowerCase().includes(q)));
    }
    return r;
  }, [assets, domainFilter, qualityFilter, assetSearch]);

  const handleTabChange = (_, v) => { setActiveTab(v); setSearchParams(v === 1 ? { tab: 'sources' } : {}); };

  if (loading) {
    return (
      <PageWrapper>
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh' }}>
          <CircularProgress size={32} />
        </Box>
      </PageWrapper>
    );
  }

  if (error === 'load-failed') {
    return (
      <PageWrapper>
        <Alert severity="error" action={<Button color="inherit" size="small" onClick={() => window.location.reload()}>Retry</Button>}>
          Failed to load your data.
        </Alert>
      </PageWrapper>
    );
  }

  if (!isDataOwner) {
    return (
      <PageWrapper>
        <EmptyState
          icon={StorageIcon}
          title="No Organizational Unit Assigned"
          description="You need to be assigned to an organizational unit to manage emission data. Contact your platform administrator."
        />
      </PageWrapper>
    );
  }

  const assetColumns = [
    {
      field: 'name', headerName: 'Asset', flex: 1.5, minWidth: 180,
      renderCell: (p) => (
        <Box>
          <Typography sx={{ ...FONT.bodySmall, fontWeight: 500 }}>{p.row.name}</Typography>
          <Typography sx={{ ...FONT.caption, color: 'text.secondary' }}>{p.row.data_table?.name || p.row.data_field?.name || '—'}</Typography>
        </Box>
      ),
    },
    {
      field: 'domain', headerName: 'Domain', flex: 0.8, minWidth: 110,
      renderCell: (p) => <Chip label={p.row.domain?.name || 'Unassigned'} size="small" variant="outlined" sx={{ ...FONT.chip, height: 20 }} />,
    },
    {
      field: 'quality_status', headerName: 'Quality', flex: 0.9, minWidth: 140,
      renderCell: (p) => <QualityBadge status={p.row.quality_status} score={p.row.quality_score} theme={theme} />,
    },
    {
      field: 'row_count', headerName: 'Rows', flex: 0.4, minWidth: 60,
      renderCell: (p) => <Typography sx={FONT.bodySmall}>{p.row.row_count ?? '—'}</Typography>,
    },
    {
      field: 'owner', headerName: 'Owner', flex: 0.7, minWidth: 90,
      renderCell: (p) => <Typography sx={FONT.caption}>{p.row.owner?.first_name || p.row.owner?.username || '—'}</Typography>,
    },
    {
      field: 'actions', headerName: '', flex: 0.5, minWidth: 90, sortable: false, filterable: false,
      renderCell: (p) => {
        const mid = p.row.module_id || p.row.module?.id;
        if (!mid) return null;
        return <Button size="small" variant="outlined" onClick={(e) => { e.stopPropagation(); navigate(`/modules/${mid}`); }} sx={{ ...FONT.chip, py: 0.25, minWidth: 'auto' }}>Enter Data</Button>;
      },
    },
  ];

  const displayColumns = isMobile ? assetColumns.filter(c => !['owner', 'row_count'].includes(c.field)) : assetColumns;

  return (
    <PageWrapper>
      <PageHeader
        title="My Data"
        subtitle="Manage your organizational unit's emission sources and activity data"
      />

      {/* Quick Stats */}
      {summary && (
        <Grid container spacing={SPACING.sm} sx={{ mb: SPACING.lg }}>
          <Grid item xs={6} sm={3}>
            <StatCard label="Emission Sources" value={enrichedModules.length} color={theme.palette.primary.main} icon={StorageIcon} />
          </Grid>
          <Grid item xs={6} sm={3}>
            <StatCard label="Data Tables" value={summary.total_tables || 0} color={theme.palette.success.main} icon={DataEntryIcon} />
          </Grid>
          <Grid item xs={6} sm={3}>
            <StatCard label="Data Quality" value={summary.avg_quality ? `${Math.round(summary.avg_quality)}%` : 'N/A'} color={theme.palette.warning.main} icon={QUALITY_CONFIG.passing.icon} />
          </Grid>
          <Grid item xs={6} sm={3}>
            <StatCard label="Total Assets" value={assets.length} color={theme.palette.info.main} icon={StorageIcon} />
          </Grid>
        </Grid>
      )}

      {/* Tabs */}
      <Tabs
        value={activeTab}
        onChange={handleTabChange}
        sx={{
          minHeight: 36,
          mb: SPACING.md,
          borderBottom: BORDER.light,
          borderColor: 'divider',
          '& .MuiTab-root': { minHeight: 36, py: 0.75, ...FONT.tab, textTransform: 'none' },
          '& .MuiTabs-indicator': { height: 2 },
        }}
      >
        <Tab icon={<DataEntryIcon sx={{ fontSize: 16 }} />} iconPosition="start" label={`Data Entry (${enrichedModules.length})`} />
        <Tab icon={<StorageIcon sx={{ fontSize: 16 }} />} iconPosition="start" label={`Emission Sources (${assets.length})`} />
      </Tabs>

      {/* Tab 1: Data Entry */}
      {activeTab === 0 && (
        <>
          {enrichedModules.length > 0 && (
            <Tabs
              value={scopeFilter}
              onChange={(_, v) => setScopeFilter(v)}
              sx={{
                minHeight: 32,
                mb: SPACING.md,
                '& .MuiTab-root': { minHeight: 32, py: 0.25, ...FONT.chip, textTransform: 'none' },
              }}
            >
              <Tab value="all" label={`All (${enrichedModules.length})`} />
              {scopeCounts[1] > 0 && <Tab value="1" label={<Stack direction="row" spacing={0.5} alignItems="center">{React.createElement(SCOPE_META[1].icon, { sx: { fontSize: 12, color: SCOPE_META[1].color } })}<span>Scope 1 ({scopeCounts[1]})</span></Stack>} />}
              {scopeCounts[2] > 0 && <Tab value="2" label={<Stack direction="row" spacing={0.5} alignItems="center">{React.createElement(SCOPE_META[2].icon, { sx: { fontSize: 12, color: SCOPE_META[2].color } })}<span>Scope 2 ({scopeCounts[2]})</span></Stack>} />}
              {scopeCounts[3] > 0 && <Tab value="3" label={<Stack direction="row" spacing={0.5} alignItems="center">{React.createElement(SCOPE_META[3].icon, { sx: { fontSize: 12, color: SCOPE_META[3].color } })}<span>Scope 3 ({scopeCounts[3]})</span></Stack>} />}
            </Tabs>
          )}

          <TextField
            fullWidth size="small" placeholder="Search emission sources..."
            value={moduleSearch} onChange={(e) => setModuleSearch(e.target.value)}
            sx={{ mb: SPACING.md }}
            InputProps={{ startAdornment: <InputAdornment position="start"><SearchIcon sx={{ fontSize: 16 }} /></InputAdornment>, sx: { ...FONT.bodySmall } }}
          />

          {filteredModules.length === 0 ? (
            <EmptyState
              icon={DataEntryIcon}
              title={enrichedModules.length === 0 ? 'No Emission Sources Assigned' : 'No sources match your filters'}
              description={enrichedModules.length === 0 ? 'Your administrator has not assigned any emission source modules to your organizational unit.' : 'Try adjusting your scope filter or search terms.'}
            />
          ) : (
            <Grid container spacing={SPACING.sm}>
              {filteredModules.map(mod => (
                <Grid item xs={12} sm={6} md={4} key={mod.id}>
                  <ModuleCard module={mod} theme={theme} onEnter={() => navigate(`/modules/${mod.id}`)} />
                </Grid>
              ))}
            </Grid>
          )}
        </>
      )}

      {/* Tab 2: Emission Sources */}
      {activeTab === 1 && (
        <>
          <Paper variant="outlined" sx={{ p: SPACING.md, mb: SPACING.md, borderRadius: BORDER.radius }}>
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={SPACING.sm} alignItems={{ sm: 'center' }}>
              <TextField size="small" placeholder="Search assets..." value={assetSearch} onChange={(e) => setAssetSearch(e.target.value)}
                sx={{ minWidth: 200 }} InputProps={{ startAdornment: <InputAdornment position="start"><SearchIcon sx={{ fontSize: 16 }} /></InputAdornment>, sx: { ...FONT.bodySmall } }} />
              <FormControl size="small" sx={{ minWidth: 140 }}>
                <InputLabel sx={FONT.bodySmall}>Domain</InputLabel>
                <Select value={domainFilter} onChange={(e) => setDomainFilter(e.target.value)} label="Domain" sx={FONT.bodySmall}>
                  <MenuItem value="" sx={FONT.bodySmall}>All Domains</MenuItem>
                  {domains.map(d => <MenuItem key={d.id} value={String(d.id)} sx={FONT.bodySmall}>{d.name}</MenuItem>)}
                </Select>
              </FormControl>
              <FormControl size="small" sx={{ minWidth: 120 }}>
                <InputLabel sx={FONT.bodySmall}>Quality</InputLabel>
                <Select value={qualityFilter} onChange={(e) => setQualityFilter(e.target.value)} label="Quality" sx={FONT.bodySmall}>
                  <MenuItem value="" sx={FONT.bodySmall}>All Statuses</MenuItem>
                  <MenuItem value="passing" sx={FONT.bodySmall}>Passing</MenuItem>
                  <MenuItem value="warning" sx={FONT.bodySmall}>Warning</MenuItem>
                  <MenuItem value="failing" sx={FONT.bodySmall}>Failing</MenuItem>
                </Select>
              </FormControl>
              {(assetSearch || domainFilter || qualityFilter) && (
                <Button variant="outlined" size="small" onClick={() => { setAssetSearch(''); setDomainFilter(''); setQualityFilter(''); }} startIcon={<FilterIcon sx={{ fontSize: 14 }} />} sx={{ ...FONT.chip }}>
                  Clear
                </Button>
              )}
            </Stack>
          </Paper>

          {filteredAssets.length === 0 ? (
            <EmptyState
              icon={StorageIcon}
              title={assets.length === 0 ? 'No Emission Source Assets' : 'No assets match your filters'}
              description={assets.length === 0 ? 'No emission source assets have been registered for your organizational unit.' : 'Try adjusting your search or filter criteria.'}
            />
          ) : (
            <Paper variant="outlined" sx={{ borderRadius: BORDER.radius, overflow: 'hidden' }}>
              <DataGrid
                rows={filteredAssets} columns={displayColumns}
                paginationModel={paginationModel} onPaginationModelChange={setPaginationModel}
                pageSizeOptions={[10, 25, 50, 100]} disableRowSelectionOnClick density="compact" autoHeight
                sx={{
                  border: 'none',
                  '& .MuiDataGrid-cell': { borderColor: 'divider', py: 0.75, ...FONT.bodySmall },
                  '& .MuiDataGrid-columnHeaders': { bgcolor: 'action.hover', ...FONT.chip, fontWeight: 600 },
                  '& .MuiDataGrid-row:hover': { bgcolor: 'action.hover' },
                  '& .MuiDataGrid-footerContainer': { ...FONT.chip },
                }}
              />
            </Paper>
          )}
        </>
      )}
    </PageWrapper>
  );
}
