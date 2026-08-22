// src/shell/DiscoveryComposer.jsx
// W5-B — guided discovery conversation before plan creation (ADR-0014 agent
// mode). The user describes an outcome; Pulse asks focused clarifying
// questions one at a time; when discovery completes, a reviewable plan is
// produced (RULE_21 — nothing executes until approved and run). Compact
// message bubbles (same density as AIConversationView, no full toolbar);
// questions and replies render as plain text (no raw JSON). Theme tokens
// only (RULE_8); outcome copy only (RULE_23).
import React, { useState } from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Button,
  CircularProgress,
  Paper,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import AddOutlinedIcon from '@mui/icons-material/AddOutlined';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import SendIcon from '@mui/icons-material/Send';
import { useAuth } from '../auth/AuthContext';
import { useNotification } from '../components/NotificationProvider';
import { advanceDiscovery, startDiscoveryPlan } from '../api/aiWorkspace';

// ── Bubble — plain-text Pulse question / user reply ──────────────────────
function Bubble({ role, text }) {
  const isUser = role === 'user';
  return (
    <Box sx={{ display: 'flex', justifyContent: isUser ? 'flex-end' : 'flex-start' }}>
      <Paper
        variant="outlined"
        sx={{
          maxWidth: '88%',
          px: 1,
          py: 0.5,
          bgcolor: isUser ? 'action.selected' : 'background.default',
          borderColor: 'divider',
        }}
      >
        {!isUser && (
          <Typography
            variant="caption"
            sx={{
              display: 'block',
              fontWeight: 600,
              fontSize: '0.625rem',
              lineHeight: 1.2,
              color: 'primary.main',
              mb: 0.25,
            }}
          >
            Pulse
          </Typography>
        )}
        <Typography
          variant="body2"
          sx={{ fontSize: '0.75rem', lineHeight: 1.4, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}
        >
          {text}
        </Typography>
      </Paper>
    </Box>
  );
}

Bubble.propTypes = {
  role: PropTypes.oneOf(['pulse', 'user']).isRequired,
  text: PropTypes.string.isRequired,
};

// ── DiscoveryComposer — brief → guided questions → ready plan ────────────
function DiscoveryComposer({ conversationId, onPlanReady }) {
  const { token } = useAuth();
  const { notifyFromError } = useNotification();

  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [planId, setPlanId] = useState(null);
  const [turns, setTurns] = useState([]); // [{ question, reply }]
  const [readyPlan, setReadyPlan] = useState(null);

  const reset = () => {
    setPlanId(null);
    setTurns([]);
    setReadyPlan(null);
    setDraft('');
    setBusy(false);
  };

  const handleSubmit = async () => {
    const value = draft.trim();
    if (!value || busy) return;

    setBusy(true);
    try {
      if (!planId) {
        // First submit — start the guided discovery conversation.
        const started = await startDiscoveryPlan(token, {
          brief: value,
          conversation_id: conversationId || '',
        });
        setPlanId(started.id);
        setTurns(
          Array.isArray(started.turns)
            ? started.turns
            : [{ question: started.question, reply: null }],
        );
      } else {
        // Reply to Pulse's current question.
        const result = await advanceDiscovery(token, planId, value);
        setTurns(Array.isArray(result.turns) ? result.turns : turns);
        if (result.status === 'plan_ready') {
          setReadyPlan(result.plan);
        }
      }
      setDraft('');
    } catch (err) {
      notifyFromError(err, planId ? 'Could not continue planning' : 'Could not start planning');
    } finally {
      setBusy(false);
    }
  };

  // Plan ready — banner + review transition (renders AITaskPlanCard on the Run tab).
  if (readyPlan) {
    return (
      <Paper variant="outlined" sx={{ p: 1.25, bgcolor: 'background.paper', borderColor: 'success.main' }}>
        <Stack direction="row" spacing={0.75} alignItems="center" sx={{ mb: 1 }}>
          <CheckCircleOutlineIcon sx={{ fontSize: 16, color: 'success.main' }} />
          <Typography variant="body2" sx={{ fontWeight: 600, fontSize: '0.75rem' }}>
            Plan ready — review below
          </Typography>
        </Stack>
        <Stack direction="row" spacing={0.75}>
          <Button
            size="small"
            variant="contained"
            startIcon={<ChevronRightIcon sx={{ fontSize: 14 }} />}
            onClick={() => {
              onPlanReady?.(readyPlan);
              reset();
            }}
            sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
          >
            Review plan
          </Button>
          <Button
            size="small"
            onClick={reset}
            sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
          >
            New task
          </Button>
        </Stack>
      </Paper>
    );
  }

  return (
    <Paper variant="outlined" sx={{ p: 1.25, bgcolor: 'background.paper' }}>
      <Typography variant="body2" sx={{ fontWeight: 600, fontSize: '0.75rem', mb: 0.5 }}>
        Plan a task
      </Typography>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: '0.6875rem', mb: 0.75 }}>
        Describe the outcome — Pulse asks a few clarifying questions first, then drafts a plan. Nothing executes until you approve and run it.
      </Typography>

      {turns.length > 0 && (
        <Stack spacing={0.75} sx={{ mb: 1 }}>
          {turns.map((turn, i) => {
            const question = (turn?.question || '').trim();
            const reply = (turn?.reply || '').trim();
            return (
              <React.Fragment key={i}>
                {question && <Bubble role="pulse" text={question} />}
                {reply && <Bubble role="user" text={reply} />}
              </React.Fragment>
            );
          })}
        </Stack>
      )}

      <TextField
        multiline
        minRows={1}
        maxRows={4}
        fullWidth
        size="small"
        placeholder={planId ? 'Reply to Pulse…' : 'e.g. Audit the emissions dataset for duplicates and create a rule to prevent them.'}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit();
          }
        }}
        inputProps={{ 'aria-label': planId ? 'Discovery reply' : 'Task brief' }}
        sx={{ '& .MuiInputBase-input': { fontSize: '0.75rem' } }}
      />
      <Button
        size="small"
        variant="contained"
        startIcon={
          busy ? (
            <CircularProgress size={12} thickness={6} color="inherit" />
          ) : planId ? (
            <SendIcon sx={{ fontSize: 14 }} />
          ) : (
            <AddOutlinedIcon sx={{ fontSize: 14 }} />
          )
        }
        disabled={busy || !draft.trim()}
        onClick={handleSubmit}
        sx={{ mt: 1, fontSize: '0.6875rem', textTransform: 'none' }}
      >
        {busy ? 'Thinking…' : planId ? 'Send' : 'Start planning'}
      </Button>
    </Paper>
  );
}

DiscoveryComposer.propTypes = {
  conversationId: PropTypes.string,
  onPlanReady: PropTypes.func,
};

export default DiscoveryComposer;
