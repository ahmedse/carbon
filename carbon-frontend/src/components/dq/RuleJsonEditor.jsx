// src/components/dq/RuleJsonEditor.jsx
// JSON-first DQ rule authoring (design decision #1 — no form builder).
//
// - Monaco JSON editor with live JSON.parse checks.
// - "Validate" button: client-side JSON.parse + structural rule_schema v1
//   mirror checks. The backend has no dry-run endpoint, so server-side
//   rule_schema errors (echoed verbatim from the submit response) are shown
//   in the same error list.
// - "Draft with AI": NL prompt → suggest job (POST /dq/jobs/) → poll until
//   done → prefill the editor from the first pending suggestion.
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
import Editor from '@monaco-editor/react';
import AIActionButton from './AIActionButton';
import { useAuth } from '../../auth/AuthContext';
import { useThemeMode } from '../../theme/useThemeMode';
import { useNotification } from '../NotificationProvider';
import { createDQJob, getDQJob, listDQSuggestions } from '../../api/dq';
import dqRuleSchema from './dqRuleSchema.json';
import { validateDefinitionClient } from './ruleJsonValidation';

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
  const { mode: themeMode } = useThemeMode();
  const { notify } = useNotification();

  const editorHeight = Math.max(200, (minRows || 16) * 22);

  const [clientErrors, setClientErrors] = useState([]);
  const [aiDraftOpen, setAiDraftOpen] = useState(false);
  const [aiTable, setAiTable] = useState('');
  const [aiPrompt, setAiPrompt] = useState('');
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

  // Detect when user chooses AI for a field-level rule — show guidance.
  const aiFieldWarning = useMemo(() => {
    if (!value || !value.trim()) return false;
    try {
      const d = JSON.parse(value);
      return d.level === 'field' && (d.type === 'nl_check' || d.type === 'anomaly_detect');
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

  const startAiDraft = async () => {
    if (!aiTable || !aiPrompt.trim()) {
      notify({ message: 'Select a table and enter a prompt', type: 'warning' });
      return;
    }
    setDrafting(true);
    stopPolling();
    try {
      const job = await createDQJob(token, {
        job_type: 'suggest',
        data_table_id: aiTable,
        payload: { prompt: aiPrompt.trim() },
      });
      if (job?.status === 'done' && job?.result) {
        applyDraftFromJob(job);
        return;
      }
      if (job?.status === 'failed') {
        notify({ message: `AI draft failed: ${job.error || 'unknown error'}`, type: 'error' });
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
            notify({ message: `AI draft ${current.status}: ${current.error || ''}`, type: 'error' });
          }
        } catch {
          // transient poll failure — keep polling
        }
      }, 4000);
    } catch (err) {
      setDrafting(false);
      notify({ message: err.message || 'Could not start AI draft', type: 'error' });
    }
  };

  const applyDraftFromJob = async (job) => {
    try {
      const data = await listDQSuggestions(token, { status: 'pending' });
      const suggestions = Array.isArray(data) ? data : data?.results || [];
      const first = suggestions.find((s) => s.data_table === job.data_table) || suggestions[0];
      if (!first?.payload) {
        notify({ message: 'AI finished but produced no suggestions', type: 'info' });
        return;
      }
      onChange(JSON.stringify(first.payload, null, 2));
      onDraftApplied?.(first.payload);
      notify({ message: 'Draft loaded from AI — review and save', type: 'success' });
      setAiDraftOpen(false);
      setAiPrompt('');
    } catch (err) {
      notify({ message: err.message || 'Could not load AI draft', type: 'error' });
    }
  };

  const handleCloseAiDraft = () => {
    stopPolling();
    setAiDraftOpen(false);
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
        <AIActionButton
          title="Draft a rule with AI"
          onClick={() => setAiDraftOpen(true)}
          disabled={disabled || tables.length === 0}
        />
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

      <Box sx={{ position: 'relative', border: 1, borderColor: 'divider', borderRadius: 1, overflow: 'hidden' }}>
        <Chip
          label="Schema v1"
          size="small"
          color="primary"
          variant="filled"
          sx={{
            position: 'absolute',
            top: 8,
            right: 8,
            zIndex: 1,
            fontFamily: 'monospace',
            fontSize: '0.65rem',
            opacity: 0.75,
          }}
        />
        <Editor
          height={`${editorHeight}px`}
          defaultLanguage="json"
          theme={themeMode === 'dark' ? 'vs-dark' : 'vs'}
          value={value}
          onChange={(newValue) => {
            onChange(newValue || '');
            setClientErrors([]);
          }}
          beforeMount={(monaco) => {
            monaco.languages.json.jsonDefaults.setDiagnosticsOptions({
              validate: true,
              allowComments: false,
              schemas: [{
                uri: dqRuleSchema.$id,
                fileMatch: ['*'],
                schema: dqRuleSchema,
              }],
            });
          }}
          loading={
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: `${editorHeight}px` }}>
              <CircularProgress size={24} />
            </Box>
          }
          options={{
            minimap: { enabled: false },
            lineNumbers: 'on',
            folding: true,
            fontSize: 13,
            tabSize: 2,
            scrollBeyondLastLine: false,
            automaticLayout: true,
            readOnly: disabled,
            wordWrap: 'on',
            renderWhitespace: 'selection',
            bracketPairColorization: { enabled: true },
            guides: { indentation: true },
          }}
        />
      </Box>

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

      {aiFieldWarning && (
        <Alert severity="info" sx={{ mt: 1 }} variant="outlined">
          <Typography variant="body2">
            <strong>AI NL Check at field level?</strong> For numeric bounds, null checks,
            format patterns, or enumerated values, prefer{' '}
            <strong>Range</strong>, <strong>Not Null</strong>, <strong>Regex</strong>, or{' '}
            <strong>Allowed Values</strong>. AI is for semantic text validation — e.g.
            &ldquo;description must describe a real incident&rdquo; or &ldquo;address must not
            be a placeholder.&rdquo;
          </Typography>
        </Alert>
      )}

      {/* Draft with AI dialog */}
      <Dialog open={aiDraftOpen} onClose={handleCloseAiDraft} fullWidth maxWidth="sm">
        <DialogTitle>Draft a rule with AI</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            Describe the rule in plain language. The AI analyzes the table and
            proposes a JSON definition for your approval — nothing is created
            until you save it.
          </Typography>
          <TextField
            select
            fullWidth
            size="small"
            label="Data table"
            value={aiTable}
            onChange={(e) => setAiTable(e.target.value)}
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
            value={aiPrompt}
            onChange={(e) => setAiPrompt(e.target.value)}
            sx={{ mt: 2 }}
            disabled={drafting}
          />
          {drafting && (
            <Stack direction="row" spacing={1} alignItems="center" sx={{ mt: 2 }}>
              <CircularProgress size={16} />
              <Typography variant="body2">AI is drafting… this can take a few seconds.</Typography>
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseAiDraft} disabled={drafting}>Cancel</Button>
          <Button
            variant="contained"
            onClick={startAiDraft}
            disabled={drafting || !aiTable || !aiPrompt.trim()}
            startIcon={drafting ? <CircularProgress size={16} /> : <AutoAwesomeIcon />}
          >
            Generate draft
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
