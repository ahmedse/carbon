// src/components/ai/CheckpointDialogs.jsx
// Reusable checkpoint dialogs (W2-C). Extracted from AIContextMenu so the
// Pulse composer slash commands (`/checkpoint`, `/fork`) can reuse the exact
// same surfaces without duplicating state or API wiring.
//
//   CheckpointPickerDialog — 4-state list (loading/error/empty/loaded) used by
//                            Restore and Fork; the parent decides what onPick does.
//   SaveCheckpointDialog    — name (required) + note (optional); saves the snapshot.
//
// RULE_8: theme tokens only. Compact density per .ai-toolkit/shared/compact-ui.md.
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
  List,
  ListItemButton,
  ListItemText,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../NotificationProvider';
import { formatDisplayDate } from '../../utils/dateUtils';
import {
  checkpointConversation,
  listCheckpoints,
} from '../../api/aiWorkspace';

function formatCheckpointDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return formatDisplayDate(d);
}

// ── Checkpoint picker (4-state: loading / error / empty / loaded) ─────────
export function CheckpointPickerDialog({ open, mode, conversationId, onClose, onPick }) {
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

// ── Save checkpoint — name (required) + note (optional) ────────────────────
export function SaveCheckpointDialog({ open, conversationId, onClose, onSaved }) {
  const { token } = useAuth();
  const { notify, notifyFromError } = useNotification();
  const [name, setName] = useState('');
  const [note, setNote] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) {
      setName('');
      setNote('');
    }
  }, [open]);

  const handleSave = useCallback(async () => {
    const trimmed = name.trim();
    if (!trimmed || saving) return;
    setSaving(true);
    try {
      await checkpointConversation(token, conversationId, {
        name: trimmed,
        note: note.trim(),
      });
      notify({ message: `Checkpoint “${trimmed}” saved`, type: 'success' });
      onSaved?.(trimmed);
      onClose();
    } catch (err) {
      notifyFromError(err, 'Could not save checkpoint');
    } finally {
      setSaving(false);
    }
  }, [name, note, saving, token, conversationId, notify, notifyFromError, onSaved, onClose]);

  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle sx={{ fontSize: '0.9375rem' }}>Save checkpoint</DialogTitle>
      <DialogContent>
        <Stack spacing={1.5} sx={{ pt: 0.5 }}>
          <TextField
            autoFocus
            size="small"
            label="Checkpoint name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            inputProps={{ 'aria-label': 'Checkpoint name' }}
            fullWidth
          />
          <TextField
            size="small"
            label="Note (optional)"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            multiline
            minRows={2}
            inputProps={{ 'aria-label': 'Checkpoint note' }}
            fullWidth
          />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button size="small" onClick={onClose} disabled={saving}>
          Cancel
        </Button>
        <Button
          size="small"
          variant="contained"
          disabled={saving || !name.trim()}
          onClick={handleSave}
        >
          Save
        </Button>
      </DialogActions>
    </Dialog>
  );
}

SaveCheckpointDialog.propTypes = {
  open: PropTypes.bool.isRequired,
  conversationId: PropTypes.string,
  onClose: PropTypes.func.isRequired,
  onSaved: PropTypes.func,
};
