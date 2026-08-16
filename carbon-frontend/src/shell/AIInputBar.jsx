// src/shell/AIInputBar.jsx
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  CircularProgress,
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
import { useAuth } from '../auth/AuthContext';
import { apiFetch } from '../api/api';
import { API_ROUTES } from '../config';

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

const MENTION_KINDS = ['table', 'rule', 'field', 'module'];

// Two-stage mention: first '#' shows kinds; after kind + space typed, search entities.
// Stage 1: /(^|\s)#([a-zA-Z]*)$/ — kind picker
// Stage 2: /(^|\s)#(table|rule|field|module) ([^#]*)$/ — entity search within a kind
const KIND_TRIGGER_RE = /(^|[\s\n])#([a-zA-Z]*)$/;
const ENTITY_TRIGGER_RE = /(^|[\s\n])#(table|rule|field|module) ([^#\n]*)$/;

// Map kind → API route + label/value keys
const KIND_CONFIG = {
  table:  { route: API_ROUTES.tables,  labelKey: 'title',    idKey: 'id',  extra: ['name'] },
  field:  { route: API_ROUTES.fields,  labelKey: 'label',    idKey: 'id',  extra: ['name'] },
  rule:   { route: API_ROUTES.dqRules, labelKey: 'name',     idKey: 'id',  extra: [] },
  module: { route: API_ROUTES.modules, labelKey: 'name',     idKey: 'id',  extra: [] },
};

function entityLabel(kind, item) {
  const cfg = KIND_CONFIG[kind];
  if (!cfg) return String(item.id);
  return item[cfg.labelKey] || item[cfg.extra?.[0]] || String(item.id);
}

// Build the canonical mention object that rides in workspace_context.mentions
function buildMention(kind, item) {
  return { kind, id: String(item.id), name: entityLabel(kind, item) };
}

