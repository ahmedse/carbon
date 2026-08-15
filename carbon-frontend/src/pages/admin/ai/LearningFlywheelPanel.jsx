// src/pages/admin/ai/LearningFlywheelPanel.jsx
// Route /admin/ai/learning-flywheel — the "Learn-facts console".
// Read-only flywheel status backed by /ai/pulse/learning-status/ plus an
// on-demand "Run sweep" write action backed by /ai/pulse/learning-status/run/.
// Never fabricated: loading spinner, offline paper, grounded empty states.
// RULE_8 tokens only; RULE_10 apiFetch only (via src/api/aiPulse.js); RULE_16.
// The Run-sweep action is gated on ai:manage_console (view is ai:view_console).
import React, { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Paper,
  Stack,
  Typography,
} from '@mui/material';
import CloudOffIcon from '@mui/icons-material/CloudOff';
import StorageIcon from '@mui/icons-material/Storage';
import PsychologyIcon from '@mui/icons-material/Psychology';
import FeedbackIcon from '@mui/icons-material/Feedback';
import AutorenewIcon from '@mui/icons-material/Autorenew';
import useDocumentTitle from '../../../hooks/useDocumentTitle';
import PageContainer from '../../../components/layout/PageContainer';
import CarbonDataGrid from '../../../components/DataGrid/CarbonDataGrid';
import { useAuth } from '../../../auth/AuthContext';
import { getLearningStatus, runLearningSweep } from '../../../api/aiPulse';
import { AI_MANAGE_CONSOLE, expandCapabilities, hasCap } from '../../../capabilities';

/** Format an integer counter defensively. */
function formatInt(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
  return Number(value).toLocaleString();
}

/** Format an ISO timestamp defensively. */
function formatDate(value) {
  if (!value) return '—';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString();
}

const OUTCOME_LABELS = {
  accepted: 'Accepted',
  rejected: 'Rejected',
  corrected: 'Corrected',
};

