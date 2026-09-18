// Professor: Courses → Assignments (stem) — design plane entry.
// compact-ui: size=small, PageHeader actions, no in-page breadcrumbs.

import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Alert, Box, Button, Chip, FormControl, InputLabel, MenuItem, Paper, Select,
  Stack, Table, TableBody, TableCell, TableHead, TableRow, TextField, Typography,
} from '@mui/material';
import ClassIcon from '@mui/icons-material/Class';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../components/Page/ErrorAlert';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import {
  createAssignment, createCourse, fetchAssignments, fetchCourses, fetchProfiles, fetchPublishGate,
} from '../../api/gradevance';
import SkipToMain from './SkipToMain';

function gateKappa(gate) {
  const rel = gate?.reliability;
  if (gate?.kappa != null) return Number(gate.kappa);
  if (typeof rel === 'object' && rel?.kappa != null) return Number(rel.kappa);
  if (typeof rel === 'number') return rel;
  return null;
}

export default function CoursesPage() {
  useDocumentTitle('GradeVance · Courses');
  const { token } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [courses, setCourses] = useState([]);
  const [assignments, setAssignments] = useState([]);
  const [profiles, setProfiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);

  const [courseCode, setCourseCode] = useState('');
  const [courseName, setCourseName] = useState('');
  const [discipline, setDiscipline] = useState('academic_english');

  const [asgCourse, setAsgCourse] = useState('');
  const [asgTitle, setAsgTitle] = useState('');
  const [asgPack, setAsgPack] = useState(searchParams.get('pack') || 'naa_cycle1_exam_prep');
  const [asgMode, setAsgMode] = useState('formative');
  const [stem, setStem] = useState('');
  const [instructions, setInstructions] = useState('');
  const [gate, setGate] = useState(null);
  const [gateLoading, setGateLoading] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      fetchCourses(token),
      fetchAssignments(token),
      fetchProfiles(token),
    ])
      .then(([c, a, p]) => {
        setCourses(c.results || []);
        setAssignments(a.results || []);
        const rows = p.results || [];
        setProfiles(rows);
        if (rows.length && !rows.some((x) => x.pack_id === asgPack)) {
          setAsgPack(rows[0].pack_id);
        }
        if ((c.results || []).length && !asgCourse) {
          setAsgCourse(c.results[0].id);
        }
      })
      .catch((e) => setError(e?.message || 'Failed to load courses'))
      .finally(() => setLoading(false));
  }, [token]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!token || !asgPack || asgMode !== 'summative') {
      setGate(null);
      return undefined;
    }
    let cancelled = false;
    setGateLoading(true);
    const selected = profiles.find((p) => p.pack_id === asgPack);
    fetchPublishGate(token, asgPack, selected?.version || 1, { as_mode: 'summative' })
      .then((g) => { if (!cancelled) setGate(g); })
      .catch((e) => { if (!cancelled) setGate({ required: true, passed: false, reason: e?.message || 'Gate check failed' }); })
      .finally(() => { if (!cancelled) setGateLoading(false); });
    return () => { cancelled = true; };
  }, [token, asgPack, asgMode, profiles]);

  const onCreateCourse = async () => {
    setError(null);
    setMsg(null);
    try {
      const c = await createCourse(token, {
        code: courseCode.trim(),
        name: courseName.trim(),
        discipline,
      });
      setMsg(`Course ${c.code} created`);
      setCourseCode('');
      setCourseName('');
      setAsgCourse(c.id);
      load();
    } catch (e) {
      setError(e?.message || 'Create course failed');
    }
  };

  const summativeBlocked = asgMode === 'summative' && gate?.required && gate?.passed === false;
  const canSaveDraft = Boolean(asgPack && stem.trim() && (asgCourse || !courses.length) && !busy);
  const canPublish = Boolean(canSaveDraft && !summativeBlocked && !gateLoading);

  const onCreateAssignment = async (status = 'published') => {
    if (!stem.trim()) {
      setError('Stem is required');
      return;
    }
    if (status === 'published' && summativeBlocked) {
      setError(gate?.reason || 'Summative publish blocked by reliability gate');
      return;
    }
    setBusy(true);
    setError(null);
    setMsg(null);
    try {
      const selected = profiles.find((p) => p.pack_id === asgPack);
      const asg = await createAssignment(token, {
        course: asgCourse || null,
        title: asgTitle || selected?.name || asgPack,
        mode: asgMode,
        status,
        profile_pack_id: asgPack,
        profile_version: selected?.version || 1,
        brief: {
          stem: stem.trim(),
          instructions: instructions.trim(),
          authored_by: 'professor',
        },
      });
      setMsg(status === 'draft' ? `Draft saved — ${asg.title}` : `Assignment published — ${asg.title}`);
      setAsgTitle('');
      setStem('');
      setInstructions('');
      navigate(`/apps/gradevance/assignments/${asg.id}`);
    } catch (e) {
      setError(e?.message || 'Create assignment failed');
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <PageContainer>
        <PageHeader icon={ClassIcon} title="Courses & stems" subtitle="Professor design plane" />
        <LoadingSkeleton variant="table" />
      </PageContainer>
    );
  }

  const kappa = gateKappa(gate);

  return (
    <PageContainer>
      <SkipToMain targetId="gv-courses" />
      <Box component="main" id="gv-courses" tabIndex={-1} aria-label="Courses and assignment stems">
        <PageHeader
          icon={ClassIcon}
          title="Courses & stems"
          subtitle="Define course → author stem → pin profile. Summative fails closed on κ."
          actions={(
            <Button
              size="small"
              variant="outlined"
              onClick={() => navigate('/apps/gradevance/calibration')}
            >
              Calibration
            </Button>
          )}
        />
        {error && <ErrorAlert message={error} onRetry={load} />}
        {msg && <Alert severity="success" sx={{ mb: 1.5 }} role="status">{msg}</Alert>}

        <Typography variant="subtitle2" sx={{ mb: 0.75 }} id="new-course-heading">New course</Typography>
        <Paper sx={{ p: 1.5, mb: 2 }} component="section" aria-labelledby="new-course-heading">
          <Stack spacing={1.25} direction={{ xs: 'column', md: 'row' }} alignItems="flex-start">
            <TextField size="small" label="Code" value={courseCode} onChange={(e) => setCourseCode(e.target.value)} sx={{ minWidth: 120 }} />
            <TextField size="small" label="Name" value={courseName} onChange={(e) => setCourseName(e.target.value)} fullWidth />
            <TextField size="small" label="Discipline" value={discipline} onChange={(e) => setDiscipline(e.target.value)} sx={{ minWidth: 160 }} />
            <Button size="small" variant="contained" onClick={onCreateCourse} disabled={!courseCode.trim() || !courseName.trim()}>
              Create course
            </Button>
          </Stack>
        </Paper>

        <Typography variant="subtitle2" sx={{ mb: 0.75 }} id="new-asg-heading">New assignment (stem)</Typography>
        <Paper sx={{ p: 1.5, mb: 2 }} component="section" aria-labelledby="new-asg-heading">
          <Stack spacing={1.25}>
            <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.25}>
              <FormControl size="small" fullWidth>
                <InputLabel id="asg-course-label">Course</InputLabel>
                <Select labelId="asg-course-label" label="Course" value={asgCourse} onChange={(e) => setAsgCourse(e.target.value)}>
                  {courses.map((c) => (
                    <MenuItem key={c.id} value={c.id}>{c.code} — {c.name}</MenuItem>
                  ))}
                </Select>
              </FormControl>
              <FormControl size="small" fullWidth>
                <InputLabel id="asg-pack-label">Profile pack</InputLabel>
                <Select labelId="asg-pack-label" label="Profile pack" value={asgPack} onChange={(e) => setAsgPack(e.target.value)}>
                  {profiles.map((p) => (
                    <MenuItem key={p.pack_id} value={p.pack_id}>
                      {p.name || p.pack_id} ({p.discipline}/{p.genre})
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <FormControl size="small" sx={{ minWidth: 140 }}>
                <InputLabel id="asg-mode-label">Mode</InputLabel>
                <Select labelId="asg-mode-label" label="Mode" value={asgMode} onChange={(e) => setAsgMode(e.target.value)}>
                  <MenuItem value="formative">Formative</MenuItem>
                  <MenuItem value="summative">Summative</MenuItem>
                  <MenuItem value="calibration">Calibration</MenuItem>
                </Select>
              </FormControl>
            </Stack>
            <TextField size="small" label="Assignment title" value={asgTitle} onChange={(e) => setAsgTitle(e.target.value)} fullWidth />
            <TextField
              size="small"
              label="Stem (prompt students see)"
              value={stem}
              onChange={(e) => setStem(e.target.value)}
              multiline
              minRows={3}
              fullWidth
              required
              helperText="Required. Bound into assignment.brief.stem at publish."
            />
            <TextField
              size="small"
              label="Instructions / success criteria"
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              multiline
              minRows={2}
              fullWidth
            />

            {asgMode === 'summative' && (
              <Alert
                severity={summativeBlocked ? 'warning' : gate?.required ? 'info' : 'success'}
                role="status"
                action={(
                  <Button size="small" color="inherit" onClick={() => navigate(`/apps/gradevance/calibration?profile_pack_id=${encodeURIComponent(asgPack)}`)}>
                    Open calibration
                  </Button>
                )}
              >
                {gateLoading && 'Checking publish gate…'}
                {!gateLoading && summativeBlocked && (
                  <>
                    Summative publish blocked
                    {kappa != null ? ` (κ ${kappa.toFixed(3)})` : ''}
                    {gate?.reason ? ` — ${gate.reason}` : ''}. Fix packs via Proposals; do not lower the bar.
                  </>
                )}
                {!gateLoading && !summativeBlocked && gate?.required && (
                  <>
                    Publish gate OK
                    {kappa != null ? ` · κ ${kappa.toFixed(3)}` : ''}
                    {gate?.held_out_n != null ? ` · held-out n=${gate.held_out_n}` : ''}
                    {gate?.minimum_kappa != null ? ` · min ${gate.minimum_kappa}` : ''}
                  </>
                )}
                {!gateLoading && gate && !gate.required && (gate.reason || 'Gate not required for this pack.')}
              </Alert>
            )}

            <Box>
              <Button
                size="small"
                variant="outlined"
                onClick={() => onCreateAssignment('draft')}
                disabled={!canSaveDraft}
                sx={{ mr: 1 }}
              >
                Save draft
              </Button>
              <Button
                size="small"
                variant="contained"
                onClick={() => onCreateAssignment('published')}
                disabled={!canPublish}
              >
                Publish assignment
              </Button>
            </Box>
          </Stack>
        </Paper>

        <Typography variant="subtitle2" sx={{ mb: 0.75 }} id="asg-list-heading">Assignments</Typography>
        <Paper component="section" aria-labelledby="asg-list-heading">
          <Table size="small" aria-label="Professor assignments">
            <TableHead>
              <TableRow>
                <TableCell>Title</TableCell>
                <TableCell>Mode</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Profile</TableCell>
                <TableCell>Stem</TableCell>
                <TableCell />
              </TableRow>
            </TableHead>
            <TableBody>
              {assignments.map((a) => (
                <TableRow key={a.id} hover>
                  <TableCell>{a.title}</TableCell>
                  <TableCell><Chip size="small" label={a.mode} /></TableCell>
                  <TableCell><Chip size="small" label={a.status} variant="outlined" /></TableCell>
                  <TableCell>
                    <Typography variant="caption">{a.profile_pack_id}@v{a.profile_version}</Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="caption" color="text.secondary">
                      {(a.brief?.stem || '').slice(0, 60) || '—'}
                      {(a.brief?.stem || '').length > 60 ? '…' : ''}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Button size="small" onClick={() => navigate(`/apps/gradevance/assignments/${a.id}`)}>
                      Open
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              {!assignments.length && (
                <TableRow>
                  <TableCell colSpan={6}>
                    <Typography color="text.secondary">No assignments yet — create a course and publish a stem above.</Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </Paper>
      </Box>
    </PageContainer>
  );
}
