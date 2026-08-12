// src/shell/AIConversationTabs.jsx
import React, { useCallback, useMemo } from 'react';
import PropTypes from 'prop-types';
import { Box, IconButton, Tab, Tabs, Tooltip, Typography } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import CloseIcon from '@mui/icons-material/Close';

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
};

function AIConversationTabs({
  conversations,
  activeId,
  onSelect,
  onNew,
  onClose,
}) {
  const activeIdx = useMemo(() => {
    const idx = conversations.findIndex((c) => c.id === activeId);
    return idx >= 0 ? idx : false;
  }, [conversations, activeId]);

  const label = useCallback(
    (conv) => {
      const title =
        conv.title ||
        `${CONVERSATION_TYPE_LABELS[conv.conversation_type] || 'Chat'} #${conv.id?.slice(0, 6)}`;
      const truncated = title.length > 20 ? title.slice(0, 18) + '…' : title;
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
            sx={{ maxWidth: 120, fontSize: '0.75rem' }}
          >
            {truncated}
          </Typography>
        </Box>
      );
    },
    [],
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
      <Tabs
        value={activeIdx}
        onChange={(_, idx) => {
          const conv = conversations[idx];
          if (conv) onSelect(conv.id);
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
        {conversations.map((conv) => (
          <Tab
            key={conv.id}
            label={label(conv)}
            value={conversations.indexOf(conv)}
            iconPosition="end"
            icon={
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
            }
          />
        ))}
      </Tabs>
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
    </Box>
  );
}

AIConversationTabs.propTypes = {
  conversations: PropTypes.array.isRequired,
  activeId: PropTypes.string,
  onSelect: PropTypes.func.isRequired,
  onNew: PropTypes.func.isRequired,
  onClose: PropTypes.func.isRequired,
};

export default AIConversationTabs;
