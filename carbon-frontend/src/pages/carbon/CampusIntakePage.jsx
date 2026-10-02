// Campus intake — a verb reached FROM a coverage row.
// Coverage is the only surface that reports Missing / Entered / Excluded.
// This page quotes named files. It does not invent a kilogram.

import React, { useCallback, useEffect, useState } from 'react';
import { Alert, Box, Button, TextField, Typography } from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';
import FactCheckIcon from '@mui/icons-material/FactCheck';
import { useTranslation } from 'react-i18next';
import { useNavigate, useSearchParams } from 'react-router-dom';

import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import EmptyState from '../../components/Page/EmptyState';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import WorkflowCard from '../../components/Cards/WorkflowCard';
import FilteredDataGrid from '../../components/FilteredDataGrid';
import { SearchSelect } from '../../components/Form';
import {
  fetchCampusIntake,
  fetchCoverageRowSubmission,
  recordDiscoveredActivity,
  submitCoverageRow,
  uploadCampusIntake,
} from '../../api/emissions-extended';

function exclusionText(t, row) {
  return t(`intake.exclusion.${row.code}`, row);
}

function periodRoleLabel(t, role) {
  if (role === 'locked') return t('intake.periodLocked');
  if (role === 'closed') return t('intake.periodClosed');
  return t('intake.periodOpen');
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
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const sourceParam = searchParams.get('source');
  useDocumentTitle(t('intake.title'));

  const [phase, setPhase] = useState('loading');
  const [error, setError] = useState('');
  const [payload, setPayload] = useState(null);
  const [leafId, setLeafId] = useState('O2');
  const [uploadNote, setUploadNote] = useState('');
  const [recordNote, setRecordNote] = useState('');

  // Coverage-driven submission: the row decides campus, scope, unit, period.
  const [coverageRow, setCoverageRow] = useState(null);
  const [coveragePhase, setCoveragePhase] = useState('idle');
  const [coverageError, setCoverageError] = useState('');
  const [coverageNote, setCoverageNote] = useState('');
  const [quantity, setQuantity] = useState('');
  const [dieselStream, setDieselStream] = useState('');
  const [method, setMethod] = useState('location_based');

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

  const loadCoverageRow = useCallback(async () => {
    if (!sourceParam) {
      setCoverageRow(null);
      setCoveragePhase('idle');
      return;
    }
    setCoveragePhase('loading');
    setCoverageError('');
    try {
      const data = await fetchCoverageRowSubmission(sourceParam, token);
      setCoverageRow(data && typeof data === 'object' ? data : null);
      setCoveragePhase('loaded');
    } catch (err) {
      setCoverageRow(null);
      setCoverageError(err?.message || t('intake.loadFailed'));
      setCoveragePhase('error');
    }
  }, [sourceParam, token, t]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    loadCoverageRow();
  }, [loadCoverageRow]);

  const leaves = Array.isArray(payload?.leaves) ? payload.leaves : [];
  const leaf = leaves.find((row) => row.id === leafId) || leaves[0] || null;
  const options = leaves.map((row) => ({ value: row.id, label: `${row.id} · ${row.title}` }));
  const rows = (leaf?.activity_rows || []).map((row, index) => ({ id: index, ...row }));
  const streams = Array.isArray(payload?.streams) ? payload.streams : [];
  const historyBoards = (Array.isArray(payload?.periods) ? payload.periods : [])
    .filter((row) => row.role === 'locked' || row.role === 'closed');
  const contract = coverageRow?.contract || {};
  const requiredFields = Array.isArray(contract.required) ? contract.required : [];
  const optionalFields = Array.isArray(contract.optional) ? contract.optional : [];
  const periodLabel = payload?.entry_period
    ? `${payload.entry_period.name} · ${payload.entry_period.start_date} – ${payload.entry_period.end_date}`
    : '';

  const openCoverageRow = (row) => {
    const id = row?.inventory_source_id;
    if (id) navigate(`/carbon/onboarding/intake?source=${id}`);
  };

  async function onRecordDiscovered() {
    try {
      const result = await recordDiscoveredActivity(token);
      const lockedMissing = (result?.exclusions || []).some((row) => row.code === 'locked_period_absent');
      setRecordNote(lockedMissing ? t('intake.lockedAbsent') : t('intake.recorded'));
      await load();
    } catch (err) {
      setRecordNote(err?.message || t('intake.loadFailed'));
    }
  }

  async function onSaveCoverageRow() {
    if (!sourceParam || !coverageRow) return;
    const body = { quantity };
    if (requiredFields.includes('stream')) body.stream = dieselStream;
    if (optionalFields.includes('method')) body.method = method;
    if (contract.activity_type === 'waste') body.treatment = 'unspecified';
    try {
      const result = await submitCoverageRow(sourceParam, body, token);
      if ((result?.errors || []).some((code) => code === 'contract_fields' || code === 'contract_value')) {
        setCoverageNote(t('intake.contractRejected'));
        return;
      }
      if (result?.errors?.includes('org scope')) {
        setCoverageNote(t('intake.notComplete'));
        return;
      }
      if (result?.exclusions?.some((row) => row.code === 'market_absent')) {
        setCoverageNote(t('intake.marketAbsent'));
        return;
      }
      setCoverageNote(result?.kilograms ? t('intake.savedEntered') : t('intake.savedAwaiting'));
      setQuantity('');
      setDieselStream('');
      await Promise.all([loadCoverageRow(), load()]);
    } catch (err) {
      setCoverageNote(err?.message || t('intake.loadFailed'));
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
          <Button variant="contained" size="small" onClick={() => { load(); loadCoverageRow(); }}>
            {t('onboarding.refresh')}
          </Button>
        )}
      />

      {/* Coverage-driven submission. The row decides campus, scope, unit, period. */}
      {sourceParam && (
        <Box sx={{ display: 'grid', gap: 1.25, mb: 2 }}>
          <Alert severity="info">{t('intake.drivenByCoverage')}</Alert>
          {coveragePhase === 'loading' && <LoadingSkeleton variant="table" />}
          {coveragePhase === 'error' && (
            <Alert
              severity="error"
              action={(
                <Button color="inherit" size="small" onClick={loadCoverageRow}>
                  {t('common:retry')}
                </Button>
              )}
            >
              {coverageError || t('intake.loadFailed')}
            </Alert>
          )}
          {coveragePhase === 'loaded' && coverageRow && (
            <Box
              component="form"
              onSubmit={(event) => { event.preventDefault(); onSaveCoverageRow(); }}
              sx={{ display: 'grid', gap: 1.25 }}
            >
              <Typography variant="subtitle1">{coverageRow.source_name}</Typography>
              <Typography variant="body2">
                {t('intake.campus')}
                {': '}
                {coverageRow.campus}
                {' · '}
                {t('intake.scope')}
                {' '}
                {coverageRow.scope}
                {' · '}
                {t('intake.unit')}
                {' '}
                {contract.activity_unit || '—'}
              </Typography>
              <Typography variant="body2">
                {t('intake.period')}
                {': '}
                {periodLabel || t('intake.noPeriod')}
              </Typography>
              <Alert severity={contract.source === 'datatable' ? 'success' : 'info'}>
                {contract.source === 'datatable'
                  ? t('intake.contractDatatable')
                  : t('intake.contractFixture')}
              </Alert>
              {requiredFields.includes('quantity') && (
                <TextField
                  label={t('intake.quantity')}
                  value={quantity}
                  onChange={(event) => setQuantity(event.target.value)}
                  size="small"
                  required
                />
              )}
              {requiredFields.includes('stream') && (
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
              {optionalFields.includes('method') && (
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
              {!payload?.entry_period && <Alert severity="warning">{t('intake.noPeriod')}</Alert>}
              <Button
                type="submit"
                variant="contained"
                size="small"
                disabled={!quantity || (requiredFields.includes('stream') && !dieselStream)}
              >
                {t('intake.save')}
              </Button>
              <Typography variant="body2" color="text.secondary">{t('intake.enterHint')}</Typography>
              {coverageNote && <Alert severity="info">{coverageNote}</Alert>}
            </Box>
          )}
        </Box>
      )}

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
                  field: 'inventory_source_id',
                  headerName: t('intake.coverageRow'),
                  width: 160,
                  renderCell: (params) => (params.value ? (
                    <Button size="small" onClick={() => openCoverageRow(params.row)}>
                      {t('intake.openRow')}
                    </Button>
                  ) : '—'),
                },
                {
                  field: 'later_year_files',
                  headerName: t('intake.laterYear'),
                  flex: 1,
                  valueGetter: (value) => (Array.isArray(value) && value.length ? value.join(', ') : ''),
                },
              ]}
              onRowClick={(params) => openCoverageRow(params?.row)}
              highlightRow={(row) => String(row.inventory_source_id) === String(sourceParam)}
              hideSearch
            />
          )}

          <WorkflowCard
            icon={<FactCheckIcon />}
            title={t('intake.recordDiscovered')}
            description={t('intake.recordDiscoveredHint')}
            onClick={onRecordDiscovered}
          />
          {recordNote && <Alert severity="info">{recordNote}</Alert>}

          {historyBoards.map((board) => (
            <Box key={board.id}>
              <Typography variant="h6">
                {t('intake.streamsFor', { name: board.name, status: periodRoleLabel(t, board.role) })}
              </Typography>
              <FilteredDataGrid
                embedded
                title={board.name}
                rows={board.streams || []}
                columns={[
                  { field: 'campus', headerName: t('intake.campus'), flex: 1 },
                  { field: 'source_name', headerName: t('intake.source'), flex: 1.4 },
                  { field: 'scope', headerName: t('intake.scope'), width: 90 },
                  {
                    field: 'inventory_kg',
                    headerName: t('intake.inventoryKg'),
                    width: 140,
                    valueGetter: (value) => (value == null || value === '' ? t('intake.kgAbsent') : String(value)),
                  },
                ]}
                hideSearch
              />
            </Box>
          ))}

          {/* Entry is reached from a coverage row. No blank generic form here. */}
          <WorkflowCard
            icon={<FactCheckIcon />}
            title={t('intake.enterTitle')}
            description={sourceParam ? t('intake.drivenByCoverage') : t('intake.coverageFirst')}
            onClick={() => navigate('/carbon/admin/inventory-coverage')}
          />

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
