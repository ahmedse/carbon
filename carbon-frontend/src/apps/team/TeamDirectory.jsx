// src/apps/team/TeamDirectory.jsx
// Team Directory — FilteredDataGrid of direct reports (manager-scoped).
// GET people/me/direct-reports/ — not HR people:view.

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Alert, Chip } from '@mui/material';
import { useTranslation } from 'react-i18next';
import FilteredDataGrid from '../../components/FilteredDataGrid';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import { fetchDirectReports } from '../../api/team';

export default function TeamDirectory() {
  const { t } = useTranslation('team');
  const { token } = useAuth();
  useDocumentTitle(t('directoryTitle'));

  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchValue, setSearchValue] = useState('');
  const [filters, setFilters] = useState({ active: '' });

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchDirectReports(token);
      setItems(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err?.message || t('error'));
    } finally {
      setLoading(false);
    }
  }, [token, t]);

  useEffect(() => {
    load();
  }, [load]);

  const filterDefs = useMemo(
    () => [
      {
        key: 'active',
        label: t('filterActive'),
        emptyLabel: t('filterAll'),
        options: [
          { value: 'true', label: t('activeYes') },
          { value: 'false', label: t('activeNo') },
        ],
      },
    ],
    [t],
  );

  const filteredRows = useMemo(() => {
    const q = searchValue.trim().toLowerCase();
    return items.filter((row) => {
      if (filters.active === 'true' && !row.is_active) return false;
      if (filters.active === 'false' && row.is_active) return false;
      if (q) {
        const hay = [
          row.employee_no,
          row.full_name,
          row.job_title,
          row.org_unit?.name,
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
        minWidth: 110,
      },
      {
        field: 'full_name',
        headerName: t('tableName'),
        flex: 1.4,
        minWidth: 160,
      },
      {
        field: 'job_title',
        headerName: t('tableJobTitle'),
        flex: 1.2,
        minWidth: 140,
        valueGetter: (value, row) => row.job_title || '—',
      },
      {
        field: 'org_unit',
        headerName: t('tableOrgUnit'),
        flex: 1.2,
        minWidth: 140,
        valueGetter: (value, row) => row.org_unit?.name || '—',
      },
      {
        field: 'is_active',
        headerName: t('tableActive'),
        width: 110,
        renderCell: (params) => (
          <Chip
            size="small"
            variant="outlined"
            color={params.row.is_active ? 'success' : 'default'}
            label={params.row.is_active ? t('activeYes') : t('activeNo')}
          />
        ),
      },
    ],
    [t],
  );

  const hasActiveFilters = Boolean(searchValue.trim() || filters.active);

  return (
    <>
      {error && (
        <Alert severity="error" sx={{ mx: 1, mt: 1 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}
      <FilteredDataGrid
        title={t('directoryTitle')}
        subtitle={t('directorySubtitle')}
        rows={filteredRows}
        columns={columns}
        loading={loading}
        getRowId={(row) => row.id}
        countLabel={t('directoryCount', { count: filteredRows.length, total: items.length })}
        searchValue={searchValue}
        onSearchChange={setSearchValue}
        searchPlaceholder={t('directorySearchPlaceholder')}
        filterDefs={filterDefs}
        filterValues={filters}
        onFilterChange={(key, value) => setFilters((prev) => ({ ...prev, [key]: value }))}
        onClearFilters={() => {
          setSearchValue('');
          setFilters({ active: '' });
        }}
        emptyMessage={hasActiveFilters ? t('directoryEmptyFiltered') : t('directoryEmpty')}
        emptySubtext={
          hasActiveFilters ? t('directoryEmptyFilteredHint') : t('directoryEmptyHint')
        }
        initialState={{
          sorting: { sortModel: [{ field: 'employee_no', sort: 'asc' }] },
        }}
        height={560}
      />
    </>
  );
}
