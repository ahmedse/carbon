// src/pages/carbon/VerificationPage.jsx
// Verification Workflow — Phase 04 G2
// 3-tab verification: Pending Review → Verified → All Periods
// Pattern: tabbed DataGrid views with approve/reject actions
// All colours via theme.palette, zero hardcoded hex

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControl,
  IconButton,
  InputLabel,
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
import {
  CheckCircle as ApproveIcon,
  Close as RejectIcon,
  ErrorOutline as FailedIcon,
  GppBad as RejectedIcon,
  GppGood as VerifiedIcon,
  HelpOutline as PendingIcon,
  HourglassEmpty as ReviewIcon,
  Refresh as RefreshIcon,
  VerifiedUser as ApprovedIcon,
} from '@mui/icons-material';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import {
  fetchVerificationRecords,
  verifyVerificationRecord,
  rejectVerificationRecord,
} from '../../api/emissions-extended';
import PageHeader from '../../components/Page/PageHeader';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../components/Page/ErrorAlert';
import EmptyState from '../../components/Page/EmptyState';

// ── Tab config ──────────────────────────────────────────────────────────

const VERIFICATION_TABS = [
  { label: 'Pending Review', key: 'pending',  icon: <ReviewIcon sx={{ fontSize: 18 }} />, status: 'pending' },
  { label: 'Verified',       key: 'verified', icon: <ApprovedIcon sx={{ fontSize: 18 }} />, status: 'verified' },
  { label: 'All Periods',    key: 'all',      icon: null,                                   status: null },
];

// ── Scope config ─────────────────────────────────────────────────────────

const SCOPE_CFG = {
  1: { label: 'Scope 1', palette: 'success' },
  2: { label: 'Scope 2', palette: 'info' },
  3: { label: 'Scope 3', palette: 'warning' },
};

// ── Period status config ──────────────────────────────────────────────────

const PERIOD_STATUS_CFG = {
  draft:     { label: 'Draft',     color: 'default' },
  open:      { label: 'Open',      color: 'info' },
  locked:    { label: 'Locked',    color: 'warning' },
  submitted: { label: 'Submitted', color: 'secondary' },
  verified:  { label: 'Verified',  color: 'success' },
  rejected:  { label: 'Rejected',  color: 'error' },
  closed:    { label: 'Closed',    color: 'default' },
};

// ── Status config ────────────────────────────────────────────────────────

const STATUS_CFG = {
  pending:  { label: 'Pending',  palette: 'warning', Icon: PendingIcon },
  verified: { label: 'Verified', palette: 'info',    Icon: VerifiedIcon },
  rejected: { label: 'Rejected', palette: 'error',   Icon: RejectedIcon },
  failed:   { label: 'Failed',   palette: 'error',   Icon: FailedIcon },
};

// ── Helpers ──────────────────────────────────────────────────────────────

function ScopeBadge({ value }) {
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
        bgcolor: p?.[50] || (p?.light + '30'),
        color: p?.dark || p?.main,
        border: 'none',
        '& .MuiChip-label': { px: 1 },
      }}
    />
  );
}

function StatusChip({ status }) {
  const cfg = STATUS_CFG[status] || STATUS_CFG.pending;
  const Icon = cfg.Icon;
  return (
    <Chip
      icon={<Icon sx={{ fontSize: '13px !important' }} />}
      label={cfg.label}
      size="small"
      color={cfg.palette}
      variant="outlined"
      sx={{ height: 20, fontSize: '0.68rem', '& .MuiChip-label': { px: 0.5 }, '& .MuiChip-icon': { ml: '4px' } }}
    />
  );
}

