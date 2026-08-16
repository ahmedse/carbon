// src/shell/InvestigateTab.jsx
// Phase 9-B — list view of "Investigate" conversations. Each row shows the
// conversation title, a status chip (running / completed / review / failed),
// and the relative time of the last activity. Clicking a row opens its thread;
// "New investigation" creates a bare investigate conversation (the real
// one-click trigger lives on the table detail page via AITaskTransferContext).

import React from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Button,
  Chip,
  Paper,
  Stack,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import { formatDistanceToNow } from '../utils/dateUtils';

const STATUS_META = {
  completed: { label: 'Completed', color: 'success' },
  needs_input: { label: 'Review', color: 'warning' },
  working: { label: 'Running', color: 'primary' },
  failed: { label: 'Failed', color: 'error' },
};

const DEFAULT_STATUS_META = { label: 'Queued', color: 'default' };

function lastActivityAt(conversation) {
  const iso = conversation?.last_message_at || conversation?.updated_at || conversation?.created_at;
  if (!iso) return null;
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? null : date;
}

export default function InvestigateTab({ conversations, onSelect, onNew }) {
  const list = Array.isArray(conversations) ? conversations : [];

  return (
    <Box sx={{ flex: 1, overflowY: 'auto', p: 1.5 }}>
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 1 }}>
        <Typography variant="subtitle2">Investigations</Typography>
        <Button size="small" variant="outlined" startIcon={<AddIcon fontSize="small" />} onClick={onNew}>
          New investigation
        </Button>
      </Stack>

      {list.length === 0 ? (
        <Box sx={{ py: 4, textAlign: 'center' }}>
          <Typography variant="caption" color="text.disabled">
            No investigations yet. Open a table and choose “Investigate” to run an
            automated data-quality review.
          </Typography>
        </Box>
      ) : (
        <Stack spacing={1}>
          {list.map((conversation) => {
            const status = STATUS_META[conversation.status] || DEFAULT_STATUS_META;
            const activity = lastActivityAt(conversation);
            return (
              <Paper
                key={conversation.id}
                variant="outlined"
                component="button"
                type="button"
                onClick={() => onSelect?.(conversation.id)}
                sx={{
                  width: '100%',
                  textAlign: 'left',
                  p: 1.25,
                  cursor: 'pointer',
                  bgcolor: 'background.paper',
                  '&:hover': { borderColor: 'primary.main' },
                }}
              >
                <Stack direction="row" alignItems="center" justifyContent="space-between" spacing={1}>
                  <Box sx={{ minWidth: 0 }}>
                    <Typography variant="body2" sx={{ fontWeight: 600 }} noWrap>
                      {conversation.title || 'Investigation'}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {activity ? `Updated ${formatDistanceToNow(activity)}` : 'No activity yet'}
                    </Typography>
                  </Box>
                  <Chip size="small" color={status.color} label={status.label} />
                </Stack>
              </Paper>
            );
          })}
        </Stack>
      )}
    </Box>
  );
}

InvestigateTab.propTypes = {
  conversations: PropTypes.arrayOf(PropTypes.object),
  onSelect: PropTypes.func,
  onNew: PropTypes.func,
};
