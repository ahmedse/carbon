// src/pages/carbon/MyDataPage.jsx
// My Data – Level 1 data owner workspace.
// Pattern: EntityDetailShell (main grid + resizable right panel)
//   – Grid: FilteredDataGrid-style with search, scope + status filters
//   – Row click: highlights row, populates right panel (tabs: Trust, Impact, Activity)
//   – Row actions: View (→ module workspace), Edit, Delete
//   – All colours via theme.palette, zero hardcoded hex

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Alert,
  Box,
  Chip,
  CircularProgress,
  Divider,
  FormControl,
  IconButton,
  InputAdornment,
  InputLabel,
  LinearProgress,
  List,
  ListItemButton,
  ListItemText,
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
import AssessmentIcon from '@mui/icons-material/Assessment';
import BoltRoundedIcon from '@mui/icons-material/BoltRounded';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';
import LocalShippingRoundedIcon from '@mui/icons-material/LocalShippingRounded';
import MemoryIcon from '@mui/icons-material/Memory';
import NatureRoundedIcon from '@mui/icons-material/NatureRounded';
import RefreshIcon from '@mui/icons-material/Refresh';
import SearchIcon from '@mui/icons-material/Search';
import ShieldIcon from '@mui/icons-material/Shield';
import TimelineIcon from '@mui/icons-material/Timeline';
import TrackChangesIcon from '@mui/icons-material/TrackChanges';
import VerifiedUserIcon from '@mui/icons-material/VerifiedUser';
import VisibilityIcon from '@mui/icons-material/Visibility';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import { useAuth } from '../../auth/AuthContext';
import { fetchMyData, fetchOwnerActivity } from '../../api/emissions';
import { fetchSBTiTargets } from '../../api/emissions-extended';
import { fetchAssetProfiles, fetchGovernanceEvents } from '../../api/catalog';
import { getOrgDQMetrics } from '../../api/dq';
import EntityDetailShell from '../../components/entity/EntityDetailShell';
import useDetailPanel from '../../components/entity/useDetailPanel';
import { EmptyState, ErrorAlert, LoadingSkeleton, PageHeader, StatCard } from '../../components';
import useDocumentTitle from '../../hooks/useDocumentTitle';

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

// ── Right panel: Trust tab ────────────────────────────────────────────────

