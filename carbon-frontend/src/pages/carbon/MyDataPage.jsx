// src/pages/carbon/MyDataPage.jsx
// My Data – Level 1 data owner workspace.
// Record list is FilteredDataGrid (design-system RULE 14).
// Scope chips use SCOPE_META palette names. Row click highlights.
// The eye icon opens the workspace.

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Chip, IconButton, Stack, Tooltip, Typography } from '@mui/material';
import { useTranslation } from 'react-i18next';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';
import RefreshIcon from '@mui/icons-material/Refresh';
import VisibilityIcon from '@mui/icons-material/Visibility';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import { useAuth } from '../../auth/AuthContext';
import { fetchMyData, fetchOwnerActivity } from '../../api/emissions';
import { ErrorAlert, PageHeader } from '../../components';
import FilteredDataGrid from '../../components/FilteredDataGrid';
import PageContainer from '../../components/layout/PageContainer';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useLanguage } from '../../i18n/useLanguage';
import { useNotes } from '../../notes/NotesContext';
import { registerMyDataSourceInspectorTabs } from '../../inspector/tabs/myDataTabs';
import { SCOPE_META } from '../../theme/themeTokens';

const STATUS_CFG = {
  passing: { key: 'passing', palette: 'success', Icon: CheckCircleOutlineIcon },
  warning: { key: 'warning', palette: 'warning', Icon: WarningAmberIcon },
  failing: { key: 'failing', palette: 'error', Icon: ErrorOutlineIcon },
  no_data: { key: 'noData', palette: undefined, Icon: HelpOutlineIcon },
};

function getStatus(mod) {
  if (!mod?.row_count) return 'no_data';
  if (mod.quality_score != null && mod.quality_score < 60) return 'failing';
  if (mod.quality_score != null && mod.quality_score < 80) return 'warning';
  return 'passing';
}

function fmtDate(v, lang) {
  if (!v) return '';
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleDateString(lang === 'ar' ? 'ar' : 'en');
}

function ScopeChip({ value }) {
  const { t } = useTranslation('emissions');
  const cfg = SCOPE_META[value] || SCOPE_META[1];
  const labelKey = value === 2 ? 'scope2' : value === 3 ? 'scope3' : 'scope1';
  return <Chip label={t(labelKey)} size="small" color={cfg.color} />;
}

function StatusChip({ row }) {
  const { t } = useTranslation('emissions');
  const cfg = STATUS_CFG[getStatus(row)];
  const Icon = cfg.Icon;
  return (
    <Chip
      icon={<Icon />}
      label={t(`myData.${cfg.key}`)}
      size="small"
      color={cfg.palette}
    />
  );
}

