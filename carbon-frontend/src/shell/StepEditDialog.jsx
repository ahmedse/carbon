// src/shell/StepEditDialog.jsx
// W3-F — per-step edit dialog for the AI Workspace plan card. Edits the
// outcome description (title), instructions and dependencies (depends_on).
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
  TextField,
  Typography,
} from '@mui/material';
import Autocomplete from '@mui/material/Autocomplete';
import Chip from '@mui/material/Chip';

/**
 * Step edit dialog.
 * @param {object} props
 * @param {boolean} props.open
 * @param {object|null} props.step - the step being edited
 * @param {Array} props.steps - all plan steps (dependency options)
 * @param {boolean} [props.busy]
 * @param {function} [props.onSave] - (fields: {title, instructions, depends_on}) => void
 * @param {function} [props.onClose]
 */
export default function StepEditDialog({ open, step, steps, busy, onSave, onClose }) {
  const [title, setTitle] = useState('');
  const [instructions, setInstructions] = useState('');
  const [dependsOn, setDependsOn] = useState([]);

  // Sync form state whenever a (new) step opens.
  useEffect(() => {
    if (!open || !step) return;
    setTitle(step.intent || '');
    setInstructions(step.instructions || '');
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
    });
  };

  return (
    <Dialog open={open} onClose={busy ? undefined : onClose} maxWidth="sm" fullWidth aria-label="Edit step">
      <DialogTitle sx={{ fontSize: '0.875rem', fontWeight: 700, py: 1.5 }}>Edit step</DialogTitle>
      <DialogContent dividers sx={{ pt: 1.25 }}>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: '0.6875rem', mb: 1 }}>
          Change what this step does. Saving opens a review of the changes — the plan needs your approval again before it runs.
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
              label="Runs after"
              placeholder="Choose steps that must finish first"
              inputProps={{ ...params.inputProps, 'aria-label': 'Depends on' }}
            />
          )}
          sx={{ '& .MuiInputBase-input': { fontSize: '0.75rem' } }}
        />
      </DialogContent>
      <DialogActions sx={{ px: 2, py: 1 }}>
        <Button size="small" onClick={onClose} disabled={busy} sx={{ fontSize: '0.6875rem', textTransform: 'none' }}>
          Cancel
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
