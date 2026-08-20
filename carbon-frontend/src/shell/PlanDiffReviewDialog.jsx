// src/shell/PlanDiffReviewDialog.jsx
// W3-F — consent gate for plan edits (RULE_21): after an edit/replan returns
// diff {added, removed, changed}, this dialog summarizes the changes in
// OUTCOME terms (RULE_23 — never engine language) and asks the user to
// explicitly keep them. Nothing executes until the user re-approves the
// revised plan via the plan consent gate. Theme tokens only (RULE_8).
import React from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Stack,
  Typography,
} from '@mui/material';
import AddCircleOutlineIcon from '@mui/icons-material/AddCircleOutline';
import RemoveCircleOutlineIcon from '@mui/icons-material/RemoveCircleOutline';
import SwapHorizIcon from '@mui/icons-material/SwapHoriz';
import { summarizePlanDiff } from '../utils/planGraph';

/**
 * Diff-review consent gate.
 * @param {object} props
 * @param {boolean} props.open
 * @param {object} props.diff - { added, removed, changed } from PATCH plans/
 * @param {boolean} [props.busy] - a follow-up action is in flight
 * @param {function} [props.onConfirm] - user reviewed and keeps the changes
 * @param {function} [props.onCancel]
 */
export default function PlanDiffReviewDialog({ open, diff, busy, onConfirm, onCancel }) {
  const summary = summarizePlanDiff(diff);

  return (
    <Dialog open={open} onClose={busy ? undefined : onCancel} maxWidth="sm" fullWidth aria-label="Review plan changes">
      <DialogTitle sx={{ fontSize: '0.875rem', fontWeight: 700, py: 1.5 }}>Review plan changes</DialogTitle>
      <DialogContent dividers sx={{ pt: 1.25, pb: 1.25 }}>
        <Typography variant="body2" sx={{ fontSize: '0.75rem', mb: 1 }}>
          {summary.count > 0
            ? `The revised plan has ${summary.summary.toLowerCase()}`
            : 'The revised plan keeps the same steps.'}
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: '0.6875rem', mb: 1 }}>
          The plan needs your approval again before anything runs.
        </Typography>

        {summary.count > 0 && (
          <>
            <Divider sx={{ mb: 0.75 }} />
            <List dense disablePadding>
              {summary.added.map((intent) => (
                <ListItem key={`add-${intent}`} disableGutters sx={{ py: 0.25 }}>
                  <ListItemIcon sx={{ minWidth: 28 }}>
                    <AddCircleOutlineIcon sx={{ fontSize: 16, color: 'success.main' }} />
                  </ListItemIcon>
                  <ListItemText
                    primary={<Typography variant="body2" sx={{ fontSize: '0.75rem' }}>New step: {intent}</Typography>}
                  />
                </ListItem>
              ))}
              {summary.removed.map((intent) => (
                <ListItem key={`remove-${intent}`} disableGutters sx={{ py: 0.25 }}>
                  <ListItemIcon sx={{ minWidth: 28 }}>
                    <RemoveCircleOutlineIcon sx={{ fontSize: 16, color: 'error.main' }} />
                  </ListItemIcon>
                  <ListItemText
                    primary={<Typography variant="body2" sx={{ fontSize: '0.75rem' }}>Removed step: {intent}</Typography>}
                  />
                </ListItem>
              ))}
              {summary.changed.map((c, i) => (
                <ListItem key={`change-${i}-${c.to}`} disableGutters sx={{ py: 0.25 }}>
                  <ListItemIcon sx={{ minWidth: 28 }}>
                    <SwapHorizIcon sx={{ fontSize: 16, color: 'warning.main' }} />
                  </ListItemIcon>
                  <ListItemText
                    primary={
                      <Stack spacing={0}>
                        <Typography variant="body2" sx={{ fontSize: '0.75rem' }}>
                          Changed step: {c.from}
                        </Typography>
                        <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem' }}>
                          now: {c.to}
                        </Typography>
                      </Stack>
                    }
                  />
                </ListItem>
              ))}
            </List>
          </>
        )}

        <Box sx={{ mt: 1.5, p: 1, borderRadius: 1, bgcolor: 'action.hover' }}>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: '0.6875rem' }}>
            Changes apply only after you confirm. Nothing runs until you approve the revised plan.
          </Typography>
        </Box>
      </DialogContent>
      <DialogActions sx={{ px: 2, py: 1 }}>
        <Button size="small" onClick={onCancel} disabled={busy} sx={{ fontSize: '0.6875rem', textTransform: 'none' }}>
          Cancel
        </Button>
        <Button
          size="small"
          variant="contained"
          onClick={onConfirm}
          disabled={busy}
          sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
        >
          {busy ? 'Applying…' : 'Keep changes'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

PlanDiffReviewDialog.propTypes = {
  open: PropTypes.bool,
  diff: PropTypes.shape({
    added: PropTypes.array,
    removed: PropTypes.array,
    changed: PropTypes.array,
  }),
  busy: PropTypes.bool,
  onConfirm: PropTypes.func,
  onCancel: PropTypes.func,
};
