// Run workbench — LCT results + HITL code edit (SystemDialog) + release + audit export.

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import {
  Alert, Box, Button, Chip, FormControl, InputLabel, MenuItem, Paper,
  Select, Stack, Table, TableBody, TableCell, TableHead, TableRow, TextField, Typography,
} from '@mui/material';
import ScienceIcon from '@mui/icons-material/Science';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../components/Page/ErrorAlert';
import SystemDialog from '../../components/SystemDialog';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import {
  fetchAgsPreview, fetchAuditExport, fetchRun, postAgsPassback, postExpertEdit, releaseRun,
  suggestSegmentationSplits,
} from '../../api/gradevance';
import SkipToMain from './SkipToMain';
import WaveChart from './WaveChart';
import LctCodesTable from './LctCodesTable';
import SegmentationEditor, { suggestSplitPoints, buildSegDraft } from '../../components/gradevance/SegmentationEditor';
import OpsCanvasAttachButton from '../people/OpsCanvasAttachButton';

const FALLBACK_SG = ['SG+', 'SG-'];
const FALLBACK_SD = ['SD-', 'SD+'];
const SG_NUMERIC_FALLBACK = { 'SG+': 1, 'SG-': 2, 'SG++': 1, 'SG--': 2 };

function codeFor(seg, dimension) {
  const codes = seg?.codes || [];
  return codes.find((c) => c.dimension === dimension) || null;
}

