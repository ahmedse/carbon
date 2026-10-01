// Campus intake for leaves that are not calculated yet.
// The catalogue quotes named files. This page does not invent a kilogram.

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Alert, Box, Button, TextField, Typography } from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';
import FactCheckIcon from '@mui/icons-material/FactCheck';
import { useTranslation } from 'react-i18next';

import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import EmptyState from '../../components/Page/EmptyState';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import WorkflowCard from '../../components/Cards/WorkflowCard';
import FilteredDataGrid from '../../components/FilteredDataGrid';
import { SearchSelect } from '../../components/Form';
import { enterCampusStream, fetchCampusIntake, uploadCampusIntake } from '../../api/emissions-extended';

function exclusionText(t, row) {
  return t(`intake.exclusion.${row.code}`, row);
}

const STATUS_KEY = {
  entered: 'intake.statusEntered',
  excluded: 'intake.statusExcluded',
  missing: 'intake.statusMissing',
  awaiting_factor: 'intake.statusAwaiting',
};

function statusLabel(t, status) {
  return t(STATUS_KEY[status] || 'intake.statusMissing');
}

function downloadTemplate(leaf) {
  const columns = leaf.template_columns || [];
  if (!columns.length) return;
  const blob = new Blob([`${columns.join(',')}\n`], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${leaf.id}-template.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

export default function CampusIntakePage() {
  const { t } = useTranslation('emissions');
  const { token } = useAuth();
  useDocumentTitle(t('intake.title'));

  const [phase, setPhase] = useState('loading');
  const [error, setError] = useState('');
  const [payload, setPayload] = useState(null);
  const [leafId, setLeafId] = useState('O2');
  const [uploadNote, setUploadNote] = useState('');
  const [streamId, setStreamId] = useState('');
  const [quantity, setQuantity] = useState('');
  const [dieselStream, setDieselStream] = useState('');
  const [method, setMethod] = useState('location_based');
  const [entryNote, setEntryNote] = useState('');

  const load = useCallback(async () => {
    setPhase('loading');
    setError('');
    try {
      const data = await fetchCampusIntake(token);
      setPayload(data && typeof data === 'object' ? data : { leaves: [] });
      setPhase('loaded');
    } catch (err) {
      setPayload(null);
      setError(err?.message || t('intake.loadFailed'));
      setPhase('error');
    }
  }, [token, t]);

  useEffect(() => {
    load();
  }, [load]);

  const leaves = Array.isArray(payload?.leaves) ? payload.leaves : [];
  const leaf = leaves.find((row) => row.id === leafId) || leaves[0] || null;
  const options = useMemo(
    () => leaves.map((row) => ({ value: row.id, label: `${row.id} · ${row.title}` })),
    [leaves],
  );
  const rows = (leaf?.activity_rows || []).map((row, index) => ({ id: index, ...row }));
  const streams = Array.isArray(payload?.streams) ? payload.streams : [];
  const stream = streams.find((row) => row.id === streamId) || null;
  const campuses = useMemo(() => {
    const names = [...new Set(streams.map((row) => row.campus).filter(Boolean))];
    return names.map((name) => ({ value: name, label: name }));
  }, [streams]);
  const sourceOptions = useMemo(
    () => streams
      .filter((row) => !stream?.campus || row.campus === stream.campus)
      .map((row) => ({ value: row.id, label: row.source_name })),
    [streams, stream?.campus],
  );
  const periodLabel = payload?.entry_period
    ? `${payload.entry_period.name} · ${payload.entry_period.start_date} – ${payload.entry_period.end_date}`
    : '';
  const o1Locked = stream?.leaf_id === 'O1' && stream?.status === 'entered';

  useEffect(() => {
    if (streamId || streams.length === 0) return;
    const next = streams.find((row) => row.status === 'missing' || row.status === 'awaiting_factor');
    if (next) setStreamId(next.id);
  }, [streamId, streams]);

  function chooseStream(next) {
    setStreamId(next?.id || '');
    setQuantity('');
    setDieselStream('');
    setMethod(next?.scope === 2 ? (next.method || 'location_based') : 'location_based');
    setEntryNote('');
  }

  async function onSaveStream() {
    if (!stream || o1Locked) return;
    try {
      const result = await enterCampusStream(token, {
        source_name: stream.source_name,
        quantity,
        stream: dieselStream,
        method: stream.scope === 2 ? method : '',
        treatment: stream.activity_type === 'waste' ? 'unspecified' : '',
      });
      if (result?.errors?.includes('org scope')) {
        setEntryNote(t('intake.notComplete'));
        return;
      }
      if (result?.exclusions?.some((row) => row.code === 'market_absent')) {
        setEntryNote(t('intake.marketAbsent'));
        return;
      }
      setEntryNote(result?.kilograms ? t('intake.savedEntered') : t('intake.savedAwaiting'));
      setQuantity('');
      await load();
    } catch (err) {
      setEntryNote(err?.message || t('intake.loadFailed'));
    }
  }

  async function onUpload(event) {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file || !leaf) return;
    const text = await file.text();
    const [header, ...body] = text.split(/\r?\n/).filter((line) => line.trim());
    const columns = (header || '').split(',').map((cell) => cell.trim());
    const parsed = body.map((line) => {
      const cells = line.split(',');
      return Object.fromEntries(columns.map((column, index) => [column, (cells[index] || '').trim()]));
    });
    try {
      const result = await uploadCampusIntake(token, leaf.id, parsed);
      setUploadNote(result?.kilograms ? String(result.kilograms) : t('intake.zeroTonnes'));
      await load();
    } catch (err) {
      setUploadNote(err?.message || t('intake.loadFailed'));
    }
  }

  return (
    <PageContainer>
      <PageHeader
        icon={FactCheckIcon}
        title={t('intake.title')}
        titleComponent="h1"
        subtitle={t('intake.subtitle')}
        description={t('intake.description')}
        actions={(
          <Button variant="contained" size="small" onClick={load}>
            {t('onboarding.refresh')}
          </Button>
        )}
      />

      {phase === 'loading' && <LoadingSkeleton variant="table" />}

      {phase === 'error' && (
        <Alert
          severity="error"
          action={(
            <Button color="inherit" size="small" onClick={load}>
              {t('common:retry')}
            </Button>
          )}
        >
          {error || t('intake.loadFailed')}
        </Alert>
      )}

      {phase === 'loaded' && (
        <Box sx={{ display: 'grid', gap: 1.5 }}>
          <Alert severity="info">{t('intake.notComplete')}</Alert>
          <Typography variant="h6">{t('intake.streamsTitle')}</Typography>
          <Typography variant="body2" color="text.secondary">{t('intake.streamsHint')}</Typography>

          {streams.length === 0 && (
            <EmptyState title={t('intake.emptyTitle')} description={t('intake.selectStream')} />
          )}
          {streams.length > 0 && (
            <FilteredDataGrid
              embedded
              title={t('intake.streamsTitle')}
              rows={streams}
              columns={[
                { field: 'campus', headerName: t('intake.campus'), flex: 1 },
                { field: 'source_name', headerName: t('intake.source'), flex: 1.4 },
                { field: 'scope', headerName: t('intake.scope'), width: 90 },
                { field: 'activity_type', headerName: t('intake.activityType'), width: 130 },
                { field: 'activity_unit', headerName: t('intake.unit'), width: 100 },
                {
                  field: 'status',
                  headerName: t('intake.status'),
                  width: 220,
                  valueGetter: (_value, row) => statusLabel(t, row.status),
                },
                {
                  field: 'inventory_kg',
                  headerName: t('intake.inventoryKg'),
                  width: 140,
                  valueGetter: (value) => (value == null || value === '' ? t('intake.kgAbsent') : String(value)),
                },
                {
                  field: 'later_year_files',
                  headerName: t('intake.laterYear'),
                  flex: 1,
                  valueGetter: (value) => (Array.isArray(value) && value.length ? value.join(', ') : ''),
                },
              ]}
              onRowClick={(params) => chooseStream(params?.row)}
              highlightRow={(row) => row.id === streamId}
              hideSearch
            />
          )}

          <WorkflowCard
            icon={<FactCheckIcon />}
            title={t('intake.enterTitle')}
            description={stream ? stream.source_name : t('intake.selectStream')}
            onClick={() => {
              if (!stream) {
                const missing = streams.find((row) => row.status === 'missing');
                if (missing) chooseStream(missing);
              }
            }}
          />

          {stream && (
            <Box sx={{ display: 'grid', gap: 1.25 }} component="form" onSubmit={(event) => { event.preventDefault(); onSaveStream(); }}>
              <SearchSelect
                label={t('intake.campus')}
                options={campuses}
                value={stream.campus}
                onChange={(option) => {
                  const next = streams.find((row) => row.campus === option?.value && row.status !== 'entered');
                  chooseStream(next || streams.find((row) => row.campus === option?.value) || null);
                }}
              />
              <SearchSelect
                label={t('intake.source')}
                options={sourceOptions}
                value={stream.id}
                onChange={(option) => chooseStream(streams.find((row) => row.id === option?.value) || null)}
              />
              <Typography variant="body2">
                {t('intake.period')}
                {': '}
                {periodLabel || t('intake.noPeriod')}
              </Typography>
              <Typography variant="body2">
                {t('intake.scope')}
                {' '}
                {stream.scope}
                {' · '}
                {t('intake.activityType')}
                {' '}
                {stream.activity_type}
                {' · '}
                {t('intake.unit')}
                {' '}
                {stream.activity_unit}
              </Typography>
              {stream.activity_type === 'diesel' && (
                <SearchSelect
                  label={t('intake.dieselStream')}
                  options={[
                    { value: 'generators', label: t('intake.generators') },
                    { value: 'fleet', label: t('intake.fleet') },
                  ]}
                  value={dieselStream}
                  onChange={(option) => setDieselStream(option?.value || '')}
                />
              )}
              {Number(stream.scope) === 2 && (
                <SearchSelect
                  label={t('intake.method')}
                  options={[
                    { value: 'location_based', label: t('intake.locationBased') },
                    { value: 'market_based', label: t('intake.marketBased') },
                  ]}
                  value={method}
                  onChange={(option) => setMethod(option?.value || 'location_based')}
                />
              )}
              <TextField
                label={t('intake.quantity')}
                value={quantity}
                onChange={(event) => setQuantity(event.target.value)}
                size="small"
                required
              />
              {o1Locked && <Alert severity="warning">{t('intake.o1Locked')}</Alert>}
              {!payload?.entry_period && <Alert severity="warning">{t('intake.noPeriod')}</Alert>}
              <Button
                type="submit"
                variant="contained"
                size="small"
                disabled={o1Locked || !payload?.entry_period || !quantity || (stream.activity_type === 'diesel' && !dieselStream)}
              >
                {t('intake.save')}
              </Button>
              <Typography variant="body2" color="text.secondary">{t('intake.enterHint')}</Typography>
            </Box>
          )}
          {entryNote && <Alert severity="info">{entryNote}</Alert>}

          <SearchSelect
            label={t('intake.leaf')}
            options={options}
            value={leaf?.id || ''}
            onChange={(option) => setLeafId(option?.value || 'O2')}
          />

          {leaf?.method === 'absent' && (
            <Alert severity="warning">{t('intake.marketAbsent')}</Alert>
          )}
          {leaf?.id === 'P1' && (
            <Alert severity="info">{t('intake.notAssured')}</Alert>
          )}
          {leaf && leaf.method !== 'absent' && leaf.id !== 'P1' && (
            <Typography variant="body1">{t('intake.zeroTonnes')}</Typography>
          )}
          {leaf && (
            <Typography variant="body2" color="text.secondary">
              {t('intake.outcome')}
              {' '}
              {t('intake.waitingFile', { file: leaf.waiting?.file || '' })}
              {' '}
              {t('intake.columns', { columns: (leaf.waiting?.columns || []).join(', ') })}
            </Typography>
          )}

          {leaf && (leaf.template_columns || []).length > 0 && (
            <WorkflowCard
              icon={<DownloadIcon />}
              title={t('intake.download')}
              description={t('intake.downloadHint')}
              onClick={() => downloadTemplate(leaf)}
            />
          )}

          {leaf && (leaf.template_columns || []).length > 0 && (
            <Button variant="outlined" component="label" size="small">
              {t('intake.upload')}
              <input hidden type="file" accept=".csv,text/csv" onChange={onUpload} />
            </Button>
          )}
          {uploadNote && <Alert severity="info">{uploadNote}</Alert>}

          {leaf && rows.length === 0 && leaf.method !== 'absent' && leaf.id !== 'P1' && (
            <EmptyState title={t('intake.emptyTitle')} description={t('intake.emptyDescription')} />
          )}

          {leaf && rows.length > 0 && (
            <FilteredDataGrid
              embedded
              title={t('intake.activity')}
              rows={rows}
              columns={[
                { field: 'label', headerName: t('intake.label'), flex: 1 },
                { field: 'quantity', headerName: t('intake.quantity'), width: 140 },
                { field: 'unit', headerName: t('intake.unit'), width: 100 },
                { field: 'source_file', headerName: t('intake.sourceFile'), flex: 1 },
              ]}
              hideSearch
            />
          )}

          {leaf && (leaf.exclusions || []).length > 0 && (
            <Box component="section" aria-label={t('intake.exclusions')}>
              <Typography variant="subtitle2">{t('intake.exclusions')}</Typography>
              {(leaf.exclusions || []).slice(0, 8).map((row) => (
                <Typography key={`${row.code}-${row.month || row.label || row.file || ''}`} variant="body2" color="text.secondary">
                  {exclusionText(t, row)}
                </Typography>
              ))}
            </Box>
          )}
        </Box>
      )}
    </PageContainer>
  );
}
