// src/pages/carbon/MyDataPage.jsx
// My Data – Level 1 data owner workspace.
// Pattern: EntityDetailShell (main grid + resizable right panel)
//   – Grid: FilteredDataGrid-style with search, scope + status filters
//   – Row click: highlights row, populates right panel (tabs: Overview, Tables, Activity)
//   – Row actions: View (→ module workspace), Edit, Delete
//   – All colours via theme.palette, zero hardcoded hex

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Alert,
  Box,
  Chip,
  Divider,
  FormControl,
  IconButton,
  InputAdornment,
  InputLabel,
  LinearProgress,
  MenuItem,
  Select,
  Snackbar,
  Stack,
  Tab,
  Tabs,
  TextField,
  Tooltip,
  Typography,
  useTheme,
} from '@mui/material';
import { DataGrid } from '@mui/x-data-grid';
import BoltRoundedIcon from '@mui/icons-material/BoltRounded';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';
import LocalShippingRoundedIcon from '@mui/icons-material/LocalShippingRounded';
import NatureRoundedIcon from '@mui/icons-material/NatureRounded';
import RefreshIcon from '@mui/icons-material/Refresh';
import SearchIcon from '@mui/icons-material/Search';
import VisibilityIcon from '@mui/icons-material/Visibility';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import { useAuth } from '../../auth/AuthContext';
import { fetchMyData, fetchOwnerActivity } from '../../api/emissions';
import EntityDetailShell from '../../components/entity/EntityDetailShell';
import { EmptyState, ErrorAlert, LoadingSkeleton, PageHeader, StatCard } from '../../components';

// ── Scope config uses MUI palette colour names ─────────────────────────────

const SCOPE_CFG = {
  1: { label: 'Scope 1', palette: 'success',  Icon: NatureRoundedIcon },
  2: { label: 'Scope 2', palette: 'info',     Icon: BoltRoundedIcon },
  3: { label: 'Scope 3', palette: 'warning',  Icon: LocalShippingRoundedIcon },
};

const STATUS_CFG = {
  passing: { label: 'Passing', palette: 'success', Icon: CheckCircleOutlineIcon },
  warning: { label: 'Warning', palette: 'warning', Icon: WarningAmberIcon },
  failing: { label: 'Failing', palette: 'error',   Icon: ErrorOutlineIcon },
  no_data: { label: 'No Data', palette: null,      Icon: HelpOutlineIcon },
};

function getStatus(mod) {
  if (!mod?.row_count) return 'no_data';
  if (mod.quality_score != null && mod.quality_score < 60) return 'failing';
  if (mod.quality_score != null && mod.quality_score < 80) return 'warning';
  return 'passing';
}

function fmtDate(v) {
  if (!v) return 'Never';
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? 'Never' : d.toLocaleDateString();
}

// ── Reusable chip helpers ──────────────────────────────────────────────────

function ScopeChip({ value }) {
  const theme = useTheme();
  const cfg = SCOPE_CFG[value] || SCOPE_CFG[1];
  const p = theme.palette[cfg.palette];
  return (
    <Chip
      label={cfg.label}
      size="small"
      sx={{
        height: 20,
        fontSize: '0.68rem',
        fontWeight: 700,
        bgcolor: p?.['50'] || p?.light + '30',
        color: p?.dark || p?.main,
        border: 'none',
        '& .MuiChip-label': { px: 1 },
      }}
    />
  );
}

function StatusChip({ row }) {
  const status = getStatus(row);
  const cfg = STATUS_CFG[status];
  const Icon = cfg.Icon;
  return (
    <Chip
      icon={<Icon sx={{ fontSize: '13px !important' }} />}
      label={cfg.label}
      size="small"
      color={cfg.palette || 'default'}
      variant="outlined"
      sx={{ height: 20, fontSize: '0.68rem', '& .MuiChip-label': { px: 0.5 }, '& .MuiChip-icon': { ml: '4px' } }}
    />
  );
}

// ── Right panel: selected module detail ────────────────────────────────────