function downloadJson(filename, data) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function ExpertEditsPanel({ edits = [] }) {
  if (!edits.length) {
    return (
      <Typography variant="caption" color="text.secondary">
        No ExpertEdits yet — HITL changes appear here as append-only learning evidence.
      </Typography>
    );
  }
  return (
    <Table size="small" aria-label="Expert edit history">
      <TableHead>
        <TableRow>
          <TableCell>When</TableCell>
          <TableCell>Kind</TableCell>
          <TableCell>Before → After</TableCell>
          <TableCell>Rationale</TableCell>
        </TableRow>
      </TableHead>
      <TableBody>
        {edits.map((e) => {
          const before = e.before?.value ?? e.before?.band ?? '—';
          const after = e.after?.value ?? e.after?.band ?? (e.after?.released ? 'released' : '—');
          const dim = e.after?.dimension || e.before?.dimension || '';
          return (
            <TableRow key={e.id} hover>
              <TableCell>
                <Typography variant="caption">
                  {e.created_at ? new Date(e.created_at).toLocaleString() : '—'}
                </Typography>
              </TableCell>
              <TableCell>
                <Chip size="small" label={e.edit_kind || '—'} variant="outlined" />
                {dim && (
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                    {dim}
                  </Typography>
                )}
              </TableCell>
              <TableCell>
                <Typography variant="body2">{before} → {after}</Typography>
              </TableCell>
              <TableCell sx={{ maxWidth: 360 }}>
                <Typography variant="body2">{e.rationale || '—'}</Typography>
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}

export default function RunWorkbenchPage() {
  const { pathname } = useLocation();
  const titlePrefix = pathname.startsWith('/teach') ? 'Teach' : 'GradeVance';
  useDocumentTitle(`${titlePrefix} · Run`);
  const { runId } = useParams();
  const { token } = useAuth();
  const navigate = useNavigate();

  const [run, setRun] = useState(null);
  const [fairness, setFairness] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const [agsInfo, setAgsInfo] = useState(null);
  const [lineitem, setLineitem] = useState('');

  const [editOpen, setEditOpen] = useState(false);
  const [editSeg, setEditSeg] = useState(null);
  const [editDim, setEditDim] = useState('semantic_gravity');
  const [editValue, setEditValue] = useState('');
  const [editRationale, setEditRationale] = useState('');
  const [segOpen, setSegOpen] = useState(false);
  const [segDraft, setSegDraft] = useState(null);
  const [segRationale, setSegRationale] = useState('');
  const [segEditorKey, setSegEditorKey] = useState(0);
  const [segSuggestions, setSegSuggestions] = useState(null);

  const sgLevels = useMemo(
    () => run?.lct_scale?.semantic_gravity?.levels || FALLBACK_SG,
    [run],
  );
  const sdLevels = useMemo(
    () => run?.lct_scale?.semantic_density?.levels || FALLBACK_SD,
    [run],
  );
  const sgNumericMap = useMemo(() => {
    const levels = sgLevels;
    const nums = run?.lct_scale?.semantic_gravity?.numeric;
    if (Array.isArray(nums) && nums.length === levels.length) {
      return Object.fromEntries(levels.map((lv, i) => [lv, nums[i]]));
    }
    return SG_NUMERIC_FALLBACK;
  }, [run, sgLevels]);

  const load = useCallback(() => {
    if (!runId) return;
    setLoading(true);
    setError(null);
    fetchRun(token, runId)
      .then(async (data) => {
        setRun(data);
        const preview = await fetchAgsPreview(token, runId).catch((e) => ({
          detail: e.message,
          allowed: false,
        }));
        setAgsInfo(preview);
        if (preview.lineitem_url) setLineitem(preview.lineitem_url);

        const fromRun = data.fairness || null;
        if (fromRun) {
          setFairness(fromRun);
        } else {
          try {
            const audit = await fetchAuditExport(token, runId);
            setFairness(audit.fairness || null);
          } catch {
            setFairness({
              mode: data.assignment?.mode || data.mode,
              released: data.released,
              advisory_only: data.coaching?.watermark === 'advisory' && !data.released,
              watermark: data.coaching?.watermark,
            });
          }
        }
      })
      .catch((e) => setError(e?.message || 'Failed to load run'))
      .finally(() => setLoading(false));
  }, [token, runId]);

  useEffect(() => { load(); }, [load]);

  const assignment = useMemo(() => run?.assignment || null, [run]);
  const assignmentId = assignment?.id || null;
  const levels = editDim === 'semantic_density' ? sdLevels : sgLevels;
  const fair = fairness || {};
  const beforeCode = editSeg ? codeFor(editSeg, editDim) : null;

  const openEdit = (seg, dimension) => {
    const existing = codeFor(seg, dimension);
    const defaults = dimension === 'semantic_density' ? sdLevels : sgLevels;
    setEditSeg(seg);
    setEditDim(dimension);
    setEditValue(existing?.value || defaults[0] || 'SG+');
    setEditRationale('');
    setEditOpen(true);
  };

  const openSegmentation = () => {
    const payload = (run?.segments || []).map((s) => ({
      id: s.id,
      ordinal: s.ordinal,
      start_word: s.start_word,
      end_word: s.end_word,
      stage_guess: s.stage_guess || 'what',
      text: s.text || '',
    }));
    setSegDraft(payload);
    setSegRationale('');
    setSegSuggestions(null);
    setSegEditorKey((k) => k + 1);
    setSegOpen(true);
  };

  const requestSegSuggestions = async () => {
    const full = run?.submission_detail?.text || '';
    const segs = segDraft || run?.segments || [];
    try {
      const res = await suggestSegmentationSplits(token, { text: full, segments: segs });
      if (res?.suggestions?.length) {
        setSegSuggestions(res.suggestions);
        return;
      }
    } catch {
      /* fall through to local heuristic */
    }
    const { words, draft } = buildSegDraft(segs, full);
    setSegSuggestions(suggestSplitPoints(words, draft, 6));
  };

  const saveSegmentation = async () => {
    if (!segRationale.trim()) {
      setError('Rationale required for segmentation ExpertEdit');
      return;
    }
    if (!Array.isArray(segDraft) || !segDraft.length) {
      setError('Add at least one segment before saving');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const before = (run?.segments || []).map((s) => ({
        id: s.id,
        ordinal: s.ordinal,
        start_word: s.start_word,
        end_word: s.end_word,
        stage_guess: s.stage_guess,
        text: s.text,
      }));
      await postExpertEdit(token, runId, {
        edit_kind: 'segment_boundary',
        before: { segments: before },
        after: { segments: segDraft },
        rationale: segRationale.trim(),
      });
      setMsg('Segmentation ExpertEdit saved — engine re-coded atoms; learning loop may draft a policy proposal');
      setSegOpen(false);
      load();
    } catch (e) {
      setError(e?.message || 'Segmentation edit failed');
    } finally {
      setBusy(false);
    }
  };

  const closeEdit = () => {
    setEditOpen(false);
    setEditSeg(null);
    setEditRationale('');
  };

  const saveEdit = async () => {
    if (!editSeg || !editRationale.trim()) {
      setError('Rationale required for ExpertEdit');
      return;
    }
    setBusy(true);
    setError(null);
    setMsg(null);
    try {
      await postExpertEdit(token, runId, {
        edit_kind: 'lct_code',
        before: {
          segment_id: editSeg.id,
          dimension: editDim,
          value: beforeCode?.value || null,
        },
        after: {
          segment_id: editSeg.id,
          dimension: editDim,
          value: editValue,
          numeric: editDim === 'semantic_gravity' ? (sgNumericMap[editValue] ?? null) : null,
        },
        rationale: editRationale.trim(),
      });
      setMsg('ExpertEdit saved — learning loop may draft a Proposal');
      closeEdit();
      load();
    } catch (e) {
      setError(e?.message || 'Edit failed');
    } finally {
      setBusy(false);
    }
  };

  const onRelease = async () => {
    setBusy(true);
    setError(null);
    try {
      await releaseRun(token, runId);
      setMsg('Run released');
      load();
    } catch (e) {
      setError(e?.message || 'Release failed');
    } finally {
      setBusy(false);
    }
  };

  const onExportAudit = async () => {
    setBusy(true);
    setError(null);
    try {
      const payload = await fetchAuditExport(token, runId);
      if (payload.fairness) setFairness(payload.fairness);
      downloadJson(`audit-run-${runId}.json`, payload);
      setMsg('Audit export downloaded');
    } catch (e) {
      setError(e?.message || 'Audit export failed');
    } finally {
      setBusy(false);
    }
  };

  const onAgsPassback = async () => {
    if (!lineitem.trim()) {
      setError('Lineitem URL required for AGS passback');
      return;
    }
    setBusy(true);
    try {
      const result = await postAgsPassback(token, runId, {
        lineitem_url: lineitem.trim(),
        dry_run: true,
      });
      setAgsInfo((prev) => ({ ...prev, passback: result }));
    } catch (e) {
      setError(e?.message || 'AGS passback failed');
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <PageContainer>
        <PageHeader icon={ScienceIcon} title="Run workbench" subtitle="LCT · HITL · release" />
        <LoadingSkeleton variant="console" />
      </PageContainer>
    );
  }

  if (error && !run) {
    return (
      <PageContainer>
        <PageHeader icon={ScienceIcon} title="Run workbench" />
        <ErrorAlert message={error} onRetry={load} />
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <SkipToMain targetId="gv-run-workbench" />
      <Box component="main" id="gv-run-workbench" tabIndex={-1} aria-label="Run workbench">
        <PageHeader
          icon={ScienceIcon}
          title="Run workbench"
          subtitle="Measure meaning → edit with rationale → release with ceremony."
          badge={run?.released ? { label: 'released', color: 'success' } : { label: 'unreleased', color: 'default' }}
          actions={(
            <Stack direction="row" spacing={0.75} alignItems="center" flexWrap="wrap" useFlexGap>
              <OpsCanvasAttachButton
                relatedType="gradevance.AssessmentRun"
                relatedId={runId}
                relatedLabel={assignment?.title || `Run ${runId}`}
              />
              <Button size="small" variant="outlined" onClick={onExportAudit} disabled={busy} aria-busy={busy}>
                Export audit
              </Button>
              {assignmentId && (
                <Button size="small" variant="outlined" onClick={() => navigate(`/teach/stems/${assignmentId}`)}>
                  Assignment hub
                </Button>
              )}
              {!run?.released && (
                <Button size="small" variant="contained" onClick={onRelease} disabled={busy}>
                  Release
                </Button>
              )}
            </Stack>
          )}
        />
        {error && <ErrorAlert message={error} onRetry={load} />}
        {msg && <Alert severity="success" sx={{ mb: 1.5 }} role="status">{msg}</Alert>}

        <Stack direction="row" spacing={1} sx={{ mb: 1.5, flexWrap: 'wrap' }} useFlexGap aria-label="Run and fairness status">
          <Chip size="small" label={run?.status || '—'} />
          <Chip size="small" label={`gate ${run?.gate_decision || '—'}`} variant="outlined" />
          <Chip
            size="small"
            label={run?.mean_confidence != null ? `conf ${Number(run.mean_confidence).toFixed(2)}` : 'conf —'}
          />
          {(fair.mode || assignment?.mode) && (
            <Chip size="small" label={`mode: ${fair.mode || assignment?.mode}`} variant="outlined" />
          )}
          <Chip
            size="small"
            color={(fair.released ?? run?.released) ? 'success' : 'default'}
            label={(fair.released ?? run?.released) ? 'released' : 'unreleased'}
          />
          {(fair.advisory_only || fair.watermark === 'advisory') && (
            <Chip size="small" color="warning" label="advisory" />
          )}
          {fair.watermark && fair.watermark !== 'advisory' && (
            <Chip size="small" label={fair.watermark} />
          )}
          {run?.profile_pack_id && (
            <Chip size="small" variant="outlined" label={`${run.profile_pack_id}@v${run.profile_version || 1}`} />
          )}
          <Button size="small" onClick={() => navigate('/teach/marking')}>
            Marking queue
          </Button>
        </Stack>

        {(assignment || run?.submission_detail) && (
          <Paper variant="outlined" sx={{ p: 1.5, mb: 2 }} component="section" aria-label="Run context">
            <Stack direction={{ xs: 'column', md: 'row' }} spacing={2}>
              <Box sx={{ flex: 1 }}>
                <Typography variant="caption" color="text.secondary">Assignment</Typography>
                <Typography variant="body2">{assignment?.title || '—'}</Typography>
                <Typography variant="caption" color="text.secondary">
                  {[assignment?.mode, assignment?.status, assignment?.course_detail?.code]
                    .filter(Boolean)
                    .join(' · ') || '—'}
                </Typography>
              </Box>
              <Box sx={{ flex: 1 }}>
                <Typography variant="caption" color="text.secondary">Submission</Typography>
                <Typography variant="body2">
                  {run?.submission_detail?.student_username
                    || run?.submission_detail?.external_student_key
                    || run?.submission
                    || '—'}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {run?.submission_detail?.word_count != null
                    ? `${run.submission_detail.word_count} words`
                    : '—'}
                  {run?.completed_at ? ` · completed ${new Date(run.completed_at).toLocaleString()}` : ''}
                </Typography>
              </Box>
            </Stack>
          </Paper>
        )}

        <Typography variant="subtitle2" sx={{ mb: 1 }} id="lct-heading">LCT report (HITL)</Typography>
        <Paper sx={{ p: 2, mb: 2 }} component="section" aria-labelledby="lct-heading">
          <LctCodesTable
            segments={run?.segments || []}
            wave={run?.wave}
            sgLevels={sgLevels}
            sdLevels={sdLevels}
            onEditSg={(seg) => openEdit(seg, 'semantic_gravity')}
            onEditSd={(seg) => openEdit(seg, 'semantic_density')}
            onEditSegmentation={openSegmentation}
          />
        </Paper>

        {run?.wave?.points?.length > 0 && (
          <Paper sx={{ p: 2, mb: 2 }} component="section" aria-label="Semantic wave">
            <Typography variant="subtitle2" sx={{ mb: 1 }}>Semantic wave</Typography>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
              Reflective-wave criteria grid: L4 SG+SD+ · L3 SG−SD+ · L2 SG+SD− · L1 SG−SD−
              (specific/general × reflective/descriptive). Hover a node for justification.
              {run.wave.metrics?.transitions != null
                ? ` · ${run.wave.metrics.transitions} swings`
                : ''}
            </Typography>
            <WaveChart
              points={run.wave.points}
              segments={run?.segments || []}
              height={300}
            />
          </Paper>
        )}

        {(run?.rubric_scores || []).length > 0 && (
          <Paper sx={{ p: 2, mb: 2 }} component="section" aria-label="Rubric scores">
            <Typography variant="subtitle2" sx={{ mb: 1 }}>Rubric</Typography>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Criterion</TableCell>
                  <TableCell>Band</TableCell>
                  <TableCell>Score</TableCell>
                  <TableCell>Source</TableCell>
                  <TableCell>Rationale / evidence</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {run.rubric_scores.map((rs) => (
                  <TableRow key={rs.id || rs.criterion_id}>
                    <TableCell>{rs.criterion_id}</TableCell>
                    <TableCell>{rs.band || '—'}</TableCell>
                    <TableCell>{rs.score_0_100 ?? '—'}</TableCell>
                    <TableCell>{rs.source || '—'}</TableCell>
                    <TableCell sx={{ maxWidth: 420 }}>
                      <Typography variant="body2">{rs.rationale || '—'}</Typography>
                      {rs.evidence_bindings && Object.keys(rs.evidence_bindings).length > 0 && (
                        <Typography variant="caption" color="text.secondary" component="pre" sx={{ m: 0, whiteSpace: 'pre-wrap' }}>
                          {JSON.stringify(rs.evidence_bindings).slice(0, 160)}
                        </Typography>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Paper>
        )}

        {run?.coaching && (
          <Paper sx={{ p: 2, mb: 2 }} component="section" aria-label="Coaching">
            <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
              <Typography variant="subtitle2">Coaching</Typography>
              {run.coaching.watermark && (
                <Chip size="small" color="warning" label={run.coaching.watermark} />
              )}
            </Stack>
            <Typography variant="caption" color="text.secondary">Strengths</Typography>
            <ul>
              {(run.coaching.strengths || []).map((s) => (
                <li key={s}><Typography variant="body2">{s}</Typography></li>
              ))}
            </ul>
            <Typography variant="caption" color="text.secondary">Diagnosis → Action</Typography>
            <ul>
              {(run.coaching.diagnosis_actions || []).map((d) => (
                <li key={d.id || d.diagnosis}>
                  <Typography variant="body2"><strong>{d.diagnosis}</strong> — {d.action}</Typography>
                </li>
              ))}
            </ul>
          </Paper>
        )}

        <Paper sx={{ p: 2, mb: 2 }} component="section" aria-labelledby="expert-edits-heading">
          <Typography id="expert-edits-heading" variant="subtitle2" sx={{ mb: 1 }}>
            ExpertEdit audit trail
          </Typography>
          <ExpertEditsPanel edits={run?.expert_edits || []} />
        </Paper>

        <Paper sx={{ p: 2 }} component="section" aria-labelledby="release-heading">
          <Typography id="release-heading" variant="subtitle2" sx={{ mb: 1 }}>
            Release &amp; LMS passback
          </Typography>
          <Stack spacing={1.5}>
            {agsInfo?.allowed === false && (
              <Alert severity="info">{agsInfo.detail || 'AGS not allowed until release'}</Alert>
            )}
            <TextField
              size="small"
              label="AGS lineitem URL"
              value={lineitem}
              onChange={(e) => setLineitem(e.target.value)}
              fullWidth
            />
            <Button size="small" variant="outlined" onClick={onAgsPassback} disabled={busy || !lineitem.trim()}>
              Dry-run AGS passback
            </Button>
            {agsInfo?.passback && (
              <Alert severity={agsInfo.passback.ok ? 'success' : 'warning'}>
                {agsInfo.passback.dry_run ? 'Dry-run OK' : `HTTP ${agsInfo.passback.status_code}`}
                {' · '}
                {agsInfo.passback.url}
              </Alert>
            )}
          </Stack>
        </Paper>
      </Box>

      <SystemDialog
        open={editOpen}
        title={`Edit ${editDim === 'semantic_density' ? 'SD' : 'SG'} · Segment #${editSeg?.ordinal ?? '—'}`}
        onClose={closeEdit}
        onCancel={closeEdit}
        cancelLabel="Cancel"
        width={520}
        height={440}
        actions={(
          <Button
            variant="contained"
            onClick={saveEdit}
            disabled={busy || !editRationale.trim()}
          >
            Save ExpertEdit
          </Button>
        )}
      >
        <Stack spacing={1.5}>
          <Typography variant="body2" color="text.secondary">
            Current: {beforeCode?.value || '—'}
            {beforeCode?.source ? ` (${beforeCode.source})` : ''}
            {' · '}
            Append-only ExpertEdit feeds the learning loop (RULE_32).
          </Typography>
          {(editSeg?.text || '').trim() && (
            <Alert severity="info" sx={{ py: 0.5 }}>
              <Typography variant="caption" sx={{ whiteSpace: 'pre-wrap' }}>
                {(editSeg.text || '').slice(0, 320)}
                {(editSeg.text || '').length > 320 ? '…' : ''}
              </Typography>
            </Alert>
          )}
          <FormControl size="small" fullWidth>
            <InputLabel id="edit-value-label">Code</InputLabel>
            <Select
              labelId="edit-value-label"
              label="Code"
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
            >
              {levels.map((lv) => (
                <MenuItem key={lv} value={lv}>{lv}</MenuItem>
              ))}
            </Select>
          </FormControl>
          <TextField
            size="small"
            label="Rationale"
            value={editRationale}
            onChange={(e) => setEditRationale(e.target.value)}
            multiline
            minRows={4}
            fullWidth
            required
            helperText="Required — ExpertEdit is append-only learning evidence"
          />
        </Stack>
      </SystemDialog>
      <SystemDialog
        open={segOpen}
        title="Resegment (HITL)"
        onClose={() => setSegOpen(false)}
        onCancel={() => setSegOpen(false)}
        cancelLabel="Cancel"
        width={780}
        height={620}
        actions={(
          <Button
            variant="contained"
            onClick={saveSegmentation}
            disabled={busy || !segRationale.trim() || !segDraft?.length}
          >
            Save ExpertEdit
          </Button>
        )}
      >
        <SegmentationEditor
          key={segEditorKey}
          segments={run?.segments || []}
          fullText={run?.submission_detail?.text || ''}
          rationale={segRationale}
          onRationaleChange={setSegRationale}
          onChange={setSegDraft}
          suggestedSplits={segSuggestions}
          onRequestSuggestions={requestSegSuggestions}
        />
      </SystemDialog>
    </PageContainer>
  );
}
