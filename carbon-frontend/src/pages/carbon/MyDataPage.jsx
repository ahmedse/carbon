// src/pages/carbon/MyDataPage.jsx
// My Data – Level 1 data owner workspace.
//   – Grid: FilteredDataGrid-style with search, scope + status filters
//   – Row click: highlights row, sets the contextual inspector context
//     (global drawer tabs: Trust / Impact / Activity — see inspector/tabs/myDataTabs.jsx)
//   – Row actions: View (→ module workspace)
//   – All colours via theme.palette, zero hardcoded hex

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Alert,
  Box,
  Chip,
  FormControl,
  IconButton,
  InputAdornment,
  InputLabel,
  MenuItem,
  Select,
  Snackbar,
  Stack,
  TextField,
  Tooltip,
  Typography,
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
import { FONT } from '../../theme/themeTokens';
import { EmptyState, ErrorAlert, LoadingSkeleton, PageHeader } from '../../components';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useNotes } from '../../notes/NotesContext';
import { registerMyDataSourceInspectorTabs } from '../../inspector/tabs/myDataTabs';

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
  const cfg = SCOPE_CFG[value] || SCOPE_CFG[1];
  return (
    <Chip
      label={cfg.label}
      size="small"
      color={cfg.palette}
      sx={{
        fontWeight: 700,
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
      icon={<Icon sx={{ fontSize: '0.8125rem' }} />}
      label={cfg.label}
      size="small"
      color={cfg.palette || 'default'}
      variant="outlined"
      sx={{ '& .MuiChip-label': { px: 0.5 }, '& .MuiChip-icon': { ml: 0.5 } }}
    />
  );
}

// ── Main page ──────────────────────────────────────────────────────────────

export default function MyDataPage() {
  useDocumentTitle("My Data");
  const navigate = useNavigate();
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
          <Typography component="span" sx={{ fontSize: '0.625rem', fontWeight: 600, textTransform: 'uppercase', color: 'text.secondary', letterSpacing: '0.05em' }}>
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
        <Typography sx={{ ...FONT.body, fontWeight: 600 }}>{value}</Typography>
      ),
    },
    {
      field: 'table_count',
      headerName: 'Tables',
      width: 75,
      type: 'number',
      renderCell: ({ value }) => <Typography sx={FONT.body}>{value ?? 0}</Typography>,
    },
    {
      field: 'row_count',
      headerName: 'Rows',
      width: 75,
      type: 'number',
      renderCell: ({ value }) => <Typography sx={FONT.body}>{value ?? 0}</Typography>,
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
          <Typography component="span" sx={{ fontSize: '0.625rem', fontWeight: 600, textTransform: 'uppercase', color: 'text.secondary', letterSpacing: '0.05em' }}>
            DQ%
          </Typography>
        </Tooltip>
      ),
      renderCell: ({ value }) => (
        <Typography
          sx={{
            ...FONT.body,
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
        <Typography sx={{ ...FONT.body, color: 'text.secondary' }}>{fmtDate(value)}</Typography>
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
              <VisibilityIcon sx={{ fontSize: '0.9375rem' }} />
            </IconButton>
          </Tooltip>
        </Stack>
      ),
    },
  ], [navigate]);

  // ── Contextual Inspector (global drawer) ────────────────────────────────
  const { setContexts } = useNotes();

  // Register the My-Data source tabs once; unregister on unmount.
  useEffect(() => registerMyDataSourceInspectorTabs(), []);

  // Expose the selected source as the active inspector context with a payload
  // fast-path ({ mod, activity }) so the registered tabs render without refetch.
  const inspectorContext = useMemo(
    () => [{ entityType: 'myDataSource', entityId: selected?.id ?? null, label: selected?.name, payload: { mod: selected, activity } }],
    [selected, activity],
  );
  useEffect(() => {
    setContexts(inspectorContext);
    return () => setContexts(null);
  }, [inspectorContext, setContexts]);

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
                <SearchIcon sx={{ fontSize: '0.9375rem', color: 'text.disabled' }} />
              </InputAdornment>
            ),
          }}
          sx={{ flex: 1 }}
        />

        <FormControl size="small" sx={{ minWidth: 100 }}>
          <InputLabel>
            <Tooltip title="GHG Protocol scope: 1 (direct), 2 (purchased electricity), 3 (value chain)" arrow>
              <Typography component="span" sx={{ fontSize: 'inherit' }}>Scope</Typography>
            </Tooltip>
          </InputLabel>
          <Select value={scopeFilter} label="Scope" onChange={(e) => setScopeFilter(e.target.value)}>
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
          <Select value={statusFilter} label="Status" onChange={(e) => setStatusFilter(e.target.value)}>
            <MenuItem value="all">All</MenuItem>
            <MenuItem value="passing">Passing</MenuItem>
            <MenuItem value="warning">Warning</MenuItem>
            <MenuItem value="failing">Failing</MenuItem>
            <MenuItem value="no_data">No Data</MenuItem>
          </Select>
        </FormControl>

        <Tooltip title="Refresh">
          <IconButton size="small" onClick={load}>
            <RefreshIcon sx={{ fontSize: '1rem' }} />
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
            }}
            onRowClick={(params) => {
              setSelectedId(params.id);
            }}
            pageSizeOptions={[25, 50, 100]}
            initialState={{ pagination: { paginationModel: { pageSize: 25 } } }}
            sx={{
              '& .MuiDataGrid-row': { cursor: 'pointer' },
              '& .MuiDataGrid-cell': {
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
      <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', bgcolor: 'background.default' }}>
        <Box sx={{ bgcolor: 'white', px: 2, pt: 1.5, pb: 0 }}>
          <PageHeader
            title="My Data"
            subtitle={orgUnit?.name || ''}
            description="Your data owner workspace. Select a source to inspect row counts, data quality scores, and activity. Open the workspace to edit tables row by row."
          />
        </Box>
        <Box sx={{ flex: 1, overflow: 'auto', bgcolor: 'white', borderTop: 1, borderColor: 'divider' }}>
          {mainContent}
        </Box>
      </Box>

      <Snackbar open={Boolean(snackbar)} autoHideDuration={4000} onClose={() => setSnackbar(null)}>
        <Alert severity={snackbar?.severity || 'info'} onClose={() => setSnackbar(null)}>
          {snackbar?.message}
        </Alert>
      </Snackbar>
    </>
  );
}
