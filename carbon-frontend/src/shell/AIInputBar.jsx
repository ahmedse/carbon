// src/shell/AIInputBar.jsx
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  IconButton,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import { PickerMenu, PickerOption } from '../components/ai/PickerMenu';
import SendIcon from '@mui/icons-material/Send';
import StopCircleIcon from '@mui/icons-material/StopCircle';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import AssignmentIcon from '@mui/icons-material/Assignment';
import ClearAllIcon from '@mui/icons-material/ClearAll';
import BookmarkIcon from '@mui/icons-material/Bookmark';
import CallSplitIcon from '@mui/icons-material/CallSplit';
import DownloadIcon from '@mui/icons-material/Download';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';
import TableChartIcon from '@mui/icons-material/TableChart';
import RuleIcon from '@mui/icons-material/Rule';
import TextFieldsIcon from '@mui/icons-material/TextFields';
import ExtensionIcon from '@mui/icons-material/Extension';
import { useAuth } from '../auth/AuthContext';
import { apiFetch } from '../api/api';
import { API_ROUTES } from '../config';
import { useExecuteMode } from './useExecuteMode';

const PLACEHOLDER_MAP = {
  working: 'AI is thinking… (Enter to queue)',
  needs_input: 'Respond to AI\'s question…',
  default: 'Ask a question or give directions…',
};



const MENTION_KINDS = ['table', 'rule', 'field', 'module'];

// Two-stage mention: first '#' shows kinds; after kind + space typed, search entities.
// Stage 1: /(^|\s)#([a-zA-Z]*)$/ — kind picker
// Stage 2: /(^|\s)#(table|rule|field|module) ([^#]*)$/ — entity search within a kind
const KIND_TRIGGER_RE = /(^|[\s\n])#([a-zA-Z]*)$/;
const ENTITY_TRIGGER_RE = /(^|[\s\n])#(table|rule|field|module) ([^#\n]*)$/;

// Slash-command menu: a '/' at the start of the input or after whitespace,
// followed by optional letters. Directives insert prompt text the user completes;
// actions trigger an existing workspace action via the optional onCommand callback.
const SLASH_TRIGGER_RE = /(^|[\s\n])\/([a-zA-Z]*)$/;

// Source of truth for the '/' command menu (W8-A). `kind` separates directives
// (insert text) from actions (call onCommand). Labels/descriptions are outcome
// copy, never engine terms (RULE_23).
const SLASH_COMMANDS = [
  { name: 'summarize',  kind: 'directive', label: 'Summarize this conversation so far', description: 'Ask for a summary of the thread' },
  { name: 'plan',       kind: 'directive', label: 'Plan a task to',                   description: 'Draft a plan before anything runs' },
  { name: 'clear',      kind: 'action',    label: 'Clear working context',            description: 'Drop the in-progress context, keep history' },
  { name: 'checkpoint', kind: 'action',    label: 'Save a checkpoint',                description: 'Snapshot the current context' },
  { name: 'fork',       kind: 'action',    label: 'Fork this conversation',           description: 'Branch from a saved checkpoint' },
  { name: 'export',     kind: 'action',    label: 'Export conversation',              description: 'Download this thread as Markdown' },
  { name: 'help',       kind: 'action',    label: 'Keyboard shortcuts',               description: 'Show Pulse shortcuts' },
];

// Icon-led rows to match ShellSidebar (icon + 0.65rem label, left-bar active
// indicator). Slash commands and mention kinds share the same visual language.
const COMMAND_ICONS = {
  summarize: <AutoAwesomeIcon />,
  plan: <AssignmentIcon />,
  clear: <ClearAllIcon />,
  checkpoint: <BookmarkIcon />,
  fork: <CallSplitIcon />,
  export: <DownloadIcon />,
  help: <HelpOutlineIcon />,
};

const KIND_ICONS = {
  table: <TableChartIcon />,
  rule: <RuleIcon />,
  field: <TextFieldsIcon />,
  module: <ExtensionIcon />,
};

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

