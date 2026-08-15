// src/shell/AIConversationView.jsx
import React, { useCallback, useEffect, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import { Box, Button, Stack, Typography } from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import { useAuth } from '../auth/AuthContext';
import { useNotification } from '../components/NotificationProvider';
import {
  acceptSuggestion,
  getConversation,
  rejectSuggestion,
  sendMessage as apiSendMessage,
  sendMessageStream,
} from '../api/aiWorkspace';
import AIMessageBubble from './AIMessageBubble';
import AIInputBar from './AIInputBar';
import AIWorkingIndicator from './AIWorkingIndicator';
import AIOfflineBanner from './AIOfflineBanner';
import { DQ_MANAGE_RULES } from '../capabilities';

const POLL_INTERVAL_MS = 2000;

function normalizeConversationShape(payload) {
  const candidate = payload?.conversation || payload;
  if (!candidate || typeof candidate !== 'object') {
    return null;
  }
  return {
    ...candidate,
    messages: Array.isArray(candidate.messages) ? candidate.messages : [],
  };
}

function AIConversationView({ conversationId }) {
  const { token, userCapabilities, isGlobalAdminFlag } = useAuth();
  const { notifyFromError } = useNotification();
  // CBAC: accepting/rejecting DQ suggestions writes rules → requires dq:manage_rules.
  const canManageRules = isGlobalAdminFlag || (userCapabilities || []).some(
    (c) => (typeof c === 'string' ? c : c?.key) === DQ_MANAGE_RULES
  );
  const [conversation, setConversation] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [actionBusyId, setActionBusyId] = useState(null);
  const [workingStartedAt, setWorkingStartedAt] = useState(null);
  const [providerOffline, setProviderOffline] = useState(false);
  // Transient assistant text accumulated while a chat response streams in.
  const [streamingText, setStreamingText] = useState(null);
  const scrollRef = useRef(null);
  const pollRef = useRef(null);
  // True while an SSE stream is in flight — polling must not clobber it.
  const streamingActiveRef = useRef(false);

  // Load conversation
  const load = useCallback(async () => {
    if (!conversationId) return;
    try {
      const data = await getConversation(token, conversationId);
      setConversation(normalizeConversationShape(data));
    } catch (err) {
      notifyFromError(err, 'Could not load conversation');
    } finally {
      setLoading(false);
    }
  }, [token, conversationId, notifyFromError]);

  useEffect(() => {
    setLoading(true);
    setConversation(null);
    load();
  }, [load]);

  // Poll when conversation is in working state
  useEffect(() => {
    if (!conversation || conversation.status !== 'working') {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      return;
    }

    pollRef.current = setInterval(async () => {
      // Never clobber an in-flight stream — its onDone owns reconciliation.
      if (streamingActiveRef.current) return;
      try {
        const data = await getConversation(token, conversationId);
        const canonical = normalizeConversationShape(data);
        setConversation(canonical);
        if (canonical?.status !== 'working') {
          setSending(false);
        }
      } catch {
        // transient poll failure — keep polling
      }
    }, POLL_INTERVAL_MS);

    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [conversation?.status, conversation, token, conversationId]);

  // Auto-scroll to bottom on new messages and while streaming deltas arrive.
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [conversation?.messages?.length, streamingText]);

  useEffect(() => {
    const isWorking = conversation?.status === 'working' || sending;
    if (!isWorking) {
      setWorkingStartedAt(null);
      return;
    }
    setWorkingStartedAt((prev) => prev || Date.now());
  }, [conversation?.status, sending]);

  const handleSend = useCallback(
    async (content) => {
      if (!conversationId || !content.trim()) return;
      const type = conversation?.conversation_type || conversation?.task_payload_json?.type || 'chat';
      setSending(true);
      setProviderOffline(false);

      // chat → stream the final answer over SSE (typing effect).
      if (type === 'chat') {
        setStreamingText('');
        streamingActiveRef.current = true;
        // Optimistically append the user message; replaced by the persisted copy on done.
        setConversation((prev) =>
          prev
            ? {
                ...prev,
                messages: [
                  ...(prev.messages || []),
                  {
                    id: `local-${Date.now()}`,
                    role: 'user',
                    content,
                    created_at: new Date().toISOString(),
                  },
                ],
              }
            : prev,
        );

        await sendMessageStream(token, conversationId, content, {
          onChunk: (delta) => {
            setStreamingText((prev) => (prev ?? '') + delta);
          },
          onDone: (conv) => {
            streamingActiveRef.current = false;
            setStreamingText(null);
            const canonical = normalizeConversationShape(conv);
            setConversation(canonical);
            if (canonical?.status !== 'working') {
              setSending(false);
            }
          },
          onError: (message) => {
            streamingActiveRef.current = false;
            setStreamingText(null);
            setSending(false);
            if (message?.includes('unavailable') || message?.includes('offline')) {
              setProviderOffline(true);
            }
            notifyFromError(new Error(message || 'Could not send message'), 'Could not send message');
          },
        });

        // Safety net: if the stream ended without a terminal frame, release the UI.
        if (streamingActiveRef.current) {
          streamingActiveRef.current = false;
          setStreamingText(null);
          setSending(false);
        }
        return;
      }

      // Non-chat → existing non-streaming path.
      try {
        const data = await apiSendMessage(token, conversationId, content);
        const canonical = normalizeConversationShape(data);
        setConversation(canonical);
        if (canonical?.status !== 'working') {
          setSending(false);
        }
      } catch (err) {
        setSending(false);
        if (err.message?.includes('unavailable') || err.message?.includes('offline')) {
          setProviderOffline(true);
        }
        notifyFromError(err, 'Could not send message');
      }
    },
    [token, conversationId, conversation, notifyFromError],
  );

  const handleRetry = useCallback(() => {
    setProviderOffline(false);
  }, []);

  const handleFollowUp = useCallback(
    (question) => {
      handleSend(question);
    },
    [handleSend],
  );

  const handleAcceptSuggestion = useCallback(
    async (suggestion) => {
      const suggestionId = suggestion?.id || suggestion?.suggestion_id;
      if (!suggestionId) return;
      setActionBusyId(`accept-${suggestionId}`);
      try {
        const createdRule = await acceptSuggestion(token, suggestionId);
        await handleSend(
          `Accepted suggestion ${suggestionId}${createdRule?.name ? ` and created rule "${createdRule.name}"` : ''}.`,
        );
      } catch (err) {
        notifyFromError(err, 'Could not accept suggestion');
      } finally {
        setActionBusyId(null);
      }
    },
    [token, handleSend, notifyFromError],
  );

  const handleRejectSuggestion = useCallback(
    async (suggestion) => {
      const suggestionId = suggestion?.id || suggestion?.suggestion_id;
      if (!suggestionId) return;
      setActionBusyId(`reject-${suggestionId}`);
      try {
        await rejectSuggestion(token, suggestionId);
        await handleSend(`Rejected suggestion ${suggestionId}. Please refine and suggest alternatives.`);
      } catch (err) {
        notifyFromError(err, 'Could not reject suggestion');
      } finally {
        setActionBusyId(null);
      }
    },
    [token, handleSend, notifyFromError],
  );

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
        <Typography variant="caption" color="text.secondary">
          Loading conversation…
        </Typography>
      </Box>
    );
  }

  if (!conversation) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography variant="caption" color="error.main">
          Conversation not found.
        </Typography>
      </Box>
    );
  }

  const messages = conversation.messages || [];
  const isWorking = conversation.status === 'working' || sending;
  const convStatus = conversation.status;
  const conversationType = conversation.conversation_type || conversation.task_payload_json?.type || 'chat';
  const lastAssistant = [...messages].reverse().find((m) => m.role === 'assistant');
  const lastMetadata = lastAssistant?.metadata || lastAssistant?.metadata_json || {};
  const suggestionActions =
    lastMetadata?.type === 'dq_suggestions' ? (lastMetadata.suggestions || lastMetadata.items || []) : [];
  const anomalyActions =
    lastMetadata?.type === 'anomalies' ? (lastMetadata.anomalies || []) : [];
  const followUpQuestions = lastMetadata?.follow_up_questions || [];

  const needsInputHint =
    convStatus === 'needs_input'
      ? conversationType === 'dq_suggest'
        ? 'Accept or reject the suggested rules above, or ask for refinements.'
        : conversationType === 'anomaly'
          ? 'Review the detected anomalies. Ask for details or dismiss.'
          : 'AI is waiting for your response…'
      : null;

  const elapsedSeconds = workingStartedAt ? Math.floor((Date.now() - workingStartedAt) / 1000) : 0;
  const workingNotice =
    isWorking && elapsedSeconds >= 30
      ? 'Taking longer than expected. You can switch to another tab and come back.'
      : isWorking && elapsedSeconds >= 15
        ? 'Still working… complex analysis in progress.'
        : isWorking && elapsedSeconds >= 5
          ? 'This may take a moment…'
          : null;

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        overflow: 'hidden',
      }}
    >
      {providerOffline && <AIOfflineBanner />}

      {/* Messages area */}
      <Box
        ref={scrollRef}
        sx={{
          flex: 1,
          overflowY: 'auto',
          overflowX: 'hidden',
          pt: 1,
          pb: 0.5,
        }}
      >
        {messages.length === 0 && !isWorking && (
          <Box sx={{ p: 3, textAlign: 'center' }}>
            <Typography variant="caption" color="text.disabled">
              Send a message to start the conversation.
            </Typography>
          </Box>
        )}

        {messages.map((msg) => (
          <AIMessageBubble
            key={msg.id}
            message={msg}
            onAcceptSuggestion={handleAcceptSuggestion}
            onRejectSuggestion={handleRejectSuggestion}
            canManageRules={canManageRules}
          />
        ))}

        {streamingText !== null ? (
          <AIMessageBubble
            message={{
              id: 'streaming',
              role: 'assistant',
              content: streamingText || '…',
              created_at: new Date().toISOString(),
            }}
          />
        ) : isWorking ? (
          <>
            {messages.length > 0 && (
              <AIMessageBubble
                message={{
                  id: 'pending',
                  role: 'user',
                  content: '…',
                  created_at: new Date().toISOString(),
                }}
              />
            )}
            <AIWorkingIndicator conversationType={conversationType} />
            {workingNotice && (
              <Box sx={{ px: 2, pb: 1 }}>
                <Typography variant="caption" color="text.secondary">
                  {workingNotice}
                </Typography>
              </Box>
            )}
          </>
        ) : null}

        {providerOffline && messages.length > 0 && (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 1 }}>
            <Button
              size="small"
              startIcon={<RefreshIcon />}
              onClick={handleRetry}
            >
              Retry
            </Button>
          </Box>
        )}

        {/* Needs-input action area */}
        {convStatus === 'needs_input' && !isWorking && (
          <Box sx={{ px: 2, py: 1 }}>
            <Typography variant="caption" color="text.secondary">
              AI needs your input to continue:
            </Typography>

            {suggestionActions.length > 0 && (
              <Stack spacing={0.75} sx={{ mt: 0.75 }}>
                {suggestionActions.map((s, i) => {
                  const sid = s.id || s.suggestion_id || i;
                  return (
                    <Stack key={sid} direction="row" spacing={0.75} alignItems="center" flexWrap="wrap">
                      <Typography variant="caption" color="text.secondary">
                        {s.definition?.name || s.name || `Suggestion ${i + 1}`}
                      </Typography>
                      {canManageRules ? (
                        <>
                          <Button
                            size="small"
                            variant="outlined"
                            color="success"
                            disabled={actionBusyId === `accept-${sid}`}
                            onClick={() => handleAcceptSuggestion(s)}
                          >
                            Accept
                          </Button>
                          <Button
                            size="small"
                            variant="outlined"
                            color="error"
                            disabled={actionBusyId === `reject-${sid}`}
                            onClick={() => handleRejectSuggestion(s)}
                          >
                            Reject
                          </Button>
                        </>
                      ) : (
                        <Typography variant="caption" color="text.disabled">
                          Requires DQ manage permission to accept or reject.
                        </Typography>
                      )}
                    </Stack>
                  );
                })}
              </Stack>
            )}

            {anomalyActions.length > 0 && (
              <Stack direction="row" spacing={0.75} sx={{ mt: 0.75 }}>
                <Button
                  size="small"
                  variant="outlined"
                  onClick={() => handleSend('Please provide anomaly details and likely causes.')}
                >
                  View Details
                </Button>
                <Button
                  size="small"
                  variant="outlined"
                  onClick={() => handleSend('Dismiss this anomaly set for now.')}
                >
                  Dismiss
                </Button>
              </Stack>
            )}

            {followUpQuestions.map((q, i) => (
              <Box key={i} sx={{ mt: 0.5 }}>
                  <Button
                    size="small"
                    variant="outlined"
                    onClick={() => handleFollowUp(q)}
                    sx={{ textTransform: 'none' }}
                  >
                    {q}
                  </Button>
              </Box>
            ))}
          </Box>
        )}
      </Box>

      {needsInputHint && (
        <Box sx={{ px: 1.5, py: 0.5, borderTop: 1, borderColor: 'divider', bgcolor: 'action.hover' }}>
          <Typography variant="caption" color="text.secondary">
            {needsInputHint}
          </Typography>
        </Box>
      )}

      {/* Input bar */}
      <AIInputBar
        onSend={handleSend}
        disabled={isWorking}
        conversationStatus={convStatus}
      />
    </Box>
  );
}

AIConversationView.propTypes = {
  conversationId: PropTypes.string.isRequired,
};

export default AIConversationView;
