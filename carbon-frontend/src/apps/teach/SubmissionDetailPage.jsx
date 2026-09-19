// Submission master-detail under a stem context (ADR-0042 cascade).
// Tabs: Text | Runs. Analyze / open workbench from here.

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Alert, Box, Button, Chip, Paper, Stack, Tab, Tabs, Typography,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import ArticleIcon from '@mui/icons-material/Article';
import FilteredDataGrid from '../../components/FilteredDataGrid';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../components/Page/ErrorAlert';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import { analyzeSubmission, fetchAssignment } from '../../api/gradevance';
import SkipToMain from '../gradevance/SkipToMain';
import { getTeachStemContext, setTeachStemContext } from './teachContext';

const TAB_STORAGE = 'teach.submissionDetail.tab';
const TAB_KEYS = ['Text', 'Runs'];

export default function SubmissionDetailPage() {
  const { assignmentId, submissionId } = useParams();
  const { token } = useAuth();
  const navigate = useNavigate();

  const [hub, setHub] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const [tabIndex, setTabIndex] = useState(() => {
    const n = parseInt(localStorage.getItem(TAB_STORAGE) || '0', 10);
    return Number.isFinite(n) && n < TAB_KEYS.length ? n : 0;
  });

  const submission = useMemo(
    () => (hub?.submissions || []).find((s) => String(s.id) === String(submissionId)),
    [hub, submissionId],
  );

  const runs = useMemo(
    () => (hub?.runs || []).filter((r) => String(r.submission) === String(submissionId)),
    [hub, submissionId],
  );

  const studentLabel = submission?.student_username
    || submission?.external_student_key
    || (submission?.student_user != null ? `user#${submission.student_user}` : 'Submission');

  useDocumentTitle(studentLabel ? `Teach · ${studentLabel}` : 'Teach · Submission');

  const load = useCallback(() => {
    if (!assignmentId) return;
    setLoading(true);
    setError(null);
    fetchAssignment(token, assignmentId)
      .then((data) => {
        setHub(data);
        const asg = data?.assignment;
        setTeachStemContext({
          assignmentId: asg?.id || assignmentId,
          title: asg?.title,
          courseCode: asg?.course_detail?.code || getTeachStemContext()?.courseCode || '',
          mode: asg?.mode,
          status: asg?.status,
        });
      })
      .catch((e) => setError(e?.message || 'Failed to load submission'))
      .finally(() => setLoading(false));
  }, [token, assignmentId]);

  useEffect(() => { load(); }, [load]);

  const handleTabChange = (_, v) => {
    setTabIndex(v);
    localStorage.setItem(TAB_STORAGE, String(v));
  };

  const onAnalyze = async () => {
    setBusy(true);
    setError(null);
    try {
      const run = await analyzeSubmission(token, submissionId);
      setMsg('Analysis started');
      navigate(`/teach/runs/${run.id}`);
    } catch (e) {
      setError(e?.message || 'Analyze failed');
      setBusy(false);
    }
  };

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
      field: 'created_at',
      headerName: 'Created',
      width: 160,
      valueGetter: (v) => (v ? new Date(v).toLocaleString() : '—'),
    },
    {
      field: 'actions',
      headerName: '',
      width: 110,
      sortable: false,
      renderCell: (p) => (
        <Button size="small" onClick={() => navigate(`/teach/runs/${p.row.id}`)}>
          Workbench
        </Button>
      ),
    },
  ], [navigate]);

  if (loading) {
    return (
      <PageContainer>
        <PageHeader icon={ArticleIcon} title="Submission" />
        <LoadingSkeleton variant="table" />
      </PageContainer>
    );
  }

  if (error && !hub) {
    return (
      <PageContainer>
        <PageHeader icon={ArticleIcon} title="Submission" />
        <ErrorAlert message={error} onRetry={load} />
      </PageContainer>
    );
  }

  if (!submission) {
    return (
      <PageContainer>
        <PageHeader icon={ArticleIcon} title="Submission" />
        <ErrorAlert
          message="Submission not found on this stem."
          onRetry={() => navigate(`/teach/stems/${assignmentId}?tab=submissions`)}
        />
      </PageContainer>
    );
  }

  const ctx = getTeachStemContext();

  return (
    <PageContainer>
      <SkipToMain targetId="teach-submission-detail" />
      <Box component="main" id="teach-submission-detail" tabIndex={-1} aria-label="Submission master-detail">
        <PageHeader
          icon={ArticleIcon}
          title={studentLabel}
          subtitle={`${ctx?.title || hub?.assignment?.title || 'Stem'} · ${submission.word_count ?? 0} words`}
          actions={(
            <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap>
              <Button
                size="small"
                variant="outlined"
                startIcon={<ArrowBackIcon />}
                onClick={() => navigate(`/teach/stems/${assignmentId}?tab=submissions`)}
              >
                Stem
              </Button>
              <Button size="small" variant="contained" disabled={busy} onClick={onAnalyze}>
                Analyze
              </Button>
              {runs[0] && (
                <Button size="small" variant="outlined" onClick={() => navigate(`/teach/runs/${runs[0].id}`)}>
                  Latest run
                </Button>
              )}
            </Stack>
          )}
        />
        {error && <ErrorAlert message={error} onRetry={load} />}
        {msg && <Alert severity="success" sx={{ mb: 1.5 }} role="status">{msg}</Alert>}

        <Stack direction="row" spacing={1} sx={{ mb: 1.5, flexWrap: 'wrap' }}>
          <Chip size="small" label={submission.status} />
          <Chip size="small" variant="outlined" label={`${runs.length} runs`} />
          {submission.created_at && (
            <Chip
              size="small"
              variant="outlined"
              label={new Date(submission.created_at).toLocaleString()}
            />
          )}
        </Stack>

        <Tabs
          value={tabIndex}
          onChange={handleTabChange}
          sx={{ mb: 2, borderBottom: 1, borderColor: 'divider', minHeight: 36 }}
          aria-label="Submission detail tabs"
        >
          {TAB_KEYS.map((label) => (
            <Tab key={label} label={label} sx={{ minHeight: 36, py: 0.5, textTransform: 'none' }} />
          ))}
        </Tabs>

        {tabIndex === 0 && (
          <Paper sx={{ p: 1.5 }} component="section" aria-label="Submission text">
            <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
              {submission.text || '—'}
            </Typography>
          </Paper>
        )}

        {tabIndex === 1 && (
          <FilteredDataGrid
            embedded
            searchPlaceholder="Search runs…"
            rows={runs}
            columns={runColumns}
            loading={false}
            countLabel={`${runs.length} runs for this submission`}
            searchValue=""
            onSearchChange={() => {}}
            filterDefs={[]}
            filterValues={{}}
            onFilterChange={() => {}}
            onClearFilters={() => {}}
            emptyMessage="No runs yet — Analyze to create one."
            getRowId={(r) => r.id}
            height={400}
            onRowClick={(params) => navigate(`/teach/runs/${params.row.id}`)}
          />
        )}
      </Box>
    </PageContainer>
  );
}
