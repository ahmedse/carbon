import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import CoverageTargetDetailPage from '../CoverageTargetDetailPage';

vi.mock('../../../hooks/useDocumentTitle', () => ({ default: () => {} }));

vi.mock('../../../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token', user: { is_superuser: true }, availablePerspectives: [] }),
}));

vi.mock('../../../components/NotificationProvider', () => ({
  useNotification: () => ({ notify: vi.fn(), notifyFromError: vi.fn() }),
}));

const fetchCoverageTarget = vi.fn();
const updateCoverageTarget = vi.fn();
const deleteCoverageTarget = vi.fn();
const createCoverageTask = vi.fn();
const updateCoverageTask = vi.fn();
const deleteCoverageTask = vi.fn();
const fetchCoverageCampusOptions = vi.fn();
const fetchCoverageOrgUnitOptions = vi.fn();
const fetchCoverageOwnerOptions = vi.fn();

vi.mock('../../../api/emissions-extended', () => ({
  fetchCoverageTarget: (...args) => fetchCoverageTarget(...args),
  updateCoverageTarget: (...args) => updateCoverageTarget(...args),
  deleteCoverageTarget: (...args) => deleteCoverageTarget(...args),
  createCoverageTask: (...args) => createCoverageTask(...args),
  updateCoverageTask: (...args) => updateCoverageTask(...args),
  deleteCoverageTask: (...args) => deleteCoverageTask(...args),
  fetchCoverageCampusOptions: (...args) => fetchCoverageCampusOptions(...args),
  fetchCoverageOrgUnitOptions: (...args) => fetchCoverageOrgUnitOptions(...args),
  fetchCoverageOwnerOptions: (...args) => fetchCoverageOwnerOptions(...args),
}));

const targetFixture = {
  id: 5,
  name: 'South Valley 1+2',
  campus: 2,
  campus_name: 'South Valley Campus',
  org_unit: 3,
  org_unit_name: 'South Valley Lab',
  reporting_period: 17,
  reporting_period_name: 'Calendar year 2026',
  scope: '1+2',
  scope_display: 'Scope 1+2',
  scope3_category: null,
  goal_kind: 'percent',
  goal_value: '80.0000',
  goal_unit: '',
  min_quality_tier: 2,
  due_date: '2026-12-31',
  owner: 9,
  owner_username: 'lead',
  owner_name: 'Lead Person',
  status: 'active',
  notes: 'Reduce the gap.',
  progress: {
    counts: {
      required: 9,
      entered: 3,
      excluded: 1,
      awaiting_factor: 1,
      missing: 4,
      measured: 3,
      settled: 4,
      settled_at_target: 2,
      below_floor: 0,
      tier_unknown: 0,
    },
    measured_pct: '44.44',
    excluded_pct: '11.11',
    settled_pct: '44.44',
    settled_at_target_pct: '22.22',
    measured_kg: null,
    measured_kg_at_target: null,
    measured_value: null,
    measured_unit: null,
    metric: 'coverage_percent',
    goal_concept: 'coverage_kpi',
    goal_kind: 'percent',
    state: 'short',
    findings: [],
    claim: 'measured_not_claimed',
    coverage_complete: false,
    streams: [],
  },
  tasks: [
    {
      id: 1,
      title: 'Bind a table',
      task_type: 'bind_data_product',
      status: 'open',
      due_date: null,
      evidence: { met: false, codes: ['data_table_unbound'], claim: 'host_evidence_only' },
    },
    {
      id: 2,
      title: 'Close the rows',
      task_type: 'complete_rows',
      status: 'open',
      due_date: null,
      evidence: { met: true, codes: [], claim: 'host_evidence_only' },
    },
  ],
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/carbon/admin/coverage-targets/5']}>
      <Routes>
        <Route path="/carbon/admin/coverage-targets" element={<div>targets-list</div>} />
        <Route path="/carbon/admin/coverage-targets/:targetId" element={<CoverageTargetDetailPage />} />
        <Route path="/carbon/onboarding/intake" element={<div>intake-page</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  fetchCoverageTarget.mockReset();
  updateCoverageTarget.mockReset();
  deleteCoverageTarget.mockReset();
  createCoverageTask.mockReset();
  updateCoverageTask.mockReset();
  deleteCoverageTask.mockReset();
  fetchCoverageCampusOptions.mockReset();
  fetchCoverageOrgUnitOptions.mockReset();
  fetchCoverageOwnerOptions.mockReset();
  fetchCoverageTarget.mockResolvedValue(targetFixture);
  updateCoverageTarget.mockResolvedValue({});
  deleteCoverageTarget.mockResolvedValue({});
  createCoverageTask.mockResolvedValue({});
  updateCoverageTask.mockResolvedValue({});
  fetchCoverageCampusOptions.mockResolvedValue({
    count: 1,
    results: [{ id: 2, name: 'South Valley Campus', code: 'SV' }],
  });
  fetchCoverageOrgUnitOptions.mockResolvedValue({
    campus: { id: 2, name: 'South Valley Campus' },
    count: 2,
    results: [
      { id: 2, name: 'South Valley Campus', is_campus: true },
      { id: 3, name: 'South Valley Lab', is_campus: false },
    ],
  });
  fetchCoverageOwnerOptions.mockResolvedValue({
    count: 1,
    page: 1,
    page_size: 200,
    results: [{ id: 9, username: 'lead', full_name: 'Lead Person', label: 'Lead Person (lead)' }],
  });
});

