// src/shell/CheckpointPicker.jsx
// G3 — Checkpoint picker drawer: lists snapshots with per-row Restore + Fork.
// RULE_8: theme tokens only — no raw hex. RULE_10: apiFetch via aiWorkspace.js.
import React, { useCallback, useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Drawer,
  IconButton,
  Stack,
  Tooltip,
  Typography,
} from '@mui/material';
import CallSplitOutlinedIcon from '@mui/icons-material/CallSplitOutlined';
import RestoreOutlinedIcon from '@mui/icons-material/RestoreOutlined';
import dayjs from 'dayjs';
import { useAuth } from '../auth/AuthContext';
import { useNotification } from '../components/NotificationProvider';
import {
  listCheckpoints,
  restoreConversation,
  forkConversation,
} from '../api/aiWorkspace';

function formatDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return dayjs(iso).format('MMM D · HH:mm');
}

function CheckpointPicker({ conversationId, open, onClose, onFork }) {
  const { token } = useAuth();
  const { notify, notifyFromError } = useNotification();
  const [checkpoints, setCheckpoints] = useState([]);
  const [loading, setLoading] = useState(false);
  const [restoreTarget, setRestoreTarget] = useState(null); // { id, name }
  const [restoring, setRestoring] = useState(false);

  const load = useCallback(async () => {
    if (!conversationId || !open) return;
    setLoading(true);
    try {
      const data = await listCheckpoints(token, conversationId);
      setCheckpoints(Array.isArray(data?.checkpoints) ? data.checkpoints : []);
    } catch (err) {
      notifyFromError(err, 'Could not load checkpoints');
    } finally {
      setLoading(false);
    }
  }, [token, conversationId, open, notifyFromError]);

  useEffect(() => {
    if (open) {
      setCheckpoints([]);
      load();
    }
  }, [open, load]);

  const handleRestoreConfirm = useCallback(async () => {
    if (!restoreTarget || !conversationId || restoring) return;
    setRestoring(true);
    try {
      await restoreConversation(token, conversationId, restoreTarget.id);
      notify({ message: 'Context restored', type: 'success' });
      setRestoreTarget(null);
      onClose?.();
    } catch (err) {
      notifyFromError(err, 'Could not restore checkpoint');
    } finally {
      setRestoring(false);
    }
  }, [restoreTarget, conversationId, restoring, token, notify, notifyFromError, onClose]);

  const handleFork = useCallback(async (checkpoint) => {
    if (!conversationId) return;
    try {
      const forked = await forkConversation(token, conversationId, checkpoint.id);
      notify({ message: 'Forked a new conversation', type: 'success' });
      onFork?.(forked);
      onClose?.();
    } catch (err) {
      notifyFromError(err, 'Could not fork conversation');
    }
  }, [conversationId, token, notify, notifyFromError, onFork, onClose]);

  // Newest first
  const sorted = [...checkpoints].reverse();

  return (
    <>
      <Drawer anchor="right" open={open} onClose={onClose} PaperProps={{ sx: { width: 320 } }}>
        <Box sx={{ p: 1.5, borderBottom: 1, borderColor: 'divider' }}>
          <Typography variant="subtitle2" fontWeight={600}>
            Checkpoints
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Restore or fork from a saved snapshot
          </Typography>
        </Box>
        <Box sx={{ flex: 1, overflowY: 'auto' }}>
          {loading && (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
              <CircularProgress size={22} />
            </Box>
          )}
          {!loading && sorted.length === 0 && (
            <Box sx={{ textAlign: 'center', py: 6 }}>
              <Typography variant="body2" color="text.secondary">
                No checkpoints yet.
              </Typography>
            </Box>
          )}
          {!loading && sorted.length > 0 && (
            <Stack spacing={0}>
              {sorted.map((cp) => (
                <Box
                  key={cp.id}
                  sx={{
                    px: 1.5,
                    py: 1,
                    borderBottom: 1,
                    borderColor: 'divider',
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: 1,
                  }}
                >
                  <Box sx={{ flex: 1, minWidth: 0 }}>
                    <Typography variant="body2" fontWeight={600} noWrap>
                      {cp.name}
                    </Typography>
                    {cp.note && (
                      <Typography variant="caption" color="text.secondary" noWrap>
                        {cp.note}
                      </Typography>
                    )}
                    <Typography variant="caption" color="text.disabled" sx={{ display: 'block' }}>
                      {formatDate(cp.created_at)}
                    </Typography>
                  </Box>
                  <Stack direction="row" spacing={0.25} sx={{ flexShrink: 0 }}>
                    <Tooltip title="Restore context">
                      <IconButton
                        size="small"
                        onClick={() => setRestoreTarget({ id: cp.id, name: cp.name })}
                        aria-label={`Restore checkpoint ${cp.name}`}
                      >
                        <RestoreOutlinedIcon sx={{ fontSize: 14 }} />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Fork from here">
                      <IconButton
                        size="small"
                        onClick={() => handleFork(cp)}
                        aria-label={`Fork from checkpoint ${cp.name}`}
                      >
                        <CallSplitOutlinedIcon sx={{ fontSize: 14 }} />
                      </IconButton>
                    </Tooltip>
                  </Stack>
                </Box>
              ))}
            </Stack>
          )}
        </Box>
      </Drawer>

      <Dialog
        open={Boolean(restoreTarget)}
        onClose={() => !restoring && setRestoreTarget(null)}
        maxWidth="xs"
      >
        <DialogTitle sx={{ fontSize: '0.9375rem' }}>Restore checkpoint?</DialogTitle>
        <DialogContent>
          <DialogContentText sx={{ fontSize: '0.875rem' }}>
            Restoring will replace your current context with the saved state. Continue?
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button
            size="small"
            onClick={() => setRestoreTarget(null)}
            disabled={restoring}
          >
            Cancel
          </Button>
          <Button
            size="small"
            variant="contained"
            onClick={handleRestoreConfirm}
            disabled={restoring}
          >
            Restore
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}

CheckpointPicker.propTypes = {
  conversationId: PropTypes.string,
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  onFork: PropTypes.func,
};

export default CheckpointPicker;
