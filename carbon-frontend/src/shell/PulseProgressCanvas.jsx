// src/shell/PulseProgressCanvas.jsx
// Read-only progress canvas: the excellence ladder (v2 exit rungs L0–L5) and
// the intention-recognition banks, from committed evidence (ADR-0049 / ADR-0050).
// Chat/Agent never mutate a host row here (ADR-0046) — this surface only reads.
import React, { useMemo } from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Chip,
  Divider,
  LinearProgress,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import InsightsOutlinedIcon from '@mui/icons-material/InsightsOutlined';
import { useTranslation } from 'react-i18next';
import { buildPulseProgress } from './pulseProgressEvidence';

const STATUS_COLOR = {
  reached: 'success',
  partial: 'warning',
  missing: 'default',
  pass: 'success',
  fail: 'error',
};

function asPercent(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return '—';
  return `${Math.round(n * 100)}%`;
}

function MetricChip({ label, value }) {
  return (
    <Chip size="small" variant="outlined" label={`${label} · ${value}`} />
  );
}

MetricChip.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
};

function SectionCard({ title, caption, children }) {
  return (
    <Box
      sx={{
        border: 1,
        borderColor: 'divider',
        borderRadius: 1,
        p: 1.5,
        bgcolor: 'background.paper',
      }}
    >
      <Typography variant="subtitle2" fontWeight={700}>{title}</Typography>
      {caption ? (
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.25 }}>
          {caption}
        </Typography>
      ) : null}
      <Box sx={{ mt: 1 }}>{children}</Box>
    </Box>
  );
}

SectionCard.propTypes = {
  title: PropTypes.string.isRequired,
  caption: PropTypes.string,
  children: PropTypes.node,
};

/**
 * @param {object} props
 * @param {ReturnType<typeof buildPulseProgress>} [props.snapshot] — override for tests
 */
