// File: src/pages/admin/AuditLogPage.jsx
// Admin Audit Log Page - comprehensive record of all system changes and user actions

import React, { useState, useEffect, useMemo } from 'react';
import {
  Box,
  Container,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
  Button,
  Stack,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  CircularProgress,
  Alert,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Grid,
  Card,
  CardContent,
  Divider,
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  Download as DownloadIcon,
  Info as InfoIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Check as CheckIcon,
  Close as CloseIcon,
  Warning as WarningIcon,
} from '@mui/icons-material';
import { useAuth } from '../../auth/AuthContext';
import { apiFetch } from '../../api/api';
import { API_ROUTES } from '../../config';

const ACTION_COLOR = {
  CREATE: '#10b981',
  UPDATE: '#3b82f6',
  DELETE: '#ef4444',
  READ: '#6b7280',
  LOGIN: '#8b5cf6',
  LOGOUT: '#9ca3af',
  EXPORT: '#f59e0b',
  IMPORT: '#06b6d4',
};

const ACTION_LABEL = {
  CREATE: 'Create',
  UPDATE: 'Update',
  DELETE: 'Delete',
  READ: 'Read',
  LOGIN: 'Login',
  LOGOUT: 'Logout',
  EXPORT: 'Export',
  IMPORT: 'Import',
};

function ActionChip({ action }) {
  const color = ACTION_COLOR[action] || '#71717a';
  const label = ACTION_LABEL[action] || action;
  return (
    <Chip
      label={label}
      size="small"
      sx={{
        backgroundColor: `${color}20`,
        color: color,
        fontWeight: 600,
        fontSize: '0.75rem',
      }}
    />
  );
}

function AuditDetailDialog({ open, onClose, audit }) {
  if (!audit) return null;

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Audit Log Details</DialogTitle>
      <DialogContent sx={{ pt: 2 }}>
        <Stack spacing={2}>
          <Box>
            <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600, textTransform: 'uppercase' }}>
              ID
            </Typography>
            <Typography variant="body2">{audit.id}</Typography>
          </Box>

          <Box>
            <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600, textTransform: 'uppercase' }}>
              User
            </Typography>
            <Typography variant="body2">{audit.user || 'System'}</Typography>
          </Box>

          <Box>
            <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600, textTransform: 'uppercase' }}>
              Action
            </Typography>
            <ActionChip action={audit.action} />
          </Box>

          <Box>
            <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600, textTransform: 'uppercase' }}>
              Entity Type
            </Typography>
            <Typography variant="body2">{audit.entity_type || 'Unknown'}</Typography>
          </Box>

          <Box>
            <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600, textTransform: 'uppercase' }}>
              Entity ID
            </Typography>
            <Typography variant="body2">{audit.entity_id || '—'}</Typography>
          </Box>

          <Box>
            <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600, textTransform: 'uppercase' }}>
              Timestamp
            </Typography>
            <Typography variant="body2">
              {new Date(audit.timestamp).toLocaleString()}
            </Typography>
          </Box>

          <Box>
            <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600, textTransform: 'uppercase' }}>
              IP Address
            </Typography>
            <Typography variant="body2">{audit.ip_address || '—'}</Typography>
          </Box>

          <Box>
            <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600, textTransform: 'uppercase' }}>
              Status
            </Typography>
            <Chip
              icon={audit.status === 'success' ? <CheckIcon /> : <WarningIcon />}
              label={audit.status}
              size="small"
              color={audit.status === 'success' ? 'success' : 'warning'}
              sx={{ fontWeight: 600 }}
            />
          </Box>

          {audit.changes && Object.keys(audit.changes).length > 0 && (
            <Box>
              <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600, textTransform: 'uppercase', display: 'block', mb: 1 }}>
                Changes
              </Typography>
              <Paper sx={{ p: 1.5, bgcolor: 'background.default' }}>
                <Typography component="pre" variant="caption" sx={{ fontSize: '0.65rem', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                  {JSON.stringify(audit.changes, null, 2)}
                </Typography>
              </Paper>
            </Box>
          )}
        </Stack>
      </DialogContent>
    </Dialog>
  );
}

