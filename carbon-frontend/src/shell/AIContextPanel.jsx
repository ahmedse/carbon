// src/shell/AIContextPanel.jsx
import React, { useCallback, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Collapse,
  Divider,
  IconButton,
  LinearProgress,
  Stack,
  Tooltip,
  Typography,
} from '@mui/material';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import SummarizeIcon from '@mui/icons-material/Summarize';
import { useNotification } from '../components/NotificationProvider';
import { useAuth } from '../auth/AuthContext';
import { summarizeConversation } from '../api/aiWorkspace';

const KIND_COLOR = {
  table: 'primary',
  field: 'secondary',
  rule: 'warning',
  module: 'default',
};

// Compute per-tier token budget percentages from context_snapshot_json.
function parseBudget(snapshot) {
  if (!snapshot || typeof snapshot !== 'object') return null;
  const tiers = ['T0', 'T1', 'T2', 'T3', 'T4'];
  const entries = tiers.map((t) => ({ tier: t, tokens: Number(snapshot[t] ?? 0) }));
  const total = entries.reduce((s, e) => s + e.tokens, 0);
  if (!total) return null;
  return entries.map((e) => ({ ...e, pct: Math.round((e.tokens / total) * 100) }));
}

const TIER_LABELS = {
  T0: 'System',
  T1: 'Workspace',
  T2: 'History',
  T3: 'Retrieval',
  T4: 'Memory',
};

const TIER_COLORS = ['primary', 'info', 'success', 'warning', 'secondary'];

function AIContextPanel({ conversation, mentions, onSummarized }) {
  const { token } = useAuth();
  const { notify, notifyFromError } = useNotification();
  const [open, setOpen] = useState(false);
  const [summarizing, setSummarizing] = useState(false);

  const scopeJson = conversation?.scope_json || {};
  const snapshot = conversation?.context_snapshot_json || {};
  const budget = parseBudget(snapshot);

  const orgUnits = scopeJson?.org_unit_ids || [];
  const appId = conversation?.app_identifier;
  const convType = conversation?.conversation_type;

  const handleSummarize = useCallback(async () => {
    if (!conversation?.id) return;
    setSummarizing(true);
    try {
      const updated = await summarizeConversation(token, conversation.id, false);
      notify({ message: 'Summary updated', type: 'success' });
      onSummarized?.(updated);
    } catch (err) {
      notifyFromError(err, 'Could not summarize');
    } finally {
      setSummarizing(false);
    }
  }, [token, conversation?.id, notify, notifyFromError, onSummarized]);

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'row',
        borderLeft: open ? 1 : 0,
        borderColor: 'divider',
        height: '100%',
        position: 'relative',
      }}
    >
      {/* Toggle strip */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'flex-start',
          pt: 1,
          borderLeft: 1,
          borderColor: 'divider',
        }}
      >
        <Tooltip title={open ? 'Hide context' : 'Show context'} placement="left">
          <IconButton
            size="small"
            onClick={() => setOpen((v) => !v)}
            aria-label={open ? 'Hide context panel' : 'Show context panel'}
            sx={{ borderRadius: 1 }}
          >
            {open ? <ChevronRightIcon fontSize="small" /> : <ChevronLeftIcon fontSize="small" />}
          </IconButton>
        </Tooltip>
      </Box>

      {/* Panel content */}
      <Collapse in={open} orientation="horizontal" sx={{ height: '100%' }}>
        <Box
          sx={{
            width: 220,
            height: '100%',
            overflowY: 'auto',
            p: 1.5,
            display: 'flex',
            flexDirection: 'column',
            gap: 1.5,
          }}
        >
          <Typography variant="caption" fontWeight={700} color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Context
          </Typography>

          {/* Scope chips */}
          <Box>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
              Scope
            </Typography>
            <Stack direction="row" flexWrap="wrap" gap={0.5}>
              {convType && (
                <Chip size="small" label={convType} variant="outlined" />
              )}
              {appId && (
                <Chip size="small" label={appId} color="info" variant="outlined" />
              )}
              {orgUnits.length === 1 && orgUnits[0] === '*' ? (
                <Chip size="small" label="All orgs" color="default" />
              ) : (
                orgUnits.slice(0, 3).map((id) => (
                  <Chip key={id} size="small" label={`Org ${id}`} />
                ))
              )}
              {orgUnits.length === 0 && !appId && !convType && (
                <Typography variant="caption" color="text.disabled">—</Typography>
              )}
            </Stack>
          </Box>

          <Divider />

          {/* Resolved mentions */}
          <Box>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
              Mentions
            </Typography>
            {mentions.length === 0 ? (
              <Typography variant="caption" color="text.disabled">
                None — type # to mention an entity
              </Typography>
            ) : (
              <Stack direction="row" flexWrap="wrap" gap={0.5}>
                {mentions.map((m) => (
                  <Chip
                    key={`${m.kind}-${m.id}`}
                    size="small"
                    color={KIND_COLOR[m.kind] || 'default'}
                    label={m.name}
                    title={`${m.kind} #${m.id}`}
                  />
                ))}
              </Stack>
            )}
          </Box>

          <Divider />

          {/* Token budget bar */}
          <Box>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
              Context budget
            </Typography>
            {!budget ? (
              <Typography variant="caption" color="text.disabled">
                Available after first message
              </Typography>
            ) : (
              <Stack spacing={0.75}>
                {budget.filter((e) => e.tokens > 0).map((e, i) => (
                  <Box key={e.tier}>
                    <Stack direction="row" justifyContent="space-between">
                      <Typography variant="caption" color="text.secondary">
                        {TIER_LABELS[e.tier] || e.tier}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {e.tokens} tok
                      </Typography>
                    </Stack>
                    <LinearProgress
                      variant="determinate"
                      value={e.pct}
                      color={TIER_COLORS[i] || 'primary'}
                      sx={{ height: 4, borderRadius: 2 }}
                    />
                  </Box>
                ))}
              </Stack>
            )}
          </Box>

          <Divider />

          {/* Summarize action */}
          <Box>
            <Button
              size="small"
              variant="outlined"
              startIcon={summarizing ? <CircularProgress size={12} /> : <SummarizeIcon sx={{ fontSize: 14 }} />}
              onClick={handleSummarize}
              disabled={summarizing || !conversation?.id}
              fullWidth
              sx={{ fontSize: '0.75rem' }}
            >
              {summarizing ? 'Summarizing…' : 'Summarize now'}
            </Button>
            {conversation?.summary && (
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ display: 'block', mt: 0.75, fontStyle: 'italic' }}
              >
                {conversation.summary.slice(0, 100)}{conversation.summary.length > 100 ? '…' : ''}
              </Typography>
            )}
          </Box>
        </Box>
      </Collapse>
    </Box>
  );
}

AIContextPanel.propTypes = {
  conversation: PropTypes.shape({
    id: PropTypes.string,
    conversation_type: PropTypes.string,
    app_identifier: PropTypes.string,
    scope_json: PropTypes.object,
    context_snapshot_json: PropTypes.object,
    summary: PropTypes.string,
  }),
  mentions: PropTypes.arrayOf(
    PropTypes.shape({ kind: PropTypes.string, id: PropTypes.string, name: PropTypes.string }),
  ),
  onSummarized: PropTypes.func,
};

AIContextPanel.defaultProps = {
  mentions: [],
};

export default AIContextPanel;
