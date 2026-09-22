// src/apps/team/TeamLeave.jsx
// Who's Out — FilteredDataGrid of direct-report leave overlapping a month.
// GET people/me/team-leave/?year=&month=

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Alert, Chip, IconButton, Stack, Typography } from '@mui/material';
import { useTranslation } from 'react-i18next';
import FilteredDataGrid from '../../components/FilteredDataGrid';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import { fetchTeamLeave } from '../../api/team';
import { ChevronStart, ChevronEnd } from '../../i18n/DirectionalIcons';
import {
  STATUS_COLOR,
  STATUS_SUFFIX,
  codeLabel,
  formatDate,
} from '../my/components/myRequestsLabels';

function shiftMonth(year, month, delta) {
  const d = new Date(year, month - 1 + delta, 1);
  return { year: d.getFullYear(), month: d.getMonth() + 1 };
}

function monthLabel(year, month, locale) {
  try {
    return new Intl.DateTimeFormat(locale || undefined, {
      month: 'long',
      year: 'numeric',
    }).format(new Date(year, month - 1, 1));
  } catch {
    return `${year}-${String(month).padStart(2, '0')}`;
  }
}

export default function TeamLeave() {
  const { t, i18n } = useTranslation('team');
  const { token } = useAuth();
  useDocumentTitle(t('leaveTitle'));

  const today = useMemo(() => new Date(), []);
  const [year, setYear] = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth() + 1);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchValue, setSearchValue] = useState('');
  const [filters, setFilters] = useState({ status: '' });

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchTeamLeave(token, { year, month });
      setItems(Array.isArray(data?.items) ? data.items : []);
    } catch (err) {
      setError(err?.message || t('error'));
    } finally {
      setLoading(false);
    }
  }, [token, t, year, month]);

  useEffect(() => {
    load();
  }, [load]);

  const goPrev = () => {
    const next = shiftMonth(year, month, -1);
    setYear(next.year);
    setMonth(next.month);
  };

  const goNext = () => {
    const next = shiftMonth(year, month, 1);
    setYear(next.year);
    setMonth(next.month);
  };

  const filterDefs = useMemo(
    () => [
      {
        key: 'status',
        label: t('filterStatus'),
        emptyLabel: t('filterAll'),
        options: ['submitted', 'approved'].map((code) => ({
          value: code,
          label: codeLabel(t, 'status', STATUS_SUFFIX, code),
        })),
      },
    ],
    [t],
  );

  const filteredRows = useMemo(() => {
    const q = searchValue.trim().toLowerCase();
    return items.filter((row) => {
      if (filters.status && row.status !== filters.status) return false;
      if (q) {
        const hay = [
          row.employee_no,
          row.employee_name,
          row.leave_type,
          row.leave_type_label,
          row.status,
          row.reference_no,
        ]
          .filter(Boolean)
          .join(' ')
          .toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [items, searchValue, filters]);

  const columns = useMemo(
    () => [
      {
        field: 'employee_no',
        headerName: t('tableEmployeeNo'),
        flex: 0.8,
        minWidth: 100,
      },
      {
        field: 'employee_name',
        headerName: t('tableName'),
        flex: 1.2,
        minWidth: 140,
      },
      {
        field: 'leave_type_label',
        headerName: t('tableLeaveType'),
        flex: 1,
        minWidth: 120,
        valueGetter: (value, row) => row.leave_type_label || row.leave_type || '—',
      },
      {
        field: 'start_date',
        headerName: t('tableStart'),
        flex: 0.9,
        minWidth: 110,
        valueGetter: (value, row) => formatDate(row.start_date, i18n.language) || '—',
      },
      {
        field: 'end_date',
        headerName: t('tableEnd'),
        flex: 0.9,
        minWidth: 110,
        valueGetter: (value, row) => formatDate(row.end_date, i18n.language) || '—',
      },
      {
        field: 'days',
        headerName: t('tableDays'),
        width: 90,
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
    ],
    [t, i18n.language],
  );

  const hasActiveFilters = Boolean(searchValue.trim() || filters.status);

  const monthToolbar = (
    <Stack direction="row" alignItems="center" spacing={0.5}>
      <IconButton size="small" onClick={goPrev} aria-label={t('leavePrevMonth')}>
        <ChevronStart fontSize="small" />
      </IconButton>
      <Typography variant="body2" sx={{ minWidth: 140, textAlign: 'center', fontWeight: 600 }}>
        {monthLabel(year, month, i18n.language)}
      </Typography>
      <IconButton size="small" onClick={goNext} aria-label={t('leaveNextMonth')}>
        <ChevronEnd fontSize="small" />
      </IconButton>
    </Stack>
  );

  return (
    <>
      {error && (
        <Alert severity="error" sx={{ mx: 1, mt: 1 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}
      <FilteredDataGrid
        title={t('leaveTitle')}
        subtitle={t('leaveSubtitle')}
        actions={monthToolbar}
        rows={filteredRows}
        columns={columns}
        loading={loading}
        getRowId={(row) => row.id}
        countLabel={t('leaveCount', { count: filteredRows.length, total: items.length })}
        searchValue={searchValue}
        onSearchChange={setSearchValue}
        searchPlaceholder={t('leaveSearchPlaceholder')}
        filterDefs={filterDefs}
        filterValues={filters}
        onFilterChange={(key, value) => setFilters((prev) => ({ ...prev, [key]: value }))}
        onClearFilters={() => {
          setSearchValue('');
          setFilters({ status: '' });
        }}
        emptyMessage={hasActiveFilters ? t('leaveEmptyFiltered') : t('leaveEmpty')}
        emptySubtext={hasActiveFilters ? t('leaveEmptyFilteredHint') : t('leaveEmptyHint')}
        initialState={{
          sorting: { sortModel: [{ field: 'start_date', sort: 'asc' }] },
        }}
        height={560}
      />
    </>
  );
}