// Replace the trailing #kind word+ with the display token.
function replaceEntityTrigger(text, kind, displayName) {
  return text.replace(ENTITY_TRIGGER_RE, `$1@${displayName} `);
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
  const { token } = useAuth();
  const inputRef = useRef(null);
  const [value, setValue] = useState('');
  // Stage: null | 'kind' | 'entity'
  const [stage, setStage] = useState(null);
  const [kindQuery, setKindQuery] = useState('');
  const [activeKind, setActiveKind] = useState(null);
  const [entityQuery, setEntityQuery] = useState('');
  const [entities, setEntities] = useState([]);
  const [entityLoading, setEntityLoading] = useState(false);
  // Resolved mention objects: { kind, id, name }
  const [resolvedMentions, setResolvedMentions] = useState([]);

  const visibleKinds = useMemo(
    () => MENTION_KINDS.filter((k) => k.startsWith(kindQuery)),
    [kindQuery],
  );

  // Notify parent of mention changes.
  useEffect(() => {
    onMentionsChange?.(resolvedMentions);
  }, [resolvedMentions, onMentionsChange]);

  // Fetch entities when the entity query changes (debounced via useEffect cleanup).
  useEffect(() => {
    if (stage !== 'entity' || !activeKind) return;
    const cfg = KIND_CONFIG[activeKind];
    if (!cfg) return;
    let cancelled = false;
    setEntityLoading(true);
    const url = entityQuery.trim()
      ? `${cfg.route}?q=${encodeURIComponent(entityQuery.trim())}&limit=8`
      : `${cfg.route}?limit=8`;
    apiFetch(url, { token })
      .then((data) => {
        if (cancelled) return;
        const list = Array.isArray(data) ? data : (data?.results ?? []);
        setEntities(list.slice(0, 8));
      })
      .catch(() => { if (!cancelled) setEntities([]); })
      .finally(() => { if (!cancelled) setEntityLoading(false); });
    return () => { cancelled = true; };
  }, [stage, activeKind, entityQuery, token]);

  const closePicker = useCallback(() => {
    setStage(null);
    setKindQuery('');
    setActiveKind(null);
    setEntityQuery('');
    setEntities([]);
  }, []);

  const handleChange = useCallback((event) => {
    const next = event.target.value;
    setValue(next);

    // Check entity stage first (more specific match).
    const entityMatch = ENTITY_TRIGGER_RE.exec(next);
    if (entityMatch) {
      const kind = entityMatch[2];
      const query = entityMatch[3];
      setStage('entity');
      setActiveKind(kind);
      setEntityQuery(query);
      return;
    }

    const kindMatch = KIND_TRIGGER_RE.exec(next);
    if (kindMatch) {
      setStage('kind');
      setKindQuery(kindMatch[2]);
      setActiveKind(null);
      setEntityQuery('');
      setEntities([]);
      return;
    }

    closePicker();
  }, [closePicker]);

  const handleSelectKind = useCallback((kind) => {
    // Replace trailing #partial with #kind (keep the space so entity search starts).
    setValue((prev) => prev.replace(KIND_TRIGGER_RE, `$1#${kind} `));
    setStage('entity');
    setActiveKind(kind);
    setKindQuery('');
    setEntityQuery('');
    setEntities([]);
    inputRef.current?.focus();
  }, []);

  const handleSelectEntity = useCallback((kind, item) => {
    const mention = buildMention(kind, item);
    setValue((prev) => replaceEntityTrigger(prev, kind, mention.name));
    setResolvedMentions((prev) => {
      const already = prev.some((m) => m.kind === kind && m.id === mention.id);
      return already ? prev : [...prev, mention];
    });
    closePicker();
    inputRef.current?.focus();
  }, [closePicker]);

  const handleSubmit = useCallback(() => {
    const val = value.trim();
    if (!val) return;
    if (working && sendMode === 'stop') {
      onStop?.();
      return;
    }
    onSend(val, resolvedMentions);
    setValue('');
    setResolvedMentions([]);
  }, [value, working, sendMode, onSend, onStop, resolvedMentions]);

  const handleKeyDown = useCallback(
    (event) => {
      if (event.key === 'Escape' && stage) {
        event.preventDefault();
        closePicker();
        return;
      }
      if (event.key === 'Enter' && !event.shiftKey && !stage) {
        event.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit, stage, closePicker],
  );

  const placeholder = working
    ? PLACEHOLDER_MAP.working
    : conversationStatus === 'needs_input'
      ? PLACEHOLDER_MAP.needs_input
      : PLACEHOLDER_MAP.default;

  const popperOpen = stage !== null && (
    (stage === 'kind' && visibleKinds.length > 0) ||
    (stage === 'entity')
  );

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

        {/* Stage 1: kind picker */}
        {stage === 'kind' && visibleKinds.length > 0 && (
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

        {/* Stage 2: entity search */}
        {stage === 'entity' && popperOpen && (
          <Paper
            elevation={2}
            role="listbox"
            aria-label={`${activeKind} search results`}
            sx={{
              position: 'absolute',
              bottom: '100%',
              left: 0,
              mb: 0.5,
              zIndex: 10,
              minWidth: 220,
              maxHeight: 220,
              overflowY: 'auto',
            }}
          >
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ display: 'block', px: 1.5, py: 0.5 }}
            >
              Select a {activeKind}
            </Typography>
            {entityLoading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 1 }}>
                <CircularProgress size={16} />
              </Box>
            ) : entities.length === 0 ? (
              <Typography variant="caption" color="text.disabled" sx={{ display: 'block', px: 1.5, pb: 1 }}>
                No matches
              </Typography>
            ) : (
              <List dense disablePadding>
                {entities.map((item) => (
                  <ListItemButton
                    key={item.id}
                    role="option"
                    onClick={() => handleSelectEntity(activeKind, item)}
                    sx={{ fontSize: '0.8125rem' }}
                  >
                    {entityLabel(activeKind, item)}
                  </ListItemButton>
                ))}
              </List>
            )}
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
