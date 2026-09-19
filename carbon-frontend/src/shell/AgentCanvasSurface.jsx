// src/shell/AgentCanvasSurface.jsx
// ADR-0043 Canvas view — exclusive OpsCanvasHost Job Map by plan_id (ADR-0041).
// Parent owns segment switching; this surface only loads + renders the board.
import React, { useCallback, useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Stack,
  Typography,
} from '@mui/material';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../auth/AuthContext';
import { useNotification } from '../components/NotificationProvider';
import { listArtifacts } from '../api/aiWorkspace';
import OpsCanvasHost from './OpsCanvasHost';

/**
 * @param {object} props
 * @param {string|null} props.planId
 * @param {string|null} [props.conversationId]
 * @param {boolean} [props.live] — poll while the plan is executing
 */
function AgentCanvasSurface({ planId, conversationId = null, live = false }) {
  const { t } = useTranslation('ai');
  const { token } = useAuth();
  const { notifyFromError } = useNotification();
  const [artifact, setArtifact] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    if (!token || !planId) {
      setArtifact(null);
      setLoading(false);
      setError(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      let maps = await listArtifacts(token, {
        artifact_type: 'job_map',
        plan_id: planId,
        limit: 10,
      });
      let list = Array.isArray(maps) ? maps : (maps?.results ?? []);
      // WA-S-SEG-04: live upserts may key by conversation; fall back when plan_id miss.
      if (!list.length && conversationId) {
        maps = await listArtifacts(token, {
          artifact_type: 'job_map',
          conversation_id: conversationId,
          limit: 20,
        });
        list = Array.isArray(maps) ? maps : (maps?.results ?? []);
        const matchPlan = list.find(
          (a) => String(a?.content_json?.plan_id || '') === String(planId),
        );
        if (matchPlan) {
          list = [matchPlan];
        } else {
          list = list.filter((a) => a?.content_json?.mode === 'agent').length
            ? list.filter((a) => a?.content_json?.mode === 'agent')
            : list;
        }
      }
      const agent = list.find((a) => a?.content_json?.mode === 'agent') || list[0] || null;
      setArtifact(agent);
    } catch (err) {
      setArtifact(null);
      setError(err);
      notifyFromError(err, t('jobMapLoadFailed'));
    } finally {
      setLoading(false);
    }
  }, [token, planId, conversationId, notifyFromError, t]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (cancelled) return;
      await load();
    })();
    if (!live || !planId) return () => { cancelled = true; };
    const tmr = setInterval(() => {
      if (!cancelled) load();
    }, 2500);
    return () => {
      cancelled = true;
      clearInterval(tmr);
    };
  }, [load, live, planId]);

  if (!planId) {
    return (
      <Typography variant="body2" color="text.secondary" sx={{ py: 3, fontSize: '0.75rem' }}>
        {t('jobMapNeedPlan')}
      </Typography>
    );
  }

  if (loading && !artifact) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }} data-testid="agent-canvas-loading">
        <CircularProgress size={22} />
      </Box>
    );
  }

  if (error && !artifact) {
    return (
      <Stack spacing={1} sx={{ py: 2 }} data-testid="agent-canvas-error">
        <Alert severity="error" sx={{ fontSize: '0.75rem' }}>
          {t('jobMapLoadFailed')}
        </Alert>
        <Button size="small" onClick={load} sx={{ alignSelf: 'flex-start', textTransform: 'none' }}>
          {t('retry')}
        </Button>
      </Stack>
    );
  }

  if (!artifact) {
    return (
      <Stack spacing={1} sx={{ py: 3 }} data-testid="agent-canvas-empty">
        <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
          {t('jobMapEmpty')}
        </Typography>
        {conversationId && (
          <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem' }}>
            {t('jobMapEmptyHint')}
          </Typography>
        )}
        <Button size="small" onClick={load} sx={{ alignSelf: 'flex-start', textTransform: 'none' }}>
          {t('retry')}
        </Button>
      </Stack>
    );
  }

  return (
    <Box data-testid="agent-canvas-board" sx={{ minHeight: 280 }}>
      <OpsCanvasHost artifact={artifact} readOnly />
    </Box>
  );
}

AgentCanvasSurface.propTypes = {
  planId: PropTypes.string,
  conversationId: PropTypes.string,
  live: PropTypes.bool,
};

export default AgentCanvasSurface;
