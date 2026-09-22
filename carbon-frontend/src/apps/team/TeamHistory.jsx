// src/apps/team/TeamHistory.jsx
// Team History — FilteredDataGrid of decisions the current user made.
// Any corr type / any outcome (approved, rejected, sent_back, ack, review).
// compact-ui: row click = highlight; eye → /team/:id (read-only when settled).

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Alert, Box, Chip, IconButton, Tooltip } from '@mui/material';
import VisibilityIcon from '@mui/icons-material/Visibility';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import FilteredDataGrid from '../../components/FilteredDataGrid';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import { fetchHistory } from '../../api/team';
import {
  STATUS_CODES,
  STATUS_COLOR,
  STATUS_SUFFIX,
  CORR_FILTER_TYPES,
  codeLabel,
  corrTypeLabel,
  formatDateTime,
  payloadSummary,
} from '../my/components/myRequestsLabels';

const HISTORY_STATUSES = [
  'approved',
  'rejected',
  'sent_back',
  'in_review',
  'submitted',
  'cancelled',
  'archived',
];

function requesterLabel(requester) {
  if (requester == null) return '—';
  if (typeof requester === 'object') {
    return (
      requester.name ||
      requester.full_name ||
      requester.username ||
      requester.label ||
      String(requester.id ?? '')
    );
  }
  return String(requester);
}

function historyTypeLabel(t, row) {
  if (row?.corr_type_label) return row.corr_type_label;
  if (row?.corr_type_code) return corrTypeLabel(t, row.corr_type_code);
  const ct = row?.corr_type;
  if (ct && typeof ct === 'object') {
    return corrTypeLabel(t, ct.code || ct.name) || ct.label || '—';
  }
  return corrTypeLabel(t, ct);
}

function recencyKey(row) {
  const ts = row?.updated_at || row?.created_at || '';
  const id = Number(row?.id) || 0;
  return `${String(ts)}\0${String(id).padStart(12, '0')}`;
}

export default function TeamHistory() {
  const { t, i18n } = useTranslation('team');
  const { t: tMy } = useTranslation('my');
  const { token } = useAuth();
  const navigate = useNavigate();
  useDocumentTitle(t('historyTitle'));

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
      const result = await fetchHistory(token);
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
      navigate(`/team/${id}`, { state: { from: 'history' } });
    },
    [navigate],
  );

  const filterDefs = useMemo(
    () => [
      {
        key: 'status',
        label: t('filterStatus'),
        emptyLabel: t('filterAll'),
        options: HISTORY_STATUSES.filter((code) => STATUS_CODES.includes(code)).map(
          (code) => ({
            value: code,
            label: codeLabel(t, 'status', STATUS_SUFFIX, code),
          }),
        ),
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
      const typeCode =
        row.corr_type_code ||
        (typeof row.corr_type === 'object' ? row.corr_type?.code : row.corr_type);
      if (filters.corr_type && typeCode !== filters.corr_type) return false;
      if (q) {
        const requester = row.requester_name || requesterLabel(row.requester);
        const type = historyTypeLabel(t, row);
        const hay = [
          row.reference_no,
          row.title,
          requester,
          type,
          row.status,
          typeCode,
        ]
          .filter(Boolean)
          .join(' ')
          .toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [items, searchValue, filters, t]);

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
        field: 'title',
        headerName: t('tableTitle'),
        flex: 1.4,
        minWidth: 180,
        valueGetter: (value, row) => row.title || '—',
      },
      {
        field: 'requester',
        headerName: t('tableRequester'),
        flex: 1,
        minWidth: 140,
        valueGetter: (value, row) => row.requester_name || requesterLabel(row.requester),
      },
      {
        field: 'corr_type_code',
        headerName: t('tableType'),
        flex: 1,
        minWidth: 140,
        valueGetter: (value, row) => historyTypeLabel(t, row),
      },
      {
        field: 'summary',
        headerName: t('tableSummary'),
        flex: 1,
        minWidth: 140,
        sortable: false,
        valueGetter: (value, row) => payloadSummary(tMy, row, i18n.language) || '—',
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
        field: 'updated_at',
        headerName: t('tableDate'),
        flex: 1,
        minWidth: 160,
        renderCell: (params) =>
          formatDateTime(params.row.updated_at || params.row.created_at, i18n.language),
      },
      {
        field: 'actions',
        headerName: t('tableActions'),
        width: 70,
        sortable: false,
        filterable: false,
        renderCell: (params) => (
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            <Tooltip title={t('openItem', { ref: params.row.reference_no || params.row.id })}>
              <IconButton
                size="small"
                aria-label={t('openItem', { ref: params.row.reference_no || params.row.id })}
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
    [t, tMy, i18n.language, openDetail],
  );

  const hasActiveFilters = Boolean(
    searchValue.trim() || filters.status || filters.corr_type,
  );

  return (
    <>
      {error && (
        <Alert severity="error" sx={{ mx: 1, mt: 1 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}
      <FilteredDataGrid
        title={t('historyTitle')}
        subtitle={t('historySubtitle')}
        rows={filteredRows}
        columns={columns}
        loading={loading}
        getRowId={(row) => row.id}
        countLabel={t('historyCount', { count: filteredRows.length, total: items.length })}
        searchValue={searchValue}
        onSearchChange={setSearchValue}
        searchPlaceholder={t('historySearchPlaceholder')}
        filterDefs={filterDefs}
        filterValues={filters}
        onFilterChange={(key, value) => setFilters((prev) => ({ ...prev, [key]: value }))}
        onClearFilters={() => {
          setSearchValue('');
          setFilters({ status: '', corr_type: '' });
        }}
        emptyMessage={hasActiveFilters ? t('historyEmptyFiltered') : t('historyEmpty')}
        emptySubtext={
          hasActiveFilters ? t('historyEmptyFilteredHint') : t('historyEmptyHint')
        }
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
