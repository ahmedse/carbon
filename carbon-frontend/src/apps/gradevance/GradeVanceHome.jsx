// GradeVance overview — cohort pulse + professor journey shortcuts (RULE_33).

import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Box, Button, Chip, Paper, Stack, Typography } from '@mui/material';
import SchoolIcon from '@mui/icons-material/School';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../components/Page/ErrorAlert';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import { fetchGradeVanceSummary, fetchLtiStatus, fetchAccessibility } from '../../api/gradevance';
import SkipToMain from './SkipToMain';

export default function GradeVanceHome() {
  useDocumentTitle('GradeVance');
  const navigate = useNavigate();
  const { token } = useAuth();
  const [summary, setSummary] = useState(null);
  const [lti, setLti] = useState(null);
  const [a11y, setA11y] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      fetchGradeVanceSummary(token),
      fetchLtiStatus(token).catch(() => null),
      fetchAccessibility(token).catch(() => null),
    ])
      .then(([sum, ltiStatus, a11yStatus]) => {
        setSummary(sum);
        setLti(ltiStatus);
        setA11y(a11yStatus);
      })
      .catch((err) => setError(err?.message || 'Failed to load GradeVance summary'))
      .finally(() => setLoading(false));
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <PageContainer>
        <PageHeader icon={SchoolIcon} title="GradeVance" subtitle="Multi-domain assessment & coaching" />
        <LoadingSkeleton variant="console" />
      </PageContainer>
    );
  }

  if (error) {
    return (
      <PageContainer>
        <PageHeader icon={SchoolIcon} title="GradeVance" subtitle="Multi-domain assessment & coaching" />
        <ErrorAlert message={error} onRetry={load} />
      </PageContainer>
    );
  }

  const cards = [
    { label: 'Profiles on disk', value: summary?.profiles_on_disk ?? 0, path: '/apps/gradevance/library' },
    { label: 'Stems', value: summary?.assignments ?? 0, path: '/teach/stems' },
    { label: 'Analysis runs', value: summary?.runs ?? 0, path: '/teach/marking' },
    { label: 'Open reviews', value: summary?.open_reviews ?? 0, path: '/teach/marking' },
  ];

  return (
    <PageContainer>
      <SkipToMain targetId="gradevance-main" />
      <Box component="main" id="gradevance-main" tabIndex={-1} aria-label="GradeVance overview">
      <PageHeader
        icon={SchoolIcon}
        title="GradeVance"
        subtitle="Engine room — pack library, proposals, and cross-course QA."
      />
      <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} sx={{ mb: 3 }} role="list" aria-label="GradeVance summary metrics">
        {cards.map((c) => (
          <Paper
            key={c.label}
            component="button"
            role="listitem"
            sx={{ p: 2, flex: 1, cursor: 'pointer', textAlign: 'left', border: 'none', bgcolor: 'background.paper' }}
            onClick={() => navigate(c.path)}
            aria-label={`${c.label}: ${c.value}. Open ${c.path}`}
          >
            <Typography variant="overline" color="text.secondary">{c.label}</Typography>
            <Typography variant="h4" component="p">{c.value}</Typography>
          </Paper>
        ))}
      </Stack>
      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 3 }} role="group" aria-label="Primary GradeVance actions">
        <Button variant="contained" endIcon={<ArrowForwardIcon />} onClick={() => navigate('/apps/gradevance/library')}>
          Pack library
        </Button>
        <Button variant="outlined" endIcon={<ArrowForwardIcon />} onClick={() => navigate('/apps/gradevance/proposals')}>
          Proposals
        </Button>
        <Button variant="text" endIcon={<ArrowForwardIcon />} onClick={() => navigate('/teach')}>
          Teach (my classes)
        </Button>
        <Button variant="text" endIcon={<ArrowForwardIcon />} onClick={() => navigate('/learn')}>
          Learn (my studies)
        </Button>
      </Box>
      {lti && (
        <Paper component="section" aria-labelledby="lti-status-heading" sx={{ p: 2, mb: 2 }}>
          <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
            <Typography id="lti-status-heading" component="h2" variant="h6">
              LTI 1.3
            </Typography>
            <Chip
              size="small"
              color={lti.ready ? 'success' : 'default'}
              label={lti.ready ? 'ready' : (lti.status || 'scaffold')}
            />
            {lti.ags?.dry_run != null && (
              <Chip size="small" label={lti.ags.dry_run ? 'AGS dry-run' : 'AGS live'} />
            )}
          </Stack>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            {lti.note || lti.reason || 'Configure GRADEVANCE_LTI_* to enable OIDC launch.'}
          </Typography>
          <Typography variant="caption" component="p" color="text.secondary">
            Login {lti.endpoints?.login} · Passback {lti.ags?.passback}
          </Typography>
        </Paper>
      )}
      {a11y && (
        <Paper component="section" aria-labelledby="a11y-heading" sx={{ p: 2 }}>
          <Typography id="a11y-heading" component="h2" variant="h6" sx={{ mb: 1 }}>
            Accessibility
          </Typography>
          <Stack direction="row" spacing={1} sx={{ mb: 1, flexWrap: 'wrap' }}>
            {Object.entries(a11y.counts || {}).map(([k, v]) => (
              <Chip key={k} size="small" label={`${k}: ${v}`} />
            ))}
          </Stack>
          <Typography variant="caption" color="text.secondary">
            {a11y.standard} — {a11y.note}
          </Typography>
        </Paper>
      )}
      </Box>
    </PageContainer>
  );
}
