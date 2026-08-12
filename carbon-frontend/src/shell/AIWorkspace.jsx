// src/shell/AIWorkspace.jsx
// AI Workspace — tabbed multi-conversation AI interface replacing PulsePane.
// Supports: empty state (no conversations), active conversations, working/polling,
// needs_input (follow-up questions), offline, and error states.
//
// RULE_8: Uses theme tokens only — no raw hex/px.
// RULE_17: Stores selected tab in localStorage (key: carbon-ai-active-conversation).

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Box, Typography } from '@mui/material';
import { useAuth } from '../auth/AuthContext';
import { useNotification } from '../components/NotificationProvider';
import {
  createConversation as apiCreateConversation,
  listConversations as apiListConversations,
} from '../api/aiWorkspace';
import AIWorkspaceHeader from './AIWorkspaceHeader';
import AIConversationTabs from './AIConversationTabs';
import AIConversationView from './AIConversationView';
import AIEmptyState from './AIEmptyState';
import AIOfflineBanner from './AIOfflineBanner';
import { useAITaskTransfer } from './useAITaskTransfer';

const LOCAL_STORAGE_KEY = 'carbon-ai-active-conversation';

export function AIWorkspace({ onClose }) {
  const { token } = useAuth();
  const { notifyFromError } = useNotification();
  const { pendingTransferId, clearPendingTransfer } = useAITaskTransfer();

  const [conversations, setConversations] = useState([]);
  const [activeId, setActiveId] = useState(() => {
    try {
      return localStorage.getItem(LOCAL_STORAGE_KEY) || null;
    } catch {
      return null;
    }
  });
  const [loading, setLoading] = useState(true);
  const [providerOffline, setProviderOffline] = useState(false);

  const activeRef = useRef(activeId);
  activeRef.current = activeId;

  // Load conversation list on mount
  const loadList = useCallback(async () => {
    try {
      const data = await apiListConversations(token, { limit: 50 });
      setConversations(data);
      setProviderOffline(false);
    } catch (err) {
      if (err.message?.includes('unavailable') || err.message?.includes('offline')) {
        setProviderOffline(true);
      } else {
        notifyFromError(err, 'Could not load conversations');
      }
    } finally {
      setLoading(false);
    }
  }, [token, notifyFromError]);

  useEffect(() => {
    loadList();
  }, [loadList]);

  // React to task transfers from the main workspace
  useEffect(() => {
    if (!pendingTransferId) return;
    (async () => {
      try {
        const data = await apiListConversations(token, { limit: 50 });
        setConversations(data);
        setActiveId(pendingTransferId);
      } catch {
        // failed silently — conversation will appear on next load
      } finally {
        clearPendingTransfer();
      }
    })();
  }, [pendingTransferId, token, clearPendingTransfer]);

  // Save active conversation to localStorage
  useEffect(() => {
    try {
      if (activeId) {
        localStorage.setItem(LOCAL_STORAGE_KEY, activeId);
      } else {
        localStorage.removeItem(LOCAL_STORAGE_KEY);
      }
    } catch {
      /* ignore */
    }
  }, [activeId]);

  // If active conversation no longer exists, switch to another
  useEffect(() => {
    if (
      activeId &&
      conversations.length > 0 &&
      !conversations.find((c) => c.id === activeId)
    ) {
      setActiveId(conversations[0].id);
    }
  }, [activeId, conversations]);

  // Handle new chat
  const handleNewChat = useCallback(async () => {
    try {
      const conv = await apiCreateConversation(token, {
        conversation_type: 'chat',
        title: 'New Chat',
      });
      setConversations((prev) => [conv, ...prev]);
      setActiveId(conv.id);
    } catch (err) {
      notifyFromError(err, 'Could not create conversation');
    }
  }, [token, notifyFromError]);

  // Handle close tab
  const handleCloseTab = useCallback(
    (convId) => {
      setConversations((prev) => {
        const next = prev.filter((c) => c.id !== convId);
        if (activeRef.current === convId) {
          if (next.length > 0) {
            setActiveId(next[0].id);
          } else {
            setActiveId(null);
          }
        }
        return next;
      });
    },
    [],
  );

  // Compute status
  const activeConversation = useMemo(
    () => conversations.find((c) => c.id === activeId) || null,
    [conversations, activeId],
  );

  // Edge: loading
  if (loading) {
    return (
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          height: '100%',
          bgcolor: 'background.default',
        }}
      >
        <AIWorkspaceHeader onClose={onClose} />
        <Box
          sx={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <Typography variant="caption" color="text.secondary">
            Loading…
          </Typography>
        </Box>
      </Box>
    );
  }

  // Edge: no conversations
  const isEmpty = conversations.length === 0;

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        bgcolor: 'background.default',
      }}
    >
      <AIWorkspaceHeader onClose={onClose} />

      {providerOffline && <AIOfflineBanner />}

      {!isEmpty && (
        <AIConversationTabs
          conversations={conversations}
          activeId={activeId}
          onSelect={setActiveId}
          onNew={handleNewChat}
          onClose={handleCloseTab}
        />
      )}

      {isEmpty ? (
        <AIEmptyState onStartChat={handleNewChat} />
      ) : activeConversation ? (
        <AIConversationView
          key={activeConversation.id}
          conversationId={activeConversation.id}
        />
      ) : (
        <AIEmptyState onStartChat={handleNewChat} />
      )}
    </Box>
  );
}

export default AIWorkspace;
