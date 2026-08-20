// src/apps/healthy/ARQueuePage.jsx
// Healthy Foods Factory — AR collections priority queue (risk-ranked).

import React, { useEffect, useState } from 'react';
import { Chip, Stack, Typography } from '@mui/material';
import AccountBalanceWalletIcon from '@mui/icons-material/AccountBalanceWallet';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../components/Page/ErrorAlert';
import EmptyState from '../../components/Page/EmptyState';
import StandardDataGrid from '../../components/StandardDataGrid';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import { fetchARQueue } from '../../api/healthy';
import { arRiskLevel, formatCurrency } from './utils';

export default function ARQueuePage() {
  useDocumentTitle('AR Queue');
  const { token } = useAuth();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetchARQueue(token)
      .then((data) => {
        const list = Array.isArray(data?.results) ? data.results : data;
        setRows(Array.isArray(list) ? list : []);
      })
      .catch((err) => setError(err?.message || 'Unable to load the AR queue.'))
      .finally(() => setLoading(false));
  }, [token]);

  const columns = [
    { field: 'customer_code', headerName: 'Customer', flex: 1.4, minWidth: 140 },
    {
      field: 'risk_score',
      headerName: 'Risk',
      flex: 1,
      minWidth: 140,
      renderCell: (params) => {
        const level = arRiskLevel(params.value);
        const percent = params.value == null ? '—' : `${Math.round(Number(params.value) * 100)}%`;
        return <Chip size="small" color={level.color} variant="outlined" label={`${level.label} · ${percent}`} />;
      },
    },
    { field: 'days_overdue', headerName: 'Days overdue', flex: 0.8, type: 'number' },
    {
      field: 'amount_overdue',
      headerName: 'Amount overdue',
      flex: 1,
      valueFormatter: (value) => formatCurrency(value),
    },
  ];

  if (loading) {
    return (
      <PageContainer>
        <PageHeader icon={AccountBalanceWalletIcon} title="AR Queue" subtitle="Collections prioritised by risk" />
        <LoadingSkeleton variant="table" />
      </PageContainer>
    );
  }

  if (error) {
    return (
      <PageContainer>
        <PageHeader icon={AccountBalanceWalletIcon} title="AR Queue" subtitle="Collections prioritised by risk" />
        <ErrorAlert message={error} onRetry={() => window.location.reload()} />
      </PageContainer>
    );
  }

  if (rows.length === 0) {
    return (
      <PageContainer>
        <PageHeader icon={AccountBalanceWalletIcon} title="AR Queue" subtitle="Collections prioritised by risk" />
        <EmptyState
          icon={<AccountBalanceWalletIcon />}
          title="No overdue accounts"
          description="The collections queue is empty. Overdue accounts will appear here ranked by risk once the AR forecast runs."
        />
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <PageHeader
        icon={AccountBalanceWalletIcon}
        title="AR Queue"
        subtitle="Collections prioritised by risk"
        description="Work the highest-risk overdue accounts first, sorted by collections risk."
      />

      <Stack spacing={1}>
        <Typography sx={{ fontSize: '0.6875rem', color: 'text.secondary' }}>
          {rows.length} overdue account{rows.length === 1 ? '' : 's'} · sorted by risk
        </Typography>
        <StandardDataGrid
          rows={rows}
          columns={columns}
          getRowId={(row) => row.prediction_id ?? row.customer_code}
          loading={loading}
          pageSize={25}
          rowsPerPageOptions={[25, 50, 100]}
          initialState={{ sorting: { sortModel: [{ field: 'risk_score', sort: 'desc' }] } }}
          sx={{ height: 480 }}
        />
      </Stack>
    </PageContainer>
  );
}