function TrustTab({ mod, theme, token }) {
  const [dqMetrics, setDqMetrics] = useState(null);
  const [assetProfile, setAssetProfile] = useState(null);

  useEffect(() => {
    if (!mod?.id || !token) return;
    getOrgDQMetrics(token)
      .then(setDqMetrics)
      .catch(() => setDqMetrics(null));
    fetchAssetProfiles(token)
      .then((profiles) => {
        const match = (profiles || []).find(
          (p) => p.id === mod.id || p.source_id === mod.id || p.name === mod.name
        );
        setAssetProfile(match || null);
      })
      .catch(() => setAssetProfile(null));
  }, [mod?.id, mod?.name, token]);

  if (!mod) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography variant="body2" color="text.secondary">
          Select a source to see trust metrics.
        </Typography>
      </Box>
    );
  }

  const dqScore = mod.quality_score ?? 0;
  const dqColor = dqScore >= 80 ? 'success.main' : dqScore >= 60 ? 'warning.main' : 'error.main';
  const failingRules = dqMetrics?.failing_rules ?? (mod.quality_score != null && mod.quality_score < 60 ? '—' : 0);
  const isLocked = assetProfile?.governance?.locked ?? false;
  const lastVerified = assetProfile?.governance?.last_verified ?? null;
  const evidenceCount = assetProfile?.evidence_count ?? 0;
  const qualityStatus = assetProfile?.quality_status ?? (dqScore >= 80 ? 'Passing' : dqScore >= 60 ? 'Warning' : dqScore > 0 ? 'Failing' : 'No data');

  return (
    <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Typography variant="body2" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.08em', fontSize: '0.68rem' }}>
        Trust
      </Typography>

      {/* DQ Gauge */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        <Box sx={{ position: 'relative', display: 'inline-flex' }}>
          <CircularProgress
            variant="determinate"
            value={Math.min(dqScore, 100)}
            size={72}
            thickness={5}
            sx={{ color: dqColor }}
          />
          <Box
            sx={{
              position: 'absolute',
              top: 0,
              left: 0,
              bottom: 0,
              right: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Typography variant="body2" sx={{ fontWeight: 700, fontSize: '0.82rem', color: dqColor }}>
              {Math.round(dqScore)}%
            </Typography>
          </Box>
        </Box>
        <Box>
          <Typography sx={{ fontSize: '0.75rem', fontWeight: 600 }}>DQ Score</Typography>
          <Chip
            label={dqScore >= 80 ? 'Passing' : dqScore >= 60 ? 'Warning' : dqScore > 0 ? 'Failing' : 'No data'}
            size="small"
            color={dqScore >= 80 ? 'success' : dqScore >= 60 ? 'warning' : dqScore > 0 ? 'error' : 'default'}
            variant="outlined"
            sx={{ height: 20, fontSize: '0.68rem', mt: 0.5 }}
          />
        </Box>
      </Box>

      <Divider />

      {/* Detail rows */}
      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr', gap: 0 }}>
        {[
          { label: 'Failing rules', value: `${failingRules}` },
          { label: 'Locked', value: isLocked ? 'Yes' : 'No' },
          { label: 'Last verified', value: fmtDate(lastVerified) },
          { label: 'Evidence', value: `${evidenceCount} docs` },
          { label: 'Quality status', value: qualityStatus },
        ].map(({ label, value }) => (
          <Box
            key={label}
            sx={{
              display: 'grid',
              gridTemplateColumns: '120px 1fr',
              gap: 1,
              py: 1,
              borderBottom: `1px solid ${theme.palette.divider}`,
            }}
          >
            <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
              {label}
            </Typography>
            <Typography
              component="span"
              variant="body2"
              sx={{ fontWeight: 600, color: 'text.primary', fontSize: '0.82rem' }}
            >
              {value}
            </Typography>
          </Box>
        ))}
      </Box>
    </Box>
  );
}

function ImpactTab({ mod, theme, token }) {
  const [sbtiTargets, setSbtiTargets] = useState([]);

  useEffect(() => {
    if (!mod?.id || !token) return;
    fetchSBTiTargets(token)
      .then((targets) => setSbtiTargets(Array.isArray(targets) ? targets : []))
      .catch(() => setSbtiTargets([]));
  }, [mod?.id, token]);

  if (!mod) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography variant="body2" color="text.secondary">
          Select a source to see downstream impact.
        </Typography>
      </Box>
    );
  }

  const sbtiCount = sbtiTargets.filter(
    (t) =>
      t.org_unit_id === mod.id ||
      t.source_id === mod.id ||
      (t.org_unit_name && t.org_unit_name === mod.name)
  ).length;
  const rowCount = mod.row_count ?? 0;

  return (
    <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Typography variant="body2" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.08em', fontSize: '0.68rem' }}>
        Impact
      </Typography>

      {/* Dependency chain */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 0.5,
          py: 1.5,
          flexWrap: 'wrap',
        }}
      >
        {[
          { label: 'Source', icon: <MemoryIcon sx={{ fontSize: 14 }} /> },
          { label: 'Tables', icon: null },
          { label: 'Calc', icon: <AssessmentIcon sx={{ fontSize: 14 }} /> },
          { label: 'Reports', icon: null },
        ].map((step, idx, arr) => (
          <React.Fragment key={step.label}>
            <Chip
              icon={step.icon}
              label={step.label}
              size="small"
              variant="outlined"
              sx={{
                height: 24,
                fontSize: '0.68rem',
                fontWeight: 600,
                borderColor: theme.palette.divider,
              }}
            />
            {idx < arr.length - 1 && (
              <Typography sx={{ color: 'text.disabled', fontSize: '0.75rem', mx: -0.25 }}>→</Typography>
            )}
          </React.Fragment>
        ))}
      </Box>

      <Divider />

      {/* Stats */}
      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr', gap: 0 }}>
        {[
          {
            label: 'SBTi targets',
            value: `${sbtiCount} reference${sbtiCount !== 1 ? 's' : ''} this org unit`,
          },
          { label: 'Calculations', value: `${rowCount} records linked` },
          {
            label: 'Data consumers',
            value: (
              <Chip
                label="Carbon app"
                size="small"
                sx={{ height: 20, fontSize: '0.68rem', fontWeight: 600 }}
              />
            ),
          },
        ].map(({ label, value }) => (
          <Box
            key={label}
            sx={{
              display: 'grid',
              gridTemplateColumns: '120px 1fr',
              gap: 1,
              py: 1,
              borderBottom: `1px solid ${theme.palette.divider}`,
            }}
          >
            <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
              {label}
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              {typeof value === 'string' || typeof value === 'number' ? (
                <Typography
                  component="span"
                  variant="body2"
                  sx={{ fontWeight: 600, color: 'text.primary', fontSize: '0.82rem' }}
                >
                  {value}
                </Typography>
              ) : (
                value
              )}
            </Box>
          </Box>
        ))}
      </Box>
    </Box>
  );
}

