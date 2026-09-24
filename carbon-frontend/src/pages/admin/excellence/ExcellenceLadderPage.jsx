import React, { useEffect, useMemo, useState } from 'react';
import { Link as RouterLink, useLocation, useNavigate, useParams } from 'react-router-dom';
import {
  Alert, Box, Button, Chip, CircularProgress, Link, MenuItem, Stack, Tab, Table, TableBody,
  TableCell, TableHead, TableRow, Tabs, TextField, ToggleButton, ToggleButtonGroup, Tooltip,
  Typography,
} from '@mui/material';
import { useAuth } from '../../../auth/AuthContext';
import { apiFetch, apiFetchStream } from '../../../api/api';
import PageContainer from '../../../components/layout/PageContainer';
import useDocumentTitle from '../../../hooks/useDocumentTitle';
import AssuranceRulesPanel from './AssuranceRulesPanel';
import { DIMENSION_SHORT, levelColor } from './excellenceUi';

function useLadder(token) {
  const [snapshot, setSnapshot] = useState(null);
  const [error, setError] = useState(null);
  const [stream, setStream] = useState('connecting');

  useEffect(() => {
    if (!token) return undefined;
    let cancelled = false;
    apiFetch('excellence/ladder/', { token })
      .then((data) => { if (!cancelled) setSnapshot(data); })
      .catch((err) => { if (!cancelled) setError(err?.message || 'Excellence ladder failed'); });
    return () => { cancelled = true; };
  }, [token]);

  useEffect(() => {
    if (!token) return undefined;
    const controller = new AbortController();
    let stopped = false;
    async function listen() {
      try {
        const response = await apiFetchStream('excellence/stream/', { token, signal: controller.signal });
        if (!response.ok || !response.body) {
          setStream('disconnected');
          return;
        }
        setStream('live');
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        while (!stopped) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const chunks = buffer.split('\n\n');
          buffer = chunks.pop() || '';
          for (const chunk of chunks) {
            const line = chunk.split('\n').find((row) => row.startsWith('data: '));
            if (!line) continue;
            try {
              setSnapshot(JSON.parse(line.slice(6)));
              setStream('live');
            } catch {
              setStream('stale');
            }
          }
        }
      } catch (err) {
        if (!stopped && err?.name !== 'AbortError') setStream('disconnected');
      }
    }
    listen();
    return () => {
      stopped = true;
      controller.abort();
    };
  }, [token]);

  return { snapshot, setSnapshot, error, stream };
}

function LevelHistogram({ subjects, levelNames }) {
  const counts = levelNames.map((_, level) => subjects.filter((s) => s.level === level).length);
  return (
    <Stack direction="row" spacing={0.5} flexWrap="wrap" sx={{ mb: 1 }}>
      {levelNames.map((name, level) => (
        <Chip
          key={name}
          size="small"
          variant={counts[level] ? 'filled' : 'outlined'}
          color={counts[level] ? levelColor(level) : 'default'}
          label={`L${level} ${name} · ${counts[level]}`}
        />
      ))}
    </Stack>
  );
}

const SAFE_COLLECTORS = [
  { id: 'repo', label: 'Repo probes' },
  { id: 'observe', label: 'Observe (CI / runbooks / fault rules)' },
  { id: 'pulse_gauge', label: 'Pulse gauge' },
  { id: 'antipatterns', label: 'Antipatterns' },
];

