// src/shell/DiscoveryComposer.jsx
// W5-B — guided discovery conversation before plan creation (ADR-0014 agent
// mode). REUSES the same rich chat building blocks as the main conversation
// (AIMessageBubble + AIInputBar + AIWorkingIndicator), so planning a task
// feels exactly like chatting with Pulse: the user describes an outcome;
// Pulse asks focused clarifying questions one at a time; when discovery
// completes, a reviewable plan is produced (RULE_21 — nothing executes until
// approved and run). Theme tokens only (RULE_8); outcome copy only (RULE_23).
import React, { useState } from 'react';
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
import { advanceDiscovery, startDiscoveryPlan } from '../api/aiWorkspace';
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
function DiscoveryComposer({ conversationId, onPlanReady }) {
  const { token } = useAuth();
  const { notifyFromError } = useNotification();

  const [busy, setBusy] = useState(false);
  const [planId, setPlanId] = useState(null);
  const [turns, setTurns] = useState([]); // [{ question, reply }]
  const [readyPlan, setReadyPlan] = useState(null);

  const reset = () => {
    setPlanId(null);
    setTurns([]);
    setReadyPlan(null);
    setBusy(false);
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
      } else {
        // Reply to Pulse's current question.
        const result = await advanceDiscovery(token, planId, text);
        setTurns(Array.isArray(result.turns) ? result.turns : turns);
        if (result.status === 'plan_ready') {
          setReadyPlan(result.plan);
        }
      }
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

  // Opening greeting — makes the composer read as a conversation from the
  // first paint, before any turns exist (W5-B chat-until-plan).
  const messages = turnsToMessages(turns);
  if (messages.length === 0) {
    messages.push({
      id: 'greeting',
      role: 'assistant',
      content:
        "Hi — I'm Pulse. Describe the outcome you want, and I'll ask you a few focused questions before drafting a plan. Nothing runs until you approve it.",
      created_at: new Date().toISOString(),
    });
  }

  return (
    <Paper variant="outlined" sx={{ p: 1.25, bgcolor: 'background.paper' }}>
      <Typography variant="body2" sx={{ fontWeight: 600, fontSize: '0.75rem', mb: 0.5 }}>
        Plan a task
      </Typography>

      {/* Same rich bubbles as the main chat (markdown, actions, provenance). */}
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.75, mb: 1 }}>
        {messages.map((msg) => (
          <AIMessageBubble key={msg.id} message={msg} />
        ))}
        {busy && <AIWorkingIndicator conversationType="chat" />}
      </Box>

      {/* Same rich composer as the main chat (mentions, working state, stop). */}
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
};

export default DiscoveryComposer;
