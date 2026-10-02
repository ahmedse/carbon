// src/pages/carbon/CoverageTargetsPage.jsx
// Coverage targets — layer 1 of the two-layer Coverage model (locked 2 Oct 2026).
//
// A TARGET is a period-scoped KPI goal (percent or absolute) with a quality
// floor, a due date and an owner. Progress is measured from real streams; the
// ratio here is labelled "measured, not claimed". Coverage streams stay the
// only surface that reports Missing / Entered / Excluded, so this page shows a
// measured ratio and a cross-link, never a stream-state column.
//
// Toolkit only: PageContainer, PageHeader, FilteredDataGrid, WorkflowCard,
// EmptyState, LoadingSkeleton, Alert+Retry, SearchSelect. RULE 8 tokens,
// ADR-0037 (no page-local fontSize / hex), ADR-0018 EN+AR parity.

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Alert, Box, Button, Chip, Stack, Typography } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import RefreshIcon from '@mui/icons-material/Refresh';
import FlagIcon from '@mui/icons-material/Flag';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

import useDocumentTitle from '../../hooks/useDocumentTitle';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import EmptyState from '../../components/Page/EmptyState';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import FilteredDataGrid from '../../components/FilteredDataGrid';
import { SearchSelect } from '../../components/Form';
import SystemDialog from '../../components/SystemDialog';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import {
  fetchCoverageTargetBoard,
  fetchCoverageTargets,
  createCoverageTarget,
} from '../../api/emissions-extended';
import {
  Ltr,
  TargetForm,
  TargetStatusChip,
  TierChip,
  emptyTargetForm,
  formToTargetPayload,
  formatDate,
  scopeLabel,
} from './coverageTargetsShared';

const PERIOD_STATUS_KEYS = {
  open: 'statusOpen',
  closed: 'statusClosed',
  locked: 'statusLocked',
};

