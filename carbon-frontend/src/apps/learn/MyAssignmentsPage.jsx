// My assignments — course-grouped list from me/assignments + me/courses (Learn Trust L2).

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Box, Chip, FormControl, InputLabel, MenuItem, Paper, Select, Stack, Typography,
} from '@mui/material';
import AssignmentIcon from '@mui/icons-material/Assignment';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../components/Page/ErrorAlert';
import EmptyState from '../../components/Page/EmptyState';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import { fetchMyAssignments, fetchMyCourses } from '../../api/gradevance';
import SkipToMain from '../../components/gradevance/SkipToMain';
import LearnReadingWidth from '../../components/gradevance/LearnReadingWidth';

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

function AssignmentRow({ a, onOpen }) {
  const myStatus = a.my_status || a.status || 'open';
  return (
    <Paper
      variant="outlined"
      role="listitem"
      sx={{ p: 1.5, cursor: 'pointer' }}
      onClick={() => onOpen(a.id)}
    >
      <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
        <Box sx={{ flex: 1, minWidth: 140 }}>
          <Typography variant="body2">{a.title || `Assignment ${a.id}`}</Typography>
          {a.due_at && (
            <Typography variant="caption" color="text.secondary">
              Due {new Date(a.due_at).toLocaleDateString()}
            </Typography>
          )}
        </Box>
        <Chip size="small" label={a.mode || 'formative'} variant="outlined" />
        <Chip size="small" label={myStatus} color={statusChipColor(myStatus)} />
      </Stack>
    </Paper>
  );
}

export default function MyAssignmentsPage() {
  useDocumentTitle('Learn · Assignments');
  const { token } = useAuth();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const courseFilter = searchParams.get('course') || '';

  const [rows, setRows] = useState([]);
  const [courses, setCourses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    const params = courseFilter ? { course: courseFilter } : {};
    Promise.all([
      fetchMyAssignments(token, params),
      fetchMyCourses(token).catch(() => ({ results: [] })),
    ])
      .then(([asgData, courseData]) => {
        setRows(asgData.results || asgData || []);
        setCourses(courseData.results || courseData || []);
      })
      .catch((err) => setError(err?.message || 'Failed to load assignments'))
      .finally(() => setLoading(false));
  }, [token, courseFilter]);

  useEffect(() => {
    load();
  }, [load]);

  const grouped = useMemo(() => {
    const map = new Map();
    for (const a of rows) {
      const key = a.course || a.course_id || '_none';
      const label = a.course_title || a.course_name
        || courses.find((c) => String(c.id) === String(key))?.name
        || 'No course';
      if (!map.has(String(key))) {
        map.set(String(key), { key: String(key), label, items: [] });
      }
      map.get(String(key)).items.push(a);
    }
    return [...map.values()].sort((a, b) => a.label.localeCompare(b.label));
  }, [rows, courses]);

  const onCourseChange = (value) => {
    const next = new URLSearchParams(searchParams);
    if (value) next.set('course', value);
    else next.delete('course');
    setSearchParams(next, { replace: true });
  };

  if (loading) {
    return (
      <PageContainer>
        <LearnReadingWidth>
          <PageHeader icon={AssignmentIcon} title="My assignments" subtitle="By course — open, draft, submit, released" />
          <LoadingSkeleton variant="console" />
        </LearnReadingWidth>
      </PageContainer>
    );
  }

  if (error) {
    return (
      <PageContainer>
        <LearnReadingWidth>
          <PageHeader icon={AssignmentIcon} title="My assignments" />
          <ErrorAlert message={error} onRetry={load} />
        </LearnReadingWidth>
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <SkipToMain targetId="learn-assignments" />
      <LearnReadingWidth>
      <Box component="main" id="learn-assignments" tabIndex={-1} aria-label="My assignments">
        <PageHeader
          icon={AssignmentIcon}
          title="My assignments"
          subtitle="Grouped by course — open, drafted, submitted, or released."
          actions={courses.length > 0 ? (
            <FormControl size="small" sx={{ minWidth: 180 }}>
              <InputLabel id="learn-course-filter">Course</InputLabel>
              <Select
                labelId="learn-course-filter"
                label="Course"
                value={courseFilter}
                onChange={(e) => onCourseChange(e.target.value)}
              >
                <MenuItem value="">All courses</MenuItem>
                {courses.map((c) => (
                  <MenuItem key={c.id} value={String(c.id)}>
                    {c.code} — {c.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          ) : null}
        />
        {rows.length === 0 ? (
          <EmptyState
            icon={<AssignmentIcon />}
            title="No assignments yet"
            description="When your instructor publishes one, or you join a course by entry code, it will appear here."
            actionLabel="Learn home"
            onAction={() => navigate('/learn')}
          />
        ) : (
          <Stack spacing={2} role="list" aria-label="Assignments by course">
            {grouped.map((group) => (
              <Box key={group.key} component="section" aria-label={group.label}>
                <Typography variant="subtitle2" sx={{ mb: 0.75 }} color="text.secondary">
                  {group.label}
                  <Typography component="span" variant="caption" sx={{ ml: 1 }}>
                    ({group.items.length})
                  </Typography>
                </Typography>
                <Stack spacing={1} role="list">
                  {group.items.map((a) => (
                    <AssignmentRow
                      key={a.id}
                      a={a}
                      onOpen={(id) => navigate(`/learn/assignments/${id}`)}
                    />
                  ))}
                </Stack>
              </Box>
            ))}
          </Stack>
        )}
      </Box>
      </LearnReadingWidth>
    </PageContainer>
  );
}
