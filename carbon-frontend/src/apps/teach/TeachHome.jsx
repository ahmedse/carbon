// Teach home — professor / marker overview with links into /teach/* (ADR-0042).

import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Box, Button, Paper, Stack, Typography } from '@mui/material';
import ClassIcon from '@mui/icons-material/Class';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../components/Page/ErrorAlert';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import { fetchGradeVanceSummary } from '../../api/gradevance';
import SkipToMain from '../gradevance/SkipToMain';

export default function TeachHome() {
  useDocumentTitle('Teach');
  const navigate = useNavigate();
  const { token } = useAuth();
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    fetchGradeVanceSummary(token)
      .then(setSummary)
      .catch((err) => setError(err?.message || 'Failed to load Teach overview'))
      .finally(() => setLoading(false));
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <PageContainer>
        <PageHeader icon={ClassIcon} title="Teach" subtitle="My classes" />
        <LoadingSkeleton variant="console" />
      </PageContainer>
    );
  }

  if (error) {
    return (
      <PageContainer>
        <PageHeader icon={ClassIcon} title="Teach" subtitle="My classes" />
        <ErrorAlert message={error} onRetry={load} />
      </PageContainer>
    );
  }

  const cards = [
    { label: 'Stems', value: summary?.assignments ?? 0, path: '/teach/stems' },
    { label: 'Analysis runs', value: summary?.runs ?? 0, path: '/teach/marking' },
    { label: 'Open reviews', value: summary?.open_reviews ?? 0, path: '/teach/marking' },
  ];

  return (
    <PageContainer>
      <SkipToMain targetId="teach-main" />
      <Box component="main" id="teach-main" tabIndex={-1} aria-label="Teach overview">
        <PageHeader
          icon={ClassIcon}
          title="Teach"
          subtitle="Design intention → prove instrument → measure meaning → release with ceremony."
        />
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5} sx={{ mb: 2 }} role="list" aria-label="Class pulse">
          {cards.map((c) => (
            <Paper
              key={c.label}
              component="button"
              role="listitem"
              sx={{ p: 1.5, flex: 1, cursor: 'pointer', textAlign: 'left', border: 'none', bgcolor: 'background.paper' }}
              onClick={() => navigate(c.path)}
              aria-label={`${c.label}: ${c.value}`}
            >
              <Typography variant="overline" color="text.secondary">{c.label}</Typography>
              <Typography variant="h5" component="p">{c.value}</Typography>
            </Paper>
          ))}
        </Stack>
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }} role="group" aria-label="Teach actions">
          <Button size="small" variant="contained" endIcon={<ArrowForwardIcon />} onClick={() => navigate('/teach/stems')}>
            Stems
          </Button>
          <Button size="small" variant="outlined" endIcon={<ArrowForwardIcon />} onClick={() => navigate('/teach/calibration')}>
            Calibration
          </Button>
          <Button size="small" variant="outlined" endIcon={<ArrowForwardIcon />} onClick={() => navigate('/teach/marking')}>
            Marking queue
          </Button>
          <Button size="small" variant="outlined" endIcon={<ArrowForwardIcon />} onClick={() => navigate('/teach/appeals')}>
            Appeals
          </Button>
          <Button size="small" variant="outlined" endIcon={<ArrowForwardIcon />} onClick={() => navigate('/teach/proposals')}>
            Proposals
          </Button>
        </Box>
      </Box>
    </PageContainer>
  );
}
