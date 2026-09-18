// src/pages/catalog/DatasetsPage.jsx
// Dataset Hub browse (ADR-0040) — versioned contract artifacts, NOT Data Products.
// Uses FilteredDataGrid page shell (SearchSelect filters — RULE 13).
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Alert, Box, Button, Chip, Typography } from '@mui/material';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import FilteredDataGrid from '../../components/FilteredDataGrid';
import { fetchDatasets } from '../../api/catalog';

function unwrap(data) {
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.results)) return data.results;
  return [];
}

export default function DatasetsPage() {
  useDocumentTitle('Datasets');
  const { t } = useTranslation('catalog');
  const { token } = useAuth();
  const { notify } = useNotification();
  const navigate = useNavigate();

  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchText, setSearchText] = useState('');
  const [filterStatus, setFilterStatus] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchDatasets(token);
      setRows(unwrap(data));
    } catch (err) {
      const msg = err.message || t('datasetsLoadError');
      setError(msg);
      notify({ message: msg, type: 'error' });
    } finally {
      setLoading(false);
    }
  }, [token, notify, t]);

  useEffect(() => { load(); }, [load]);

  const filtered = useMemo(() => {
    let list = rows;
    const q = searchText.trim().toLowerCase();
    if (q) {
      list = list.filter((d) =>
        (d.name || '').toLowerCase().includes(q)
        || (d.slug || '').toLowerCase().includes(q)
        || (d.description || '').toLowerCase().includes(q),
      );
    }
    if (filterStatus) {
      list = list.filter((d) => d.status === filterStatus);
    }
    return list;
  }, [rows, searchText, filterStatus]);

  const columns = useMemo(() => [
    {
      field: 'name',
      headerName: t('name'),
      flex: 1.5,
      minWidth: 180,
      renderCell: (params) => (
        <Typography variant="body2" fontWeight={500}>{params.value || '—'}</Typography>
      ),
    },
    {
      field: 'status',
      headerName: t('status'),
      width: 130,
      renderCell: (params) => (
        <Chip size="small" label={params.value || '—'} variant="outlined" />
      ),
    },
    {
      field: 'classification',
      headerName: t('classification'),
      width: 140,
      renderCell: (params) => params.value || '—',
    },
    {
      field: 'module',
      headerName: t('dataProduct'),
      width: 120,
      renderCell: (params) => (
        params.value ? (
          <Typography
            variant="body2"
            color="primary"
            sx={{ cursor: 'pointer' }}
            onClick={(e) => {
              e.stopPropagation();
              navigate(`/catalog/products/${params.value}`);
            }}
          >
            #{params.value}
          </Typography>
        ) : '—'
      ),
    },
    {
      field: 'updated_at',
      headerName: t('updatedAt'),
      width: 160,
      renderCell: (params) => (
        params.value ? new Date(params.value).toLocaleDateString() : '—'
      ),
    },
  ], [t, navigate]);

  const statusOptions = useMemo(() => {
    const set = new Set(rows.map((r) => r.status).filter(Boolean));
    return [...set].map((s) => ({ value: s, label: s }));
  }, [rows]);

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
      {error && (
        <Alert
          severity="error"
          sx={{ mx: 2, mt: 2 }}
          action={(
            <Button color="inherit" size="small" onClick={load}>
              {t('retry')}
            </Button>
          )}
        >
          {error}
        </Alert>
      )}
      <FilteredDataGrid
        title={t('datasets')}
        subtitle={t('datasetsSubtitle')}
        description={t('relatedDatasetsHint')}
        rows={filtered}
        loading={loading}
        columns={columns}
        countLabel={t('datasetsCount', { shown: filtered.length, total: rows.length })}
        searchValue={searchText}
        onSearchChange={setSearchText}
        filterDefs={[
          {
            key: 'status',
            label: t('status'),
            emptyLabel: t('allStatus'),
            options: statusOptions,
          },
        ]}
        filterValues={{ status: filterStatus }}
        onFilterChange={(key, value) => {
          if (key === 'status') setFilterStatus(value);
        }}
        onClearFilters={() => {
          setSearchText('');
          setFilterStatus('');
        }}
        pageSize={25}
        getRowId={(row) => row.id}
        emptyMessage={t('noRelatedDatasets')}
        emptySubtext={t('tryAdjustingFilters')}
      />
    </Box>
  );
}
