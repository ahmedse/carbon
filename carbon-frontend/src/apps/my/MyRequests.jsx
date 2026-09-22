// src/apps/my/MyRequests.jsx
// My Requests — FilteredDataGrid shell (search + status/type filters).
// Loads the employee's correspondence once; filters/search are client-side.
// compact-ui: ROW CLICK = HIGHLIGHT ONLY; open detail via eye action.

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Alert, Box, Chip, IconButton, Tooltip } from '@mui/material';
import VisibilityIcon from '@mui/icons-material/Visibility';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import FilteredDataGrid from '../../components/FilteredDataGrid';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import { fetchMyCorrespondence } from '../../api/my';
import {
  STATUS_CODES,
  STATUS_COLOR,
  STATUS_SUFFIX,
  CORR_FILTER_TYPES,
  codeLabel,
  corrTypeLabel,
  requestTypeLabel,
  payloadSummary,
  formatDateTime,
} from './components/myRequestsLabels';

function recencyKey(row) {
  const ts = row?.updated_at || row?.created_at || '';
  const id = Number(row?.id) || 0;
  return `${String(ts)}\0${String(id).padStart(12, '0')}`;
}

export default function MyRequests() {
  const { t, i18n } = useTranslation('my');
  const { token } = useAuth();
  const navigate = useNavigate();
  useDocumentTitle(t('requestsTitle'));

  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchValue, setSearchValue] = useState('');
  const [filters, setFilters] = useState({ status: '', corr_type: '' });
  const [selectedId, setSelectedId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchMyCorrespondence(token);
      const list = Array.isArray(result?.items) ? [...result.items] : [];
      list.sort((a, b) => recencyKey(b).localeCompare(recencyKey(a)));
      setItems(list);
    } catch (err) {
      setError(err?.message || t('error'));
    } finally {
      setLoading(false);
    }
  }, [token, t]);

  useEffect(() => {
    load();
  }, [load]);

  const openDetail = useCallback(
    (id) => {
      if (id == null) return;
      navigate(`/my/requests/${id}`);
    },
    [navigate],
  );

  const filterDefs = useMemo(
    () => [
      {
        key: 'status',
        label: t('filterStatus'),
        emptyLabel: t('filterAll'),
        options: STATUS_CODES.map((code) => ({
          value: code,
          label: codeLabel(t, 'status', STATUS_SUFFIX, code),
        })),
      },
      {
        key: 'corr_type',
        label: t('filterType'),
        emptyLabel: t('filterAll'),
        options: CORR_FILTER_TYPES.map((code) => ({
          value: code,
          label: corrTypeLabel(t, code),
        })),
      },
    ],
    [t],
  );

  const filteredRows = useMemo(() => {
    const q = searchValue.trim().toLowerCase();
    return items.filter((row) => {
      if (filters.status && row.status !== filters.status) return false;
      if (filters.corr_type && row.corr_type_code !== filters.corr_type) return false;
      if (q) {
        const typeLabel = requestTypeLabel(t, row);
        const summary = payloadSummary(t, row, i18n.language) || '';
        const hay = [
          row.reference_no,
          row.title,
          typeLabel,
          summary,
          row.status,
          row.corr_type_code,
        ]
          .filter(Boolean)
          .join(' ')
          .toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [items, searchValue, filters, t, i18n.language]);

  const columns = useMemo(
    () => [
      {
        field: 'reference_no',
        headerName: t('tableReferenceNo'),
        flex: 1,
        minWidth: 140,
        valueGetter: (value, row) => row.reference_no || '—',
      },
      {
        field: 'corr_type_code',
        headerName: t('tableType'),
        flex: 1,
        minWidth: 150,
        valueGetter: (value, row) => requestTypeLabel(t, row),
      },
      {
        field: 'title',
        headerName: t('tableTitle'),
        flex: 1.4,
        minWidth: 200,
        valueGetter: (value, row) => row.title || '—',
      },
      {
        field: 'summary',
        headerName: t('tableSummary'),
        flex: 1,
        minWidth: 140,
        sortable: false,
        valueGetter: (value, row) => payloadSummary(t, row, i18n.language) || '—',
      },
      {
        field: 'status',
        headerName: t('tableStatus'),
        width: 130,
        renderCell: (params) => (
          <Chip
            size="small"
            variant="outlined"
            color={STATUS_COLOR[params.row.status] || 'default'}
            label={codeLabel(t, 'status', STATUS_SUFFIX, params.row.status)}
          />
        ),
      },
      {
        field: 'created_at',
        headerName: t('tableCreated'),
        flex: 1,
        minWidth: 160,
        renderCell: (params) => formatDateTime(params.row.created_at, i18n.language),
      },
      {
        field: 'updated_at',
        headerName: t('tableUpdated'),
        flex: 1,
        minWidth: 160,
        renderCell: (params) => formatDateTime(params.row.updated_at, i18n.language),
      },
      {
        field: 'actions',
        headerName: t('tableActions'),
        width: 70,
        sortable: false,
        filterable: false,
        renderCell: (params) => (
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            <Tooltip title={t('openRequest', { ref: params.row.reference_no || params.row.id })}>
              <IconButton
                size="small"
                aria-label={t('openRequest', { ref: params.row.reference_no || params.row.id })}
                onClick={(e) => {
                  e.stopPropagation();
                  openDetail(params.row.id);
                }}
                sx={{ color: 'primary.main' }}
              >
                <VisibilityIcon sx={{ fontSize: 16 }} />
              </IconButton>
            </Tooltip>
          </Box>
        ),
      },
    ],
    [t, i18n.language, openDetail],
  );

  return (
    <>
      {error && (
        <Alert severity="error" sx={{ mx: 1, mt: 1 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}
      <FilteredDataGrid
        title={t('requestsTitle')}
        subtitle={t('requestsSubtitle')}
        rows={filteredRows}
        columns={columns}
        loading={loading}
        getRowId={(row) => row.id}
        countLabel={`${filteredRows.length} of ${items.length}`}
        searchValue={searchValue}
        onSearchChange={setSearchValue}
        searchPlaceholder={t('requestsSearchPlaceholder')}
        filterDefs={filterDefs}
        filterValues={filters}
        onFilterChange={(key, value) => setFilters((prev) => ({ ...prev, [key]: value }))}
        onClearFilters={() => {
          setSearchValue('');
          setFilters({ status: '', corr_type: '' });
        }}
        emptyMessage={t('requestsEmpty')}
        emptySubtext={t('requestsEmptyFiltered')}
        onRowClick={(params) => {
          const id = params.row.id;
          setSelectedId((prev) => (prev === id ? null : id));
        }}
        highlightRow={(row) => row.id === selectedId}
        initialState={{
          sorting: { sortModel: [{ field: 'updated_at', sort: 'desc' }] },
        }}
        height={560}
      />
    </>
  );
}
