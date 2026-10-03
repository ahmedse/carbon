import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  Chip,
  FormControlLabel,
  Stack,
  Switch,
  TextField,
  Typography,
} from '@mui/material';
import UploadIcon from '@mui/icons-material/Upload';
import { useTranslation } from 'react-i18next';
import PageContainer from '../layout/PageContainer';
import PageHeader from '../Page/PageHeader';
import LoadingSkeleton from '../Page/LoadingSkeleton';
import ErrorAlert from '../Page/ErrorAlert';
import FilteredDataGrid from '../FilteredDataGrid';
import Wizard from '../Wizard/Wizard';
import { CsvDropzone, SearchSelect } from '../Form';
import FormField from '../Form/FormField';
import SystemDialog from '../SystemDialog';
import ConfirmDialog from '../ConfirmDialog';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../NotificationProvider';
import { fetchReferenceSets } from '../../api/catalog';
import {
  commitInboundBatch,
  downloadInboundRejects,
  fetchInboundBatch,
  fetchInboundTargets,
  fetchInboundTemplates,
  saveInboundMapping,
  saveInboundTemplate,
  smokeInboundBatch,
  uploadInboundFile,
} from '../../api/inbound';
import { INBOUND_STATUS_COLOR, inboundCaps, setInboundCrumb } from './inboundAccess';
import InboundStatRow from './InboundStatRow';
import InboundRowsViewer from './InboundRowsViewer';
import InboundExampleTemplates from './InboundExampleTemplates';
import {
  headersMatchIdentity,
  isIdentityMapping,
  pickOfficialIdentityTemplate,
  suggestColumnMap,
  unmappedRequired,
} from './suggestMap';

const ENCODINGS = [
  { value: 'utf-8', label: 'UTF-8' },
  { value: 'windows-1256', label: 'Windows-1256' },
  { value: 'cp1252', label: 'CP1252' },
];

function toList(data) {
  return Array.isArray(data) ? data : data?.results || [];
}

/**
 * Surface the official People · * template in Map when headers are identity.
 * Uses the same mapping merge as a SearchSelect apply. Never commits.
 */
async function applyOfficialIdentityIfMatch({
  token,
  tplList,
  hdrs,
  fieldDefs,
  existingCols,
  baseColumns,
  baseCrosswalks,
  targetKey,
  batchId,
  canPrepare,
  committed,
  setColumns,
  setCrosswalks,
  setTemplateId,
  setBatch,
  notifyFromError,
  mapFailedMsg,
}) {
  if (committed || !canPrepare || !batchId) return false;
  if (!headersMatchIdentity(hdrs || [], fieldDefs || [])) return false;
  const hasExisting = Object.values(existingCols || {}).some(Boolean);
  if (hasExisting && !isIdentityMapping(existingCols || {}, fieldDefs || [])) return false;
  const official = pickOfficialIdentityTemplate(tplList, fieldDefs, targetKey);
  if (!official?.mapping?.columns) return false;
  const next = { ...(baseColumns || {}), ...official.mapping.columns };
  const walks = { ...(baseCrosswalks || {}), ...(official.mapping.crosswalks || {}) };
  setColumns(next);
  setCrosswalks(walks);
  setTemplateId(String(official.id));
  try {
    const saved = await saveInboundMapping(token, batchId, {
      columns: next,
      crosswalks: walks,
    });
    setBatch(saved);
  } catch (err) {
    if (err?.status !== 400) notifyFromError(err, mapFailedMsg);
  }
  return true;
}

