// src/shell/AIInputBar.jsx
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  IconButton,
  List,
  ListItemButton,
  MenuItem,
  Paper,
  Select,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import SendIcon from '@mui/icons-material/Send';

const PLACEHOLDER_MAP = {
  working: 'AI is thinking… (Enter to queue)',
  needs_input: 'Respond to AI\'s question…',
  default: 'Ask a question or give directions…',
};

const SEND_MODE_OPTIONS = [
  { value: 'queue', label: 'Send on done' },
  { value: 'steer', label: 'Interrupt & send' },
  { value: 'stop', label: 'Stop' },
];

// Sprint 17: fixed mention kinds the WorkspaceContext understands. Selecting a
// kind inserts "#table " / "#rule " etc. TODO(mentions): resolve these kinds to
// concrete entity ids from the source workspace (table pk / rule id / field name /
// module slug) and send the resolved entities in workspace_context — this sprint
// only surfaces the kind list (no remote entity search).
const MENTION_KINDS = ['table', 'rule', 'field', 'module'];

// Matches a trailing "#" + partial word at the very end of the input.
const MENTION_TRIGGER_RE = /(^|[\s\n])#([a-zA-Z]*)$/;

function extractMentions(text) {
  const matches = (text || '').match(/#(table|rule|field|module)\b/g) || [];
  return Array.from(new Set(matches));
}

function AIInputBar({
  onSend,
  working,
  sendMode,
  onModeChange,
  onStop,
  conversationStatus,
  onMentionsChange,
}) {
  const inputRef = useRef(null);
  const [value, setValue] = useState('');
  const [mentionQuery, setMentionQuery] = useState('');
  const [mentionOpen, setMentionOpen] = useState(false);

  const mentions = useMemo(() => extractMentions(value), [value]);
  const visibleKinds = useMemo(
    () => MENTION_KINDS.filter((kind) => kind.startsWith(mentionQuery)),
    [mentionQuery],
  );

  useEffect(() => {
    onMentionsChange?.(mentions);
  }, [mentions, onMentionsChange]);

  const handleChange = useCallback((event) => {
    const next = event.target.value;
    setValue(next);
    const match = MENTION_TRIGGER_RE.exec(next);
    if (match) {
      setMentionQuery(match[2]);
      setMentionOpen(true);
    } else {
      setMentionQuery('');
      setMentionOpen(false);
    }
  }, []);

  const handleSelectKind = useCallback((kind) => {
    setValue((prev) => prev.replace(MENTION_TRIGGER_RE, `$1#${kind} `));
    setMentionQuery('');
    setMentionOpen(false);
    inputRef.current?.focus();
  }, []);

  const handleSubmit = useCallback(() => {
    const val = value.trim();
    if (!val) return;
    if (working && sendMode === 'stop') {
      onStop?.();
      return;
    }
    onSend(val, extractMentions(value));
    setValue('');
  }, [value, working, sendMode, onSend, onStop]);

  const handleKeyDown = useCallback(
    (event) => {
      if (event.key === 'Escape' && mentionOpen) {
        event.preventDefault();
        setMentionOpen(false);
        setMentionQuery('');
        return;
      }
      if (event.key === 'Enter' && !event.shiftKey && !mentionOpen) {
        event.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit, mentionOpen],
  );

  const placeholder = working
    ? PLACEHOLDER_MAP.working
    : conversationStatus === 'needs_input'
      ? PLACEHOLDER_MAP.needs_input
      : PLACEHOLDER_MAP.default;

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'flex-end',
        gap: 0.5,
        px: 1.5,
        py: 1,
        borderTop: 1,
        borderColor: 'divider',
        bgcolor: 'background.paper',
      }}
    >
      <Box sx={{ position: 'relative', flex: 1, minWidth: 0 }}>
        <TextField
          inputRef={inputRef}
          fullWidth
          multiline
          minRows={1}
          maxRows={4}
          size="small"
          value={value}
          onChange={handleChange}
          placeholder={placeholder}
          onKeyDown={handleKeyDown}
          sx={{
            '& .MuiOutlinedInput-root': {
              fontSize: '0.8125rem',
              bgcolor: 'action.hover',
            },
          }}
          inputProps={{ 'aria-label': 'Message input' }}
        />
        {mentionOpen && visibleKinds.length > 0 && (
          <Paper
            elevation={2}
            role="listbox"
            aria-label="Mention kinds"
            sx={{
              position: 'absolute',
              bottom: '100%',
              left: 0,
              mb: 0.5,
              zIndex: 10,
              minWidth: 180,
              maxHeight: 200,
              overflowY: 'auto',
            }}
          >
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ display: 'block', px: 1.5, py: 0.5 }}
            >
              Mention an entity kind
            </Typography>
            <List dense disablePadding>
              {visibleKinds.map((kind) => (
                <ListItemButton
                  key={kind}
                  role="option"
                  onClick={() => handleSelectKind(kind)}
                  sx={{ fontSize: '0.8125rem' }}
                >
                  #{kind}
                </ListItemButton>
              ))}
            </List>
          </Paper>
        )}
      </Box>
      {working && (
        <Select
          size="small"
          value={sendMode}
          onChange={(e) => onModeChange?.(e.target.value)}
          inputProps={{ 'aria-label': 'Send mode' }}
          sx={{ fontSize: '0.75rem' }}
        >
          {SEND_MODE_OPTIONS.map((opt) => (
            <MenuItem key={opt.value} value={opt.value} sx={{ fontSize: '0.75rem' }}>
              {opt.label}
            </MenuItem>
          ))}
        </Select>
      )}
      <Tooltip title="Send message (Enter)">
        <span>
          <IconButton
            size="small"
            color="primary"
            onClick={handleSubmit}
            aria-label="Send message"
          >
            <SendIcon fontSize="small" />
          </IconButton>
        </span>
      </Tooltip>
    </Box>
  );
}

AIInputBar.propTypes = {
  onSend: PropTypes.func.isRequired,
  working: PropTypes.bool,
  sendMode: PropTypes.oneOf(['queue', 'steer', 'stop']),
  onModeChange: PropTypes.func,
  onStop: PropTypes.func,
  conversationStatus: PropTypes.string,
  onMentionsChange: PropTypes.func,
};

export default AIInputBar;
