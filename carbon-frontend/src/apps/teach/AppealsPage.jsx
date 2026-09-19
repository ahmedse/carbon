// Teach appeals inbox — resolve student review requests (Phase D).

import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Alert, Box, Button, Chip, Drawer, Paper, Stack, Table, TableBody, TableCell,
  TableHead, TableRow, TextField, Typography,
} from '@mui/material';
import RateReviewIcon from '@mui/icons-material/RateReview';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../components/Page/ErrorAlert';
import EmptyState from '../../components/Page/EmptyState';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import { fetchAppeals, resolveAppeal } from '../../api/gradevance';
import SkipToMain from '../gradevance/SkipToMain';

export default function AppealsPage() {
  useDocumentTitle('Teach · Appeals');
  const { token } = useAuth();
  const navigate = useNavigate();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selected, setSelected] = useState(null);
  const [resolution, setResolution] = useState('');

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    fetchAppeals(token, { status: 'open' })
      .then((data) => setRows(data.results || data || []))
      .catch((err) => setError(err?.message || 'Failed to load appeals'))
      .finally(() => setLoading(false));
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  const openResolve = (row) => {
    setSelected(row);
    setResolution('');
    setDrawerOpen(true);
  };

  const onResolve = async (status) => {
    if (!selected?.id || !resolution.trim()) return;
    setBusy(true);
    setError(null);
    setMsg(null);
    try {
      await resolveAppeal(token, selected.id, {
        resolution: resolution.trim(),
        status,
      });
      setMsg(`Appeal ${status}`);
      setDrawerOpen(false);
      setSelected(null);
      load();
    } catch (err) {
      setError(err?.message || 'Resolve failed');
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <PageContainer>
        <PageHeader icon={RateReviewIcon} title="Appeals" subtitle="Student review requests" />
        <LoadingSkeleton variant="table" />
      </PageContainer>
    );
  }

  if (error && rows.length === 0) {
    return (
      <PageContainer>
        <PageHeader icon={RateReviewIcon} title="Appeals" />
        <ErrorAlert message={error} onRetry={load} />
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <SkipToMain targetId="teach-appeals" />
      <Box component="main" id="teach-appeals" tabIndex={-1} aria-label="Appeals inbox">
        <PageHeader
          icon={RateReviewIcon}
          title="Appeals"
          subtitle="Open student review requests for your courses."
          actions={(
            <Button size="small" variant="outlined" onClick={() => navigate('/teach/marking')}>
              Marking queue
            </Button>
          )}
        />
        {error && <ErrorAlert message={error} onRetry={load} />}
        {msg && <Alert severity="success" sx={{ mb: 1.5 }} role="status">{msg}</Alert>}

        {rows.length === 0 ? (
          <EmptyState
            icon={<RateReviewIcon />}
            title="No open appeals"
            description="When a student requests a review of a released run, it appears here."
          />
        ) : (
          <Paper component="section" aria-label="Open appeals">
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Student</TableCell>
                  <TableCell>Assignment</TableCell>
                  <TableCell>Reason</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Opened</TableCell>
                  <TableCell />
                </TableRow>
              </TableHead>
              <TableBody>
                {rows.map((row) => {
                  const runId = row.run_id || row.run;
                  return (
                    <TableRow key={row.id} hover>
                      <TableCell>
                        {row.student_name || row.student_user_email || row.student_user || '—'}
                      </TableCell>
                      <TableCell>{row.assignment_title || row.assignment || '—'}</TableCell>
                      <TableCell>
                        <Typography variant="caption" color="text.secondary">
                          {(row.reason || '').slice(0, 80)}
                          {(row.reason || '').length > 80 ? '…' : ''}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip size="small" label={row.status || 'open'} />
                      </TableCell>
                      <TableCell>
                        <Typography variant="caption">
                          {row.created_at ? new Date(row.created_at).toLocaleString() : '—'}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Stack direction="row" spacing={0.5}>
                          {runId && (
                            <Button size="small" onClick={() => navigate(`/teach/runs/${runId}`)}>
                              Open run
                            </Button>
                          )}
                          <Button size="small" variant="outlined" onClick={() => openResolve(row)}>
                            Resolve
                          </Button>
                        </Stack>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </Paper>
        )}
      </Box>

      <Drawer anchor="right" open={drawerOpen} onClose={() => setDrawerOpen(false)}>
        <Box sx={{ width: 360, p: 2 }} role="dialog" aria-label="Resolve appeal">
          <Typography variant="h6" sx={{ mb: 1 }}>Resolve appeal</Typography>
          {selected && (
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5, whiteSpace: 'pre-wrap' }}>
              {selected.reason}
            </Typography>
          )}
          <TextField
            size="small"
            label="Resolution"
            value={resolution}
            onChange={(e) => setResolution(e.target.value)}
            multiline
            minRows={3}
            fullWidth
            sx={{ mb: 2 }}
            required
          />
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            <Button
              size="small"
              variant="contained"
              color="success"
              disabled={busy || !resolution.trim()}
              onClick={() => onResolve('accepted')}
              aria-busy={busy}
            >
              Accept
            </Button>
            <Button
              size="small"
              variant="contained"
              color="error"
              disabled={busy || !resolution.trim()}
              onClick={() => onResolve('rejected')}
              aria-busy={busy}
            >
              Reject
            </Button>
            <Button size="small" onClick={() => setDrawerOpen(false)}>Cancel</Button>
          </Stack>
        </Box>
      </Drawer>
    </PageContainer>
  );
}
