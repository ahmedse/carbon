// src/pages/admin/ai/PulseArchetypesPanel.jsx
// Lists the vendored engine's declarative archetype bundles (filesystem
// read-only, via /ai/pulse/archetypes/). Never fabricated: loading spinner,
// offline paper, grounded empty state, then the real bundle list.
// RULE_8 tokens only; RULE_10 apiFetch only (via src/api/aiPulse.js); RULE_16.
import React, { useEffect, useMemo, useState } from 'react';
import { Box, Chip, CircularProgress, Paper, Stack, Typography } from '@mui/material';
import CloudOffIcon from '@mui/icons-material/CloudOff';
import useDocumentTitle from '../../../hooks/useDocumentTitle';
import { useTranslation } from 'react-i18next';
import PageContainer from '../../../components/layout/PageContainer';
import CarbonDataGrid from '../../../components/DataGrid/CarbonDataGrid';
import { useAuth } from '../../../auth/AuthContext';
import { getPulseArchetypes } from '../../../api/aiPulse';

export default function PulseArchetypesPanel() {
  const { t } = useTranslation('ai');
  useDocumentTitle(t('control.pulseArchetypes.title'));
  const { token } = useAuth();

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const payload = await getPulseArchetypes(token);
        if (!cancelled) {
          setData(payload);
          setOffline(false);
        }
      } catch {
        if (!cancelled) {
          setData(null);
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

  const bundles = data?.bundles ?? [];
  const columns = useMemo(
    () => [
      { field: 'name', headerName: 'Bundle', minWidth: 240, flex: 1 },
      { field: 'kind', headerName: 'Kind', width: 140 },
    ],
    []
  );

  return (
    <PageContainer>
      <Stack spacing={1} sx={{ flex: 1, minHeight: 0 }}>
        <Stack direction="row" spacing={1} alignItems="center">
          <Typography variant="h5" fontWeight={700} sx={{ flex: 1 }}>{t('control.pulseArchetypes.title')}</Typography>
          {data && !offline && (
            <Chip size="small" variant="outlined" label={t('control.pulseArchetypes.bundlesCount', { count: bundles.length })} />
          )}
        </Stack>
        <Typography variant="body2" color="text.secondary">
          {t('control.pulseArchetypes.subtitle')}
        </Typography>

        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
            <CircularProgress size={24} />
          </Box>
        ) : offline || !data ? (
          <Paper variant="outlined" sx={{ p: 4, textAlign: 'center' }}>
            <CloudOffIcon fontSize="large" sx={{ color: 'text.secondary' }} />
            <Typography variant="subtitle1" sx={{ mt: 1 }} fontWeight={600}>
              {t('control.pulseArchetypes.dataUnavailable')}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              {t('control.pulseArchetypes.offline')}
            </Typography>
          </Paper>
        ) : bundles.length === 0 ? (
          <Paper variant="outlined" sx={{ p: 4, textAlign: 'center' }}>
            <Typography variant="subtitle1" fontWeight={600}>{t('control.pulseArchetypes.title')}</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              {t('control.pulseArchetypes.empty')}
            </Typography>
          </Paper>
        ) : (
          <Paper variant="outlined" sx={{ flex: 1, minHeight: 0 }}>
            <CarbonDataGrid
              columns={columns}
              rows={bundles}
              getRowId={(row) => row.name}
              emptyMessage={t('control.pulseArchetypes.empty')}
            />
          </Paper>
        )}
      </Stack>
    </PageContainer>
  );
}
