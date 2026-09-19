// Assignment desk — draft, autosave, coaching, submit, results, appeal (Phase D).

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Alert, Box, Button, Chip, Paper, Stack, TextField, Typography,
} from '@mui/material';
import EditNoteIcon from '@mui/icons-material/EditNote';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../components/Page/ErrorAlert';
import EmptyState from '../../components/Page/EmptyState';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import {
  createMyAppeal, createMySubmission, fetchAssignment, fetchMyAppeals, fetchMyAssignment,
  fetchMyRun, fetchMySubmissions, patchMySubmission, withdrawMyAppeal,
} from '../../api/gradevance';
import SkipToMain from '../../components/gradevance/SkipToMain';
import WaveChart from '../../components/gradevance/WaveChart';
import LctCodesTable from '../../components/gradevance/LctCodesTable';
import LearnReadingWidth, { useLearnPrimarySize } from '../../components/gradevance/LearnReadingWidth';

const AUTOSAVE_MS = 800;

function bandsWithheld(assignment, run) {
  if (!run) return false;
  if (run.bands_withheld === true) return true;
  if (run.summative_withheld === true) return true;
  const bands = run.advisory_bands;
  if (bands && typeof bands === 'object' && bands.withheld === true) return true;
  if (bands == null && run.released === false) {
    const mode = (assignment?.mode || run.mode || '').toLowerCase();
    if (mode === 'summative') return true;
  }
  const mode = (assignment?.mode || run.mode || '').toLowerCase();
  if (mode === 'summative' && run.released === false) return true;
  return false;
}

/** Learner-readable band expectations — never JSON.stringify dump. */
function BandExpectationsBlock({ expectations }) {
  if (!expectations) return null;
  if (typeof expectations === 'string') {
    return (
      <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>{expectations}</Typography>
    );
  }
  if (Array.isArray(expectations)) {
    return (
      <Stack spacing={0.75} component="ul" sx={{ m: 0, pl: 2 }}>
        {expectations.map((item, i) => (
          <Typography key={i} component="li" variant="body2">
            {typeof item === 'string' ? item : (item.label || item.name || item.band || String(item))}
          </Typography>
        ))}
      </Stack>
    );
  }
  // Object: criterion → descriptor string | nested bands
  const entries = Object.entries(expectations);
  if (!entries.length) return null;
  return (
    <Stack spacing={1}>
      {entries.map(([key, val]) => {
        if (key === 'withheld') return null;
        let body;
        if (typeof val === 'string') body = val;
        else if (val && typeof val === 'object') {
          if (val.description || val.descriptor) body = val.description || val.descriptor;
          else if (val.bands && typeof val.bands === 'object') {
            body = Object.entries(val.bands)
              .map(([b, d]) => `${b}: ${typeof d === 'string' ? d : (d.description || '')}`)
              .join('\n');
          } else {
            body = Object.entries(val)
              .filter(([k]) => k !== 'withheld')
              .map(([b, d]) => `${b}: ${typeof d === 'string' ? d : ''}`)
              .filter((line) => !line.endsWith(': '))
              .join('\n');
          }
        } else body = String(val ?? '');
        return (
          <Box key={key}>
            <Typography variant="body2" sx={{ fontWeight: 600 }}>{key}</Typography>
            {body ? (
              <Typography variant="body2" color="text.secondary" sx={{ whiteSpace: 'pre-wrap' }}>
                {body}
              </Typography>
            ) : null}
          </Box>
        );
      })}
    </Stack>
  );
}

function displayableBands(bands) {
  if (!bands || typeof bands !== 'object') return {};
  if (bands.withheld === true) return {};
  return Object.fromEntries(
    Object.entries(bands).filter(([k, v]) => k !== 'withheld' && v != null && typeof v !== 'object'),
  );
}

function statusChipColor(status) {
  switch ((status || '').toLowerCase()) {
    case 'released': return 'success';
    case 'submitted': return 'info';
    case 'drafted':
    case 'draft': return 'default';
    case 'open':
    case 'published': return 'primary';
    default: return 'default';
  }
}

function canRequestReview(assignment, run) {
  if (!run) return false;
  if (run.released === true) return true;
  const mode = (assignment?.mode || run.mode || '').toLowerCase();
  const finished = ['complete', 'needs_review', 'done'].includes(
    (run.status || '').toLowerCase(),
  );
  if (mode === 'formative' && (finished || run.coaching)) {
    return true;
  }
  return false;
}

/**
 * Full assignment lifecycle desk. Embeddable in teach preview Drawer via previewMode.
 */
