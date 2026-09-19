// Teach stems console — first-class stems with FilteredDataGrid + multitab
// (Stems | Author | Courses). Click row → stem master-detail. ADR-0042 / Carbon IA.

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Alert, Box, Button, Chip, FormControl, IconButton, InputLabel, MenuItem, Paper,
  Select, Stack, Tab, Tabs, TextField, Tooltip, Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import ClassIcon from '@mui/icons-material/Class';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import VisibilityIcon from '@mui/icons-material/Visibility';
import FilteredDataGrid from '../../components/FilteredDataGrid';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../components/Page/ErrorAlert';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import {
  createAssignment, createCourse, createCourseEnrollment, fetchAssignments,
  fetchCourseEnrollments, fetchCourses, fetchProfiles, fetchPublishGate, patchEnrollment,
} from '../../api/gradevance';
import SkipToMain from '../gradevance/SkipToMain';
import { clearTeachStemContext } from './teachContext';

const TAB_STORAGE = 'teach.stemsConsole.tab';
const TAB_KEYS = ['Stems', 'Author', 'Courses'];

function gateKappa(gate) {
  const rel = gate?.reliability;
  if (gate?.kappa != null) return Number(gate.kappa);
  if (typeof rel === 'object' && rel?.kappa != null) return Number(rel.kappa);
  if (typeof rel === 'number') return rel;
  return null;
}

function stemExcerpt(brief, n = 72) {
  const stem = (brief?.stem || '').trim();
  if (!stem) return '—';
  return stem.length > n ? `${stem.slice(0, n)}…` : stem;
}

