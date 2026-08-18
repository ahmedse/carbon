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
  IconButton,
  Tab,
  Tabs,
  Tooltip,
  Typography,
} from '@mui/material';
import AddCommentOutlinedIcon from '@mui/icons-material/AddCommentOutlined';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import DataUsageIcon from '@mui/icons-material/DataUsage';
import ForumOutlinedIcon from '@mui/icons-material/ForumOutlined';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import Inventory2OutlinedIcon from '@mui/icons-material/Inventory2Outlined';
import ManageSearchIcon from '@mui/icons-material/ManageSearch';
import PsychologyOutlinedIcon from '@mui/icons-material/PsychologyOutlined';
import SettingsOutlinedIcon from '@mui/icons-material/SettingsOutlined';
import { useAuth } from '../auth/AuthContext';
import { useNotification } from '../components/NotificationProvider';
import {
  createConversation as apiCreateConversation,
  findOpenConversation,
  listConversations as apiListConversations,
  sendMessage as apiSendMessage,
  updateConversation as apiUpdateConversation,
  deleteConversation as apiDeleteConversation,
} from '../api/aiWorkspace';
import { listDomainManifests } from '../api/aiPulse';
import AIContextPanel from './AIContextPanel';
import AIWorkspaceHeader from './AIWorkspaceHeader';
import AIConversationTabs from './AIConversationTabs';
import AIConversationView from './AIConversationView';
import AIEmptyState from './AIEmptyState';
import AIOfflineBanner from './AIOfflineBanner';
import AIArtifactBrowser from './AIArtifactBrowser';
import AISuggestionRail from './AISuggestionRail';
import AIUsageTab from './AIUsageTab';
import AISettingsTab from './AISettingsTab';
import AIMemoryTab from './AIMemoryTab';
import AILearntTab from './AILearntTab';
import AIRelationshipTab from './AIRelationshipTab';
import InvestigateTab from './InvestigateTab';
import { useAITaskTransfer } from './useAITaskTransfer';
import { ExecuteModeProvider } from './ExecuteModeContext';

const LOCAL_STORAGE_KEY = 'carbon-ai-active-conversation';

