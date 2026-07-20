import React, { useEffect, useMemo, useState } from 'react';
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
        const message = err.message || 'Failed to load quality metrics';
        setError(message);
        notify({ message, type: 'error' });
      } finally {
        setLoading(false);
      }
    };

    if (tableId) load();
  }, [notify, tableId, token]);

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
      {!asset && !error && <Alert severity="info">No quality profile available for this table yet.</Alert>}
      <Stack spacing={1.5}>
        <Paper variant="outlined" sx={{ p: 2.5 }}>
          <Typography variant="caption" color="text.secondary">Quality Status</Typography>
          <Box sx={{ mt: 1 }}>
            <Chip label={asset?.quality_status || 'unknown'} color={STATUS_COLOR[asset?.quality_status] || 'default'} />
          </Box>
        </Paper>
        <Paper variant="outlined" sx={{ p: 2.5 }}>
          <Typography variant="caption" color="text.secondary">Quality Score</Typography>
          <Typography variant="h5" sx={{ mt: 1 }}>
            {asset?.quality_score != null ? `${asset.quality_score}/100` : 'N/A'}
          </Typography>
        </Paper>
        <Paper variant="outlined" sx={{ p: 2.5 }}>
          <Typography variant="caption" color="text.secondary">Active DQ Rules</Typography>
          <Typography variant="h5" sx={{ mt: 1 }}>
            {activeRuleCount}
          </Typography>
        </Paper>
        <Paper variant="outlined" sx={{ p: 2.5 }}>
          <Typography variant="caption" color="text.secondary">Last Modified</Typography>
          <Typography variant="body1" sx={{ mt: 1 }}>
            {asset?.updated_at ? new Date(asset.updated_at).toLocaleString() : 'N/A'}
          </Typography>
        </Paper>
      </Stack>
    </DetailTabContent>
  );
}
