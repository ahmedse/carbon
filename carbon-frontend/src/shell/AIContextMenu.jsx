// src/shell/AIContextMenu.jsx
// W2-C — header kebab for context lifecycle: clear / save checkpoint /
// restore / fork. All actions operate on the conversation's *working* context;
// the durable conversation, its message log, and learned facts are never
// deleted — the copy below makes that explicit (Notes for the Master).
import React, { useCallback, useState } from 'react';
import PropTypes from 'prop-types';
import {
  IconButton,
  ListItemIcon,
  Menu,
  MenuItem,
  Tooltip,
} from '@mui/material';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import DeleteSweepIcon from '@mui/icons-material/DeleteSweep';
import BookmarkAddIcon from '@mui/icons-material/BookmarkAdd';
import RestoreIcon from '@mui/icons-material/Restore';
import CallSplitIcon from '@mui/icons-material/CallSplit';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../auth/AuthContext';
import { useNotification } from '../components/NotificationProvider';
import ConfirmDialog from '../components/ConfirmDialog';
import { CheckpointPickerDialog, SaveCheckpointDialog } from '../components/ai/CheckpointDialogs';
import {
  clearContext,
  forkConversation,
  restoreConversation,
} from '../api/aiWorkspace';

// ── Header kebab menu ─────────────────────────────────────────────────────
function AIContextMenu({ conversationId, onConversationUpdated, onForked }) {
  const { t } = useTranslation('ai');
  const { token } = useAuth();
  const { notify, notifyFromError } = useNotification();

  const [menuAnchor, setMenuAnchor] = useState(null);
  const [clearOpen, setClearOpen] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [saveOpen, setSaveOpen] = useState(false);
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
      notify({ message: t('contextCleared'), type: 'success' });
      onConversationUpdated?.(updated);
      setClearOpen(false);
    } catch (err) {
      notifyFromError(err, t('contextClearFailed'));
    } finally {
      setClearing(false);
    }
  }, [conversationId, clearing, token, notify, notifyFromError, onConversationUpdated, t]);

  // Save checkpoint — name + note (handled by SaveCheckpointDialog).

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
        notify({ message: t('contextRestored'), type: 'success' });
        onConversationUpdated?.(updated);
        setPickerOpen(false);
      } catch (err) {
        notifyFromError(err, t('contextRestoreFailed'));
      }
    },
    [pickerMode, token, conversationId, notify, notifyFromError, onConversationUpdated, t],
  );

  // Fork confirm — creates a NEW chat; the current one is untouched.
  const handleForkConfirm = useCallback(async () => {
    if (!forkTarget || !conversationId) return;
    try {
      const forked = await forkConversation(token, conversationId, forkTarget.id);
      notify({ message: t('forkedChat'), type: 'success' });
      onForked?.(forked);
      setForkTarget(null);
    } catch (err) {
      notifyFromError(err, t('forkFailed'));
    }
  }, [forkTarget, conversationId, token, notify, notifyFromError, onForked, t]);

  return (
    <>
      <Tooltip title={t('contextActions')}>
        {/* span wrapper: Tooltips don't fire on disabled IconButton */}
        <span>
          <IconButton
            size="small"
            aria-label={t('contextActions')}
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
          {t('clearContext')}
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
          {t('saveCheckpoint')}
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
          {t('restoreCheckpoint')}
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
          {t('forkFromHere')}
        </MenuItem>
      </Menu>

      {/* Clear context — destructive-ish; the durable conversation is kept. */}
      <ConfirmDialog
        open={clearOpen}
        title={t('clearWorkingContextTitle')}
        message={t('clearWorkingContextBody')}
        confirmLabel={t('clearContext')}
        destructive
        onCancel={() => setClearOpen(false)}
        onConfirm={handleClearConfirm}
      />

      {/* Save checkpoint — name (required) + note (optional). */}
      <SaveCheckpointDialog
        open={saveOpen}
        conversationId={conversationId}
        onClose={() => setSaveOpen(false)}
      />

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
        title={t('forkNewChatTitle')}
        message={t('forkNewChatBody', {
          name: forkTarget?.name || t('selectedCheckpoint'),
        })}
        confirmLabel={t('forkConfirm')}
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
