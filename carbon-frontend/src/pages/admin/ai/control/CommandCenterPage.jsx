// src/pages/admin/ai/control/CommandCenterPage.jsx
// ADR-0036 Phase 2 — Command Center: health, queues, graduated containment.
import React, { useCallback, useEffect, useState } from 'react';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Link,
  MenuItem,
  Paper,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';
import CloudOffIcon from '@mui/icons-material/CloudOff';
import useDocumentTitle from '../../../../hooks/useDocumentTitle';
import PageContainer from '../../../../components/layout/PageContainer';
import { useAuth } from '../../../../auth/AuthContext';
import { useNotification } from '../../../../components/NotificationProvider';
import { getCommandCenter, setContainment } from '../../../../api/aiControlPlane';
import ControlHub from './ControlHub';
import AIExpertisePanel from '../AIExpertisePanel';
import MonitoringPanel from '../MonitoringPanel';

const LEVELS = [
  { value: 'normal', label: 'Normal' },
  { value: 'autonomy_clamp', label: 'Autonomy clamp' },
  { value: 'tool_freeze', label: 'Tool freeze' },
  { value: 'learning_freeze', label: 'Learning freeze' },
  { value: 'full_stop', label: 'Full stop (kill active)' },
];

function OverviewPanel() {
  useDocumentTitle('Command Center');
  const { token } = useAuth();
  const { notify } = useNotification();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);
  const [level, setLevel] = useState('normal');
  const [reason, setReason] = useState('');
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const payload = await getCommandCenter(token);
      setData(payload);
      setLevel(payload?.containment?.containment_level || 'normal');
      setOffline(false);
    } catch {
      setData(null);
      setOffline(true);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  const onContain = async () => {
    setSaving(true);
    try {
      await setContainment(token, { level, reason });
      notify({ message: 'Containment updated', type: 'success' });
      await load();
    } catch (err) {
      notify({ message: err?.detail || err?.message || 'Containment update failed', type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
        <CircularProgress size={24} />
      </Box>
    );
  }

  if (offline || !data) {
    return (
      <PageContainer>
        <Paper variant="outlined" sx={{ p: 4, textAlign: 'center' }}>
          <CloudOffIcon fontSize="large" sx={{ color: 'text.secondary' }} />
          <Typography variant="subtitle1" sx={{ mt: 1 }} fontWeight={600}>
            Command Center unavailable
          </Typography>
        </Paper>
      </PageContainer>
    );
  }

  const health = data.health || {};
  const queues = data.queues || {};
  const spend = data.spend || {};
  const caps = health.capabilities || {};

  return (
    <PageContainer>
      <Stack spacing={2}>
        <Stack direction="row" alignItems="center" spacing={1} flexWrap="wrap">
          <Typography variant="h5" fontWeight={700} sx={{ flex: 1 }}>
            Command Center
          </Typography>
          <Chip
            size="small"
            color={health.healthy ? 'success' : 'error'}
            label={health.healthy ? 'Healthy' : 'Degraded'}
          />
          <Chip
            size="small"
            variant="outlined"
            label={`Containment: ${data.containment?.containment_level || 'normal'}`}
          />
        </Stack>

        <Typography variant="overline" color="text.secondary">
          Queues
        </Typography>
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
          {[
            ['Inbox', queues.inbox_pending, data.links?.inbox],
            ['Review', queues.review_queue, data.links?.review],
            ['Failing runs', queues.failing_runs, data.links?.runs],
            ['Learning', queues.learning_candidates, data.links?.review],
          ].map(([label, count, href]) => (
            <Paper key={label} variant="outlined" sx={{ p: 1.5, minWidth: 140 }}>
              <Typography variant="caption" color="text.secondary">
                {label}
              </Typography>
              <Typography variant="h6" fontWeight={700}>
                {count ?? '—'}
              </Typography>
              {href && (
                <Link component={RouterLink} to={href} variant="caption">
                  Open
                </Link>
              )}
            </Paper>
          ))}
          <Paper variant="outlined" sx={{ p: 1.5, minWidth: 160 }}>
            <Typography variant="caption" color="text.secondary">
              Spend today
            </Typography>
            <Typography variant="h6" fontWeight={700}>
              ${Number(spend.spent_today_usd || 0).toFixed(2)}
              <Typography component="span" variant="caption" color="text.secondary">
                {' '}/ ${Number(spend.budget_usd || 0).toFixed(2)}
              </Typography>
            </Typography>
            {spend.budget_exceeded && (
              <Chip size="small" color="error" label="Budget exceeded" />
            )}
          </Paper>
        </Stack>

        <Typography variant="overline" color="text.secondary">
          Capabilities
        </Typography>
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
          {Object.entries(caps).map(([name, cap]) => (
            <Paper key={name} variant="outlined" sx={{ p: 1.5, minWidth: 140 }}>
              <Stack direction="row" justifyContent="space-between" alignItems="center">
                <Typography variant="body2" fontWeight={600}>
                  {name}
                </Typography>
                <Chip size="small" label={cap?.status || 'unknown'} />
              </Stack>
              {cap?.detail && (
                <Typography variant="caption" color="text.secondary">
                  {cap.detail}
                </Typography>
              )}
            </Paper>
          ))}
        </Stack>

        <Typography variant="overline" color="text.secondary">
          Graduated containment
        </Typography>
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Stack spacing={1.5} direction={{ xs: 'column', sm: 'row' }} alignItems="flex-start">
            <TextField
              select
              size="small"
              label="Level"
              value={level}
              onChange={(e) => setLevel(e.target.value)}
              sx={{ minWidth: 220 }}
            >
              {LEVELS.map((opt) => (
                <MenuItem key={opt.value} value={opt.value}>
                  {opt.label}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              size="small"
              label="Reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              fullWidth
            />
            <Button variant="contained" onClick={onContain} disabled={saving}>
              Apply
            </Button>
          </Stack>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
            Full stop enables kill_switch on all active processes. Changes are audited.
          </Typography>
        </Paper>
      </Stack>
    </PageContainer>
  );
}

export default function CommandCenterPage() {
  return (
    <ControlHub
      title="Command Center"
      defaultTab="overview"
      tabs={[
        { id: 'overview', label: 'Overview', element: <OverviewPanel /> },
        { id: 'expertise', label: 'Expertise', element: <AIExpertisePanel /> },
        { id: 'monitoring', label: 'Monitoring', element: <MonitoringPanel /> },
      ]}
    />
  );
}
