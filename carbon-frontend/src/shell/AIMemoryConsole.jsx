// src/shell/AIMemoryConsole.jsx
// G2 — Unified memory console: Learned / Episodes / Session / Org sub-tabs.
// RULE_8: theme tokens only — no raw hex. RULE_10: apiFetch via aiWorkspace.js.
import React, { useCallback, useEffect, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Button,
  Chip,
  IconButton,
  Snackbar,
  Stack,
  Tab,
  Tabs,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import CheckIcon from '@mui/icons-material/Check';
import CloseIcon from '@mui/icons-material/Close';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import { useAuth } from '../auth/AuthContext';
import { useNotification } from '../components/NotificationProvider';
import {
  listFacts,
  forgetFact,
  updateMemoryFact,
  restoreMemoryFact,
  listOrgMemory,
} from '../api/aiWorkspace';
import AIMemoryTab from './AIMemoryTab';

dayjs.extend(relativeTime);

const CONSOLE_TAB_KEY = 'carbon-ai-memory-tab';

const CHIP_COLOR = { preference: 'primary', feedback: 'secondary', context: 'default' };

// ── Single fact row with inline edit ────────────────────────────────────────

function FactRow({ fact, onEdit, onDelete }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(fact.content || '');

  const handleEditStart = () => {
    setDraft(fact.content || '');
    setEditing(true);
  };

  const handleCancel = () => {
    setDraft(fact.content || '');
    setEditing(false);
  };

  const handleSave = () => {
    const trimmed = draft.trim();
    if (trimmed) onEdit(fact.id, trimmed);
    setEditing(false);
  };

  const tag = fact.memory_type || fact.category || 'memory';
  const color = CHIP_COLOR[tag] || 'default';
  const created = fact.created_at || fact.provenance?.created_at;
  const relDate = created ? dayjs(created).fromNow() : '—';
  const rawContent = fact.content || '';
  const truncated = rawContent.length > 120 ? `${rawContent.slice(0, 120)}…` : rawContent;

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: 0.75,
        py: 0.75,
        px: 1,
        borderBottom: 1,
        borderColor: 'divider',
        '&:last-of-type': { borderBottom: 0 },
      }}
    >
      <Chip
        label={tag}
        size="small"
        color={color}
        variant="outlined"
        sx={{ fontSize: '0.625rem', height: 18, mt: 0.25, flexShrink: 0 }}
      />
      <Box sx={{ flex: 1, minWidth: 0 }}>
        {editing ? (
          <TextField
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            size="small"
            fullWidth
            multiline
            maxRows={4}
            variant="outlined"
            inputProps={{ 'aria-label': 'Edit memory content' }}
            sx={{ '& .MuiInputBase-input': { fontSize: '0.8125rem' } }}
          />
        ) : (
          <Typography
            variant="body2"
            sx={{ fontSize: '0.8125rem', wordBreak: 'break-word' }}
            title={rawContent}
          >
            {truncated}
          </Typography>
        )}
        <Typography variant="caption" color="text.disabled" sx={{ mt: 0.25, display: 'block' }}>
          {relDate}
        </Typography>
      </Box>
      {editing ? (
        <Stack direction="row" spacing={0.25} sx={{ flexShrink: 0 }}>
          <Tooltip title="Save">
            <IconButton size="small" onClick={handleSave} color="primary" aria-label="Save edit">
              <CheckIcon sx={{ fontSize: 14 }} />
            </IconButton>
          </Tooltip>
          <Tooltip title="Cancel">
            <IconButton size="small" onClick={handleCancel} aria-label="Cancel edit">
              <CloseIcon sx={{ fontSize: 14 }} />
            </IconButton>
          </Tooltip>
        </Stack>
      ) : (
        <Stack direction="row" spacing={0.25} sx={{ flexShrink: 0 }}>
          <Tooltip title="Edit">
            <IconButton size="small" onClick={handleEditStart} aria-label="Edit memory entry">
              <EditOutlinedIcon sx={{ fontSize: 14 }} />
            </IconButton>
          </Tooltip>
          <Tooltip title="Delete">
            <IconButton
              size="small"
              onClick={() => onDelete(fact)}
              aria-label="Delete memory entry"
              color="error"
            >
              <DeleteOutlineIcon sx={{ fontSize: 14 }} />
            </IconButton>
          </Tooltip>
        </Stack>
      )}
    </Box>
  );
}

// ── "Learned" sub-tab ────────────────────────────────────────────────────────

