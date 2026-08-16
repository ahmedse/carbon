// src/shell/AIWorkspace.jsx
// AI Workspace — tabbed multi-conversation AI interface replacing PulsePane.
// Supports: empty state (no conversations), active conversations, working/streaming,
// needs_input (follow-up questions), offline, and error states.
//
// RULE_8: Uses theme tokens only — no raw hex/px.
// RULE_10: all API via apiFetch (src/api/aiWorkspace.js).
// RULE_17: Stores selected tab in localStorage (key: carbon-ai-active-conversation).

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Tab,
  Tabs,
  TextField,
  Typography,
} from '@mui/material';
import { useAuth } from '../auth/AuthContext';
import { useNotification } from '../components/NotificationProvider';
import {
  createConversation as apiCreateConversation,
  listConversations as apiListConversations,
  updateConversation as apiUpdateConversation,
  deleteConversation as apiDeleteConversation,
} from '../api/aiWorkspace';
import AIWorkspaceHeader from './AIWorkspaceHeader';
import AIConversationTabs from './AIConversationTabs';
import AIConversationView from './AIConversationView';
import AIEmptyState from './AIEmptyState';
import AIOfflineBanner from './AIOfflineBanner';
import AIArtifactBrowser from './AIArtifactBrowser';
import AISuggestionRail from './AISuggestionRail';
import { useAITaskTransfer } from './useAITaskTransfer';

const LOCAL_STORAGE_KEY = 'carbon-ai-active-conversation';

