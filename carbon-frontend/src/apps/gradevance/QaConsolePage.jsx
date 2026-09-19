// QA console — reliability, canary, appeals, calibration deep-link (Phase D).

import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Alert, Box, Button, Chip, Paper, Stack, Typography,
} from '@mui/material';
import ScienceIcon from '@mui/icons-material/Science';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../components/Page/ErrorAlert';
import EmptyState from '../../components/Page/EmptyState';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import { fetchQaSummary } from '../../api/gradevance';
import SkipToMain from './SkipToMain';

export default function QaConsolePage() {
  useDocumentTitle('GradeVance · QA');
  const { token } = useAuth();
  const navigate = useNavigate();
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    fetchQaSummary(token)
      .then(setSummary)
      .catch((err) => setError(err?.message || 'Failed to load QA summary'))
      .finally(() => setLoading(false));
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <PageContainer>
        <PageHeader icon={ScienceIcon} title="QA console" subtitle="Reliability · canary · appeals" />
        <LoadingSkeleton variant="console" />
      </PageContainer>
    );
  }

  if (error && !summary) {
    return (
      <PageContainer>
        <PageHeader icon={ScienceIcon} title="QA console" />
        <ErrorAlert message={error} onRetry={load} />
      </PageContainer>
    );
  }

  if (!summary) {
    return (
      <PageContainer>
        <PageHeader icon={ScienceIcon} title="QA console" />
        <EmptyState
          icon={<ScienceIcon />}
          title="No QA data"
          description="QA summary is empty. Check calibration after held-out scoring."
          actionLabel="Calibration"
          onAction={() => navigate('/teach/calibration')}
        />
      </PageContainer>
    );
  }

  const kappa = summary.kappa ?? summary.cohen_kappa ?? summary.held_out_kappa ?? summary.reliability?.kappa ?? summary.reliability?.value;
  const kappaSd = summary.kappa_sd ?? summary.reliability_sd?.value;
  const openAppeals = summary.open_appeals ?? summary.appeals_open ?? 0;
  const canary = summary.canary_note || summary.canary || null;
  const packId = summary.profile_pack_id || summary.default_pack_id;
  const goldEval = summary.gold_eval || null;

  const cards = [
    { label: 'Held-out SG κ', value: kappa != null ? Number(kappa).toFixed(3) : '—' },
    { label: 'Held-out SD κ', value: kappaSd != null ? Number(kappaSd).toFixed(3) : '—' },
    { label: 'Open appeals', value: openAppeals },
    { label: 'Publish gate', value: summary.publish_gate_passed === true ? 'pass' : (summary.publish_gate_passed === false ? 'fail' : (summary.gate || '—')) },
  ];

  return (
    <PageContainer>
      <SkipToMain targetId="gv-qa-console" />
      <Box component="main" id="gv-qa-console" tabIndex={-1} aria-label="QA console">
        <PageHeader
          icon={ScienceIcon}
          title="QA console"
          subtitle="Reliability (κ), canary notes, open appeals, and audit sampling."
          actions={(
            <Stack direction="row" spacing={0.75}>
              <Button
                size="small"
                variant="outlined"
                endIcon={<ArrowForwardIcon />}
                onClick={() => navigate(packId ? `/teach/calibration?profile_pack_id=${encodeURIComponent(packId)}` : '/teach/calibration')}
              >
                Calibration
              </Button>
              <Button
                size="small"
                variant="outlined"
                endIcon={<ArrowForwardIcon />}
                onClick={() => navigate('/teach/appeals')}
              >
                Appeals
              </Button>
            </Stack>
          )}
        />

        {error && <ErrorAlert message={error} onRetry={load} />}

        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} sx={{ mb: 2 }} role="list" aria-label="QA stats">
          {cards.map((c) => (
            <Paper key={c.label} variant="outlined" sx={{ p: 1.5, flex: 1 }} role="listitem">
              <Typography variant="overline" color="text.secondary">{c.label}</Typography>
              <Typography variant="h5" component="p">{c.value}</Typography>
            </Paper>
          ))}
        </Stack>

        {canary && (
          <Alert severity="info" sx={{ mb: 2 }} role="status">
            {typeof canary === 'string' ? canary : (canary.note || JSON.stringify(canary))}
          </Alert>
        )}

        {(summary.fairness_notes || summary.fairness_note) && (
          <Paper variant="outlined" sx={{ p: 1.5, mb: 2 }} component="section" aria-labelledby="fairness-notes">
            <Typography id="fairness-notes" variant="subtitle2" sx={{ mb: 0.5 }}>Fairness notes</Typography>
            <Typography variant="body2" color="text.secondary">
              {summary.fairness_notes || summary.fairness_note}
            </Typography>
          </Paper>
        )}

        <Paper variant="outlined" sx={{ p: 1.5, mb: 2 }} component="section" aria-labelledby="gold-eval-heading">
          <Typography id="gold-eval-heading" variant="subtitle2" sx={{ mb: 0.5 }}>
            Gold eval (Instrument Trust)
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            Full-pipeline agreement vs held_out. Artifact:
            {' '}
            <Typography component="span" variant="body2" sx={{ fontFamily: 'monospace' }}>
              docs/eduos/qa-evidence/GOLD-EVAL-LATEST.json
            </Typography>
            . Run
            {' '}
            <Typography component="span" variant="body2" sx={{ fontFamily: 'monospace' }}>
              manage.py gradevance_gold_eval
            </Typography>
            {' '}
            (DJANGO_BRAND=eduos). See GOLD-PROVENANCE.md — no live PDF scoring.
          </Typography>
          {goldEval && (
            <Typography variant="caption" color="text.secondary">
              Last report: SG κ {goldEval.sg_kappa ?? '—'} · essays {goldEval.essay_count ?? '—'}
            </Typography>
          )}
        </Paper>

        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
          {summary.mode && <Chip size="small" label={`mode: ${summary.mode}`} />}
          {summary.canary_active != null && (
            <Chip size="small" color={summary.canary_active ? 'warning' : 'default'} label={summary.canary_active ? 'canary active' : 'canary off'} />
          )}
          {openAppeals > 0 && (
            <Chip size="small" color="warning" label={`${openAppeals} open appeals`} onClick={() => navigate('/teach/appeals')} />
          )}
        </Stack>
      </Box>
    </PageContainer>
  );
}
