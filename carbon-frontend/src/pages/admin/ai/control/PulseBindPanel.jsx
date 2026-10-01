// Platform → Pulse: pack health, Pulse on/off, per-app jail (ADR-0036 tab).
// No brand picker. No seventh sidebar. Writes require ai:manage_console.
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Button,
  Chip,
  CircularProgress,
  FormControlLabel,
  Paper,
  Stack,
  Switch,
  Typography,
} from '@mui/material';
import { useTranslation } from 'react-i18next';
import useDocumentTitle from '../../../../hooks/useDocumentTitle';
import PageContainer from '../../../../components/layout/PageContainer';
import { useAuth } from '../../../../auth/AuthContext';
import { useNotification } from '../../../../components/NotificationProvider';
import { AI_MANAGE_CONSOLE, AI_VIEW_CONSOLE, expandCapabilities, hasCap } from '../../../../capabilities';
import { getPulseBind, patchPulseBind } from '../../../../api/aiControlPlane';

function capabilityKeys(caps) {
  return (caps || []).map((c) => (typeof c === 'string' ? c : c?.key || c?.capability));
}

export default function PulseBindPanel() {
  const { t } = useTranslation('ai');
  useDocumentTitle(t('control.platform.pulseTitle'));
  const { token, userCapabilities } = useAuth();
  const { notify } = useNotification();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [pulseOn, setPulseOn] = useState(true);
  const [apps, setApps] = useState({});
  const [extraApps, setExtraApps] = useState({});

  const caps = useMemo(
    () => expandCapabilities(capabilityKeys(userCapabilities)),
    [userCapabilities],
  );
  const canView = hasCap(caps, AI_VIEW_CONSOLE);
  const canManage = hasCap(caps, AI_MANAGE_CONSOLE);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const body = await getPulseBind(token);
      setData(body);
      setPulseOn(Boolean(body?.pulse_enabled));
      const next = {};
      (body?.apps || []).forEach((row) => {
        next[row.slug] = Boolean(row.pulse_enabled);
      });
      setApps(next);
      const nextExtra = {};
      (body?.extra_pack_apps || []).forEach((group) => {
        if (!group?.pack) return;
        nextExtra[group.pack] = {};
        (group.apps || []).forEach((row) => {
          nextExtra[group.pack][row.slug] = Boolean(row.pulse_enabled);
        });
      });
      setExtraApps(nextExtra);
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  const onSave = async () => {
    if (!canManage) return;
    setSaving(true);
    try {
      const body = await patchPulseBind(token, {
        pulse_enabled: pulseOn,
        apps,
        extra_apps: extraApps,
      });
      setData(body);
      setPulseOn(Boolean(body?.pulse_enabled));
      notify({ message: t('control.platform.pulseSaved'), type: 'success' });
      await load();
    } catch (err) {
      notify({
        message: err?.detail || err?.message || t('control.platform.saveFailed'),
        type: 'error',
      });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <PageContainer>
        <CircularProgress size={24} />
      </PageContainer>
    );
  }

  if (!data) {
    return (
      <PageContainer>
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Typography color="text.secondary">{t('control.platform.pulseUnavailable')}</Typography>
        </Paper>
      </PageContainer>
    );
  }

  const health = data.health || {};
  const mismatch = health.files_match_process === false;

  return (
    <PageContainer>
      <Stack spacing={2}>
        <Typography variant="h5" fontWeight={700}>
          {t('control.platform.pulseTitle')}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {t('control.platform.pulseHint')}
        </Typography>
        {mismatch ? (
          <Alert severity="warning">
            {t('control.platform.pulseMismatch', {
              files: health.files_brand,
              process: health.process_brand,
            })}
          </Alert>
        ) : null}
        {!canManage && canView ? (
          <Alert severity="info">{t('control.platform.pulseReadOnly')}</Alert>
        ) : null}
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Stack spacing={1.5}>
            <Typography variant="overline" color="text.secondary">
              {t('control.platform.pulseHealth')}
            </Typography>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              <Chip size="small" label={`${t('control.platform.pulseBrand')}: ${health.process_brand || '—'}`} />
              <Chip size="small" label={`${t('control.platform.pulsePack')}: ${health.pack || '—'}`} />
              <Chip
                size="small"
                label={`${t('control.platform.pulseVersion')}: ${health.pack_version ?? '—'}`}
              />
              <Chip
                size="small"
                color={health.pack_present ? 'success' : 'error'}
                label={
                  health.pack_present
                    ? t('control.platform.pulsePackPresent')
                    : t('control.platform.pulsePackMissing')
                }
              />
              <Chip
                size="small"
                label={`${t('control.platform.pulseRedis')}: ${health.redis_memory_db ?? '—'}`}
              />
              <Chip
                size="small"
                label={`${t('control.platform.pulseJwt')}: ${health.jwt_instance || '—'}`}
              />
              {(health.extra_packs || []).map((pack) => (
                <Chip
                  key={pack}
                  size="small"
                  label={`${t('control.platform.pulseExtraPack')}: ${pack}`}
                />
              ))}
            </Stack>
          </Stack>
        </Paper>
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Stack spacing={1.5}>
            <FormControlLabel
              control={
                <Switch
                  checked={pulseOn}
                  onChange={(e) => setPulseOn(e.target.checked)}
                  disabled={!canManage || mismatch}
                />
              }
              label={t('control.platform.pulseEnabled')}
            />
            <Typography variant="overline" color="text.secondary">
              {t('control.platform.pulseApps')}
            </Typography>
            {(data.apps || []).map((row) => (
              <FormControlLabel
                key={row.slug}
                control={
                  <Switch
                    checked={Boolean(apps[row.slug])}
                    onChange={(e) =>
                      setApps((prev) => ({ ...prev, [row.slug]: e.target.checked }))
                    }
                    disabled={!canManage || mismatch}
                  />
                }
                label={row.slug}
              />
            ))}
            {(data.extra_pack_apps || []).map((group) => (
              <Stack key={group.pack} spacing={1} sx={{ pt: 1 }}>
                <Typography variant="overline" color="text.secondary">
                  {t('control.platform.pulseExtraPackApps', {
                    pack: group.pack,
                    processPack: health.pack,
                  })}
                </Typography>
                {(group.apps || []).map((row) => (
                  <FormControlLabel
                    key={`${group.pack}:${row.slug}`}
                    control={
                      <Switch
                        checked={Boolean(extraApps[group.pack]?.[row.slug])}
                        onChange={(e) =>
                          setExtraApps((prev) => ({
                            ...prev,
                            [group.pack]: {
                              ...(prev[group.pack] || {}),
                              [row.slug]: e.target.checked,
                            },
                          }))
                        }
                        disabled={!canManage || mismatch}
                      />
                    }
                    label={row.slug}
                  />
                ))}
              </Stack>
            ))}
            <Stack direction="row" spacing={1}>
              <Button variant="contained" onClick={onSave} disabled={!canManage || saving || mismatch}>
                {t('control.platform.save')}
              </Button>
            </Stack>
          </Stack>
        </Paper>
      </Stack>
    </PageContainer>
  );
}

PulseBindPanel.displayName = 'PulseBindPanel';
