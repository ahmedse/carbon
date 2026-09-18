// src/pages/admin/ai/control/PolicyDryRunPanel.jsx
import React, { useState } from 'react';
import {
  Button,
  Chip,
  MenuItem,
  Paper,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import useDocumentTitle from '../../../../hooks/useDocumentTitle';
import PageContainer from '../../../../components/layout/PageContainer';
import { useAuth } from '../../../../auth/AuthContext';
import { useNotification } from '../../../../components/NotificationProvider';
import { pdpDryRun } from '../../../../api/aiControlPlane';

const AUTONOMY = [
  'observe',
  'propose',
  'act_confirm',
  'act_notify',
  'act_silent',
  'human_only',
];

export default function PolicyDryRunPanel() {
  useDocumentTitle('Policy Dry-Run');
  const { token } = useAuth();
  const { notify } = useNotification();
  const [action, setAction] = useState('call_host_api');
  const [autonomy, setAutonomy] = useState('human_only');
  const [objects, setObjects] = useState('');
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);

  const onRun = async () => {
    setBusy(true);
    try {
      const data = await pdpDryRun(token, {
        action: action.trim(),
        autonomy,
        objects: objects
          .split(',')
          .map((s) => s.trim())
          .filter(Boolean),
      });
      setResult(data);
    } catch (err) {
      setResult(null);
      notify({ message: err?.detail || err?.message || 'Dry-run failed', type: 'error' });
    } finally {
      setBusy(false);
    }
  };

  return (
    <PageContainer>
      <Stack spacing={2}>
        <Typography variant="h5" fontWeight={700}>
          Policy dry-run
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Simulate PDP without executing a host effect. Result is audited as dry_run.
        </Typography>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
          <TextField
            size="small"
            label="Action"
            value={action}
            onChange={(e) => setAction(e.target.value)}
            fullWidth
          />
          <TextField
            select
            size="small"
            label="Autonomy"
            value={autonomy}
            onChange={(e) => setAutonomy(e.target.value)}
            sx={{ minWidth: 180 }}
          >
            {AUTONOMY.map((a) => (
              <MenuItem key={a} value={a}>
                {a}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            size="small"
            label="Objects (comma-separated)"
            value={objects}
            onChange={(e) => setObjects(e.target.value)}
            fullWidth
          />
          <Button variant="contained" onClick={onRun} disabled={busy || !action.trim()}>
            Simulate
          </Button>
        </Stack>
        {result && (
          <Paper variant="outlined" sx={{ p: 2 }}>
            <Stack direction="row" spacing={1} alignItems="center">
              <Chip label={result.decision} color="primary" />
              <Typography variant="body2">{result.reason || '—'}</Typography>
            </Stack>
          </Paper>
        )}
      </Stack>
    </PageContainer>
  );
}