// ---------------------------------------------------------------------------
// Picker rows match ShellSidebar (W8-A polish): icon + 0.65rem label, left-bar
// active indicator, dense keyboard-navigable rows. The PickerMenu/PickerOption
// listbox lives in components/ai/PickerMenu.jsx.
// ---------------------------------------------------------------------------
const MENTION_KIND_LABELS = {
  table: 'Data table',
  rule: 'DQ rule',
  field: 'Field',
  module: 'Module',
};

const MENTION_KIND_DESCRIPTIONS = {
  table: 'Reference a data table',
  rule: 'Reference a DQ rule',
  field: 'Reference a field',
  module: 'Reference a module',
};

function AIInputBar({
  onSend,
  working,
  onStop,
  conversationStatus,
  onMentionsChange,
  onCommand,
}) {
  const { token } = useAuth();
  const { executeMode } = useExecuteMode();
  const inputRef = useRef(null);
  const rootRef = useRef(null);
  // VS Code Copilot-style growth: the composer expands up to ~55% of the
  // available pane height (row ≈ 20px), then scrolls internally instead of
  // clipping. Measured from the parent (fixed-height flex column), so there
  // is no feedback loop between growth and measurement.
  const [maxRows, setMaxRows] = useState(10);
  const [value, setValue] = useState('');
  // Stage: null | 'kind' | 'entity' | 'slash'
  const [stage, setStage] = useState(null);
  const [kindQuery, setKindQuery] = useState('');
  const [activeKind, setActiveKind] = useState(null);
  const [entityQuery, setEntityQuery] = useState('');
  const [slashQuery, setSlashQuery] = useState('');
  // Keyboard highlight within the open picker (ArrowUp/Down + Enter).
  const [activeIndex, setActiveIndex] = useState(0);
  const [entities, setEntities] = useState([]);
  const [entityLoading, setEntityLoading] = useState(false);
  // Resolved mention objects: { kind, id, name }
  const [resolvedMentions, setResolvedMentions] = useState([]);

  const visibleKinds = useMemo(
    () => MENTION_KINDS.filter((k) => k.startsWith(kindQuery)),
    [kindQuery],
  );

  // Slash-command matches (case-insensitive prefix on the registered name).
  const visibleCommands = useMemo(
    () => SLASH_COMMANDS.filter((c) => c.name.startsWith(slashQuery.toLowerCase())),
    [slashQuery],
  );

  // Notify parent of mention changes.
  useEffect(() => {
    onMentionsChange?.(resolvedMentions);
  }, [resolvedMentions, onMentionsChange]);

  // Grow-to-fit: watch the parent height and derive the max textarea rows.
  useEffect(() => {
    const el = rootRef.current?.parentElement;
    if (!el) return undefined;
    const compute = () => {
      const h = el.clientHeight || 600;
      const rows = Math.max(6, Math.min(18, Math.round((h * 0.55) / 20)));
      setMaxRows(rows);
    };
    compute();
    if (typeof ResizeObserver === 'undefined') {
      window.addEventListener('resize', compute);
      return () => window.removeEventListener('resize', compute);
    }
    const ro = new ResizeObserver(compute);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

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

  // Reset the keyboard highlight whenever the menu contents change.
  useEffect(() => {
    setActiveIndex(0);
  }, [stage, slashQuery, kindQuery, entityQuery]);

  const closePicker = useCallback(() => {
    setStage(null);
    setKindQuery('');
    setActiveKind(null);
    setEntityQuery('');
    setEntities([]);
    setSlashQuery('');
  }, []);

  const handleChange = useCallback((event) => {
    const next = event.target.value;
    setValue(next);

    // Slash-command menu: a '/' at the start or after whitespace + optional letters.
    // Mutually exclusive with '#' — a '/' token can never also be a '#' token.
    const slashMatch = SLASH_TRIGGER_RE.exec(next);
    if (slashMatch) {
      setStage('slash');
      setSlashQuery(slashMatch[2]);
      setKindQuery('');
      setActiveKind(null);
      setEntityQuery('');
      setEntities([]);
      return;
    }

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

  const handleSelectCommand = useCallback((command) => {
    if (command.kind === 'directive') {
      // Replace the trailing /partial with the command label + a trailing space,
      // so the user keeps typing the rest of the prompt and presses Enter.
      setValue((prev) => prev.replace(SLASH_TRIGGER_RE, `$1${command.label} `));
      closePicker();
      inputRef.current?.focus();
      return;
    }
    // Action → dispatch to the parent (no-op when onCommand is absent).
    onCommand?.(command.name);
    setValue('');
    closePicker();
    inputRef.current?.focus();
  }, [closePicker, onCommand]);

  const handleSubmit = useCallback(() => {
    const val = value.trim();
    if (!val) return;
    onSend(val, resolvedMentions);
    setValue('');
    // Context persists across turns (VS Code Copilot-style) — the composer
    // keeps attached mentions until the user clears them, so "restore
    // context" keeps working for follow-up questions.
  }, [value, onSend, resolvedMentions]);

  const removeMention = useCallback((kind, id) => {
    setResolvedMentions((prev) => prev.filter((m) => !(m.kind === kind && m.id === id)));
  }, []);

  const handleKeyDown = useCallback(
    (event) => {
      // No picker open → Enter submits (Shift+Enter inserts a newline).
      if (!stage) {
        if (event.key === 'Enter' && !event.shiftKey) {
          event.preventDefault();
          handleSubmit();
        }
        return;
      }

      const items = stage === 'slash' ? visibleCommands
        : stage === 'kind' ? visibleKinds
        : stage === 'entity' ? entities
        : [];

      if (event.key === 'Escape') {
        event.preventDefault();
        closePicker();
        return;
      }
      if (event.key === 'ArrowDown' && items.length > 0) {
        event.preventDefault();
        setActiveIndex((i) => (i + 1) % items.length);
        return;
      }
      if (event.key === 'ArrowUp' && items.length > 0) {
        event.preventDefault();
        setActiveIndex((i) => (i - 1 + items.length) % items.length);
        return;
      }
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        const item = items[activeIndex];
        if (!item) return;
        if (stage === 'slash') handleSelectCommand(item);
        else if (stage === 'kind') handleSelectKind(item);
        else if (stage === 'entity') handleSelectEntity(activeKind, item);
      }
      // Shift+Enter falls through → newline in the multiline textarea.
    },
    [
      stage,
      visibleCommands,
      visibleKinds,
      entities,
      activeKind,
      activeIndex,
      handleSubmit,
      closePicker,
      handleSelectCommand,
      handleSelectKind,
      handleSelectEntity,
    ],
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
      ref={rootRef}
      sx={{
        borderTop: 1,
        borderLeft: executeMode ? 1 : 0,
        borderRight: executeMode ? 1 : 0,
        borderBottom: executeMode ? 1 : 0,
        borderColor: executeMode ? 'warning.main' : 'divider',
        bgcolor: 'background.paper',
      }}
    >


      {/* Composer chrome — W5-A (ADR-0014): the Ask/Agent mode selector moved
          to the workspace header. The composer is mode-agnostic now; the
          safety contract lives in AIWorkspaceHeader. */}

      {/* Persistent context chips — attached mentions survive across turns
          until explicitly removed (restore context). */}
      {resolvedMentions.length > 0 && (
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 0.5,
            flexWrap: 'wrap',
            px: 1.5,
            pt: 0.75,
          }}
        >
          <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.625rem' }}>
            Context
          </Typography>
          {resolvedMentions.map((m) => (
            <Chip
              key={`${m.kind}-${m.id}`}
              size="small"
              variant="outlined"
              label={`#${m.kind} ${m.name}`}
              onDelete={() => removeMention(m.kind, m.id)}
              aria-label={`Remove context ${m.kind} ${m.name}`}
            />
          ))}
          <Button
            size="small"
            onClick={() => setResolvedMentions([])}
            aria-label="Clear all context"
            sx={{ fontSize: '0.625rem', minHeight: 20, p: 0.5 }}
          >
            Clear
          </Button>
        </Box>
      )}

      <Box
        sx={{
          display: 'flex',
          alignItems: 'flex-end',
          gap: 0.5,
          px: 1.5,
          py: 1,
        }}
      >
        <Box sx={{ position: 'relative', flex: 1, minWidth: 0 }}>
        <TextField
          inputRef={inputRef}
          fullWidth
          multiline
          minRows={1}
          maxRows={maxRows}
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
            // Scroll within the composer once it reaches maxRows (Copilot-style)
            '& .MuiOutlinedInput-input': {
              overflowY: 'auto',
            },
          }}
          inputProps={{ 'aria-label': 'Message input' }}
        />

        {/* Slash command menu (ShellSidebar-style, compact + keyboard navigable) */}
        {stage === 'slash' && visibleCommands.length > 0 && (
          <PickerMenu label="Commands" minWidth={300} maxHeight={220}>
            {visibleCommands.map((cmd, i) => (
              <PickerOption
                key={cmd.name}
                active={i === activeIndex}
                ariaLabel={cmd.label}
                icon={COMMAND_ICONS[cmd.name]}
                title={cmd.label}
                description={cmd.description}
                onClick={() => handleSelectCommand(cmd)}
                onHover={() => setActiveIndex(i)}
              />
            ))}
          </PickerMenu>
        )}

        {/* Stage 1: kind picker */}
        {stage === 'kind' && visibleKinds.length > 0 && (
          <PickerMenu label="Mention kinds" minWidth={220} maxHeight={180}>
            {visibleKinds.map((kind, i) => (
              <PickerOption
                key={kind}
                active={i === activeIndex}
                ariaLabel={`#${kind}`}
                icon={KIND_ICONS[kind]}
                title={MENTION_KIND_LABELS[kind]}
                description={MENTION_KIND_DESCRIPTIONS[kind]}
                onClick={() => handleSelectKind(kind)}
                onHover={() => setActiveIndex(i)}
              />
            ))}
          </PickerMenu>
        )}

        {/* Stage 2: entity search */}
        {stage === 'entity' && popperOpen && (
          <PickerMenu label={`${activeKind} search results`} minWidth={240} maxHeight={200}>
            {entityLoading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 1 }}>
                <CircularProgress size={14} />
              </Box>
            ) : entities.length === 0 ? (
              <Typography variant="caption" color="text.disabled" sx={{ display: 'block', px: 1.25, py: 1 }}>
                No matches
              </Typography>
            ) : (
              entities.map((item, i) => (
                <PickerOption
                  key={item.id}
                  active={i === activeIndex}
                  ariaLabel={entityLabel(activeKind, item)}
                  icon={KIND_ICONS[activeKind]}
                  title={entityLabel(activeKind, item)}
                  description={`#${activeKind}`}
                  onClick={() => handleSelectEntity(activeKind, item)}
                  onHover={() => setActiveIndex(i)}
                />
              ))
            )}
          </PickerMenu>
        )}
      </Box>

      {working && (
        <Tooltip title="Stop generation">
          <IconButton size="small" color="warning" onClick={onStop} aria-label="Stop generation">
            <StopCircleIcon fontSize="small" />
          </IconButton>
        </Tooltip>
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
    </Box>
  );
}

AIInputBar.propTypes = {
  onSend: PropTypes.func.isRequired,
  working: PropTypes.bool,
  onStop: PropTypes.func,
  conversationStatus: PropTypes.string,
  onMentionsChange: PropTypes.func,
  onCommand: PropTypes.func,
};

export default AIInputBar;
