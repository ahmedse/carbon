// src/components/dq/RuleJsonEditor.jsx
// JSON-first DQ rule authoring (design decision #1 — no form builder).
//
// - Monospace textarea with a live JSON.parse check.
// - "Validate" button: client-side JSON.parse + structural rule_schema v1
//   mirror checks. The backend has no dry-run endpoint, so server-side
//   rule_schema errors (echoed verbatim from the submit response) are shown
//   in the same error list.
// - "Draft with Pulse": NL prompt → suggest job (POST /dq/jobs/) → poll until
//   done → prefill the textarea from the first pending suggestion.
//
// Used by both the "New rule" dialog (DQWorkspacePage Rules tab) and the
// Definition tab (RuleDetailPage).
import React, { useMemo, useRef, useState } from 'react';
import {
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Alert,
  CircularProgress,
  List,
  ListItem,
  ListItemText,
  MenuItem,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import FactCheckIcon from '@mui/icons-material/FactCheck';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../NotificationProvider';
import { createDQJob, getDQJob, listDQSuggestions } from '../../api/dq';

// ── rule_schema v1 (backend/dq/rule_schema.py) mirror — client checks only ──

export const RULE_TYPES = [
  'not_null', 'unique', 'allowed_values', 'range', 'regex',
  'reference_integrity', 'threshold', 'nl_check', 'anomaly_detect',
];

export const RULE_LEVELS = ['field', 'business'];

export const DIMENSION_CODES = [
  'completeness', 'validity', 'accuracy', 'consistency', 'timeliness',
  'uniqueness', 'integrity', 'reasonability',
];

export const SEVERITY_VALUES = ['info', 'warn', 'error'];

/**
 * Client-side structural validation mirroring backend rule_schema.validate_definition.
 * Returns [{field, code, message}] — empty array = looks valid.
 */
export function validateDefinitionClient(d) {
  const errors = [];
  if (!d || typeof d !== 'object' || Array.isArray(d)) {
    return [{ field: '_root', code: 'invalid_type', message: 'definition must be a JSON object' }];
  }
  if (d.schema_version !== 1) {
    errors.push({ field: 'schema_version', code: 'invalid_value', message: 'schema_version must be 1' });
  }
  if (!d.name || typeof d.name !== 'string' || !d.name.trim()) {
    errors.push({ field: 'name', code: 'required', message: 'name is required and must be a non-empty string' });
  }
  if (!RULE_LEVELS.includes(d.level)) {
    errors.push({ field: 'level', code: 'invalid_value', message: `level must be one of ${RULE_LEVELS.join(', ')}` });
  }
  if (!DIMENSION_CODES.includes(d.dimension)) {
    errors.push({ field: 'dimension', code: 'invalid_value', message: `dimension must be one of ${DIMENSION_CODES.join(', ')}` });
  }
  if (!RULE_TYPES.includes(d.type)) {
    errors.push({ field: 'type', code: 'invalid_value', message: `type must be one of ${RULE_TYPES.join(', ')}` });
  }
  if (!SEVERITY_VALUES.includes(d.severity)) {
    errors.push({ field: 'severity', code: 'invalid_value', message: `severity must be one of ${SEVERITY_VALUES.join(', ')}` });
  }
  if (typeof d.active !== 'boolean') {
    errors.push({ field: 'active', code: 'invalid_type', message: 'active must be a boolean' });
  }
  const bindings = d.bindings;
  if (!Array.isArray(bindings) || bindings.length === 0) {
    errors.push({ field: 'bindings', code: 'required', message: 'bindings must be a non-empty list of {table, field} objects' });
  } else {
    bindings.forEach((b, i) => {
      if (!b || typeof b !== 'object' || !b.table || typeof b.table !== 'string') {
        errors.push({ field: `bindings[${i}].table`, code: 'required', message: 'binding table is required and must be a string' });
      }
    });
  }
  if (d.params !== undefined && (typeof d.params !== 'object' || d.params === null || Array.isArray(d.params))) {
    errors.push({ field: 'params', code: 'invalid_type', message: 'params must be a JSON object' });
  }
  if (d.enforcement && d.enforcement.on_write === true && (d.type === 'nl_check' || d.type === 'anomaly_detect')) {
    errors.push({ field: 'enforcement.on_write', code: 'invalid_value', message: `enforcement.on_write cannot be true for ${d.type} rules` });
  }
  return errors;
}

/**
 * Format server-side rule_schema errors (DRF returns {definition: [errors]}).
 */
export function normalizeServerErrors(payload) {
  const list = [];
  const raw = payload?.definition;
  if (Array.isArray(raw)) {
    raw.forEach((e) => {
      if (typeof e === 'string') list.push({ field: 'definition', code: 'server', message: e });
      else if (e && typeof e === 'object') list.push({ field: e.field || 'definition', code: e.code || 'server', message: e.message || JSON.stringify(e) });
    });
  } else if (typeof raw === 'string') {
    list.push({ field: 'definition', code: 'server', message: raw });
  } else if (typeof payload?.error === 'string') {
    list.push({ field: '_root', code: 'server', message: payload.error });
  }
  return list;
}

// ── Sample template (empty-but-valid skeleton for new rules) ────────────────

export const EMPTY_DEFINITION_TEMPLATE = `{
  "schema_version": 1,
  "name": "",
  "level": "field",
  "dimension": "validity",
  "type": "not_null",
  "severity": "warn",
  "active": true,
  "bindings": [
    { "table": "TABLE_NAME", "field": "FIELD_NAME" }
  ],
  "params": {},
  "enforcement": { "on_write": true },
  "description": ""
}`;

// ── Component ───────────────────────────────────────────────────────────────

export default function RuleJsonEditor({
  value,
  onChange,
  serverErrors = [],
  disabled = false,
  tables = [],
  onDraftApplied = null,
  minRows = 16,
}) {
  const { token } = useAuth();
  const { notify } = useNotification();

  const [clientErrors, setClientErrors] = useState([]);
  const [pulseOpen, setPulseOpen] = useState(false);
  const [pulseTable, setPulseTable] = useState('');
  const [pulsePrompt, setPulsePrompt] = useState('');
  const [drafting, setDrafting] = useState(false);
  const pollRef = useRef(null);

  const jsonValid = useMemo(() => {
    if (!value || !value.trim()) return true; // empty = not validated yet
    try {
      JSON.parse(value);
      return true;
    } catch {
      return false;
    }
  }, [value]);

  const handleValidate = () => {
    setClientErrors([]);
    let parsed = null;
    try {
      parsed = JSON.parse(value);
    } catch (err) {
      setClientErrors([{ field: '_root', code: 'parse', message: `Invalid JSON: ${err.message}` }]);
      return;
    }
    const errors = validateDefinitionClient(parsed);
    setClientErrors(errors);
    if (errors.length === 0) {
      notify({ message: 'Definition looks valid', type: 'success' });
    }
  };

  const allErrors = useMemo(
    () => [...clientErrors, ...(Array.isArray(serverErrors) ? serverErrors : [])],
    [clientErrors, serverErrors],
  );

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  const startPulseDraft = async () => {
    if (!pulseTable || !pulsePrompt.trim()) {
      notify({ message: 'Select a table and enter a prompt', type: 'warning' });
      return;
    }
    setDrafting(true);
    stopPolling();
    try {
      const job = await createDQJob(token, {
        job_type: 'suggest',
        data_table_id: pulseTable,
        payload: { prompt: pulsePrompt.trim() },
      });
      if (job?.status === 'done' && job?.result) {
        applyDraftFromJob(job);
        return;
      }
      if (job?.status === 'failed') {
        notify({ message: `Pulse draft failed: ${job.error || 'unknown error'}`, type: 'error' });
        setDrafting(false);
        return;
      }
      // Poll until the suggest job reaches a terminal state.
      pollRef.current = setInterval(async () => {
        try {
          const current = await getDQJob(token, job.id);
          if (current.status === 'done') {
            stopPolling();
            setDrafting(false);
            applyDraftFromJob(current);
          } else if (['failed', 'canceled'].includes(current.status)) {
            stopPolling();
            setDrafting(false);
            notify({ message: `Pulse draft ${current.status}: ${current.error || ''}`, type: 'error' });
          }
        } catch {
          // transient poll failure — keep polling
        }
      }, 4000);
    } catch (err) {
      setDrafting(false);
      notify({ message: err.message || 'Could not start Pulse draft', type: 'error' });
    }
  };

  const applyDraftFromJob = async (job) => {
    try {
      const data = await listDQSuggestions(token, { status: 'pending' });
      const suggestions = Array.isArray(data) ? data : data?.results || [];
      const first = suggestions.find((s) => s.data_table === job.data_table) || suggestions[0];
      if (!first?.payload) {
        notify({ message: 'Pulse finished but produced no suggestions', type: 'info' });
        return;
      }
      onChange(JSON.stringify(first.payload, null, 2));
      onDraftApplied?.(first.payload);
      notify({ message: 'Draft loaded from Pulse — review and save', type: 'success' });
      setPulseOpen(false);
      setPulsePrompt('');
    } catch (err) {
      notify({ message: err.message || 'Could not load Pulse draft', type: 'error' });
    }
  };

  const handleClosePulse = () => {
    stopPolling();
    setPulseOpen(false);
    setDrafting(false);
  };

  return (
    <Box>
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} sx={{ mb: 1 }} alignItems="center">
        <Tooltip title="Client JSON.parse + structural rule_schema v1 checks. Server-side errors are echoed verbatim on submit.">
          <Button
            size="small"
            variant="outlined"
            startIcon={<FactCheckIcon />}
            onClick={handleValidate}
            disabled={disabled || !value?.trim()}
          >
            Validate
          </Button>
        </Tooltip>
        <Button
          size="small"
          variant="outlined"
          startIcon={<AutoAwesomeIcon />}
          onClick={() => setPulseOpen(true)}
          disabled={disabled || tables.length === 0}
        >
          Draft with Pulse
        </Button>
        <Chip
          size="small"
          label={jsonValid ? 'JSON OK' : 'JSON invalid'}
          color={jsonValid ? 'success' : 'error'}
          variant="outlined"
        />
        {allErrors.length > 0 && (
          <Chip size="small" label={`${allErrors.length} validation error(s)`} color="warning" />
        )}
      </Stack>

      <TextField
        fullWidth
        multiline
        minRows={minRows}
        maxRows={30}
        value={value}
        onChange={(e) => {
          onChange(e.target.value);
          setClientErrors([]);
        }}
        disabled={disabled}
        spellCheck={false}
        inputProps={{
          style: { fontFamily: "'JetBrains Mono', 'Fira Code', Consolas, monospace", fontSize: 13 },
        }}
        placeholder='Paste a rule definition or use "Draft with Pulse".'
        sx={{ '& .MuiOutlinedInput-root': { bgcolor: 'background.paper' } }}
      />

      {allErrors.length > 0 && (
        <Alert severity="warning" sx={{ mt: 1 }} variant="outlined">
          <List dense disablePadding>
            {allErrors.slice(0, 12).map((e, i) => (
              <ListItem key={i} disableGutters sx={{ py: 0.25 }}>
                <ListItemText
                  primary={e.message}
                  secondary={e.field ? `field: ${e.field} (${e.code})` : e.code}
                  primaryTypographyProps={{ variant: 'body2' }}
                  secondaryTypographyProps={{ variant: 'caption' }}
                />
              </ListItem>
            ))}
          </List>
        </Alert>
      )}

      {/* Draft with Pulse dialog */}
      <Dialog open={pulseOpen} onClose={handleClosePulse} fullWidth maxWidth="sm">
        <DialogTitle>Draft a rule with Pulse</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            Describe the rule in plain language. Pulse analyzes the table and
            proposes a JSON definition for your approval — nothing is created
            until you save it.
          </Typography>
          <TextField
            select
            fullWidth
            size="small"
            label="Data table"
            value={pulseTable}
            onChange={(e) => setPulseTable(e.target.value)}
            sx={{ mt: 2 }}
          >
            {tables.map((t) => (
              <MenuItem key={t.data_table ?? t.id} value={t.data_table ?? t.id}>
                {t.title || t.name || t.table_name || `Table #${t.data_table ?? t.id}`}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            fullWidth
            multiline
            minRows={3}
            label="Prompt"
            placeholder='e.g. "meter readings must be positive and within 0–100000 kWh"'
            value={pulsePrompt}
            onChange={(e) => setPulsePrompt(e.target.value)}
            sx={{ mt: 2 }}
            disabled={drafting}
          />
          {drafting && (
            <Stack direction="row" spacing={1} alignItems="center" sx={{ mt: 2 }}>
              <CircularProgress size={16} />
              <Typography variant="body2">Pulse is drafting… this can take a few seconds.</Typography>
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={handleClosePulse} disabled={drafting}>Cancel</Button>
          <Button
            variant="contained"
            onClick={startPulseDraft}
            disabled={drafting || !pulseTable || !pulsePrompt.trim()}
            startIcon={drafting ? <CircularProgress size={16} /> : <AutoAwesomeIcon />}
          >
            Generate draft
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
