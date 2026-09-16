// src/shell/DiscoveryComposer.jsx
// W5-B — guided discovery conversation before plan creation (ADR-0014 agent
// mode). REUSES the same rich chat building blocks as the main conversation
// (AIMessageBubble + AIInputBar + AIWorkingIndicator), so planning a task
// feels exactly like chatting with Pulse: the user describes an outcome;
// Pulse asks focused clarifying questions one at a time; when discovery
// completes, a reviewable plan is produced (RULE_21 — nothing executes until
// approved and run). Theme tokens only (RULE_8); outcome copy only (RULE_23).
import React, { useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Button,
  Paper,
  Stack,
  Typography,
} from '@mui/material';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import { useAuth } from '../auth/AuthContext';
import { useNotification } from '../components/NotificationProvider';
import { advanceDiscovery, finalizeDiscovery, startDiscoveryPlan } from '../api/aiWorkspace';
import AIMessageBubble from './AIMessageBubble';
import AIInputBar from './AIInputBar';
import AIWorkingIndicator from './AIWorkingIndicator';

// Map discovery turns onto the message shape AIMessageBubble expects, so the
// same rich bubble component renders both the main chat and discovery.
function turnsToMessages(turns) {
  const messages = [];
  turns.forEach((turn, i) => {
    const question = (turn?.question || '').trim();
    const reply = (turn?.reply || '').trim();
    if (question) {
      messages.push({
        id: `q-${i}`,
        role: 'assistant',
        content: question,
        created_at: new Date().toISOString(),
      });
    }
    if (reply) {
      messages.push({
        id: `r-${i}`,
        role: 'user',
        content: reply,
        created_at: new Date().toISOString(),
      });
    }
  });
  return messages;
}

// ── DiscoveryComposer — brief → guided questions → ready plan ────────────
function DiscoveryComposer({
  conversationId,
  onPlanReady,
  onStarted,
  resumePlanId = null,
  resumeTurns = null,
}) {
  const { token } = useAuth();
  const { notifyFromError } = useNotification();

  const [busy, setBusy] = useState(false);
  const [planId, setPlanId] = useState(null);
  const [turns, setTurns] = useState([]); // [{ question, reply }]
  const [readyPlan, setReadyPlan] = useState(null);

  // Resume a stuck/in-progress discovering run selected from the task picker.
  // Do NOT clear local discovery when resumePlanId is simply unset (new brief).
  useEffect(() => {
    if (!resumePlanId) return;
    setPlanId(resumePlanId);
    setTurns(Array.isArray(resumeTurns) ? resumeTurns : []);
    setReadyPlan(null);
    setBusy(false);
  }, [resumePlanId, resumeTurns]);

  const reset = () => {
    setPlanId(null);
    setTurns([]);
    setReadyPlan(null);
    setBusy(false);
  };

  const handlePlanReady = (plan) => {
    setReadyPlan(plan);
  };

  const handleSubmit = async (value) => {
    const text = (value || '').trim();
    if (!text || busy) return;

    setBusy(true);
    try {
      if (!planId) {
        // First submit — start the guided discovery conversation.
        const started = await startDiscoveryPlan(token, {
          brief: text,
          conversation_id: conversationId || '',
        });
        setPlanId(started.id);
        setTurns(
          Array.isArray(started.turns)
            ? started.turns
            : [{ question: started.question, reply: null }],
        );
        onStarted?.({ ...started, brief: text });
      } else {
        // Reply to Pulse's current question.
        const result = await advanceDiscovery(token, planId, text);
        setTurns(Array.isArray(result.turns) ? result.turns : turns);
        if (result.status === 'plan_ready') {
          handlePlanReady(result.plan);
        }
      }
    } catch (err) {
      notifyFromError(err, planId ? 'Could not continue planning' : 'Could not start planning');
    } finally {
      setBusy(false);
    }
  };

  const handleFinalize = async () => {
    if (!planId || busy) return;
    setBusy(true);
    try {
      const result = await finalizeDiscovery(token, planId);
      if (result.status === 'plan_ready' && result.plan) {
        handlePlanReady(result.plan);
      }
    } catch (err) {
      notifyFromError(err, 'Could not build the plan');
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

  const messages = turnsToMessages(turns);

  // When no conversation has started yet, show a compact input-only state.
  if (messages.length === 0) {
    return (
      <AIInputBar
        onSend={handleSubmit}
        working={busy}
      />
    );
  }

  return (
    <Paper variant="outlined" sx={{ p: 1.25, bgcolor: 'background.paper' }}>
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.75, mb: 1 }}>
        {messages.map((msg) => (
          <AIMessageBubble key={msg.id} message={msg} />
        ))}
        {busy && <AIWorkingIndicator conversationType="chat" />}
      </Box>

      <Stack direction="row" spacing={0.75} alignItems="center" sx={{ mb: 0.75 }}>
        <Typography variant="caption" color="text.secondary" sx={{ flex: 1, fontSize: '0.6875rem' }}>
          Answer above, or plan with the brief as stated.
        </Typography>
        <Button
          size="small"
          variant="outlined"
          disabled={busy || !planId}
          onClick={handleFinalize}
          sx={{ fontSize: '0.6875rem', textTransform: 'none', flexShrink: 0 }}
        >
          Plan now
        </Button>
      </Stack>

      <AIInputBar
        onSend={handleSubmit}
        working={busy}
        conversationStatus={planId ? 'needs_input' : undefined}
      />
    </Paper>
  );
}

DiscoveryComposer.propTypes = {
  conversationId: PropTypes.string,
  onPlanReady: PropTypes.func,
  onStarted: PropTypes.func,
  resumePlanId: PropTypes.string,
  resumeTurns: PropTypes.arrayOf(PropTypes.shape({
    question: PropTypes.string,
    reply: PropTypes.string,
  })),
};

export default DiscoveryComposer;