export default function InboundStudio({
  kind,
  listPath,
  ns = 'people',
  aliases = {},
  icon: Icon = UploadIcon,
}) {
  const { t } = useTranslation(ns);
  const { t: tCommon } = useTranslation('common');
  const { id } = useParams();
  const navigate = useNavigate();
  const { token, user, isGlobalAdminFlag, userCapabilities } = useAuth();
  const { notify, notifyFromError } = useNotification();

  const [batch, setBatch] = useState(null);
  const [fields, setFields] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [encoding, setEncoding] = useState('utf-8');
  const [columns, setColumns] = useState({});
  const [crosswalks, setCrosswalks] = useState({});
  const [busy, setBusy] = useState(false);
  const [allowPartial, setAllowPartial] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [walkField, setWalkField] = useState(null);
  const [walkOptions, setWalkOptions] = useState([]);
  const [walkDraft, setWalkDraft] = useState({});
  const [templateId, setTemplateId] = useState('');
  const [saveTplOpen, setSaveTplOpen] = useState(false);
  const [tplName, setTplName] = useState('');

  const { canPrepare, canCommit, canSee } = inboundCaps(userCapabilities, isGlobalAdminFlag);
  const readOnly = !canPrepare || batch?.status === 'committed';
  const title = batch?.original_filename || t('importTitle');
  useDocumentTitle(title);

  const load = useCallback(async () => {
    if (!token || !id) return;
    setLoading(true);
    setError(null);
    try {
      const [row, targetRes] = await Promise.all([
        fetchInboundBatch(token, id),
        fetchInboundTargets(token, kind),
      ]);
      setBatch(row);
      setEncoding(row.encoding || 'utf-8');
      const targets = toList(targetRes);
      const hit = targets.find((item) => item.key === row.target_key);
      const fieldDefs = hit?.fields || [];
      setFields(fieldDefs);
      const existing = { ...(row.mapping?.columns || {}) };
      const suggested = suggestColumnMap(row.headers || [], fieldDefs, aliases);
      const cols = {};
      (row.headers || []).forEach((h) => {
        cols[h] = existing[h] || suggested[h] || '';
      });
      setColumns(cols);
      const walks = row.mapping?.crosswalks || {};
      setCrosswalks(walks);
      setInboundCrumb(row.id, row.original_filename);
      if (
        row.status !== 'committed'
        && !Object.values(existing).some(Boolean)
        && Object.values(cols).some(Boolean)
      ) {
        try {
          const mapped = await saveInboundMapping(token, row.id, {
            columns: cols,
            crosswalks: walks,
          });
          setBatch(mapped);
        } catch (mapErr) {
          if (mapErr?.status !== 400) notifyFromError(mapErr, t('importMapFailed'));
        }
      }
      const tplRes = await fetchInboundTemplates(token, { kind, target_key: row.target_key });
      const tplList = toList(tplRes);
      setTemplates(tplList);
      setTemplateId('');
      await applyOfficialIdentityIfMatch({
        token,
        tplList,
        hdrs: row.headers || [],
        fieldDefs,
        existingCols: existing,
        baseColumns: cols,
        baseCrosswalks: walks,
        targetKey: row.target_key,
        batchId: row.id,
        canPrepare,
        committed: row.status === 'committed',
        setColumns,
        setCrosswalks,
        setTemplateId,
        setBatch,
        notifyFromError,
        mapFailedMsg: t('importMapFailed'),
      });
    } catch (err) {
      setError(err?.status === 403 ? 'forbidden' : (err.message || t('importLoadFailed')));
    } finally {
      setLoading(false);
    }
  }, [token, id, kind, aliases, t, notifyFromError, canPrepare]);

  useEffect(() => {
    load();
  }, [load]);

  const fieldByName = useMemo(
    () => Object.fromEntries(fields.map((f) => [f.name, f])),
    [fields],
  );
  const missingRequired = useMemo(
    () => unmappedRequired(columns, fields),
    [columns, fields],
  );
  const rejects = Number(batch?.reject_count ?? batch?.smoke?.reject ?? 0);
  const sodBlocked = Boolean(
    canCommit
    && batch?.prepared_by_username
    && user?.username
    && batch.prepared_by_username === user.username
    && isGlobalAdminFlag !== true,
  );

  const persistMapping = useCallback(async (nextColumns, nextWalks) => {
    if (!batch || readOnly) return;
    try {
      const next = await saveInboundMapping(token, batch.id, {
        columns: nextColumns,
        crosswalks: nextWalks,
      });
      setBatch(next);
    } catch (err) {
      if (err?.status !== 400) notifyFromError(err, t('importMapFailed'));
    }
  }, [batch, readOnly, token, notifyFromError, t]);

  const handleFile = async (file) => {
    if (!file || readOnly) return;
    setBusy(true);
    try {
      const next = await uploadInboundFile(token, id, file, encoding);
      setBatch(next);
      setInboundCrumb(next.id, next.original_filename);
      const suggested = suggestColumnMap(next.headers || [], fields, aliases);
      const existing = next.mapping?.columns || {};
      const merged = { ...suggested, ...Object.fromEntries(
        Object.entries(existing).filter(([, v]) => v),
      ) };
      (next.headers || []).forEach((h) => {
        if (!(h in merged)) merged[h] = suggested[h] || '';
      });
      setColumns(merged);
      const walks = next.mapping?.crosswalks || {};
      try {
        const mapped = await saveInboundMapping(token, next.id, {
          columns: merged,
          crosswalks: walks,
        });
        setBatch(mapped);
      } catch (mapErr) {
        if (mapErr?.status !== 400) notifyFromError(mapErr, t('importMapFailed'));
      }
      setTemplateId('');
      await applyOfficialIdentityIfMatch({
        token,
        tplList: templates,
        hdrs: next.headers || [],
        fieldDefs: fields,
        existingCols: existing,
        baseColumns: merged,
        baseCrosswalks: walks,
        targetKey: next.target_key,
        batchId: next.id,
        canPrepare,
        committed: false,
        setColumns,
        setCrosswalks,
        setTemplateId,
        setBatch,
        notifyFromError,
        mapFailedMsg: t('importMapFailed'),
      });
      notify({ message: t('importUploaded'), type: 'success' });
    } catch (err) {
      notifyFromError(err, t('importUploadFailed'));
    } finally {
      setBusy(false);
    }
  };

  const handleColumnChange = (header, target) => {
    const next = { ...columns, [header]: target || '' };
    setColumns(next);
    persistMapping(next, crosswalks);
  };

  const applyTemplate = (tpl) => {
    if (!tpl?.mapping?.columns) return;
    const next = { ...columns, ...tpl.mapping.columns };
    const walks = { ...crosswalks, ...(tpl.mapping.crosswalks || {}) };
    setColumns(next);
    setCrosswalks(walks);
    setTemplateId(String(tpl.id));
    persistMapping(next, walks);
    notify({ message: t('importTemplateApplied'), type: 'success' });
  };

  const downloadBlankHeader = () => {
    if (!fields.length) return;
    const header = fields.map((f) => f.name).join(',');
    const blob = new Blob([`${header}\n`], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const key = (batch?.target_key || 'inbound').replace(/[^\w.-]+/g, '_');
    a.download = `${key}.template.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const onSaveTemplate = async () => {
    if (!tplName.trim() || !batch) return;
    try {
      const saved = await saveInboundTemplate(token, {
        name: tplName.trim(),
        kind: batch.kind,
        target_key: batch.target_key,
        mapping: { columns, crosswalks },
      });
      setTemplates((prev) => {
        const rest = prev.filter((item) => item.id !== saved.id);
        return [...rest, saved];
      });
      setSaveTplOpen(false);
      setTplName('');
      notify({ message: t('importTemplateSaved'), type: 'success' });
    } catch (err) {
      notifyFromError(err, t('importTemplateFailed'));
    }
  };

  const runSmoke = async () => {
    setBusy(true);
    try {
      const next = await smokeInboundBatch(token, id);
      setBatch(next);
      notify({ message: t('importSmoked'), type: 'success' });
    } catch (err) {
      notifyFromError(err, t('importSmokeFailed'));
    } finally {
      setBusy(false);
    }
  };

  const onCommit = async () => {
    setBusy(true);
    try {
      const next = await commitInboundBatch(token, id, allowPartial);
      setBatch(next);
      setConfirmOpen(false);
      notify({ message: t('importCommitted'), type: 'success' });
      navigate(listPath);
    } catch (err) {
      notifyFromError(err, t('importCommitFailed'));
    } finally {
      setBusy(false);
    }
  };

  const onDownloadRejects = async () => {
    try {
      const blob = await downloadInboundRejects(token, id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `batch-${id}-rejects.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      notifyFromError(err, t('importRejectsFailed'));
    }
  };

  const openCrosswalk = async (fieldName) => {
    const field = fieldByName[fieldName];
    if (!field?.ref_set) return;
    setWalkField(field);
    setWalkDraft({ ...(crosswalks[fieldName] || {}) });
    try {
      const data = await fetchReferenceSets(token);
      const sets = toList(data);
      const set = sets.find(
        (s) => (s.name || '').toLowerCase() === field.ref_set.toLowerCase()
          || (s.slug || '').toLowerCase() === field.ref_set.toLowerCase(),
      );
      const values = toList(set?.values || set?.reference_values);
      setWalkOptions(values.map((v) => ({
        value: v.code,
        label: v.label || v.name || v.code,
      })));
    } catch (err) {
      notifyFromError(err, t('importCrosswalkFailed'));
      setWalkOptions([]);
    }
  };

  const sourceValuesFor = (fieldName) => {
    const header = Object.entries(columns).find(([, tgt]) => tgt === fieldName)?.[0];
    if (!header) return [];
    const seen = new Set();
    (batch?.sample || []).forEach((row) => {
      const v = row[header];
      if (v !== undefined && v !== '') seen.add(String(v));
    });
    return [...seen];
  };

  const sampleRows = useMemo(
    () => (batch?.sample || []).slice(0, 20).map((row, i) => ({ ...row, __i: i })),
    [batch],
  );
  const sampleCols = useMemo(
    () => (batch?.headers || []).slice(0, 30).map((h) => ({
      field: h,
      headerName: h,
      flex: 1,
      minWidth: 120,
    })),
    [batch],
  );
  const mapRows = useMemo(
    () => (batch?.headers || []).map((header) => ({
      id: header,
      header,
      target: columns[header] || '',
    })),
    [batch, columns],
  );
  const reconcileRows = useMemo(() => {
    const preview = batch?.smoke?.reconcile_preview || batch?.smoke?.commit?.reconcile || {};
    return Object.entries(preview).map(([key, value], i) => ({
      id: key, key, value: String(value), __i: i,
    }));
  }, [batch]);

  const startStep = useMemo(() => {
    if (!batch) return 0;
    if (['smoked', 'committed', 'failed'].includes(batch.status)) return 2;
    if (batch.status === 'mapped') return 1;
    return 0;
  }, [batch]);

  const fieldOptions = useMemo(() => [
    { value: '', label: t('importSkip') },
    ...fields.map((f) => ({
      value: f.name,
      label: f.required ? `${f.label} *` : f.label,
    })),
  ], [fields, t]);

  const steps = (() => {
    if (!batch) return [];
    const upload = {
      key: 'upload',
      label: t('importStepUpload'),
      validate: () => (
        (batch.headers || []).length
          ? { valid: true }
          : { valid: false, errors: [t('importUploadFirst')] }
      ),
      content: (
        <Stack spacing={1.5}>
          <FormField label={t('importEncoding')} helperText={t('importEncodingHint')}>
            <SearchSelect
              label={t('importEncoding')}
              value={encoding}
              onChange={(opt) => setEncoding(opt?.value || 'utf-8')}
              options={ENCODINGS}
              disabled={readOnly}
              clearable={false}
            />
          </FormField>
          <CsvDropzone
            onFile={handleFile}
            disabled={readOnly || busy}
            filename={batch.original_filename}
            emptyLabel={t('importNoFile')}
            chooseLabel={t('importChooseFile')}
            hint={t('importDropHint')}
          />
          {sampleCols.length > 0 && (
            <FilteredDataGrid
              embedded
              hideSearch
              rows={sampleRows}
              columns={sampleCols}
              getRowId={(row) => String(row.__i)}
              height={320}
              emptyMessage={t('importNoSample')}
              emptySubtext=""
              dataGridProps={{ hideFooter: true }}
            />
          )}
        </Stack>
      ),
    };

    const map = {
      key: 'map',
      label: t('importStepMap'),
      validate: () => (
        missingRequired.length
          ? { valid: false, errors: [t('importMapRequired', { fields: missingRequired.join(', ') })] }
          : { valid: true }
      ),
      content: (
        <Stack spacing={1.5}>
          {missingRequired.length > 0 && (
            <Alert severity="warning">
              {t('importMapRequired', { fields: missingRequired.join(', ') })}
            </Alert>
          )}
          <Stack direction="row" spacing={1} alignItems="flex-end" flexWrap="wrap" useFlexGap>
            <Box sx={{ minWidth: 240, flex: 1 }}>
              <FormField label={t('importTemplate')}>
                <SearchSelect
                  label={t('importTemplate')}
                  value={templateId}
                  onChange={(opt) => {
                    setTemplateId(opt?.value || '');
                    const tpl = templates.find((item) => String(item.id) === String(opt?.value));
                    if (tpl) applyTemplate(tpl);
                  }}
                  options={templates.map((item) => ({ value: String(item.id), label: item.name }))}
                  disabled={readOnly}
                />
              </FormField>
            </Box>
            {fields.length > 0 && (
              <Button size="small" variant="outlined" onClick={downloadBlankHeader}>
                {t('importDownloadBlankHeader')}
              </Button>
            )}
            <InboundExampleTemplates token={token} ns={ns} />
            {canPrepare && batch.status !== 'committed' && (
              <Button size="small" variant="outlined" onClick={() => setSaveTplOpen(true)}>
                {t('importSaveTemplate')}
              </Button>
            )}
          </Stack>
          <FilteredDataGrid
            embedded
            hideSearch
            rows={mapRows}
            columns={[
              { field: 'header', headerName: t('importColSource'), flex: 1, minWidth: 160 },
              {
                field: 'target',
                headerName: t('importColMappedField'),
                flex: 1,
                minWidth: 240,
                sortable: false,
                renderCell: (params) => (
                  <SearchSelect
                    value={params.row.target}
                    onChange={(opt) => handleColumnChange(params.row.header, opt?.value ?? '')}
                    options={fieldOptions}
                    disabled={readOnly}
                    size="small"
                  />
                ),
              },
              {
                field: 'required',
                headerName: t('importColRequired'),
                width: 110,
                valueGetter: (_v, row) => {
                  const field = fieldByName[row.target];
                  return field?.required ? t('yes') : t('no');
                },
              },
              {
                field: 'crosswalk',
                headerName: t('importColCrosswalk'),
                width: 140,
                sortable: false,
                renderCell: (params) => {
                  const field = fieldByName[params.row.target];
                  if (!field?.ref_set) return '—';
                  return (
                    <Button size="small" disabled={readOnly} onClick={() => openCrosswalk(field.name)}>
                      {t('importCrosswalk')}
                    </Button>
                  );
                },
              },
            ]}
            getRowId={(row) => row.id}
            height={420}
            emptyMessage={t('importUploadFirst')}
            dataGridProps={{ getRowHeight: () => 56, hideFooter: true }}
          />
        </Stack>
      ),
    };

    const smoke = {
      key: 'smoke',
      label: t('importStepSmoke'),
      // A committed batch has already passed smoke. Gating on 'smoked' alone
      // made reopening a committed batch (Wizard startStep 2) a dead end:
      // the Run-smoke button is hidden and Finish is disabled, so the only
      // Next click showed a false "Run smoke before continuing".
      validate: () => (
        ['smoked', 'committed'].includes(batch.status)
          ? { valid: true }
          : { valid: false, errors: [t('importSmokeFirst')] }
      ),
      content: (
        <Stack spacing={1.5}>
          {batch.status === 'committed' && (
            <Alert severity="info">{t('importCommittedReadOnly')}</Alert>
          )}
          <InboundStatRow
            items={['insert', 'update', 'skip', 'reject'].map((key) => ({
              key,
              label: t(`importSmoke_${key}`),
              value: batch.smoke?.[key] ?? 0,
              tone: key === 'reject' && rejects ? 'error' : undefined,
            }))}
          />
          <Stack direction="row" spacing={1}>
            {canPrepare && batch.status !== 'committed' && (
              <Button size="small" variant="outlined" disabled={busy} onClick={runSmoke}>
                {t('importRunSmoke')}
              </Button>
            )}
            {rejects > 0 && (
              <Button size="small" onClick={onDownloadRejects}>
                {t('importDownloadRejects')}
              </Button>
            )}
          </Stack>
          <Typography variant="caption" color="text.secondary">{t('importSmokeHint')}</Typography>
          <InboundRowsViewer
            token={token}
            batchId={batch.id}
            headers={batch.headers || []}
            ns={ns}
          />
        </Stack>
      ),
    };

    const commit = {
      key: 'commit',
      label: t('importStepCommit'),
      content: (
        <Stack spacing={1.5}>
          {sodBlocked && <Alert severity="warning">{t('importSodBanner')}</Alert>}
          <Typography variant="body2">
            {t('importCommitSummary', {
              target: batch.target_label || batch.target_key,
              insert: batch.smoke?.insert ?? 0,
              update: batch.smoke?.update ?? 0,
              reject: rejects,
            })}
          </Typography>
          {reconcileRows.length > 0 && (
            <FilteredDataGrid
              embedded
              hideSearch
              rows={reconcileRows}
              columns={[
                { field: 'key', headerName: t('importColReconcile'), flex: 1, minWidth: 160 },
                { field: 'value', headerName: t('importColCount'), width: 120 },
              ]}
              getRowId={(row) => row.id}
              height={220}
              dataGridProps={{ hideFooter: true }}
            />
          )}
          {rejects > 0 && (
            <FormControlLabel
              control={(
                <Switch
                  checked={allowPartial}
                  onChange={(e) => setAllowPartial(e.target.checked)}
                  disabled={batch.status === 'committed'}
                />
              )}
              label={t('importAllowPartial')}
            />
          )}
        </Stack>
      ),
    };

    return canCommit ? [upload, map, smoke, commit] : [upload, map, smoke];
  })();

  if (!canSee) {
    return (
      <PageContainer>
        <PageHeader icon={Icon} title={t('importTitle')} />
        <ErrorAlert message={t('importForbidden')} />
      </PageContainer>
    );
  }

  if (loading) {
    return (
      <PageContainer>
        <PageHeader icon={Icon} title={t('importTitle')} />
        <LoadingSkeleton variant="console" />
      </PageContainer>
    );
  }

  if (error || !batch) {
    return (
      <PageContainer>
        <PageHeader icon={Icon} title={t('importTitle')} />
        <ErrorAlert
          message={error === 'forbidden' ? t('importForbidden') : (error || t('importLoadFailed'))}
          onRetry={error === 'forbidden' ? undefined : load}
        />
      </PageContainer>
    );
  }

  const disableFinish = batch.status === 'committed'
    || (canCommit && (sodBlocked || (rejects > 0 && !allowPartial)));

  return (
    <PageContainer>
      <PageHeader
        icon={Icon}
        title={title}
        subtitle={batch.target_label || batch.target_key}
        badge={{
          label: t(`importStatus_${batch.status}`, { defaultValue: batch.status }),
          color: INBOUND_STATUS_COLOR[batch.status] || 'default',
        }}
      />
      <Box sx={{ flex: 1, minHeight: 0 }}>
        <Wizard
          key={`${batch.id}-${startStep}-${canCommit ? 'c' : 'p'}`}
          steps={steps}
          initialStep={startStep}
          onFinish={() => {
            if (!canCommit) {
              navigate(listPath);
              return;
            }
            setConfirmOpen(true);
          }}
          onCancel={() => navigate(listPath)}
          finishLabel={canCommit ? t('importCommit') : tCommon('done', { defaultValue: 'Done' })}
          nextLabel={t('wizardNext')}
          backLabel={t('wizardBack')}
          cancelLabel={tCommon('cancel')}
          submitting={busy}
          disableFinish={disableFinish}
        />
      </Box>
      <ConfirmDialog
        open={confirmOpen}
        title={t('importCommitTitle')}
        message={t('importCommitConfirm', {
          target: batch.target_label || batch.target_key,
          insert: batch.smoke?.insert ?? 0,
          update: batch.smoke?.update ?? 0,
        })}
        confirmLabel={t('importCommit')}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={onCommit}
      />
      <SystemDialog
        open={Boolean(walkField)}
        title={t('importCrosswalkTitle', { field: walkField?.label || '' })}
        onClose={() => setWalkField(null)}
        onCancel={() => setWalkField(null)}
        cancelLabel={tCommon('cancel')}
        actions={(
          <Button
            variant="contained"
            onClick={() => {
              const next = { ...crosswalks, [walkField.name]: walkDraft };
              setCrosswalks(next);
              persistMapping(columns, next);
              setWalkField(null);
            }}
          >
            {tCommon('save')}
          </Button>
        )}
      >
        <Stack spacing={1.5}>
          {sourceValuesFor(walkField?.name).map((src) => (
            <FormField key={src} label={src}>
              <SearchSelect
                value={walkDraft[src] || ''}
                onChange={(opt) => setWalkDraft((prev) => ({ ...prev, [src]: opt?.value || '' }))}
                options={walkOptions}
              />
            </FormField>
          ))}
          {walkField && sourceValuesFor(walkField.name).length === 0 && (
            <Typography variant="body2" color="text.secondary">{t('importCrosswalkEmpty')}</Typography>
          )}
        </Stack>
      </SystemDialog>
      <SystemDialog
        open={saveTplOpen}
        title={t('importSaveTemplate')}
        onClose={() => setSaveTplOpen(false)}
        onCancel={() => setSaveTplOpen(false)}
        cancelLabel={tCommon('cancel')}
        actions={(
          <Button variant="contained" disabled={!tplName.trim()} onClick={onSaveTemplate}>
            {tCommon('save')}
          </Button>
        )}
      >
        <FormField label={t('importTemplateName')} required>
          <TextField
            size="small"
            fullWidth
            value={tplName}
            onChange={(e) => setTplName(e.target.value)}
          />
        </FormField>
      </SystemDialog>
    </PageContainer>
  );
}
