// carbon-frontend/src/pages/dq/tabs/OperationsTab.jsx
import React, { useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Paper,
  Stack,
  Typography,
} from '@mui/material';
import {
  Archive,
  ContentCopy,
  DeleteForever,
  PlayArrow,
  PowerSettingsNew,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../../auth/AuthContext';
import { useNotification } from '../../../components/NotificationProvider';
import { updateDQRule, deleteDQRule, createDQRule } from '../../../api/dq';

function OperationsTab({ rule, onChanged, onRun }) {
  const { token } = useAuth();
  const { notify, notifyFromError } = useNotification();
  const navigate = useNavigate();
  const [busy, setBusy] = useState('');
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [confirmArchive, setConfirmArchive] = useState(false);

  const hasResults = Number(rule?.results_count) > 0;

  const handleToggleActive = async () => {
    setBusy('toggle');
    try {
      await updateDQRule(token, rule.id, { is_active: !rule.is_active });
      notify({ message: `Rule ${rule.is_active ? 'deactivated' : 'activated'}`, type: 'success' });
      onChanged?.();
    } catch (err) {
      notifyFromError(err, 'Could not update rule');
    } finally {
      setBusy('');
    }
  };

  const handleDuplicate = async () => {
    setBusy('duplicate');
    try {
      const newRule = await createDQRule(token, {
        definition: { ...(rule.definition || {}), name: `${rule.name} (copy)` },
        field_assignments_write: (rule.field_assignments || []).map((a) => ({
          data_table: a.data_table,
          data_field: a.data_field,
        })),
        tag_ids: (rule.tags || []).map((t) => t.id),
      });
      notify({ message: `Duplicated as "${newRule.name}"`, type: 'success' });
      navigate(`/dq/rules/${newRule.id}`, { replace: true });
      onChanged?.();
    } catch (err) {
      notifyFromError(err, 'Could not duplicate rule');
    } finally {
      setBusy('');
    }
  };

  const handleArchive = async () => {
    setBusy('archive');
    try {
      await deleteDQRule(rule.id);
      notify({ message: `Rule "${rule.name}" archived`, type: 'success' });
      setConfirmArchive(false);
      navigate('/dq', { replace: true });
    } catch (err) {
      notifyFromError(err, 'Could not archive rule');
    } finally {
      setBusy('');
    }
  };

  const handleDelete = async () => {
    setBusy('delete');
    try {
      await deleteDQRule(rule.id);
      notify({ message: `Rule "${rule.name}" deleted`, type: 'success' });
      setConfirmDelete(false);
      navigate('/dq', { replace: true });
    } catch (err) {
      notifyFromError(err, 'Could not delete rule');
    } finally {
      setBusy('');
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      {rule?.archived ? (
        <Alert severity="warning" sx={{ mb: 2 }}>
          This rule is archived. Restore it before running or editing.
        </Alert>
      ) : null}

      <Stack spacing={1.5}>
        <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
          <Typography sx={{ fontSize: '0.875rem', fontWeight: 700, mb: 1 }}>Run</Typography>
          <Stack direction="row" spacing={1} flexWrap="wrap">
            <Button
              variant="contained"
              size="small"
              startIcon={<PlayArrow />}
              disabled={busy === 'run' || rule?.archived || !rule?.is_active}
              onClick={() => onRun?.(rule)}
            >
              Run now
            </Button>
            <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary', alignSelf: 'center' }}>
              Creates a followable job — track it on the Jobs tab of the workspace.
            </Typography>
          </Stack>
        </Paper>

        <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
          <Typography sx={{ fontSize: '0.875rem', fontWeight: 700, mb: 1 }}>State</Typography>
          <Stack direction="row" spacing={1} flexWrap="wrap" alignItems="center">
            <Button
              variant="outlined"
              size="small"
              startIcon={<PowerSettingsNew />}
              disabled={busy === 'toggle' || rule?.archived}
              onClick={handleToggleActive}
            >
              {rule?.is_active ? 'Deactivate' : 'Activate'}
            </Button>
            <Chip
              size="small"
              color={rule?.is_active ? 'success' : 'default'}
              label={rule?.is_active ? 'Active' : 'Inactive'}
            />
          </Stack>
        </Paper>

        <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
          <Typography sx={{ fontSize: '0.875rem', fontWeight: 700, mb: 1 }}>Versioning</Typography>
          <Stack direction="row" spacing={1} flexWrap="wrap">
            <Button
              variant="outlined"
              size="small"
              startIcon={<ContentCopy />}
              disabled={busy === 'duplicate'}
              onClick={handleDuplicate}
            >
              Duplicate rule
            </Button>
            <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary', alignSelf: 'center' }}>
              Current version: {rule?.version ?? 1} — every definition save creates a new version.
            </Typography>
          </Stack>
        </Paper>

        <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
          <Typography sx={{ fontSize: '0.875rem', fontWeight: 700, mb: 1 }}>Delete</Typography>
          <Stack direction="row" spacing={1} flexWrap="wrap" alignItems="center">
            {hasResults ? (
              <>
                <Button
                  variant="outlined"
                  color="error"
                  size="small"
                  startIcon={<Archive />}
                  disabled={busy === 'archive'}
                  onClick={() => setConfirmArchive(true)}
                >
                  Archive rule
                </Button>
                <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary' }}>
                  {rule?.results_count} result(s) exist — deleting archives instead of hard-deleting.
                </Typography>
              </>
            ) : (
              <>
                <Button
                  variant="outlined"
                  color="error"
                  size="small"
                  startIcon={<DeleteForever />}
                  disabled={busy === 'delete'}
                  onClick={() => setConfirmDelete(true)}
                >
                  Delete rule
                </Button>
                <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary' }}>
                  No results exist — this permanently removes the rule.
                </Typography>
              </>
            )}
          </Stack>
        </Paper>
      </Stack>

      <Dialog open={confirmDelete} onClose={() => setConfirmDelete(false)} fullWidth maxWidth="sm">
        <DialogTitle>Delete rule?</DialogTitle>
        <DialogContent>
          <Typography sx={{ fontSize: '0.875rem' }}>
            This permanently removes <strong>{rule?.name}</strong>. This cannot be undone.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmDelete(false)}>Cancel</Button>
          <Button variant="contained" color="error" startIcon={<DeleteForever />} onClick={handleDelete}>
            Delete permanently
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={confirmArchive} onClose={() => setConfirmArchive(false)} fullWidth maxWidth="sm">
        <DialogTitle>Archive rule?</DialogTitle>
        <DialogContent>
          <Typography sx={{ fontSize: '0.875rem' }}>
            Archives <strong>{rule?.name}</strong> — it keeps its {rule?.results_count} result(s) but is
            deactivated and hidden from the active rules list. You can unarchive later.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmArchive(false)}>Cancel</Button>
          <Button variant="contained" color="error" startIcon={<Archive />} onClick={handleArchive}>
            Archive
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

OperationsTab.propTypes = {
  rule: PropTypes.object,
  onChanged: PropTypes.func,
  onRun: PropTypes.func,
};

export default OperationsTab;
