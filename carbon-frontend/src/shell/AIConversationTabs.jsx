// src/shell/AIConversationTabs.jsx
import React, { useCallback, useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  IconButton,
  Menu,
  MenuItem,
  Tab,
  Tabs,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import CloseIcon from '@mui/icons-material/Close';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import { useAuth } from '../auth/AuthContext';

const STATUS_DOT_COLORS = {
  completed: 'success.main',
  needs_input: 'warning.main',
  working: 'primary.main',
  pending: 'grey.400',
  failed: 'error.main',
};

const CONVERSATION_TYPE_LABELS = {
  chat: 'Chat',
  dq_validate: 'DQ Check',
  dq_suggest: 'DQ Suggest',
  nl_query: 'NL Query',
  anomaly: 'Anomaly',
  investigate: 'Investigate',
  report_draft: 'Report',
};

function AIConversationTabs({
  conversations,
  activeId,
  onSelect,
  onNew,
  onClose,
  onRename,
  onPin,
  onArchive,
  onDelete,
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

  const owned = useMemo(() => conversations.filter(isOwned), [conversations, isOwned]);
  const shared = useMemo(() => conversations.filter((c) => !isOwned(c)), [conversations, isOwned]);

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

  const openRename = useCallback((conv) => {
    setRenameConvId(conv.id);
    setRenameValue(conv.title || '');
    closeMenu();
  }, [closeMenu]);

  const commitRename = useCallback(() => {
    if (renameConvId && renameValue.trim()) {
      onRename?.(renameConvId, renameValue.trim());
    }
    setRenameConvId(null);
    setRenameValue('');
  }, [renameConvId, renameValue, onRename]);

  const label = useCallback(
    (conv) => {
      const typeLabel = CONVERSATION_TYPE_LABELS[conv.conversation_type] || 'Chat';
      const title = conv.title || `${typeLabel} #${conv.id?.slice(0, 6)}`;
      const truncated = title.length > 20 ? title.slice(0, 18) + '…' : title;
      const isShared = !isOwned(conv);
      return (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
          <Box
            sx={{
              width: 6,
              height: 6,
              borderRadius: '50%',
              bgcolor: STATUS_DOT_COLORS[conv.status] || 'grey.400',
              flexShrink: 0,
            }}
          />
          <Typography
            variant="caption"
            noWrap
            sx={{ maxWidth: 110, fontSize: '0.75rem' }}
          >
            {truncated}
          </Typography>
          {isShared && <Chip size="small" label="Shared" />}
          <IconButton
            size="small"
            component="span"
            onClick={(e) => openMenu(e, conv)}
            sx={{ p: 0.25, ml: 0.25 }}
            aria-label={`Conversation actions for ${title}`}
          >
            <MoreVertIcon sx={{ fontSize: 12 }} />
          </IconButton>
        </Box>
      );
    },
    [openMenu, isOwned],
  );

  if (!conversations.length) {
    return (
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          px: 1,
          minHeight: 36,
          borderBottom: 1,
          borderColor: 'divider',
        }}
      >
        <Tooltip title="New chat">
          <IconButton size="small" onClick={onNew} aria-label="New chat">
            <AddIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </Box>
    );
  }

  const renderTab = (conv) => {
    const ownedTab = isOwned(conv);
    return (
      <Tab
        key={conv.id}
        label={label(conv)}
        value={conv.id}
        iconPosition="end"
        icon={
          ownedTab ? (
            <IconButton
              size="small"
              component="span"
              onClick={(e) => {
                e.stopPropagation();
                onClose(conv.id);
              }}
              sx={{ ml: 0.25, p: 0.25 }}
              aria-label={`Close conversation ${conv.title || conv.id}`}
            >
              <CloseIcon sx={{ fontSize: 12 }} />
            </IconButton>
          ) : null
        }
      />
    );
  };

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        borderBottom: 1,
        borderColor: 'divider',
        minHeight: 36,
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', flex: 1, minWidth: 0 }}>
        <Tabs
          value={activeId}
          onChange={(_, id) => {
            if (id) onSelect(id);
          }}
          variant="scrollable"
          scrollButtons="auto"
          sx={{
            minHeight: 36,
            flex: 1,
            '& .MuiTab-root': {
              minHeight: 36,
              py: 0,
              px: 1.25,
              fontSize: '0.75rem',
              textTransform: 'none',
            },
          }}
        >
          {owned.map(renderTab)}
        </Tabs>
        {owned.length > 0 && shared.length > 0 && (
          <Divider orientation="vertical" flexItem sx={{ mx: 0.5 }} />
        )}
        {shared.length > 0 && (
          <Tabs
            value={activeId}
            onChange={(_, id) => {
              if (id) onSelect(id);
            }}
            variant="scrollable"
            scrollButtons="auto"
            sx={{
              minHeight: 36,
              flex: 1,
              '& .MuiTab-root': {
                minHeight: 36,
                py: 0,
                px: 1.25,
                fontSize: '0.75rem',
                textTransform: 'none',
              },
            }}
          >
            {shared.map(renderTab)}
          </Tabs>
        )}
      </Box>
      <Tooltip title="New chat">
        <IconButton
          size="small"
          onClick={onNew}
          sx={{ mr: 0.5, flexShrink: 0 }}
          aria-label="New chat"
        >
          <AddIcon fontSize="small" />
        </IconButton>
      </Tooltip>

      {/* Per-tab context menu */}
      <Menu anchorEl={menuAnchor} open={Boolean(menuAnchor)} onClose={closeMenu}>
        {menuConv && isOwned(menuConv) && (
          <MenuItem
            onClick={() => {
              if (menuConv) onPin?.(menuConv.id);
              closeMenu();
            }}
          >
            {menuConv?.is_pinned ? 'Unpin' : 'Pin'}
          </MenuItem>
        )}
        {menuConv && isOwned(menuConv) && (
          <MenuItem
            onClick={() => {
              if (menuConv) openRename(menuConv);
            }}
          >
            Rename
          </MenuItem>
        )}
        {menuConv && isOwned(menuConv) && (
          <MenuItem
            onClick={() => {
              if (menuConv) onArchive?.(menuConv.id);
              closeMenu();
            }}
          >
            {menuConv?.is_archived ? 'Restore' : 'Archive'}
          </MenuItem>
        )}
        <MenuItem
          onClick={() => {
            if (menuConv) onDelete?.(menuConv.id);
            closeMenu();
          }}
          disabled={!!menuConv && !isOwned(menuConv)}
        >
          Delete
        </MenuItem>
      </Menu>

      {/* Rename dialog */}
      <Dialog open={Boolean(renameConvId)} onClose={() => setRenameConvId(null)} maxWidth="xs" fullWidth>
        <DialogTitle>Rename conversation</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            fullWidth
            size="small"
            value={renameValue}
            onChange={(e) => setRenameValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') commitRename();
              else if (e.key === 'Escape') setRenameConvId(null);
            }}
            inputProps={{ 'aria-label': 'Conversation title' }}
          />
        </DialogContent>
        <DialogActions>
          <Button size="small" onClick={() => setRenameConvId(null)}>
            Cancel
          </Button>
          <Button size="small" variant="contained" onClick={commitRename} disabled={!renameValue.trim()}>
            Save
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
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
