// src/pages/admin/ai/control/EvidenceExplorerPanel.jsx
// ADR-0036 Phase 2 — unified evidence spine by run_id / conversation_id.
// Deep-links from thin grids: ?run_id= / ?conversation_id= auto-fill + Trace.
import React, { useEffect, useState } from 'react';
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
import { useSearchParams } from 'react-router-dom';
import useDocumentTitle from '../../../../hooks/useDocumentTitle';
import { useTranslation } from 'react-i18next';
import PageContainer from '../../../../components/layout/PageContainer';
import { useAuth } from '../../../../auth/AuthContext';
import { getEvidence } from '../../../../api/aiControlPlane';

export default function EvidenceExplorerPanel() {
  const { t } = useTranslation('ai');
  useDocumentTitle(t('control.evidenceExplorer.title'));
  const { token } = useAuth();
  const [searchParams] = useSearchParams();
  const [runId, setRunId] = useState('');
  const [conversationId, setConversationId] = useState('');
  const [loading, setLoading] = useState(false);
  const [payload, setPayload] = useState(null);
  const [error, setError] = useState('');

  const onSearch = async () => {
    const rid = runId.trim();
    const cid = conversationId.trim();
    if (!rid && !cid) return;
    setLoading(true);
    setError('');
    try {
      const data = await getEvidence(token, {
        runId: rid || undefined,
        conversationId: cid || undefined,
      });
      setPayload(data);
    } catch (err) {
      setPayload(null);
      setError(err?.detail || err?.message || 'Evidence lookup failed');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const qRun = (searchParams.get('run_id') || '').trim();
    const qConv = (searchParams.get('conversation_id') || '').trim();
    if (!qRun && !qConv) return undefined;

    setRunId(qRun);
    setConversationId(qConv);

    let cancelled = false;
    (async () => {
      setLoading(true);
      setError('');
      try {
        const data = await getEvidence(token, {
          runId: qRun || undefined,
          conversationId: qConv || undefined,
        });
        if (!cancelled) setPayload(data);
      } catch (err) {
        if (!cancelled) {
          setPayload(null);
          setError(err?.detail || err?.message || 'Evidence lookup failed');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [searchParams, token]);

  return (
    <PageContainer>
      <Stack spacing={2}>
        <Typography variant="h5" fontWeight={700}>
          {t('control.evidenceExplorer.title')}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {t('control.evidenceExplorer.subtitle')}
        </Typography>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
          <TextField
            size="small"
            label={t('control.evidenceExplorer.runId')}
            value={runId}
            onChange={(e) => setRunId(e.target.value)}
            fullWidth
          />
          <TextField
            size="small"
            label={t('control.evidenceExplorer.conversationId')}
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
                  {t('control.evidenceExplorer.empty')}
                </Typography>
              )}
            </Stack>
          </>
        )}
      </Stack>
    </PageContainer>
  );
}
