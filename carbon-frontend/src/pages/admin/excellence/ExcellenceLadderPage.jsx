import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { Alert, Box, Button, Chip, CircularProgress, Stack, Typography } from '@mui/material';
import StairsIcon from '@mui/icons-material/Stairs';
import { useAuth } from '../../../auth/AuthContext';
import { apiFetch } from '../../../api/api';
import PageContainer from '../../../components/layout/PageContainer';
import PageHeader from '../../../components/Page/PageHeader';
import { SearchSelect } from '../../../components/Form';
import FilteredDataGrid from '../../../components/FilteredDataGrid';
import { useNotification } from '../../../components/NotificationProvider';
import useDocumentTitle from '../../../hooks/useDocumentTitle';
import AssuranceRulesPanel from './AssuranceRulesPanel';
import { levelColor, stateColor } from './excellenceUi';

const COLLECTORS = [
  { value: 'repo', label: 'Repo probes (owner, paths, tests)' },
  { value: 'observe', label: 'Observe (CI, runbooks, fault rules)' },
  { value: 'pulse_gauge', label: 'Pulse gauge' },
  { value: 'antipatterns', label: 'Antipatterns' },
];

const PULSE_APP = 'pulse';

const TRACK_REACH = {
  chat: 'Climb to intelligence L2 (grounded reads), then L3 (multi-turn state).',
  agent: 'Climb to intelligence L4 (an ESS write that waits for consent).',
  memory: 'Facts and ConversationState. No track check of its own yet.',
  packs: 'Pack contract: versioned, self-contained, core stays domain-free.',
  ops: 'Five consecutive live PASS nights, and a gauge series younger than 14 days.',
};

function useLadder(token) {
  const [snapshot, setSnapshot] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(() => {
    if (!token) return Promise.resolve();
    setLoading(true);
    return apiFetch('excellence/ladder/', { token })
      .then((data) => { setSnapshot(data); setError(null); })
      .catch((err) => setError(err?.message || 'Excellence ladder failed'))
      .finally(() => setLoading(false));
  }, [token]);

  useEffect(() => { reload(); }, [reload]);
  return { snapshot, setSnapshot, error, loading, reload };
}

function appsFor(contextId, subjects) {
  if (contextId === PULSE_APP) return [{ value: PULSE_APP, label: 'Pulse' }];
  return (subjects || [])
    .filter((s) => s.tier === contextId)
    .map((s) => ({ value: s.subject_id, label: s.title }));
}

function trackLevel(subjects) {
  if (!subjects.length) return null;
  return subjects.reduce((min, s) => Math.min(min, s.level), subjects[0].level);
}

function pulseLadderRows(subjects) {
  const rows = [];
  const seen = new Set();
  subjects.forEach((subject) => {
    (subject.checks || []).forEach((check) => {
      if (!String(check.check_id).startsWith('PULSE-')) return;
      const key = `${subject.track || 'engine'}:${check.check_id}`;
      if (seen.has(key)) return;
      seen.add(key);
      rows.push({
        id: key,
        track: subject.track || 'engine',
        title: check.title,
        rank: `L${check.rank}`,
        state: check.state,
        solution: check.solution || '',
      });
    });
  });
  return rows;
}

