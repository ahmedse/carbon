import React, { useCallback, useEffect, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { Alert, Button, Chip, Skeleton, Stack, Tab, Tabs, TextField, Typography } from '@mui/material';
import StairsIcon from '@mui/icons-material/Stairs';
import { useAuth } from '../../../auth/AuthContext';
import { apiFetch } from '../../../api/api';
import PageContainer from '../../../components/layout/PageContainer';
import PageHeader from '../../../components/Page/PageHeader';
import { SearchSelect } from '../../../components/Form';
import FilteredDataGrid from '../../../components/FilteredDataGrid';
import TabPanel from '../../../components/Layout/TabPanel';
import SystemDialog from '../../../components/SystemDialog';
import { useNotification } from '../../../components/NotificationProvider';
import useDocumentTitle from '../../../hooks/useDocumentTitle';
import AssuranceRulesPanel from './AssuranceRulesPanel';
import ExcellenceCellMap from './ExcellenceCellMap';
import EmptyState from '../../../components/Page/EmptyState';
import { aspectLabel, levelColor, levelName, stateColor } from './excellenceUi';

const COLLECTORS = [
  { value: 'repo', label: 'Repo probes' },
  { value: 'observe', label: 'Observe' },
  { value: 'pulse_gauge', label: 'Pulse gauge' },
  { value: 'antipatterns', label: 'Antipatterns' },
  { value: 'rbac', label: 'RBAC marker' },
  { value: 'budget', label: 'Budget ceiling' },
  { value: 'design_lint', label: 'Design lint' },
];

const LEVELS = [1, 2, 3, 4, 5, 6].map((n) => ({ value: String(n), label: levelName(n) }));

const SECTIONS = new Set(['rules', 'standard', 'runs', 'exemptions', 'initiatives', 'subjects']);

function useGet(token, url) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(Boolean(url));
  const reload = useCallback(() => {
    if (!token || !url) return Promise.resolve();
    setLoading(true);
    return apiFetch(url, { token })
      .then((body) => { setData(body); setError(null); })
      .catch((err) => setError(err?.message || 'Excellence failed'))
      .finally(() => setLoading(false));
  }, [token, url]);
  useEffect(() => { reload(); }, [reload]);
  return { data, setData, error, loading, reload };
}

function StateChip({ state }) {
  return <Chip size="small" color={stateColor(state)} label={state} />;
}

function LevelChip({ level, name }) {
  return <Chip size="small" color={levelColor(level)} label={name ? `L${level} ${name}` : `L${level}`} />;
}

