// src/shell/AIContextMenu.jsx
// W2-C — header kebab for context lifecycle: clear / save checkpoint /
// restore / fork. All actions operate on the conversation's *working* context;
// the durable conversation, its message log, and learned facts are never
// deleted — the copy below makes that explicit (Notes for the Master).
import React, { useCallback, useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import DeleteSweepIcon from '@mui/icons-material/DeleteSweep';
import BookmarkAddIcon from '@mui/icons-material/BookmarkAdd';
import RestoreIcon from '@mui/icons-material/Restore';
import CallSplitIcon from '@mui/icons-material/CallSplit';
import { useAuth } from '../auth/AuthContext';
import { useNotification } from '../components/NotificationProvider';
import ConfirmDialog from '../components/ConfirmDialog';
import { formatDisplayDate } from '../utils/dateUtils';
import {
  checkpointConversation,
  clearContext,
  forkConversation,
  listCheckpoints,
  restoreConversation,
} from '../api/aiWorkspace';

function formatCheckpointDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return formatDisplayDate(d);
}

// ── Checkpoint picker (4-state: loading / error / empty / loaded) ─────────
// Used for both Restore and Fork — the parent decides what `onPick` does.
function CheckpointPickerDialog({ open, mode, conversationId, onClose, onPick }) {
  const { token } = useAuth();
  const [state, setState] = useState('idle'); // idle | loading | error | empty | loaded
  const [checkpoints, setCheckpoints] = useState([]);
  const [error, setError] = useState('');
  const [selectedId, setSelectedId] = useState(null);

  const load = useCallback(async () => {
    if (!open || !conversationId) return;
    setState('loading');
    setError('');
    try {
      const data = await listCheckpoints(token, conversationId);
      const items = Array.isArray(data?.checkpoints) ? data.checkpoints : [];
      setCheckpoints(items);
      setState(items.length ? 'loaded' : 'empty');
    } catch (err) {
      setError(err?.message || 'Could not load checkpoints');
      setState('error');
    }
  }, [open, conversationId, token]);

  useEffect(() => {
    if (open) {
      setSelectedId(null);
      load();
    }
  }, [open, load]);

  const selected = checkpoints.find((c) => c.id === selectedId) || null;
  const isFork = mode === 'fork';

  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle sx={{ fontSize: '0.9375rem' }}>
        {isFork ? 'Fork from here' : 'Restore working context'}
      </DialogTitle>
      <DialogContent sx={{ minHeight: 160 }}>
        {state === 'loading' && (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
            <CircularProgress size={22} />
          </Box>
        )}
        {state === 'error' && (
          <Stack spacing={1}>
            <Typography variant="body2" color="error.main">
              {error}
            </Typography>
            <Box>
              <Button size="small" variant="outlined" onClick={load}>
                Retry
              </Button>
            </Box>
          </Stack>
        )}
        {state === 'empty' && (
          <Typography variant="body2" color="text.secondary" sx={{ py: 1 }}>
            No checkpoints saved yet. Use “Save checkpoint” to snapshot the
            current working context first.
          </Typography>
        )}
        {state === 'loaded' && (
          <List dense disablePadding>
            {checkpoints.map((cp) => (
              <ListItemButton
                key={cp.id}
                selected={selectedId === cp.id}
                onClick={() => setSelectedId(cp.id)}
                sx={{
                  border: 1,
                  borderColor: selectedId === cp.id ? 'primary.main' : 'divider',
                  borderRadius: 1,
                  mb: 0.5,
                  px: 1,
                }}
              >
                <ListItemText
                  primary={<Typography variant="body2" sx={{ fontWeight: 600 }}>{cp.name}</Typography>}
                  secondary={
                    <Stack spacing={0.25} sx={{ mt: 0.25 }}>
                      {cp.note ? (
                        <Typography variant="caption" color="text.secondary">
                          {cp.note}
                        </Typography>
                      ) : null}
                      <Typography variant="caption" color="text.disabled">
                        {cp.snapshot?.message_count ?? 0} messages ·{' '}
                        {formatCheckpointDate(cp.created_at)}
                      </Typography>
                    </Stack>
                  }
                  secondaryTypographyProps={{ component: 'div' }}
                />
              </ListItemButton>
            ))}
          </List>
        )}
      </DialogContent>
      <DialogActions>
        <Button size="small" onClick={onClose}>
          Cancel
        </Button>
        <Button
          size="small"
          variant="contained"
          disabled={!selected}
          onClick={() => selected && onPick(selected)}
        >
          {isFork ? 'Fork' : 'Restore'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

CheckpointPickerDialog.propTypes = {
  open: PropTypes.bool.isRequired,
  mode: PropTypes.oneOf(['restore', 'fork']).isRequired,
  conversationId: PropTypes.string,
  onClose: PropTypes.func.isRequired,
  onPick: PropTypes.func.isRequired,
};

// ── Header kebab menu ─────────────────────────────────────────────────────
function AIContextMenu({ conversationId, onConversationUpdated, onForked }) {
  const { token } = useAuth();
  const { notify, notifyFromError } = useNotification();

  const [menuAnchor, setMenuAnchor] = useState(null);
  const [clearOpen, setClearOpen] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [saveOpen, setSaveOpen] = useState(false);
  const [checkpointName, setCheckpointName] = useState('');
  const [checkpointNote, setCheckpointNote] = useState('');
  const [saving, setSaving] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [pickerMode, setPickerMode] = useState('restore');
  const [forkTarget, setForkTarget] = useState(null);

  const closeMenu = () => setMenuAnchor(null);

  // Clear context — resets the *working* context only; durable chat is kept.
  const handleClearConfirm = useCallback(async () => {
    if (!conversationId || clearing) return;
    setClearing(true);
    try {
      const updated = await clearContext(token, conversationId);
      notify({ message: 'Working context cleared — chat history kept', type: 'success' });
      onConversationUpdated?.(updated);
      setClearOpen(false);
    } catch (err) {
      notifyFromError(err, 'Could not clear context');
    } finally {
      setClearing(false);
    }
  }, [conversationId, clearing, token, notify, notifyFromError, onConversationUpdated]);

  // Save checkpoint — name + note.
  const handleSaveCheckpoint = useCallback(async () => {
    const name = checkpointName.trim();
    if (!name || saving) return;
    setSaving(true);
    try {
      await checkpointConversation(token, conversationId, {
        name,
        note: checkpointNote.trim(),
      });
      notify({ message: `Checkpoint “${name}” saved`, type: 'success' });
      setSaveOpen(false);
      setCheckpointName('');
      setCheckpointNote('');
    } catch (err) {
      notifyFromError(err, 'Could not save checkpoint');
    } finally {
      setSaving(false);
    }
  }, [checkpointName, checkpointNote, saving, token, conversationId, notify, notifyFromError]);

  // Picker action: restore immediately; fork defers to a confirm dialog.
  const handlePick = useCallback(
    async (checkpoint) => {
      if (pickerMode === 'fork') {
        setForkTarget(checkpoint);
        setPickerOpen(false);
        return;
      }
      try {
        const updated = await restoreConversation(token, conversationId, checkpoint.id);
        notify({ message: 'Working context restored from checkpoint', type: 'success' });
        onConversationUpdated?.(updated);
        setPickerOpen(false);
      } catch (err) {
        notifyFromError(err, 'Could not restore checkpoint');
      }
    },
    [pickerMode, token, conversationId, notify, notifyFromError, onConversationUpdated],
  );

  // Fork confirm — creates a NEW chat; the current one is untouched.
  const handleForkConfirm = useCallback(async () => {
    if (!forkTarget || !conversationId) return;
    try {
      const forked = await forkConversation(token, conversationId, forkTarget.id);
      notify({ message: 'Forked a new chat from this point', type: 'success' });
      onForked?.(forked);
      setForkTarget(null);
    } catch (err) {
      notifyFromError(err, 'Could not fork conversation');
    }
  }, [forkTarget, conversationId, token, notify, notifyFromError, onForked]);

  return (
    <>
      <Tooltip title="Context actions">
        {/* span wrapper: Tooltips don't fire on disabled IconButton */}
        <span>
          <IconButton
            size="small"
            aria-label="Context actions"
            disabled={!conversationId}
            onClick={(e) => setMenuAnchor(e.currentTarget)}
          >
            <MoreVertIcon fontSize="small" />
          </IconButton>
        </span>
      </Tooltip>

      <Menu
        anchorEl={menuAnchor}
        open={Boolean(menuAnchor)}
        onClose={closeMenu}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        transformOrigin={{ vertical: 'top', horizontal: 'right' }}
      >
        <MenuItem
          sx={{ fontSize: '0.8125rem' }}
          onClick={() => {
            setClearOpen(true);
            closeMenu();
          }}
        >
          <ListItemIcon>
            <DeleteSweepIcon fontSize="small" />
          </ListItemIcon>
          Clear context
        </MenuItem>
        <MenuItem
          sx={{ fontSize: '0.8125rem' }}
          onClick={() => {
            setSaveOpen(true);
            closeMenu();
          }}
        >
          <ListItemIcon>
            <BookmarkAddIcon fontSize="small" />
          </ListItemIcon>
          Save checkpoint
        </MenuItem>
        <MenuItem
          sx={{ fontSize: '0.8125rem' }}
          onClick={() => {
            setPickerMode('restore');
            setPickerOpen(true);
            closeMenu();
          }}
        >
          <ListItemIcon>
            <RestoreIcon fontSize="small" />
          </ListItemIcon>
          Restore
        </MenuItem>
        <MenuItem
          sx={{ fontSize: '0.8125rem' }}
          onClick={() => {
            setPickerMode('fork');
            setPickerOpen(true);
            closeMenu();
          }}
        >
          <ListItemIcon>
            <CallSplitIcon fontSize="small" />
          </ListItemIcon>
          Fork from here
        </MenuItem>
      </Menu>

      {/* Clear context — destructive-ish; the durable conversation is kept. */}
      <ConfirmDialog
        open={clearOpen}
        title="Clear working context?"
        message="This clears the AI's working context (summary and memory snapshot) for this chat. Your conversation history and learned facts are kept — nothing is deleted."
        confirmLabel="Clear context"
        destructive
        onCancel={() => setClearOpen(false)}
        onConfirm={handleClearConfirm}
      />

      {/* Save checkpoint — name (required) + note (optional). */}
      <Dialog open={saveOpen} onClose={() => setSaveOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle sx={{ fontSize: '0.9375rem' }}>Save checkpoint</DialogTitle>
        <DialogContent>
          <Stack spacing={1.5} sx={{ pt: 0.5 }}>
            <TextField
              autoFocus
              size="small"
              label="Checkpoint name"
              value={checkpointName}
              onChange={(e) => setCheckpointName(e.target.value)}
              inputProps={{ 'aria-label': 'Checkpoint name' }}
              fullWidth
            />
            <TextField
              size="small"
              label="Note (optional)"
              value={checkpointNote}
              onChange={(e) => setCheckpointNote(e.target.value)}
              multiline
              minRows={2}
              inputProps={{ 'aria-label': 'Checkpoint note' }}
              fullWidth
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button size="small" onClick={() => setSaveOpen(false)} disabled={saving}>
            Cancel
          </Button>
          <Button
            size="small"
            variant="contained"
            disabled={saving || !checkpointName.trim()}
            onClick={handleSaveCheckpoint}
          >
            Save
          </Button>
        </DialogActions>
      </Dialog>

      {/* Checkpoint picker — shared by Restore and Fork-from-here. */}
      <CheckpointPickerDialog
        open={pickerOpen}
        mode={pickerMode}
        conversationId={conversationId}
        onClose={() => setPickerOpen(false)}
        onPick={handlePick}
      />

      {/* Fork confirm — a new chat is created; the current one stays as is. */}
      <ConfirmDialog
        open={Boolean(forkTarget)}
        title="Fork a new chat?"
        message={`A new chat will be created from the “${forkTarget?.name || 'selected'}” checkpoint. Your current chat stays exactly as it is — nothing is deleted.`}
        confirmLabel="Fork"
        destructive
        onCancel={() => setForkTarget(null)}
        onConfirm={handleForkConfirm}
      />
    </>
  );
}

AIContextMenu.propTypes = {
  conversationId: PropTypes.string,
  onConversationUpdated: PropTypes.func,
  onForked: PropTypes.func,
};

export default AIContextMenu;