export default function ExcellenceLadderPage() {
  const { token } = useAuth();
  const { notify } = useNotification();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const { tier: pathTier } = useParams();
  const { pathname } = useLocation();
  const rulesOnly = pathname.endsWith('/excellence/rules');
  const contextId = params.get('context') || (pathTier && pathTier !== 'rules' && pathTier !== 'subjects' ? pathTier : '');
  const appId = params.get('app') || (contextId === PULSE_APP ? PULSE_APP : '');
  useDocumentTitle('Excellence');

  const { snapshot, setSnapshot, error, loading, reload } = useLadder(token);
  const [subject, setSubject] = useState(null);
  const [subjectError, setSubjectError] = useState(null);
  const [subjectLoading, setSubjectLoading] = useState(false);
  const [collector, setCollector] = useState(contextId === PULSE_APP ? 'pulse_gauge' : 'repo');
  const [running, setRunning] = useState(false);

  const tiers = snapshot?.tiers || [];
  const context = tiers.find((t) => t.id === contextId) || null;
  const apps = useMemo(
    () => appsFor(contextId, snapshot?.subjects),
    [snapshot, contextId],
  );
  const pulseSubjects = useMemo(
    () => (snapshot?.subjects || []).filter((s) => s.tier === PULSE_APP),
    [snapshot],
  );

  useEffect(() => {
    if (!token || !appId || appId === PULSE_APP) {
      setSubject(null);
      return undefined;
    }
    let cancelled = false;
    setSubjectLoading(true);
    setSubjectError(null);
    apiFetch(`excellence/subjects/${encodeURIComponent(appId)}/`, { token })
      .then((data) => { if (!cancelled) setSubject(data); })
      .catch((err) => { if (!cancelled) setSubjectError(err?.message || 'App failed to load'); })
      .finally(() => { if (!cancelled) setSubjectLoading(false); });
    return () => { cancelled = true; };
  }, [token, appId]);

  function setContext(id) {
    const next = new URLSearchParams();
    if (id) next.set('context', id);
    if (id === PULSE_APP) next.set('app', PULSE_APP);
    setCollector(id === PULSE_APP ? 'pulse_gauge' : 'repo');
    setParams(next, { replace: true });
  }

  function setApp(id) {
    const next = new URLSearchParams(params);
    if (id) next.set('app', id);
    else next.delete('app');
    setParams(next, { replace: true });
  }

  async function measure() {
    if (!token || running || !contextId) return;
    setRunning(true);
    try {
      const body = await apiFetch('excellence/runs/', {
        token,
        method: 'POST',
        timeoutMs: 120000,
        body: { collectors: [collector], tier: contextId, write_snapshot: true },
      });
      if (body.ladder) setSnapshot(body.ladder);
      else await reload();
      if (appId && appId !== PULSE_APP) {
        const detail = await apiFetch(`excellence/subjects/${encodeURIComponent(appId)}/`, { token });
        setSubject(detail);
      }
      const n = body.event_count ?? 0;
      notify({
        message: n
          ? `Measured ${collector}: ${n} events`
          : `Measured ${collector}: no checks in this context use that collector`,
        type: n ? 'success' : 'warning',
      });
    } catch (err) {
      notify({ message: err?.message || 'Measure failed', type: 'error' });
    } finally {
      setRunning(false);
    }
  }

  if (rulesOnly) {
    return (
      <PageContainer>
        <PageHeader
          icon={StairsIcon}
          title="Release rules"
          subtitle="Nibras release rules. This is not an app dashboard."
          actions={<Button size="small" component={Link} to="/admin/excellence">Back to Excellence</Button>}
        />
        <AssuranceRulesPanel embedded />
      </PageContainer>
    );
  }

  const pulseTracks = [
    ...(context?.tracks || []),
    { id: 'engine', title: 'Engine core' },
  ];
  const pulseRows = pulseLadderRows(pulseSubjects);
  const pulseLevel = trackLevel(pulseSubjects);

  const checkRows = (subject?.checks || []).map((c) => ({
    id: c.check_id,
    rank: `L${c.rank}`,
    title: c.title,
    dimension: c.dimension,
    state: c.state,
    evidence: c.evidence_class,
    solution: c.solution || '',
  }));

  return (
    <PageContainer>
      <PageHeader
        icon={StairsIcon}
        title="Excellence"
        subtitle={appId === PULSE_APP ? 'Pulse' : (context ? context.title : 'Pick a context, then an app')}
        description={appId === PULSE_APP
          ? 'Pulse is one app. Chat, Agent, Memory, Packs, and Ops are the ladders inside it.'
          : undefined}
        badge={snapshot?.head ? { label: snapshot.head.slice(0, 7), color: 'default' } : null}
      />

      {loading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
          <CircularProgress size={24} />
        </Box>
      )}
      {error && !loading && (
        <Alert severity="error" action={<Button color="inherit" size="small" onClick={reload}>Retry</Button>}>
          {error}
        </Alert>
      )}

      {!loading && !error && snapshot && (
        <Stack spacing={2}>
          <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5}>
            <Box sx={{ flex: 1, minWidth: 220 }}>
              <SearchSelect
                label="Context"
                options={tiers.map((t) => ({ value: t.id, label: t.id === PULSE_APP ? 'Pulse' : t.title }))}
                value={contextId}
                onChange={(opt) => setContext(opt?.value || '')}
                placeholder="Data Trust, Nibras, Carbon, Pulse, Platform"
              />
            </Box>
            <Box sx={{ flex: 1, minWidth: 220 }}>
              <SearchSelect
                label="App"
                options={apps}
                value={appId}
                onChange={(opt) => setApp(opt?.value || '')}
                disabled={!contextId}
                placeholder={contextId ? 'Pick an app' : 'Pick a context first'}
                noOptionsText="No apps declared for this context"
              />
            </Box>
            <Box sx={{ flex: 1, minWidth: 220 }}>
              <SearchSelect
                label="Measure"
                options={COLLECTORS}
                value={collector}
                onChange={(opt) => setCollector(opt?.value || 'repo')}
                clearable={false}
                disabled={!contextId}
              />
            </Box>
            <Button
              variant="contained"
              size="small"
              sx={{ alignSelf: 'center' }}
              disabled={!contextId || running}
              onClick={measure}
            >
              {running ? 'Measuring…' : 'Measure'}
            </Button>
          </Stack>

          {!contextId && (
            <Alert severity="info">
              Contexts are the product lines: Platform, Data Trust, Nibras, Carbon (AASTMT), Pulse.
              Pulse is one app.
            </Alert>
          )}

          {contextId && !appId && contextId !== PULSE_APP && (
            <FilteredDataGrid
              embedded
              title={`${context?.title || contextId} apps`}
              subtitle="Select a row to open that app"
              rows={(snapshot.subjects || []).filter((s) => s.tier === contextId)}
              getRowId={(row) => row.subject_id}
              onRowClick={(rowParams) => setApp(rowParams.row.subject_id)}
              columns={[
                { field: 'title', headerName: 'App', flex: 1.4, minWidth: 180 },
                { field: 'kind', headerName: 'Kind', width: 110 },
                {
                  field: 'level',
                  headerName: 'Level',
                  width: 140,
                  renderCell: (p) => (
                    <Chip size="small" color={levelColor(p.row.level)} label={`L${p.row.level} ${p.row.level_name}`} />
                  ),
                },
                {
                  field: 'next',
                  headerName: 'Next',
                  flex: 1,
                  minWidth: 160,
                  valueGetter: (_v, row) => (row.next || []).join(', '),
                },
              ]}
              emptyMessage="No apps declared"
              emptySubtext="Add subjects to this context's ladder.yaml"
            />
          )}

          {appId === PULSE_APP && (
            <Stack spacing={2}>
              <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                <Chip
                  size="small"
                  color={levelColor(pulseLevel ?? 0)}
                  label={pulseLevel == null ? 'No ladder' : `Pulse L${pulseLevel}`}
                />
                {pulseTracks.filter((tr) => tr.id !== 'engine' || pulseSubjects.some((s) => !s.track)).map((tr) => {
                  const members = pulseSubjects.filter((s) => (s.track || 'engine') === tr.id);
                  const lv = trackLevel(members);
                  return (
                    <Chip
                      key={tr.id}
                      size="small"
                      variant="outlined"
                      color={levelColor(lv ?? 0)}
                      label={`${tr.title} ${lv == null ? '—' : `L${lv}`}`}
                    />
                  );
                })}
              </Stack>
              {pulseTracks.filter((tr) => TRACK_REACH[tr.id]).map((tr) => (
                <Typography key={tr.id} variant="body2" color="text.secondary">
                  {tr.title}. {TRACK_REACH[tr.id]}
                </Typography>
              ))}
              <FilteredDataGrid
                embedded
                title="Pulse ladder"
                subtitle="These are the rungs Pulse still has to clear. Chat, Agent, Memory, Packs, and Ops are tracks of this one app."
                rows={pulseRows}
                getRowId={(row) => row.id}
                columns={[
                  { field: 'track', headerName: 'Track', width: 110 },
                  { field: 'rank', headerName: 'Rank', width: 70 },
                  { field: 'title', headerName: 'Rung', flex: 1.4, minWidth: 240 },
                  {
                    field: 'state',
                    headerName: 'State',
                    width: 130,
                    renderCell: (p) => <Chip size="small" color={stateColor(p.value)} label={p.value} />,
                  },
                  { field: 'solution', headerName: 'How to earn it', flex: 1.4, minWidth: 220 },
                ]}
                emptyMessage="No Pulse rungs declared"
                emptySubtext="The Pulse ladder has no PULSE checks yet"
              />
            </Stack>
          )}

          {appId && appId !== PULSE_APP && subjectLoading && (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
              <CircularProgress size={24} />
            </Box>
          )}
          {subjectError && <Alert severity="error">{subjectError}</Alert>}

          {subject && !subjectLoading && appId !== PULSE_APP && (
            <Stack spacing={2}>
              <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
                <Typography variant="subtitle1">{subject.title}</Typography>
                <Chip size="small" color={levelColor(subject.level)} label={`L${subject.level} ${subject.level_name}`} />
              </Stack>
              <FilteredDataGrid
                embedded
                title="Checks"
                rows={checkRows}
                getRowId={(row) => row.id}
                highlightRow={(row) => (subject.next || []).includes(row.id)}
                columns={[
                  { field: 'rank', headerName: 'Rank', width: 70 },
                  { field: 'title', headerName: 'Check', flex: 1.2, minWidth: 200 },
                  {
                    field: 'state',
                    headerName: 'State',
                    width: 130,
                    renderCell: (p) => <Chip size="small" color={stateColor(p.value)} label={p.value} />,
                  },
                  { field: 'solution', headerName: 'How to earn it', flex: 1.4, minWidth: 220 },
                ]}
                emptyMessage="No checks apply"
              />
              <Button size="small" onClick={() => navigate(`/admin/excellence/subjects/${encodeURIComponent(subject.subject_id)}`)}>
                Exemptions and evidence
              </Button>
            </Stack>
          )}
        </Stack>
      )}
    </PageContainer>
  );
}
