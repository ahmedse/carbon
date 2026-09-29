import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Chip, IconButton, Tooltip } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import UploadIcon from '@mui/icons-material/Upload';
import VisibilityRounded from '@mui/icons-material/VisibilityRounded';
import { useTranslation } from 'react-i18next';
import PageContainer from '../layout/PageContainer';
import PageHeader from '../Page/PageHeader';
import LoadingSkeleton from '../Page/LoadingSkeleton';
import ErrorAlert from '../Page/ErrorAlert';
import FilteredDataGrid from '../FilteredDataGrid';
import { SearchSelect } from '../Form';
import FormField from '../Form/FormField';
import SystemDialog from '../SystemDialog';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../NotificationProvider';
import { createInboundBatch, fetchInboundBatches, fetchInboundTargets } from '../../api/inbound';
import { INBOUND_STATUS_COLOR, inboundCaps } from './inboundAccess';

export default function InboundList({
  kind,
  listPath,
  ns = 'people',
  icon: Icon = UploadIcon,
}) {
  const { t } = useTranslation(ns);
  const { t: tCommon } = useTranslation('common');
  useDocumentTitle(t('importTitle'));
  const navigate = useNavigate();
  const { token, isGlobalAdminFlag, userCapabilities } = useAuth();
  const { notifyFromError } = useNotification();

  const [rows, setRows] = useState([]);
  const [targets, setTargets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [open, setOpen] = useState(false);
  const [targetKey, setTargetKey] = useState('');
  const [creating, setCreating] = useState(false);
  const [searchValue, setSearchValue] = useState('');
  const [gridFilters, setGridFilters] = useState({ status: '', target_key: '' });
  const [selectedId, setSelectedId] = useState(null);

  const { canPrepare, canSee } = inboundCaps(userCapabilities, isGlobalAdminFlag);

  const load = useCallback(async () => {
    if (!token || !canSee) return;
    setLoading(true);
    setError(null);
    try {
      const [batchRes, targetRes] = await Promise.all([
        fetchInboundBatches(token, kind),
        fetchInboundTargets(token, kind),
      ]);
      setRows(Array.isArray(batchRes) ? batchRes : batchRes.results || []);
      setTargets(Array.isArray(targetRes) ? targetRes : targetRes.results || []);
    } catch (err) {
      if (err?.status === 403) {
        setError('forbidden');
      } else {
        setError(err.message || t('importLoadFailed'));
        notifyFromError(err, t('importLoadFailed'));
      }
    } finally {
      setLoading(false);
    }
  }, [token, canSee, kind, notifyFromError, t]);

  useEffect(() => {
    load();
  }, [load]);

  const filterDefs = useMemo(() => [
    {
      key: 'status',
      label: t('importColStatus'),
      emptyLabel: tCommon('all', { defaultValue: 'All' }),
      options: ['draft', 'mapped', 'smoked', 'committed', 'failed'].map((value) => ({
        value,
        label: t(`importStatus_${value}`),
      })),
    },
    {
      key: 'target_key',
      label: t('importColTarget'),
      emptyLabel: tCommon('all', { defaultValue: 'All' }),
      options: targets.map((item) => ({ value: item.key, label: item.label })),
    },
  ], [t, tCommon, targets]);

  const filteredRows = useMemo(() => {
    const q = searchValue.trim().toLowerCase();
    return rows.filter((row) => {
      if (gridFilters.status && row.status !== gridFilters.status) return false;
      if (gridFilters.target_key && row.target_key !== gridFilters.target_key) return false;
      if (!q) return true;
      const hay = [
        row.target_label, row.target_key, row.original_filename,
        row.status, row.prepared_by_username,
      ].join(' ').toLowerCase();
      return hay.includes(q);
    });
  }, [rows, searchValue, gridFilters]);

  const columns = useMemo(() => [
    {
      field: 'status',
      headerName: t('importColStatus'),
      width: 140,
      valueGetter: (value) => t(`importStatus_${value}`, { defaultValue: value }),
      renderCell: (params) => (
        <Chip
          size="small"
          variant="outlined"
          color={INBOUND_STATUS_COLOR[params.row.status] || 'default'}
          label={params.value}
        />
      ),
    },
    {
      field: 'target_label',
      headerName: t('importColTarget'),
      flex: 1,
      minWidth: 180,
      valueGetter: (_value, row) => row.target_label || row.target_key || '—',
    },
    {
      field: 'original_filename',
      headerName: t('importColFile'),
      flex: 1,
      minWidth: 160,
      valueGetter: (value) => value || '—',
    },
    {
      field: 'row_count',
      headerName: t('importColRows'),
      width: 90,
      valueGetter: (value) => value ?? 0,
    },
    {
      field: 'reject_count',
      headerName: t('importColRejects'),
      width: 100,
      valueGetter: (value) => value ?? 0,
    },
    {
      field: 'updated_at',
      headerName: t('importColUpdated'),
      width: 170,
      valueGetter: (value) => (value ? new Date(value).toLocaleString() : '—'),
    },
    {
      field: 'prepared_by_username',
      headerName: t('importColPreparedBy'),
      width: 140,
      valueGetter: (value) => value || '—',
    },
    {
      field: 'actions',
      headerName: t('importColActions'),
      width: 72,
      sortable: false,
      filterable: false,
      renderCell: (params) => {
        const label = t('importOpen');
        return (
          <Tooltip title={label}>
            <IconButton
              size="small"
              color="primary"
              aria-label={label}
              onClick={(event) => {
                event.stopPropagation();
                navigate(`${listPath}/${params.row.id}`);
              }}
            >
              <VisibilityRounded fontSize="small" />
            </IconButton>
          </Tooltip>
        );
      },
    },
  ], [t, navigate, listPath]);

  const onCreate = async () => {
    if (!targetKey) return;
    setCreating(true);
    try {
      const batch = await createInboundBatch(token, { kind, target_key: targetKey });
      setOpen(false);
      setTargetKey('');
      navigate(`${listPath}/${batch.id}`);
    } catch (err) {
      notifyFromError(err, t('importCreateFailed'));
    } finally {
      setCreating(false);
    }
  };

  if (!canSee) {
    return (
      <PageContainer>
        <PageHeader icon={Icon} title={t('importTitle')} subtitle={t('importSubtitle')} />
        <ErrorAlert message={t('importForbidden')} />
      </PageContainer>
    );
  }

  const hasFilters = Boolean(searchValue || gridFilters.status || gridFilters.target_key);

  return (
    <PageContainer>
      <PageHeader
        icon={Icon}
        title={t('importTitle')}
        subtitle={t('importSubtitle')}
        description={t('importDescription')}
        actions={canPrepare ? (
          <Button variant="contained" size="small" startIcon={<AddIcon />} onClick={() => setOpen(true)}>
            {t('importNew')}
          </Button>
        ) : null}
      />

      {loading ? (
        <LoadingSkeleton variant="console" />
      ) : error === 'forbidden' ? (
        <ErrorAlert message={t('importForbidden')} />
      ) : error ? (
        <ErrorAlert message={error} onRetry={load} />
      ) : (
        <FilteredDataGrid
          embedded
          rows={filteredRows}
          columns={columns}
          getRowId={(row) => row.id}
          searchValue={searchValue}
          onSearchChange={setSearchValue}
          searchPlaceholder={t('importSearch')}
          filterDefs={filterDefs}
          filterValues={gridFilters}
          onFilterChange={(key, value) => setGridFilters((prev) => ({ ...prev, [key]: value }))}
          onClearFilters={() => {
            setSearchValue('');
            setGridFilters({ status: '', target_key: '' });
          }}
          emptyMessage={hasFilters
            ? t('importNoResults')
            : (canPrepare ? t('importEmpty') : t('importEmptyCommit'))}
          emptySubtext={hasFilters
            ? t('importNoResultsDesc')
            : (canPrepare ? t('importEmptyDesc') : t('importEmptyCommitDesc'))}
          pageSize={25}
          height={560}
          onRowClick={(params) => {
            const id = params.row.id;
            setSelectedId((prev) => (prev === id ? null : id));
          }}
          highlightRow={(row) => row.id === selectedId}
        />
      )}

      <SystemDialog
        open={open}
        title={t('importNewTitle')}
        onClose={() => setOpen(false)}
        onCancel={() => setOpen(false)}
        cancelLabel={tCommon('cancel')}
        actions={(
          <Button variant="contained" disabled={!targetKey || creating} onClick={onCreate}>
            {t('importStart')}
          </Button>
        )}
      >
        <FormField label={t('importTarget')} required helperText={t('importTargetHint')}>
          <SearchSelect
            label={t('importTarget')}
            value={targetKey}
            onChange={(opt) => setTargetKey(opt?.value ?? '')}
            options={targets.map((item) => ({
              value: item.key,
              label: item.label,
            }))}
          />
        </FormField>
      </SystemDialog>
    </PageContainer>
  );
}
