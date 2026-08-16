// src/shell/AIConversationView.jsx
import React, { useCallback, useEffect, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import { Alert, Box, Button, Chip, Menu, MenuItem, Stack, Typography } from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import DownloadIcon from '@mui/icons-material/Download';
import ArrowDropDownIcon from '@mui/icons-material/ArrowDropDown';
import HistoryIcon from '@mui/icons-material/History';
import { useAuth } from '../auth/AuthContext';
import { useNotification } from '../components/NotificationProvider';
import {
  acceptSuggestion,
  createArtifact,
  exportConversation,
  getConversation,
  listMessages,
  recordFeedback,
  rejectSuggestion,
  resumeConversation,
  sendMessageStream,
  stopGeneration,
} from '../api/aiWorkspace';
import { createDQRule } from '../api/dq';
import AIMessageBubble from './AIMessageBubble';
import AIContextPanel from './AIContextPanel';
import AIInputBar from './AIInputBar';
import AIWorkingIndicator from './AIWorkingIndicator';
import AIOfflineBanner from './AIOfflineBanner';
import { useAITaskTransfer } from './useAITaskTransfer';
import { useExecuteMode } from './useExecuteMode';
import { DQ_MANAGE_RULES } from '../capabilities';

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
  const { notify, notifyFromError } = useNotification();
  const { executeMode } = useExecuteMode();
  const { transferTask } = useAITaskTransfer();
  // CBAC: accepting/rejecting DQ suggestions writes rules → requires dq:manage_rules.
  const canManageRules = isGlobalAdminFlag || (userCapabilities || []).some(
    (c) => (typeof c === 'string' ? c : c?.key) === DQ_MANAGE_RULES
  );
  const [conversation, setConversation] = useState(null);
  const [messages, setMessages] = useState([]);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [sending, setSending] = useState(false);
  const [stopped, setStopped] = useState(false);
  const [workingStage, setWorkingStage] = useState(null);
  const [sendMode, setSendMode] = useState('queue');
  const [actionBusyId, setActionBusyId] = useState(null);
  const [workingStartedAt, setWorkingStartedAt] = useState(null);
  const [providerOffline, setProviderOffline] = useState(false);
  const [exportAnchorEl, setExportAnchorEl] = useState(null);
  // Resolved mention objects from the input bar: [{ kind, id, name }, …]
  const [mentions, setMentions] = useState([]);
  // Transient assistant text accumulated while a chat response streams in.
  const [streamingText, setStreamingText] = useState(null);
  // Phase 5B — pinned "Since your last visit" catch-up summary (null = no banner).
  const [catchUp, setCatchUp] = useState(null);
  // Guard so `resume` fires exactly once per conversation open (idempotent).
  const resumeRequestedRef = useRef(null);
  const scrollRef = useRef(null);
  // Latest user content (for "Continue" after an interrupt).
  const lastUserContentRef = useRef(null);
  // Queued content while a generation is in-flight (send mode: queue).
  const queuedRef = useRef(null);
  // Monotonic generation counter — stale terminal frames are ignored.
  const generationRef = useRef(0);
  // True while an SSE stream is in flight (safety net for missing terminal frame).
  const streamingActiveRef = useRef(false);
  const conversationRef = useRef(null);
  conversationRef.current = conversation;

  // Load conversation (initial): metadata + first page of messages.
  const load = useCallback(async () => {
    if (!conversationId) return;
    try {
      const data = await getConversation(token, conversationId);
      const canonical = normalizeConversationShape(data);
      setConversation(canonical);
      const initial = canonical?.messages || [];
      setMessages(initial);
      setHasMore(initial.length >= 50);
    } catch (err) {
      notifyFromError(err, 'Could not load conversation');
    } finally {
      setLoading(false);
    }
  }, [token, conversationId, notifyFromError]);

  useEffect(() => {
    setLoading(true);
    setConversation(null);
    setMessages([]);
    load();
  }, [load]);

  // Phase 5B — resume catch-up. Call once per conversation open (server is
  // idempotent: it bumps last_viewed_at, so a stale thread only yields a
  // catch-up the first reopen). 404s are expected for inaccessible ids and
  // must not block the thread — handled quietly.
  useEffect(() => {
    if (!conversationId || resumeRequestedRef.current === conversationId) return;
    resumeRequestedRef.current = conversationId;
    let cancelled = false;
    (async () => {
      try {
        const data = await resumeConversation(token, conversationId);
        if (!cancelled && data?.catch_up) setCatchUp(data.catch_up);
      } catch (err) {
        if (cancelled) return;
        // 404 = inaccessible/unknown id — the thread still renders; stay quiet.
        if (err?.status !== 404) {
          notifyFromError(err, 'Could not load conversation summary');
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token, conversationId, notifyFromError]);

  // Auto-scroll to bottom on new messages and while streaming deltas arrive.
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages.length, streamingText, workingStage]);

  useEffect(() => {
    const isWorking = conversation?.status === 'working' || sending;
    if (!isWorking) {
      setWorkingStartedAt(null);
      return;
    }
    setWorkingStartedAt((prev) => prev || Date.now());
  }, [conversation?.status, sending]);

  // Finish a streamed generation: reconcile canonical messages + release UI.
  const finishStream = useCallback(
    (conv) => {
      const canonical = normalizeConversationShape(conv);
      if (canonical) {
        setConversation((prev) => ({ ...prev, ...canonical }));
        const canonicalMsgs = canonical.messages || [];
        if (canonicalMsgs.length) {
          setMessages((prev) => {
            const nonLocal = prev.filter((m) => !String(m.id).startsWith('local-'));
            const seen = new Set(nonLocal.map((m) => m.id));
            const merged = [...nonLocal];
            for (const m of canonicalMsgs) {
              if (!seen.has(m.id)) {
                merged.push(m);
                seen.add(m.id);
              }
            }
            return merged;
          });
        }
      }
      setStreamingText(null);
      setWorkingStage(null);
      if (canonical?.status !== 'working') {
        setSending(false);
      }
    },
    [],
  );

  const handleRetry = useCallback(() => {
    setProviderOffline(false);
  }, []);

  // Core streaming send — every conversation type goes through SSE now.
  const streamSend = useCallback(
    async (content, mentions = []) => {
      if (!conversationId || !content?.trim()) return;
      const type =
        conversationRef.current?.conversation_type ||
        conversationRef.current?.task_payload_json?.type ||
        'chat';
      const genId = ++generationRef.current;
      lastUserContentRef.current = content;
      streamingActiveRef.current = true;
      setSending(true);
      setStopped(false);
      setProviderOffline(false);

      if (type === 'chat') {
        setStreamingText('');
      } else {
        setWorkingStage('Starting…');
      }

      // Optimistically append the user message; replaced by the persisted copy on done.
      setMessages((prev) => [
        ...prev,
        {
          id: `local-${Date.now()}`,
          role: 'user',
          content,
          created_at: new Date().toISOString(),
        },
      ]);

      // Sprint 17: resolved #-mentions ride along as workspace_context. TODO(mentions):
      // map #table/#rule/#field/#module kinds to concrete entity ids from the source
      // workspace before sending (the stream serializer persists only `content` today).
      const workspaceContext =
        Array.isArray(mentions) && mentions.length > 0 ? { mentions } : undefined;

      await sendMessageStream(token, conversationId, content, {
        workspaceContext,
        onChunk: (delta) => {
          if (genId !== generationRef.current) return;
          setStreamingText((prev) => (prev ?? '') + delta);
        },
        onProgress: (stage, message) => {
          if (genId !== generationRef.current) return;
          setWorkingStage(message || stage);
        },
        onDone: (conv) => {
          if (genId !== generationRef.current) return;
          streamingActiveRef.current = false;
          finishStream(conv);
        },
        onStopped: (conv) => {
          if (genId !== generationRef.current) return;
          streamingActiveRef.current = false;
          setStopped(true);
          finishStream(conv);
        },
        onError: (message) => {
          if (genId !== generationRef.current) return;
          streamingActiveRef.current = false;
          setStreamingText(null);
          setWorkingStage(null);
          setSending(false);
          if (message?.includes('unavailable') || message?.includes('offline')) {
            setProviderOffline(true);
          }
          notifyFromError(new Error(message || 'Could not send message'), 'Could not send message');
        },
      });

      // Safety net: if the stream ended without a terminal frame, release the UI.
      if (genId === generationRef.current && streamingActiveRef.current) {
        streamingActiveRef.current = false;
        setStreamingText(null);
        setWorkingStage(null);
        setSending(false);
      }
    },
    [token, conversationId, finishStream, notifyFromError],
  );

  const handleSend = useCallback(
    (content, extraMentions = []) => {
      streamSend(content, extraMentions);
    },
    [streamSend],
  );

  // Called when the conversation is refreshed after a summarize action.
  const handleSummarized = useCallback((updated) => {
    if (!updated) return;
    const canonical = normalizeConversationShape(updated);
    if (canonical) setConversation((prev) => ({ ...prev, ...canonical }));
  }, []);

  const handleFollowUp = useCallback(
    (question) => {
      handleSend(question);
    },
    [handleSend],
  );

  const handleStop = useCallback(async () => {
    if (!conversationId) return;
    try {
      await stopGeneration(token, conversationId);
    } catch (err) {
      notifyFromError(err, 'Could not stop generation');
    }
  }, [token, conversationId, notifyFromError]);

  const handleSteer = useCallback(
    async (content, mentions = []) => {
      if (!conversationId || !content?.trim()) return;
      try {
        await stopGeneration(token, conversationId);
      } catch (err) {
        notifyFromError(err, 'Could not interrupt generation');
        return;
      }
      streamSend(content, mentions);
    },
    [token, conversationId, notifyFromError, streamSend],
  );

  // Send-mode aware input: queue (buffer) / steer (stop then send) / stop.
  const handleInputSend = useCallback(
    (content, resolvedMentions = []) => {
      const val = (content || '').trim();
      if (!val) return;
      // Merge input-bar resolved mentions with any in-flight panel state.
      const allMentions = resolvedMentions.length ? resolvedMentions : mentions;
      if (!sending) {
        streamSend(val, allMentions);
        return;
      }
      if (sendMode === 'steer') {
        handleSteer(val, allMentions);
      } else {
        // queue — send once the current generation finishes.
        queuedRef.current = { content: val, mentions: allMentions };
      }
    },
    [sending, sendMode, streamSend, handleSteer, mentions],
  );

  // Flush a queued message once the current generation finishes.
  useEffect(() => {
    if (!sending && queuedRef.current) {
      const { content, mentions } = queuedRef.current;
      queuedRef.current = null;
      streamSend(content, mentions);
    }
  }, [sending, streamSend]);

  const handleContinue = useCallback(() => {
    streamSend(lastUserContentRef.current || 'Please continue.');
  }, [streamSend]);

  // Infinite scroll: page older messages when the user reaches the top.
  const loadOlder = useCallback(async () => {
    if (!conversationId || !hasMore || loadingMore) return;
    const oldest = messages[0];
    if (!oldest) return;
    setLoadingMore(true);
    try {
      const data = await listMessages(token, conversationId, { limit: 50, before: oldest.id });
      const older = data?.messages || [];
      setMessages((prev) => {
        const seen = new Set(prev.map((m) => m.id));
        const unique = older.filter((m) => !seen.has(m.id));
        return [...unique, ...prev];
      });
      setHasMore(!!data?.has_more);
    } catch {
      // transient pagination failure — ignore; user can scroll again.
    } finally {
      setLoadingMore(false);
    }
  }, [token, conversationId, hasMore, loadingMore, messages]);

  const handleScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el || !hasMore || loadingMore) return;
    if (el.scrollTop <= 40) {
      loadOlder();
    }
  }, [hasMore, loadingMore, loadOlder]);

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

  // Phase 8-B — "Test live" on a DQ suggestion: open a dedicated nl_rule_test
  // conversation scoped to the suggestion's table, so the engine can evaluate
  // the candidate rule against live rows before it is saved.
  const handleTestLive = useCallback(
    (suggestion) => {
      const tableId =
        suggestion?.table_id ??
        suggestion?.data_table ??
        suggestion?.definition?.table_id ??
        conversationRef.current?.task_payload_json?.table_id ??
        null;
      const nl = suggestion?.prompt || suggestion?.definition?.name || suggestion?.name || '';
      transferTask(
        'nl_rule_test',
        { table_id: tableId, nl },
        { title: `NL test: ${suggestion?.definition?.name || suggestion?.name || 'rule'}` },
      );
    },
    [transferTask],
  );

  // Phase 8-B — persist a tested NL rule into the DQ catalog.
  const handleSaveRule = useCallback(
    async (rulePreview) => {
      const tableId =
        rulePreview?.table_id ??
        conversationRef.current?.task_payload_json?.table_id ??
        null;
      const definition = {
        schema_version: 1,
        name: rulePreview?.name || rulePreview?.rule_text || 'NL rule',
        level: 'field',
        dimension: 'accuracy',
        type: rulePreview?.type || 'threshold',
        severity: rulePreview?.severity || 'warn',
        active: true,
        bindings: [],
        params: rulePreview?.params || {},
        enforcement: { on_write: false },
      };
      try {
        const created = await createDQRule(token, {
          definition,
          field_assignments_write: tableId
            ? [{ data_table: tableId, data_field: null }]
            : [],
          tag_ids: [],
        });
        notify({ message: `Saved rule "${created?.name || created?.id}"`, type: 'success' });
        return created;
      } catch (err) {
        notifyFromError(err, 'Could not save rule');
        throw err;
      }
    },
    [token, notify, notifyFromError],
  );

  // Phase 9-B — re-run the read-only investigation pipeline for the active
  // conversation by re-sending the same sentinel the one-click trigger uses.
  const handleRerunInvestigation = useCallback(() => {
    handleSend('Investigate this table');
  }, [handleSend]);

  // Phase 9-B — "Chat about this" on a finding: follow up in-thread.
  const handleChatAboutFinding = useCallback(
    (finding) => {
      const parts = [finding?.title, finding?.detail, finding?.recommended_action].filter(Boolean);
      handleSend(`Tell me more about this finding and how to resolve it: ${parts.join(' — ')}`);
    },
    [handleSend],
  );

  // Phase 9-B — "Create rule" on a finding: open an nl_rule_test conversation
  // scoped to the investigated table, seeded from the finding text, reusing the
  // Phase 8-B test → save flow.
  const handleCreateRuleFromFinding = useCallback(
    (finding) => {
      const tableId =
        conversationRef.current?.task_payload_json?.table_id ??
        conversationRef.current?.task_payload_json?.table ??
        null;
      const nl = [finding?.title, finding?.recommended_action].filter(Boolean).join(' — ');
      transferTask(
        'nl_rule_test',
        { table_id: tableId, nl },
        { title: `NL rule: ${finding?.title || 'finding'}` },
      );
    },
    [transferTask],
  );

  const updateMessageInState = useCallback((updatedMessage) => {
    if (!updatedMessage?.id) return;
    setMessages((prev) =>
      prev.map((m) => (m.id === updatedMessage.id ? { ...m, ...updatedMessage } : m)),
    );
  }, []);

  const persistFeedback = useCallback(
    async (message, outcome, correctionText = '') => {
      if (!message?.id) return;
      try {
        const updatedMessage = await recordFeedback(
          token,
          conversationId,
          message.id,
          outcome,
          correctionText,
        );
        updateMessageInState(updatedMessage);
      } catch (err) {
        notifyFromError(err, 'Could not save feedback');
      }
    },
    [token, conversationId, updateMessageInState, notifyFromError],
  );

  const handleAcceptFeedback = useCallback(
    (message) => persistFeedback(message, 'accepted'),
    [persistFeedback],
  );

  const handleRejectFeedback = useCallback(
    (message) => persistFeedback(message, 'rejected'),
    [persistFeedback],
  );

  const handleCorrectFeedback = useCallback(
    (message, correctionText) => persistFeedback(message, 'corrected', correctionText || ''),
    [persistFeedback],
  );

  const handlePromote = useCallback(
    async (message) => {
      if (!message?.id || !conversationId) return;
      const title = (message.content || '').slice(0, 80).trim() || 'AI Artifact';
      const artifactType =
        (message.metadata_json?.type || message.metadata?.type) === 'dq_suggestions' ? 'rule_set'
        : (message.metadata_json?.type || message.metadata?.type) === 'nl_query_result' ? 'query'
        : (message.metadata_json?.type || message.metadata?.type) === 'anomalies' ? 'analysis'
        : 'report';
      try {
        await createArtifact(token, {
          conversation_id: conversationId,
          message_id: message.id,
          title,
          artifact_type: artifactType,
          content_json: message.metadata_json || message.metadata || { content: message.content },
        });
        notify({ message: 'Promoted to artifact', type: 'success' });
      } catch (err) {
        notifyFromError(err, 'Could not promote artifact');
      }
    },
    [token, conversationId, notify, notifyFromError],
  );

  const handleExportMenuOpen = useCallback((event) => {
    setExportAnchorEl(event.currentTarget);
  }, []);

  const handleExportMenuClose = useCallback(() => {
    setExportAnchorEl(null);
  }, []);

  const handleExport = useCallback(
    async (format) => {
      setExportAnchorEl(null);
      if (!conversationId) return;
      try {
        const result = await exportConversation(token, conversationId, format);
        const isJson = format === 'json';
        const content = result?.content;
        const text = isJson
          ? JSON.stringify(content, null, 2)
          : typeof content === 'string'
            ? content
            : JSON.stringify(content, null, 2);
        const mime = isJson ? 'application/json' : 'text/markdown';
        const ext = isJson ? 'json' : 'md';
        const blob = new Blob([text], { type: `${mime};charset=utf-8` });
        const url = URL.createObjectURL(blob);
        const safeTitle =
          (conversation?.title || 'conversation')
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, '-')
            .replace(/^-+|-+$/g, '') || 'conversation';
        const link = document.createElement('a');
        link.href = url;
        link.download = `${safeTitle}.${ext}`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
        notify({ message: `Exported as ${isJson ? 'JSON' : 'Markdown'}`, type: 'success' });
      } catch (err) {
        notifyFromError(err, 'Could not export conversation');
      }
    },
    [token, conversationId, conversation, notify, notifyFromError],
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
    <Box sx={{ display: 'flex', flexDirection: 'row', height: '100%', overflow: 'hidden' }}>
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        flex: 1,
        minWidth: 0,
        height: '100%',
        overflow: 'hidden',
      }}
    >
      {providerOffline && <AIOfflineBanner />}

      {/* Export / provenance header action */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'flex-end',
          px: 1.5,
          py: 0.5,
          borderBottom: 1,
          borderColor: 'divider',
        }}
      >
        <Button
          size="small"
          variant="outlined"
          startIcon={<DownloadIcon />}
          endIcon={<ArrowDropDownIcon />}
          onClick={handleExportMenuOpen}
          aria-label="Export conversation"
        >
          Export
        </Button>
        <Menu
          anchorEl={exportAnchorEl}
          open={Boolean(exportAnchorEl)}
          onClose={handleExportMenuClose}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
          transformOrigin={{ vertical: 'top', horizontal: 'right' }}
        >
          <MenuItem onClick={() => handleExport('markdown')} sx={{ fontSize: '0.8125rem' }}>
            Markdown (.md)
          </MenuItem>
          <MenuItem onClick={() => handleExport('json')} sx={{ fontSize: '0.8125rem' }}>
            JSON (.json)
          </MenuItem>
        </Menu>
      </Box>

      {/* Messages area */}
      <Box
        ref={scrollRef}
        onScroll={handleScroll}
        sx={{
          flex: 1,
          overflowY: 'auto',
          overflowX: 'hidden',
          pt: 1,
          pb: 0.5,
        }}
      >
        {/* Phase 5B — pinned catch-up summary (distinct surface, not a bubble) */}
        {catchUp && (
          <Alert
            severity="info"
            icon={<HistoryIcon fontSize="inherit" />}
            onClose={() => setCatchUp(null)}
            sx={{
              mx: 1,
              mt: 1,
              borderRadius: 1,
              '& .MuiAlert-message': { flex: 1 },
            }}
          >
            <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
              Since your last visit
            </Typography>
            {typeof catchUp.hours_since_last_view === 'number' && (
              <Typography variant="caption" color="text.secondary">
                {catchUp.hours_since_last_view}h since your last visit
              </Typography>
            )}
            {Array.isArray(catchUp.summary_lines) && catchUp.summary_lines.length > 0 && (
              <Box component="ul" sx={{ m: 0, pl: 2.5, mt: 0.5 }}>
                {catchUp.summary_lines.map((line, i) => (
                  <Box component="li" key={i}>
                    <Typography variant="caption" color="text.primary">
                      {line}
                    </Typography>
                  </Box>
                ))}
              </Box>
            )}
          </Alert>
        )}

        {loadingMore && (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 0.5 }}>
            <Typography variant="caption" color="text.disabled">
              Loading older messages…
            </Typography>
          </Box>
        )}

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
            onAccept={handleAcceptFeedback}
            onReject={handleRejectFeedback}
            onCorrect={handleCorrectFeedback}
            onFollowUp={handleFollowUp}
            onPromote={handlePromote}
            conversationType={conversationType}
            appIdentifier={conversation.app_identifier}
            scopeJson={conversation.scope_json}
            executeMode={executeMode}
            onTestLive={handleTestLive}
            onSave={handleSaveRule}
            onRerun={handleRerunInvestigation}
            onChatAbout={handleChatAboutFinding}
            onCreateRule={handleCreateRuleFromFinding}
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
            <AIWorkingIndicator conversationType={conversationType} stage={workingStage} />
            {workingNotice && (
              <Box sx={{ px: 2, pb: 1 }}>
                <Typography variant="caption" color="text.secondary">
                  {workingNotice}
                </Typography>
              </Box>
            )}
          </>
        ) : null}

        {stopped && !isWorking && (
          <Stack direction="row" spacing={1} alignItems="center" sx={{ px: 2, py: 1 }}>
            <Chip
              size="small"
              color="warning"
              label="Interrupted"
              sx={{ fontSize: '0.625rem', height: 20 }}
            />
            <Button size="small" variant="outlined" onClick={handleContinue}>
              Continue
            </Button>
          </Stack>
        )}

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
        onSend={handleInputSend}
        working={isWorking}
        sendMode={sendMode}
        onModeChange={setSendMode}
        onStop={handleStop}
        conversationStatus={convStatus}
        onMentionsChange={setMentions}
      />
    </Box>

    {/* Context panel — collapsible right rail */}
    <AIContextPanel
      conversation={conversation}
      mentions={mentions}
      onSummarized={handleSummarized}
    />
    </Box>
  );
}

AIConversationView.propTypes = {
  conversationId: PropTypes.string.isRequired,
};

export default AIConversationView;
