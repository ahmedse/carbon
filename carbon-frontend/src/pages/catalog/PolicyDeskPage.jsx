// Policy desk. Data Trust admin lists versions and publishes.
// People submits drafts. This page does not edit payroll fields.

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  Chip,
  IconButton,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import PolicyIcon from '@mui/icons-material/Policy';
import PublishIcon from '@mui/icons-material/Publish';
import VisibilityIcon from '@mui/icons-material/Visibility';
import { useTranslation } from 'react-i18next';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../components/Page/ErrorAlert';
import EmptyState from '../../components/Page/EmptyState';
import SystemDialog from '../../components/SystemDialog';
import FilteredDataGrid from '../../components/FilteredDataGrid';
import { FormField } from '../../components/Form';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import {
  fetchPolicyVersion,
  fetchPolicyVersions,
  publishPolicyVersion,
  submitPolicyVersion,
} from '../../api/catalog';

const STATE_TONE = {
  draft: 'info',
  in_review: 'warning',
  authoritative: 'success',
  superseded: 'default',
};

function passLabel(t, passed) {
  return passed ? t('policyPass') : t('policyFail');
}

function readCitation(detail, row) {
  if (typeof detail?.citation === 'string') return detail.citation;
  if (typeof row?.citation === 'string') return row.citation;
  return '';
}

