// Run workbench — LCT results + HITL code edit + release (professor review plane).

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Alert, Box, Button, Chip, Drawer, FormControl, InputLabel, MenuItem, Paper,
  Select, Stack, Table, TableBody, TableCell, TableHead, TableRow, TextField, Typography,
} from '@mui/material';
import ScienceIcon from '@mui/icons-material/Science';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../components/Page/ErrorAlert';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import {
  fetchAgsPreview, fetchRun, postAgsPassback, postExpertEdit, releaseRun,
} from '../../api/gradevance';
import SkipToMain from './SkipToMain';
import WaveChart from './WaveChart';
import LctCodesTable from './LctCodesTable';
import OpsCanvasAttachButton from '../people/OpsCanvasAttachButton';

const SG_LEVELS = ['SG++', 'SG+', 'SG-', 'SG--'];
const SD_LEVELS = ['SD-', 'SD+'];
const SG_NUMERIC = { 'SG++': 1, 'SG+': 2, 'SG-': 3, 'SG--': 4 };

function codeFor(seg, dimension) {
  const codes = seg?.codes || [];
  return codes.find((c) => c.dimension === dimension) || null;
}

export default function RunWorkbenchPage() {
  useDocumentTitle('GradeVance · Run');
  const { runId } = useParams();
  const { token } = useAuth();
  const navigate = useNavigate();

  const [run, setRun] = useState(null);
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
      })
      .catch((e) => setError(e?.message || 'Failed to load run'))
      .finally(() => setLoading(false));
  }, [token, runId]);

  useEffect(() => { load(); }, [load]);

  const assignment = useMemo(() => run?.assignment || null, [run]);
  const assignmentId = assignment?.id || null;

  const openEdit = (seg, dimension) => {
    const existing = codeFor(seg, dimension);
    setEditSeg(seg);
    setEditDim(dimension);
    setEditValue(existing?.value || (dimension === 'semantic_density' ? 'SD-' : 'SG+'));
    setEditRationale('');
    setEditOpen(true);
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
      const beforeCode = codeFor(editSeg, editDim);
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
          numeric: editDim === 'semantic_gravity' ? SG_NUMERIC[editValue] : null,
        },
        rationale: editRationale.trim(),
      });
      setMsg('ExpertEdit saved — learning loop may draft a Proposal');
      setEditOpen(false);
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

  const levels = editDim === 'semantic_density' ? SD_LEVELS : SG_LEVELS;

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
            <Stack direction="row" spacing={0.75} alignItems="center">
              <OpsCanvasAttachButton
                relatedType="gradevance.AssessmentRun"
                relatedId={runId}
                relatedLabel={assignment?.title || `Run ${runId}`}
              />
              {assignmentId && (
                <Button size="small" variant="outlined" onClick={() => navigate(`/apps/gradevance/assignments/${assignmentId}`)}>
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

        <Stack direction="row" spacing={1} sx={{ mb: 1.5, flexWrap: 'wrap' }}>
          <Chip size="small" label={run?.status || '—'} />
          <Chip size="small" label={`gate ${run?.gate_decision || '—'}`} variant="outlined" />
          <Chip
            size="small"
            label={run?.mean_confidence != null ? `conf ${Number(run.mean_confidence).toFixed(2)}` : 'conf —'}
          />
          <Button size="small" onClick={() => navigate('/apps/gradevance/marking')}>
            Marking queue
          </Button>
        </Stack>

        <Typography variant="subtitle2" sx={{ mb: 1 }} id="lct-heading">LCT codes (HITL)</Typography>
        <Paper sx={{ p: 2, mb: 2 }} component="section" aria-labelledby="lct-heading">
          <LctCodesTable segments={run?.segments || []} wave={run?.wave} />
          <Table size="small" sx={{ mt: 1 }} aria-label="Edit LCT codes per segment">
            <TableHead>
              <TableRow>
                <TableCell>#</TableCell>
                <TableCell>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(run?.segments || []).map((seg) => (
                <TableRow key={seg.id || seg.ordinal}>
                  <TableCell>{seg.ordinal ?? '—'}</TableCell>
                  <TableCell>
                    <Button size="small" onClick={() => openEdit(seg, 'semantic_gravity')}>Edit SG</Button>
                    <Button size="small" onClick={() => openEdit(seg, 'semantic_density')}>Edit SD</Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Paper>

        {run?.wave?.points?.length > 0 && (
          <Paper sx={{ p: 2, mb: 2 }} component="section" aria-label="Semantic wave">
            <Typography variant="subtitle2" sx={{ mb: 1 }}>Semantic wave</Typography>
            <WaveChart points={run.wave.points} />
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
                </TableRow>
              </TableHead>
              <TableBody>
                {run.rubric_scores.map((rs) => (
                  <TableRow key={rs.id || rs.criterion_id}>
                    <TableCell>{rs.criterion_id}</TableCell>
                    <TableCell>{rs.band || '—'}</TableCell>
                    <TableCell>{rs.score_0_100 ?? '—'}</TableCell>
                    <TableCell>{rs.source || '—'}</TableCell>
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

      <Drawer anchor="right" open={editOpen} onClose={() => setEditOpen(false)}>
        <Box sx={{ width: 360, p: 2 }} role="dialog" aria-label="Edit LCT code">
          <Typography variant="h6" sx={{ mb: 2 }}>
            Edit {editDim === 'semantic_density' ? 'SD' : 'SG'}
          </Typography>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
            Segment #{editSeg?.ordinal ?? '—'}
          </Typography>
          <FormControl size="small" fullWidth sx={{ mb: 1.5 }}>
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
            minRows={3}
            fullWidth
            required
            sx={{ mb: 2 }}
            helperText="Required — ExpertEdit is append-only learning evidence"
          />
          <Stack direction="row" spacing={1}>
            <Button variant="contained" onClick={saveEdit} disabled={busy || !editRationale.trim()}>
              Save ExpertEdit
            </Button>
            <Button onClick={() => setEditOpen(false)}>Cancel</Button>
          </Stack>
        </Box>
      </Drawer>
    </PageContainer>
  );
}