export default function ExcellenceConsolePage() {
  const { token } = useAuth();
  const { notify } = useNotification();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const params = useParams();
  const section = pathname.split('/').filter(Boolean)[2] || '';
  const named = SECTIONS.has(section);
  const context = named ? '' : (params.context || '');
  const app = named ? '' : (params.app || '');
  useDocumentTitle('Excellence');

  const overview = useGet(token, (!named && !app) || section === 'initiatives' || Boolean(context && app) ? 'excellence/overview/' : null);
  const appData = useGet(token, app ? `excellence/apps/${encodeURIComponent(app)}/` : null);
  const standard = useGet(token, section === 'standard' ? 'excellence/standard/' : null);
  const runs = useGet(token, section === 'runs' ? 'excellence/runs/' : null);
  const exemptions = useGet(token, section === 'exemptions' ? 'excellence/exemptions/' : null);
  const initiatives = useGet(token, section === 'initiatives' ? 'excellence/initiatives/' : null);

  const [tab, setTab] = useState(0);
  const [track, setTrack] = useState('');
  const [cell, setCell] = useState(null);
  const [collector, setCollector] = useState('repo');
  const [running, setRunning] = useState(false);
  const [exemptOpen, setExemptOpen] = useState(false);
  const [exemptForm, setExemptForm] = useState({ check_id: '', subject_id: '', reason: '', until: '' });
  const [initOpen, setInitOpen] = useState(false);
  const [initForm, setInitForm] = useState({ title: '', tier: '', target_level: '3', deadline: '', app_ids: [] });

  const contexts = overview.data?.contexts || [];
  const current = contexts.find((c) => c.id === context) || null;
  const grid = appData.data;
  const loading = overview.loading || appData.loading || standard.loading || runs.loading || exemptions.loading || initiatives.loading;
  const error = overview.error || appData.error || standard.error || runs.error || exemptions.error || initiatives.error;

  async function measure(extra) {
    if (!token || running) return;
    const tier = extra?.tier || context || grid?.tier;
    if (!tier) return;
    setRunning(true);
    try {
      const body = await apiFetch('excellence/runs/', {
        token,
        method: 'POST',
        timeoutMs: 120000,
        body: { collectors: [extra?.collector || collector], tier, write_snapshot: true },
      });
      notify({
        message: body.event_count ? `Measured: ${body.event_count} events` : 'Measured: no events for that collector',
        type: body.event_count ? 'success' : 'warning',
      });
      await appData.reload();
      await overview.reload();
      await runs.reload();
    } catch (err) {
      notify({ message: err?.message || 'Measure failed', type: 'error' });
    } finally {
      setRunning(false);
    }
  }

  async function grantExemption() {
    try {
      await apiFetch('excellence/exemptions/', { token, method: 'POST', body: exemptForm });
      notify({ message: 'Exemption granted', type: 'success' });
      setExemptOpen(false);
      await appData.reload();
      await exemptions.reload();
    } catch (err) {
      notify({ message: err?.message || 'Exemption failed', type: 'error' });
    }
  }

  async function createInitiative() {
    try {
      await apiFetch('excellence/initiatives/', {
        token,
        method: 'POST',
        body: { ...initForm, target_level: Number(initForm.target_level) },
      });
      notify({ message: 'Initiative opened', type: 'success' });
      setInitOpen(false);
      await initiatives.reload();
    } catch (err) {
      notify({ message: err?.message || 'Initiative failed', type: 'error' });
    }
  }

  const checkRows = (grid?.checks || []).map((c, i) => ({ ...c, id: `${c.check_id}-${c.subject_id}-${i}` }));

  useEffect(() => {
    if (loading || error || !context || app || !current) return;
    const apps = current.apps || [];
    if (apps.length === 1) {
      navigate(`/admin/excellence/${context}/${encodeURIComponent(apps[0].id)}`, { replace: true });
    }
  }, [loading, error, context, app, current, navigate]);

  return (
    <PageContainer>
      <PageHeader
        icon={StairsIcon}
        title="Excellence"
        subtitle={grid ? `${grid.title}` : (current ? current.title : 'One ledger, many ladders')}
        description={grid?.tier === 'pulse' ? 'Pulse is one app. Tracks are filters, not separate apps.' : undefined}
        badge={(grid?.head || overview.data?.head) ? { label: (grid?.head || overview.data.head).slice(0, 7), color: 'default' } : null}
        actions={context ? (
          <Button size="small" variant="contained" disabled={running} onClick={() => measure()}>
            {running ? 'Measuring…' : 'Measure'}
          </Button>
        ) : null}
      />

      {loading && (
        <Stack spacing={1} aria-busy="true" aria-label="Loading excellence">
          <Skeleton variant="rounded" sx={{ height: 4 }} />
          <Skeleton variant="rounded" sx={{ height: 22 }} />
        </Stack>
      )}
      {error && !loading && (
        <Alert
          severity="error"
          action={(
            <Button
              color="inherit"
              size="small"
              onClick={() => {
                overview.reload();
                appData.reload();
                standard.reload();
                runs.reload();
                exemptions.reload();
                initiatives.reload();
              }}
            >
              Retry
            </Button>
          )}
        >
          {error}
        </Alert>
      )}

      {section === 'rules' && <AssuranceRulesPanel embedded />}

      {!loading && !error && context && !current && !grid && (
        <EmptyState
          title={`Unknown context “${context}”`}
          description="That context is not on the excellence ledger."
          actionLabel="Back to contexts"
          onAction={() => navigate('/admin/excellence')}
        />
      )}

      {!loading && !error && !named && !context && (
        <Stack spacing={1} role="list" aria-label="Contexts">
          {contexts.map((row) => (
            <Button
              key={row.id}
              variant="outlined"
              fullWidth
              sx={{ justifyContent: 'flex-start', textAlign: 'left', py: 1.5 }}
              aria-label={`Open ${row.title}`}
              onClick={() => {
                const apps = row.apps || [];
                if (apps.length === 1) {
                  navigate(`/admin/excellence/${row.id}/${encodeURIComponent(apps[0].id)}`);
                } else {
                  navigate(`/admin/excellence/${row.id}`);
                }
              }}
            >
              <Stack spacing={0.25} alignItems="flex-start">
                <Typography variant="subtitle1">{row.title}</Typography>
                <Typography variant="body2" color="text.secondary">
                  {row.app_count === 1 ? 'One app' : `${row.app_count} apps`}
                  {' · '}
                  {levelName(row.floor)}
                </Typography>
              </Stack>
            </Button>
          ))}
          {contexts.length === 0 && (
            <EmptyState title="No contexts declared" description="Nothing is registered on the excellence ledger yet." />
          )}
        </Stack>
      )}

      {!loading && !error && context && !app && current && (current.apps?.length !== 1) && (
        <Stack spacing={1} role="list" aria-label={`${current.title} apps`}>
          {(current.apps || []).map((row) => (
            <Button
              key={row.id}
              variant="outlined"
              fullWidth
              sx={{ justifyContent: 'flex-start', textAlign: 'left', py: 1.5 }}
              aria-label={`Open ${row.title}`}
              onClick={() => navigate(`/admin/excellence/${context}/${encodeURIComponent(row.id)}`)}
            >
              <Stack spacing={0.25} alignItems="flex-start">
                <Typography variant="subtitle1">{row.title}</Typography>
                <Typography variant="body2" color="text.secondary">
                  {row.level_name || levelName(row.level)}
                  {row.weakest ? ` · Weakest ${aspectLabel(row.weakest)}` : ''}
                </Typography>
              </Stack>
            </Button>
          ))}
          {(current.apps || []).length === 0 && (
            <EmptyState title="No apps declared" description="This context has no apps on the ladder yet." />
          )}
        </Stack>
      )}

      {!loading && !error && grid && (
        <Stack spacing={2} sx={{ width: '100%' }}>
          <Stack spacing={0.5}>
            <Typography variant="h6">{grid.level_name || levelName(grid.level)}</Typography>
            <Typography variant="body2" color="text.secondary">
              The level is the weakest aspect.
              {grid.weakest ? ` Weakest: ${aspectLabel(grid.weakest)}.` : ''}
            </Typography>
          </Stack>
          <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap alignItems="flex-end">
            {grid.tier === 'pulse' && (
              <Stack spacing={0.5} sx={{ minWidth: '12rem', flex: 1 }}>
                <Typography variant="body2" component="label" id="excellence-track-label">
                  Track
                </Typography>
                <SearchSelect
                  aria-labelledby="excellence-track-label"
                  fullWidth
                  options={[{ value: '', label: 'All tracks' }, ...(grid.tracks || []).map((t) => ({ value: t.id, label: t.title }))]}
                  value={track}
                  onChange={async (opt) => {
                    const next = opt?.value || '';
                    setTrack(next);
                    const detail = await apiFetch(`excellence/apps/pulse/${next ? `?track=${next}` : ''}`, { token });
                    appData.setData(detail);
                    setCell(null);
                  }}
                />
              </Stack>
            )}
            <Stack spacing={0.5} sx={{ minWidth: '12rem', flex: 1 }}>
              <Typography variant="body2" component="label" id="excellence-collector-label">
                Collector
              </Typography>
              <SearchSelect
                aria-labelledby="excellence-collector-label"
                fullWidth
                options={COLLECTORS}
                value={collector}
                clearable={false}
                onChange={(opt) => setCollector(opt?.value || 'repo')}
              />
            </Stack>
          </Stack>
          {grid.level === 0 && (
            <Alert severity="warning">
              Unmanaged: a rank-1 cell is open, failed, or not passed on this commit. An open cell has no check yet.
            </Alert>
          )}
          <ExcellenceCellMap cells={grid.cells || []} level={grid.level} selected={cell} onSelect={setCell} />
          <Tabs value={tab} onChange={(_e, v) => setTab(v)} variant="scrollable" aria-label="App dashboard">
            {['Checks', 'Evidence', 'Run log', 'Trend', 'Waivers'].map((label) => <Tab key={label} label={label} />)}
          </Tabs>
          <TabPanel value={tab} index={0}>
            <FilteredDataGrid
              embedded
              title="Checks"
              rows={checkRows}
              getRowId={(row) => row.id}
              columns={[
                { field: 'dimension', headerName: 'Dimension', width: 130 },
                { field: 'rank', headerName: 'Level', width: 80 },
                { field: 'title', headerName: 'Check', flex: 1, minWidth: 200 },
                { field: 'state', headerName: 'State', width: 130, renderCell: (p) => <StateChip state={p.value} /> },
                { field: 'subject_id', headerName: 'Subject', flex: 1, minWidth: 160 },
              ]}
              emptyMessage="No checks bound yet"
              emptySubtext="Open cells on the grid are rungs waiting for a check"
            />
          </TabPanel>
          <TabPanel value={tab} index={1}>
            <FilteredDataGrid
              embedded
              title="Evidence"
              rows={grid.events || []}
              getRowId={(row) => row.id}
              columns={[
                { field: 'at', headerName: 'When', width: 180 },
                { field: 'check_id', headerName: 'Check', flex: 1, minWidth: 140 },
                { field: 'result', headerName: 'Result', width: 110, renderCell: (p) => <StateChip state={p.value} /> },
                { field: 'evidence_class', headerName: 'Evidence', width: 160 },
                { field: 'commit', headerName: 'Commit', width: 110 },
              ]}
              emptyMessage="No evidence on this app"
              emptySubtext="Measure a collector to write events on this commit"
            />
          </TabPanel>
          <TabPanel value={tab} index={2}>
            <FilteredDataGrid
              embedded
              title="Runs"
              rows={grid.runs || []}
              getRowId={(row) => row.id}
              columns={[
                { field: 'id', headerName: '#', width: 70 },
                { field: 'status', headerName: 'Status', width: 120, renderCell: (p) => <StateChip state={p.value === 'succeeded' ? 'passed' : p.value} /> },
                { field: 'collectors', headerName: 'Collectors', flex: 1, minWidth: 160, valueGetter: (_v, row) => (row.collectors || []).join(', ') },
                { field: 'event_count', headerName: 'Events', width: 90 },
                { field: 'requested_by', headerName: 'By', width: 120 },
              ]}
              emptyMessage="No runs for this context"
            />
          </TabPanel>
          <TabPanel value={tab} index={3}>
            <FilteredDataGrid
              embedded
              title="Trend"
              subtitle="Lowest subject level on each snapshot day"
              rows={(grid.trend || []).map((t) => ({ ...t, id: t.date }))}
              getRowId={(row) => row.id}
              columns={[
                { field: 'date', headerName: 'Date', flex: 1 },
                { field: 'level', headerName: 'Level', width: 120, renderCell: (p) => <LevelChip level={p.value} /> },
              ]}
              emptyMessage="No snapshots yet"
              emptySubtext="Measure with a snapshot write to start the series"
            />
          </TabPanel>
          <TabPanel value={tab} index={4}>
            <FilteredDataGrid
              embedded
              title="Exemptions"
              rows={grid.exemptions || []}
              getRowId={(row) => row.id}
              columns={[
                { field: 'check_id', headerName: 'Check', flex: 1, minWidth: 140 },
                { field: 'subject_id', headerName: 'Subject', flex: 1, minWidth: 160 },
                { field: 'until', headerName: 'Until', width: 120 },
                { field: 'active', headerName: 'Active', width: 100, valueGetter: (_v, row) => (row.active ? 'yes' : 'expired') },
                { field: 'reason', headerName: 'Reason', flex: 1.2, minWidth: 180 },
              ]}
              emptyMessage="No exemptions"
            />
          </TabPanel>
        </Stack>
      )}

      {section === 'standard' && !loading && !error && standard.data && (
        <FilteredDataGrid
          embedded
          title={`Standard v${standard.data.version}`}
          subtitle="Nine dimensions, six levels. A cell with no check stays open and caps that dimension."
          rows={(standard.data.rungs || []).map((r) => ({ id: `${r.dimension}-${r.level}`, ...r, rank: `L${r.level}` }))}
          getRowId={(row) => row.id}
          columns={[
            { field: 'dimension', headerName: 'Dimension', width: 140 },
            { field: 'rank', headerName: 'Level', width: 80 },
            { field: 'title', headerName: 'Rung', flex: 1, minWidth: 280 },
            { field: 'evidence_floor', headerName: 'Evidence floor', width: 180 },
          ]}
        />
      )}

      {section === 'runs' && !loading && !error && (
        <FilteredDataGrid
          embedded
          title="Runs"
          rows={runs.data?.runs || []}
          getRowId={(row) => row.id}
          columns={[
            { field: 'id', headerName: '#', width: 70 },
            { field: 'status', headerName: 'Status', width: 130, renderCell: (p) => <StateChip state={p.value} /> },
            { field: 'tier', headerName: 'Context', width: 120 },
            { field: 'collectors', headerName: 'Collectors', flex: 1, minWidth: 160, valueGetter: (_v, row) => (row.collectors || []).join(', ') },
            { field: 'event_count', headerName: 'Events', width: 90 },
            { field: 'requested_by', headerName: 'By', width: 120 },
            { field: 'started_at', headerName: 'Started', width: 180 },
          ]}
          emptyMessage="No runs yet"
        />
      )}

      {section === 'exemptions' && !loading && !error && (
        <FilteredDataGrid
          embedded
          title="Exemptions"
          subtitle="A waiver has an owner and an end date. After that date it no longer counts."
          rows={exemptions.data?.exemptions || []}
          getRowId={(row) => row.id}
          columns={[
            { field: 'check_id', headerName: 'Check', flex: 1, minWidth: 140 },
            { field: 'subject_id', headerName: 'Subject', flex: 1, minWidth: 160 },
            { field: 'until', headerName: 'Until', width: 120 },
            { field: 'active', headerName: 'Active', width: 100, valueGetter: (_v, row) => (row.active ? 'yes' : 'expired') },
            { field: 'granted_by', headerName: 'By', width: 120 },
            { field: 'reason', headerName: 'Reason', flex: 1.2, minWidth: 180 },
            {
              field: 'actions', headerName: 'Actions', width: 110, sortable: false,
              renderCell: (p) => (
                <Button size="small" aria-label={`Revoke ${p.row.check_id}`} onClick={async () => {
                  await apiFetch(`excellence/exemptions/${p.row.id}/`, { token, method: 'DELETE' });
                  notify({ message: 'Exemption revoked', type: 'success' });
                  exemptions.reload();
                }}
                >Revoke</Button>
              ),
            },
          ]}
          emptyMessage="No exemptions"
        />
      )}

      {section === 'initiatives' && !loading && !error && (
        <Stack spacing={1}>
          <Button size="small" variant="contained" sx={{ alignSelf: 'flex-start' }} onClick={() => setInitOpen(true)}>New initiative</Button>
          <FilteredDataGrid
            embedded
            title="Initiatives"
            subtitle="A deadline on top of the ladder. Progress is apps already at the target level."
            rows={initiatives.data?.initiatives || []}
            getRowId={(row) => row.id}
            columns={[
              { field: 'title', headerName: 'Initiative', flex: 1, minWidth: 160 },
              { field: 'tier', headerName: 'Context', width: 120 },
              { field: 'target_level', headerName: 'Target', width: 90, renderCell: (p) => <LevelChip level={p.value} /> },
              { field: 'reached', headerName: 'Reached', width: 100, valueGetter: (_v, row) => `${row.reached}/${row.scope}` },
              { field: 'deadline', headerName: 'Deadline', width: 120 },
              { field: 'status', headerName: 'Status', width: 110, renderCell: (p) => <StateChip state={p.value} /> },
              {
                field: 'actions', headerName: 'Actions', width: 160, sortable: false,
                renderCell: (p) => (
                  <Button size="small" aria-label={`Close ${p.row.title}`} onClick={async () => {
                    const status = p.row.reached === p.row.scope && p.row.scope > 0 ? 'met' : 'missed';
                    await apiFetch(`excellence/initiatives/${p.row.id}/close/`, { token, method: 'POST', body: { status } });
                    initiatives.reload();
                  }}
                  >Close</Button>
                ),
              },
            ]}
            emptyMessage="No initiatives"
            emptySubtext="Open one when a set of apps must reach a level by a date"
          />
        </Stack>
      )}

      <RightPanel
        open={Boolean(cell)}
        onClose={() => setCell(null)}
        title={cell ? `${aspectLabel(cell.dimension)} · ${levelName(cell.level)}` : ''}
        width={380}
      >
        {cell && (
          <Stack spacing={1}>
            <StateChip state={cell.state} />
            <Typography variant="body2">{cell.rung}</Typography>
            <Typography variant="caption" color="text.secondary">Evidence floor: {cell.evidence_floor}</Typography>
            {(cell.checks || []).map((check) => (
              <Typography key={`${check.check_id}-${check.subject_id}`} variant="body2">{check.title} — {check.state}</Typography>
            ))}
            {cell.state === 'open' && <Typography variant="body2">No check is bound to this cell. It caps the dimension.</Typography>}
            <Button size="small" variant="contained" disabled={running} onClick={() => measure({ collector })}>Measure this context</Button>
            {(cell.checks || []).length > 0 && (
              <Button size="small" onClick={() => {
                const first = cell.checks[0];
                setExemptForm({ check_id: first.check_id, subject_id: first.subject_id, reason: '', until: '' });
                setExemptOpen(true);
              }}
              >Request exemption</Button>
            )}
          </Stack>
        )}
      </RightPanel>

      <SystemDialog
        open={exemptOpen}
        title="Grant exemption"
        onClose={() => setExemptOpen(false)}
        actions={<Button size="small" variant="contained" onClick={grantExemption}>Grant</Button>}
      >
        <Stack spacing={1}>
          <SearchSelect
            label="Check"
            options={(cell?.checks || []).map((c) => ({ value: c.check_id, label: c.title }))}
            value={exemptForm.check_id}
            onChange={(opt) => setExemptForm((f) => ({ ...f, check_id: opt?.value || '' }))}
          />
          <SearchSelect
            label="Subject"
            options={(grid?.subjects || []).map((s) => ({ value: s.id, label: s.title }))}
            value={exemptForm.subject_id}
            onChange={(opt) => setExemptForm((f) => ({ ...f, subject_id: opt?.value || '' }))}
          />
          <TextField size="small" label="Reason" value={exemptForm.reason} onChange={(e) => setExemptForm((f) => ({ ...f, reason: e.target.value }))} />
          <TextField size="small" label="Until" type="date" InputLabelProps={{ shrink: true }} value={exemptForm.until} onChange={(e) => setExemptForm((f) => ({ ...f, until: e.target.value }))} />
        </Stack>
      </SystemDialog>

      <SystemDialog
        open={initOpen}
        title="New initiative"
        onClose={() => setInitOpen(false)}
        actions={<Button size="small" variant="contained" onClick={createInitiative}>Open initiative</Button>}
      >
        <Stack spacing={1}>
          <TextField size="small" label="Title" value={initForm.title} onChange={(e) => setInitForm((f) => ({ ...f, title: e.target.value }))} />
          <SearchSelect
            label="Context"
            options={contexts.map((c) => ({ value: c.id, label: c.title }))}
            value={initForm.tier}
            onChange={(opt) => setInitForm((f) => ({ ...f, tier: opt?.value || '', app_ids: [] }))}
          />
          <SearchSelect label="Target level" options={LEVELS} value={initForm.target_level} clearable={false} onChange={(opt) => setInitForm((f) => ({ ...f, target_level: opt?.value || '3' }))} />
          <SearchSelect
            label="Apps"
            multiple
            options={(contexts.find((c) => c.id === initForm.tier)?.apps || []).map((a) => ({ value: a.id, label: a.title }))}
            value={initForm.app_ids}
            onChange={(opts) => setInitForm((f) => ({ ...f, app_ids: (opts || []).map((o) => o.value) }))}
          />
          <TextField size="small" label="Deadline" type="date" InputLabelProps={{ shrink: true }} value={initForm.deadline} onChange={(e) => setInitForm((f) => ({ ...f, deadline: e.target.value }))} />
        </Stack>
      </SystemDialog>
    </PageContainer>
  );
}