function SourceOverviewTab({ mod, theme }) {
  if (!mod) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography variant="body2" color="text.secondary">
          Select a source to see source metadata and row entry history.
        </Typography>
      </Box>
    );
  }

  const dqPct = mod.quality_score ?? 0;

  const details = [
    { label: 'Source Name', value: mod.name },
    { label: 'Source ID', value: mod.id },
    { label: 'Scope', value: <ScopeChip value={mod.scope} /> },
    { label: 'Tables', value: mod.table_count ?? 0 },
    { label: 'Rows', value: mod.row_count ?? 0 },
    { label: 'Last entry', value: fmtDate(mod.last_entry) },
    { label: 'Status', value: <StatusChip row={mod} /> },
    { label: 'Data quality', value: mod.quality_score != null ? `${Math.round(mod.quality_score)}%` : 'Not available' },
  ];

  return (
    <Box sx={{ p: 1.5, display: 'flex', flexDirection: 'column', gap: 1.5, fontSize: '0.75rem' }}>
      <Typography variant="body2" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.08em', fontSize: '0.68rem' }}>
        Overview
      </Typography>

      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr', gap: 1.25 }}>
        {details.map(({ label, value }) => (
          <Box
            key={label}
            sx={{
              display: 'grid',
              gridTemplateColumns: '140px 1fr',
              gap: 1,
              py: 1,
              borderBottom: `1px solid ${theme.palette.divider}`,
            }}
          >
            <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.68rem' }}>
              {label}
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
              {typeof value === 'string' || typeof value === 'number' ? (
                <Typography component="span" variant="body2" sx={{ fontWeight: 600, color: 'text.primary', fontSize: '0.8rem' }}>
                  {value}
                </Typography>
              ) : (
                value
              )}
            </Box>
          </Box>
        ))}
      </Box>

      <Box sx={{ pt: 1 }}>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1, fontWeight: 700, fontSize: '0.76rem' }}>
          Data trust context
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.72rem' }}>
          Detailed rules, lineage, and governance are typically managed at the table or asset level. This page focuses on source selection and row entry operations.
        </Typography>
      </Box>

      <Box sx={{ pt: 1 }}>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1, fontWeight: 700, fontSize: '0.76rem' }}>
          Quality summary
        </Typography>
        <Typography variant="body2" sx={{ fontWeight: 600, color: dqPct >= 80 ? 'success.main' : dqPct >= 60 ? 'warning.main' : 'error.main', fontSize: '0.8rem' }}>
          {mod.quality_score != null ? `${Math.round(dqPct)}%` : 'No score available'}
        </Typography>
      </Box>
    </Box>
  );
}

function StatsTab({ stats, modules, theme }) {
  const dqScore = useMemo(() => {
    const q = stats?.data_quality || {};
    if (!q.total_assets) return 'N/A';
    return `${Math.round((q.passing / q.total_assets) * 100)}%`;
  }, [stats]);

  const scopeCounts = useMemo(() => {
    const c = { 1: 0, 2: 0, 3: 0 };
    modules.forEach((m) => { if (c[m.scope] !== undefined) c[m.scope]++; });
    return c;
  }, [modules]);

  return (
    <Box sx={{ p: 1.5, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1 }}>
        <StatCard title="Sources"   value={stats?.total_modules ?? 0}    color="primary" />
        <StatCard title="With Data" value={stats?.modules_with_data ?? 0} color="success" />
        <StatCard title="Total Rows" value={stats?.total_rows ?? 0}       color="info" />
        <StatCard title="DQ Score"  value={dqScore}                       color="warning" />
      </Box>

      <Divider />
      <Typography sx={{ fontSize: '0.68rem', fontWeight: 700, textTransform: 'uppercase', color: 'text.secondary', letterSpacing: '0.05em' }}>
        By Scope
      </Typography>
      {[1, 2, 3].map((s) => {
        const cfg = SCOPE_CFG[s];
        const p = theme.palette[cfg.palette];
        return (
          <Stack key={s} direction="row" alignItems="center" spacing={1}>
            <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: p?.main, flexShrink: 0 }} />
            <Typography sx={{ fontSize: '0.72rem', flex: 1, color: 'text.secondary' }}>{cfg.label}</Typography>
            <Typography sx={{ fontSize: '0.72rem', fontWeight: 700 }}>{scopeCounts[s]}</Typography>
          </Stack>
        );
      })}
    </Box>
  );
}

