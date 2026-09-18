// Assignment hub — stem/config + submissions + runs (professor execution plane).
// Phase C: draft stem PATCH, file upload, KB pin, batch analyze.

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Alert, Box, Button, Chip, FormControl, InputLabel, MenuItem, Paper, Select,
  Stack, Table, TableBody, TableCell, TableHead, TableRow, TextField, Typography,
} from '@mui/material';
import AssignmentIcon from '@mui/icons-material/Assignment';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../components/Page/ErrorAlert';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import {
  analyzeSubmission, batchAnalyzeAssignment, createSubmission, fetchAssignment,
  fetchDemoExamples, fetchKnowledgeBases, patchAssignment, submitAndAnalyze,
  uploadSubmissionFile,
} from '../../api/gradevance';
import SkipToMain from './SkipToMain';
import PackDetailDrawer from './PackDetailDrawer';

export default function AssignmentHubPage() {
  useDocumentTitle('GradeVance · Assignment');
  const { assignmentId } = useParams();
  const { token } = useAuth();
  const navigate = useNavigate();
  const fileRef = useRef(null);

  const [hub, setHub] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [msg, setMsg] = useState(null);
  const [paste, setPaste] = useState('');
  const [busy, setBusy] = useState(false);
  const [examples, setExamples] = useState([]);
  const [kbs, setKbs] = useState([]);
  const [stemEdit, setStemEdit] = useState('');
  const [instructionsEdit, setInstructionsEdit] = useState('');
  const [kbId, setKbId] = useState('');
  const [packOpen, setPackOpen] = useState(false);

  const load = useCallback(() => {
    if (!assignmentId) return;
    setLoading(true);
    setError(null);
    Promise.all([
      fetchAssignment(token, assignmentId),
      fetchDemoExamples(token).catch(() => ({ results: [] })),
      fetchKnowledgeBases(token).catch(() => ({ results: [] })),
    ])
      .then(([data, ex, kb]) => {
        setHub(data);
        const asg = data?.assignment;
        const brief = asg?.brief || {};
        setStemEdit(brief.stem || '');
        setInstructionsEdit(brief.instructions || '');
        setKbId(brief.kb?.pack_id || brief.kb_pack_id || '');
        const pack = asg?.profile_pack_id;
        const rows = (ex.results || []).filter((e) => !pack || e.profile_pack_id === pack);
        setExamples(rows.slice(0, 12));
        setKbs(kb.results || []);
      })
      .catch((e) => setError(e?.message || 'Failed to load assignment'))
      .finally(() => setLoading(false));
  }, [token, assignmentId]);

  useEffect(() => { load(); }, [load]);

  const asg = hub?.assignment;
  const brief = asg?.brief || {};
  const isDraft = asg?.status === 'draft';

  const onSaveStem = async () => {
    if (!isDraft) {
      setError('Stem is frozen on published assignments — create a draft to edit');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await patchAssignment(token, assignmentId, {
        brief: { stem: stemEdit.trim(), instructions: instructionsEdit.trim() },
      });
      setMsg('Stem saved');
      load();
    } catch (e) {
      setError(e?.message || 'Save stem failed');
    } finally {
      setBusy(false);
    }
  };

  const onSaveKb = async () => {
    setBusy(true);
    setError(null);
    try {
      const kb = kbId
        ? { pack_id: kbId, version: kbs.find((k) => k.pack_id === kbId)?.version || 1 }
        : null;
      await patchAssignment(token, assignmentId, { brief: { kb } });
      setMsg(kb ? `KB pinned: ${kbId}` : 'KB pin cleared');
      load();
    } catch (e) {
      setError(e?.message || 'KB pin failed');
    } finally {
      setBusy(false);
    }
  };

  const onPublishDraft = async () => {
    setBusy(true);
    setError(null);
    try {
      await patchAssignment(token, assignmentId, { status: 'published' });
      setMsg('Assignment published');
      load();
    } catch (e) {
      setError(e?.message || 'Publish failed');
    } finally {
      setBusy(false);
    }
  };

  const onAnalyzePaste = async (alsoAnalyze = true) => {
    if (!paste.trim()) {
      setError('Paste submission text first');
      return;
    }
    setBusy(true);
    setError(null);
    setMsg(null);
    try {
      if (alsoAnalyze) {
        const payload = await submitAndAnalyze(token, {
          assignment: assignmentId,
          text: paste.trim(),
        });
        setMsg('Submission analyzed');
        setPaste('');
        if (payload?.run?.id) {
          navigate(`/apps/gradevance/runs/${payload.run.id}`);
          return;
        }
      } else {
        await createSubmission(token, { assignment: assignmentId, text: paste.trim() });
        setMsg('Submission saved (not analyzed)');
        setPaste('');
      }
      load();
    } catch (e) {
      setError(e?.message || 'Submit failed');
    } finally {
      setBusy(false);
    }
  };

  const onAnalyzeExisting = async (submissionId) => {
    setBusy(true);
    setError(null);
    try {
      const run = await analyzeSubmission(token, submissionId);
      navigate(`/apps/gradevance/runs/${run.id}`);
    } catch (e) {
      setError(e?.message || 'Analyze failed');
      setBusy(false);
    }
  };

  const onUpload = async (ev) => {
    const file = ev.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const payload = await uploadSubmissionFile(token, {
        assignment: assignmentId,
        file,
        analyze: true,
      });
      setMsg(`Uploaded ${payload.filename || file.name}`);
      if (payload?.run?.id) {
        navigate(`/apps/gradevance/runs/${payload.run.id}`);
        return;
      }
      load();
    } catch (e) {
      setError(e?.message || 'Upload failed');
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  const onBatchAnalyze = async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await batchAnalyzeAssignment(token, assignmentId, {});
      setMsg(`Batch analyze: ${result.analyzed} new · ${result.skipped} skipped · ${result.errors?.length || 0} errors`);
      load();
    } catch (e) {
      setError(e?.message || 'Batch analyze failed');
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <PageContainer>
        <PageHeader icon={AssignmentIcon} title="Assignment hub" subtitle="Stem · submissions · runs" />
        <LoadingSkeleton variant="table" />
      </PageContainer>
    );
  }

  if (error && !hub) {
    return (
      <PageContainer>
        <PageHeader icon={AssignmentIcon} title="Assignment hub" />
        <ErrorAlert message={error} onRetry={load} />
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <SkipToMain targetId="gv-assignment-hub" />
      <Box component="main" id="gv-assignment-hub" tabIndex={-1} aria-label="Assignment hub">
        <PageHeader
          icon={AssignmentIcon}
          title={asg?.title || 'Assignment'}
          subtitle="Operate one stem — ingest thinking, analyze, open Run workbench."
          badge={asg?.mode ? { label: asg.mode, color: 'primary' } : null}
          actions={(
            <Stack direction="row" spacing={0.75}>
              <Button size="small" variant="outlined" onClick={() => navigate('/apps/gradevance/courses')}>
                Courses
              </Button>
              <Button
                size="small"
                variant="outlined"
                onClick={() => setPackOpen(true)}
              >
                Pack detail
              </Button>
              <Button
                size="small"
                variant="contained"
                disabled={busy || !paste.trim()}
                onClick={() => onAnalyzePaste(true)}
              >
                Analyze
              </Button>
            </Stack>
          )}
        />
        {error && <ErrorAlert message={error} onRetry={load} />}
        {msg && <Alert severity="success" sx={{ mb: 1.5 }} role="status">{msg}</Alert>}

        <Stack direction="row" spacing={1} sx={{ mb: 1.5, flexWrap: 'wrap' }} aria-label="Assignment config">
          <Chip size="small" label={asg?.status} variant="outlined" color={isDraft ? 'warning' : 'default'} />
          <Chip size="small" label={`${asg?.profile_pack_id}@v${asg?.profile_version}`} />
          <Chip size="small" label={`${hub?.counts?.submissions ?? 0} submissions`} />
          <Chip size="small" label={`${hub?.counts?.runs ?? 0} runs`} />
          {(hub?.counts?.open_reviews > 0) && (
            <Chip size="small" color="warning" label={`${hub.counts.open_reviews} open reviews`} />
          )}
          {isDraft && (
            <Button size="small" variant="contained" disabled={busy} onClick={onPublishDraft}>
              Publish draft
            </Button>
          )}
        </Stack>

        <Typography variant="subtitle2" sx={{ mb: 0.75 }} id="stem-heading">Stem</Typography>
        <Paper sx={{ p: 1.5, mb: 2 }} component="section" aria-labelledby="stem-heading">
          {isDraft ? (
            <Stack spacing={1.25}>
              <TextField
                size="small"
                label="Stem"
                value={stemEdit}
                onChange={(e) => setStemEdit(e.target.value)}
                multiline
                minRows={3}
                fullWidth
              />
              <TextField
                size="small"
                label="Instructions"
                value={instructionsEdit}
                onChange={(e) => setInstructionsEdit(e.target.value)}
                multiline
                minRows={2}
                fullWidth
              />
              <Button size="small" variant="contained" disabled={busy || !stemEdit.trim()} onClick={onSaveStem}>
                Save stem
              </Button>
            </Stack>
          ) : (
            <>
              <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                {brief.stem || '— No stem on this assignment.'}
              </Typography>
              {brief.instructions && (
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1, whiteSpace: 'pre-wrap' }}>
                  {brief.instructions}
                </Typography>
              )}
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
                Published — stem frozen (RULE_32). KB pin below may still change.
              </Typography>
            </>
          )}
        </Paper>

        <Typography variant="subtitle2" sx={{ mb: 0.75 }} id="kb-heading">Knowledge base pin</Typography>
        <Paper sx={{ p: 1.5, mb: 2 }} component="section" aria-labelledby="kb-heading">
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.25} alignItems="flex-start">
            <FormControl size="small" sx={{ minWidth: 260 }} fullWidth>
              <InputLabel id="kb-label">KB pack</InputLabel>
              <Select
                labelId="kb-label"
                label="KB pack"
                value={kbId}
                onChange={(e) => setKbId(e.target.value)}
              >
                <MenuItem value="">None</MenuItem>
                {kbs.map((k) => (
                  <MenuItem key={k.pack_id} value={k.pack_id}>
                    {k.name || k.pack_id} ({k.status})
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <Button size="small" variant="outlined" disabled={busy} onClick={onSaveKb}>
              Save KB pin
            </Button>
          </Stack>
        </Paper>

        <Typography variant="subtitle2" sx={{ mb: 0.75 }} id="ingest-heading">Add submission</Typography>
        <Paper sx={{ p: 1.5, mb: 2 }} component="section" aria-labelledby="ingest-heading">
          <Stack spacing={1.25}>
            {examples.length > 0 && (
              <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                {examples.map((ex) => (
                  <Button
                    key={ex.id || ex.title}
                    size="small"
                    variant="outlined"
                    onClick={() => setPaste(ex.text || '')}
                  >
                    {(ex.title || ex.id || 'Example').slice(0, 28)}
                  </Button>
                ))}
              </Stack>
            )}
            <TextField
              size="small"
              label="Student text"
              value={paste}
              onChange={(e) => setPaste(e.target.value)}
              multiline
              minRows={4}
              fullWidth
            />
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              <Button size="small" variant="outlined" disabled={busy || !paste.trim()} onClick={() => onAnalyzePaste(false)}>
                Save only
              </Button>
              <Button size="small" variant="outlined" component="label" disabled={busy}>
                Upload .txt / .md
                <input ref={fileRef} hidden type="file" accept=".txt,.md,.text,text/plain,text/markdown" onChange={onUpload} />
              </Button>
              <Button size="small" variant="outlined" disabled={busy} onClick={onBatchAnalyze}>
                Batch analyze cohort
              </Button>
            </Stack>
          </Stack>
        </Paper>

        <Typography variant="subtitle2" sx={{ mb: 0.75 }} id="subs-heading">Submissions</Typography>
        <Paper sx={{ mb: 2 }} component="section" aria-labelledby="subs-heading">
          <Table size="small" aria-label="Assignment submissions">
            <TableHead>
              <TableRow>
                <TableCell>Created</TableCell>
                <TableCell>Words</TableCell>
                <TableCell>Excerpt</TableCell>
                <TableCell />
              </TableRow>
            </TableHead>
            <TableBody>
              {(hub?.submissions || []).map((s) => (
                <TableRow key={s.id} hover>
                  <TableCell>
                    <Typography variant="caption">
                      {s.created_at ? new Date(s.created_at).toLocaleString() : '—'}
                    </Typography>
                  </TableCell>
                  <TableCell>{s.word_count ?? '—'}</TableCell>
                  <TableCell>
                    <Typography variant="caption" color="text.secondary">
                      {(s.text || '').slice(0, 80)}{(s.text || '').length > 80 ? '…' : ''}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Button size="small" disabled={busy} onClick={() => onAnalyzeExisting(s.id)}>
                      Analyze
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              {!(hub?.submissions || []).length && (
                <TableRow>
                  <TableCell colSpan={4}>
                    <Typography color="text.secondary">No submissions yet — paste or upload text above.</Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </Paper>

        <Typography variant="subtitle2" sx={{ mb: 0.75 }} id="runs-heading">Runs</Typography>
        <Paper component="section" aria-labelledby="runs-heading">
          <Table size="small" aria-label="Analysis runs">
            <TableHead>
              <TableRow>
                <TableCell>Status</TableCell>
                <TableCell>Gate</TableCell>
                <TableCell>Confidence</TableCell>
                <TableCell>Released</TableCell>
                <TableCell />
              </TableRow>
            </TableHead>
            <TableBody>
              {(hub?.runs || []).map((r) => (
                <TableRow key={r.id} hover>
                  <TableCell><Chip size="small" label={r.status} /></TableCell>
                  <TableCell>{r.gate_decision || '—'}</TableCell>
                  <TableCell>{r.mean_confidence != null ? Number(r.mean_confidence).toFixed(2) : '—'}</TableCell>
                  <TableCell>{r.released ? 'yes' : 'no'}</TableCell>
                  <TableCell>
                    <Button size="small" onClick={() => navigate(`/apps/gradevance/runs/${r.id}`)}>
                      Open run
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              {!(hub?.runs || []).length && (
                <TableRow>
                  <TableCell colSpan={5}>
                    <Typography color="text.secondary">No runs yet — analyze a submission.</Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </Paper>
      </Box>

      <PackDetailDrawer
        open={packOpen}
        onClose={() => setPackOpen(false)}
        packId={asg?.profile_pack_id}
        version={asg?.profile_version || 1}
      />
    </PageContainer>
  );
}