const ACTIVITY_KINDS = {
  data_change: { label: 'Data change', color: 'info', Icon: MemoryIcon },
  dq_run: { label: 'DQ run', color: 'success', Icon: AssessmentIcon },
  governance: { label: 'Governance', color: 'secondary', Icon: ShieldIcon },
  calculation: { label: 'Calculation', color: 'warning', Icon: AssessmentIcon },
};

function detectActivityKind(item) {
  const detail = (item.detail || item.message || item.event || '').toLowerCase();
  if (detail.includes('governance') || detail.includes('lock') || detail.includes('policy') || detail.includes('approve')) return 'governance';
  if (detail.includes('dq') || detail.includes('quality') || detail.includes('check') || detail.includes('rule')) return 'dq_run';
  if (detail.includes('calc') || detail.includes('compute') || detail.includes('emission') || detail.includes('target')) return 'calculation';
  return 'data_change';
}

function ActivityTab({ activity, theme, token }) {
  const [filter, setFilter] = useState('all');
  const [govEvents, setGovEvents] = useState([]);

  useEffect(() => {
    if (!token) return;
    fetchGovernanceEvents(token, { limit: 20 })
      .then((events) => setGovEvents(Array.isArray(events) ? events : []))
      .catch(() => setGovEvents([]));
  }, [token]);

  const merged = useMemo(() => {
    const govMapped = govEvents.map((e) => ({
      id: e.id,
      detail: e.description || e.event || e.action || 'Governance event',
      timestamp: e.timestamp || e.created_at,
      kind: 'governance',
    }));
    const actMapped = (activity || []).map((a) => ({
      ...a,
      kind: detectActivityKind(a),
    }));
    const combined = [...actMapped, ...govMapped];
    combined.sort((a, b) => new Date(b.timestamp || b.created_at || 0) - new Date(a.timestamp || a.created_at || 0));
    return combined;
  }, [activity, govEvents]);

  const filtered = useMemo(() => {
    if (filter === 'all') return merged;
    return merged.filter((item) => item.kind === filter);
  }, [merged, filter]);

  const filterOptions = [
    { value: 'all', label: 'All' },
    { value: 'data_change', label: 'Data', color: 'info' },
    { value: 'dq_run', label: 'DQ', color: 'success' },
    { value: 'governance', label: 'Gov', color: 'secondary' },
    { value: 'calculation', label: 'Calc', color: 'warning' },
  ];

  return (
    <Box sx={{ p: 1.5 }}>
      {/* Filter row */}
      <Stack direction="row" spacing={0.5} sx={{ mb: 1.5, flexWrap: 'wrap', gap: 0.5 }}>
        {filterOptions.map((opt) => {
          const isActive = filter === opt.value;
          return (
            <Chip
              key={opt.value}
              label={opt.label}
              size="small"
              variant={isActive ? 'filled' : 'outlined'}
              color={isActive ? (opt.color || 'primary') : 'default'}
              onClick={() => setFilter(opt.value)}
              sx={{
                height: 22,
                fontSize: '0.65rem',
                fontWeight: isActive ? 700 : 500,
                cursor: 'pointer',
                '&:hover': { bgcolor: isActive ? undefined : theme.palette.action.hover },
              }}
            />
          );
        })}
      </Stack>

      {filtered.length === 0 ? (
        <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary' }}>No recent activity.</Typography>
      ) : (
        <Stack divider={<Divider flexItem />} spacing={0}>
          {filtered.map((item, i) => {
            const cfg = ACTIVITY_KINDS[item.kind] || ACTIVITY_KINDS.data_change;
            const Icon = cfg.Icon;
            return (
              <Box key={item.id ?? i} sx={{ py: 1, display: 'flex', gap: 1, alignItems: 'flex-start' }}>
                <Icon
                  sx={{
                    fontSize: 14,
                    mt: '2px',
                    color: `${cfg.color}.main`,
                    flexShrink: 0,
                  }}
                />
                <Box sx={{ minWidth: 0 }}>
                  <Typography sx={{ fontSize: '0.75rem', lineHeight: 1.35 }}>
                    {item.detail || item.message || 'Updated'}
                  </Typography>
                  <Typography sx={{ fontSize: '0.65rem', color: 'text.disabled', mt: 0.25 }}>
                    {fmtDate(item.timestamp || item.created_at)}
                  </Typography>
                </Box>
              </Box>
            );
          })}
        </Stack>
      )}
    </Box>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────

export default function MyDataPage() {
  useDocumentTitle("My Data");
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
      renderHeader: () => (
        <Tooltip title="GHG Protocol scope classification. Scope 1 = direct emissions from owned sources. Scope 2 = purchased electricity. Scope 3 = value chain (supply chain, travel, etc.)." arrow>
          <Typography component="span" sx={{ fontSize: '0.72rem', fontWeight: 700, textTransform: 'uppercase', color: 'text.secondary', letterSpacing: '0.04em' }}>
            Scope
          </Typography>
        </Tooltip>
      ),
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
      renderHeader: () => (
        <Tooltip title="Data Quality score (%) — computed from completeness, freshness, accuracy, and consistency checks. ≥80% passing, 60–79% warning, <60% failing." arrow>
          <Typography component="span" sx={{ fontSize: '0.72rem', fontWeight: 700, textTransform: 'uppercase', color: 'text.secondary', letterSpacing: '0.04em' }}>
            DQ%
          </Typography>
        </Tooltip>
      ),
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

  const { metricsPanel, metricsTabs, activeMetricsTab, onMetricsTabChange, resetTab } = useDetailPanel({
    tabs: [
      { label: 'Trust',    render: () => <TrustTab mod={selected} theme={theme} token={token} /> },
      { label: 'Impact',   render: () => <ImpactTab mod={selected} theme={theme} token={token} /> },
      { label: 'Activity', render: () => <ActivityTab activity={activity} theme={theme} token={token} /> },
    ],
    storageKey: 'myData:panelTab',
  });

  // ── Loading / error states ─────────────────────────────────────────────
  if (loading) return (
    <Box>
      <PageHeader title="My Data" subtitle="Loading…" />
      <LoadingSkeleton variant="table" />
    </Box>
  );

  if (error) return (
    <Box>
      <PageHeader title="My Data" />
      <ErrorAlert message={error} onRetry={load} />
    </Box>
  );

  // ── Main layout ────────────────────────────────────────────────────────
  const mainContent = (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>

      {/* ── Filter bar ── */}
      <Stack
        direction="row"
        spacing={1}
        alignItems="center"
        sx={{
          px: 2,
          py: 1,
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
                <SearchIcon sx={{ fontSize: 15, color: 'text.disabled' }} />
              </InputAdornment>
            ),
          }}
          sx={{
            flex: 1,
            '& .MuiInputBase-input': { fontSize: '0.8125rem', py: '6px' },
          }}
        />

        <FormControl size="small" sx={{ minWidth: 100 }}>
          <InputLabel>
            <Tooltip title="GHG Protocol scope: 1 (direct), 2 (purchased electricity), 3 (value chain)" arrow>
              <Typography component="span" sx={{ fontSize: 'inherit' }}>Scope</Typography>
            </Tooltip>
          </InputLabel>
          <Select value={scopeFilter} label="Scope" onChange={(e) => setScopeFilter(e.target.value)}
            sx={{ fontSize: '0.8125rem' }}>
            <MenuItem value="all">All scopes</MenuItem>
            <MenuItem value="1">Scope 1</MenuItem>
            <MenuItem value="2">Scope 2</MenuItem>
            <MenuItem value="3">Scope 3</MenuItem>
          </Select>
        </FormControl>

        <FormControl size="small" sx={{ minWidth: 110 }}>
          <InputLabel>
            <Tooltip title="Data quality threshold: Passing (DQ ≥ 80%), Warning (60–79%), Failing (< 60%), No data (no entries)." arrow>
              <Typography component="span" sx={{ fontSize: 'inherit' }}>Status</Typography>
            </Tooltip>
          </InputLabel>
          <Select value={statusFilter} label="Status" onChange={(e) => setStatusFilter(e.target.value)}
            sx={{ fontSize: '0.8125rem' }}>
            <MenuItem value="all">All</MenuItem>
            <MenuItem value="passing">Passing</MenuItem>
            <MenuItem value="warning">Warning</MenuItem>
            <MenuItem value="failing">Failing</MenuItem>
            <MenuItem value="no_data">No Data</MenuItem>
          </Select>
        </FormControl>

        <Tooltip title="Refresh">
          <IconButton size="small" onClick={load}>
            <RefreshIcon sx={{ fontSize: 16 }} />
          </IconButton>
        </Tooltip>

        <Typography variant="caption" color="text.secondary" sx={{ ml: 0.5, whiteSpace: 'nowrap' }}>
          {filtered.length} of {modules.length}
        </Typography>
      </Stack>

      {/* ── Data grid ── */}
      <Box sx={{ flex: 1, minHeight: 0, overflowX: 'auto' }}>
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
              resetTab();
            }}
            onRowClick={(params) => {
              setSelectedId(params.id);
              resetTab();
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
                  fontSize: '0.72rem',
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
            description="Your data owner workspace. Select a source to inspect row counts, data quality scores, and activity. Open the workspace to edit tables row by row."
          />
        }
        mainContent={mainContent}
        metricsPanel={metricsPanel}
        metricsTabs={metricsTabs}
        activeMetricsTab={activeMetricsTab}
        onMetricsTabChange={onMetricsTabChange}
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
