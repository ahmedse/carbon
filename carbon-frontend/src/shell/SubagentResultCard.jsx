// src/shell/SubagentResultCard.jsx
// Wave I4-F — a self-contained subagent result card that owns its own
// progress polling. One card per dispatched subagent, nested under the
// AITaskPanel "Subagents" section (never flattened into run steps). Polls
// GET …/subagents/{id}/ every ~1.5s (backing off to ~3s after ~5 polls)
// until the subagent reaches a terminal status, then stops — no leaked
// timers. Outcome copy + icon+label only (RULE_23); theme tokens only
// (RULE_8).
import { useEffect, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Collapse,
  Paper,
  Stack,
  Typography,
} from '@mui/material';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import CloudOffIcon from '@mui/icons-material/CloudOff';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';
import { useTranslation } from 'react-i18next';
import { getSubagent } from '../api/aiWorkspace';
import { KeyValueOutput } from '../components/ai/StepOutputRenderer';
import AIGeneratedBadge from './AIGeneratedBadge';

// Poll cadence: start fast, back off after ~5 polls to bound chatter.
const FAST_POLL_MS = 1500;
const SLOW_POLL_MS = 3000;
const BACKOFF_AFTER_POLLS = 5;

function statusIcon(status) {
  if (status === 'running') {
    return <CircularProgress size={12} thickness={6} sx={{ color: 'primary.main' }} />;
  }
  if (status === 'completed') {
    return <CheckCircleOutlineIcon sx={{ fontSize: 15, color: 'success.main' }} />;
  }
  if (status === 'failed') {
    return <CloudOffIcon sx={{ fontSize: 15, color: 'error.main' }} />;
  }
  return <HelpOutlineIcon sx={{ fontSize: 15, color: 'text.secondary' }} />;
}

function SubagentResultCard({ subagent, token, conversationId, onResolved }) {
  const { t } = useTranslation('ai');
  const [sub, setSub] = useState(subagent);
  const [detailOpen, setDetailOpen] = useState(false);
  const [pollFailed, setPollFailed] = useState(false);

  // Keep the latest onResolved in a ref so the poll effect can stay keyed on
  // [status, conversationId, token] without re-running on every parent render.
  const onResolvedRef = useRef(onResolved);
  onResolvedRef.current = onResolved;

  useEffect(() => {
    const status = sub.status;

    // Terminal — announce once and never poll. `not_found` is a local sentinel
    // (404/403 on status) and needs no onResolved callback.
    if (status === 'completed' || status === 'failed') {
      onResolvedRef.current?.(sub);
      return undefined;
    }
    if (status === 'not_found') {
      return undefined;
    }

    let timer = null;
    let cancelled = false;
    let pollCount = 0;

    const schedule = (delay) => {
      timer = setTimeout(async () => {
        if (cancelled) return;
        try {
          const next = await getSubagent(token, conversationId, sub.id);
          if (cancelled) return;
          setPollFailed(false);
          setSub(next);
          // A terminal `next` re-runs this effect (status changed) which takes
          // the terminal branch above, calls onResolved, and stops polling.
          if (next.status === 'completed' || next.status === 'failed' || next.status === 'not_found') {
            return;
          }
          pollCount += 1;
          schedule(pollCount >= BACKOFF_AFTER_POLLS ? SLOW_POLL_MS : FAST_POLL_MS);
        } catch (err) {
          if (cancelled) return;
          if (err?.status === 404 || err?.status === 403) {
            setSub((prev) => ({ ...prev, status: 'not_found' }));
            return;
          }
          setPollFailed(true);
          pollCount += 1;
          schedule(pollCount >= BACKOFF_AFTER_POLLS ? SLOW_POLL_MS : FAST_POLL_MS);
        }
      }, delay);
    };

    schedule(FAST_POLL_MS);

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [sub.status, conversationId, token]);

  const terminal =
    sub.status === 'completed' || sub.status === 'failed' || sub.status === 'not_found';
  const hasScope =
    sub.scope_restriction &&
    typeof sub.scope_restriction === 'object' &&
    Object.keys(sub.scope_restriction).length > 0;
  const statusLabel = {
    pending: t('statusPending'),
    running: t('statusRunning'),
    completed: t('statusCompleted'),
    failed: t('statusFailed'),
    not_found: t('statusNotFound'),
  }[sub.status] || sub.status;
  const statusColor =
    sub.status === 'completed'
      ? 'success'
      : sub.status === 'failed'
        ? 'error'
        : sub.status === 'running'
          ? 'primary'
          : 'default';

  return (
    <Paper variant="outlined" sx={{ p: 1, bgcolor: 'background.paper' }}>
      <Stack spacing={1}>
        <Stack direction="row" alignItems="center" spacing={1}>
          <AIGeneratedBadge label={t('subagent')} />
          <Typography variant="body2" sx={{ flex: 1, minWidth: 0, fontSize: '0.75rem', wordBreak: 'break-word' }}>
            {sub.name}
          </Typography>
          <Box aria-live="polite" sx={{ flexShrink: 0 }}>
            <Chip size="small" variant="outlined" color={statusColor} icon={statusIcon(sub.status)} label={statusLabel} />
          </Box>
        </Stack>

        {hasScope && (
          <Box>
            <Typography
              variant="caption"
              sx={{
                display: 'block',
                fontWeight: 600,
                fontSize: '0.625rem',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                color: 'text.secondary',
              }}
            >
              {t('scopeRestrictionLabel')}
            </Typography>
            <KeyValueOutput value={sub.scope_restriction} />
          </Box>
        )}

        {sub.result_summary ? (
          <Box>
            <Typography
              variant="caption"
              sx={{
                display: 'block',
                fontWeight: 600,
                fontSize: '0.625rem',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                color: 'text.secondary',
              }}
            >
              {t('result')}
            </Typography>
            <Typography sx={{ fontSize: '0.75rem', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
              {sub.result_summary}
            </Typography>
          </Box>
        ) : sub.status === 'completed' && !sub.result_detail ? (
          <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem' }}>
            {t('noOutput')}
          </Typography>
        ) : null}

        {sub.result_detail && (
          <Box>
            <Button
              size="small"
              color="inherit"
              onClick={() => setDetailOpen((v) => !v)}
              aria-expanded={detailOpen}
              endIcon={detailOpen ? <ExpandLessIcon /> : <ExpandMoreIcon />}
              sx={{ fontSize: '0.6875rem', textTransform: 'none', px: 0, minWidth: 0 }}
            >
              {t('resultDetail')}
            </Button>
            <Collapse in={detailOpen}>
              <pre
                dir="ltr"
                style={{
                  fontFamily: 'monospace',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  fontSize: '0.6875rem',
                  margin: 0,
                }}
              >
                {sub.result_detail}
              </pre>
            </Collapse>
          </Box>
        )}

        {sub.status === 'failed' && sub.error && (
          <Alert severity="error" sx={{ fontSize: '0.6875rem', py: 0.25 }}>
            {sub.error}
          </Alert>
        )}

        {pollFailed && !terminal && (
          <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem' }}>
            {t('couldNotRefreshSubagent')}
          </Typography>
        )}
      </Stack>
    </Paper>
  );
}

SubagentResultCard.propTypes = {
  subagent: PropTypes.object.isRequired,
  token: PropTypes.string.isRequired,
  conversationId: PropTypes.string.isRequired,
  onResolved: PropTypes.func,
};

export default SubagentResultCard;
