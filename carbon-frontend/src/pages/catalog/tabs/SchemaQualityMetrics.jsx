import React, { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Alert, Box, Chip, CircularProgress, Paper, Stack, Typography } from '@mui/material';
import { useAuth } from '../../../auth/AuthContext';
import { useNotification } from '../../../components/NotificationProvider';
import { DetailTabContent } from '../../../components/detail/DetailMainPanel';
import { fetchAssetProfiles } from '../../../api/catalog';
import { listDQRules } from '../../../api/dq';

const STATUS_COLOR = {
  passing: 'success',
  warning: 'warning',
  failing: 'error',
  unknown: 'default',
};

function unwrap(data) {
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.results)) return data.results;
  return [];
}

export default function SchemaQualityMetrics({ tableId }) {
  const { t, i18n } = useTranslation('catalog');
  const { token } = useAuth();
  const { notify } = useNotification();
  const [loading, setLoading] = useState(true);
  const [asset, setAsset] = useState(null);
  const [rules, setRules] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const [assetsData, dqRulesData] = await Promise.all([
          fetchAssetProfiles(token).catch(() => []),
          listDQRules(token, { data_table: tableId }).catch(() => []),
        ]);
        const assets = unwrap(assetsData);
        const tableAsset = assets.find((item) => item.data_table === Number(tableId) && !item.data_field) || null;
        setAsset(tableAsset);
        setRules(unwrap(dqRulesData));
      } catch (err) {
        const message = err.message || t('failedToLoadQualityMetrics');
        setError(message);
        notify({ message, type: 'error' });
      } finally {
        setLoading(false);
      }
    };

    if (tableId) load();
  }, [notify, tableId, token, t]);

  const activeRuleCount = useMemo(() => rules.filter((rule) => rule.is_active !== false).length, [rules]);

  if (loading) {
    return (
      <DetailTabContent>
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
          <CircularProgress />
        </Box>
      </DetailTabContent>
    );
  }

  return (
    <DetailTabContent>
      {error && <Alert severity="warning">{error}</Alert>}
      {!asset && !error && <Alert severity="info">{t('noQualityProfileForTable')}</Alert>}
      <Stack spacing={1.5}>
        <Paper variant="outlined" sx={{ p: 2.5 }}>
          <Typography variant="caption" color="text.secondary">{t('qualityStatus')}</Typography>
          <Box sx={{ mt: 1 }}>
            <Chip label={asset?.quality_status || t('unknown')} color={STATUS_COLOR[asset?.quality_status] || 'default'} />
          </Box>
        </Paper>
        <Paper variant="outlined" sx={{ p: 2.5 }}>
          <Typography variant="caption" color="text.secondary">{t('qualityScore')}</Typography>
          <Typography variant="h5" sx={{ mt: 1 }}>
            {asset?.quality_score != null ? `${asset.quality_score}/100` : t('na')}
          </Typography>
        </Paper>
        <Paper variant="outlined" sx={{ p: 2.5 }}>
          <Typography variant="caption" color="text.secondary">{t('activeDqRules')}</Typography>
          <Typography variant="h5" sx={{ mt: 1 }}>
            {activeRuleCount}
          </Typography>
        </Paper>
        <Paper variant="outlined" sx={{ p: 2.5 }}>
          <Typography variant="caption" color="text.secondary">{t('lastModified')}</Typography>
          <Typography variant="body1" sx={{ mt: 1 }}>
            {asset?.updated_at ? new Date(asset.updated_at).toLocaleString(i18n.language) : t('na')}
          </Typography>
        </Paper>
      </Stack>
    </DetailTabContent>
  );
}