// RULE_17: grouped Memory surface persists its internal tab selection.
const MEMORY_TAB_KEY = 'carbon-ai-memory-tab';

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
  const [query] = useState('');
  // Sessions drawer starts collapsed (VS Code Copilot-style) — the user opens
  // it via the Sessions activity-bar icon when needed.
  const [activePanel, setActivePanel] = useState(null);
  // Grouped Memory surface: episodes (memory) / facts (learnt) / relationship
  // are one domain — one activity icon, internal MUI Tabs (RULE_17).
  const [memoryTab, setMemoryTab] = useState(() => {
    try {
      return localStorage.getItem(MEMORY_TAB_KEY) || 'episodes';
    } catch {
      return 'episodes';
    }
  });
  const [drawerWidth, setDrawerWidth] = useState(200);
  const dragRef = useRef(null);
  const [showArchived, setShowArchived] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [loading, setLoading] = useState(true);
  const [providerOffline, setProviderOffline] = useState(false);
  const [manifests, setManifests] = useState([]);

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

  // Load domain-app manifests once on mount. Failures are silent — an empty
  // manifests array simply keeps the existing empty-state fallback.
  useEffect(() => {
    listDomainManifests(token)
      .then((data) => setManifests(data?.apps || []))
      .catch(() => setManifests([]));
  }, [token]);

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

  // Persist the grouped Memory tab (RULE_17).
  useEffect(() => {
    try {
      localStorage.setItem(MEMORY_TAB_KEY, memoryTab);
    } catch {
      /* ignore */
    }
  }, [memoryTab]);

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

  // Phase 9-B — investigate conversations, newest first.
  const investigateConversations = useMemo(() => {
    const list = order
      .map((id) => byId[id])
      .filter((c) => c && c.conversation_type === 'investigate');
    return [...list].sort((a, b) => {
      const ta = a.updated_at || a.last_message_at || a.created_at || '';
      const tb = b.updated_at || b.last_message_at || b.created_at || '';
      return String(tb).localeCompare(String(ta));
    });
  }, [order, byId]);

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
      // Phase 16 — reuse the most recent open chat thread instead of always
      // creating a new one.
      const existing = await findOpenConversation(token, {
        conversation_type: 'chat',
      });
      if (existing) {
        setActiveId(existing.id);
        setShowArchived(false);
        return;
      }
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

  // Handle a manifest starter chip: open a conversation of the right type and
  // (for prompt-bearing chips) seed the first user message.
  const handleStartStarter = useCallback(
    async (appId, taskType, label, prompt) => {
      try {
        const conv = await apiCreateConversation(token, {
          conversation_type: taskType,
          title: label,
          app_identifier: appId,
        });
        setById((prev) => ({ ...prev, [conv.id]: conv }));
        setOrder((prev) => [conv.id, ...prev]);
        setActiveId(conv.id);
        setShowArchived(false);
        if (prompt) {
          await apiSendMessage(token, conv.id, prompt);
        }
      } catch (err) {
        notifyFromError(err, 'Could not start conversation');
      }
    },
    [token, notifyFromError],
  );

  // Phase 9-B — "New investigation" opens a bare investigate conversation
  // (chat-style); the real one-click trigger lives on the table detail page.
  const handleNewInvestigation = useCallback(async () => {
    try {
      const conv = await apiCreateConversation(token, {
        conversation_type: 'investigate',
        title: 'Investigation',
        task_payload: { type: 'investigate' },
      });
      setById((prev) => ({ ...prev, [conv.id]: conv }));
      setOrder((prev) => [conv.id, ...prev]);
      setActiveId(conv.id);
      setShowArchived(false);
      setActivePanel('sessions');
    } catch (err) {
      notifyFromError(err, 'Could not create investigation');
    }
  }, [token, notifyFromError]);

  // Phase 9-B — open an investigate conversation's thread (rendered in chat mode).
  const handleOpenInvestigation = useCallback((convId) => {
    setActiveId(convId);
    setActivePanel('sessions');
  }, []);

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
  const startDrawerResize = useCallback((e) => {
    e.preventDefault();
    dragRef.current = { startX: e.clientX, startW: drawerWidth };
    const onMove = (ev) => {
      const delta = dragRef.current.startX - ev.clientX;
      setDrawerWidth(Math.min(360, Math.max(140, dragRef.current.startW + delta)));
    };
    const onUp = () => {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
    };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  }, [drawerWidth]);

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

  const togglePanel = (panel) => setActivePanel((prev) => (prev === panel ? null : panel));

  return (
    <ExecuteModeProvider>
      <Box sx={{ display: 'flex', height: '100%', bgcolor: 'background.default' }}>

        {/* Main content — leftmost, flex:1 */}
        <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, overflow: 'hidden' }}>
          <AIWorkspaceHeader onClose={onClose} />
          {providerOffline && <AIOfflineBanner />}
          {activePanel === 'usage' ? (
            <AIUsageTab />
          ) : activePanel === 'settings' ? (
            <AISettingsTab />
          ) : activePanel === 'memory' ? (
            /* Grouped Memory surface: episodes / facts / relationship are one
               domain — internal MUI Tabs (RULE_17), like Copilot's grouped views. */
            <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
              <Box sx={{ px: 1, pt: 0.5, borderBottom: 1, borderColor: 'divider' }}>
                <Tabs
                  value={memoryTab}
                  onChange={(e, v) => setMemoryTab(v)}
                  variant="fullWidth"
                  aria-label="Memory views"
                  sx={{
                    minHeight: 34,
                    '& .MuiTab-root': { minHeight: 34, fontSize: '0.6875rem', py: 0.5 },
                  }}
                >
                  <Tab value="episodes" label="Episodes" />
                  <Tab value="facts" label="Facts" />
                  <Tab value="relationship" label="Relationship" />
                </Tabs>
              </Box>
              <Box sx={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
                {memoryTab === 'episodes' ? (
                  <AIMemoryTab />
                ) : memoryTab === 'facts' ? (
                  <AILearntTab />
                ) : (
                  <AIRelationshipTab
                    onShowFacts={() => setMemoryTab('facts')}
                    onShowEpisodes={() => setMemoryTab('episodes')}
                    onShowUsage={() => setActivePanel('usage')}
                  />
                )}
              </Box>
            </Box>
          ) : activePanel === 'investigate' ? (
            <InvestigateTab conversations={investigateConversations} onSelect={handleOpenInvestigation} onNew={handleNewInvestigation} />
          ) : activePanel === 'artifacts' ? (
            <AIArtifactBrowser />
          ) : !hasAny ? (
            <AIEmptyState onStartChat={handleNewChat} manifests={manifests} onStartStarter={handleStartStarter} />
          ) : activeConversation ? (
            <AIConversationView key={activeConversation.id} conversationId={activeConversation.id} showContextPanel={false} />
          ) : (
            <AIEmptyState onStartChat={handleNewChat} manifests={manifests} onStartStarter={handleStartStarter} />
          )}
        </Box>

        {/* Drawer — sessions or context; pushes chat area, never overlays */}
        {(activePanel === 'sessions' || activePanel === 'context') && (
          <Box sx={{ width: drawerWidth, flexShrink: 0, display: 'flex', flexDirection: 'column', borderLeft: 1, borderColor: 'divider', overflow: 'hidden', position: 'relative' }}>
            {/* Drag handle */}
            <Box onMouseDown={startDrawerResize} sx={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 4, cursor: 'col-resize', zIndex: 10, '&:hover': { bgcolor: 'primary.main', opacity: 0.4 } }} />

            {activePanel === 'sessions' ? (
              <>
                <Box sx={{ display: 'flex', alignItems: 'center', px: 1.25, py: 0.625, borderBottom: 1, borderColor: 'divider' }}>
                  <Typography variant="caption" sx={{ flex: 1, fontWeight: 600, fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.07em', color: 'text.secondary' }}>
                    Sessions
                  </Typography>
                  {archivedIds.length > 0 && (
                    <Button size="small" variant={showArchived ? 'outlined' : 'text'} onClick={() => setShowArchived((v) => !v)} sx={{ fontSize: '0.65rem', minWidth: 0, px: 0.75, py: 0 }}>
                      {archivedIds.length} archived
                    </Button>
                  )}
                  <Tooltip title="Collapse">
                    <IconButton size="small" onClick={() => setActivePanel(null)} sx={{ p: 0.25, ml: 0.25 }} aria-label="Collapse sessions panel">
                      <ChevronRightIcon sx={{ fontSize: 14 }} />
                    </IconButton>
                  </Tooltip>
                </Box>
                {effectiveActiveId && <AISuggestionRail conversationId={effectiveActiveId} />}
                <Box sx={{ flex: 1, overflowY: 'auto' }}>
                  <AIConversationTabs
                    compact
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
                </Box>
              </>
            ) : (
              /* Context drawer */
              <Box sx={{ flex: 1, overflowY: 'auto' }}>
                <Box sx={{ display: 'flex', alignItems: 'center', px: 1.25, py: 0.625, borderBottom: 1, borderColor: 'divider', position: 'sticky', top: 0, bgcolor: 'background.paper', zIndex: 1 }}>
                  <Typography variant="caption" sx={{ flex: 1, fontWeight: 600, fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.07em', color: 'text.secondary' }}>
                    Context
                  </Typography>
                  <Tooltip title="Collapse">
                    <IconButton size="small" onClick={() => setActivePanel(null)} sx={{ p: 0.25 }} aria-label="Collapse context panel">
                      <ChevronRightIcon sx={{ fontSize: 14 }} />
                    </IconButton>
                  </Tooltip>
                </Box>
                {activeConversation ? (
                  <AIContextPanel
                    conversation={activeConversation}
                    mentions={[]}
                    onSummarized={(updated) => setById((prev) => ({ ...prev, [updated.id]: { ...prev[updated.id], ...updated } }))}
                    defaultOpen
                  />
                ) : (
                  <Typography variant="caption" color="text.disabled" sx={{ display: 'block', p: 1.5, fontSize: '0.75rem' }}>
                    Open a conversation to see its context.
                  </Typography>
                )}
              </Box>
            )}
          </Box>
        )}

        {/* Activity bar — rightmost edge */}
        <Box
          sx={{
            width: 32,
            flexShrink: 0,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            borderLeft: 1,
            borderColor: 'divider',
            bgcolor: 'background.paper',
            py: 0.5,
          }}
        >
          {[
            { id: 'sessions',     icon: <ForumOutlinedIcon sx={{ fontSize: 16 }} />,             label: 'Sessions'     },
            { id: 'context',      icon: <InfoOutlinedIcon sx={{ fontSize: 16 }} />,               label: 'Context'      },
            { id: 'investigate',  icon: <ManageSearchIcon sx={{ fontSize: 16 }} />,               label: 'Investigate'  },
            { id: 'artifacts',    icon: <Inventory2OutlinedIcon sx={{ fontSize: 16 }} />,         label: 'Artifacts'    },
            { id: 'usage',        icon: <DataUsageIcon sx={{ fontSize: 16 }} />,                  label: 'Usage'        },
            { id: 'memory',       icon: <PsychologyOutlinedIcon sx={{ fontSize: 16 }} />,         label: 'Memory'       },
            { id: 'settings',     icon: <SettingsOutlinedIcon sx={{ fontSize: 16 }} />,           label: 'Settings'     },
          ].map(({ id, icon, label }) => (
            <Tooltip key={id} title={label} placement="left">
              <Box sx={{ width: '100%', display: 'flex', justifyContent: 'center', borderRight: 2, borderColor: activePanel === id ? 'primary.main' : 'transparent' }}>
                <IconButton
                  size="small"
                  onClick={() => togglePanel(id)}
                  color={activePanel === id ? 'primary' : 'default'}
                  aria-label={label}
                  aria-pressed={activePanel === id}
                  sx={{ p: 0.875, borderRadius: 1 }}
                >
                  {icon}
                </IconButton>
              </Box>
            </Tooltip>
          ))}
          <Box sx={{ flex: 1 }} />
          <Tooltip title="New chat" placement="left">
            <IconButton size="small" onClick={handleNewChat} aria-label="New chat" sx={{ p: 0.875 }}>
              <AddCommentOutlinedIcon sx={{ fontSize: 16 }} />
            </IconButton>
          </Tooltip>
        </Box>

        <Dialog open={Boolean(deleteTarget)} onClose={() => setDeleteTarget(null)}>
          <DialogTitle>Delete conversation?</DialogTitle>
          <DialogContent>
            <DialogContentText>This permanently removes the conversation and its messages.</DialogContentText>
          </DialogContent>
          <DialogActions>
            <Button size="small" onClick={() => setDeleteTarget(null)}>Cancel</Button>
            <Button size="small" color="error" variant="contained" onClick={confirmDelete}>Delete</Button>
          </DialogActions>
        </Dialog>
      </Box>
    </ExecuteModeProvider>
  );

}

export default AIWorkspace;