export default function ExcellenceLadderPage() {
  const { token } = useAuth();
  const { tier: tierParam, track: trackParam } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const rulesView = location.pathname.endsWith('/excellence/rules') || tierParam === 'rules';
  useDocumentTitle(rulesView ? 'Excellence · Rules' : 'Excellence');
  const { snapshot, setSnapshot, error, stream } = useLadder(token);
  const [collector, setCollector] = useState('repo');
  const [running, setRunning] = useState(false);
  const [runMsg, setRunMsg] = useState(null);
  const [runs, setRuns] = useState([]);

  useEffect(() => {
    if (!token || rulesView) return undefined;
    let cancelled = false;
    apiFetch('excellence/runs/', { token })
      .then((data) => { if (!cancelled) setRuns(data.runs || []); })
      .catch(() => { /* non-fatal */ });
    return () => { cancelled = true; };
  }, [token, rulesView, runMsg]);

  const tiers = snapshot?.tiers || [];
  const tierId = rulesView ? (tiers[0]?.id || 'platform') : (tierParam || tiers[0]?.id || 'platform');
  const tier = tiers.find((t) => t.id === tierId);
  const track = rulesView ? '' : (trackParam || '');

  const subjects = useMemo(() => {
    const all = (snapshot?.subjects || []).filter((s) => s.tier === tierId);
    return track ? all.filter((s) => s.track === track) : all;
  }, [snapshot, tierId, track]);

  const levelNames = tier?.level_names || [];

  async function measure() {
    if (!token || running) return;
    setRunning(true);
    setRunMsg(null);
    try {
      const body = await apiFetch('excellence/runs/', {
        token,
        method: 'POST',
        timeoutMs: 120000,
        body: {
          collectors: [collector],
          tier: rulesView ? undefined : tierId,
          write_snapshot: true,
        },
      });
      setRunMsg(`Run #${body.id}: ${body.status} · ${body.event_count} events`);
      if (body.ladder) setSnapshot(body.ladder);
      else {
        const ladder = await apiFetch('excellence/ladder/', { token });
        setSnapshot(ladder);
      }
    } catch (err) {
      setRunMsg(err?.message || 'Measure failed');
    } finally {
      setRunning(false);
    }
  }

  return (
    <PageContainer>
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }} flexWrap="wrap">
        <Typography variant="h6">Excellence</Typography>
        <ToggleButtonGroup
          size="small"
          exclusive
          value={rulesView ? 'rules' : 'ladder'}
          onChange={(_, value) => {
            if (!value) return;
            navigate(value === 'rules' ? '/admin/excellence/rules' : '/admin/excellence');
          }}
        >
          <ToggleButton value="ladder">Ladder</ToggleButton>
          <ToggleButton value="rules">Rules</ToggleButton>
        </ToggleButtonGroup>
        {!rulesView && (
          <>
            <Chip size="small" label={stream} color={stream === 'live' ? 'success' : 'default'} />
            <Chip size="small" variant="outlined" label={snapshot?.head ? snapshot.head.slice(0, 7) : '…'} />
            {snapshot?.problems?.length > 0 && (
              <Chip size="small" color="error" label={`${snapshot.problems.length} catalogue problems`} />
            )}
          </>
        )}
      </Stack>

      {rulesView ? (
        <AssuranceRulesPanel embedded />
      ) : (
        <>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            Levels are earned from evidence on the current commit. A subject&apos;s level is its weakest dimension.
          </Typography>
          <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }} flexWrap="wrap">
            <TextField
              select
              size="small"
              label="Collector"
              value={collector}
              onChange={(e) => setCollector(e.target.value)}
              sx={{ minWidth: 180 }}
            >
              {SAFE_COLLECTORS.map((c) => <MenuItem key={c.id} value={c.id}>{c.label}</MenuItem>)}
            </TextField>
            <Button variant="contained" size="small" onClick={measure} disabled={running || !token}>
              {running ? 'Measuring…' : 'Measure'}
            </Button>
            {runMsg && <Typography variant="caption" color="text.secondary">{runMsg}</Typography>}
          </Stack>
          {error && <Alert severity="error" sx={{ mb: 1 }}>{error}</Alert>}
          {!snapshot && !error && <CircularProgress size={28} />}
          {snapshot && (
            <>
              <Tabs
                value={tierId}
                onChange={(_, value) => navigate(`/admin/excellence/${value}`)}
                variant="scrollable"
                sx={{ mb: 1 }}
              >
                {tiers.map((t) => <Tab key={t.id} value={t.id} label={t.title} />)}
              </Tabs>
              {tier?.tracks?.length > 0 && (
                <ToggleButtonGroup
                  size="small"
                  exclusive
                  value={track}
                  onChange={(_, value) => navigate(value ? `/admin/excellence/${tierId}/${value}` : `/admin/excellence/${tierId}`)}
                  sx={{ mb: 1 }}
                >
                  <ToggleButton value="">All</ToggleButton>
                  {tier.tracks.map((tr) => <ToggleButton key={tr.id} value={tr.id}>{tr.title}</ToggleButton>)}
                </ToggleButtonGroup>
              )}
              <LevelHistogram subjects={subjects} levelNames={levelNames} />
              <Box sx={{ overflow: 'auto' }}>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Subject</TableCell>
                      <TableCell>Track</TableCell>
                      <TableCell>Level</TableCell>
                      <TableCell>Dimensions</TableCell>
                      <TableCell>Next</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {subjects.map((s) => (
                      <TableRow key={s.subject_id} hover>
                        <TableCell>
                          <Link component={RouterLink} to={`/admin/excellence/subjects/${encodeURIComponent(s.subject_id)}`}>
                            {s.title}
                          </Link>
                          <Typography variant="caption" color="text.secondary" display="block">{s.subject_id}</Typography>
                        </TableCell>
                        <TableCell>{s.track || '—'}</TableCell>
                        <TableCell>
                          <Chip size="small" color={levelColor(s.level)} label={`L${s.level} ${s.level_name}`} />
                        </TableCell>
                        <TableCell>
                          <Stack direction="row" spacing={0.5} flexWrap="wrap">
                            {Object.entries(s.dimensions).map(([dim, lv]) => (
                              <Tooltip key={dim} title={dim}>
                                <Chip size="small" variant="outlined" label={`${DIMENSION_SHORT[dim] || dim} ${lv}`} />
                              </Tooltip>
                            ))}
                          </Stack>
                        </TableCell>
                        <TableCell>{s.next.length ? s.next.join(', ') : '—'}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Box>
              {subjects.length === 0 && (
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                  No subjects declared for this tier yet. Add them to its ladder.yaml.
                </Typography>
              )}
              {runs.length > 0 && (
                <>
                  <Typography variant="subtitle2" sx={{ mt: 2, mb: 0.5 }}>Recent runs</Typography>
                  <Box sx={{ overflow: 'auto' }}>
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>#</TableCell>
                          <TableCell>When</TableCell>
                          <TableCell>Collectors</TableCell>
                          <TableCell>Status</TableCell>
                          <TableCell>Events</TableCell>
                          <TableCell>By</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {runs.slice(0, 15).map((r) => (
                          <TableRow key={r.id}>
                            <TableCell>{r.id}</TableCell>
                            <TableCell>{r.started_at ? new Date(r.started_at).toLocaleString() : '—'}</TableCell>
                            <TableCell>{(r.collectors || []).join(', ')}</TableCell>
                            <TableCell>
                              <Chip
                                size="small"
                                color={r.status === 'succeeded' ? 'success' : r.status === 'failed' ? 'error' : 'default'}
                                label={r.status}
                              />
                            </TableCell>
                            <TableCell>{r.event_count}</TableCell>
                            <TableCell>{r.requested_by}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </Box>
                </>
              )}
            </>
          )}
        </>
      )}
    </PageContainer>
  );
}