export default function LearningFlywheelPanel() {
  useDocumentTitle('Learning Flywheel');
  const { token, userCapabilities } = useAuth();

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);
  const [running, setRunning] = useState(false);
  const [sweepResult, setSweepResult] = useState(null);
  const [sweepError, setSweepError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const payload = await getLearningStatus(token);
        if (!cancelled) {
          setData(payload);
          setOffline(false);
        }
      } catch {
        if (!cancelled) {
          setData(null);
          setOffline(true);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  const caps = useMemo(
    () => (userCapabilities || []).map((c) => (typeof c === 'string' ? c : c?.key || c?.capability)),
    [userCapabilities]
  );
  const canRun = hasCap(expandCapabilities(caps), AI_MANAGE_CONSOLE);

  const handleRunSweep = async () => {
    setRunning(true);
    setSweepResult(null);
    setSweepError(null);
    try {
      const payload = await runLearningSweep(token);
      setSweepResult(payload.sweep);
      setData(payload.status);
      setOffline(false);
    } catch (err) {
      setSweepError(err?.message || 'Sweep failed — the learning flywheel API is unavailable');
    } finally {
      setRunning(false);
    }
  };

  const factsRows = useMemo(
    () => (data?.facts?.recent ?? []).map((row) => ({ ...row, id: row.id ?? String(Math.random()) })),
    [data]
  );
  const feedbackRows = useMemo(
    () => (data?.feedback_records?.recent ?? []).map((row) => ({ ...row, id: row.id ?? String(Math.random()) })),
    [data]
  );

  const factColumns = useMemo(
    () => [
      { field: 'category', headerName: 'Category', width: 140, valueFormatter: ({ value }) => value ?? '—' },
      { field: 'content', headerName: 'Fact', minWidth: 320, flex: 1 },
      { field: 'confidence', headerName: 'Confidence', width: 120, valueFormatter: ({ value }) => formatInt(value) },
      { field: 'created_at', headerName: 'Created', width: 200, valueFormatter: ({ value }) => formatDate(value) },
    ],
    []
  );

  const feedbackColumns = useMemo(
    () => [
      { field: 'signal_type', headerName: 'Signal', width: 150, valueFormatter: ({ value }) => value ?? '—' },
      { field: 'message_id', headerName: 'Message', width: 220, valueFormatter: ({ value }) => value ?? '—' },
      { field: 'user_comment', headerName: 'Comment', minWidth: 240, flex: 1, valueFormatter: ({ value }) => value || '—' },
      { field: 'quality_score', headerName: 'Quality', width: 110, valueFormatter: ({ value }) => formatInt(value) },
      { field: 'created_at', headerName: 'Created', width: 200, valueFormatter: ({ value }) => formatDate(value) },
    ],
    []
  );

  const outcomeEntries = Object.entries(data?.by_outcome ?? {});

  return (
    <PageContainer>
      <Stack spacing={1.5} sx={{ flex: 1, minHeight: 0 }}>
        <Stack direction="row" spacing={1} alignItems="center">
          <Typography variant="h5" fontWeight={700} sx={{ flex: 1 }}>Learning Flywheel</Typography>
          {data && !offline && (
            <Chip
              size="small"
              color={data?.durable ? 'success' : 'warning'}
              icon={<StorageIcon />}
              label={data?.durable ? 'Durable store' : 'In-memory'}
            />
          )}
        </Stack>
        <Typography variant="body2" color="text.secondary">
          Feedback → learning → long-term memory. Shows judged messages pending consumption,
          the durable-fact ledger, and the feedback signals that feed the flywheel.
        </Typography>

        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
            <CircularProgress size={24} />
          </Box>
        ) : offline || !data ? (
          <Paper variant="outlined" sx={{ p: 4, textAlign: 'center' }}>
            <CloudOffIcon fontSize="large" sx={{ color: 'text.secondary' }} />
            <Typography variant="subtitle1" sx={{ mt: 1 }} fontWeight={600}>Data unavailable</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              Data unavailable — the learning flywheel API is offline
            </Typography>
          </Paper>
        ) : (
          <>
            {/* ── Flywheel status ── */}
            <Paper variant="outlined" sx={{ p: 2 }}>
              <Typography variant="overline" color="text.secondary">Flywheel status</Typography>
              <Stack direction="row" spacing={4} sx={{ mt: 0.5 }} flexWrap="wrap">
                <Box>
                  <Typography variant="body2" color="text.secondary">Pending</Typography>
                  <Typography variant="h6" fontWeight={700}>{formatInt(data?.pending)}</Typography>
                </Box>
                <Box>
                  <Typography variant="body2" color="text.secondary">Processed</Typography>
                  <Typography variant="h6" fontWeight={700}>{formatInt(data?.processed)}</Typography>
                </Box>
                <Box>
                  <Typography variant="body2" color="text.secondary">Feedback records</Typography>
                  <Typography variant="h6" fontWeight={700}>{formatInt(data?.feedback_records?.count)}</Typography>
                </Box>
                <Box>
                  <Typography variant="body2" color="text.secondary">Durable facts</Typography>
                  <Typography variant="h6" fontWeight={700}>
                    {formatInt((data?.facts?.counts?.learned ?? 0) + (data?.facts?.counts?.correction ?? 0))}
                  </Typography>
                </Box>
              </Stack>

              {/* Outcome breakdown */}
              {outcomeEntries.length > 0 ? (
                <Stack direction="row" spacing={1} sx={{ mt: 1.5 }} flexWrap="wrap">
                  {outcomeEntries.map(([outcome, count]) => (
                    <Chip
                      key={outcome}
                      size="small"
                      variant="outlined"
                      label={`${OUTCOME_LABELS[outcome] ?? outcome}: ${formatInt(count)}`}
                    />
                  ))}
                </Stack>
              ) : (
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1.5 }}>
                  No learned outcomes yet — judge a message (accept / reject / correct) to start the flywheel.
                </Typography>
              )}
            </Paper>

            {/* ── Run sweep action ── */}
            <Paper variant="outlined" sx={{ p: 2 }}>
              <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap">
                <Box sx={{ flex: 1, minWidth: 260 }}>
                  <Typography variant="overline" color="text.secondary">Manual sweep</Typography>
                  <Typography variant="body2" color="text.secondary">
                    Consume every pending judged message into the feedback ledger and long-term memory now
                    (the scheduler also runs this automatically).
                  </Typography>
                </Box>
                {canRun ? (
                  <Button
                    variant="contained"
                    startIcon={<AutorenewIcon />}
                    disabled={running || data?.pending === 0}
                    onClick={handleRunSweep}
                  >
                    {running ? 'Running…' : 'Run sweep'}
                  </Button>
                ) : (
                  <Chip size="small" variant="outlined" label="Requires ai:manage_console" />
                )}
              </Stack>

              {sweepResult && (
                <Alert severity={sweepResult.errors > 0 ? 'warning' : 'success'} sx={{ mt: 1.5 }}>
                  Sweep complete — {formatInt(sweepResult.processed)} processed
                  (accepted {formatInt(sweepResult.accepted)}, rejected {formatInt(sweepResult.rejected)},
                  corrected {formatInt(sweepResult.corrected)}
                  {sweepResult.errors > 0 ? `, ${formatInt(sweepResult.errors)} errors` : ''}).
                </Alert>
              )}
              {sweepError && (
                <Alert severity="error" sx={{ mt: 1.5 }}>{sweepError}</Alert>
              )}
            </Paper>

            {/* ── Recent durable facts ── */}
            <Paper variant="outlined" sx={{ p: 2 }}>
              <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
                <PsychologyIcon color="primary" fontSize="small" />
                <Typography variant="overline" color="text.secondary">Recent durable facts</Typography>
              </Stack>
              <CarbonDataGrid
                columns={factColumns}
                rows={factsRows}
                loading={false}
                getRowId={(row) => row.id}
                emptyMessage="No durable facts yet — accept or correct answers to capture knowledge."
              />
            </Paper>

            {/* ── Recent feedback signals ── */}
            <Paper variant="outlined" sx={{ p: 2 }}>
              <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
                <FeedbackIcon color="primary" fontSize="small" />
                <Typography variant="overline" color="text.secondary">Recent feedback signals</Typography>
              </Stack>
              <CarbonDataGrid
                columns={feedbackColumns}
                rows={feedbackRows}
                loading={false}
                getRowId={(row) => row.id}
                emptyMessage="No feedback signals recorded yet."
              />
            </Paper>
          </>
        )}
      </Stack>
    </PageContainer>
  );
}
