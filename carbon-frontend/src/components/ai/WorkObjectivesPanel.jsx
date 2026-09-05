// src/components/ai/WorkObjectivesPanel.jsx
// Pulse v2 Phase 8 — shows the user's saved work objectives so they can
// resume an investigation. Click an objective to load its context; click the
// check to mark it complete.
import React, { useEffect, useState, useCallback } from 'react';
import {
  Box, Typography, List, ListItem, ListItemText,
  Chip, IconButton, Tooltip, CircularProgress,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import { getWorkObjectives, updateObjectiveStatus } from '../../api/aiWorkspace';

const STATUS_COLOR = {
  open: 'warning',
  in_progress: 'info',
  waiting_for_user: 'secondary',
  completed: 'success',
  cancelled: 'default',
};

export default function WorkObjectivesPanel({ onSelectObjective }) {
  const [objectives, setObjectives] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getWorkObjectives({ statusFilter: 'open' });
      setObjectives(Array.isArray(data) ? data : (data?.results ?? []));
    } catch {
      setError('Could not load objectives');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleComplete = async (id, e) => {
    e.stopPropagation();
    try {
      await updateObjectiveStatus(id, 'completed');
      setObjectives(prev => prev.filter(o => o.id !== id));
    } catch {
      /* silently swallow — user can refresh */
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
        <CircularProgress size={24} />
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', px: 1, pb: 1 }}>
        <Typography variant="caption" color="text.secondary" fontWeight={600}>
          SAVED OBJECTIVES
        </Typography>
        <Tooltip title="Refresh">
          <IconButton size="small" onClick={load} aria-label="Refresh objectives">
            <RefreshIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </Box>

      {error && (
        <Typography variant="caption" color="error" sx={{ px: 1 }}>
          {error}
        </Typography>
      )}

      {!loading && objectives.length === 0 && (
        <Typography variant="caption" color="text.secondary" sx={{ px: 1 }}>
          No saved objectives. Tell Pulse to &quot;save this investigation&quot; to create one.
        </Typography>
      )}

      <List dense disablePadding>
        {objectives.map(obj => (
          <ListItem
            key={obj.id}
            button
            onClick={() => onSelectObjective?.(obj)}
            secondaryAction={
              <Tooltip title="Mark complete">
                <IconButton
                  edge="end"
                  size="small"
                  aria-label="Mark complete"
                  onClick={(e) => handleComplete(obj.id, e)}
                >
                  <CheckCircleOutlineIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            }
            sx={{ py: 0.75, px: 1, borderRadius: 1, '&:hover': { bgcolor: 'action.hover' } }}
          >
            <ListItemText
              primary={
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  <Typography variant="body2" fontWeight={500} noWrap sx={{ flex: 1 }}>
                    {obj.title}
                  </Typography>
                  <Chip
                    label={(obj.status || '').replace('_', ' ')}
                    size="small"
                    color={STATUS_COLOR[obj.status] || 'default'}
                    sx={{ height: 18, fontSize: '0.65rem' }}
                  />
                </Box>
              }
              secondary={
                obj.latest_summary
                  ? <Typography variant="caption" color="text.secondary" noWrap>
                      {obj.latest_summary.slice(0, 80)}
                    </Typography>
                  : null
              }
            />
          </ListItem>
        ))}
      </List>
    </Box>
  );
}