function fmtDate(v) {
  if (!v) return '—';
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function fmtNum(v) {
  if (v == null) return '—';
  return Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// ── Reject Dialog ──────────────────────────────────────────────────────

function RejectDialog({ open, record, onClose, onConfirm, loading }) {
  const [notes, setNotes] = useState('');

  useEffect(() => {
    if (open) setNotes('');
  }, [open]);

  const handleConfirm = () => {
    onConfirm(record, notes);
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Reject Period</DialogTitle>
      <DialogContent>
        <Typography sx={{ fontSize: '0.85rem', mb: 2 }}>
          Reject verification for <strong>{record?.period_label || record?.period_name || record?.id}</strong>?
        </Typography>
        <TextField
          autoFocus
          label="Rejection Notes"
          multiline
          rows={3}
          fullWidth
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Provide a reason for rejection…"
          sx={{ '& .MuiInputBase-root': { fontSize: '0.82rem' } }}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={loading}>Cancel</Button>
        <Button
          onClick={handleConfirm}
          variant="contained"
          color="error"
          disabled={loading || !notes.trim()}
          startIcon={loading ? <CircularProgress size={16} /> : <RejectIcon />}
        >
          {loading ? 'Rejecting…' : 'Reject'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

// ── Approve Dialog ─────────────────────────────────────────────────────

function ApproveDialog({ open, record, onClose, onConfirm, loading }) {
  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs">
      <DialogTitle>Confirm Approval</DialogTitle>
      <DialogContent>
        <Typography sx={{ fontSize: '0.85rem' }}>
          Approve verification for <strong>{record?.period_label || record?.period_name || record?.id}</strong>?
          <Box component="span" sx={{ display: 'block', mt: 1, fontSize: '0.78rem', color: 'text.secondary' }}>
            This confirms the calculation data is accurate and complete.
          </Box>
        </Typography>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={loading}>Cancel</Button>
        <Button
          onClick={onConfirm}
          variant="contained"
          color="success"
          disabled={loading}
          startIcon={loading ? <CircularProgress size={16} /> : <ApproveIcon />}
        >
          {loading ? 'Approving…' : 'Approve'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

// ── Main Component ─────────────────────────────────────────────────────

export default function VerificationPage() {
  useDocumentTitle("Verification");
  const { token } = useAuth();
  const [activeTab, setActiveTab] = useState(0);

  // Data
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Scope filter
  const [scopeFilter, setScopeFilter] = useState('');

  // Dialogs
  const [rejectDialog, setRejectDialog] = useState({ open: false, record: null });
  const [approveDialog, setApproveDialog] = useState({ open: false, record: null });
  const [actionLoading, setActionLoading] = useState(false);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });

  // ── Compute current status filter from active tab ──────────────────────

  const currentStatus = VERIFICATION_TABS[activeTab]?.status;

  // ── Load ──────────────────────────────────────────────────────────────

  const loadRecords = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = { scope: scopeFilter || undefined };
      if (currentStatus) params.status = currentStatus;
      const data = await fetchVerificationRecords(params, token);
      setRecords(Array.isArray(data) ? data : data?.results || []);
    } catch (err) {
      setError(err.message || 'Failed to load verification records');
    } finally {
      setLoading(false);
    }
  }, [currentStatus, scopeFilter, token]);

  useEffect(() => {
    loadRecords();
  }, [loadRecords]);

  // ── Actions ──────────────────────────────────────────────────────────

  const handleApprove = async () => {
    const record = approveDialog.record;
    if (!record) return;
    setActionLoading(true);
    try {
      await verifyVerificationRecord(record.id, token);
      setSnackbar({ open: true, message: `Approved: ${record.period_label || record.period_name || record.id}`, severity: 'success' });
      setApproveDialog({ open: false, record: null });
      await loadRecords();
    } catch (err) {
      setSnackbar({ open: true, message: err.message || 'Approval failed', severity: 'error' });
    } finally {
      setActionLoading(false);
    }
  };

  const handleReject = async (record, notes) => {
    setActionLoading(true);
    try {
      await rejectVerificationRecord(record.id, notes, token);
      setSnackbar({ open: true, message: `Rejected: ${record.period_label || record.period_name || record.id}`, severity: 'warning' });
      setRejectDialog({ open: false, record: null });
      await loadRecords();
    } catch (err) {
      setSnackbar({ open: true, message: err.message || 'Rejection failed', severity: 'error' });
    } finally {
      setActionLoading(false);
    }
  };

  // ── Columns ───────────────────────────────────────────────────────────

  const isPendingTab = activeTab === 0;

  const columns = useMemo(() => {
    const base = [
      {
        field: 'period_label',
        headerName: 'Period',
        flex: 1.5,
        minWidth: 220,
        renderCell: (params) => (
          <Typography sx={{ fontSize: '0.8rem', fontWeight: 500 }}>
            {params.value || params.row.period_name || '—'}
          </Typography>
        ),
      },
      {
        field: 'period_status',
        headerName: 'Period Status',
        width: 120,
        renderCell: (params) => {
          const cfg = PERIOD_STATUS_CFG[params.value] || PERIOD_STATUS_CFG.draft;
          return <Chip label={cfg.label} size="small" color={cfg.color} variant="outlined" sx={{ height: 20, fontSize: '0.68rem' }} />;
        },
      },
      {
        field: 'total_co2e_tonnes',
        headerName: 'tCO₂e',
        width: 110,
        align: 'right',
        headerAlign: 'right',
        valueFormatter: (value) => fmtNum(value),
      },
      {
        field: 'scope_summary',
        headerName: 'Scope Summary',
        flex: 1,
        minWidth: 160,
        renderCell: (params) => {
          const summary = params.value;
          if (!summary || typeof summary !== 'object' || Object.keys(summary).length === 0) {
            return <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary' }}>—</Typography>;
          }
          return (
            <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
              {Object.entries(summary).map(([scope, tonnes]) => (
                <Chip
                  key={scope}
                  label={`S${scope}: ${fmtNum(tonnes)}`}
                  size="small"
                  sx={{
                    height: 20,
                    fontSize: '0.65rem',
                    fontWeight: 600,
                    bgcolor: 'action.hover',
                  }}
                />
              ))}
            </Stack>
          );
        },
      },
      {
        field: 'status',
        headerName: 'Verification',
        width: 110,
        renderCell: (params) => <StatusChip status={params.value} />,
      },
      {
        field: 'verifier_name',
        headerName: 'Verifier',
        width: 130,
        renderCell: (params) => (
          <Typography sx={{ fontSize: '0.78rem' }}>{params.value || '—'}</Typography>
        ),
      },
      {
        field: 'created_at',
        headerName: 'Created',
        width: 150,
        valueFormatter: (value) => fmtDate(value),
      },
    ];

    // Add verified_at for non-pending tabs
    if (!isPendingTab) {
      base.push({
        field: 'verified_at',
        headerName: 'Verified At',
        width: 150,
        valueFormatter: (value) => fmtDate(value),
      });
    }

    // Add notes column for pending/rejected
    if (isPendingTab) {
      base.push({
        field: 'notes',
        headerName: 'Notes',
        flex: 1,
        minWidth: 120,
        renderCell: (params) => (
          <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary', fontStyle: 'italic' }}>
            {params.value || '—'}
          </Typography>
        ),
      });
    }

    // Actions column for pending tab
    if (isPendingTab) {
      base.push({
        field: 'actions',
        headerName: 'Actions',
        width: 130,
        sortable: false,
        renderCell: (params) => (
          <Stack direction="row" spacing={0.5}>
            <Tooltip title="Approve">
              <IconButton
                size="small"
                color="success"
                onClick={(e) => {
                  e.stopPropagation();
                  setApproveDialog({ open: true, record: params.row });
                }}
              >
                <ApproveIcon sx={{ fontSize: 18 }} />
              </IconButton>
            </Tooltip>
            <Tooltip title="Reject">
              <IconButton
                size="small"
                color="error"
                onClick={(e) => {
                  e.stopPropagation();
                  setRejectDialog({ open: true, record: params.row });
                }}
              >
                <RejectIcon sx={{ fontSize: 18 }} />
              </IconButton>
            </Tooltip>
          </Stack>
        ),
      });
    }

    return base;
  }, [isPendingTab]);

  // ── Render ────────────────────────────────────────────────────────────

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Header */}
      <Box sx={{ px: 2.5, pt: 2, pb: 0 }}>
        <PageHeader
          title="Verification Workflow"
          subtitle="Review, approve, or reject period-level emission calculations"
          description="Independent verification of emission results with auditor workflow. Review calculation evidence, approve valid results, and reject discrepancies with documented justification."
          actions={
            <Stack direction="row" spacing={1}>
              <FormControl size="small" sx={{ minWidth: 120 }}>
                <InputLabel id="scope-filter-label">Scope</InputLabel>
                <Select
                  labelId="scope-filter-label"
                  value={scopeFilter}
                  label="Scope"
                  onChange={(e) => setScopeFilter(e.target.value)}
                >
                  <MenuItem value="">All Scopes</MenuItem>
                  <MenuItem value="1">Scope 1</MenuItem>
                  <MenuItem value="2">Scope 2</MenuItem>
                  <MenuItem value="3">Scope 3</MenuItem>
                </Select>
              </FormControl>
              <Tooltip title="Refresh">
                <IconButton onClick={loadRecords} size="small" disabled={loading}>
                  <RefreshIcon />
                </IconButton>
              </Tooltip>
            </Stack>
          }
        />
      </Box>

      {/* Tabs */}
      <Box sx={{ px: 2.5, borderBottom: '1px solid', borderColor: 'divider' }}>
        <Tabs
          value={activeTab}
          onChange={(_, v) => setActiveTab(v)}
          sx={{
            minHeight: 40,
            '& .MuiTab-root': { minHeight: 40, fontSize: '0.78rem', textTransform: 'none', px: 2 },
          }}
        >
          {VERIFICATION_TABS.map((tab) => (
            <Tab
              key={tab.key}
              label={tab.label}
              icon={tab.icon}
              iconPosition="start"
            />
          ))}
        </Tabs>
      </Box>

      {/* Error */}
      {error && (
        <Box sx={{ px: 2.5, pt: 1.5 }}>
          <ErrorAlert message={error} onRetry={loadRecords} />
        </Box>
      )}

      {/* DataGrid */}
      <Box sx={{ flex: 1, overflow: 'auto', px: 2.5, pb: 2, pt: 1.5 }}>
        {loading ? (
          <LoadingSkeleton variant="table" />
        ) : records.length === 0 ? (
          <EmptyState
            icon={isPendingTab ? <ReviewIcon /> : <VerifiedIcon />}
            title={isPendingTab ? 'No pending reviews' : 'No verified records'}
            description={
              isPendingTab
                ? 'All periods have been reviewed. Check the Verified tab for completed verifications.'
                : 'No records match the current filter criteria.'
            }
          />
        ) : (
          <DataGrid
            rows={records}
            columns={columns}
            autoHeight
            pageSizeOptions={[25, 50, 100]}
            initialState={{ pagination: { paginationModel: { pageSize: 25 } } }}
            disableRowSelectionOnClick
            getRowId={(row) => row.id || `${row.period_id}-${row.scope}`}
            sx={{
              border: '1px solid',
              borderColor: 'divider',
              borderRadius: 2,
              minHeight: 350,
              bgcolor: 'background.paper',
              '& .MuiDataGrid-cell': { outline: 'none' },
            }}
          />
        )}
      </Box>

      {/* ── Approve Dialog ── */}
      <ApproveDialog
        open={approveDialog.open}
        record={approveDialog.record}
        onClose={() => setApproveDialog({ open: false, record: null })}
        onConfirm={handleApprove}
        loading={actionLoading}
      />

      {/* ── Reject Dialog ── */}
      <RejectDialog
        open={rejectDialog.open}
        record={rejectDialog.record}
        onClose={() => setRejectDialog({ open: false, record: null })}
        onConfirm={handleReject}
        loading={actionLoading}
      />

      {/* ── Snackbar ── */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={() => setSnackbar((prev) => ({ ...prev, open: false }))}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert severity={snackbar.severity} variant="filled" sx={{ width: '100%' }}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
}
