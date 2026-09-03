// src/pages/admin/ai/AuditPanel.jsx
// Route /admin/ai/audit — read-only AI Audit Trail panel (filters + CSV export).
// Consumes GET /carbon-api/ai/audit/ via getAuditTrail (RULE_10 apiFetch only).
// Gated on ai:manage_console (CBAC). Never fabricated: loading spinner,
// offline paper, grounded empty state. RULE_8 tokens only; RULE_16 PageContainer.
import React, { Fragment, useEffect, useMemo, useState } from 'react';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  IconButton,
  MenuItem,
  Paper,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import CloudOffIcon from '@mui/icons-material/CloudOff';
import DownloadIcon from '@mui/icons-material/Download';
import RefreshIcon from '@mui/icons-material/Refresh';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import useDocumentTitle from '../../../hooks/useDocumentTitle';
import PageContainer from '../../../components/layout/PageContainer';
import { useAuth } from '../../../auth/AuthContext';
import { getAuditTrail } from '../../../api/aiPulse';
import { AI_MANAGE_CONSOLE, expandCapabilities, hasCap } from '../../../capabilities';

/** Format an ISO timestamp defensively (em-dash when missing/invalid). */
function formatTimestamp(value) {
  if (!value) return '—';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString();
}

/** Format a plain-string cell defensively (em-dash when empty). */
function formatText(value) {
  if (value === null || value === undefined || value === '') return '—';
  return String(value);
}

/** Quote one CSV field and double any inner double-quotes. */
function csvField(value) {
  const s = value === null || value === undefined ? '' : String(value);
  return `"${s.replace(/"/g, '""')}"`;
}

const ACTION_CHOICES = [
  { value: '', label: 'All actions' },
  { value: 'ai.tool_call', label: 'ai.tool_call' },
  { value: 'ai.consent_approved', label: 'ai.consent_approved' },
  { value: 'ai.consent_declined', label: 'ai.consent_declined' },
  { value: 'ai.memory_write', label: 'ai.memory_write' },
];

const EMPTY_FILTERS = { action: '', actor: '', start: '', end: '' };

