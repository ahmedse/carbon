// src/shell/AgentTaskPicker.jsx
// Chat-first Agent remake — compact task Select at the top (replaces the fat
// left MY TASKS rail). Active tasks first; terminal statuses grouped under
// Done. Theme tokens only (RULE_8); outcome copy only (RULE_23).
import React, { useMemo } from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Chip,
  CircularProgress,
  FormControl,
  IconButton,
  InputLabel,
  ListSubheader,
  MenuItem,
  Select,
  Stack,
  Tooltip,
  Typography,
} from '@mui/material';
import DeleteOutlinedIcon from '@mui/icons-material/DeleteOutlined';
import { effectivePlanStatus, planStatusMeta } from './aiTaskStatus';

const ACTIVE = new Set(['discovering', 'pending_approval', 'approved', 'running', 'paused']);
const TERMINAL = new Set(['completed', 'failed', 'cancelled']);

function briefLabel(plan) {
  const raw = (plan?.brief || '').trim() || 'Untitled task';
  return raw.length > 72 ? `${raw.slice(0, 72)}…` : raw;
}

function AgentTaskPicker({
  plans,
  loading,
  selectedId,
  onSelect,
  onDelete,
  deletingId,
}) {
  const { active, done } = useMemo(() => {
    const a = [];
    const d = [];
    (plans || []).forEach((p) => {
      const st = effectivePlanStatus(p);
      if (ACTIVE.has(st)) a.push(p);
      else if (TERMINAL.has(st)) d.push(p);
      else a.push(p);
    });
    return { active: a, done: d };
  }, [plans]);

  const value = selectedId || '';

  return (
    <Stack direction="row" alignItems="center" spacing={1} sx={{ minWidth: 0 }}>
      <FormControl size="small" fullWidth sx={{ minWidth: 0 }}>
        <InputLabel id="agent-task-picker-label">Task</InputLabel>
        <Select
          labelId="agent-task-picker-label"
          label="Task"
          value={value}
          displayEmpty
          onChange={(e) => {
            const id = e.target.value;
            if (!id) {
              onSelect(null);
              return;
            }
            onSelect(id);
          }}
          renderValue={(v) => {
            if (!v) {
              return (
                <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.8125rem' }}>
                  {loading ? 'Loading tasks…' : 'New task / pick one'}
                </Typography>
              );
            }
            const plan = (plans || []).find((p) => p.id === v);
            if (!plan) return v;
            const meta = planStatusMeta(effectivePlanStatus(plan));
            return (
              <Stack direction="row" alignItems="center" spacing={0.75} sx={{ minWidth: 0 }}>
                <Typography
                  variant="body2"
                  sx={{
                    fontSize: '0.8125rem',
                    fontWeight: 500,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                    minWidth: 0,
                    flex: 1,
                  }}
                >
                  {briefLabel(plan)}
                </Typography>
                <Chip
                  size="small"
                  variant="outlined"
                  label={meta.label}
                  color={meta.color}
                  sx={{ height: 18, fontSize: '0.625rem', flexShrink: 0 }}
                />
              </Stack>
            );
          }}
          sx={{
            '& .MuiSelect-select': { py: 0.75, display: 'flex', alignItems: 'center' },
          }}
          MenuProps={{ PaperProps: { sx: { maxHeight: 360 } } }}
        >
          <MenuItem value="">
            <em>New task</em>
          </MenuItem>
          {loading && (
            <MenuItem disabled value="__loading">
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <CircularProgress size={14} />
                Loading…
              </Box>
            </MenuItem>
          )}
          {!loading && active.length === 0 && done.length === 0 && (
            <MenuItem disabled value="__empty">
              No tasks yet
            </MenuItem>
          )}
          {active.length > 0 && <ListSubheader>Active</ListSubheader>}
          {active.map((plan) => {
            const meta = planStatusMeta(effectivePlanStatus(plan));
            return (
              <MenuItem key={plan.id} value={plan.id} sx={{ maxWidth: 420 }}>
                <Stack direction="row" alignItems="center" spacing={1} sx={{ width: '100%', minWidth: 0 }}>
                  <Box sx={{ flex: 1, minWidth: 0 }}>
                    <Typography variant="body2" sx={{ fontSize: '0.75rem', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {briefLabel(plan)}
                    </Typography>
                  </Box>
                  <Chip size="small" variant="outlined" label={meta.label} color={meta.color} sx={{ height: 16, fontSize: '0.5625rem' }} />
                </Stack>
              </MenuItem>
            );
          })}
          {done.length > 0 && <ListSubheader>Done</ListSubheader>}
          {done.map((plan) => {
            const st = effectivePlanStatus(plan);
            const meta = planStatusMeta(st);
            const canDelete = TERMINAL.has(st);
            return (
              <MenuItem key={plan.id} value={plan.id} sx={{ maxWidth: 420 }}>
                <Stack direction="row" alignItems="center" spacing={0.5} sx={{ width: '100%', minWidth: 0 }}>
                  <Box sx={{ flex: 1, minWidth: 0 }}>
                    <Typography variant="body2" sx={{ fontSize: '0.75rem', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {briefLabel(plan)}
                    </Typography>
                  </Box>
                  <Chip size="small" variant="outlined" label={meta.label} color={meta.color} sx={{ height: 16, fontSize: '0.5625rem' }} />
                  {canDelete && onDelete && (
                    <Tooltip title="Delete task">
                      <IconButton
                        size="small"
                        aria-label="Delete task"
                        onClick={(e) => {
                          e.stopPropagation();
                          onDelete(plan.id);
                        }}
                        sx={{ p: 0.25 }}
                      >
                        <DeleteOutlinedIcon sx={{ fontSize: 14, color: deletingId === plan.id ? 'error.main' : 'text.disabled' }} />
                      </IconButton>
                    </Tooltip>
                  )}
                </Stack>
              </MenuItem>
            );
          })}
        </Select>
      </FormControl>
    </Stack>
  );
}

AgentTaskPicker.propTypes = {
  plans: PropTypes.arrayOf(PropTypes.object),
  loading: PropTypes.bool,
  selectedId: PropTypes.string,
  onSelect: PropTypes.func.isRequired,
  onDelete: PropTypes.func,
  deletingId: PropTypes.string,
};

export default AgentTaskPicker;