function ActivityTab({ activity }) {
  if (!activity?.length) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography sx={{ fontSize: '0.72rem', color: 'text.secondary' }}>No recent activity.</Typography>
      </Box>
    );
  }
  return (
    <Box sx={{ p: 1.5 }}>
      <Stack divider={<Divider flexItem />} spacing={0}>
        {activity.map((item, i) => (
          <Box key={item.id ?? i} sx={{ py: 1 }}>
            <Typography sx={{ fontSize: '0.72rem' }}>{item.detail || item.message || 'Updated'}</Typography>
            <Typography sx={{ fontSize: '0.62rem', color: 'text.disabled', mt: 0.25 }}>
              {fmtDate(item.timestamp || item.created_at)}
            </Typography>
          </Box>
        ))}
      </Stack>
    </Box>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────

export default function MyDataPage() {
  const navigate = useNavigate();
  const theme = useTheme();
  const { token } = useAuth();

  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState(null);
  const [data, setData]             = useState(null);
  const [activity, setActivity]     = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [searchText, setSearchText] = useState('');
  const [scopeFilter, setScopeFilter]   = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [snackbar, setSnackbar]     = useState(null);

  const modules  = useMemo(() => data?.modules  || [], [data]);
  const orgUnit  = data?.org_unit;
  const selected = useMemo(() => modules.find((m) => m.id === selectedId) || null, [modules, selectedId]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [res, act] = await Promise.all([
        fetchMyData(token),
        fetchOwnerActivity({ limit: 15 }, token).catch(() => []),
      ]);
      setData(res);
      setActivity(Array.isArray(act) ? act : []);
    } catch (err) {
      setError(err.message || 'Failed to load My Data');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { if (token) load(); }, [load, token]);

  // Client-side filter
  const filtered = useMemo(() => {
    let rows = modules;
    if (scopeFilter !== 'all')  rows = rows.filter((m) => m.scope === Number(scopeFilter));
    if (statusFilter !== 'all') rows = rows.filter((m) => getStatus(m) === statusFilter);
    if (searchText) {
      const q = searchText.toLowerCase();
      rows = rows.filter((m) => (m.name || '').toLowerCase().includes(q));
    }
    return rows;
  }, [modules, scopeFilter, statusFilter, searchText]);

  // Grid columns
  const columns = useMemo(() => [
    {
      field: 'scope',
      headerName: 'Scope',
      width: 105,
      renderCell: ({ value }) => <ScopeChip value={value} />,
    },
    {
      field: 'name',
      headerName: 'Source Name',
      flex: 2,
      minWidth: 180,
      renderCell: ({ value }) => (
        <Typography sx={{ fontSize: '0.8125rem', fontWeight: 600 }}>{value}</Typography>
      ),
    },
    {
      field: 'table_count',
      headerName: 'Tables',
      width: 75,
      type: 'number',
      renderCell: ({ value }) => <Typography sx={{ fontSize: '0.8125rem' }}>{value ?? 0}</Typography>,
    },
    {
      field: 'row_count',
      headerName: 'Rows',
      width: 75,
      type: 'number',
      renderCell: ({ value }) => <Typography sx={{ fontSize: '0.8125rem' }}>{value ?? 0}</Typography>,
    },
    {
      field: 'status',
      headerName: 'Status',
      width: 115,
      valueGetter: (valueOrParams, row) => {
        const currentRow = row ?? valueOrParams?.row ?? valueOrParams;
        return getStatus(currentRow);
      },
      renderCell: (params) => <StatusChip row={params?.row ?? params} />,
    },
    {
      field: 'quality_score',
      headerName: 'DQ%',
      width: 68,
      renderCell: ({ value }) => (
        <Typography
          sx={{
            fontSize: '0.8125rem',
            fontWeight: 600,
            color: value == null
              ? 'text.disabled'
              : value >= 80 ? 'success.dark' : value >= 60 ? 'warning.dark' : 'error.dark',
          }}
        >
          {value != null ? `${Math.round(value)}%` : '—'}
        </Typography>
      ),
    },
    {
      field: 'last_entry',
      headerName: 'Last Entry',
      width: 110,
      renderCell: ({ value }) => (
        <Typography sx={{ fontSize: '0.8125rem', color: 'text.secondary' }}>{fmtDate(value)}</Typography>
      ),
    },
    {
      field: 'actions',
      headerName: '',
      width: 90,
      sortable: false,
      disableColumnMenu: true,
      renderCell: ({ row }) => (
        <Stack direction="row" spacing={0.25} onClick={(e) => e.stopPropagation()}>
          <Tooltip title="Open workspace">
            <IconButton size="small" onClick={() => navigate(`/carbon/my-data/${row.id}`)}>
              <VisibilityIcon sx={{ fontSize: 15 }} />
            </IconButton>
          </Tooltip>
        </Stack>
      ),
    },
  ], [navigate]);

  const breadcrumbs = [
    { label: 'Home',    path: '/dashboard' },
    { label: 'My Data' },
  ];

  const rightPanelTabs = [
    { label: 'Overview', render: () => <SourceOverviewTab mod={selected} theme={theme} /> },
    { label: 'Activity', render: () => <ActivityTab activity={activity} /> },
  ];

  const [activePanelTab, setActivePanelTab] = useState(0);

  const rightPanel = (
    <Box sx={{ height: '100%', overflow: 'auto' }}>
      <Box sx={{ borderBottom: 1, borderColor: 'divider', bgcolor: 'white' }}>
        <Tabs
          value={activePanelTab}
          onChange={(event, next) => setActivePanelTab(next)}
          variant="fullWidth"
          sx={{ '& .MuiTab-root': { textTransform: 'none', fontSize: '0.78rem', minHeight: 36, py: 0.5 } }}
        >
          {rightPanelTabs.map((tab) => (
            <Tab key={tab.label} label={tab.label} />
          ))}
        </Tabs>
      </Box>
      <Box sx={{ p: 2, fontSize: '0.78rem' }}>{rightPanelTabs[activePanelTab]?.render()}</Box>
    </Box>
  );

  // ── Loading / error states ─────────────────────────────────────────────
  if (loading) return (
    <Box>
      <PageHeader title="My Data" subtitle="Loading…" breadcrumbs={breadcrumbs} />
      <LoadingSkeleton variant="table" />
    </Box>
  );

  if (error) return (
    <Box>
      <PageHeader title="My Data" breadcrumbs={breadcrumbs} />
      <ErrorAlert message={error} onRetry={load} />
    </Box>
  );

  // ── Main layout ────────────────────────────────────────────────────────
  const mainContent = (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>

      {/* ── Filter bar ── */}
      <Stack
        direction="row"
        spacing={0.75}
        alignItems="center"
        sx={{
          px: 1.5,
          py: 0.5,
          flexShrink: 0,
          borderBottom: 1,
          borderColor: 'divider',
          bgcolor: 'background.paper',
        }}
      >
        <TextField
          size="small"
          placeholder="Search sources…"
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon sx={{ fontSize: 14, color: 'text.disabled' }} />
              </InputAdornment>
            ),
          }}
          sx={{
            flex: 1,
            '& .MuiInputBase-input': { fontSize: '0.75rem', py: '6px' },
          }}
        />

        <FormControl size="small" sx={{ minWidth: 100 }}>
          <InputLabel sx={{ fontSize: '0.75rem' }}>Scope</InputLabel>
          <Select value={scopeFilter} label="Scope" onChange={(e) => setScopeFilter(e.target.value)}
            sx={{ fontSize: '0.75rem' }}>
            <MenuItem value="all" sx={{ fontSize: '0.75rem' }}>All scopes</MenuItem>
            <MenuItem value="1" sx={{ fontSize: '0.75rem' }}>Scope 1</MenuItem>
            <MenuItem value="2" sx={{ fontSize: '0.75rem' }}>Scope 2</MenuItem>
            <MenuItem value="3" sx={{ fontSize: '0.75rem' }}>Scope 3</MenuItem>
          </Select>
        </FormControl>

        <FormControl size="small" sx={{ minWidth: 110 }}>
          <InputLabel sx={{ fontSize: '0.75rem' }}>Status</InputLabel>
          <Select value={statusFilter} label="Status" onChange={(e) => setStatusFilter(e.target.value)}
            sx={{ fontSize: '0.75rem' }}>
            <MenuItem value="all" sx={{ fontSize: '0.75rem' }}>All</MenuItem>
            <MenuItem value="passing" sx={{ fontSize: '0.75rem' }}>Passing</MenuItem>
            <MenuItem value="warning" sx={{ fontSize: '0.75rem' }}>Warning</MenuItem>
            <MenuItem value="failing" sx={{ fontSize: '0.75rem' }}>Failing</MenuItem>
            <MenuItem value="no_data" sx={{ fontSize: '0.75rem' }}>No Data</MenuItem>
          </Select>
        </FormControl>

        <Tooltip title="Refresh">
          <IconButton size="small" onClick={load} sx={{ p: 0.5 }}>
            <RefreshIcon sx={{ fontSize: 14 }} />
          </IconButton>
        </Tooltip>

