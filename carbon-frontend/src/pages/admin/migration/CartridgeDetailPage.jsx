import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Button, IconButton, TextField, Tooltip, Typography } from '@mui/material';
import CategoryIcon from '@mui/icons-material/Category';
import VisibilityRounded from '@mui/icons-material/VisibilityRounded';
import { useTranslation } from 'react-i18next';
import PageContainer from '../../../components/layout/PageContainer';
import PageHeader from '../../../components/Page/PageHeader';
import LoadingSkeleton from '../../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../../components/Page/ErrorAlert';
import FilteredDataGrid from '../../../components/FilteredDataGrid';
import FormField from '../../../components/Form/FormField';
import { SearchSelect } from '../../../components/Form';
import SystemDialog from '../../../components/SystemDialog';
import ConfirmDialog from '../../../components/ConfirmDialog';
import InboundStatRow from '../../../components/inbound/InboundStatRow';
import useDocumentTitle from '../../../hooks/useDocumentTitle';
import { useAuth } from '../../../auth/AuthContext';
import { useNotification } from '../../../components/NotificationProvider';
import {
  deleteInboundCartridge,
  fetchInboundCartridge,
  updateInboundCartridge,
} from '../../../api/inbound';

const LIST = '/admin/migration/cartridges';

export default function CartridgeDetailPage() {
  const { id } = useParams();
  const { t } = useTranslation('migration');
  const { t: tCommon } = useTranslation('common');
  const navigate = useNavigate();
  const { token } = useAuth();
  const { notifyFromError } = useNotification();
  const [row, setRow] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedName, setSelectedName] = useState(null);
  const [labelsOpen, setLabelsOpen] = useState(false);
  const [fieldOpen, setFieldOpen] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [inspect, setInspect] = useState(null);
  const [selectedBatchId, setSelectedBatchId] = useState(null);
  const [label, setLabel] = useState('');
  const [labelAr, setLabelAr] = useState('');
  const [fieldName, setFieldName] = useState('');
  const [fieldLabel, setFieldLabel] = useState('');
  const [required, setRequired] = useState('yes');
  const [editingName, setEditingName] = useState('');

  useDocumentTitle(row?.label || t('cartridgeTitle'));

  const load = useCallback(async () => {
    if (!token || !id) return;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchInboundCartridge(token, id);
      setRow(data);
      setLabel(data.label || '');
      setLabelAr(data.label_ar || '');
    } catch (err) {
      setError(err?.status === 403 ? 'forbidden' : (err.message || t('cartridgeLoadFailed')));
    } finally {
      setLoading(false);
    }
  }, [id, t, token]);

  useEffect(() => { load(); }, [load]);

  const fields = row?.fields || [];

  const save = async (patch) => {
    const next = await updateInboundCartridge(token, id, patch);
    setRow(next);
    return next;
  };

  const openField = useCallback((field) => {
    setEditingName(field?.name || '');
    setFieldName(field?.name || '');
    setFieldLabel(field?.label || '');
    setRequired(field?.required ? 'yes' : 'no');
    setFieldOpen(true);
  }, []);

  const openBatch = useCallback((batch) => {
    if (batch.kind === 'data_product') {
      navigate(`/catalog/imports/${batch.id}`);
      return;
    }
    if (row?.owner_app === 'people' && batch.kind === 'typed_object') {
      navigate(`/people/import/${batch.id}`);
      return;
    }
    setInspect(batch);
  }, [navigate, row?.owner_app]);

  const batchColumns = useMemo(() => [
    { field: 'id', headerName: t('cartridgeBatchId'), width: 90 },
    { field: 'status', headerName: t('cartridgeBatchStatus'), width: 130 },
    { field: 'original_filename', headerName: t('cartridgeBatchFile'), flex: 1, minWidth: 160 },
    {
      field: 'reject',
      headerName: t('cartridgeBatchReject'),
      width: 100,
      valueGetter: (value) => (value == null ? '—' : value),
    },
    {
      field: 'actions',
      headerName: t('cartridgeColActions'),
      width: 72,
      sortable: false,
      renderCell: (params) => (
        <Tooltip title={t('cartridgeOpenBatch')}>
          <IconButton
            size="small"
            color="primary"
            aria-label={t('cartridgeOpenBatch')}
            onClick={(event) => {
              event.stopPropagation();
              openBatch(params.row);
            }}
          >
            <VisibilityRounded fontSize="small" />
          </IconButton>
        </Tooltip>
      ),
    },
  ], [openBatch, t]);

  const onSaveField = async () => {
    const nextField = {
      name: fieldName.trim(),
      label: fieldLabel.trim(),
      required: required === 'yes',
    };
    const nextFields = editingName
      ? fields.map((field) => (field.name === editingName ? { ...field, ...nextField } : field))
      : [...fields, nextField];
    try {
      await save({ fields: nextFields });
      setFieldOpen(false);
    } catch (err) {
      notifyFromError(err, t('cartridgeSaveFailed'));
    }
  };

  const onRemoveField = async () => {
    if (fields.length < 2) return;
    try {
      await save({ fields: fields.filter((field) => field.name !== editingName) });
      setFieldOpen(false);
    } catch (err) {
      notifyFromError(err, t('cartridgeSaveFailed'));
    }
  };

  const columns = useMemo(() => [
    { field: 'name', headerName: t('cartridgeFieldName'), width: 180 },
    { field: 'label', headerName: t('cartridgeFieldLabel'), flex: 1, minWidth: 160 },
    {
      field: 'required',
      headerName: t('cartridgeRequired'),
      width: 120,
      valueGetter: (value) => (value ? t('cartridgeYes') : t('cartridgeNo')),
    },
    {
      field: 'actions',
      headerName: t('cartridgeColActions'),
      width: 72,
      sortable: false,
      renderCell: (params) => (
        <Tooltip title={t('cartridgeOpen')}>
          <IconButton
            size="small"
            color="primary"
            aria-label={t('cartridgeOpen')}
            onClick={(event) => {
              event.stopPropagation();
              openField(params.row);
            }}
          >
            <VisibilityRounded fontSize="small" />
          </IconButton>
        </Tooltip>
      ),
    },
  ], [openField, t]);

  if (loading) {
    return <PageContainer><LoadingSkeleton variant="console" /></PageContainer>;
  }
  if (error === 'forbidden') {
    return <PageContainer><ErrorAlert message={t('cartridgeForbidden')} /></PageContainer>;
  }
  if (error || !row) {
    return <PageContainer><ErrorAlert message={error || t('cartridgeLoadFailed')} onRetry={load} /></PageContainer>;
  }

  return (
    <PageContainer>
      <PageHeader
        icon={CategoryIcon}
        title={row.label}
        subtitle={`${row.key} · ${row.owner_app}`}
        description={t('cartridgeHandlerNote')}
        actions={(
          <>
            <Button size="small" onClick={() => setLabelsOpen(true)}>{t('cartridgeEditLabels')}</Button>
            <Button
              size="small"
              onClick={async () => {
                try { await save({ enabled: !row.enabled }); } catch (err) { notifyFromError(err, t('cartridgeSaveFailed')); }
              }}
            >
              {row.enabled ? t('cartridgeDisable') : t('cartridgeEnable')}
            </Button>
            <Button
              size="small"
              color="error"
              disabled={row.bound || row.batch_count > 0}
              onClick={() => setConfirmDelete(true)}
            >
              {t('cartridgeDelete')}
            </Button>
          </>
        )}
      />
      <InboundStatRow
        items={[
          { key: 'bound', label: t('cartridgeColBound'), value: row.bound ? t('cartridgeBound') : t('cartridgeUnbound') },
          { key: 'enabled', label: t('cartridgeColEnabled'), value: row.enabled ? t('cartridgeEnabled') : t('cartridgeDisabled') },
          { key: 'batches', label: t('cartridgeColBatches'), value: row.batch_count },
          { key: 'last', label: t('cartridgeColLast'), value: row.last_status || '—' },
        ]}
      />
      <PageHeader
        title={t('cartridgeFields')}
        actions={(
          <Button size="small" variant="contained" onClick={() => openField(null)}>
            {t('cartridgeAddField')}
          </Button>
        )}
      />
      <FilteredDataGrid
        embedded
        hideSearch
        rows={fields}
        columns={columns}
        getRowId={(field) => field.name}
        emptyMessage={t('cartridgeFieldsEmpty')}
        emptySubtext={t('cartridgeFieldsEmptyDesc')}
        pageSize={25}
        height={360}
        onRowClick={(params) => {
          const name = params.row.name;
          setSelectedName((prev) => (prev === name ? null : name));
        }}
        highlightRow={(field) => field.name === selectedName}
      />
      <PageHeader title={t('cartridgeRecent')} />
      <FilteredDataGrid
        embedded
        hideSearch
        rows={row.recent_batches || []}
        columns={batchColumns}
        getRowId={(batch) => batch.id}
        emptyMessage={t('cartridgeRecentEmpty')}
        emptySubtext={t('cartridgeRecentEmptyDesc')}
        pageSize={25}
        height={280}
        onRowClick={(params) => {
          const id = params.row.id;
          setSelectedBatchId((prev) => (prev === id ? null : id));
        }}
        highlightRow={(batch) => batch.id === selectedBatchId}
      />
      <SystemDialog
        open={labelsOpen}
        title={t('cartridgeEditLabels')}
        onClose={() => setLabelsOpen(false)}
        onCancel={() => setLabelsOpen(false)}
        cancelLabel={tCommon('cancel')}
        actions={(
          <Button
            variant="contained"
            disabled={!label.trim()}
            onClick={async () => {
              try {
                await save({ label: label.trim(), label_ar: labelAr.trim() });
                setLabelsOpen(false);
              } catch (err) {
                notifyFromError(err, t('cartridgeSaveFailed'));
              }
            }}
          >
            {tCommon('save')}
          </Button>
        )}
      >
        <FormField label={t('cartridgeLabel')} required>
          <TextField size="small" fullWidth value={label} onChange={(event) => setLabel(event.target.value)} />
        </FormField>
        <FormField label={t('cartridgeLabelAr')}>
          <TextField size="small" fullWidth value={labelAr} onChange={(event) => setLabelAr(event.target.value)} />
        </FormField>
      </SystemDialog>
      <SystemDialog
        open={fieldOpen}
        title={editingName ? t('cartridgeEditField') : t('cartridgeAddField')}
        onClose={() => setFieldOpen(false)}
        onCancel={() => setFieldOpen(false)}
        cancelLabel={tCommon('cancel')}
        actions={(
          <>
            {editingName && fields.length > 1 ? (
              <Button color="error" onClick={onRemoveField}>{tCommon('delete')}</Button>
            ) : null}
            <Button variant="contained" disabled={!fieldName.trim() || !fieldLabel.trim()} onClick={onSaveField}>
              {tCommon('save')}
            </Button>
          </>
        )}
      >
        <FormField label={t('cartridgeFieldName')} required>
          <TextField size="small" fullWidth value={fieldName} onChange={(event) => setFieldName(event.target.value)} />
        </FormField>
        <FormField label={t('cartridgeFieldLabel')} required>
          <TextField size="small" fullWidth value={fieldLabel} onChange={(event) => setFieldLabel(event.target.value)} />
        </FormField>
        <FormField label={t('cartridgeRequired')} required>
          <SearchSelect
            label={t('cartridgeRequired')}
            value={required}
            onChange={(opt) => setRequired(opt?.value ?? 'no')}
            options={[
              { value: 'yes', label: t('cartridgeYes') },
              { value: 'no', label: t('cartridgeNo') },
            ]}
          />
        </FormField>
      </SystemDialog>
      <SystemDialog
        open={Boolean(inspect)}
        title={t('cartridgeBatchInspect')}
        onClose={() => setInspect(null)}
        onCancel={() => setInspect(null)}
        cancelLabel={tCommon('close')}
      >
        <FormField label={t('cartridgeBatchFile')}>
          <TextField size="small" fullWidth value={inspect?.original_filename || '—'} InputProps={{ readOnly: true }} />
        </FormField>
        <FormField label={t('cartridgeBatchStatus')}>
          <TextField size="small" fullWidth value={inspect?.status || '—'} InputProps={{ readOnly: true }} />
        </FormField>
        <Typography variant="body2" color="text.secondary">{t('cartridgeBatchNoDoor')}</Typography>
      </SystemDialog>
      <ConfirmDialog
        open={confirmDelete}
        title={t('cartridgeDeleteTitle')}
        message={t('cartridgeDeleteBody')}
        destructive
        confirmLabel={tCommon('delete')}
        onCancel={() => setConfirmDelete(false)}
        onConfirm={async () => {
          try {
            await deleteInboundCartridge(token, id);
            navigate(LIST);
          } catch (err) {
            notifyFromError(err, t('cartridgeSaveFailed'));
            setConfirmDelete(false);
          }
        }}
      />
    </PageContainer>
  );
}
