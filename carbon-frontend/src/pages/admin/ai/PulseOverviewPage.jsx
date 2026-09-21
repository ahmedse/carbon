// src/pages/admin/ai/PulseOverviewPage.jsx
// Pulse console overview — provider health + task envelope status.
// Graceful degrade: the /ai/pulse/health/ endpoint lands in backend Phase 2b,
// so on 404/error we render an offline empty state instead of inventing data.
// RULE_8 tokens only; RULE_10 apiFetch only.
import React, { useEffect, useState } from 'react';
import { Box, Chip, CircularProgress, Paper, Stack, Typography } from '@mui/material';
import CloudOffIcon from '@mui/icons-material/CloudOff';
import MonitorHeartIcon from '@mui/icons-material/MonitorHeart';
import { useTranslation } from 'react-i18next';
import useDocumentTitle from '../../../hooks/useDocumentTitle';
import PageContainer from '../../../components/layout/PageContainer';
import { useAuth } from '../../../auth/AuthContext';
import { apiFetch } from '../../../api/api';

// Per-capability status → MUI chip color (P1-14). Unknown states fall back
// to the neutral default chip so a new backend state never breaks the UI.
const CAPABILITY_STATUS_COLORS = {
  healthy: 'success',
  configured: 'primary',
  degraded: 'warning',
  disabled: 'default',
  unavailable: 'error',
};

const CAPABILITY_LABEL_KEYS = {
  store: 'control.overview.capStore',
  reason_lane: 'control.overview.capReasonLane',
  verify: 'control.overview.capVerify',
  mcp: 'control.overview.capMcp',
  sandbox: 'control.overview.capSandbox',
};

/** One capability: name + status chip + detail line. */
function CapabilityCard({ name, cap }) {
  const { t } = useTranslation('ai');
  const status = cap?.status || 'unavailable';
  return (
    <Paper variant="outlined" sx={{ p: 1.5 }}>
      <Stack direction="row" alignItems="center" justifyContent="space-between" spacing={1}>
        <Typography variant="body2" sx={{ fontWeight: 600 }}>
          {CAPABILITY_LABEL_KEYS[name] ? t(CAPABILITY_LABEL_KEYS[name]) : name}
        </Typography>
        <Chip
          size="small"
          color={CAPABILITY_STATUS_COLORS[status] || 'default'}
          label={status}
        />
      </Stack>
      {cap?.detail && (
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
          {cap.detail}
        </Typography>
      )}
    </Paper>
  );
}

export default function PulseOverviewPage() {
  const { t } = useTranslation('ai');
  useDocumentTitle(t('control.overview.title'));
  const { token } = useAuth();

  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const data = await apiFetch('ai/pulse/health/', { token });
        if (!cancelled) {
          setHealth(data);
          setOffline(false);
        }
      } catch {
        if (!cancelled) {
          setHealth(null);
          setOffline(true);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  return (
    <PageContainer>
      <Stack spacing={1} sx={{ flex: 1, minHeight: 0 }}>
        <Typography variant="h5" fontWeight={700}>{t('control.overview.title')}</Typography>
        <Typography variant="body2" color="text.secondary">
          {t('control.overview.subtitle')}
        </Typography>

        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
            <CircularProgress size={24} />
          </Box>
        ) : offline || !health ? (
          <Paper variant="outlined" sx={{ p: 4, textAlign: 'center' }}>
            <CloudOffIcon fontSize="large" sx={{ color: 'text.secondary' }} />
            <Typography variant="subtitle1" sx={{ mt: 1 }} fontWeight={600}>
              {t('control.overview.offlineTitle')}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              {t('control.overview.offlineBody')}
            </Typography>
          </Paper>
        ) : (
          <Paper variant="outlined" sx={{ p: 2 }}>
            <Stack spacing={2}>
              <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
                <MonitorHeartIcon color="primary" />
                <Typography variant="h6" fontWeight={600}>{health.name || 'Pulse'}</Typography>
                {health.version && (
                  <Chip size="small" variant="outlined" label={`v${health.version}`} />
                )}
                <Chip
                  size="small"
                  color={health.healthy ? 'success' : 'error'}
                  label={health.healthy ? t('control.overview.healthy') : t('control.overview.unhealthy')}
                />
              </Stack>

              {Array.isArray(health.modules) && health.modules.length > 0 && (
                <Stack spacing={0.5}>
                  <Typography variant="overline" color="text.secondary">
                    {t('control.overview.modules')}
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                    {health.modules.map((m) => (
                      <Chip key={m} size="small" variant="outlined" label={m} />
                    ))}
                  </Box>
                </Stack>
              )}

              {health.capabilities && (
                <Stack spacing={1}>
                  <Typography variant="overline" color="text.secondary">
                    {t('control.overview.capabilities')}
                  </Typography>
                  <Box
                    sx={{
                      display: 'grid',
                      gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' },
                      gap: 1,
                    }}
                  >
                    {Object.entries(health.capabilities).map(([name, cap]) => (
                      <CapabilityCard key={name} name={name} cap={cap} />
                    ))}
                  </Box>
                </Stack>
              )}
            </Stack>
          </Paper>
        )}
      </Stack>
    </PageContainer>
  );
}