function LearnedTab() {
  const { token } = useAuth();
  const { notify, notifyFromError } = useNotification();
  const [facts, setFacts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [pendingDelete, setPendingDelete] = useState(null); // { id, fact }
  const undoTimerRef = useRef(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listFacts(token);
      setFacts(Array.isArray(data?.results) ? data.results : []);
    } catch (err) {
      notifyFromError(err, 'Could not load memory facts');
    } finally {
      setLoading(false);
    }
  }, [token, notifyFromError]);

  useEffect(() => { load(); }, [load]);

  // Clear undo timer on unmount
  useEffect(() => () => { if (undoTimerRef.current) clearTimeout(undoTimerRef.current); }, []);

  const handleEdit = useCallback(async (pk, content) => {
    const original = facts.find((f) => f.id === pk);
    setFacts((prev) => prev.map((f) => (f.id === pk ? { ...f, content } : f)));
    try {
      await updateMemoryFact(token, pk, content);
      notify({ message: 'Memory entry updated', type: 'success' });
    } catch (err) {
      if (original) setFacts((prev) => prev.map((f) => (f.id === pk ? original : f)));
      notifyFromError(err, 'Could not update memory entry');
    }
  }, [token, facts, notify, notifyFromError]);

  const handleDelete = useCallback(async (fact) => {
    setFacts((prev) => prev.filter((f) => f.id !== fact.id));
    if (undoTimerRef.current) clearTimeout(undoTimerRef.current);
    setPendingDelete({ id: fact.id, fact });
    try {
      await forgetFact(token, fact.id);
    } catch (err) {
      // Re-add if delete fails
      setFacts((prev) => [fact, ...prev]);
      setPendingDelete(null);
      notifyFromError(err, 'Could not delete memory entry');
      return;
    }
    // 30s undo window — closes snackbar when expired
    undoTimerRef.current = setTimeout(() => setPendingDelete(null), 30000);
  }, [token, notifyFromError]);

  const handleUndo = useCallback(async () => {
    if (!pendingDelete) return;
    const { id, fact } = pendingDelete;
    if (undoTimerRef.current) clearTimeout(undoTimerRef.current);
    setPendingDelete(null);
    setFacts((prev) => [fact, ...prev]);
    try {
      await restoreMemoryFact(token, id);
    } catch (err) {
      setFacts((prev) => prev.filter((f) => f.id !== id));
      notifyFromError(err, 'Could not undo delete');
    }
  }, [pendingDelete, token, notifyFromError]);

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <Box sx={{ flex: 1, overflowY: 'auto' }}>
        {loading && (
          <Typography variant="caption" color="text.secondary" sx={{ p: 1.5, display: 'block' }}>
            Loading…
          </Typography>
        )}
        {!loading && facts.length === 0 && (
          <Box sx={{ textAlign: 'center', py: 6 }}>
            <Typography variant="body2" color="text.secondary">
              No memory entries yet.
            </Typography>
          </Box>
        )}
        {!loading && facts.length > 0 && facts.map((fact) => (
          <FactRow key={fact.id} fact={fact} onEdit={handleEdit} onDelete={handleDelete} />
        ))}
      </Box>
      <Snackbar
        open={Boolean(pendingDelete)}
        message="Entry deleted · Undo"
        action={
          <Button size="small" color="inherit" onClick={handleUndo} aria-label="Undo delete">
            Undo
          </Button>
        }
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      />
    </Box>
  );
}

// ── "Org" sub-tab (admin only) ───────────────────────────────────────────────

function OrgTab() {
  const { token, isGlobalAdminFlag } = useAuth();
  const { notifyFromError } = useNotification();
  const [facts, setFacts] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!isGlobalAdminFlag) return;
    setLoading(true);
    listOrgMemory(token)
      .then((data) => setFacts(Array.isArray(data?.results) ? data.results : []))
      .catch((err) => notifyFromError(err, 'Could not load org memory'))
      .finally(() => setLoading(false));
  }, [token, isGlobalAdminFlag, notifyFromError]);

  if (!isGlobalAdminFlag) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography variant="body2" color="text.secondary">
          Admin access required.
        </Typography>
      </Box>
    );
  }

  if (loading) {
    return (
      <Typography variant="caption" color="text.secondary" sx={{ p: 1.5, display: 'block' }}>
        Loading…
      </Typography>
    );
  }

  return (
    <Box sx={{ p: 1, overflowY: 'auto', height: '100%' }}>
      {facts.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          No org-scoped memory entries.
        </Typography>
      ) : (
        <Stack spacing={0.5}>
          {facts.map((fact) => (
            <Box key={fact.id} sx={{ p: 1, border: 1, borderColor: 'divider', borderRadius: 1 }}>
              <Chip
                label={fact.memory_type || fact.category || 'memory'}
                size="small"
                variant="outlined"
                sx={{ fontSize: '0.625rem', height: 18, mb: 0.5 }}
              />
              <Typography variant="body2" sx={{ fontSize: '0.8125rem' }}>
                {fact.content}
              </Typography>
            </Box>
          ))}
        </Stack>
      )}
    </Box>
  );
}

// ── Main console component ───────────────────────────────────────────────────

function AIMemoryConsole({ conversationId }) {
  const [tab, setTab] = useState(() => {
    try { return localStorage.getItem(CONSOLE_TAB_KEY) || 'learned'; } catch { return 'learned'; }
  });

  useEffect(() => {
    try { localStorage.setItem(CONSOLE_TAB_KEY, tab); } catch { /* ignore */ }
  }, [tab]);

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <Box sx={{ px: 1, pt: 0.5, borderBottom: 1, borderColor: 'divider' }}>
        <Tabs
          value={tab}
          onChange={(_, v) => setTab(v)}
          variant="fullWidth"
          aria-label="Memory console tabs"
          sx={{
            minHeight: 34,
            '& .MuiTab-root': { minHeight: 34, fontSize: '0.6875rem', py: 0.5 },
          }}
        >
          <Tab value="learned" label="Learned" />
          <Tab value="episodes" label="Episodes" />
          <Tab value="session" label="Session" />
          <Tab value="org" label="Org" />
        </Tabs>
      </Box>
      <Box sx={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
        {tab === 'learned' && <LearnedTab conversationId={conversationId} />}
        {tab === 'episodes' && <AIMemoryTab />}
        {tab === 'session' && (
          <Box sx={{ p: 2 }}>
            <Typography variant="body2" color="text.secondary">
              Working memory is session-scoped and not persisted.
            </Typography>
          </Box>
        )}
        {tab === 'org' && <OrgTab />}
      </Box>
    </Box>
  );
}

AIMemoryConsole.propTypes = {
  conversationId: PropTypes.string,
};

export default AIMemoryConsole;
