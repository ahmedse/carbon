// src/shell/DiscoveryComposer.jsx
// W5-B — guided discovery conversation before plan creation (ADR-0014 agent
// mode). REUSES the same rich chat building blocks as the main conversation
// (AIMessageBubble + AIInputBar + AIWorkingIndicator), so planning a task
// feels exactly like chatting with Pulse: the user describes an outcome;
// Pulse asks focused clarifying questions one at a time; when discovery
// completes, a reviewable plan is produced (RULE_21 — nothing executes until
// approved and run). Theme tokens only (RULE_8); outcome copy only (RULE_23).
// Track B — scope_route gates: refuse / recommend / handoff before Plan now.
import React, { useEffect, useRef, useState } from 'react';
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
import { advanceDiscovery, createPlan, finalizeDiscovery, startDiscoveryPlan } from '../api/aiWorkspace';
import AIMessageBubble from './AIMessageBubble';
import AIInputBar from './AIInputBar';
import AIWorkingIndicator from './AIWorkingIndicator';

const COMPLIANCE_BRIEF = 'Prepare a leave-compliance board pack summarizing risk for the latest period';

/** Text the operator actually stated. Discovery often starts on a non-leave
 *  seed ("Run via Agent"); the leave sentence is the later reply. */
function statedBrief(turns, lastBrief) {
  const replies = (Array.isArray(turns) ? turns : [])
    .map((turn) => (turn?.reply || '').trim())
    .filter(Boolean);
  const latest = replies.length ? replies[replies.length - 1] : '';
  const seed = (lastBrief || '').trim();
  if (latest && seed && latest !== seed) return `${seed}\n${latest}`;
  return latest || seed;
}

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

function ScopeRouteCard({ route, busy, onPick }) {
  if (!route) return null;
  const cards = Array.isArray(route.cards) ? route.cards : [];
  return (
    <Paper
      variant="outlined"
      data-testid="scope-route-card"
      sx={{ p: 1.25, bgcolor: 'background.paper', borderColor: 'warning.main' }}
    >
      <Typography variant="body2" sx={{ fontWeight: 600, fontSize: '0.8125rem', mb: 0.5 }}>
        {route.class === 'ABUSE' ? 'I can’t help with that' : 'Let’s route this correctly'}
      </Typography>
      {route.message && (
        <Typography variant="caption" sx={{ display: 'block', fontSize: '0.75rem', mb: 1, color: 'text.primary' }}>
          {route.message}
        </Typography>
      )}
      {cards.length > 0 && (
        <Stack spacing={0.75}>
          {cards.map((card) => (
            <Button
              key={card.id}
              size="small"
              variant={card.primary ? 'contained' : 'outlined'}
              color={card.primary ? 'primary' : 'inherit'}
              disabled={busy}
              onClick={() => onPick(card.id)}
              sx={{
                fontSize: '0.75rem',
                textTransform: 'none',
                justifyContent: 'flex-start',
                textAlign: 'left',
                fontWeight: card.primary ? 600 : 500,
              }}
            >
              <Box>
                <Typography component="span" sx={{ display: 'block', fontSize: '0.75rem', fontWeight: 'inherit' }}>
                  {card.label}
                </Typography>
                {card.hint && (
                  <Typography component="span" variant="caption" color="text.secondary" sx={{ fontSize: '0.625rem' }}>
                    {card.hint}
                  </Typography>
                )}
              </Box>
            </Button>
          ))}
        </Stack>
      )}
    </Paper>
  );
}

ScopeRouteCard.propTypes = {
  route: PropTypes.object,
  busy: PropTypes.bool,
  onPick: PropTypes.func.isRequired,
};