export function AssignmentDesk({
  assignmentId: assignmentIdProp,
  previewMode = false,
  lockedText = null,
  hideActions = false,
  previewSubmissionId = null,
}) {
  const { assignmentId: routeId } = useParams();
  const assignmentId = assignmentIdProp || routeId;
  const { token } = useAuth();
  const navigate = useNavigate();

  const [assignment, setAssignment] = useState(null);
  const [submission, setSubmission] = useState(null);
  const [text, setText] = useState('');
  const [run, setRun] = useState(null);
  const [appeal, setAppeal] = useState(null);
  const [appealReason, setAppealReason] = useState('');
  const [loading, setLoading] = useState(true);
  const [forbidden, setForbidden] = useState(false);
  const [error, setError] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [msg, setMsg] = useState(null);
  const [saving, setSaving] = useState(false);
  const [coaching, setCoachingBusy] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [appealBusy, setAppealBusy] = useState(false);
  const [withdrawBusy, setWithdrawBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  const primarySize = useLearnPrimarySize();

  const textRef = useRef(text);
  const submissionRef = useRef(submission);
  const autosaveTimer = useRef(null);
  textRef.current = text;
  submissionRef.current = submission;

  const readOnly = previewMode || hideActions;
  const displayText = lockedText != null ? lockedText : text;

  const load = useCallback(() => {
    if (!assignmentId || !token) return;
    setLoading(true);
    setError(null);
    setForbidden(false);

    if (previewMode) {
      fetchAssignment(token, assignmentId)
        .then((data) => {
          const asg = data?.assignment || data;
          setAssignment({
            ...asg,
            course_title: asg.course_title || data?.course?.name,
            brief: asg.brief,
          });
          setSubmission(null);
          setRun(null);
          setAppeal(null);
          if (lockedText == null) setText('');
        })
        .catch((err) => {
          setError(err?.message || 'Failed to load assignment preview');
        })
        .finally(() => setLoading(false));
      return;
    }

    Promise.all([
      fetchMyAssignment(token, assignmentId),
      fetchMySubmissions(token, { assignment: assignmentId }).catch(() => ({ results: [] })),
      fetchMyAppeals(token, { assignment: assignmentId }).catch(() => ({ results: [] })),
    ])
      .then(async ([asg, subData, appealData]) => {
        setAssignment(asg);
        const subs = subData.results || subData || [];
        let latest = subs[0] || null;
        if (previewSubmissionId) {
          latest = subs.find((s) => String(s.id) === String(previewSubmissionId)) || latest;
        }
        setSubmission(latest);
        if (lockedText == null) {
          setText(latest?.text || '');
        }
        setDirty(false);

        const appeals = appealData.results || appealData || [];
        setAppeal(appeals[0] || null);

        const runId = latest?.latest_run_id || latest?.run?.id || latest?.run;
        if (runId) {
          try {
            const r = await fetchMyRun(token, runId);
            setRun(r);
          } catch {
            if (latest?.run && typeof latest.run === 'object') setRun(latest.run);
            else setRun(null);
          }
        } else {
          setRun(null);
        }
      })
      .catch((err) => {
        const status = err?.status || err?.response?.status;
        if (status === 403 || status === 404) {
          setForbidden(true);
          setError(err?.message || 'Assignment not available');
        } else {
          setError(err?.message || 'Failed to load assignment');
        }
      })
      .finally(() => setLoading(false));
  }, [token, assignmentId, previewSubmissionId, lockedText, previewMode]);

  useEffect(() => {
    load();
  }, [load]);

  const persistDraft = useCallback(async (nextText, { analyze = false, status = 'draft' } = {}) => {
    const body = { assignment: assignmentId, text: nextText, status, analyze };
    const existing = submissionRef.current;
    if (existing?.id && !analyze && status === 'draft') {
      const updated = await patchMySubmission(token, existing.id, { text: nextText, status: 'draft' });
      const sub = updated.submission || updated;
      setSubmission(sub);
      submissionRef.current = sub;
      return { submission: sub, run: updated.run || null };
    }
    const result = await createMySubmission(token, body);
    const sub = result.submission || result;
    setSubmission(sub);
    submissionRef.current = sub;
    if (result.run) setRun(result.run);
    return result;
  }, [token, assignmentId]);

  const scheduleAutosave = useCallback((nextText) => {
    if (readOnly) return;
    if (autosaveTimer.current) clearTimeout(autosaveTimer.current);
    autosaveTimer.current = setTimeout(async () => {
      const sub = submissionRef.current;
      if (sub?.status === 'submitted') return;
      setSaving(true);
      setActionError(null);
      try {
        await persistDraft(nextText, { status: 'draft' });
        setDirty(false);
        setMsg('Draft saved');
      } catch (err) {
        setActionError(err?.message || 'Autosave failed');
      } finally {
        setSaving(false);
      }
    }, AUTOSAVE_MS);
  }, [persistDraft, readOnly]);

  useEffect(() => () => {
    if (autosaveTimer.current) clearTimeout(autosaveTimer.current);
  }, []);

  const onTextChange = (e) => {
    const next = e.target.value;
    setText(next);
    setDirty(true);
    setMsg(null);
    scheduleAutosave(next);
  };

  const onSaveDraft = async () => {
    if (autosaveTimer.current) clearTimeout(autosaveTimer.current);
    setSaving(true);
    setActionError(null);
    setMsg(null);
    try {
      await persistDraft(textRef.current, { status: 'draft' });
      setDirty(false);
      setMsg('Draft saved');
    } catch (err) {
      setActionError(err?.message || 'Save draft failed');
    } finally {
      setSaving(false);
    }
  };

  const onCoach = async () => {
    if (autosaveTimer.current) clearTimeout(autosaveTimer.current);
    setCoachingBusy(true);
    setActionError(null);
    setMsg(null);
    try {
      const result = await persistDraft(textRef.current, { analyze: true, status: 'draft' });
      if (result.run) {
        setRun(result.run);
      } else if (result.run_id || result.latest_run_id) {
        const runId = result.run_id || result.latest_run_id;
        setRun(await fetchMyRun(token, runId));
      }
      setDirty(false);
      setMsg('Formative coaching ready');
    } catch (err) {
      setActionError(err?.message || 'Coaching request failed');
    } finally {
      setCoachingBusy(false);
    }
  };

  const onSubmit = async () => {
    if (autosaveTimer.current) clearTimeout(autosaveTimer.current);
    setSubmitting(true);
    setActionError(null);
    setMsg(null);
    try {
      const existing = submissionRef.current;
      if (existing?.id) {
        const updated = await patchMySubmission(token, existing.id, {
          text: textRef.current,
          status: 'submitted',
        });
        const sub = updated.submission || updated;
        setSubmission(sub);
        submissionRef.current = sub;
        if (updated.run) setRun(updated.run);
      } else {
        await persistDraft(textRef.current, { status: 'submitted' });
      }
      setDirty(false);
      setMsg('Submitted for marking');
      load();
    } catch (err) {
      setActionError(err?.message || 'Submit failed');
    } finally {
      setSubmitting(false);
    }
  };

  const onAppeal = async () => {
    if (!run?.id || !appealReason.trim()) return;
    setAppealBusy(true);
    setActionError(null);
    setMsg(null);
    try {
      const created = await createMyAppeal(token, {
        run: run.id,
        reason: appealReason.trim(),
      });
      setAppeal(created);
      setAppealReason('');
      setMsg('Review request submitted');
    } catch (err) {
      setActionError(err?.message || 'Appeal failed');
    } finally {
      setAppealBusy(false);
    }
  };

  const onWithdrawAppeal = async () => {
    if (!appeal?.id) return;
    const status = (appeal.status || '').toLowerCase();
    if (status !== 'open') return;
    setWithdrawBusy(true);
    setActionError(null);
    setMsg(null);
    try {
      const updated = await withdrawMyAppeal(token, appeal.id);
      setAppeal(updated);
      setMsg('Appeal withdrawn');
    } catch (err) {
      setActionError(err?.message || 'Withdraw failed');
    } finally {
      setWithdrawBusy(false);
    }
  };

  if (loading) {
    return (
      <Box>
        {!previewMode && <PageHeader icon={EditNoteIcon} title="Assignment" />}
        <LoadingSkeleton variant="console" />
      </Box>
    );
  }

  if (forbidden) {
    return (
      <EmptyState
        icon={<EditNoteIcon />}
        title="Assignment not available"
        description="You may not be enrolled, or this assignment is not published for you."
        actionLabel={previewMode ? undefined : 'My assignments'}
        onAction={previewMode ? undefined : () => navigate('/learn/assignments')}
      />
    );
  }

  if (error && !assignment) {
    return <ErrorAlert message={error} onRetry={load} />;
  }

  if (!assignment) {
    return (
      <EmptyState
        icon={<EditNoteIcon />}
        title="No assignment"
        description="This assignment could not be found."
      />
    );
  }

  const brief = assignment.brief?.stem
    || assignment.brief
    || assignment.stem
    || assignment.prompt
    || assignment.description
    || '';
  const briefText = typeof brief === 'string' ? brief : (brief.stem || brief.instructions || '');
  const expectations = assignment.band_expectations
    || assignment.brief?.band_expectations
    || null;
  const coachingPayload = run?.coaching || {};
  const withheld = bandsWithheld(assignment, run);
  const bands = withheld ? {} : displayableBands(run?.advisory_bands || {});
  const myStatus = assignment.my_status || submission?.status || 'open';
  const busy = saving || coaching || submitting;
  const textTooShort = (displayText || '').trim().length < 40;
  const isSubmitted = (submission?.status || '').toLowerCase() === 'submitted'
    || (myStatus || '').toLowerCase() === 'submitted'
    || (myStatus || '').toLowerCase() === 'released';

  const headerActions = !readOnly ? (
    <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap>
      <Button
        size="small"
        variant="outlined"
        onClick={onSaveDraft}
        disabled={busy || !dirty}
        aria-busy={saving}
      >
        {saving ? 'Saving…' : 'Save draft'}
      </Button>
      <Button
        size="small"
        variant="outlined"
        onClick={onCoach}
        disabled={busy || textTooShort}
        aria-busy={coaching}
      >
        {coaching ? 'Analyzing…' : 'Get formative coaching'}
      </Button>
      <Button
        size="small"
        variant="contained"
        onClick={onSubmit}
        disabled={busy || textTooShort || isSubmitted}
        aria-busy={submitting}
      >
        {submitting ? 'Submitting…' : 'Submit for marking'}
      </Button>
    </Stack>
  ) : null;

  return (
    <Box>
      {!previewMode && (
        <PageHeader
          icon={EditNoteIcon}
          title={assignment.title || 'Assignment'}
          subtitle={assignment.course_title || assignment.mode || 'Draft, coach, submit'}
          actions={headerActions}
        />
      )}
      {previewMode && (
        <Typography variant="subtitle1" sx={{ mb: 1 }}>
          {assignment.title || 'Assignment'}
          {assignment.course_title ? ` · ${assignment.course_title}` : ''}
        </Typography>
      )}

      <Stack direction="row" spacing={1} sx={{ mb: 1.5, flexWrap: 'wrap' }} useFlexGap aria-label="Assignment status">
        <Chip size="small" label={myStatus} color={statusChipColor(myStatus)} />
        <Chip size="small" label={assignment.mode || 'formative'} variant="outlined" />
        {run?.released === true && <Chip size="small" color="success" label="released" />}
        {run?.released === false && assignment.mode === 'summative' && (
          <Chip size="small" label="unreleased" />
        )}
        {dirty && !readOnly && <Chip size="small" label="unsaved" color="warning" />}
      </Stack>

      {(briefText || expectations) && (
        <Paper variant="outlined" sx={{ p: 1.5, mb: 1.5 }} component="section" aria-labelledby="brief-heading">
          <Typography id="brief-heading" variant="subtitle2" sx={{ mb: 0.5 }}>Brief</Typography>
          {briefText && (
            <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>{String(briefText)}</Typography>
          )}
          {expectations && (
            <Box sx={{ mt: 1 }}>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                Band expectations
              </Typography>
              <BandExpectationsBlock expectations={expectations} />
            </Box>
          )}
        </Paper>
      )}

      <TextField
        label="Your draft"
        multiline
        minRows={8}
        fullWidth
        size="small"
        value={displayText}
        onChange={readOnly ? undefined : onTextChange}
        placeholder="Write your response…"
        disabled={readOnly}
        inputProps={{
          'aria-describedby': 'draft-hint',
          readOnly: readOnly || undefined,
        }}
        sx={{ mb: 0.5 }}
      />
      <Typography id="draft-hint" variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1.5 }}>
        Formative coaching is advisory. Summative bands stay withheld until release.
        {!readOnly && saving ? ' · Saving…' : ''}
      </Typography>

      {actionError && (
        <Alert severity="error" sx={{ mb: 1.5 }} role="alert" onClose={() => setActionError(null)}>
          {actionError}
        </Alert>
      )}
      {msg && (
        <Alert severity="success" sx={{ mb: 1.5 }} role="status" onClose={() => setMsg(null)}>
          {msg}
        </Alert>
      )}

      {run && (
        <Paper sx={{ p: 1.5, mb: 1.5 }} component="section" aria-labelledby="coaching-heading">
          <Stack direction="row" spacing={1} sx={{ mb: 1 }} alignItems="center" flexWrap="wrap" useFlexGap>
            <Typography id="coaching-heading" variant="subtitle1">Results</Typography>
            <Chip size="small" label={run.status || 'done'} />
            {run.gate_decision && <Chip size="small" label={`gate: ${run.gate_decision}`} />}
            {coachingPayload.watermark && (
              <Chip size="small" color="warning" label={coachingPayload.watermark} />
            )}
          </Stack>

          {withheld ? (
            <Alert severity="info" sx={{ mb: 1.5 }} role="status">
              Summative bands are withheld until a marker releases your results.
            </Alert>
          ) : (
            <>
              <Typography variant="subtitle2">Advisory bands</Typography>
              <Stack direction="row" spacing={1} sx={{ mb: 1.5, flexWrap: 'wrap' }} useFlexGap>
                {Object.keys(bands).length === 0 ? (
                  <Typography variant="body2" color="text.secondary">No bands yet.</Typography>
                ) : (
                  Object.entries(bands).map(([k, v]) => (
                    <Chip key={k} size="small" label={`${k}: ${v}`} />
                  ))
                )}
              </Stack>
            </>
          )}

          <Typography variant="subtitle2">Strengths</Typography>
          <ul style={{ marginTop: 4, marginBottom: 8 }}>
            {(coachingPayload.strengths || []).map((s) => (
              <li key={s}><Typography variant="body2">{s}</Typography></li>
            ))}
          </ul>
          <Typography variant="subtitle2">Diagnosis → Action</Typography>
          <ul style={{ marginTop: 4, marginBottom: 8 }}>
            {(coachingPayload.diagnosis_actions || []).map((d) => (
              <li key={d.id || d.diagnosis}>
                <Typography variant="body2"><strong>{d.diagnosis}</strong> — {d.action}</Typography>
              </li>
            ))}
          </ul>
          <LctCodesTable segments={run.segments || []} wave={run.wave} />
          {(run.wave?.points?.length > 0) && (
            <Box sx={{ mt: 1.5 }}>
              <Typography variant="subtitle2">Semantic wave (SG)</Typography>
              <WaveChart points={run.wave.points} />
            </Box>
          )}
        </Paper>
      )}

      {!readOnly && (
        <Paper sx={{ p: 1.5 }} component="section" aria-labelledby="appeal-heading">
          <Typography id="appeal-heading" variant="subtitle2" sx={{ mb: 1 }}>Request review</Typography>
          {appeal ? (
            <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
              <Typography variant="body2">Existing appeal</Typography>
              <Chip size="small" label={appeal.status || 'open'} color={appeal.status === 'accepted' ? 'success' : 'default'} />
              {appeal.resolution && (
                <Typography variant="body2" color="text.secondary">{appeal.resolution}</Typography>
              )}
              {(appeal.status || '').toLowerCase() === 'open' && !readOnly && (
                <Button
                  size={primarySize}
                  variant="outlined"
                  color="inherit"
                  onClick={onWithdrawAppeal}
                  disabled={withdrawBusy}
                  aria-busy={withdrawBusy}
                  sx={{ minHeight: primarySize === 'medium' ? 40 : undefined }}
                >
                  {withdrawBusy ? 'Withdrawing…' : 'Withdraw'}
                </Button>
              )}
            </Stack>
          ) : (
            <Stack spacing={1.25}>
              <TextField
                size="small"
                label="Reason"
                value={appealReason}
                onChange={(e) => setAppealReason(e.target.value)}
                multiline
                minRows={2}
                fullWidth
                disabled={!canRequestReview(assignment, run)}
                helperText={
                  canRequestReview(assignment, run)
                    ? 'Explain why you are requesting a review of this run.'
                    : 'Available after formative coaching completes or summative results are released.'
                }
              />
              <Box>
                <Button
                  size={primarySize}
                  variant="outlined"
                  onClick={onAppeal}
                  disabled={appealBusy || !appealReason.trim() || !canRequestReview(assignment, run)}
                  aria-busy={appealBusy}
                  sx={{ minHeight: primarySize === 'medium' ? 40 : undefined }}
                >
                  {appealBusy ? 'Submitting…' : 'Request review'}
                </Button>
              </Box>
            </Stack>
          )}
        </Paper>
      )}
    </Box>
  );
}

export default function AssignmentPage() {
  useDocumentTitle('Learn · Assignment');
  const { assignmentId } = useParams();

  return (
    <PageContainer>
      <SkipToMain targetId="learn-assignment" />
      <LearnReadingWidth>
        <Box component="main" id="learn-assignment" tabIndex={-1} aria-label="Assignment">
          <AssignmentDesk assignmentId={assignmentId} />
        </Box>
      </LearnReadingWidth>
    </PageContainer>
  );
}