<Typography variant="caption" color="text.secondary" sx={{ ml: 0.5, whiteSpace: 'nowrap', fontSize: '0.72rem' }}>
          {filtered.length} of {modules.length}
        </Typography>
      </Stack>

      {/* ── Data grid ── */}
      <Box sx={{ flex: 1, minHeight: 0 }}>
        {filtered.length === 0 ? (
          <Box sx={{ p: 4 }}>
            <EmptyState title="No sources match your filters" description="Try adjusting the search or filters." />
          </Box>
        ) : (
          <DataGrid
            rows={filtered}
            columns={columns}
            density="compact"
            rowSelection
            rowSelectionModel={selectedId ? { type: 'include', ids: new Set([selectedId]) } : { type: 'include', ids: new Set() }}
            onRowSelectionModelChange={(model) => {
              const ids = Array.from(model.ids || []);
              setSelectedId(ids[0] ?? null);
              setActivePanelTab(0);
            }}
            onRowClick={(params) => {
              setSelectedId(params.id);
              setActivePanelTab(0);
            }}
            pageSizeOptions={[25, 50, 100]}
            initialState={{ pagination: { paginationModel: { pageSize: 25 } } }}
            sx={{
              border: 'none',
              fontSize: '0.8125rem',
              '& .MuiDataGrid-columnHeaders': {
                bgcolor: 'grey.50',
                borderBottom: 1,
                borderColor: 'divider',
                '& .MuiDataGrid-columnHeaderTitle': {
                  fontSize: '0.68rem',
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  color: 'text.secondary',
                  letterSpacing: '0.04em',
                },
              },
              '& .MuiDataGrid-row': {
                cursor: 'pointer',
                '&:hover': { bgcolor: 'action.hover' },
                '&.Mui-selected': {
                  bgcolor: `${theme.palette.primary.main}14`,
                  '&:hover': { bgcolor: `${theme.palette.primary.main}1e` },
                },
              },
              '& .MuiDataGrid-cell': {
                borderBottom: `1px solid ${theme.palette.divider}`,
                fontSize: '0.72rem',
                '&:focus, &:focus-within': { outline: 'none' },
              },
              '& .MuiDataGrid-footerContainer': {
                borderTop: 1,
                borderColor: 'divider',
                minHeight: 40,
              },
            }}
          />
        )}
      </Box>
    </Box>
  );

  return (
    <>
      <EntityDetailShell
        header={
          <PageHeader
            title="My Data"
            subtitle={orgUnit?.name || ''}
          />
        }
        mainContent={mainContent}
        metricsPanel={rightPanel}
        metricsTabs={rightPanelTabs}
        initialMetricsTab={activePanelTab}
        activeMetricsTab={activePanelTab}
        onMetricsTabChange={(event, next) => setActivePanelTab(next)}
        panelWidthKey="myData:panelWidth"
      />

      <Snackbar open={Boolean(snackbar)} autoHideDuration={4000} onClose={() => setSnackbar(null)}>
        <Alert severity={snackbar?.severity || 'info'} onClose={() => setSnackbar(null)}>
          {snackbar?.message}
        </Alert>
      </Snackbar>
    </>
  );
}