export default function PulseProgressCanvas({ snapshot = null }) {
  const { t } = useTranslation('ai');
  const progress = useMemo(() => snapshot || buildPulseProgress(), [snapshot]);
  const { ladder, intention, intentionTotals, soak } = progress;

  const reached = ladder.levels.filter((level) => level.status === 'reached').length;
  const ladderPct = Math.round((100 * reached) / (ladder.levels.length || 1));

  return (
    <Box sx={{ p: 2, height: '100%', overflow: 'auto' }} data-testid="pulse-progress-canvas">
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5 }} flexWrap="wrap" useFlexGap>
        <InsightsOutlinedIcon sx={{ fontSize: 18, color: 'primary.main' }} />
        <Typography variant="subtitle2" fontWeight={700} sx={{ flex: 1, minWidth: 140 }}>
          {t('progress.title')}
        </Typography>
        <Chip
          size="small"
          variant="outlined"
          label={t('progress.measuredAt', { date: progress.measuredAt })}
        />
      </Stack>

      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1.5 }}>
        {t('progress.subtitle')}
      </Typography>

      <Stack spacing={1.5}>
        <SectionCard title={t('progress.ladderTitle')} caption={t('progress.ladderCaption')}>
          <Stack spacing={1}>
            <Stack direction="row" spacing={1} alignItems="center">
              <Typography variant="caption" color="text.secondary" sx={{ flex: 1 }}>
                {t('progress.ladderReached', { reached, total: ladder.levels.length })}
              </Typography>
              <Typography variant="caption" fontWeight={600}>{ladderPct}%</Typography>
            </Stack>
            <LinearProgress
              variant="determinate"
              value={ladderPct}
              color="success"
              sx={{ height: 8, borderRadius: 1 }}
            />
            <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
              {ladder.levels.map((level) => (
                <Chip
                  key={level.id}
                  size="small"
                  color={STATUS_COLOR[level.status] || 'default'}
                  variant={level.status === 'reached' ? 'filled' : 'outlined'}
                  label={`${level.id} ${t(`progress.levels.${level.id}`)}`}
                />
              ))}
            </Stack>
            <Typography variant="caption" color="text.disabled">
              {t('progress.beyondLadder')}
            </Typography>
            <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap sx={{ pt: 0.5 }}>
              <MetricChip label={t('progress.metricG6Accuracy')} value={asPercent(ladder.metrics.g6Accuracy)} />
              <MetricChip label={t('progress.metricG6Parity')} value={asPercent(ladder.metrics.g6Parity)} />
              <MetricChip label={t('progress.metricG5Turns')} value={ladder.metrics.g5Turns} />
              <MetricChip label={t('progress.metricStreak')} value={ladder.metrics.sixBStreak} />
              <MetricChip
                label={t('progress.metricPacks')}
                value={ladder.metrics.packsOk ? t('progress.metricPacksOk') : t('progress.metricPacksFail')}
              />
              <MetricChip label={t('progress.metricAgentPlan')} value={ladder.metrics.agentPlan} />
            </Stack>
          </Stack>
        </SectionCard>

        <SectionCard title={t('progress.intentionTitle')} caption={t('progress.intentionCaption')}>
          <Stack spacing={1.5}>
            <Chip
              size="small"
              color={intentionTotals.passed === intentionTotals.total ? 'success' : 'warning'}
              label={t('progress.totalsRecognized', {
                passed: intentionTotals.passed,
                total: intentionTotals.total,
              })}
            />
            {intention.map((bank) => (
              <Box key={bank.bank}>
                <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                  <Typography variant="body2" fontWeight={600}>
                    {t('progress.intentionBank', { bank: bank.bank })}
                  </Typography>
                  <Chip
                    size="small"
                    color={bank.pass ? 'success' : 'error'}
                    variant="outlined"
                    label={t('progress.intentionPassed', { passed: bank.passed, total: bank.total })}
                  />
                </Stack>
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.25 }}>
                  {t('progress.intentionRunAt', { at: bank.runAt })}
                </Typography>
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                  {t('progress.intentionLatency', {
                    p50: bank.latency.p50Ms,
                    over4s: bank.latency.over4s,
                    llm: bank.latency.llmCallsP50,
                  })}
                </Typography>
                <Box sx={{ mt: 0.5, overflow: 'auto' }}>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell sx={{ fontSize: '0.7rem', py: 0.25 }}>
                          {t('progress.threads')}
                        </TableCell>
                        <TableCell sx={{ fontSize: '0.7rem', py: 0.25 }}>
                          {t('progress.decisionColumn')}
                        </TableCell>
                        <TableCell sx={{ fontSize: '0.7rem', py: 0.25 }}>
                          {t('progress.resultColumn')}
                        </TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {bank.threads.map((thread) => (
                        <TableRow key={thread.id}>
                          <TableCell sx={{ fontSize: '0.7rem', py: 0.25 }}>{thread.id}</TableCell>
                          <TableCell sx={{ fontSize: '0.7rem', py: 0.25 }}>
                            {t(`progress.decision.${thread.decision}`, { defaultValue: thread.decision })}
                          </TableCell>
                          <TableCell sx={{ fontSize: '0.7rem', py: 0.25 }}>
                            <Chip
                              size="small"
                              color={STATUS_COLOR[thread.pass ? 'pass' : 'fail']}
                              label={thread.pass ? t('progress.pass') : t('progress.fail')}
                            />
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </Box>
                <Divider sx={{ mt: 1 }} />
              </Box>
            ))}
          </Stack>
        </SectionCard>

        <SectionCard title={t('progress.soakTitle')} caption={t('progress.soakCaption')}>
          <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap alignItems="center">
            <Chip
              size="small"
              color={soak.soakComplete ? 'success' : 'warning'}
              label={t('progress.soakStreak', { count: soak.consecutiveGreen, required: soak.required })}
            />
            <Chip
              size="small"
              variant="outlined"
              label={soak.soakComplete ? t('progress.soakComplete') : t('progress.soakOpen')}
            />
            <Typography variant="caption" color="text.secondary">
              {t('progress.soakLastFail', { night: soak.lastFailNight })}
            </Typography>
          </Stack>
        </SectionCard>
      </Stack>

      <Divider sx={{ my: 1.5 }} />
      <Typography variant="caption" color="text.disabled" sx={{ display: 'block' }}>
        {t('progress.sourceLabel')}
      </Typography>
      {[ladder.source, ...intention.map((bank) => bank.source), soak.source].map((src) => (
        <Typography key={src} variant="caption" color="text.disabled" sx={{ display: 'block' }}>
          {src}
        </Typography>
      ))}
    </Box>
  );
}

PulseProgressCanvas.propTypes = {
  snapshot: PropTypes.object,
};
