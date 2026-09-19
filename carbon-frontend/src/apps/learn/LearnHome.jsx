// Learn home — join, due soon, released results, latest coaching (Phase D).

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link as RouterLink, useNavigate } from 'react-router-dom';
import {
  Alert, Box, Button, Chip, Paper, Stack, TextField, Typography,
} from '@mui/material';
import EditNoteIcon from '@mui/icons-material/EditNote';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../components/Page/ErrorAlert';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import {
  fetchMyAssignments, fetchMyProgress, fetchMySubmissions, joinCourseByCode,
} from '../../api/gradevance';
import SkipToMain from '../../components/gradevance/SkipToMain';
import LearnReadingWidth, { useLearnPrimarySize } from '../../components/gradevance/LearnReadingWidth';

function statusChipColor(status) {
  switch ((status || '').toLowerCase()) {
    case 'released': return 'success';
    case 'submitted': return 'info';
    case 'drafted':
    case 'draft': return 'default';
    case 'open': return 'primary';
    default: return 'default';
  }
}

export default function LearnHome() {
  useDocumentTitle('Learn');
  const { token } = useAuth();
  const navigate = useNavigate();
  const primarySize = useLearnPrimarySize();
  const [assignments, setAssignments] = useState([]);
  const [submissions, setSubmissions] = useState([]);
  const [progress, setProgress] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [joinCode, setJoinCode] = useState('');
  const [joinMsg, setJoinMsg] = useState(null);
  const [joinError, setJoinError] = useState(null);
  const [joinBusy, setJoinBusy] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      fetchMyAssignments(token),
      fetchMySubmissions(token).catch(() => ({ results: [] })),
      fetchMyProgress(token).catch(() => ({ results: [] })),
    ])
      .then(([asgData, subData, progData]) => {
        setAssignments(asgData.results || asgData || []);
        setSubmissions(subData.results || subData || []);
        setProgress(progData.results || progData || []);
      })
      .catch((err) => setError(err?.message || 'Failed to load your studies'))
      .finally(() => setLoading(false));
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  const onJoin = async () => {
    if (!joinCode.trim()) return;
    setJoinBusy(true);
    setJoinMsg(null);
    setJoinError(null);
    try {
      const course = await joinCourseByCode(token, joinCode.trim());
      setJoinMsg(`Joined ${course.code} — ${course.name}`);
      setJoinCode('');
      load();
    } catch (err) {
      setJoinError(err?.message || 'Join failed');
    } finally {
      setJoinBusy(false);
    }
  };

  const dueSoon = useMemo(() => {
    const now = Date.now();
    const week = 7 * 24 * 60 * 60 * 1000;
    return [...assignments]
      .filter((a) => {
        const dueRaw = a.due_at || a.due_date;
        if (!dueRaw) return false;
        const due = new Date(dueRaw).getTime();
        return !Number.isNaN(due) && due >= now && due <= now + week;
      })
      .sort((a, b) => new Date(a.due_at || a.due_date) - new Date(b.due_at || b.due_date))
      .slice(0, 5);
  }, [assignments]);

  const releasedResults = useMemo(() => {
    const fromAsg = assignments.filter((a) => (a.my_status || '').toLowerCase() === 'released');
    const fromProg = progress.filter((r) => r.released === true || (r.status || '').toLowerCase() === 'released');
    const seen = new Set();
    const rows = [];
    for (const a of fromAsg) {
      const id = a.id;
      if (seen.has(String(id))) continue;
      seen.add(String(id));
      rows.push({
        id,
        title: a.title,
        assignment_id: id,
        status: a.my_status || 'released',
        course_title: a.course_title,
      });
    }
    for (const r of fromProg) {
      const id = r.assignment_id || r.assignment;
      if (!id || seen.has(String(id))) continue;
      seen.add(String(id));
      rows.push({
        id: r.run_id || id,
        title: r.title,
        assignment_id: id,
        status: r.status || 'released',
        bands: r.advisory_bands,
      });
    }
    return rows.slice(0, 8);
  }, [assignments, progress]);

  const latestCoaching = useMemo(() => {
    const withCoach = submissions
      .map((s) => ({
        submission: s,
        coaching: s.latest_run?.coaching || s.coaching || s.run?.coaching,
        assignmentId: s.assignment || s.assignment_id,
        title: s.assignment_title || s.title,
      }))
      .filter((x) => x.coaching && (x.coaching.strengths?.length || x.coaching.diagnosis_actions?.length));
    return withCoach[0] || null;
  }, [submissions]);

  if (loading) {
    return (
      <PageContainer>
        <LearnReadingWidth>
          <PageHeader icon={EditNoteIcon} title="Learn" subtitle="My studies" />
          <LoadingSkeleton variant="console" />
        </LearnReadingWidth>
      </PageContainer>
    );
  }

  if (error) {
    return (
      <PageContainer>
        <LearnReadingWidth>
          <PageHeader icon={EditNoteIcon} title="Learn" subtitle="My studies" />
          <ErrorAlert message={error} onRetry={load} />
        </LearnReadingWidth>
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <SkipToMain targetId="learn-home" />
      <LearnReadingWidth>
      <Box component="main" id="learn-home" tabIndex={-1} aria-label="Learn home">
        <PageHeader
          icon={EditNoteIcon}
          title="Learn"
          subtitle="Your assignments and coaching — calm, private, just for you."
          actions={(
            <Button
              size={primarySize}
              variant="contained"
              endIcon={<ArrowForwardIcon />}
              onClick={() => navigate('/learn/assignments')}
              sx={{ minHeight: primarySize === 'medium' ? 40 : undefined }}
            >
              My assignments
            </Button>
          )}
        />

        <Paper
          variant="outlined"
          sx={{ p: 1.5, mb: 2 }}
          component="form"
          onSubmit={(e) => { e.preventDefault(); onJoin(); }}
          aria-label="Join course by entry code"
        >
          <Typography variant="subtitle2" sx={{ mb: 1 }}>Join a course</Typography>
          <Stack
            direction={{ xs: 'column', sm: 'row' }}
            spacing={1}
            alignItems={{ xs: 'stretch', sm: 'center' }}
          >
            <TextField
              size="small"
              label="Course entry code"
              value={joinCode}
              onChange={(e) => setJoinCode(e.target.value)}
              sx={{ minWidth: 180, flex: 1 }}
            />
            <Button
              size={primarySize}
              variant="outlined"
              type="submit"
              disabled={joinBusy || !joinCode.trim()}
              aria-busy={joinBusy}
              sx={{ minHeight: primarySize === 'medium' ? 40 : undefined }}
            >
              Join
            </Button>
          </Stack>
          {joinMsg && <Alert severity="success" sx={{ mt: 1 }} role="status">{joinMsg}</Alert>}
          {joinError && <Alert severity="error" sx={{ mt: 1 }} role="alert">{joinError}</Alert>}
        </Paper>

        <Typography variant="subtitle2" sx={{ mb: 1 }} id="due-soon-heading">Due soon</Typography>
        {dueSoon.length === 0 ? (
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Nothing due in the next week.
            {' '}
            <RouterLink to="/learn/assignments">Browse all assignments</RouterLink>
          </Typography>
        ) : (
          <Stack spacing={1} sx={{ mb: 2 }} role="list" aria-labelledby="due-soon-heading">
            {dueSoon.map((a) => (
              <Paper
                key={a.id}
                variant="outlined"
                role="listitem"
                sx={{ p: 1.5, cursor: 'pointer' }}
                onClick={() => navigate(`/learn/assignments/${a.id}`)}
              >
                <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                  <Typography variant="body2" sx={{ flex: 1, minWidth: 120 }}>
                    {a.title || `Assignment ${a.id}`}
                  </Typography>
                  <Chip
                    size="small"
                    label={a.my_status || a.status || 'open'}
                    color={statusChipColor(a.my_status || a.status)}
                  />
                  <Typography variant="caption" color="text.secondary">
                    Due {new Date(a.due_at || a.due_date).toLocaleDateString()}
                  </Typography>
                </Stack>
              </Paper>
            ))}
          </Stack>
        )}

        <Typography variant="subtitle2" sx={{ mb: 1, mt: 2 }} id="released-heading">Released results</Typography>
        {releasedResults.length === 0 ? (
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            No released results yet.
            {' '}
            <RouterLink to="/learn/progress">View progress</RouterLink>
          </Typography>
        ) : (
          <Stack spacing={1} sx={{ mb: 2 }} role="list" aria-labelledby="released-heading">
            {releasedResults.map((r) => (
              <Paper
                key={r.id}
                variant="outlined"
                role="listitem"
                sx={{ p: 1.5, cursor: r.assignment_id ? 'pointer' : 'default' }}
                onClick={() => {
                  if (r.assignment_id) navigate(`/learn/assignments/${r.assignment_id}`);
                }}
              >
                <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                  <Box sx={{ flex: 1, minWidth: 120 }}>
                    <Typography variant="body2">{r.title || 'Assignment'}</Typography>
                    {r.course_title && (
                      <Typography variant="caption" color="text.secondary">{r.course_title}</Typography>
                    )}
                  </Box>
                  <Chip size="small" color="success" label={r.status || 'released'} />
                  {r.bands && Object.entries(r.bands).slice(0, 3).map(([k, v]) => (
                    <Chip key={k} size="small" variant="outlined" label={`${k}: ${v}`} />
                  ))}
                </Stack>
              </Paper>
            ))}
          </Stack>
        )}

        <Typography variant="subtitle2" sx={{ mb: 1 }}>Latest coaching</Typography>
        {!latestCoaching ? (
          <Alert severity="info" sx={{ mb: 1 }} role="status">
            Open an assignment and choose “Get formative coaching” to see Strengths → Diagnosis → Action here.
          </Alert>
        ) : (
          <Paper variant="outlined" sx={{ p: 1.5, mb: 1 }}>
            <Typography variant="body2" sx={{ mb: 0.5 }}>
              {latestCoaching.title || 'Recent draft'}
            </Typography>
            {(latestCoaching.coaching.strengths || []).slice(0, 2).map((s) => (
              <Typography key={s} variant="body2" color="text.secondary">• {s}</Typography>
            ))}
            {latestCoaching.assignmentId && (
              <Button
                size={primarySize}
                sx={{ mt: 1, minHeight: primarySize === 'medium' ? 40 : undefined }}
                onClick={() => navigate(`/learn/assignments/${latestCoaching.assignmentId}`)}
              >
                Continue
              </Button>
            )}
          </Paper>
        )}
      </Box>
      </LearnReadingWidth>
    </PageContainer>
  );
}
