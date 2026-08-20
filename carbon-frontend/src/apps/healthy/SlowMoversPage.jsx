// src/apps/healthy/SlowMoversPage.jsx
// Healthy Foods Factory — inventory slow movers / dead stock (heatmap + alert table).

import React, { useEffect, useMemo, useState } from 'react';
import { Box, Chip, Grid, Paper, Stack, Typography } from '@mui/material';
import { alpha, useTheme } from '@mui/material/styles';
import StorageIcon from '@mui/icons-material/Storage';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../components/Page/ErrorAlert';
import EmptyState from '../../components/Page/EmptyState';
import StandardDataGrid from '../../components/StandardDataGrid';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import { fetchSlowMovers } from '../../api/healthy';
import { slowMoverSeverity } from './utils';

const SEVERITY_LABEL = {
  dead: 'Dead stock',
  slow: 'Slow mover',
  moving: 'Moving',
  unknown: 'No data',
};

const SEVERITY_ALPHA = { dead: 0.24, slow: 0.14, moving: 0.05, unknown: 0.04 };

export default function SlowMoversPage() {
  useDocumentTitle('Slow Movers');
  const theme = useTheme();
  const { token } = useAuth();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetchSlowMovers(token)
      .then((data) => {
        const list = Array.isArray(data?.results) ? data.results : data;
        setRows(Array.isArray(list) ? list : []);
      })
      .catch((err) => setError(err?.message || 'Unable to load slow movers.'))
      .finally(() => setLoading(false));
  }, [token]);

  const columns = useMemo(
    () => [
      { field: 'item_code', headerName: 'Item code', flex: 1.2, minWidth: 140 },
      { field: 'demand_forecast_4w', headerName: '4-week forecast', flex: 0.8, type: 'number' },
      {
        field: 'severity',
        headerName: 'Status',
        flex: 1,
        renderCell: (params) => {
          const severity = slowMoverSeverity(params.row.demand_forecast_4w);
          const color = severity === 'dead' ? 'error' : severity === 'slow' ? 'warning' : severity === 'moving' ? 'success' : 'default';
          return <Chip size="small" color={color} variant="outlined" label={SEVERITY_LABEL[severity]} />;
        },
      },
    ],
    [],
  );

  if (loading) {
    return (
      <PageContainer>
        <PageHeader icon={StorageIcon} title="Slow Movers" subtitle="Dead-stock and slow-moving inventory" />
        <LoadingSkeleton variant="table" />
      </PageContainer>
    );
  }

  if (error) {
    return (
      <PageContainer>
        <PageHeader icon={StorageIcon} title="Slow Movers" subtitle="Dead-stock and slow-moving inventory" />
        <ErrorAlert message={error} onRetry={() => window.location.reload()} />
      </PageContainer>
    );
  }

  if (rows.length === 0) {
    return (
      <PageContainer>
        <PageHeader icon={StorageIcon} title="Slow Movers" subtitle="Dead-stock and slow-moving inventory" />
        <EmptyState
          icon={<StorageIcon />}
          title="No slow movers"
          description="No dead or slow-moving inventory flagged. Items with weak 4-week demand will surface here after the demand forecast runs."
        />
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <PageHeader
        icon={StorageIcon}
        title="Slow Movers"
        subtitle="Dead-stock and slow-moving inventory"
        description="Spot items at risk of sitting on the shelf, ranked by their 4-week demand forecast."
      />

      <Stack spacing={2}>
        <Box>
          <Typography sx={{ fontSize: '0.8125rem', fontWeight: 600, mb: 1 }}>Demand heatmap</Typography>
          <Grid container spacing={1}>
            {rows.map((item) => {
              const severity = slowMoverSeverity(item.demand_forecast_4w);
              const intensity = SEVERITY_ALPHA[severity] ?? SEVERITY_ALPHA.unknown;
              return (
                <Grid key={item.prediction_id ?? item.item_code} size={{ xs: 4, sm: 3, md: 2 }}>
                  <Paper
                    variant="outlined"
                    sx={{
                      p: 1,
                      borderRadius: 2,
                      textAlign: 'center',
                      bgcolor: alpha(theme.palette.error.main, intensity),
                    }}
                  >
                    <Typography sx={{ fontSize: '0.75rem', fontWeight: 600 }} noWrap>
                      {item.item_code}
                    </Typography>
                    <Typography sx={{ fontSize: '0.6875rem', color: 'text.secondary' }}>
                      {item.demand_forecast_4w == null ? '—' : Number(item.demand_forecast_4w)} units
                    </Typography>
                  </Paper>
                </Grid>
              );
            })}
          </Grid>
        </Box>

        <Box>
          <Typography sx={{ fontSize: '0.8125rem', fontWeight: 600, mb: 1 }}>Alert table</Typography>
          <StandardDataGrid
            rows={rows}
            columns={columns}
            getRowId={(row) => row.prediction_id ?? row.item_code}
            loading={loading}
            pageSize={25}
            rowsPerPageOptions={[25, 50, 100]}
            sx={{ height: 480 }}
          />
        </Box>
      </Stack>
    </PageContainer>
  );
}
