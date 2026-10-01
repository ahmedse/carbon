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
  IconButton,
  Snackbar,
  Stack,
  Tab,
  Tabs,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import FilteredDataGrid from '../../components/FilteredDataGrid';
import { SCOPE_META } from '../../theme/themeTokens';
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
import { useTranslation } from 'react-i18next';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import PageContainer from '../../components/layout/PageContainer';
import { Scope2MethodChip, MarketBasedAbsentAlert } from './Scope2Labels';
import { useAuth } from '../../auth/AuthContext';
import {
  fetchVerificationRecords,
  verifyVerificationRecord,
  rejectVerificationRecord,
} from '../../api/emissions-extended';
import PageHeader from '../../components/Page/PageHeader';
import ErrorAlert from '../../components/Page/ErrorAlert';

// ── Tab config ──────────────────────────────────────────────────────────

const VERIFICATION_TABS = [
  { labelKey: 'pendingReview', key: 'pending',  icon: <ReviewIcon />, status: 'pending' },
  { labelKey: 'verifiedTab',   key: 'verified', icon: <ApprovedIcon />, status: 'verified' },
  { labelKey: 'allPeriodsTab', key: 'all',      icon: null,                                   status: null },
];

// ── Scope config ─────────────────────────────────────────────────────────

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

function StatusChip({ status }) {
  const cfg = STATUS_CFG[status] || STATUS_CFG.pending;
  const Icon = cfg.Icon;
  return (
    <Chip
      icon={<Icon fontSize="small" />}
      label={cfg.label}
      size="small"
      color={cfg.palette}
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
        <Typography variant="body2" sx={{ mb: 2 }}>
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
        <Typography variant="body2">
          Approve verification for <strong>{record?.period_label || record?.period_name || record?.id}</strong>?
          <Typography component="span" variant="caption" color="text.secondary" sx={{ display: "block", mt: 1 }}>
            This confirms the calculation data is accurate and complete.
          </Typography>
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
  const { t } = useTranslation('emissions');
  useDocumentTitle(t('verificationTitle'));
  const { token } = useAuth();
  const [activeTab, setActiveTab] = useState(0);

  // Data
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Scope filter
  const [scopeFilter, setScopeFilter] = useState('');
  const [search, setSearch] = useState('');

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

  const visibleRecords = useMemo(() => {
    if (!search) return records;
    const q = search.toLowerCase();
    return records.filter((row) =>
      (row.period_label || row.period_name || '').toLowerCase().includes(q)
    );
  }, [records, search]);

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
          <Typography variant="body2">
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
          return <Chip label={cfg.label} size="small" color={cfg.color === 'default' ? undefined : cfg.color} />;
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
        field: 'scope2_method',
        headerName: t('scope2MethodCol'),
        width: 160,
        renderCell: (params) => (
          params.row.scope2_method
            ? <Scope2MethodChip method={params.row.scope2_method} scope={2} />
            : '—'
        ),
      },
      {
        field: 'scope_summary',
        headerName: 'Scope Summary',
        flex: 1,
        minWidth: 160,
        renderCell: (params) => {
          const summary = params.value;
          if (!summary || typeof summary !== 'object' || Object.keys(summary).length === 0) {
            return <Typography variant="caption" color="text.secondary">—</Typography>;
          }
          return (
            <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
              {Object.entries(summary).map(([scope, tonnes]) => {
                const scopeNum = Number(scope);
                let label = `S${scope}: ${fmtNum(tonnes)}`;
                if (scopeNum === 2) {
                  const raw = String(params.row.scope2_method || '').toLowerCase().replace(/-/g, '_');
                  const method = raw === 'market_based'
                    ? t('scope2MarketBased')
                    : raw === 'location_based'
                      ? t('scope2LocationBased')
                      : t('chairman.scope2Unlabelled');
                  label = `S2 ${method}: ${fmtNum(tonnes)}`;
                }
                return (
                  <Chip
                    key={scope}
                    label={label}
                    size="small"
                    color={SCOPE_META[scopeNum]?.color}
                  />
                );
              })}
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
          <Typography variant="body2">{params.value || '—'}</Typography>
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
          <Typography variant="caption" color="text.secondary">
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
                <ApproveIcon fontSize="medium" />
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
                <RejectIcon fontSize="medium" />
              </IconButton>
            </Tooltip>
          </Stack>
        ),
      });
    }

    return base;
  }, [isPendingTab, t]);

  // ── Render ────────────────────────────────────────────────────────────

  return (
    <PageContainer sx={{ height: '100%', overflow: 'hidden' }}>
      {/* Header */}
      <Box sx={{ px: 2.5, pt: 2, pb: 0 }}>
        <PageHeader
          title={t('verificationTitle')}
          subtitle={t('verificationSubtitle')}
          description={t('verificationDescription')}
          actions={
            <Tooltip title="Refresh">
              <span>
                <IconButton onClick={loadRecords} size="small" disabled={loading} aria-label="Refresh">
                  <RefreshIcon />
                </IconButton>
              </span>
            </Tooltip>
          }
        />
      </Box>

      <Box sx={{ px: 2.5, pt: 1 }}>
        <MarketBasedAbsentAlert payload={records?.[0]} />
      </Box>

      {/* Tabs */}
      <Box sx={{ px: 2.5, borderBottom: '1px solid', borderColor: 'divider' }}>
        <Tabs value={activeTab} onChange={(_, v) => setActiveTab(v)}>
          {VERIFICATION_TABS.map((tab) => (
            <Tab
              key={tab.key}
              label={t(tab.labelKey)}
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
      <FilteredDataGrid
        embedded
        rows={visibleRecords}
        columns={columns}
        loading={loading}
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder={t('searchPeriods')}
        filterDefs={[{
          key: 'scope',
          label: 'Scope',
          options: [
            { value: '1', label: 'Scope 1' },
            { value: '2', label: 'Scope 2' },
            { value: '3', label: 'Scope 3' },
          ],
        }]}
        filterValues={{ scope: scopeFilter }}
        onFilterChange={(key, value) => {
          if (key === 'scope') setScopeFilter(value || '');
        }}
        onClearFilters={() => {
          setSearch('');
          setScopeFilter('');
        }}
        emptyMessage={isPendingTab ? 'No pending reviews' : 'No verified records'}
        emptySubtext={
          isPendingTab
            ? 'All periods have been reviewed. Check the Verified tab for completed verifications.'
            : 'No records match the current filter criteria.'
        }
        getRowId={(row) => row.id || `${row.period_id}-${row.scope}`}
      />

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
    </PageContainer>
  );
}