export default function AuditLogPage() {
  const { user } = useAuth();
  const [audits, setAudits] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [selectedAudit, setSelectedAudit] = useState(null);

  // Filter state
  const [filterAction, setFilterAction] = useState('');
  const [filterUser, setFilterUser] = useState('');
  const [filterDateFrom, setFilterDateFrom] = useState('');
  const [filterDateTo, setFilterDateTo] = useState('');

  const fetchAudits = async () => {
    setLoading(true);
    setError(null);
    try {
      const token = localStorage.getItem('access');
      const params = new URLSearchParams();
      if (filterAction) params.append('action', filterAction);
      if (filterUser) params.append('user', filterUser);
      if (filterDateFrom) params.append('created_from', filterDateFrom);
      if (filterDateTo) params.append('created_to', filterDateTo);

      const endpoint =
        params.toString()
          ? `${API_ROUTES.auditLogs}?${params.toString()}`
          : API_ROUTES.auditLogs;

      const data = await apiFetch(endpoint, { token });
      setAudits(Array.isArray(data) ? data : data?.results || []);
    } catch (err) {
      setError(err.message || 'Failed to load audit logs');
      console.error('Failed to fetch audits:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAudits();
  }, [filterAction, filterUser, filterDateFrom, filterDateTo]);

  const handleRefresh = () => {
    fetchAudits();
  };

  const handleDownload = () => {
    const csv = [
      ['ID', 'User', 'Action', 'Entity Type', 'Entity ID', 'Timestamp', 'IP Address', 'Status'].join(','),
      ...audits.map((a) =>
        [a.id, a.user || 'System', a.action, a.entity_type, a.entity_id, a.timestamp, a.ip_address, a.status].join(',')
      ),
    ].join('\n');

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `audit-log-${new Date().toISOString()}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const stats = useMemo(() => {
    const actionCounts = {};
    audits.forEach((a) => {
      actionCounts[a.action] = (actionCounts[a.action] || 0) + 1;
    });
    return actionCounts;
  }, [audits]);

  return (
    <Container maxWidth="lg" sx={{ py: 3 }}>
      {/* Header */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" sx={{ fontWeight: 700, mb: 1 }}>
          Audit Log
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Complete record of all system changes, user actions, and security events
        </Typography>
      </Box>

      {/* Stats */}
      <Grid container spacing={2} sx={{ mb: 4 }}>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Card>
            <CardContent>
              <Typography color="text.secondary" variant="caption" sx={{ fontWeight: 600, textTransform: 'uppercase' }}>
                Total Events
              </Typography>
              <Typography variant="h4" sx={{ fontWeight: 700, mt: 1 }}>
                {audits.length}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        {Object.entries(stats).map(([action, count]) => (
          <Grid size={{ xs: 12, sm: 6, md: 3 }} key={action}>
            <Card>
              <CardContent>
                <Typography color="text.secondary" variant="caption" sx={{ fontWeight: 600, textTransform: 'uppercase' }}>
                  {ACTION_LABEL[action] || action}
                </Typography>
                <Typography variant="h4" sx={{ fontWeight: 700, mt: 1, color: ACTION_COLOR[action] }}>
                  {count}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      <Divider sx={{ my: 3 }} />

      {/* Filters */}
      <Paper sx={{ p: 2.5, mb: 3 }}>
        <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
          Filters
        </Typography>
        <Grid container spacing={2}>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <FormControl fullWidth size="small">
              <InputLabel>Action</InputLabel>
              <Select
                label="Action"
                value={filterAction}
                onChange={(e) => setFilterAction(e.target.value)}
              >
                <MenuItem value="">All Actions</MenuItem>
                {Object.entries(ACTION_LABEL).map(([key, label]) => (
                  <MenuItem key={key} value={key}>{label}</MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <TextField
              fullWidth
              size="small"
              label="User"
              value={filterUser}
              onChange={(e) => setFilterUser(e.target.value)}
              placeholder="Filter by username"
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <TextField
              fullWidth
              size="small"
              label="From"
              type="date"
              value={filterDateFrom}
              onChange={(e) => setFilterDateFrom(e.target.value)}
              InputLabelProps={{ shrink: true }}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <TextField
              fullWidth
              size="small"
              label="To"
              type="date"
              value={filterDateTo}
              onChange={(e) => setFilterDateTo(e.target.value)}
              InputLabelProps={{ shrink: true }}
            />
          </Grid>
        </Grid>
      </Paper>

      {/* Actions */}
      <Stack direction="row" spacing={1} sx={{ mb: 3 }}>
        <Button
          startIcon={<RefreshIcon />}
          onClick={handleRefresh}
          disabled={loading}
          variant="outlined"
        >
          Refresh
        </Button>
        <Button
          startIcon={<DownloadIcon />}
          onClick={handleDownload}
          disabled={audits.length === 0}
          variant="outlined"
        >
          Export CSV
        </Button>
      </Stack>

      {/* Error Alert */}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {/* Table */}
      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      ) : audits.length === 0 ? (
        <Alert severity="info">No audit logs found matching the filters</Alert>
      ) : (
        <TableContainer component={Paper}>
          <Table>
            <TableHead sx={{ bgcolor: 'action.hover' }}>
              <TableRow>
                <TableCell sx={{ fontWeight: 700, fontSize: '0.8rem', textTransform: 'uppercase' }}>ID</TableCell>
                <TableCell sx={{ fontWeight: 700, fontSize: '0.8rem', textTransform: 'uppercase' }}>User</TableCell>
                <TableCell sx={{ fontWeight: 700, fontSize: '0.8rem', textTransform: 'uppercase' }}>Action</TableCell>
                <TableCell sx={{ fontWeight: 700, fontSize: '0.8rem', textTransform: 'uppercase' }}>Entity</TableCell>
                <TableCell sx={{ fontWeight: 700, fontSize: '0.8rem', textTransform: 'uppercase' }}>Timestamp</TableCell>
                <TableCell sx={{ fontWeight: 700, fontSize: '0.8rem', textTransform: 'uppercase' }}>Status</TableCell>
                <TableCell sx={{ fontWeight: 700, fontSize: '0.8rem', textTransform: 'uppercase' }}>Details</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {audits.map((audit) => (
                <TableRow key={audit.id} sx={{ '&:hover': { bgcolor: 'action.hover' } }}>
                  <TableCell sx={{ fontSize: '0.75rem', fontFamily: 'monospace' }}>
                    {String(audit.id).slice(0, 8)}
                  </TableCell>
                  <TableCell sx={{ fontSize: '0.8rem' }}>
                    {audit.user || '(System)'}
                  </TableCell>
                  <TableCell>
                    <ActionChip action={audit.action} />
                  </TableCell>
                  <TableCell sx={{ fontSize: '0.8rem' }}>
                    {audit.entity_type}
                    {audit.entity_id && ` #${audit.entity_id}`}
                  </TableCell>
                  <TableCell sx={{ fontSize: '0.75rem' }}>
                    {new Date(audit.timestamp).toLocaleString()}
                  </TableCell>
                  <TableCell>
                    <Chip
                      icon={audit.status === 'success' ? <CheckIcon /> : <CloseIcon />}
                      label={audit.status}
                      size="small"
                      color={audit.status === 'success' ? 'success' : 'error'}
                      variant="outlined"
                    />
                  </TableCell>
                  <TableCell>
                    <Button
                      size="small"
                      startIcon={<InfoIcon />}
                      onClick={() => {
                        setSelectedAudit(audit);
                        setDetailOpen(true);
                      }}
                    >
                      View
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {/* Detail Dialog */}
      <AuditDetailDialog open={detailOpen} onClose={() => setDetailOpen(false)} audit={selectedAudit} />
    </Container>
  );
}