function DiscoveryComposer({
  conversationId,
  onPlanReady,
  onStarted,
  onSwitchToChat,
  resumePlanId = null,
  resumeTurns = null,
  seedBrief = null,
  onSeedBriefConsumed,
}) {
  const { token } = useAuth();
  const { notifyFromError } = useNotification();

  const [busy, setBusy] = useState(false);
  const [planId, setPlanId] = useState(null);
  const [turns, setTurns] = useState([]);
  const [readyPlan, setReadyPlan] = useState(null);
  const [route, setRoute] = useState(null);
  const [lastBrief, setLastBrief] = useState('');
  const seedConsumedRef = useRef(null);

  useEffect(() => {
    if (!resumePlanId) return;
    setPlanId(resumePlanId);
    setTurns(Array.isArray(resumeTurns) ? resumeTurns : []);
    setReadyPlan(null);
    setRoute(null);
    setBusy(false);
  }, [resumePlanId, resumeTurns]);

  const reset = () => {
    setPlanId(null);
    setTurns([]);
    setReadyPlan(null);
    setRoute(null);
    setBusy(false);
    setLastBrief('');
  };

  const handlePlanReady = (plan) => {
    setReadyPlan(plan);
    setRoute(null);
  };

  const applyRoutePayload = (payload, briefText) => {
    if (payload?.route && payload.plannable === false) {
      setRoute(payload.route);
      if (briefText) setLastBrief(briefText);
      if (payload.id) setPlanId(payload.id);
      if (Array.isArray(payload.turns)) setTurns(payload.turns);
      return true;
    }
    setRoute(null);
    return false;
  };

  const startWithBrief = async (text) => {
    const started = await startDiscoveryPlan(token, {
      brief: text,
      conversation_id: conversationId || '',
    });
    if (applyRoutePayload(started, text)) {
      return;
    }
    // ESS process dials (loan / attendance) skip clarifying and land a plan.
    if (started?.status === 'plan_ready' && started.plan) {
      setLastBrief(text);
      handlePlanReady(started.plan);
      onPlanReady?.(started.plan);
      return;
    }
    setPlanId(started.id);
    setTurns(
      Array.isArray(started.turns)
        ? started.turns
        : [{ question: started.question, reply: null }],
    );
    setLastBrief(text);
    onStarted?.({ ...started, brief: text });
  };

  // ADR-0046 Chat→Agent handoff: start discovery with the Chat draft so the
  // process dial materializes without retyping (never stages in Chat).
  useEffect(() => {
    const text = typeof seedBrief === 'string' ? seedBrief.trim() : '';
    if (!text || seedConsumedRef.current === text || planId || busy) return;
    seedConsumedRef.current = text;
    onSeedBriefConsumed?.();
    let cancelled = false;
    setBusy(true);
    (async () => {
      try {
        await startWithBrief(text);
      } catch (err) {
        if (!cancelled) {
          notifyFromError(err, 'Could not start planning from Chat handoff');
        }
      } finally {
        if (!cancelled) setBusy(false);
      }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- seedBrief is the intentional trigger
  }, [seedBrief]);

  const handleSubmit = async (value) => {
    const text = (value || '').trim();
    if (!text || busy) return;

    setBusy(true);
    try {
      if (!planId) {
        await startWithBrief(text);
      } else {
        const result = await advanceDiscovery(token, planId, text);
        setTurns(Array.isArray(result.turns) ? result.turns : turns);
        if (applyRoutePayload(result, lastBrief)) {
          return;
        }
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
    if (!planId || busy || (route && route.plannable === false)) return;
    setBusy(true);
    try {
      const result = await finalizeDiscovery(token, planId);
      if (applyRoutePayload(result, lastBrief)) {
        return;
      }
      if (result.status === 'plan_ready' && result.plan) {
        handlePlanReady(result.plan);
      }
    } catch (err) {
      notifyFromError(err, 'Could not build the plan');
    } finally {
      setBusy(false);
    }
  };

  const handleCardPick = async (cardId) => {
    if (busy) return;
    // Explicit Chat opt-in only — never bounce new-task creation into Chat.
    if (cardId === 'handoff_chat') {
      onSwitchToChat?.(statedBrief(turns, lastBrief));
      reset();
      return;
    }
    // Personal leave → create a reviewable Agent plan (editable), stay here.
    if (cardId === 'leave_request') {
      setBusy(true);
      try {
        const brief = statedBrief(turns, lastBrief) || 'Submit a leave request';
        const plan = await createPlan(token, {
          brief,
          conversation_id: conversationId || '',
        });
        onPlanReady?.(plan);
        reset();
      } catch (err) {
        notifyFromError(err, 'Could not create the leave plan');
      } finally {
        setBusy(false);
      }
      return;
    }
    if (cardId === 'compliance_report') {
      setBusy(true);
      try {
        reset();
        await startWithBrief(COMPLIANCE_BRIEF);
      } catch (err) {
        notifyFromError(err, 'Could not start planning');
      } finally {
        setBusy(false);
      }
      return;
    }
    if (cardId === 'rewrite_brief') {
      reset();
    }
  };

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
  const gated = Boolean(route && route.plannable === false);
  const planNowDisabled = busy || !planId || gated;

  if (messages.length === 0 && !gated) {
    return (
      <AIInputBar
        onSend={handleSubmit}
        working={busy}
      />
    );
  }

  return (
    <Paper variant="outlined" sx={{ p: 1.25, bgcolor: 'background.paper' }}>
      {messages.length > 0 && (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.75, mb: 1 }}>
          {messages.map((msg) => (
            <AIMessageBubble key={msg.id} message={msg} />
          ))}
          {busy && <AIWorkingIndicator conversationType="chat" />}
        </Box>
      )}

      {gated && (
        <Box sx={{ mb: 1 }}>
          <ScopeRouteCard route={route} busy={busy} onPick={handleCardPick} />
        </Box>
      )}

      {!gated && (
        <Stack direction="row" spacing={0.75} alignItems="center" sx={{ mb: 0.75 }}>
          <Typography variant="caption" color="text.secondary" sx={{ flex: 1, fontSize: '0.6875rem' }}>
            Answer above, or plan with the brief as stated.
          </Typography>
          <Button
            size="small"
            variant="outlined"
            disabled={planNowDisabled}
            onClick={handleFinalize}
            sx={{ fontSize: '0.6875rem', textTransform: 'none', flexShrink: 0 }}
          >
            Plan now
          </Button>
        </Stack>
      )}

      {!gated && (
        <AIInputBar
          onSend={handleSubmit}
          working={busy}
          conversationStatus={planId ? 'needs_input' : undefined}
        />
      )}

      {gated && (
        <Button
          size="small"
          onClick={reset}
          sx={{ mt: 0.75, fontSize: '0.6875rem', textTransform: 'none' }}
        >
          Start over
        </Button>
      )}
    </Paper>
  );
}

DiscoveryComposer.propTypes = {
  conversationId: PropTypes.string,
  onPlanReady: PropTypes.func,
  onStarted: PropTypes.func,
  onSwitchToChat: PropTypes.func,
  resumePlanId: PropTypes.string,
  resumeTurns: PropTypes.arrayOf(PropTypes.shape({
    question: PropTypes.string,
    reply: PropTypes.string,
  })),
  seedBrief: PropTypes.string,
  onSeedBriefConsumed: PropTypes.func,
};

export default DiscoveryComposer;
