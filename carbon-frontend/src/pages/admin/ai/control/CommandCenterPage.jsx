// src/pages/admin/ai/control/CommandCenterPage.jsx
// ADR-0036 Phase 2 — Command Center: health, queues, graduated containment.
import React, { useCallback, useEffect, useMemo, useState } from 'react';
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
import { useTranslation } from 'react-i18next';
import { shellLabel } from '../../../../i18n/shellLabels';
import useDocumentTitle from '../../../../hooks/useDocumentTitle';
import PageContainer from '../../../../components/layout/PageContainer';
import { useAuth } from '../../../../auth/AuthContext';
import { useNotification } from '../../../../components/NotificationProvider';
import { getCommandCenter, setContainment } from '../../../../api/aiControlPlane';
import ControlHub from './ControlHub';
import AIExpertisePanel from '../AIExpertisePanel';
import MonitoringPanel from '../MonitoringPanel';

const LEVEL_VALUES = ['normal', 'autonomy_clamp', 'tool_freeze', 'learning_freeze', 'full_stop'];

function OverviewPanel() {
  const { t } = useTranslation('ai');
  useDocumentTitle(t('control.commandCenter.title'));
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
      notify({ message: t('control.commandCenter.updated'), type: 'success' });
      await load();
    } catch (err) {
      notify({
        message: err?.detail || err?.message || t('control.commandCenter.updateFailed'),
        type: 'error',
      });
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
            {t('control.commandCenter.unavailable')}
          </Typography>
        </Paper>
      </PageContainer>
    );
  }

  const health = data.health || {};
  const queues = data.queues || {};
  const spend = data.spend || {};
  const caps = health.capabilities || {};
  const containmentLevel = data.containment?.containment_level || 'normal';

  const queueCards = [
    [t('control.commandCenter.queueInbox'), queues.inbox_pending, data.links?.inbox],
    [t('control.commandCenter.queueReview'), queues.review_queue, data.links?.review],
    [t('control.commandCenter.queueFailingRuns'), queues.failing_runs, data.links?.runs],
    [t('control.commandCenter.queueLearning'), queues.learning_candidates, data.links?.review],
  ];

  return (
    <PageContainer>
      <Stack spacing={2}>
        <Stack direction="row" alignItems="center" spacing={1} flexWrap="wrap">
          <Typography variant="h5" fontWeight={700} sx={{ flex: 1 }}>
            {t('control.commandCenter.title')}
          </Typography>
          <Chip
            size="small"
            color={health.healthy ? 'success' : 'error'}
            label={health.healthy ? t('control.commandCenter.healthy') : t('control.commandCenter.degraded')}
          />
          <Chip
            size="small"
            variant="outlined"
            label={t('control.commandCenter.containmentChip', { level: containmentLevel })}
          />
        </Stack>

        <Typography variant="overline" color="text.secondary">
          {t('control.commandCenter.queues')}
        </Typography>
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
          {queueCards.map(([label, count, href]) => (
            <Paper key={label} variant="outlined" sx={{ p: 1.5, minWidth: 140 }}>
              <Typography variant="caption" color="text.secondary">
                {label}
              </Typography>
              <Typography variant="h6" fontWeight={700}>
                {count ?? '—'}
              </Typography>
              {href && (
                <Link component={RouterLink} to={href} variant="caption">
                  {t('control.commandCenter.open')}
                </Link>
              )}
            </Paper>
          ))}
          <Paper variant="outlined" sx={{ p: 1.5, minWidth: 160 }}>
            <Typography variant="caption" color="text.secondary">
              {t('control.commandCenter.spendToday')}
            </Typography>
            <Typography variant="h6" fontWeight={700}>
              ${Number(spend.spent_today_usd || 0).toFixed(2)}
              <Typography component="span" variant="caption" color="text.secondary">
                {' '}/ ${Number(spend.budget_usd || 0).toFixed(2)}
              </Typography>
            </Typography>
            {spend.budget_exceeded && (
              <Chip size="small" color="error" label={t('control.commandCenter.budgetExceeded')} />
            )}
          </Paper>
        </Stack>

        <Typography variant="overline" color="text.secondary">
          {t('control.commandCenter.capabilities')}
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
          {t('control.commandCenter.containment')}
        </Typography>
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Stack spacing={1.5} direction={{ xs: 'column', sm: 'row' }} alignItems="flex-start">
            <TextField
              select
              size="small"
              label={t('control.commandCenter.level')}
              value={level}
              onChange={(e) => setLevel(e.target.value)}
              sx={{ minWidth: 220 }}
            >
              {LEVEL_VALUES.map((value) => (
                <MenuItem key={value} value={value}>
                  {t(`control.commandCenter.levels.${value}`)}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              size="small"
              label={t('control.commandCenter.reason')}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              fullWidth
            />
            <Button variant="contained" onClick={onContain} disabled={saving}>
              {t('control.commandCenter.apply')}
            </Button>
          </Stack>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
            {t('control.commandCenter.containmentHint')}
          </Typography>
        </Paper>
      </Stack>
    </PageContainer>
  );
}

export default function CommandCenterPage() {
  const { t: ts } = useTranslation('shell');
  const label = (english) => shellLabel(ts, english);
  const tabs = useMemo(
    () => [
      { id: 'overview', label: label('Overview'), element: <OverviewPanel /> },
      { id: 'expertise', label: label('Expertise'), element: <AIExpertisePanel /> },
      { id: 'monitoring', label: label('Monitoring'), element: <MonitoringPanel /> },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [ts],
  );
  return (
    <ControlHub
      title={label('Command Center')}
      defaultTab="overview"
      tabs={tabs}
    />
  );
}