describe('CoverageTargetDetailPage — target, progress, tasks', () => {
  it('renders the target header and its three WorkflowCard sections', async () => {
    renderPage();
    expect(await screen.findByText('South Valley 1+2')).toBeInTheDocument();
    expect(screen.getByText('Calendar year 2026 · Scope 1+2')).toBeInTheDocument();
    expect(screen.getByTestId('coverage-target-panel')).toBeInTheDocument();
    expect(screen.getByTestId('coverage-progress-panel')).toBeInTheDocument();
    expect(screen.getByTestId('coverage-tasks-panel')).toBeInTheDocument();
  });

  it('shows the real campus, org unit and owner names — never a bare id', async () => {
    renderPage();
    const panel = await screen.findByTestId('coverage-target-panel');
    expect(within(panel).getByText('South Valley Campus')).toBeInTheDocument();
    expect(within(panel).getByText('South Valley Lab')).toBeInTheDocument();
    expect(within(panel).getByText('Lead Person')).toBeInTheDocument();
    expect(within(panel).queryByText('9')).not.toBeInTheDocument();
  });

  it('names the coverage targets source on load failure and offers Retry', async () => {
    fetchCoverageTarget.mockRejectedValueOnce(
      Object.assign(new Error('The requested resource was not found.'), { status: 404 }),
    );

    renderPage();

    const alert = await screen.findByRole('alert');
    expect(within(alert).getByText(/coverage targets source returned an error/i)).toBeInTheDocument();
    expect(within(alert).getByRole('button', { name: /Retry/i })).toBeInTheDocument();
    // The bare 404 sentence must not be the only thing on screen.
    expect(screen.queryByText(/The requested resource was not found\./)).not.toBeInTheDocument();
  });

  it('labels the ratio measured, not claimed, and cross-links to the streams', async () => {
    renderPage();
    const panel = await screen.findByTestId('coverage-progress-panel');
    expect(within(panel).getByText('Measured, not claimed')).toBeInTheDocument();
    expect(within(panel).getByText(/not a coverage-complete claim/)).toBeInTheDocument();
    // Counts are read from Coverage streams; Coverage stays the only reporter.
    expect(within(panel).getByText(/only reporter of Missing \/ Entered \/ Excluded/)).toBeInTheDocument();
    expect(within(panel).getByRole('button', { name: /Open coverage streams/ })).toBeInTheDocument();
    expect(within(panel).getByText(/No measured kilogram/)).toBeInTheDocument();
  });

  it('disables Mark done without host evidence and allows it with evidence', async () => {
    renderPage();
    const tasks = await screen.findAllByTestId('coverage-task');
    const withoutEvidence = within(tasks[0]).getByRole('button', { name: /Mark done/ });
    const withEvidence = within(tasks[1]).getByRole('button', { name: /Mark done/ });

    expect(withoutEvidence).toBeDisabled();
    expect(withEvidence).not.toBeDisabled();

    const user = userEvent.setup();
    await user.click(withEvidence);
    await waitFor(() => expect(updateCoverageTask).toHaveBeenCalledWith(2, { status: 'done' }, 'test-token'));
    expect(updateCoverageTask).not.toHaveBeenCalledWith(1, { status: 'done' }, 'test-token');
  });

  it('edits the target through the Target section', async () => {
    const user = userEvent.setup();
    renderPage();
    const panel = await screen.findByTestId('coverage-target-panel');

    await user.click(within(panel).getByRole('button', { name: 'Edit' }));
    const dialog = await screen.findByRole('dialog');
    const nameField = within(dialog).getByLabelText(/Target name/i);
    await user.clear(nameField);
    await user.type(nameField, 'South Valley merged');
    await user.click(within(dialog).getByRole('button', { name: 'Update' }));

    await waitFor(() => expect(updateCoverageTarget).toHaveBeenCalledTimes(1));
    expect(updateCoverageTarget.mock.calls[0][0]).toBe('5');
    expect(updateCoverageTarget.mock.calls[0][1]).toMatchObject({ name: 'South Valley merged' });
  });

  it('deletes the target and returns to the list', async () => {
    const user = userEvent.setup();
    renderPage();
    const panel = await screen.findByTestId('coverage-target-panel');

    await user.click(within(panel).getByRole('button', { name: 'Delete' }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText(/never changes a stream state/)).toBeInTheDocument();
    await user.click(within(dialog).getByRole('button', { name: 'Delete' }));

    await waitFor(() => expect(deleteCoverageTarget).toHaveBeenCalledWith(5, 'test-token'));
    expect(await screen.findByText('targets-list')).toBeInTheDocument();
  });

  it('keeps a neutral, target-derived counts rollup — no second-reporter vocabulary (R-DC)', async () => {
    renderPage();
    const panel = await screen.findByTestId('coverage-progress-panel');

    // Neutral, target-derived counters (not Missing / Entered / Excluded states).
    expect(within(panel).getByText('Streams in scope: 9')).toBeInTheDocument();
    expect(within(panel).getByText('Streams measured (with kg): 3')).toBeInTheDocument();
    expect(within(panel).getByText('Streams below floor: 0')).toBeInTheDocument();
    expect(within(panel).getByText('Streams tier unknown: 0')).toBeInTheDocument();
    expect(within(panel).getByText('Excluded records: 1')).toBeInTheDocument();
    expect(within(panel).getByText('Awaiting factor: 1')).toBeInTheDocument();
    expect(within(panel).getByText('Streams with no entry: 4')).toBeInTheDocument();

    // The Coverage streams page is the sole Missing / Entered / Excluded reporter.
    expect(within(panel).queryByText(/^Missing/)).not.toBeInTheDocument();
    expect(within(panel).queryByText(/^Entered/)).not.toBeInTheDocument();
    expect(within(panel).queryByText(/^Excluded:/)).not.toBeInTheDocument();
  });

  it('shows measured and excluded separately and flags a fully-excluded target short, not met', async () => {
    fetchCoverageTarget.mockResolvedValue({
      ...targetFixture,
      progress: {
        ...targetFixture.progress,
        counts: {
          required: 4, measured: 0, settled: 4, settled_at_target: 0,
          below_floor: 0, tier_unknown: 0, excluded: 4, awaiting_factor: 0, missing: 0,
        },
        measured_pct: '0.00',
        excluded_pct: '100.00',
        settled_pct: '100.00',
        settled_at_target_pct: '0.00',
        state: 'short',
      },
    });
    renderPage();
    const panel = await screen.findByTestId('coverage-progress-panel');
    expect(within(panel).getByText('Measured (with kg)')).toBeInTheDocument();
    expect(within(panel).getByText('0%')).toBeInTheDocument();
    expect(within(panel).getByText('Excluded share')).toBeInTheDocument();
    expect(within(panel).getAllByText('100%').length).toBeGreaterThan(0);
    expect(within(panel).getByText('Short of goal')).toBeInTheDocument();
    expect(within(panel).queryByText('Goal met (measured)')).not.toBeInTheDocument();
    // Still the sole-reporter claim, never a coverage-complete claim.
    expect(within(panel).getByText('Measured, not claimed')).toBeInTheDocument();
  });

  it('surfaces quality-floor and tier-unknown counts distinctly', async () => {
    fetchCoverageTarget.mockResolvedValue({
      ...targetFixture,
      progress: {
        ...targetFixture.progress,
        counts: {
          ...targetFixture.progress.counts,
          measured: 5,
          below_floor: 2,
          tier_unknown: 1,
        },
      },
    });
    renderPage();
    const panel = await screen.findByTestId('coverage-progress-panel');
    expect(within(panel).getByText('Streams below floor: 2')).toBeInTheDocument();
    expect(within(panel).getByText('Streams tier unknown: 1')).toBeInTheDocument();
    expect(within(panel).getByText('2 below the quality floor')).toBeInTheDocument();
    expect(within(panel).getByText('1 tier unknown')).toBeInTheDocument();
  });

  it('renders an absolute emissions target with the measured value, absent as an em dash', async () => {
    fetchCoverageTarget.mockResolvedValue({
      ...targetFixture,
      goal_kind: 'absolute',
      goal_value: '100.0000',
      goal_unit: 'tCO2e',
      progress: {
        ...targetFixture.progress,
        metric: 'absolute_emissions',
        goal_concept: 'emissions_value',
        goal_kind: 'absolute',
        measured_value: null,
        measured_unit: null,
        state: 'short',
      },
    });
    renderPage();
    const panel = await screen.findByTestId('coverage-progress-panel');
    expect(within(panel).getByText(/No measured value — no real Calculation on this period yet/)).toBeInTheDocument();
    expect(within(panel).queryByText(/^0 tCO2e/)).not.toBeInTheDocument();
    // The target section labels the kind distinctly.
    const targetPanel = await screen.findByTestId('coverage-target-panel');
    expect(within(targetPanel).getByText('Emissions value target')).toBeInTheDocument();
  });

  it('shows no_declared_sources and goal_unit_not_co2e as explicit headlined findings', async () => {
    fetchCoverageTarget.mockResolvedValue({
      ...targetFixture,
      progress: {
        ...targetFixture.progress,
        counts: {
          required: 0, measured: 0, settled: 0, settled_at_target: 0,
          below_floor: 0, tier_unknown: 0, excluded: 0, awaiting_factor: 0, missing: 0,
        },
        measured_pct: null,
        excluded_pct: null,
        state: 'invalid_unit',
        findings: [
          { code: 'no_declared_sources', detail: 'none' },
          { code: 'goal_unit_not_co2e', detail: 'bad unit' },
        ],
      },
    });
    renderPage();
    const panel = await screen.findByTestId('coverage-progress-panel');
    expect(within(panel).getAllByText('Finding:').length).toBe(2);
    expect(within(panel).getByText(/No declared sources under this boundary/)).toBeInTheDocument();
    expect(within(panel).getByText(/not a CO2e mass unit/)).toBeInTheDocument();
    expect(within(panel).getByText('Invalid goal unit')).toBeInTheDocument();
    // Not rendered as the generic empty line.
    expect(within(panel).queryByText(/No active streams in this target's scope yet/)).not.toBeInTheDocument();
  });

  it('shows the next-action gap + verb and a prefilled intake CTA from the live payload (D6)', async () => {
    fetchCoverageTarget.mockResolvedValue({
      ...targetFixture,
      progress: {
        ...targetFixture.progress,
        next_actions: [
          {
            code: 'missing',
            count: 1,
            verb: 'enter_stream',
            moves: ['entered', 'measured'],
            streams: [
              {
                inventory_source_id: 42,
                source_name: 'Smart Village electricity',
                org_unit_id: 3,
                scope: 2,
              },
            ],
          },
        ],
      },
    });
    const user = userEvent.setup();
    renderPage();
    const panel = await screen.findByTestId('coverage-progress-panel');
    expect(within(panel).getByText('Missing entry · 1')).toBeInTheDocument();
    expect(within(panel).getByText('Enter the stream')).toBeInTheDocument();

    await user.click(within(panel).getByRole('button', { name: /Open Smart Village electricity/ }));
    expect(await screen.findByText('intake-page')).toBeInTheDocument();
  });

  it('distinguishes a genuinely closed task from one done without moving data (D6)', async () => {
    fetchCoverageTarget.mockResolvedValue({
      ...targetFixture,
      tasks: [
        {
          id: 1,
          title: 'Bind a table',
          task_type: 'bind_data_product',
          status: 'open',
          due_date: null,
          evidence: { met: false, codes: ['data_table_unbound'], claim: 'host_evidence_only' },
          closes: {
            state: 'awaiting_evidence',
            gap: 'missing',
            gap_changed: false,
            evidence_met: false,
            moves: ['entered', 'measured'],
            codes: ['data_table_unbound'],
            claim: 'host_evidence_only',
          },
        },
        {
          id: 2,
          title: 'Close the rows',
          task_type: 'complete_rows',
          status: 'done',
          due_date: null,
          evidence: { met: true, codes: [], claim: 'host_evidence_only' },
          closes: {
            state: 'closed',
            gap: 'in_progress',
            gap_changed: true,
            evidence_met: true,
            moves: ['entered', 'measured'],
            codes: [],
            claim: 'host_evidence_only',
          },
        },
      ],
    });
    renderPage();
    const tasks = await screen.findAllByTestId('coverage-task');
    expect(within(tasks[0]).getByText('Not closed — evidence missing')).toBeInTheDocument();
    expect(within(tasks[0]).getByText('Closes: Missing entry')).toBeInTheDocument();
    expect(within(tasks[1]).getByText('Closed — data moved')).toBeInTheDocument();
    expect(within(tasks[1]).getByText('Closes: Entry started, no Calculation yet')).toBeInTheDocument();
    // The summary counts only genuinely closed tasks, never a bare done flag.
    expect(screen.getByText('1/2 closed by real data')).toBeInTheDocument();
  });

  it('keeps the board and detail wording consistent for measured / excluded', async () => {
    renderPage();
    const panel = await screen.findByTestId('coverage-progress-panel');
    // Same terms as the board ratio — not "Measured 44.44% · excluded 11.11%".
    expect(within(panel).getByText('Measured (with kg): 44.44% · Excluded share: 11.11%')).toBeInTheDocument();
  });
});