export default function MyDataPage() {
  const { t } = useTranslation('emissions');
  const { lang } = useLanguage();
  useDocumentTitle(t('myData.title'));
  const navigate = useNavigate();
  const { token } = useAuth();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);
  const [activity, setActivity] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [searchText, setSearchText] = useState('');
  const [scopeFilter, setScopeFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  const modules = useMemo(() => data?.modules || [], [data]);
  const orgUnit = data?.org_unit;
  const selected = useMemo(() => modules.find((m) => m.id === selectedId) || null, [modules, selectedId]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [res, act] = await Promise.all([
        fetchMyData(token),
        fetchOwnerActivity({ limit: 15 }, token).catch(() => []),
      ]);
      setData(res);
      setActivity(Array.isArray(act) ? act : []);
    } catch (err) {
      setError(err.message || t('myData.loadError'));
    } finally {
      setLoading(false);
    }
  }, [token, t]);

  useEffect(() => { if (token) load(); }, [load, token]);

  const filtered = useMemo(() => {
    let rows = modules;
    if (scopeFilter) rows = rows.filter((m) => m.scope === Number(scopeFilter));
    if (statusFilter) rows = rows.filter((m) => getStatus(m) === statusFilter);
    if (searchText) {
      const q = searchText.toLowerCase();
      rows = rows.filter((m) => (m.name || '').toLowerCase().includes(q));
    }
    return rows;
  }, [modules, scopeFilter, statusFilter, searchText]);

  const columns = useMemo(() => [
    {
      field: 'scope',
      headerName: t('myData.scope'),
      width: 120,
      renderCell: ({ value }) => <ScopeChip value={value} />,
    },
    {
      field: 'name',
      headerName: t('myData.sourceName'),
      flex: 2,
      minWidth: 180,
    },
    {
      field: 'table_count',
      headerName: t('myData.tables'),
      width: 90,
      type: 'number',
    },
    {
      field: 'row_count',
      headerName: t('myData.rows'),
      width: 90,
      type: 'number',
    },
    {
      field: 'status',
      headerName: t('myData.status'),
      width: 130,
      valueGetter: (valueOrParams, row) => {
        const currentRow = row ?? valueOrParams?.row ?? valueOrParams;
        return getStatus(currentRow);
      },
      renderCell: (params) => <StatusChip row={params?.row ?? params} />,
    },
    {
      field: 'quality_score',
      headerName: t('myData.dq'),
      width: 80,
      renderCell: ({ value }) => (
        <Typography
          variant="body2"
          sx={{
            fontWeight: 600,
            color: value == null
              ? 'text.disabled'
              : value >= 80 ? 'success.dark' : value >= 60 ? 'warning.dark' : 'error.dark',
          }}
        >
          {value != null ? `${Math.round(value)}%` : '—'}
        </Typography>
      ),
    },
    {
      field: 'last_entry',
      headerName: t('myData.lastEntry'),
      width: 120,
      renderCell: ({ value }) => (
        <Typography variant="body2" color="text.secondary">
          {fmtDate(value, lang) || t('myData.never')}
        </Typography>
      ),
    },
    {
      field: 'actions',
      headerName: '',
      width: 70,
      sortable: false,
      disableColumnMenu: true,
      renderCell: ({ row }) => (
        <Stack direction="row" onClick={(e) => e.stopPropagation()}>
          <Tooltip title={t('myData.openWorkspace')}>
            <IconButton
              size="small"
              aria-label={t('myData.openWorkspace')}
              onClick={() => navigate(`/carbon/my-data/${row.id}`)}
            >
              <VisibilityIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Stack>
      ),
    },
  ], [navigate, t, lang]);

  const filterDefs = useMemo(() => [
    {
      key: 'scope',
      label: t('myData.scope'),
      options: [1, 2, 3].map((n) => ({
        value: String(n),
        label: t(n === 1 ? 'scope1' : n === 2 ? 'scope2' : 'scope3'),
      })),
    },
    {
      key: 'status',
      label: t('myData.status'),
      options: Object.entries(STATUS_CFG).map(([value, cfg]) => ({
        value,
        label: t(`myData.${cfg.key}`),
      })),
    },
  ], [t]);

  const { setContexts } = useNotes();
  useEffect(() => registerMyDataSourceInspectorTabs(), []);
  const inspectorContext = useMemo(
    () => [{ entityType: 'myDataSource', entityId: selected?.id ?? null, label: selected?.name, payload: { mod: selected, activity } }],
    [selected, activity],
  );
  useEffect(() => {
    setContexts(inspectorContext);
    return () => setContexts(null);
  }, [inspectorContext, setContexts]);

  if (error && !data) {
    return (
      <PageContainer>
        <PageHeader title={t('myData.title')} />
        <ErrorAlert message={error} onRetry={load} />
      </PageContainer>
    );
  }

  return (
    <FilteredDataGrid
      title={t('myData.title')}
      subtitle={orgUnit?.name || ''}
      description={t('myData.description')}
      actions={(
        <Tooltip title={t('myData.refresh')}>
          <IconButton size="small" aria-label={t('myData.refresh')} onClick={load}>
            <RefreshIcon />
          </IconButton>
        </Tooltip>
      )}
      rows={filtered}
      columns={columns}
      loading={loading}
      countLabel={t('myData.count', { shown: filtered.length, total: modules.length })}
      searchValue={searchText}
      onSearchChange={setSearchText}
      searchPlaceholder={t('myData.search')}
      filterDefs={filterDefs}
      filterValues={{ scope: scopeFilter, status: statusFilter }}
      onFilterChange={(key, value) => {
        if (key === 'scope') setScopeFilter(value || '');
        if (key === 'status') setStatusFilter(value || '');
      }}
      onClearFilters={() => {
        setSearchText('');
        setScopeFilter('');
        setStatusFilter('');
      }}
      emptyMessage={t('myData.empty')}
      emptySubtext={t('myData.emptyHint')}
      onRowClick={(params) => setSelectedId(params.id)}
      highlightRow={(row) => row.id === selectedId}
    />
  );
}