export default function StemsPage() {
  useDocumentTitle('Teach · Stems');
  const { token } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [tabIndex, setTabIndex] = useState(() => {
    const q = searchParams.get('tab');
    if (q === 'author') return 1;
    if (q === 'courses') return 2;
    const n = parseInt(localStorage.getItem(TAB_STORAGE) || '0', 10);
    return Number.isFinite(n) && n < TAB_KEYS.length ? n : 0;
  });

  const [courses, setCourses] = useState([]);
  const [assignments, setAssignments] = useState([]);
  const [profiles, setProfiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);

  const [searchValue, setSearchValue] = useState('');
  const [filters, setFilters] = useState({
    status: '',
    mode: '',
    course: '',
    profile: '',
  });

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

  const [courseSearch, setCourseSearch] = useState('');
  const [rosterCourseId, setRosterCourseId] = useState(null);
  const [rosterRows, setRosterRows] = useState([]);
  const [rosterLoading, setRosterLoading] = useState(false);
  const [rosterUser, setRosterUser] = useState('');
  const [rosterRole, setRosterRole] = useState('student');

  useEffect(() => {
    clearTeachStemContext();
  }, []);

  const handleTabChange = (_, v) => {
    setTabIndex(v);
    localStorage.setItem(TAB_STORAGE, String(v));
  };

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      fetchCourses(token),
      fetchAssignments(token),
      fetchProfiles(token),
    ])
      .then(([c, a, p]) => {
        const courseRows = c.results || [];
        setCourses(courseRows);
        setAssignments(a.results || []);
        const rows = p.results || [];
        setProfiles(rows);
        if (rows.length && !rows.some((x) => x.pack_id === asgPack)) {
          setAsgPack(rows[0].pack_id);
        }
        if (courseRows.length && !asgCourse) {
          setAsgCourse(courseRows[0].id);
        }
      })
      .catch((e) => setError(e?.message || 'Failed to load stems'))
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
      .catch((e) => {
        if (!cancelled) setGate({ required: true, passed: false, reason: e?.message || 'Gate check failed' });
      })
      .finally(() => { if (!cancelled) setGateLoading(false); });
    return () => { cancelled = true; };
  }, [token, asgPack, asgMode, profiles]);

  const courseMap = useMemo(() => {
    const map = {};
    for (const c of courses) map[c.id] = c;
    return map;
  }, [courses]);

  const filterDefs = useMemo(() => [
    {
      key: 'status',
      label: 'Status',
      emptyLabel: 'All statuses',
      options: [
        { value: 'draft', label: 'Draft' },
        { value: 'published', label: 'Published' },
        { value: 'archived', label: 'Archived' },
      ],
    },
    {
      key: 'mode',
      label: 'Mode',
      emptyLabel: 'All modes',
      options: [
        { value: 'formative', label: 'Formative' },
        { value: 'summative', label: 'Summative' },
        { value: 'calibration', label: 'Calibration' },
      ],
    },
    {
      key: 'course',
      label: 'Course',
      emptyLabel: 'All courses',
      options: courses.map((c) => ({ value: String(c.id), label: `${c.code} — ${c.name}` })),
    },
    {
      key: 'profile',
      label: 'Profile pack',
      emptyLabel: 'All packs',
      options: [...new Set(assignments.map((a) => a.profile_pack_id).filter(Boolean))]
        .sort()
        .map((id) => ({ value: id, label: id })),
    },
  ], [courses, assignments]);

  const filteredRows = useMemo(() => {
    const q = searchValue.trim().toLowerCase();
    return assignments.filter((a) => {
      if (q) {
        const course = courseMap[a.course];
        const hay = [
          a.title, a.mode, a.status, a.profile_pack_id,
          course?.code, course?.name, a.brief?.stem, a.brief?.instructions,
        ].filter(Boolean).join(' ').toLowerCase();
        if (!hay.includes(q)) return false;
      }
      if (filters.status && a.status !== filters.status) return false;
      if (filters.mode && a.mode !== filters.mode) return false;
      if (filters.course && String(a.course) !== String(filters.course)) return false;
      if (filters.profile && a.profile_pack_id !== filters.profile) return false;
      return true;
    });
  }, [assignments, searchValue, filters, courseMap]);

  const openStem = useCallback((row) => {
    navigate(`/teach/stems/${row.id}`);
  }, [navigate]);

  const columns = useMemo(() => [
    {
      field: 'title',
      headerName: 'Stem',
      flex: 1.4,
      minWidth: 200,
      renderCell: (params) => (
        <Box sx={{ minWidth: 0 }}>
          <Typography noWrap sx={{ fontSize: '0.75rem', fontWeight: 600 }}>
            {params.row.title || '—'}
          </Typography>
          <Typography noWrap sx={{ fontSize: '0.65rem', color: 'text.secondary' }}>
            {stemExcerpt(params.row.brief)}
          </Typography>
        </Box>
      ),
    },
    {
      field: 'mode',
      headerName: 'Mode',
      width: 110,
      renderCell: (p) => <Chip size="small" label={p.value} />,
    },
    {
      field: 'status',
      headerName: 'Status',
      width: 110,
      renderCell: (p) => (
        <Chip
          size="small"
          variant="outlined"
          color={p.value === 'draft' ? 'warning' : p.value === 'published' ? 'success' : 'default'}
          label={p.value}
        />
      ),
    },
    {
      field: 'course',
      headerName: 'Course',
      width: 120,
      valueGetter: (_v, row) => courseMap[row.course]?.code || '—',
    },
    {
      field: 'profile_pack_id',
      headerName: 'Profile',
      flex: 1,
      minWidth: 140,
      renderCell: (p) => (
        <Typography variant="caption" noWrap>
          {p.row.profile_pack_id}@v{p.row.profile_version}
        </Typography>
      ),
    },
    {
      field: 'updated_at',
      headerName: 'Updated',
      width: 140,
      valueGetter: (v) => (v ? new Date(v).toLocaleDateString() : '—'),
    },
    {
      field: 'actions',
      headerName: '',
      width: 72,
      sortable: false,
      filterable: false,
      renderCell: (params) => (
        <Tooltip title="Open stem">
          <IconButton
            size="small"
            aria-label="Open stem"
            onClick={(e) => {
              e.stopPropagation();
              openStem(params.row);
            }}
          >
            <VisibilityIcon fontSize="inherit" />
          </IconButton>
        </Tooltip>
      ),
    },
  ], [courseMap, openStem]);

  const filteredCourses = useMemo(() => {
    const q = courseSearch.trim().toLowerCase();
    if (!q) return courses;
    return courses.filter((c) => {
      const hay = [c.code, c.name, c.discipline, c.entry_code].filter(Boolean).join(' ').toLowerCase();
      return hay.includes(q);
    });
  }, [courses, courseSearch]);

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

  const openRoster = async (courseId) => {
    if (rosterCourseId === courseId) {
      setRosterCourseId(null);
      setRosterRows([]);
      return;
    }
    setRosterCourseId(courseId);
    setRosterLoading(true);
    setError(null);
    try {
      const data = await fetchCourseEnrollments(token, courseId);
      setRosterRows(data.results || []);
    } catch (e) {
      setError(e?.message || 'Failed to load roster');
      setRosterRows([]);
    } finally {
      setRosterLoading(false);
    }
  };

  const onToggleEnrollment = async (row) => {
    if (!rosterCourseId || !row?.id) return;
    setBusy(true);
    setError(null);
    setMsg(null);
    try {
      const nextActive = row.active === false;
      await patchEnrollment(token, rosterCourseId, row.id, { active: nextActive });
      setMsg(nextActive ? `Reactivated ${row.user}` : `Deactivated ${row.user}`);
      const data = await fetchCourseEnrollments(token, rosterCourseId);
      setRosterRows(data.results || []);
    } catch (e) {
      setError(e?.message || 'Failed to update enrollment');
    } finally {
      setBusy(false);
    }
  };

  const onAddEnrollment = async () => {
    if (!rosterCourseId || !rosterUser.trim()) return;
    setBusy(true);
    setError(null);
    setMsg(null);
    try {
      await createCourseEnrollment(token, rosterCourseId, {
        username: rosterUser.trim(),
        role: rosterRole,
      });
      setMsg(`Enrolled ${rosterUser.trim()} as ${rosterRole}`);
      setRosterUser('');
      const data = await fetchCourseEnrollments(token, rosterCourseId);
      setRosterRows(data.results || []);
    } catch (e) {
      setError(e?.message || 'Add enrollment failed');
    } finally {
      setBusy(false);
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
      setMsg(status === 'draft' ? `Draft saved — ${asg.title}` : `Stem published — ${asg.title}`);
      setAsgTitle('');
      setStem('');
      setInstructions('');
      navigate(`/teach/stems/${asg.id}`);
    } catch (e) {
      setError(e?.message || 'Create stem failed');
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <PageContainer>
        <PageHeader icon={ClassIcon} title="Stems" subtitle="Author · filter · open master-detail" />
        <LoadingSkeleton variant="table" />
      </PageContainer>
    );
  }

  const kappa = gateKappa(gate);

  const stemsTab = (
    <FilteredDataGrid
      embedded
      searchPlaceholder="Search stems, course, profile…"
      rows={filteredRows}
      columns={columns}
      loading={false}
      countLabel={`${filteredRows.length} of ${assignments.length} stems`}
      searchValue={searchValue}
      onSearchChange={setSearchValue}
      filterDefs={filterDefs}
      filterValues={filters}
      onFilterChange={(key, value) => setFilters((prev) => ({ ...prev, [key]: value }))}
      onClearFilters={() => {
        setSearchValue('');
        setFilters({ status: '', mode: '', course: '', profile: '' });
      }}
      emptyMessage="No stems yet"
      emptySubtext="Author a stem on the Author tab, or clear filters."
      getRowId={(r) => r.id}
      height={520}
      onRowClick={(params) => openStem(params.row)}
      initialState={{
        sorting: { sortModel: [{ field: 'updated_at', sort: 'desc' }] },
      }}
    />
  );

  const authorTab = (
    <Paper sx={{ p: 1.5 }} component="section" aria-label="Author new stem">
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
        <TextField size="small" label="Stem title" value={asgTitle} onChange={(e) => setAsgTitle(e.target.value)} fullWidth />
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
              <Button size="small" color="inherit" onClick={() => navigate(`/teach/calibration?profile_pack_id=${encodeURIComponent(asgPack)}`)}>
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
            Publish stem
          </Button>
        </Box>
      </Stack>
    </Paper>
  );

  const coursesTab = (
    <Stack spacing={2}>
      <Paper sx={{ p: 1.5 }} component="section" aria-label="New course">
        <Typography variant="subtitle2" sx={{ mb: 1 }}>New course</Typography>
        <Stack spacing={1.25} direction={{ xs: 'column', md: 'row' }} alignItems="flex-start">
          <TextField size="small" label="Code" value={courseCode} onChange={(e) => setCourseCode(e.target.value)} sx={{ minWidth: 120 }} />
          <TextField size="small" label="Name" value={courseName} onChange={(e) => setCourseName(e.target.value)} fullWidth />
          <TextField size="small" label="Discipline" value={discipline} onChange={(e) => setDiscipline(e.target.value)} sx={{ minWidth: 160 }} />
          <Button size="small" variant="contained" onClick={onCreateCourse} disabled={!courseCode.trim() || !courseName.trim()}>
            Create course
          </Button>
        </Stack>
      </Paper>

      <FilteredDataGrid
        embedded
        searchPlaceholder="Search courses…"
        rows={filteredCourses}
        columns={[
          { field: 'code', headerName: 'Code', width: 120 },
          { field: 'name', headerName: 'Name', flex: 1, minWidth: 160 },
          { field: 'discipline', headerName: 'Discipline', width: 140 },
          { field: 'entry_code', headerName: 'Entry code', width: 120 },
          {
            field: 'actions',
            headerName: '',
            width: 100,
            sortable: false,
            renderCell: (p) => (
              <Button size="small" onClick={() => openRoster(p.row.id)}>
                {rosterCourseId === p.row.id ? 'Hide' : 'Roster'}
              </Button>
            ),
          },
        ]}
        loading={false}
        countLabel={`${filteredCourses.length} of ${courses.length} courses`}
        searchValue={courseSearch}
        onSearchChange={setCourseSearch}
        filterDefs={[]}
        filterValues={{}}
        onFilterChange={() => {}}
        onClearFilters={() => setCourseSearch('')}
        emptyMessage="No courses yet"
        getRowId={(r) => r.id}
        height={320}
      />

      {rosterCourseId && (
        <Paper sx={{ p: 1.5 }} component="section" aria-label="Course roster">
          <Typography variant="subtitle2" sx={{ mb: 1 }}>
            Roster
            {courseMap[rosterCourseId] ? ` — ${courseMap[rosterCourseId].code}` : ''}
          </Typography>
          {rosterLoading ? (
            <Typography variant="body2" color="text.secondary">Loading…</Typography>
          ) : (
            <Stack spacing={1}>
              {(rosterRows || []).map((row) => (
                <Stack key={row.id} direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                  <Typography variant="body2" sx={{ minWidth: 120 }}>{row.user}</Typography>
                  <Chip size="small" label={row.role} />
                  <Chip
                    size="small"
                    variant="outlined"
                    color={row.active === false ? 'default' : 'success'}
                    label={row.active === false ? 'inactive' : 'active'}
                  />
                  <Typography variant="caption" color="text.secondary">{row.source}</Typography>
                  <Button size="small" onClick={() => onToggleEnrollment(row)} disabled={busy}>
                    {row.active === false ? 'Reactivate' : 'Deactivate'}
                  </Button>
                </Stack>
              ))}
              {!rosterRows.length && (
                <Typography variant="body2" color="text.secondary">No enrollments yet.</Typography>
              )}
              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} alignItems="flex-start">
                <TextField
                  size="small"
                  label="Username"
                  value={rosterUser}
                  onChange={(e) => setRosterUser(e.target.value)}
                  sx={{ minWidth: 160 }}
                />
                <FormControl size="small" sx={{ minWidth: 120 }}>
                  <InputLabel id="roster-role-label">Role</InputLabel>
                  <Select
                    labelId="roster-role-label"
                    label="Role"
                    value={rosterRole}
                    onChange={(e) => setRosterRole(e.target.value)}
                  >
                    <MenuItem value="student">Student</MenuItem>
                    <MenuItem value="ta">TA</MenuItem>
                    <MenuItem value="instructor">Instructor</MenuItem>
                  </Select>
                </FormControl>
                <Button
                  size="small"
                  variant="contained"
                  onClick={onAddEnrollment}
                  disabled={busy || !rosterUser.trim()}
                >
                  Add
                </Button>
              </Stack>
            </Stack>
          )}
        </Paper>
      )}
    </Stack>
  );

  return (
    <PageContainer>
      <SkipToMain targetId="teach-stems" />
      <Box component="main" id="teach-stems" tabIndex={-1} aria-label="Stems console">
        <PageHeader
          icon={ClassIcon}
          title="Stems"
          subtitle="First-class stems — filter, open master-detail, operate cohort."
          actions={(
            <Stack direction="row" spacing={0.75}>
              <Button
                size="small"
                variant="contained"
                startIcon={<AddIcon />}
                onClick={() => handleTabChange(null, 1)}
              >
                New stem
              </Button>
              <Button
                size="small"
                variant="outlined"
                endIcon={<OpenInNewIcon />}
                onClick={() => navigate('/teach/calibration')}
              >
                Calibration
              </Button>
            </Stack>
          )}
        />
        {error && <ErrorAlert message={error} onRetry={load} />}
        {msg && <Alert severity="success" sx={{ mb: 1.5 }} role="status">{msg}</Alert>}

        <Tabs
          value={tabIndex}
          onChange={handleTabChange}
          sx={{ mb: 2, borderBottom: 1, borderColor: 'divider', minHeight: 36 }}
          aria-label="Stems console tabs"
        >
          {TAB_KEYS.map((label) => (
            <Tab key={label} label={label} sx={{ minHeight: 36, py: 0.5, textTransform: 'none' }} />
          ))}
        </Tabs>

        {tabIndex === 0 && stemsTab}
        {tabIndex === 1 && authorTab}
        {tabIndex === 2 && coursesTab}
      </Box>
    </PageContainer>
  );
}
