// src/apps/healthy/RepHealthPage.jsx
// Healthy Foods Factory — rep health cards (churn risk + book-of-business metrics).

import React, { useEffect, useState } from 'react';
import { Box, Chip, Grid, Paper, Stack, Typography } from '@mui/material';
import PeopleIcon from '@mui/icons-material/People';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../components/Page/ErrorAlert';
import EmptyState from '../../components/Page/EmptyState';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import { fetchRepHealth } from '../../api/healthy';
import { churnRiskLevel, formatCurrency, formatPercent } from './utils';

function Metric({ label, value }) {
  return (
    <Box>
      <Typography sx={{ fontSize: '0.625rem', color: 'text.secondary', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
        {label}
      </Typography>
      <Typography sx={{ fontSize: '0.875rem', fontWeight: 600 }}>{value}</Typography>
    </Box>
  );
}

export default function RepHealthPage() {
  useDocumentTitle('Rep Health');
  const { token } = useAuth();
  const [cards, setCards] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetchRepHealth({}, token)
      .then((data) => {
        const list = Array.isArray(data?.results) ? data.results : [];
        setCards(list);
      })
      .catch((err) => setError(err?.message || 'Unable to load rep health.'))
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) {
    return (
      <PageContainer>
        <PageHeader icon={PeopleIcon} title="Rep Health" subtitle="Churn risk across the sales team" />
        <LoadingSkeleton variant="console" />
      </PageContainer>
    );
  }

  if (error) {
    return (
      <PageContainer>
        <PageHeader icon={PeopleIcon} title="Rep Health" subtitle="Churn risk across the sales team" />
        <ErrorAlert message={error} onRetry={() => window.location.reload()} />
      </PageContainer>
    );
  }

  if (cards.length === 0) {
    return (
      <PageContainer>
        <PageHeader icon={PeopleIcon} title="Rep Health" subtitle="Churn risk across the sales team" />
        <EmptyState
          icon={<PeopleIcon />}
          title="No rep health cards yet"
          description="Rep health cards are generated from the churn forecast. Check back after the next pipeline run."
        />
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <PageHeader
        icon={PeopleIcon}
        title="Rep Health"
        subtitle="Churn risk across the sales team"
        description="Prioritise rep retention using churn probability alongside each rep's book of business."
      />

      <Grid container spacing={2}>
        {cards.map((card) => {
          const risk = churnRiskLevel(card.churn_probability);
          return (
            <Grid key={card.id ?? `${card.week_start}-${card.rep_code}`} size={{ xs: 12, sm: 6, md: 4 }}>
              <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 2 }}>
                <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1.5 }}>
                  <Typography sx={{ fontSize: '0.875rem', fontWeight: 600 }}>{card.rep_code}</Typography>
                  <Chip
                    size="small"
                    color={risk.color}
                    variant="outlined"
                    label={`${formatPercent(card.churn_probability)} churn · ${risk.label}`}
                  />
                </Stack>
                <Box
                  sx={{
                    display: 'grid',
                    gap: 1,
                    gridTemplateColumns: '1fr 1fr',
                  }}
                >
                  <Metric label="Active customers" value={card.active_customer_count ?? '—'} />
                  <Metric label="Visit coverage" value={formatPercent(card.visit_coverage)} />
                  <Metric label="Avg order value" value={formatCurrency(card.avg_order_value)} />
                  <Metric label="AR overdue" value={formatCurrency(card.ar_overdue_amount)} />
                </Box>
              </Paper>
            </Grid>
          );
        })}
      </Grid>
    </PageContainer>
  );
}
