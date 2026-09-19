// Stem master-detail — multitab console for one stem (ADR-0042).
// Tabs: Stem | Submissions (FilteredDataGrid) | Runs | Ingest.
// Sets teach stem context on load. Click submission → submission master-detail.

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import {
  Alert, Box, Button, Chip, Drawer, FormControl, IconButton, InputLabel, MenuItem,
  Paper, Select, Stack, Tab, Tabs, TextField, Tooltip, Typography,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import AssignmentIcon from '@mui/icons-material/Assignment';
import VisibilityIcon from '@mui/icons-material/Visibility';
import FilteredDataGrid from '../../components/FilteredDataGrid';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../components/Page/ErrorAlert';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import {
  batchAnalyzeAssignment, createSubmission, fetchAssignment,
  fetchDemoExamples, fetchKnowledgeBases, patchAssignment, submitAndAnalyze,
  uploadSubmissionFile,
} from '../../api/gradevance';
import SkipToMain from '../gradevance/SkipToMain';
import PackDetailDrawer from '../gradevance/PackDetailDrawer';
import { AssignmentDesk } from '../learn/AssignmentPage';
import { setTeachStemContext } from './teachContext';

const TAB_STORAGE = 'teach.stemDetail.tab';
const TAB_KEYS = ['Stem', 'Submissions', 'Runs', 'Ingest'];

