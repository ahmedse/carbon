// src/pages/admin/ai/control/EvidenceExplorerPanel.jsx
// ADR-0036 Phase 2 — unified evidence spine by run_id / conversation_id.
import React, { useState } from 'react';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Paper,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import useDocumentTitle from '../../../../hooks/useDocumentTitle';
import PageContainer from '../../../../components/layout/PageContainer';
import { useAuth } from '../../../../auth/AuthContext';
import { getEvidence } from '../../../../api/aiControlPlane';

export default function EvidenceExplorerPanel() {
  useDocumentTitle('Evidence Explorer');
  const { token } = useAuth();
  const [runId, setRunId] = useState('');
  const [conversationId, setConversationId] = useState('');
  const [loading, setLoading] = useState(false);
  const [payload, setPayload] = useState(null);
  const [error, setError] = useState('');

  const onSearch = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await getEvidence(token, {
        runId: runId.trim() || undefined,
        conversationId: conversationId.trim() || undefined,
      });
      setPayload(data);
    } catch (err) {
      setPayload(null);
      setError(err?.detail || err?.message || 'Evidence lookup failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <PageContainer>
      <Stack spacing={2}>
        <Typography variant="h5" fontWeight={700}>
          Evidence Explorer
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Reconstruct a run or conversation on one spine: run events, PDP decisions,
          human tasks, and audit rows.
        </Typography>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
          <TextField
            size="small"
            label="Run ID"
            value={runId}
            onChange={(e) => setRunId(e.target.value)}
            fullWidth
          />
          <TextField
            size="small"
            label="Conversation ID"
            value={conversationId}
            onChange={(e) => setConversationId(e.target.value)}
            fullWidth
          />
          <Button
            variant="contained"
            onClick={onSearch}
            disabled={loading || (!runId.trim() && !conversationId.trim())}
          >
            Trace
          </Button>
        </Stack>
        {loading && (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress size={24} />
          </Box>
        )}
        {error && (
          <Typography color="error" variant="body2">
            {error}
          </Typography>
        )}
        {payload && (
          <>
            <Stack direction="row" spacing={1} alignItems="center">
              <Chip size="small" label={`${payload.count} events`} />
              {payload.meta?.run_status && (
                <Chip size="small" variant="outlined" label={payload.meta.run_status} />
              )}
            </Stack>
            <Stack spacing={1}>
              {(payload.events || []).map((ev, idx) => (
                <Paper key={`${ev.t}-${ev.type}-${idx}`} variant="outlined" sx={{ p: 1.5 }}>
                  <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
                    <Chip size="small" label={ev.source} />
                    <Typography variant="body2" fontWeight={600}>
                      {ev.type}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ ml: 'auto' }}>
                      {ev.t || '—'}
                    </Typography>
                  </Stack>
                  <Box
                    component="pre"
                    sx={{
                      m: 0,
                      mt: 1,
                      p: 1,
                      bgcolor: 'action.hover',
                      borderRadius: 1,
                      fontSize: '0.75rem',
                      overflow: 'auto',
                      maxHeight: 160,
                    }}
                  >
                    {JSON.stringify(ev.detail || {}, null, 2)}
                  </Box>
                </Paper>
              ))}
              {!payload.events?.length && (
                <Typography variant="body2" color="text.secondary">
                  No events found for this lookup.
                </Typography>
              )}
            </Stack>
          </>
        )}
      </Stack>
    </PageContainer>
  );
}