export function AIWorkspace({ onClose }) {
  const { token } = useAuth();
  const { notifyFromError } = useNotification();
  const { pendingTransferId, clearPendingTransfer } = useAITaskTransfer();

  // Durable, id-keyed store (normalized).
  const [byId, setById] = useState({});
  const [order, setOrder] = useState([]); // visible (non-archived) ids, pinned first
  const [archivedIds, setArchivedIds] = useState([]);
  const [activeId, setActiveId] = useState(() => {
    try {
      return localStorage.getItem(LOCAL_STORAGE_KEY) || null;
    } catch {
      return null;
    }
  });
  const [query, setQuery] = useState('');
  const [showArchived, setShowArchived] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [loading, setLoading] = useState(true);
  const [providerOffline, setProviderOffline] = useState(false);
  // Fixed mode tabs: 'chat' | 'artifacts'
  const [mode, setMode] = useState('chat');

  const activeRef = useRef(activeId);
  activeRef.current = activeId;
  const lastArchivedRef = useRef(null);

  // Index a list of conversation summaries into the normalized store.
  const indexList = useCallback((list) => {
    const nextById = {};
    const nextOrder = [];
    const nextArchived = [];
    for (const c of list || []) {
      if (!c?.id) continue;
      nextById[c.id] = c;
      if (c.is_archived) nextArchived.push(c.id);
      else nextOrder.push(c.id);
    }
    // Pinned conversations float to the front.
    nextOrder.sort(
      (a, b) => (nextById[b]?.is_pinned ? 1 : 0) - (nextById[a]?.is_pinned ? 1 : 0),
    );
    setById(nextById);
    setOrder(nextOrder);
    setArchivedIds(nextArchived);
  }, []);

  // Load conversation list on mount.
  const loadList = useCallback(async () => {
    try {
      const data = await apiListConversations(token, { limit: 200 });
      indexList(data);
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
  }, [token, notifyFromError, indexList]);

  useEffect(() => {
    loadList();
  }, [loadList]);

  // React to task transfers from the main workspace.
  useEffect(() => {
    if (!pendingTransferId) return;
    (async () => {
      try {
        const data = await apiListConversations(token, { limit: 200 });
        indexList(data);
        setActiveId(pendingTransferId);
      } catch {
        // failed silently — conversation will appear on next load
      } finally {
        clearPendingTransfer();
      }
    })();
  }, [pendingTransferId, token, clearPendingTransfer, indexList]);

  // Save active conversation to localStorage.
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

  // Visible ids after archived-filter + client-side title search.
  const visibleIds = useMemo(() => {
    const source = showArchived ? archivedIds : order;
    const q = query.trim().toLowerCase();
    if (!q) return source;
    return source.filter((id) => (byId[id]?.title || '').toLowerCase().includes(q));
  }, [showArchived, archivedIds, order, query, byId]);

  const visibleConversations = useMemo(
    () => visibleIds.map((id) => byId[id]).filter(Boolean),
    [visibleIds, byId],
  );

  // The active tab must always reference a visible conversation. Derive the
  // effective id so the Tabs `value` is always valid (MUI rejects a null or
  // stale value with "The `value` provided to the Tabs component is invalid").
  // Falls back to the first visible conversation when none is active — e.g. a
  // fresh session with no stored selection, or the active tab was just closed.
  const effectiveActiveId = useMemo(
    () => (visibleIds.includes(activeId) ? activeId : visibleIds[0] || null),
    [visibleIds, activeId],
  );

  // Persist the effective id into state so localStorage and the activeRef
  // (Ctrl+W archive target) stay in sync with what's actually rendered.
  useEffect(() => {
    if (activeId !== effectiveActiveId) {
      setActiveId(effectiveActiveId);
    }
  }, [activeId, effectiveActiveId]);

  // Handle new chat.
  const handleNewChat = useCallback(async () => {
    try {
      const conv = await apiCreateConversation(token, {
        conversation_type: 'chat',
        title: 'New Chat',
      });
      setById((prev) => ({ ...prev, [conv.id]: conv }));
      setOrder((prev) => [conv.id, ...prev]);
      setActiveId(conv.id);
      setShowArchived(false);
    } catch (err) {
      notifyFromError(err, 'Could not create conversation');
    }
  }, [token, notifyFromError]);

  // Archive (persistent close). Reversible via restore.
  const handleArchive = useCallback(
    async (convId) => {
      if (!convId) return;
      lastArchivedRef.current = convId;
      setOrder((prev) => prev.filter((x) => x !== convId));
      setArchivedIds((prev) => [convId, ...prev]);
      try {
        await apiUpdateConversation(token, convId, { is_archived: true });
      } catch (err) {
        notifyFromError(err, 'Could not archive conversation');
      }
    },
    [token, notifyFromError],
  );

  // Restore an archived conversation and make it active.
  const handleRestore = useCallback(
    async (convId) => {
      if (!convId) return;
      setArchivedIds((prev) => prev.filter((x) => x !== convId));
      setOrder((prev) => [convId, ...prev]);
      setActiveId(convId);
      setShowArchived(false);
      try {
        const updated = await apiUpdateConversation(token, convId, { is_archived: false });
        setById((prev) => ({ ...prev, [convId]: updated }));
      } catch (err) {
        notifyFromError(err, 'Could not restore conversation');
      }
    },
    [token, notifyFromError],
  );

  // Context-menu archive/restore toggle.
  const handleToggleArchive = useCallback(
    (convId) => {
      const conv = byId[convId];
      if (conv?.is_archived) handleRestore(convId);
      else handleArchive(convId);
    },
    [byId, handleRestore, handleArchive],
  );

  // Pin / unpin toggle.
  const handlePin = useCallback(
    async (convId) => {
      const current = byId[convId];
      if (!current) return;
      const nextPinned = !current.is_pinned;
      setById((prev) => ({
        ...prev,
        [convId]: { ...prev[convId], is_pinned: nextPinned },
      }));
      try {
        const updated = await apiUpdateConversation(token, convId, { is_pinned: nextPinned });
        setById((prev) => ({ ...prev, [convId]: updated }));
      } catch (err) {
        notifyFromError(err, 'Could not update pin');
        setById((prev) => ({
          ...prev,
          [convId]: { ...prev[convId], is_pinned: current.is_pinned },
        }));
      }
    },
    [token, byId, notifyFromError],
  );

  // Rename conversation title.
  const handleRename = useCallback(
    async (convId, title) => {
      const t = (title || '').trim();
      if (!convId || !t) return;
      setById((prev) => ({
        ...prev,
        [convId]: { ...prev[convId], title: t },
      }));
      try {
        const updated = await apiUpdateConversation(token, convId, { title: t });
        setById((prev) => ({ ...prev, [convId]: updated }));
      } catch (err) {
        notifyFromError(err, 'Could not rename conversation');
      }
    },
    [token, notifyFromError],
  );

  // Delete (confirm dialog → hard delete).
  const confirmDelete = useCallback(async () => {
    if (!deleteTarget) return;
    const id = deleteTarget;
    setDeleteTarget(null);
    setById((prev) => {
      const { [id]: _removed, ...rest } = prev;
      return rest;
    });
    setOrder((prev) => prev.filter((x) => x !== id));
    setArchivedIds((prev) => prev.filter((x) => x !== id));
    try {
      await apiDeleteConversation(token, id);
    } catch (err) {
      notifyFromError(err, 'Could not delete conversation');
    }
  }, [deleteTarget, token, notifyFromError]);

  // Selecting an archived tab restores it; otherwise just switch.
  const handleSelect = useCallback(
    (convId) => {
      const conv = byId[convId];
      if (conv?.is_archived) handleRestore(convId);
      else setActiveId(convId);
    },
    [byId, handleRestore],
  );

  // Search submit → refetch with ?q=.
  const handleSearchSubmit = useCallback(async () => {
    try {
      const data = await apiListConversations(token, { q: query.trim(), limit: 200 });
      indexList(data);
    } catch (err) {
      notifyFromError(err, 'Could not search conversations');
    }
  }, [token, query, indexList, notifyFromError]);

  // Keyboard: Ctrl+W archives active tab; Ctrl+Shift+T restores last-archived.
  useEffect(() => {
    const handler = (e) => {
      const isCtrl = e.ctrlKey || e.metaKey;
      if (!isCtrl) return;
      if (e.shiftKey && e.key.toLowerCase() === 't') {
        e.preventDefault();
        const last = lastArchivedRef.current;
        if (last) handleRestore(last);
      } else if (!e.shiftKey && e.key.toLowerCase() === 'w') {
        e.preventDefault();
        if (activeRef.current) handleArchive(activeRef.current);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [handleRestore, handleArchive]);

  // Compute status.
  const activeConversation = useMemo(
    () => (effectiveActiveId ? byId[effectiveActiveId] || null : null),
    [byId, effectiveActiveId],
  );

  // Edge: loading.
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

  const hasAny = order.length > 0 || archivedIds.length > 0;

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

      {/* Fixed mode tabs — never dynamic per conversation */}
      <Tabs
        value={mode}
        onChange={(_, v) => setMode(v)}
        sx={{ minHeight: 36, borderBottom: 1, borderColor: 'divider', '& .MuiTab-root': { minHeight: 36, py: 0, px: 2, fontSize: '0.8125rem', textTransform: 'none' } }}
      >
        <Tab label="Chat" value="chat" />
        <Tab label="Artifacts" value="artifacts" />
      </Tabs>

      {providerOffline && <AIOfflineBanner />}

      {hasAny && (
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1,
            px: 1,
            py: 0.5,
            borderBottom: 1,
            borderColor: 'divider',
          }}
        >
          <TextField
            size="small"
            placeholder="Search conversations…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSearchSubmit();
            }}
            inputProps={{ 'aria-label': 'Search conversations' }}
            sx={{ '& .MuiOutlinedInput-root': { fontSize: '0.8125rem' } }}
          />
          <Button
            size="small"
            variant={showArchived ? 'outlined' : 'text'}
            onClick={() => setShowArchived((v) => !v)}
          >
            Archived ({archivedIds.length})
          </Button>
        </Box>
      )}

      {/* Phase 5B — proactive suggestions rail, pinned above the thread rail.
          Only rendered when there is an effective active conversation. */}
      {hasAny && effectiveActiveId && (
        <AISuggestionRail conversationId={effectiveActiveId} />
      )}

      {hasAny && (
        <AIConversationTabs
          conversations={visibleConversations}
          activeId={effectiveActiveId}
          onSelect={handleSelect}
          onNew={handleNewChat}
          onClose={handleArchive}
          onRename={handleRename}
          onPin={handlePin}
          onArchive={handleToggleArchive}
          onDelete={(id) => setDeleteTarget(id)}
        />
      )}

      {mode === 'artifacts' ? (
        <AIArtifactBrowser />
      ) : !hasAny ? (
        <AIEmptyState onStartChat={handleNewChat} />
      ) : activeConversation ? (
        <AIConversationView
          key={activeConversation.id}
          conversationId={activeConversation.id}
        />
      ) : (
        <AIEmptyState onStartChat={handleNewChat} />
      )}

      {/* Delete confirmation */}
      <Dialog open={Boolean(deleteTarget)} onClose={() => setDeleteTarget(null)}>
        <DialogTitle>Delete conversation?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            This permanently removes the conversation and its messages.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button size="small" onClick={() => setDeleteTarget(null)}>
            Cancel
          </Button>
          <Button size="small" color="error" variant="contained" onClick={confirmDelete}>
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

export default AIWorkspace;
