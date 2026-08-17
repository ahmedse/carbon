// src/shell/AIConversationTabs.jsx  (sessions list — replaces horizontal tabs)
import React, { useCallback, useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  Menu,
  MenuItem,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import { useAuth } from '../auth/AuthContext';

const STATUS_COLORS = {
  completed: 'success.main',
  needs_input: 'warning.main',
  working: 'primary.main',
  pending: 'grey.400',
  failed: 'error.main',
};

const TYPE_LABELS = {
  chat: 'Chat',
  dq_validate: 'DQ',
  dq_suggest: 'DQ',
  nl_query: 'NL',
  nl_rule_test: 'Rule',
  anomaly: 'Alert',
  investigate: 'Inv.',
  report_draft: 'Report',
};

function ageLabel(conv) {
  const raw = conv.updated_at || conv.created_at;
  if (!raw) return '';
  const diff = Date.now() - new Date(raw).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return 'now';
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h`;
  return `${Math.floor(h / 24)}d`;
}

function getGroup(conv) {
  const raw = conv.updated_at || conv.created_at;
  if (!raw) return 'Older';
  const diff = Date.now() - new Date(raw).getTime();
  const days = diff / 86400000;
  if (days < 1) return 'Today';
  if (days < 2) return 'Yesterday';
  if (days < 7) return 'Previous 7 days';
  return 'Older';
}

const GROUP_ORDER = ['Today', 'Yesterday', 'Previous 7 days', 'Older'];

function AIConversationTabs({
  conversations,
  activeId,
  onSelect,
  onNew,
  onClose: _onClose,
  onRename,
  onPin,
  onArchive,
  onDelete,
  compact = false,
}) {
  const { user } = useAuth();
  const [menuConvId, setMenuConvId] = useState(null);
  const [menuAnchor, setMenuAnchor] = useState(null);
  const [renameConvId, setRenameConvId] = useState(null);
  const [renameValue, setRenameValue] = useState('');

  const isOwned = useCallback(
    (c) => c.visibility !== 'shared' || String(c.user_id) === String(user?.id),
    [user],
  );

  const grouped = useMemo(() => {
    const map = {};
    for (const conv of conversations) {
      const g = getGroup(conv);
      if (!map[g]) map[g] = [];
      map[g].push(conv);
    }
    return map;
  }, [conversations]);

  const menuConv = useMemo(
    () => conversations.find((c) => c.id === menuConvId) || null,
    [conversations, menuConvId],
  );

  const closeMenu = useCallback(() => {
    setMenuAnchor(null);
    setMenuConvId(null);
  }, []);

  const openMenu = useCallback((e, conv) => {
    e.stopPropagation();
    setMenuAnchor(e.currentTarget);
    setMenuConvId(conv.id);
  }, []);

  const commitRename = useCallback(() => {
    if (renameConvId && renameValue.trim()) onRename?.(renameConvId, renameValue.trim());
    setRenameConvId(null);
    setRenameValue('');
  }, [renameConvId, renameValue, onRename]);

  const renderItem = useCallback((conv) => {
    const active = conv.id === activeId;
    const owned = isOwned(conv);
    const type = TYPE_LABELS[conv.conversation_type] || 'Chat';
    const title = conv.title || `${type} #${String(conv.id).slice(0, 6)}`;
    const age = ageLabel(conv);

    return (
      <Box
        key={conv.id}
        role="option"
        aria-selected={active}
        onClick={() => onSelect(conv.id)}
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 0.75,
          px: 1.25,
          height: 26,
          cursor: 'pointer',
          userSelect: 'none',
          borderLeft: 3,
          borderColor: active ? 'primary.main' : 'transparent',
          bgcolor: active ? 'action.selected' : 'transparent',
          '&:hover': { bgcolor: active ? 'action.selected' : 'action.hover' },
          '&:hover .sess-menu': { opacity: 1 },
          '.sess-menu': { opacity: 0, transition: 'opacity 0.1s' },
        }}
      >
        <Box sx={{ width: 5, height: 5, borderRadius: '50%', bgcolor: STATUS_COLORS[conv.status] || 'grey.400', flexShrink: 0 }} />
        <Typography variant="caption" noWrap sx={{ flex: 1, fontSize: '0.8rem', fontWeight: active ? 600 : 400 }}>
          {title}
        </Typography>
        <Typography variant="caption" sx={{ fontSize: '0.65rem', color: 'text.disabled', flexShrink: 0, minWidth: 24, textAlign: 'right' }}>
          {type}
        </Typography>
        <Typography variant="caption" sx={{ fontSize: '0.65rem', color: 'text.disabled', flexShrink: 0, minWidth: 18, textAlign: 'right' }}>
          {age}
        </Typography>
        {owned && (
          <IconButton
            size="small"
            className="sess-menu"
            onClick={(e) => openMenu(e, conv)}
            aria-label={`Session options for ${title}`}
            sx={{ p: 0.25, flexShrink: 0, ml: -0.5 }}
          >
            <MoreVertIcon sx={{ fontSize: 12 }} />
          </IconButton>
        )}
      </Box>
    );
  }, [activeId, isOwned, onSelect, openMenu]);

  return (
    <>
      {!compact && (
        <Box sx={{ display: 'flex', alignItems: 'center', px: 1.25, py: 0.375, borderBottom: 1, borderColor: 'divider' }}>
          <Typography variant="caption" sx={{ fontSize: '0.7rem', color: 'text.secondary', fontWeight: 600, flex: 1, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            Sessions
          </Typography>
          <Tooltip title="New chat">
            <IconButton size="small" onClick={onNew} aria-label="New chat" sx={{ p: 0.25 }}>
              <AddIcon sx={{ fontSize: 14 }} />
            </IconButton>
          </Tooltip>
        </Box>
      )}

      <Box role="listbox" aria-label="Conversation sessions" sx={{ overflowY: 'auto', maxHeight: 160, borderBottom: 1, borderColor: 'divider' }}>
        {conversations.length === 0 ? (
          <Typography variant="caption" color="text.disabled" sx={{ display: 'block', px: 1.5, py: 1, fontSize: '0.75rem' }}>
            No sessions yet
          </Typography>
        ) : (
          GROUP_ORDER.filter((g) => grouped[g]?.length).map((group) => (
            <Box key={group}>
              <Typography variant="caption" sx={{ display: 'block', px: 1.25, py: 0.25, fontSize: '0.65rem', color: 'text.disabled', textTransform: 'uppercase', letterSpacing: '0.05em', bgcolor: 'background.default' }}>
                {group}
              </Typography>
              {grouped[group].map(renderItem)}
            </Box>
          ))
        )}
      </Box>

      <Menu anchorEl={menuAnchor} open={Boolean(menuAnchor)} onClose={closeMenu}>
        {menuConv && isOwned(menuConv) && [
          <MenuItem key="pin" onClick={() => { onPin?.(menuConv.id); closeMenu(); }} sx={{ fontSize: '0.8125rem' }}>
            {menuConv.is_pinned ? 'Unpin' : 'Pin'}
          </MenuItem>,
          <MenuItem key="rename" onClick={() => { setRenameConvId(menuConv.id); setRenameValue(menuConv.title || ''); closeMenu(); }} sx={{ fontSize: '0.8125rem' }}>
            Rename
          </MenuItem>,
          <MenuItem key="archive" onClick={() => { onArchive?.(menuConv.id); closeMenu(); }} sx={{ fontSize: '0.8125rem' }}>
            {menuConv.is_archived ? 'Restore' : 'Archive'}
          </MenuItem>,
        ]}
        <MenuItem onClick={() => { onDelete?.(menuConv?.id); closeMenu(); }} disabled={!!menuConv && !isOwned(menuConv)} sx={{ fontSize: '0.8125rem', color: 'error.main' }}>
          Delete
        </MenuItem>
      </Menu>

      <Dialog open={Boolean(renameConvId)} onClose={() => setRenameConvId(null)} maxWidth="xs" fullWidth>
        <DialogTitle sx={{ fontSize: '0.9375rem' }}>Rename session</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus fullWidth size="small"
            value={renameValue}
            onChange={(e) => setRenameValue(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') commitRename(); else if (e.key === 'Escape') setRenameConvId(null); }}
            inputProps={{ 'aria-label': 'Session title' }}
          />
        </DialogContent>
        <DialogActions>
          <Button size="small" onClick={() => setRenameConvId(null)}>Cancel</Button>
          <Button size="small" variant="contained" onClick={commitRename} disabled={!renameValue.trim()}>Save</Button>
        </DialogActions>
      </Dialog>
    </>
  );
}

AIConversationTabs.propTypes = {
  conversations: PropTypes.array.isRequired,
  activeId: PropTypes.string,
  onSelect: PropTypes.func.isRequired,
  onNew: PropTypes.func.isRequired,
  onClose: PropTypes.func.isRequired,
  onRename: PropTypes.func,
  onPin: PropTypes.func,
  onArchive: PropTypes.func,
  onDelete: PropTypes.func,
};

export default AIConversationTabs;