export default function PolicyDeskPage() {
  const { t } = useTranslation('catalog');
  const { t: tCommon } = useTranslation('common');
  const { token } = useAuth();
  const { notify } = useNotification();
  const [params] = useSearchParams();
  useDocumentTitle(t('policyDeskTitle'));

  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState('');
  const [stateFilter, setStateFilter] = useState('');
  const [highlightId, setHighlightId] = useState(null);

  const [dialogMode, setDialogMode] = useState(null);
  const [activeRow, setActiveRow] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailError, setDetailError] = useState('');
  const [publishing, setPublishing] = useState(false);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchPolicyVersions(token);
      setRows(Array.isArray(data?.results) ? data.results : []);
    } catch (err) {
      setError(err?.message || t('policyDeskLoadError'));
    } finally {
      setLoading(false);
    }
  }, [token, t]);

  useEffect(() => { loadData(); }, [loadData]);

  useEffect(() => {
    const focus = params.get('focus');
    if (focus) setHighlightId(Number(focus));
  }, [params]);

  const visibleRows = useMemo(() => {
    const q = search.trim().toLowerCase();
    return rows.filter((row) => {
      if (stateFilter && row.state !== stateFilter) return false;
      if (!q) return true;
      return [row.policy, row.version, row.name].some((value) => String(value || '').toLowerCase().includes(q));
    });
  }, [rows, search, stateFilter]);

  const stateOptions = ['draft', 'in_review', 'authoritative', 'superseded'].map((value) => ({
    value,
    label: t(`policyState_${value}`),
  }));

  const closeDialog = () => {
    setDialogMode(null);
    setActiveRow(null);
    setDetail(null);
    setDetailError('');
  };

  const openRecord = async (row, mode) => {
    setDialogMode(mode);
    setActiveRow(row);
    setDetail(null);
    setDetailError('');
    try {
      setDetail(await fetchPolicyVersion(row.id, token));
    } catch (err) {
      setDetailError(err?.message || t('policyDeskLoadError'));
    }
  };

  const confirmPublish = async () => {
    if (!activeRow || dialogMode !== 'publish') return;
    setPublishing(true);
    setDetailError('');
    try {
      await publishPolicyVersion(activeRow.id, token);
      closeDialog();
      notify({ message: t('policyPublished'), type: 'success' });
      await loadData();
    } catch (err) {
      setDetailError(err?.message || t('policyPublishRefused'));
    } finally {
      setPublishing(false);
    }
  };

  const runSubmit = async (row) => {
    try {
      await submitPolicyVersion(row.id, token);
      notify({ message: t('policySubmitted'), type: 'success' });
      await loadData();
    } catch (err) {
      notify({ message: err?.message || t('policyPublishRefused'), type: 'error' });
    }
  };

  const columns = [
    { field: 'policy', headerName: t('policy'), flex: 1.2, minWidth: 160 },
    { field: 'version', headerName: t('policyVersion'), width: 110 },
    {
      field: 'state',
      headerName: t('policyState'),
      width: 150,
      renderCell: (p) => (
        <Chip
          size="small"
          variant="outlined"
          color={STATE_TONE[p.value] || 'default'}
          label={t(`policyState_${p.value}`, { defaultValue: p.value || '—' })}
        />
      ),
    },
    {
      field: 'citation',
      headerName: t('policyCitation'),
      flex: 1.6,
      minWidth: 220,
      renderCell: (p) => {
        const text = p.value || '—';
        return (
          <Tooltip title={text === '—' ? '' : text}>
            <Box
              component="span"
              sx={{
                display: 'block',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                width: '100%',
              }}
            >
              {text}
            </Box>
          </Tooltip>
        );
      },
    },
    { field: 'effective_date', headerName: t('policyEffective'), width: 118 },
    {
      field: 'actions',
      headerName: t('policyActions'),
      width: 96,
      sortable: false,
      renderCell: (p) => {
        const row = p.row;
        return (
          <Box sx={{ display: 'flex', gap: 0.25 }}>
            <Tooltip title={t('policyView')}>
              <IconButton
                size="small"
                aria-label={t('policyView')}
                onClick={(event) => {
                  event.stopPropagation();
                  openRecord(row, 'view');
                }}
              >
                <VisibilityIcon sx={{ fontSize: 16 }} />
              </IconButton>
            </Tooltip>
            {row.state === 'draft' && (
              <Tooltip title={t('policySubmit')}>
                <IconButton
                  size="small"
                  aria-label={t('policySubmit')}
                  onClick={(event) => {
                    event.stopPropagation();
                    runSubmit(row);
                  }}
                >
                  <PublishIcon sx={{ fontSize: 16 }} />
                </IconButton>
              </Tooltip>
            )}
            {row.state === 'in_review' && (
              <Tooltip title={t('policyPublish')}>
                <IconButton
                  size="small"
                  aria-label={t('policyPublish')}
                  onClick={(event) => {
                    event.stopPropagation();
                    openRecord(row, 'publish');
                  }}
                >
                  <PublishIcon sx={{ fontSize: 16 }} />
                </IconButton>
              </Tooltip>
            )}
          </Box>
        );
      },
    },
  ];

  const event = detail?.event;
  const citation = readCitation(detail, activeRow);
  const recordState = detail?.state || activeRow?.state;
  const publishingMode = dialogMode === 'publish';

  return (
    <>
      {loading ? (
        <LoadingSkeleton variant="table" />
      ) : error ? (
        <ErrorAlert message={error} onRetry={loadData} />
      ) : rows.length === 0 ? (
        <EmptyState icon={<PolicyIcon />} title={t('policyDeskEmpty')} description={t('policyDeskEmptyHint')} />
      ) : (
        <FilteredDataGrid
          title={t('policyDeskTitle')}
          subtitle={t('policyDeskSubtitle')}
          rows={visibleRows}
          columns={columns}
          getRowId={(row) => row.id}
          loading={false}
          searchValue={search}
          onSearchChange={setSearch}
          searchPlaceholder={t('policySearch')}
          filterDefs={[{
            key: 'state',
            label: t('policyState'),
            options: stateOptions,
          }]}
          filterValues={{ state: stateFilter }}
          onFilterChange={(_key, value) => setStateFilter(value || '')}
          onClearFilters={() => setStateFilter('')}
          pageSize={25}
          height={520}
          onRowClick={(gridParams) => setHighlightId(gridParams.id)}
          highlightRow={(row) => row.id === highlightId}
          dataGridProps={{ density: 'compact', disableRowSelectionOnClick: true }}
        />
      )}

      <SystemDialog
        open={Boolean(activeRow)}
        title={publishingMode ? t('policyPublishTitle') : t('policyViewTitle')}
        onClose={closeDialog}
        onCancel={closeDialog}
        cancelLabel={publishingMode ? undefined : tCommon('close')}
        height={560}
        actions={publishingMode ? (
          <Button size="small" variant="contained" onClick={confirmPublish} disabled={publishing || !detail}>
            {publishing ? t('policyWorking') : t('policyPublish')}
          </Button>
        ) : null}
      >
        <Stack spacing={1} sx={{ pt: 0.5 }}>
          {detailError ? <Alert severity="error">{detailError}</Alert> : null}
          {!detail && !detailError ? <LoadingSkeleton variant="table" /> : null}
          {detail ? (
            <>
              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
                <FormField label={t('policy')}>
                  <TextField size="small" fullWidth value={detail.policy || activeRow?.policy || ''} disabled inputProps={{ 'aria-label': t('policy') }} />
                </FormField>
                <FormField label={t('policyVersion')}>
                  <TextField size="small" fullWidth value={detail.version || activeRow?.version || ''} disabled inputProps={{ 'aria-label': t('policyVersion') }} />
                </FormField>
              </Stack>
              <Stack direction="row" spacing={1} alignItems="center">
                <Typography variant="body2">{t('policyState')}</Typography>
                <Chip
                  size="small"
                  variant="outlined"
                  color={STATE_TONE[recordState] || 'default'}
                  label={t(`policyState_${recordState}`, { defaultValue: recordState || '—' })}
                />
              </Stack>
              <Typography variant="body2">
                {t('policyExamples')}: {passLabel(t, detail.examples?.passed)}
              </Typography>
              <Typography variant="body2">
                {t('policyFloor')}: {passLabel(t, detail.floors?.passed)}
              </Typography>
              <Typography variant="body2" sx={{ whiteSpace: 'normal', overflowWrap: 'anywhere' }}>
                {citation ? `${t('policyCitation')}: ${citation}` : t('policyCitationMissing')}
              </Typography>
              <Typography variant="subtitle2">{t('policyDiff')}</Typography>
              {detail.diff?.length ? (
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>{t('policyField')}</TableCell>
                      <TableCell>{t('policyBefore')}</TableCell>
                      <TableCell>{t('policyAfter')}</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {detail.diff.map((line) => (
                      <TableRow key={line.field}>
                        <TableCell>{line.field}</TableCell>
                        <TableCell>{line.before || '—'}</TableCell>
                        <TableCell>{line.after || '—'}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <Typography variant="body2" color="text.secondary">{t('policyDiffEmpty')}</Typography>
              )}
              <Typography variant="subtitle2">{t('policyEvent')}</Typography>
              <Typography variant="body2">
                {event
                  ? `${event.action}: ${event.before?.lifecycle || '—'} → ${event.after?.lifecycle || '—'}`
                  : t('policyEventEmpty')}
              </Typography>
            </>
          ) : null}
        </Stack>
      </SystemDialog>
    </>
  );
}
