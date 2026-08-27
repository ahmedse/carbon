// src/components/ai/ScheduleList.jsx
// W6-E F-29 — the scheduled-runs list. Each row shows the SERVER-SUPPLIED
// `preview` (single source of truth, RULE_23), owner, enabled state, and
// edit / pause / delete actions. Delete names the consequence before
// confirming (RULE_21 — never silent destruction).
//
// Handles all four data states: loading, error, empty, and ready.
import React from 'react';
import PropTypes from 'prop-types';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  IconButton,
  List,
  ListItem,
  ListItemSecondaryAction,
  ListItemText,
  Paper,
  Stack,
  Tooltip,
  Typography,
} from '@mui/material';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import PauseIcon from '@mui/icons-material/Pause';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';

/**
 * @param {object} props
 * @param {Array} props.schedules
 * @param {boolean} props.loading
 * @param {string|null} props.error
 * @param {function} [props.onEdit] - (schedule) => void
 * @param {function} [props.onPause] - (schedule) => void
 * @param {function} [props.onDelete] - (schedule) => void
 */
export default function ScheduleList({ schedules, loading, error, onEdit, onPause, onDelete }) {
  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }} data-testid="schedules-loading">
        <CircularProgress size={22} />
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ fontSize: '0.6875rem', py: 0.5 }}>
        {error}
      </Alert>
    );
  }

  if (!schedules || schedules.length === 0) {
    return (
      <Box sx={{ py: 3, textAlign: 'center' }} data-testid="schedules-empty">
        <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem' }}>
          No scheduled runs yet. Choose a template and press “Schedule” to set one up.
        </Typography>
      </Box>
    );
  }

  return (
    <List disablePadding data-testid="schedules-list">
      {schedules.map((s) => (
        <Paper key={s.id} variant="outlined" sx={{ mb: 1 }}>
          <ListItem alignItems="flex-start" sx={{ py: 1 }}>
            <ListItemText
              primary={
                <Stack direction="row" spacing={1} alignItems="center">
                  <Typography component="span" variant="body2" sx={{ fontWeight: 600, fontSize: '0.75rem' }}>
                    {s.name || 'Untitled schedule'}
                  </Typography>
                  <Chip
                    size="small"
                    label={s.enabled ? 'Enabled' : 'Paused'}
                    color={s.enabled ? 'success' : 'default'}
                    variant="outlined"
                    sx={{ fontSize: '0.625rem', height: 18, '& .MuiChip-label': { px: 0.75 } }}
                  />
                </Stack>
              }
              secondary={
                <>
                  <Typography
                    component="span"
                    variant="caption"
                    sx={{ display: 'block', fontSize: '0.6875rem', color: 'text.primary' }}
                    data-testid={`schedule-preview-${s.id}`}
                  >
                    {s.preview || 'No preview available'}
                  </Typography>
                  <Typography component="span" variant="caption" color="text.secondary" sx={{ fontSize: '0.625rem' }}>
                    Owner: {s.owner || '—'}
                  </Typography>
                </>
              }
              sx={{ '& .MuiListItemText-secondary': { mt: 0.25 } }}
            />
            <ListItemSecondaryAction>
              <Stack direction="row" spacing={0.25}>
                <Tooltip title="Edit">
                  <span>
                    <IconButton size="small" onClick={() => onEdit?.(s)} aria-label={`Edit ${s.name}`}>
                      <EditOutlinedIcon sx={{ fontSize: '1rem' }} />
                    </IconButton>
                  </span>
                </Tooltip>
                <Tooltip title={s.enabled ? 'Pause' : 'Resume'}>
                  <span>
                    <IconButton size="small" onClick={() => onPause?.(s)} aria-label={s.enabled ? `Pause ${s.name}` : `Resume ${s.name}`}>
                      {s.enabled ? <PauseIcon sx={{ fontSize: '1rem' }} /> : <PlayArrowIcon sx={{ fontSize: '1rem' }} />}
                    </IconButton>
                  </span>
                </Tooltip>
                <Tooltip title="Delete">
                  <span>
                    <IconButton size="small" onClick={() => onDelete?.(s)} aria-label={`Delete ${s.name}`}>
                      <DeleteOutlineIcon sx={{ fontSize: '1rem' }} />
                    </IconButton>
                  </span>
                </Tooltip>
              </Stack>
            </ListItemSecondaryAction>
          </ListItem>
        </Paper>
      ))}
    </List>
  );
}

ScheduleList.propTypes = {
  schedules: PropTypes.array,
  loading: PropTypes.bool,
  error: PropTypes.string,
  onEdit: PropTypes.func,
  onPause: PropTypes.func,
  onDelete: PropTypes.func,
};