export default function StemDetailPage() {
  const { assignmentId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
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
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewSubId, setPreviewSubId] = useState('');

  const [subSearch, setSubSearch] = useState('');
  const [subFilters, setSubFilters] = useState({
    status: '',
    run_status: '',
    released: '',
    group_by: '',
  });
  const [runSearch, setRunSearch] = useState('');
  const [runFilters, setRunFilters] = useState({ status: '', gate: '', released: '' });

  const [tabIndex, setTabIndex] = useState(() => {
    const q = searchParams.get('tab');
    const fromQ = TAB_KEYS.findIndex((k) => k.toLowerCase() === (q || '').toLowerCase());
    if (fromQ >= 0) return fromQ;
    const n = parseInt(localStorage.getItem(TAB_STORAGE) || '0', 10);
    return Number.isFinite(n) && n < TAB_KEYS.length ? n : 0;
  });

  useDocumentTitle(hub?.assignment?.title ? `Teach · ${hub.assignment.title}` : 'Teach · Stem');

  const handleTabChange = (_, v) => {
    setTabIndex(v);
    localStorage.setItem(TAB_STORAGE, String(v));
    const next = new URLSearchParams(searchParams);
    next.set('tab', TAB_KEYS[v].toLowerCase());
    setSearchParams(next, { replace: true });
  };

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
        setTeachStemContext({
          assignmentId: asg?.id || assignmentId,
          title: asg?.title,
          courseCode: asg?.course_detail?.code || '',
          mode: asg?.mode,
          status: asg?.status,
        });
      })
      .catch((e) => setError(e?.message || 'Failed to load stem'))
      .finally(() => setLoading(false));
  }, [token, assignmentId]);

  useEffect(() => { load(); }, [load]);

  const asg = hub?.assignment;
  const brief = asg?.brief || {};
  const isDraft = asg?.status === 'draft';

  const runsBySubmission = useMemo(() => {
    const map = {};
    for (const r of hub?.runs || []) {
      const sid = String(r.submission);
      if (!map[sid] || new Date(r.created_at) > new Date(map[sid].created_at)) {
        map[sid] = r;
      }
    }
    return map;
  }, [hub?.runs]);

  const submissionRows = useMemo(() => {
    const rows = (hub?.submissions || []).map((s) => {
      const latest = runsBySubmission[String(s.id)];
      return {
        ...s,
        student_label: s.student_username || s.external_student_key || (s.student_user != null ? `user#${s.student_user}` : '—'),
        excerpt: (s.text || '').slice(0, 100),
        latest_run_status: latest?.status || 'none',
        latest_gate: latest?.gate_decision || '—',
        latest_released: latest ? (latest.released ? 'yes' : 'no') : '—',
        latest_run_id: latest?.id || null,
        confidence: latest?.mean_confidence ?? null,
        group_key: subFilters.group_by === 'student'
          ? (s.student_username || s.external_student_key || 'unknown')
          : subFilters.group_by === 'run_status'
            ? (latest?.status || 'none')
            : subFilters.group_by === 'status'
              ? (s.status || '—')
              : '',
      };
    });

    const q = subSearch.trim().toLowerCase();
    let filtered = rows.filter((s) => {
      if (q) {
        const hay = [
          s.student_label, s.status, s.excerpt, s.text,
          s.latest_run_status, s.latest_gate, String(s.id),
        ].join(' ').toLowerCase();
        if (!hay.includes(q)) return false;
      }
      if (subFilters.status && s.status !== subFilters.status) return false;
      if (subFilters.run_status) {
        if (subFilters.run_status === 'none' && s.latest_run_status !== 'none') return false;
        if (subFilters.run_status !== 'none' && s.latest_run_status !== subFilters.run_status) return false;
      }
      if (subFilters.released === 'yes' && s.latest_released !== 'yes') return false;
      if (subFilters.released === 'no' && s.latest_released !== 'no') return false;
      return true;
    });

    if (subFilters.group_by) {
      filtered = [...filtered].sort((a, b) => String(a.group_key).localeCompare(String(b.group_key)));
    }
    return filtered;
  }, [hub?.submissions, runsBySubmission, subSearch, subFilters]);

  const runRows = useMemo(() => {
    const q = runSearch.trim().toLowerCase();
    return (hub?.runs || []).filter((r) => {
      if (q) {
        const hay = [r.status, r.gate_decision, r.profile_pack_id, String(r.submission), String(r.id)].join(' ').toLowerCase();
        if (!hay.includes(q)) return false;
      }
      if (runFilters.status && r.status !== runFilters.status) return false;
      if (runFilters.gate && r.gate_decision !== runFilters.gate) return false;
      if (runFilters.released === 'yes' && !r.released) return false;
      if (runFilters.released === 'no' && r.released) return false;
      return true;
    });
  }, [hub?.runs, runSearch, runFilters]);

  const openSubmission = useCallback((row) => {
    navigate(`/teach/stems/${assignmentId}/submissions/${row.id}`);
  }, [navigate, assignmentId]);

  const subFilterDefs = useMemo(() => [
    {
      key: 'status',
      label: 'Status',
      emptyLabel: 'All statuses',
      options: [
        { value: 'draft', label: 'Draft' },
        { value: 'submitted', label: 'Submitted' },
        { value: 'analyzed', label: 'Analyzed' },
      ],
    },
    {
      key: 'run_status',
      label: 'Latest run',
      emptyLabel: 'Any run',
      options: [
        { value: 'none', label: 'No run' },
        { value: 'complete', label: 'Complete' },
        { value: 'needs_review', label: 'Needs review' },
        { value: 'failed', label: 'Failed' },
        { value: 'pending', label: 'Pending' },
        { value: 'running', label: 'Running' },
      ],
    },
    {
      key: 'released',
      label: 'Released',
      emptyLabel: 'Any',
      options: [
        { value: 'yes', label: 'Released' },
        { value: 'no', label: 'Not released' },
      ],
    },
    {
      key: 'group_by',
      label: 'Group by',
      emptyLabel: 'No grouping',
      options: [
        { value: 'status', label: 'Submission status' },
        { value: 'run_status', label: 'Run status' },
        { value: 'student', label: 'Student' },
      ],
    },
  ], []);

  const subColumns = useMemo(() => {
    const cols = [];
    if (subFilters.group_by) {
      cols.push({
        field: 'group_key',
        headerName: 'Group',
        width: 130,
        renderCell: (p) => <Chip size="small" variant="outlined" label={p.value || '—'} />,
      });
    }
    cols.push(
      {
        field: 'student_label',
        headerName: 'Student',
        width: 130,
      },
      {
        field: 'status',
        headerName: 'Status',
        width: 110,
        renderCell: (p) => <Chip size="small" label={p.value} />,
      },
      {
        field: 'word_count',
        headerName: 'Words',
        width: 80,
        type: 'number',
      },
      {
        field: 'latest_run_status',
        headerName: 'Run',
        width: 120,
        renderCell: (p) => (
          <Chip
            size="small"
            variant="outlined"
            color={p.value === 'needs_review' ? 'warning' : p.value === 'complete' ? 'success' : 'default'}
            label={p.value}
          />
        ),
      },
      {
        field: 'latest_gate',
        headerName: 'Gate',
        width: 100,
      },
      {
        field: 'latest_released',
        headerName: 'Released',
        width: 90,
      },
      {
        field: 'excerpt',
        headerName: 'Excerpt',
        flex: 1,
        minWidth: 160,
        renderCell: (p) => (
          <Typography variant="caption" color="text.secondary" noWrap>
            {p.value}{(p.row.text || '').length > 100 ? '…' : ''}
          </Typography>
        ),
      },
      {
        field: 'created_at',
        headerName: 'Created',
        width: 150,
        valueGetter: (v) => (v ? new Date(v).toLocaleString() : '—'),
      },
      {
        field: 'actions',
        headerName: '',
        width: 72,
        sortable: false,
        renderCell: (params) => (
          <Tooltip title="Open submission">
            <IconButton
              size="small"
              aria-label="Open submission"
              onClick={(e) => {
                e.stopPropagation();
                openSubmission(params.row);
              }}
            >
              <VisibilityIcon fontSize="inherit" />
            </IconButton>
          </Tooltip>
        ),
      },
    );
    return cols;
  }, [subFilters.group_by, openSubmission]);

  const runFilterDefs = useMemo(() => [
    {
      key: 'status',
      label: 'Status',
      emptyLabel: 'All',
      options: [
        { value: 'complete', label: 'Complete' },
        { value: 'needs_review', label: 'Needs review' },
        { value: 'failed', label: 'Failed' },
        { value: 'pending', label: 'Pending' },
        { value: 'running', label: 'Running' },
      ],
    },
    {
      key: 'gate',
      label: 'Gate',
      emptyLabel: 'All',
      options: [
        { value: 'auto', label: 'Auto' },
        { value: 'review', label: 'Review' },
        { value: 'withhold', label: 'Withhold' },
      ],
    },
    {
      key: 'released',
      label: 'Released',
      emptyLabel: 'Any',
      options: [
        { value: 'yes', label: 'Yes' },
        { value: 'no', label: 'No' },
      ],
    },
  ], []);

  const runColumns = useMemo(() => [
    {
      field: 'status',
      headerName: 'Status',
      width: 130,
      renderCell: (p) => <Chip size="small" label={p.value} />,
    },
    { field: 'gate_decision', headerName: 'Gate', width: 110 },
    {
      field: 'mean_confidence',
      headerName: 'Confidence',
      width: 110,
      valueGetter: (v) => (v != null ? Number(v).toFixed(2) : '—'),
    },
    {
      field: 'released',
      headerName: 'Released',
      width: 90,
      valueGetter: (v) => (v ? 'yes' : 'no'),
    },
    {
      field: 'submission',
      headerName: 'Submission',
      width: 120,
      renderCell: (p) => (
        <Button
          size="small"
          onClick={(e) => {
            e.stopPropagation();
            navigate(`/teach/stems/${assignmentId}/submissions/${p.value}`);
          }}
        >
          Open
        </Button>
      ),
    },
    {
      field: 'created_at',
      headerName: 'Created',
      width: 150,
      valueGetter: (v) => (v ? new Date(v).toLocaleString() : '—'),
    },
    {
      field: 'actions',
      headerName: '',
      width: 100,
      sortable: false,
      renderCell: (p) => (
        <Button size="small" onClick={() => navigate(`/teach/runs/${p.row.id}`)}>
          Workbench
        </Button>
      ),
    },
  ], [navigate, assignmentId]);

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
      setMsg('Stem published');
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
          navigate(`/teach/runs/${payload.run.id}`);
          return;
        }
      } else {
        await createSubmission(token, { assignment: assignmentId, text: paste.trim() });
        setMsg('Submission saved (not analyzed)');
        setPaste('');
      }
      load();
      handleTabChange(null, 1);
    } catch (e) {
      setError(e?.message || 'Submit failed');
    } finally {
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
        navigate(`/teach/runs/${payload.run.id}`);
        return;
      }
      load();
      handleTabChange(null, 1);
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
        <PageHeader icon={AssignmentIcon} title="Stem" subtitle="Master-detail" />
        <LoadingSkeleton variant="table" />
      </PageContainer>
    );
  }

  if (error && !hub) {
    return (
      <PageContainer>
        <PageHeader icon={AssignmentIcon} title="Stem" />
        <ErrorAlert message={error} onRetry={load} />
      </PageContainer>
    );
  }

  const stemTab = (
    <Stack spacing={2}>
      <Paper sx={{ p: 1.5 }} component="section" aria-label="Stem prompt">
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

      <Paper sx={{ p: 1.5 }} component="section" aria-label="Knowledge base pin">
        <Typography variant="subtitle2" sx={{ mb: 1 }}>Knowledge base pin</Typography>
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
    </Stack>
  );

  const submissionsTab = (
    <FilteredDataGrid
      embedded
      searchPlaceholder="Search student, excerpt, status…"
      rows={submissionRows}
      columns={subColumns}
      loading={false}
      countLabel={`${submissionRows.length} of ${hub?.counts?.submissions ?? 0} submissions`}
      searchValue={subSearch}
      onSearchChange={setSubSearch}
      filterDefs={subFilterDefs}
      filterValues={subFilters}
      onFilterChange={(key, value) => setSubFilters((prev) => ({ ...prev, [key]: value }))}
      onClearFilters={() => {
        setSubSearch('');
        setSubFilters({ status: '', run_status: '', released: '', group_by: '' });
      }}
      emptyMessage="No submissions yet"
      emptySubtext="Use the Ingest tab to paste or upload, or clear filters."
      getRowId={(r) => r.id}
      height={480}
      onRowClick={(params) => openSubmission(params.row)}
      initialState={{
        sorting: { sortModel: [{ field: 'created_at', sort: 'desc' }] },
      }}
    />
  );

  const runsTab = (
    <FilteredDataGrid
      embedded
      searchPlaceholder="Search runs…"
      rows={runRows}
      columns={runColumns}
      loading={false}
      countLabel={`${runRows.length} of ${hub?.counts?.runs ?? 0} runs`}
      searchValue={runSearch}
      onSearchChange={setRunSearch}
      filterDefs={runFilterDefs}
      filterValues={runFilters}
      onFilterChange={(key, value) => setRunFilters((prev) => ({ ...prev, [key]: value }))}
      onClearFilters={() => {
        setRunSearch('');
        setRunFilters({ status: '', gate: '', released: '' });
      }}
      emptyMessage="No runs yet"
      emptySubtext="Analyze a submission from Submissions or Ingest."
      getRowId={(r) => r.id}
      height={480}
      onRowClick={(params) => navigate(`/teach/runs/${params.row.id}`)}
      initialState={{
        sorting: { sortModel: [{ field: 'created_at', sort: 'desc' }] },
      }}
    />
  );

  const ingestTab = (
    <Paper sx={{ p: 1.5 }} component="section" aria-label="Ingest submissions">
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
          <Button size="small" variant="contained" disabled={busy || !paste.trim()} onClick={() => onAnalyzePaste(true)}>
            Save & analyze
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
  );

  return (
    <PageContainer>
      <SkipToMain targetId="teach-stem-detail" />
      <Box component="main" id="teach-stem-detail" tabIndex={-1} aria-label="Stem master-detail">
        <PageHeader
          icon={AssignmentIcon}
          title={asg?.title || 'Stem'}
          subtitle={`${asg?.course_detail?.code || 'Course'} · operate one stem`}
          badge={asg?.mode ? { label: asg.mode, color: 'primary' } : null}
          actions={(
            <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap>
              <Button
                size="small"
                variant="outlined"
                startIcon={<ArrowBackIcon />}
                onClick={() => navigate('/teach/stems')}
              >
                Stems
              </Button>
              <Button size="small" variant="outlined" onClick={() => setPackOpen(true)}>
                Pack detail
              </Button>
              <Button
                size="small"
                variant="outlined"
                onClick={() => {
                  const first = (hub?.submissions || [])[0];
                  setPreviewSubId(first?.id ? String(first.id) : '');
                  setPreviewOpen(true);
                }}
              >
                Preview as student
              </Button>
              {isDraft && (
                <Button size="small" variant="contained" disabled={busy} onClick={onPublishDraft}>
                  Publish draft
                </Button>
              )}
            </Stack>
          )}
        />
        {error && <ErrorAlert message={error} onRetry={load} />}
        {msg && <Alert severity="success" sx={{ mb: 1.5 }} role="status">{msg}</Alert>}

        <Stack direction="row" spacing={1} sx={{ mb: 1.5, flexWrap: 'wrap' }} aria-label="Stem context">
          <Chip size="small" label={asg?.status} variant="outlined" color={isDraft ? 'warning' : 'default'} />
          <Chip size="small" label={`${asg?.profile_pack_id}@v${asg?.profile_version}`} />
          <Chip size="small" label={`${hub?.counts?.submissions ?? 0} submissions`} />
          <Chip size="small" label={`${hub?.counts?.runs ?? 0} runs`} />
          {(hub?.counts?.open_reviews > 0) && (
            <Chip size="small" color="warning" label={`${hub.counts.open_reviews} open reviews`} />
          )}
        </Stack>

        <Tabs
          value={tabIndex}
          onChange={handleTabChange}
          sx={{ mb: 2, borderBottom: 1, borderColor: 'divider', minHeight: 36 }}
          aria-label="Stem detail tabs"
        >
          {TAB_KEYS.map((label) => (
            <Tab key={label} label={label} sx={{ minHeight: 36, py: 0.5, textTransform: 'none' }} />
          ))}
        </Tabs>

        {tabIndex === 0 && stemTab}
        {tabIndex === 1 && submissionsTab}
        {tabIndex === 2 && runsTab}
        {tabIndex === 3 && ingestTab}
      </Box>

      <PackDetailDrawer
        open={packOpen}
        onClose={() => setPackOpen(false)}
        packId={asg?.profile_pack_id}
        version={asg?.profile_version || 1}
      />

      <Drawer
        anchor="right"
        open={previewOpen}
        onClose={() => setPreviewOpen(false)}
        PaperProps={{ sx: { width: { xs: '100%', sm: 480, md: 560 } } }}
      >
        <Box sx={{ p: 2 }} role="dialog" aria-label="Preview as student">
          <Typography variant="h6" sx={{ mb: 1.5 }}>Preview as student</Typography>
          <FormControl size="small" fullWidth sx={{ mb: 1.5 }}>
            <InputLabel id="preview-sub-label">Submission</InputLabel>
            <Select
              labelId="preview-sub-label"
              label="Submission"
              value={previewSubId}
              onChange={(e) => setPreviewSubId(e.target.value)}
            >
              <MenuItem value="">None (empty draft)</MenuItem>
              {(hub?.submissions || []).map((s) => (
                <MenuItem key={s.id} value={String(s.id)}>
                  {(s.created_at ? new Date(s.created_at).toLocaleString() : s.id)}
                  {s.word_count != null ? ` · ${s.word_count} words` : ''}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          {(() => {
            const selected = (hub?.submissions || []).find((s) => String(s.id) === String(previewSubId));
            return (
              <AssignmentDesk
                assignmentId={assignmentId}
                previewMode
                hideActions
                lockedText={selected?.text ?? ''}
                previewSubmissionId={previewSubId || null}
              />
            );
          })()}
        </Box>
      </Drawer>
    </PageContainer>
  );
}
