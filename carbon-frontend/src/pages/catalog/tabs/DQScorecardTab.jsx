// src/pages/catalog/tabs/DQScorecardTab.jsx
// DQ quality scorecard for a single table (EPH-3A): an overall score ring plus
// six per-dimension DAMA DMBOK2 bars. All scores arrive as 0..1 floats.
import React, { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Alert, Box, CircularProgress, LinearProgress, Paper, Stack, Typography,
} from '@mui/material';
import { useAuth } from '../../../auth/AuthContext';
import { useNotification } from '../../../components/NotificationProvider';
import { DetailTabContent } from '../../../components/detail/DetailMainPanel';
import { getTableScorecard } from '../../../api/profiling';

const DIMENSION_KEYS = [
  { key: 'completeness', labelKey: 'dimCompleteness' },
  { key: 'validity', labelKey: 'dimValidity' },
  { key: 'accuracy', labelKey: 'dimAccuracy' },
  { key: 'uniqueness', labelKey: 'dimUniqueness' },
  { key: 'consistency', labelKey: 'dimConsistency' },
  { key: 'timeliness', labelKey: 'dimTimeliness' },
];

function formatDateTime(value) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleString();
}

function ScoreRing({ value }) {
  const pct = Math.round((Number(value) || 0) * 100);
  return (
    <Box sx={{ position: 'relative', display: 'inline-flex' }}>
      <CircularProgress variant="determinate" value={pct} size={128} thickness={5} />
      <Box
        sx={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <Typography variant="h4" component="div" sx={{ fontWeight: 600 }}>
          {pct}
        </Typography>
      </Box>
    </Box>
  );
}

export default function DQScorecardTab({ tableId }) {
  const { token } = useAuth();
  const { notify } = useNotification();
  const { t } = useTranslation('catalog');

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [scorecard, setScorecard] = useState(null);

  const load = useCallback(async () => {
    if (!tableId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await getTableScorecard(tableId, token);
      setScorecard(data || null);
    } catch (err) {
      const message = err?.message || t('failedToLoadScorecard');
      setError(message);
      notify({ message, type: 'error' });
    } finally {
      setLoading(false);
    }
  }, [tableId, token, notify, t]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <DetailTabContent>
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
          <CircularProgress />
        </Box>
      </DetailTabContent>
    );
  }

  if (error) {
    return (
      <DetailTabContent>
        <Alert severity="warning">{error}</Alert>
      </DetailTabContent>
    );
  }

  const totalRules = scorecard?.total_rules ?? 0;
  if (!scorecard || totalRules === 0) {
    return (
      <DetailTabContent>
        <Alert severity="info">{t('noDqRulesAssigned')}</Alert>
      </DetailTabContent>
    );
  }

  const dimensions = scorecard.dimensions || {};
  const rowCount = scorecard.profile_summary?.row_count;
  const lastRunAt = formatDateTime(scorecard.last_run_at);

  return (
    <DetailTabContent>
      <Stack spacing={2}>
        <Paper
          variant="outlined"
          sx={{
            p: 3,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 1,
          }}
        >
          <Typography variant="caption" color="text.secondary">
            {t('qualityScore')}
          </Typography>
          <ScoreRing value={scorecard.quality_score} />
          {rowCount != null && (
            <Typography variant="caption" color="text.secondary">
              {Number(rowCount).toLocaleString()} {t('rows')}
            </Typography>
          )}
          {lastRunAt && (
            <Typography variant="caption" color="text.secondary">
              {t('lastRunAt')}: {lastRunAt}
            </Typography>
          )}
        </Paper>

        <Paper variant="outlined" sx={{ p: 2.5 }}>
          <Stack spacing={2}>
            {DIMENSION_KEYS.map(({ key, labelKey }) => {
              const dim = dimensions[key] || { passed: 0, failed: 0, score: 0 };
              const pct = Math.round((Number(dim.score) || 0) * 100);
              return (
                <Box key={key}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                    <Typography variant="body2">{t(labelKey)}</Typography>
                    <Typography variant="body2" color="text.secondary">
                      {t('passedFailed', {
                        passed: dim.passed ?? 0,
                        failed: dim.failed ?? 0,
                      })}{' '}· {pct}%
                    </Typography>
                  </Box>
                  <LinearProgress variant="determinate" value={pct} />
                </Box>
              );
            })}
          </Stack>
        </Paper>
      </Stack>
    </DetailTabContent>
  );
}
