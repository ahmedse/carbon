// src/shell/StepEditDialog.jsx
// W3-F — per-step edit dialog for the AI Workspace plan card. Edits the
// outcome description (title), instructions, dependencies, and agent_role.
// Saving goes through the parent, which shows the diff-review consent gate
// (RULE_21) before the revised plan is re-approved. Theme tokens only (RULE_8).
import React, { useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  TextField,
  Typography,
} from '@mui/material';
import Autocomplete from '@mui/material/Autocomplete';
import Chip from '@mui/material/Chip';
import { useTranslation } from 'react-i18next';
import { AGENT_ROLE_LABELS } from './aiTaskStatus';

const AGENT_ROLE_OPTIONS = Object.keys(AGENT_ROLE_LABELS);

/**
 * Step edit dialog.
 * @param {object} props
 * @param {boolean} props.open
 * @param {object|null} props.step - the step being edited
 * @param {Array} props.steps - all plan steps (dependency options)
 * @param {boolean} [props.busy]
 * @param {function} [props.onSave] - (fields) => void
 * @param {function} [props.onClose]
 */
export default function StepEditDialog({ open, step, steps, busy, onSave, onClose }) {
  const { t } = useTranslation('ai');
  const [title, setTitle] = useState('');
  const [instructions, setInstructions] = useState('');
  const [dependsOn, setDependsOn] = useState([]);
  const [agentRole, setAgentRole] = useState('orchestrator');

  // Sync form state whenever a (new) step opens.
  useEffect(() => {
    if (!open || !step) return;
    setTitle(step.intent || '');
    setInstructions(step.instructions || '');
    const role = String(step.agent_role || 'orchestrator').trim();
    setAgentRole(AGENT_ROLE_OPTIONS.includes(role) ? role : 'orchestrator');
    const deps = Array.isArray(step.depends_on) ? step.depends_on : [];
    setDependsOn(
      (steps || [])
        .filter((s) => s && s.step_id !== step.step_id && deps.includes(s.step_id))
        .map((s) => ({ id: s.step_id, label: s.intent || `Step ${s.step_id}` })),
    );
  }, [open, step, steps]);

  const options = (steps || [])
    .filter((s) => s && s.step_id !== step?.step_id)
    .map((s) => ({ id: s.step_id, label: s.intent || `Step ${s.step_id}` }));

  const handleSave = () => {
    if (!step) return;
    onSave?.({
      title: title.trim(),
      instructions: instructions.trim(),
      depends_on: dependsOn.map((d) => d.id),
      agent_role: agentRole,
    });
  };

  return (
    <Dialog open={open} onClose={busy ? undefined : onClose} maxWidth="sm" fullWidth aria-label="Edit step">
      <DialogTitle sx={{ fontSize: '0.875rem', fontWeight: 700, py: 1.5 }}>Edit step</DialogTitle>
      <DialogContent dividers sx={{ pt: 1.25 }}>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: '0.6875rem', mb: 1 }}>
          Change what this step does and which agent role runs it. Saving opens a review of the changes — the plan needs your approval again before it runs.
        </Typography>
        <TextField
          fullWidth
          size="small"
          label="Title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          inputProps={{ 'aria-label': 'Step title' }}
          sx={{ mb: 1.5, '& .MuiInputBase-input': { fontSize: '0.75rem' } }}
        />
        <TextField
          fullWidth
          size="small"
          label="Instructions"
          multiline
          minRows={2}
          maxRows={4}
          value={instructions}
          onChange={(e) => setInstructions(e.target.value)}
          inputProps={{ 'aria-label': 'Step instructions' }}
          sx={{ mb: 1.5, '& .MuiInputBase-input': { fontSize: '0.75rem' } }}
        />
        <FormControl fullWidth size="small" sx={{ mb: 1.5 }}>
          <InputLabel id="step-agent-role-label">{t('stepEdit.agentRole')}</InputLabel>
          <Select
            labelId="step-agent-role-label"
            label={t('stepEdit.agentRole')}
            value={agentRole}
            onChange={(e) => setAgentRole(e.target.value)}
            inputProps={{ 'aria-label': t('stepEdit.agentRoleAria') }}
            sx={{ fontSize: '0.75rem' }}
          >
            {AGENT_ROLE_OPTIONS.map((role) => (
              <MenuItem key={role} value={role} sx={{ fontSize: '0.75rem' }}>
                {AGENT_ROLE_LABELS[role]}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <Autocomplete
          multiple
          size="small"
          options={options}
          getOptionLabel={(o) => o.label}
          isOptionEqualToValue={(o, v) => o.id === v.id}
          value={dependsOn}
          onChange={(_e, value) => setDependsOn(value)}
          renderTags={(value, getTagProps) =>
            value.map((option, index) => (
              <Chip
                key={option.id}
                size="small"
                variant="outlined"
                label={option.label}
                sx={{ height: 18, fontSize: '0.625rem' }}
                {...getTagProps({ index })}
              />
            ))
          }
          renderInput={(params) => (
            <TextField
              {...params}
              size="small"
              label={t('stepEdit.runsAfter')}
              placeholder={t('stepEdit.dependsPlaceholder')}
              inputProps={{ ...params.inputProps, 'aria-label': t('stepEdit.dependsAria') }}
            />
          )}
          sx={{ '& .MuiInputBase-input': { fontSize: '0.75rem' } }}
        />
      </DialogContent>
      <DialogActions sx={{ px: 2, py: 1 }}>
        <Button size="small" onClick={onClose} disabled={busy} sx={{ fontSize: '0.6875rem', textTransform: 'none' }}>
          {t('stepEdit.cancel')}
        </Button>
        <Button
          size="small"
          variant="contained"
          onClick={handleSave}
          disabled={busy}
          sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
        >
          {busy ? 'Saving…' : 'Save changes'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

StepEditDialog.propTypes = {
  open: PropTypes.bool,
  step: PropTypes.object,
  steps: PropTypes.array,
  busy: PropTypes.bool,
  onSave: PropTypes.func,
  onClose: PropTypes.func,
};