export default function CoverageTargetsPage() {
  useDocumentTitle('Coverage targets');
  const { t } = useTranslation('emissions');
  const navigate = useNavigate();
  const { token, user, availablePerspectives } = useAuth();
  const { notify, notifyFromError } = useNotification();

  const [periods, setPeriods] = useState([]);
  const [openPeriodId, setOpenPeriodId] = useState(null);
  const [selectedPeriod, setSelectedPeriod] = useState('');
  const [targets, setTargets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  // True only once the board payload has actually resolved. The read-only
  // history banner must never appear before that (loading or failed load).
  const [boardLoaded, setBoardLoaded] = useState(false);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState(emptyTargetForm());
  const [saving, setSaving] = useState(false);

  const isAdmin = Boolean(
    user?.is_staff || user?.is_superuser || (availablePerspectives || []).includes('carbon-admin'),
  );

  const loadBoard = useCallback(async () => {
    setLoading(true);
    setError('');
    setBoardLoaded(false);
    try {
      const board = await fetchCoverageTargetBoard(token);
      const periodList = Array.isArray(board?.periods) ? board.periods : [];
      const defaultId = board?.period_default != null
        ? String(board.period_default)
        : (board?.open_period?.id != null ? String(board.open_period.id) : '');
      setPeriods(periodList);
      setOpenPeriodId(defaultId || null);
      setSelectedPeriod(defaultId || (periodList[0] ? String(periodList[0].id) : ''));
      setTargets(Array.isArray(board?.targets) ? board.targets : []);
      setBoardLoaded(true);
    } catch (err) {
      setError(err?.message || t('coverageTargets.loadFailed'));
      setTargets([]);
    } finally {
      setLoading(false);
    }
  }, [token, t]);

  useEffect(() => {
    loadBoard();
  }, [loadBoard]);

  const loadTargets = useCallback(async (periodId) => {
    if (!periodId) return;
    setLoading(true);
    setError('');
    try {
      const data = await fetchCoverageTargets({ reporting_period: periodId }, token);
      setTargets(Array.isArray(data) ? data : data?.results || []);
    } catch (err) {
      setError(err?.message || t('coverageTargets.loadFailed'));
      setTargets([]);
    } finally {
      setLoading(false);
    }
  }, [token, t]);

  const selectedPeriodRow = useMemo(
    () => periods.find((row) => String(row.id) === String(selectedPeriod)),
    [periods, selectedPeriod],
  );
  // Editability follows the selected cycle's own status, not a guess made
  // before the board arrives. The read-only history banner is honest only once
  // the board has actually loaded and the selected cycle is genuinely not the
  // open period — never while loading, never on a failed load (RULE 8).
  const selectedPeriodIsOpen = Boolean(selectedPeriodRow) && selectedPeriodRow.status === 'open';
  const readOnly = !selectedPeriodIsOpen;
  const showReadOnlyHistory = boardLoaded
    && !loading
    && !error
    && Boolean(selectedPeriodRow)
    && !selectedPeriodIsOpen;

  const periodStatusLabel = (row) => {
    if (!row) return '';
    const key = PERIOD_STATUS_KEYS[row.status];
    return key ? t(key) : row.status;
  };

  const cycleOptions = periods.map((row) => {
    const status = periodStatusLabel(row);
    return {
      value: String(row.id),
      label: status ? `${row.name} · ${status}` : row.name,
    };
  });

  const openCreate = () => {
    setForm(emptyTargetForm());
    setDialogOpen(true);
  };

  const handleField = (name, value) => {
    setForm((prev) => {
      const next = { ...prev, [name]: value };
      if (name === 'goal_kind' && value === 'percent') next.goal_unit = '';
      if (name === 'scope' && !String(value).includes('3')) next.scope3_category = '';
      // Org unit is campus-dependent: a new campus invalidates the old unit.
      if (name === 'campus' && String(value) !== String(prev.campus)) next.org_unit = '';
      return next;
    });
  };

  const handleCreate = async () => {
    if (!form.name.trim() || !form.campus || !form.org_unit || form.goal_value === '') {
      notify({ message: t('coverageTargets.saveFailed'), type: 'error' });
      return;
    }
    setSaving(true);
    try {
      await createCoverageTarget(
        { ...formToTargetPayload(form), reporting_period: Number(openPeriodId || selectedPeriod) },
        token,
      );
      notify({ message: t('coverageTargets.created'), type: 'success' });
      setDialogOpen(false);
      setForm(emptyTargetForm());
      await loadTargets(selectedPeriod);
    } catch (err) {
      notifyFromError(err, t('coverageTargets.saveFailed'));
    } finally {
      setSaving(false);
    }
  };

  const columns = useMemo(() => [
    {
      field: 'name',
      headerName: t('name'),
      flex: 1,
      minWidth: 160,
    },
    {
      field: 'campus_name',
      headerName: t('coverageTargets.colCampus'),
      flex: 1,
      minWidth: 140,
      valueGetter: (_value, row) => row.campus_name || row.org_unit_name || '—',
    },
    {
      field: 'org_unit_name',
      headerName: t('coverageTargets.colOrgUnit'),
      flex: 1,
      minWidth: 140,
      valueGetter: (_value, row) => row.org_unit_name || row.org_unit || '—',
    },
    {
      field: 'scope',
      headerName: t('coverageTargets.colScope'),
      width: 170,
      valueGetter: (_value, row) => scopeLabel(row),
      renderCell: (params) => <Ltr>{params.value}</Ltr>,
    },
    {
      field: 'goal_value',
      headerName: t('coverageTargets.colGoal'),
      width: 150,
      renderCell: (params) => {
        const row = params.row;
        if (row.goal_kind === 'absolute') {
          return (
            <span>
              {row.goal_value}
              {' '}
              <Ltr>{row.goal_unit || ''}</Ltr>
            </span>
          );
        }
        return <span>{`${row.goal_value}%`}</span>;
      },
    },
    {
      field: 'min_quality_tier',
      headerName: t('coverageTargets.colQualityFloor'),
      width: 140,
      renderCell: (params) => <TierChip value={params.value} />,
    },
    {
      field: 'due_date',
      headerName: t('coverageTargets.colDue'),
      width: 120,
      valueFormatter: (value) => formatDate(value),
    },
    {
      field: 'owner_name',
      headerName: t('coverageTargets.colOwner'),
      width: 150,
      valueGetter: (_value, row) => row.owner_name || row.owner_username || '—',
    },
    {
      field: 'status',
      headerName: t('coverageTargets.colStatus'),
      width: 120,
      renderCell: (params) => <TargetStatusChip value={params.value} t={t} />,
    },
    {
      field: 'progress',
      headerName: t('coverageTargets.colProgress'),
      flex: 1.2,
      minWidth: 220,
      sortable: false,
      renderCell: (params) => {
        const progress = params.row.progress || {};
        const counts = progress.counts || {};
        if (progress.state === 'empty' || !counts.required) {
          return (
            <Typography variant="body2" color="text.secondary">
              {t('coverageTargets.emptyProgress')}
            </Typography>
          );
        }
        const settled = (counts.entered || 0) + (counts.excluded || 0);
        return (
          <Stack spacing={0.25}>
            <Typography variant="body2">
              {t('coverageTargets.measuredRatio', {
                settled,
                required: counts.required || 0,
                pct: progress.measured_pct ?? '—',
              })}
            </Typography>
            <Chip size="small" variant="outlined" label={t('coverageTargets.measuredNotClaimed')} />
          </Stack>
        );
      },
    },
  ], [t]);

  return (
    <PageContainer>
      <PageHeader
        icon={FlagIcon}
        title={t('coverageTargets.pageTitle')}
        description={t('coverageTargets.pageDescription')}
        actions={(
          <Stack direction="row" spacing={1}>
            <Button
              variant="contained"
              size="small"
              startIcon={<AddIcon />}
              onClick={openCreate}
              disabled={readOnly || !isAdmin || !selectedPeriod}
            >
              {t('coverageTargets.addTarget')}
            </Button>
            <Button size="small" startIcon={<RefreshIcon />} onClick={loadBoard}>
              {t('common:refresh')}
            </Button>
          </Stack>
        )}
      />

      {showReadOnlyHistory && (
        <Box sx={{ mb: 1.5 }}>
          <Chip color="info" size="small" label={t('coverageTargets.readOnlyHistory', { status: periodStatusLabel(selectedPeriodRow) })} />
        </Box>
      )}

      <Box sx={{ maxWidth: 480, my: 1 }}>
        <SearchSelect
          label={t('coverageTargets.cycle')}
          options={cycleOptions}
          value={selectedPeriod}
          onChange={(option) => {
            const next = option?.value ? String(option.value) : '';
            setSelectedPeriod(next);
            if (next) loadTargets(next);
          }}
          helperText={t('coverageTargets.cycleHint')}
          loading={loading && periods.length === 0}
          clearable={false}
        />
      </Box>

      {error && (
        <Alert
          severity="error"
          sx={{ mb: 2 }}
          action={(
            <Button color="inherit" size="small" onClick={() => (selectedPeriod ? loadTargets(selectedPeriod) : loadBoard())}>
              {t('common:retry')}
            </Button>
          )}
        >
          {t('coverageTargets.loadError')}
        </Alert>
      )}

      {loading ? (
        <LoadingSkeleton variant="table" />
      ) : error ? null : targets.length === 0 ? (
        <EmptyState
          icon={<FlagIcon />}
          title={t('coverageTargets.noTargets')}
          description={t('coverageTargets.noTargetsHint')}
          actionLabel={!readOnly && isAdmin ? t('coverageTargets.addTarget') : undefined}
          onAction={openCreate}
        />
      ) : (
        <FilteredDataGrid
          embedded
          hideSearch
          rows={targets}
          columns={columns}
          onRowClick={(params) => navigate(`/carbon/admin/coverage-targets/${params.row.id}`)}
        />
      )}

      <SystemDialog
        open={dialogOpen}
        title={t('coverageTargets.newTarget')}
        onClose={() => setDialogOpen(false)}
        onCancel={() => setDialogOpen(false)}
        cancelLabel={t('common:cancel')}
        width={560}
        height={640}
        minWidth={420}
        minHeight={420}
        actions={(
          <Button variant="contained" size="small" onClick={handleCreate} disabled={saving}>
            {t('create')}
          </Button>
        )}
      >
        <TargetForm values={form} onField={handleField} t={t} />
      </SystemDialog>
    </PageContainer>
  );
}
