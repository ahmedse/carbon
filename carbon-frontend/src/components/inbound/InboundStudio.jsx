import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
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
import OperationProgress from '../OperationProgress';
import { useOperationProgress } from '../../hooks/useOperationProgress';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../NotificationProvider';
import { fetchReferenceSets } from '../../api/catalog';
import {
  commitInboundBatch,
  downloadInboundRejects,
  fetchInboundBatch,
  fetchInboundCommitRun,
  fetchInboundCommitRuns,
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

// Commit-run status → theme chip color. Status is ALWAYS shown as a chip PLUS a
// text label (RULE 5: never color alone).
const RUN_STATUS_COLOR = {
  queued: 'default',
  running: 'info',
  done: 'success',
  failed: 'error',
  canceled: 'default',
};

// Compact HH:MM:SS from an ISO timestamp. Falls back to '' for anything else.
function shortTime(value) {
  const match = String(value || '').match(/T(\d{2}:\d{2}:\d{2})/);
  return match ? match[1] : '';
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
  // Primitive identity for the load callback: the auth `user` object is not
  // referentially stable across renders.
  const username = user?.username || '';

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
  // ID2 commit progress: one durable run (queued → running → done|failed) shown
  // in a single SystemDialog. `commitLog` accumulates the batched progress lines.
  const [progressOpen, setProgressOpen] = useState(false);
  const [commitRun, setCommitRun] = useState(null);
  const [commitLog, setCommitLog] = useState([]);
  const [commitError, setCommitError] = useState(null);
  const commitInFlightRef = useRef(false);
  const runIdRef = useRef(null);
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

  // Any step jump (node click, Next, Back) drops a pending commit confirm and
  // any open crosswalk dialog — an approval must never survive an edit or a
  // step change. Only state is touched; no server call.
  const closeEditDialogs = useCallback(() => {
    setConfirmOpen(false);
    setWalkField(null);
    setWalkDraft({});
  }, []);

  // A file or mapping edit invalidates smoke + consent client-side. The server
  // already clears `smoke` and resets status on re-upload/re-map; this mirrors
  // it in the UI so the smoke stat row, rejects and the allow-partial consent
  // all reset from the same edit.
  const resetEditState = useCallback(() => {
    setAllowPartial(false);
    closeEditDialogs();
  }, [closeEditDialogs]);

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
      // A pure view open must not write. Only the preparer who owns the batch
      // gets the suggested mapping persisted on open, and only for a draft.
      const isPreparer = isGlobalAdminFlag === true
        || Boolean(username && row.prepared_by_username === username);
      if (
        canPrepare
        && isPreparer
        && row.status !== 'committed'
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
        canPrepare: canPrepare && isPreparer,
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
  }, [token, id, kind, aliases, t, notifyFromError, canPrepare, username, isGlobalAdminFlag]);

  useEffect(() => {
    load();
  }, [load]);

  // Keep the active run id in a ref so the shared SSE callback (registered once)
  // can filter frames without re-subscribing.
  useEffect(() => {
    runIdRef.current = commitRun?.id ?? null;
  }, [commitRun?.id]);

  // Live progress over the EXISTING shared SSE stream. While a commit is in
  // flight, `commitInFlightRef` lets us adopt the run id from the first import
  // frame (the client cannot know the id until the synchronous POST returns).
  const { connected } = useOperationProgress((frame) => {
    if (!frame || frame.op_type !== 'import') return;
    const knownId = runIdRef.current;
    const matches = knownId != null && String(frame.op_id) === String(knownId);
    if (!matches && !commitInFlightRef.current) return;
    if (knownId == null) runIdRef.current = frame.op_id;
    const entry = {
      t: frame.created_at || new Date().toISOString(),
      message: frame.message || '',
      percent: frame.percent,
    };
    setCommitLog((prev) => [...prev, entry]);
    setCommitRun((prev) => ({
      ...(prev || {}),
      id: frame.op_id,
      status: frame.status,
      progress: frame.percent ?? prev?.progress ?? 0,
      message: frame.message || prev?.message,
    }));
  });

  const commitRunActive = progressOpen
    && (!commitRun || ['queued', 'running'].includes(commitRun.status));

  // Disconnected fallback: no SSE, so recover the durable run record on a slow
  // interval until it is terminal. No poll while the stream is connected.
  useEffect(() => {
    if (connected || !commitRunActive) return undefined;
    const timer = setInterval(async () => {
      try {
        let run = null;
        if (runIdRef.current != null) {
          run = await fetchInboundCommitRun(token, id, runIdRef.current);
        } else {
          const listed = toList(await fetchInboundCommitRuns(token, id));
          run = listed[0] || null;
        }
        if (!run) return;
        runIdRef.current = run.id;
        setCommitRun(run);
        if (Array.isArray(run.log)) setCommitLog(run.log);
        if (run.status === 'failed') setCommitError(run.error || t('importCommitFailed'));
      } catch {
        // Transient — the next tick retries; SSE stays the primary path.
      }
    }, 2000);
    return () => clearInterval(timer);
  }, [connected, commitRunActive, token, id, t]);

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
    // A mapping change is an edit: drop any pending commit consent/dialog now,
    // before the round-trip, so a failed save cannot leave a stale approval.
    resetEditState();
    try {
      const next = await saveInboundMapping(token, batch.id, {
        columns: nextColumns,
        crosswalks: nextWalks,
      });
      setBatch(next);
    } catch (err) {
      if (err?.status !== 400) notifyFromError(err, t('importMapFailed'));
    }
  }, [batch, readOnly, token, notifyFromError, t, resetEditState]);

  const handleFile = async (file) => {
    if (!file || readOnly) return;
    // A new file invalidates the prior smoke and any pending commit consent.
    resetEditState();
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

  const onCommit = useCallback(async () => {
    // Close the confirm BEFORE the request so only ONE dialog is ever open;
    // then open the single progress surface keyed to this run.
    setConfirmOpen(false);
    setCommitError(null);
    setCommitLog([]);
    runIdRef.current = null;
    commitInFlightRef.current = true;
    setCommitRun({ status: 'queued', progress: 0 });
    setProgressOpen(true);
    setBusy(true);
    try {
      const res = await commitInboundBatch(token, id, allowPartial);
      const run = res?.commit_run || null;
      if (run) {
        runIdRef.current = run.id;
        setCommitRun(run);
        setCommitLog(Array.isArray(run.log) ? run.log : []);
        if (run.status === 'failed') setCommitError(run.error || t('importCommitFailed'));
      }
      setBatch(res);
    } catch (err) {
      // The failed run persists server-side; recover it from the error payload
      // so a Retry can safely re-post the same commit (replay-return is safe).
      const failedRun = err?.data?.commit_run || null;
      if (failedRun) {
        runIdRef.current = failedRun.id;
        setCommitRun(failedRun);
        setCommitLog(Array.isArray(failedRun.log) ? failedRun.log : []);
      } else {
        setCommitRun((prev) => ({ ...(prev || {}), status: 'failed' }));
      }
      setCommitError(err?.message || t('importCommitFailed'));
    } finally {
      commitInFlightRef.current = false;
      setBusy(false);
    }
  }, [token, id, allowPartial, t]);

  const handleProgressClose = useCallback(() => {
    const status = commitRun?.status;
    if (commitInFlightRef.current || status === 'queued' || status === 'running') return;
    setProgressOpen(false);
  }, [commitRun?.status]);

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

  // Clickable step nodes (opt-in Wizard). A step is reachable only at or before
  // the furthest step the batch's own state has already unlocked, so a node
  // click can never jump forward past a guard. The server still enforces every
  // guard (commit-before-smoke 409, re-smoke/re-map/re-upload on committed 409,
  // cross-kind 403, SoD); this only shapes the affordance.
  const maxClickableStep = useMemo(() => {
    const status = batch?.status;
    if (!(batch?.headers || []).length) return 0;
    if (status === 'draft') return 1;
    if (status === 'mapped') return 2;
    if (status === 'smoked') return canCommit ? 3 : 2;
    if (status === 'failed') return 2;
    if (status === 'committed') return canCommit ? 3 : 2;
    return 0;
  }, [batch, canCommit]);

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
              dataGridProps={{ density: 'compact', hideFooter: true }}
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
            dataGridProps={{ density: 'compact', getRowHeight: () => 56, hideFooter: true }}
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
            fields={fields}
            columnMap={columns}
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
              dataGridProps={{ density: 'compact', hideFooter: true }}
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

  const runStatus = commitRun?.status || 'queued';
  const runStatusLabel = runStatus === 'running'
    ? t('importCommitRunning')
    : runStatus === 'done'
      ? t('importCommitDone')
      : runStatus === 'failed'
        ? t('importCommitError')
        : t('importCommitQueued');
  const runTerminal = ['done', 'failed', 'canceled'].includes(runStatus);
  const progressActions = (
    <Stack direction="row" spacing={1}>
      {runStatus === 'failed' && (
        <Button variant="contained" disabled={busy} onClick={onCommit}>
          {t('importCommitRetry')}
        </Button>
      )}
      {runTerminal && (
        <Button variant="outlined" onClick={() => navigate(listPath)}>
          {t('importCommitOpenBatch')}
        </Button>
      )}
      {runTerminal && (
        <Button color="inherit" onClick={handleProgressClose}>
          {t('importCommitClose')}
        </Button>
      )}
    </Stack>
  );

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
          clickableSteps
          isStepEnabled={(index) => index <= maxClickableStep}
          onStepChange={closeEditDialogs}
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
      <SystemDialog
        open={progressOpen}
        title={t('importCommitProgressTitle')}
        onClose={handleProgressClose}
        onCancel={handleProgressClose}
        showCancel={false}
        cancelLabel={tCommon('close')}
        actions={progressActions}
      >
        <Stack spacing={1.5}>
          <Stack direction="row" spacing={1} alignItems="center" useFlexGap flexWrap="wrap">
            <Chip size="small" label={runStatusLabel} color={RUN_STATUS_COLOR[runStatus] || 'default'} />
            <Typography variant="caption" color="text.secondary">
              {t('importCommitAsUser', { user: username || '—' })}
            </Typography>
          </Stack>
          <Typography variant="caption" color="text.secondary">
            {t('importCommitSodLine', {
              preparer: commitRun?.prepared_by_username || batch.prepared_by_username || '—',
              committer: commitRun?.committed_by_username || username || '—',
            })}
          </Typography>
          <OperationProgress
            status={commitRun?.status}
            message={commitError || commitRun?.message}
            percent={commitRun?.progress}
          />
          {runStatus === 'done' && (
            <Stack direction="row" spacing={2} useFlexGap flexWrap="wrap">
              <Box>
                <Typography variant="caption" color="text.secondary">{t('importColCount')}</Typography>
                <Typography variant="mono">{commitRun?.written ?? 0}</Typography>
              </Box>
              {Object.entries(commitRun?.reconcile || {}).map(([key, value]) => (
                <Box key={key}>
                  <Typography variant="caption" color="text.secondary">{key}</Typography>
                  <Typography variant="mono">{String(value)}</Typography>
                </Box>
              ))}
            </Stack>
          )}
          {commitLog.length > 0 && (
            <Box>
              <Typography variant="subtitle2">{t('importCommitLogTitle')}</Typography>
              <Box
                data-testid="commit-log"
                sx={{
                  maxHeight: 220,
                  overflow: 'auto',
                  border: '1px solid',
                  borderColor: 'divider',
                  borderRadius: 1,
                  p: 1,
                }}
              >
                {commitLog.map((entry, index) => (
                  <Stack
                    key={`${entry.t}-${index}`}
                    direction="row"
                    spacing={1}
                    alignItems="baseline"
                  >
                    <Typography variant="mono" sx={{ color: 'text.disabled', flexShrink: 0 }}>
                      {shortTime(entry.t)}
                    </Typography>
                    <Typography variant="caption" sx={{ minWidth: 0, flex: 1 }}>
                      {entry.message}
                    </Typography>
                    {entry.percent != null && (
                      <Typography variant="mono" sx={{ color: 'text.secondary' }}>
                        {entry.percent}%
                      </Typography>
                    )}
                  </Stack>
                ))}
              </Box>
            </Box>
          )}
        </Stack>
      </SystemDialog>
    </PageContainer>
  );
}
