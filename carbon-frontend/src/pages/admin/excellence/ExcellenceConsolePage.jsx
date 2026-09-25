import React, { useCallback, useEffect, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { Alert, Button, Chip, IconButton, Skeleton, Stack, Tab, Tabs, TextField, Tooltip, Typography } from '@mui/material';
import VisibilityRounded from '@mui/icons-material/VisibilityRounded';
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
import { aspectLabel, COWORKER_LEVELS, levelColor, levelName, PULSE_AREAS, pulseArea, stateColor } from './excellenceUi';

const LEVELS = [1, 2, 3, 4, 5, 6].map((n) => ({ value: String(n), label: levelName(n) }));

const SECTIONS = new Set(['rules', 'standard', 'runs', 'evidence', 'exemptions', 'initiatives', 'subjects']);
const PROOF_COLLECTORS = ['repo', 'pulse_gauge', 'observe', 'rbac', 'budget', 'design_lint'];

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
  useEffect(() => {
    if (!url) {
      setData(null);
      setLoading(false);
      return;
    }
    reload();
  }, [reload, url]);
  return { data, setData, error, loading, reload };
}

function StateChip({ state }) {
  return <Chip size="small" color={stateColor(state)} label={state} />;
}

function LevelChip({ level, name }) {
  return <Chip size="small" color={levelColor(level)} label={name || levelName(level)} />;
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
  const rawApp = named ? '' : (params.app || '');
  const area = context === 'pulse' ? pulseArea(rawApp) : null;
  const app = area ? '' : rawApp;
  useDocumentTitle('Excellence');

  const inContext = Boolean(context);
  const overview = useGet(token, (!named && !app) || section === 'initiatives' || inContext ? 'excellence/overview/' : null);
  const appData = useGet(token, app ? `excellence/apps/${encodeURIComponent(app)}/` : (context === 'pulse' ? 'excellence/apps/pulse/' : null));
  const standard = useGet(token, section === 'standard' || inContext ? 'excellence/standard/' : null);
  const runs = useGet(token, section === 'runs' || section === 'evidence' || inContext ? `excellence/runs/${inContext ? `?tier=${encodeURIComponent(context)}` : ''}` : null);
  const exemptions = useGet(token, section === 'exemptions' || inContext ? 'excellence/exemptions/' : null);
  const initiatives = useGet(token, section === 'initiatives' || inContext ? 'excellence/initiatives/' : null);

  const [tab, setTab] = useState(0);
  const [cell, setCell] = useState(null);
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
        body: { collectors: extra?.collectors || PROOF_COLLECTORS, tier, write_snapshot: true },
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
  const portfolioFloor = contexts.length ? Math.min(...contexts.map((c) => Number(c.floor ?? 0))) : 0;
  const portfolioCoverage = contexts.length
    ? contexts.reduce((sum, c) => sum + Number(c.coverage || 0), 0) / contexts.length
    : 0;
  const unmanagedCount = contexts.filter((c) => Number(c.floor ?? 0) === 0).length;

  return (
    <PageContainer>
      <PageHeader
        icon={StairsIcon}
        title="Excellence"
        subtitle={area ? area.title : (current ? current.title : 'Coverage and progress on the quality ladder')}
        description={
          area
            ? area.promise
            : (app
              ? undefined
              : (current
                ? 'The level is the weakest aspect. Coverage is how much of the standard has a check.'
                : 'A framework with a window: see what you have, how far you are, and what to do next.'))
        }
        badge={(grid?.head || overview.data?.head) ? { label: (grid?.head || overview.data.head).slice(0, 7), color: 'default' } : null}
        actions={context ? (
          <Button size="small" variant="contained" disabled={running} onClick={() => measure()}>
            {running ? 'Measuring…' : 'Measure proof'}
          </Button>
        ) : (!named ? (
          <Button size="small" variant="contained" disabled={running} onClick={() => measure({ collectors: PROOF_COLLECTORS })}>
            {running ? 'Measuring…' : 'Measure proof'}
          </Button>
        ) : null)}
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

      {(section === 'rules' || section === 'evidence') && <AssuranceRulesPanel embedded />}

      {!loading && !error && context && !current && !grid && (
        <EmptyState
          title={`Unknown context “${context}”`}
          description="That context is not on the excellence ledger."
          actionLabel="Back to contexts"
          onAction={() => navigate('/admin/excellence')}
        />
      )}

      {!loading && !error && !named && !context && (
        <Stack spacing={2}>
          <Alert severity="info">
            Excellence is Carbon’s quality framework: nine aspects and six maturity levels.
            This page is your window onto coverage and progress on that ladder.
            The level is always the weakest aspect. An open cell has no check yet — silence is not a pass.
          </Alert>

          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            <LevelChip level={portfolioFloor} />
            <Chip size="small" variant="outlined" label={`Coverage ${Math.round(portfolioCoverage * 100)}%`} />
            <Chip size="small" variant="outlined" label={`${contexts.length} products on the ledger`} />
            {unmanagedCount > 0 && (
              <Chip size="small" color="warning" label={`${unmanagedCount} still Unmanaged`} />
            )}
          </Stack>

          <Typography variant="body2" color="text.secondary">
            Coverage is honesty of the standard (cells with a check ÷ applicable cells). It is not the score.
            Progress is the level. Open a product to see which aspect is holding it down and what to prove next.
          </Typography>

          <FilteredDataGrid
            embedded
            title="Where to look"
            subtitle="Each product opens the same window for that scope."
            rows={contexts}
            getRowId={(row) => row.id}
            columns={[
              { field: 'title', headerName: 'Product', flex: 1, minWidth: 180 },
              { field: 'floor', headerName: 'Progress', width: 140, renderCell: (p) => <LevelChip level={p.value} /> },
              { field: 'coverage', headerName: 'Coverage', width: 110, valueGetter: (_v, row) => `${Math.round((row.coverage || 0) * 100)}%` },
              {
                field: 'actions', headerName: '', width: 72, sortable: false, filterable: false,
                renderCell: (p) => (
                  <Tooltip title={`View ${p.row.title}`}>
                    <IconButton
                      size="small"
                      aria-label={`View ${p.row.title}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        navigate(`/admin/excellence/${p.row.id}`);
                      }}
                    >
                      <VisibilityRounded fontSize="small" />
                    </IconButton>
                  </Tooltip>
                ),
              },
            ]}
            emptyMessage="No products on the ledger"
          />

          <FilteredDataGrid
            embedded
            title="Take action"
            subtitle="Measure, raise a program, waive with expiry, or read the standard."
            rows={[
              { id: 'standard', title: 'Read the standard', hint: 'Nine aspects × six levels', path: '/admin/excellence/standard' },
              { id: 'evidence', title: 'Inspect evidence', hint: 'Runs, events, release rules', path: '/admin/excellence/evidence' },
              { id: 'initiatives', title: 'Open initiatives', hint: 'Target a level by a date', path: '/admin/excellence/initiatives' },
              { id: 'exemptions', title: 'Review exemptions', hint: 'Temporary look-aways', path: '/admin/excellence/exemptions' },
            ]}
            getRowId={(row) => row.id}
            columns={[
              { field: 'title', headerName: 'Action', flex: 1, minWidth: 180 },
              { field: 'hint', headerName: 'Why', flex: 1.2, minWidth: 200 },
              {
                field: 'actions', headerName: '', width: 72, sortable: false, filterable: false,
                renderCell: (p) => (
                  <Tooltip title={`View ${p.row.title}`}>
                    <IconButton size="small" aria-label={`View ${p.row.title}`} onClick={(e) => { e.stopPropagation(); navigate(p.row.path); }}>
                      <VisibilityRounded fontSize="small" />
                    </IconButton>
                  </Tooltip>
                ),
              },
            ]}
          />
        </Stack>
      )}

      {!loading && !error && context && !app && !area && current && (
        <Stack spacing={2}>
          <Alert severity="info">
            This product’s level is the weakest of nine aspects.
            Coverage tells you how much of the standard already has a check. Open a component for the 9×6 ladder and the next proof to earn.
          </Alert>
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            <LevelChip level={current.floor} />
            <Chip size="small" variant="outlined" label={`Coverage ${Math.round((current.coverage || 0) * 100)}%`} />
            {grid?.weakest && <Chip size="small" variant="outlined" label={`Weakest ${aspectLabel(grid.weakest)}`} />}
            <Chip size="small" variant="outlined" label={`${(current.apps || []).length} assessed components`} />
          </Stack>

          <FilteredDataGrid
            embedded
            title="Assessed components"
            subtitle="Open one to see coverage and progress on the excellence ladder."
            rows={current.apps || []}
            getRowId={(row) => row.id}
            columns={[
              { field: 'title', headerName: 'Component', flex: 1, minWidth: 180 },
              { field: 'level', headerName: 'Progress', width: 150, renderCell: (p) => <LevelChip level={p.row.level} name={p.row.level_name} /> },
              {
                field: 'actions', headerName: '', width: 72, sortable: false, filterable: false,
                renderCell: (p) => (
                  <Tooltip title={`View ${p.row.title}`}>
                    <IconButton size="small" aria-label={`View ${p.row.title}`} onClick={(e) => { e.stopPropagation(); navigate(`/admin/excellence/${context}/${encodeURIComponent(p.row.id)}`); }}>
                      <VisibilityRounded fontSize="small" />
                    </IconButton>
                  </Tooltip>
                ),
              },
            ]}
            emptyMessage="No components declared"
          />

          {context === 'pulse' && (
            <Stack spacing={1}>
              <Typography variant="subtitle2">Pulse coworker maturity (separate scale)</Typography>
              <Typography variant="body2" color="text.secondary">
                Not the Excellence level. Safe → Lean is Pulse intelligence. Only Continuous, Coherent, and Proactive are mapped today.
              </Typography>
              <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                {COWORKER_LEVELS.map((level) => (
                  <Chip key={level.id} size="small" variant={level.mapped ? 'filled' : 'outlined'} color={level.mapped ? 'primary' : 'default'} label={level.mapped ? level.name : `${level.name} · not mapped`} />
                ))}
              </Stack>
              <FilteredDataGrid
                embedded
                title="Coworker capability areas"
                rows={PULSE_AREAS}
                getRowId={(row) => row.id}
                columns={[
                  { field: 'title', headerName: 'Area', flex: 1, minWidth: 180 },
                  { field: 'promise', headerName: 'Promise', flex: 1.4, minWidth: 220 },
                  { field: 'mapped', headerName: 'On the ladder', width: 140, renderCell: (p) => <Chip size="small" color={p.value ? 'primary' : 'default'} label={p.value ? 'Mapped' : 'Not mapped'} /> },
                  {
                    field: 'actions', headerName: '', width: 72, sortable: false, filterable: false,
                    renderCell: (p) => (
                      <Tooltip title={`View ${p.row.title}`}>
                        <IconButton size="small" aria-label={`View ${p.row.title}`} onClick={(e) => { e.stopPropagation(); navigate(`/admin/excellence/pulse/${p.row.id}`); }}>
                          <VisibilityRounded fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    ),
                  },
                ]}
              />
            </Stack>
          )}
        </Stack>
      )}

      {!loading && !error && area && (
        <Stack spacing={1}>
          <Alert severity={area.mapped ? 'info' : 'warning'}>{area.proof}</Alert>
          <Button size="small" onClick={() => navigate('/admin/excellence/pulse/pulse')}>View the Pulse quality frame</Button>
        </Stack>
      )}

      {!loading && !error && app && grid && (
        <Stack spacing={2} sx={{ width: '100%' }}>
          <Stack spacing={0.5}>
            <Typography variant="h6">{grid.level_name || levelName(grid.level)}</Typography>
            <Typography variant="body2" color="text.secondary">
              The level is the weakest aspect.
              {grid.weakest ? ` Weakest: ${aspectLabel(grid.weakest)}.` : ''}
            </Typography>
          </Stack>
          {grid.level === 0 && (
            <Alert severity="warning">
              Unmanaged: a rank-1 cell is open, failed, or not passed on this commit. An open cell has no check yet.
            </Alert>
          )}
          <ExcellenceCellMap cells={grid.cells || []} level={grid.level} selected={cell} onSelect={setCell} />
          <Tabs value={tab} onChange={(_e, v) => setTab(v)} variant="scrollable" aria-label="App dashboard">
            {['Checks', 'Evidence', 'Trend'].map((label) => <Tab key={label} label={label} />)}
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

      {(section === 'runs' || section === 'evidence') && !loading && !error && (
        <FilteredDataGrid
          embedded
          title="Runs"
          rows={(runs.data?.runs || []).filter((row) => !inContext || row.tier === context)}
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
          rows={(exemptions.data?.exemptions || []).filter((row) => !inContext || String(row.subject_id || '').startsWith(`${context}.`))}
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
            rows={(initiatives.data?.initiatives || []).filter((row) => !inContext || row.tier === context)}
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

      <SystemDialog
        open={Boolean(cell)}
        title={cell ? `${aspectLabel(cell.dimension)} · ${levelName(cell.level)}` : 'Cell'}
        onClose={() => setCell(null)}
        actions={(
          <Button size="small" variant="contained" disabled={running || !cell} onClick={() => measure()}>
            Measure this context
          </Button>
        )}
      >
        {cell && (
          <Stack spacing={1}>
            <StateChip state={cell.state} />
            <Typography variant="body2">{cell.rung}</Typography>
            <Typography variant="body2" color="text.secondary">Evidence floor: {cell.evidence_floor}</Typography>
            {(cell.checks || []).map((check) => (
              <Typography key={`${check.check_id}-${check.subject_id}`} variant="body2">{check.title} — {check.state}</Typography>
            ))}
            {cell.state === 'open' && <Typography variant="body2">No check is bound to this cell. It caps the dimension.</Typography>}
            {(cell.checks || []).length > 0 && (
              <Button size="small" onClick={() => {
                const first = cell.checks[0];
                setExemptForm({ check_id: first.check_id, subject_id: first.subject_id, reason: '', until: '' });
                setCell(null);
                setExemptOpen(true);
              }}
              >Request exemption</Button>
            )}
          </Stack>
        )}
      </SystemDialog>

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
