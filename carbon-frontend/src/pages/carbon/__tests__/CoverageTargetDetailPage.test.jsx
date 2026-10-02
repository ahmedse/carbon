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
    counts: { required: 9, entered: 3, excluded: 1, awaiting_factor: 1, missing: 4 },
    measured_pct: '44.44',
    measured_kg: null,
    state: 'short',
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
});