export default function AuditPanel() {
  useDocumentTitle('AI Audit Trail');
  const { token, userCapabilities } = useAuth();

  const [rows, setRows] = useState([]);
  const [count, setCount] = useState(0);
  const [page, setPage] = useState(0); // 0-based (TablePagination)
  const [pageSize, setPageSize] = useState(50);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [draftFilters, setDraftFilters] = useState(EMPTY_FILTERS);
  const [expanded, setExpanded] = useState(null);

  const caps = useMemo(
    () => (userCapabilities || []).map((c) => (typeof c === 'string' ? c : c?.key || c?.capability)),
    [userCapabilities]
  );
  const canView = hasCap(expandCapabilities(caps), AI_MANAGE_CONSOLE);

  useEffect(() => {
    if (!canView) return undefined;
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const payload = await getAuditTrail(token, {
          action: filters.action,
          actor: filters.actor,
          start: filters.start,
          end: filters.end,
          page: page + 1, // backend is 1-based
          pageSize,
        });
        if (!cancelled) {
          setRows(payload?.results ?? []);
          setCount(payload?.count ?? 0);
          setOffline(false);
        }
      } catch {
        if (!cancelled) {
          setRows([]);
          setCount(0);
          setOffline(true);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token, filters, page, pageSize, canView]);

  const handleApply = () => {
    setFilters(draftFilters);
    setPage(0);
  };

  const handleClear = () => {
    setDraftFilters(EMPTY_FILTERS);
    setFilters(EMPTY_FILTERS);
    setPage(0);
  };

  // Re-trigger the fetch by giving `filters` a new identity (the effect
  // depends on it), so manual refresh re-fetches the current page/filters.
  const handleRefresh = () => setFilters((prev) => ({ ...prev }));

  const toggleExpand = (id) => setExpanded((prev) => (prev === id ? null : id));

  const handleExportCsv = () => {
    const header = ['timestamp', 'actor', 'action', 'target', 'detail'].join(',');
    const lines = [header];
    rows.forEach((row) => {
      const fields = [
        row.timestamp ?? '',
        row.actor ?? '',
        row.action ?? '',
        row.target ?? '',
        JSON.stringify(row.detail ?? {}),
      ];
      lines.push(fields.map(csvField).join(','));
    });
    const csv = lines.join('\n');
    const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'ai-audit.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  if (!canView) {
    return (
      <PageContainer>
        <Typography color="text.secondary">
          Access to the AI Audit Trail requires the AI manage console capability.
        </Typography>
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <Stack spacing={1.5} sx={{ flex: 1, minHeight: 0 }}>
        <Stack direction="row" spacing={1} alignItems="center">
          <Typography variant="h5" fontWeight={700} sx={{ flex: 1 }}>AI Audit Trail</Typography>
          <IconButton
            aria-label="Refresh audit trail"
            onClick={handleRefresh}
            disabled={loading}
            size="small"
          >
            <RefreshIcon />
          </IconButton>
          <Button
            startIcon={<DownloadIcon />}
            onClick={handleExportCsv}
            disabled={rows.length === 0}
            size="small"
          >
            Export CSV
          </Button>
        </Stack>
        <Typography variant="body2" color="text.secondary">
          Read-only audit trail of AI actions across the platform.
        </Typography>

        <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
          <Select
            value={draftFilters.action}
            onChange={(e) => setDraftFilters((f) => ({ ...f, action: e.target.value }))}
            size="small"
            displayEmpty
            aria-label="Action type"
            sx={{ minWidth: 200 }}
          >
            {ACTION_CHOICES.map((choice) => (
              <MenuItem key={choice.value} value={choice.value}>{choice.label}</MenuItem>
            ))}
          </Select>
          <TextField
            size="small"
            placeholder="Actor"
            value={draftFilters.actor}
            onChange={(e) => setDraftFilters((f) => ({ ...f, actor: e.target.value }))}
          />
          <TextField
            size="small"
            type="date"
            label="Start"
            value={draftFilters.start}
            onChange={(e) => setDraftFilters((f) => ({ ...f, start: e.target.value }))}
            InputLabelProps={{ shrink: true }}
          />
          <TextField
            size="small"
            type="date"
            label="End"
            value={draftFilters.end}
            onChange={(e) => setDraftFilters((f) => ({ ...f, end: e.target.value }))}
            InputLabelProps={{ shrink: true }}
          />
          <Button variant="outlined" onClick={handleApply} size="small">Apply</Button>
          <Button variant="text" onClick={handleClear} size="small">Clear</Button>
        </Stack>

        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
            <CircularProgress size={24} />
          </Box>
        ) : offline ? (
          <Paper variant="outlined" sx={{ p: 4, textAlign: 'center' }}>
            <CloudOffIcon fontSize="large" sx={{ color: 'text.secondary' }} />
            <Typography variant="subtitle1" sx={{ mt: 1 }} fontWeight={600}>Data unavailable</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              Data unavailable — the AI audit API is offline
            </Typography>
          </Paper>
        ) : rows.length === 0 ? (
          <Paper variant="outlined" sx={{ p: 4, textAlign: 'center' }}>
            <Typography color="text.secondary">No audit entries match the current filters.</Typography>
          </Paper>
        ) : (
          <>
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Timestamp</TableCell>
                    <TableCell>Actor</TableCell>
                    <TableCell>Action</TableCell>
                    <TableCell>Target</TableCell>
                    <TableCell align="right" />
                  </TableRow>
                </TableHead>
                <TableBody>
                  {rows.map((row) => {
                    const isExpanded = expanded === row.id;
                    return (
                      <Fragment key={row.id}>
                        <TableRow hover onClick={() => toggleExpand(row.id)} sx={{ cursor: 'pointer' }}>
                          <TableCell>{formatTimestamp(row.timestamp)}</TableCell>
                          <TableCell>{formatText(row.actor)}</TableCell>
                          <TableCell>
                            <Chip size="small" variant="outlined" label={formatText(row.action)} />
                          </TableCell>
                          <TableCell>{formatText(row.target)}</TableCell>
                          <TableCell align="right">
                            {isExpanded ? (
                              <ExpandLessIcon fontSize="small" color="action" />
                            ) : (
                              <ExpandMoreIcon fontSize="small" color="action" />
                            )}
                          </TableCell>
                        </TableRow>
                        {isExpanded && (
                          <TableRow>
                            <TableCell colSpan={5} sx={{ borderBottom: 'none', p: 0 }}>
                              <Box
                                component="pre"
                                sx={{
                                  m: 0,
                                  p: 1.5,
                                  bgcolor: 'action.hover',
                                  overflow: 'auto',
                                  maxHeight: 240,
                                  fontSize: '0.75rem',
                                  whiteSpace: 'pre-wrap',
                                  fontFamily: 'monospace',
                                }}
                              >
                                {JSON.stringify(row.detail ?? {}, null, 2)}
                              </Box>
                            </TableCell>
                          </TableRow>
                        )}
                      </Fragment>
                    );
                  })}
                </TableBody>
              </Table>
            </TableContainer>
            <TablePagination
              component="div"
              count={count}
              page={page}
              onPageChange={(event, newPage) => setPage(newPage)}
              rowsPerPage={pageSize}
              onRowsPerPageChange={(event) => {
                setPageSize(parseInt(event.target.value, 10));
                setPage(0);
              }}
              rowsPerPageOptions={[20, 50, 100, 200]}
            />
          </>
        )}
      </Stack>
    </PageContainer>
  );
}
