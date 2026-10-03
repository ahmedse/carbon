// src/__tests__/InboundCommitProgress.test.jsx
// ID2 — People Import commit: close-the-confirm-first, one live progress dialog
// driven by the shared SSE hook, batched log rows, an actionable Retry on
// failure, and the SoD identities.
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

const mocks = vi.hoisted(() => ({
  notify: vi.fn(),
  notifyFromError: vi.fn(),
  fetchInboundBatch: vi.fn(),
  fetchInboundTargets: vi.fn(),
  fetchInboundTemplates: vi.fn(),
  fetchInboundRows: vi.fn(),
  fetchInboundTemplateExamples: vi.fn(),
  downloadInboundTemplateExample: vi.fn(),
  saveInboundMapping: vi.fn(),
  saveInboundTemplate: vi.fn(),
  commitInboundBatch: vi.fn(),
  fetchInboundCommitRun: vi.fn(),
  fetchInboundCommitRuns: vi.fn(),
  downloadInboundRejects: vi.fn(),
  smokeInboundBatch: vi.fn(),
  uploadInboundFile: vi.fn(),
  fetchReferenceSets: vi.fn(),
  progress: { onFrame: null, connected: true },
}));

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({
    token: 't',
    isGlobalAdminFlag: false,
    user: { username: 'emp_2400' },
    userCapabilities: ['inbound:commit'],
  }),
}));

vi.mock('../components/NotificationProvider', () => ({
  useNotification: () => ({ notify: mocks.notify, notifyFromError: mocks.notifyFromError }),
}));

// Capture the shared-hook frame callback so tests can drive live progress.
vi.mock('../hooks/useOperationProgress', () => ({
  useOperationProgress: (onFrame) => {
    mocks.progress.onFrame = onFrame;
    return { connected: mocks.progress.connected, error: null };
  },
}));

vi.mock('../api/inbound', () => ({
  fetchInboundBatch: mocks.fetchInboundBatch,
  fetchInboundTargets: mocks.fetchInboundTargets,
  fetchInboundTemplates: mocks.fetchInboundTemplates,
  fetchInboundRows: mocks.fetchInboundRows,
  fetchInboundTemplateExamples: mocks.fetchInboundTemplateExamples,
  downloadInboundTemplateExample: mocks.downloadInboundTemplateExample,
  saveInboundMapping: mocks.saveInboundMapping,
  saveInboundTemplate: mocks.saveInboundTemplate,
  commitInboundBatch: mocks.commitInboundBatch,
  fetchInboundCommitRun: mocks.fetchInboundCommitRun,
  fetchInboundCommitRuns: mocks.fetchInboundCommitRuns,
  downloadInboundRejects: mocks.downloadInboundRejects,
  smokeInboundBatch: mocks.smokeInboundBatch,
  uploadInboundFile: mocks.uploadInboundFile,
}));

vi.mock('../api/catalog', () => ({
  fetchReferenceSets: mocks.fetchReferenceSets,
}));

vi.mock('../components/FilteredDataGrid', () => ({
  default: ({ rows = [], columns = [], emptyMessage }) => (
    <div data-testid="grid">
      {rows.length === 0
        ? <div data-testid="grid-empty">{emptyMessage}</div>
        : rows.map((row, index) => (
          <div key={String(row.id ?? row.__i ?? index)} data-testid="grid-row">
            {columns.map((col) => {
              const value = col.valueGetter ? col.valueGetter(row[col.field], row) : row[col.field];
              const content = col.renderCell ? col.renderCell({ row, value }) : String(value ?? '');
              return <span key={col.field} data-testid={`cell-${col.field}`}>{content}</span>;
            })}
          </div>
        ))}
    </div>
  ),
}));

import ImportStudioPage from '../apps/people/ImportStudioPage';

const FIELDS = [
  { name: 'employee_no', label: 'Employee number', required: true },
  { name: 'full_name', label: 'Full name', required: true },
  { name: 'org_unit', label: 'Org unit code', required: true },
  { name: 'basic_salary', label: 'Basic salary', required: true },
];

const SMOKED_BATCH = {
  id: 7,
  kind: 'typed_object',
  target_key: 'people.employee_snapshot',
  target_label: 'Employee snapshot',
  status: 'smoked',
  original_filename: 'nibras-dms-dry.csv',
  encoding: 'utf-8',
  headers: ['employee_no', 'full_name', 'org_unit', 'basic_salary'],
  sample: [],
  row_count: 1,
  mapping: {
    columns: {
      employee_no: 'employee_no',
      full_name: 'full_name',
      org_unit: 'org_unit',
      basic_salary: 'basic_salary',
    },
    crosswalks: {},
  },
  smoke: { insert: 1, update: 0, skip: 0, reject: 0, sample: [], reject_rows: [], commit: {} },
  reject_count: 0,
  prepared_by_username: 'emp_2378',
  committed_by_username: null,
};

const DONE_RUN = {
  id: 55,
  batch: 7,
  target_key: 'people.employee_snapshot',
  status: 'done',
  progress: 100,
  log: [
    { t: '2026-10-03T14:00:00+00:00', message: 'Commit queued.', percent: 0 },
    { t: '2026-10-03T14:00:01+00:00', message: 'Committing row 1 of 1…', percent: 99 },
    { t: '2026-10-03T14:00:02+00:00', message: 'Committed 1 row(s).', percent: 100 },
  ],
  written: 1,
  reconcile: { employees: 1 },
  error: '',
  requested_by_username: 'emp_2400',
  prepared_by_username: 'emp_2378',
  committed_by_username: 'emp_2400',
};

function renderStudio() {
  return render(
    <MemoryRouter initialEntries={['/people/import/7']}>
      <Routes>
        <Route path="/people/import/:id" element={<ImportStudioPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

function footerButton(name) {
  const stepper = document.querySelector('.MuiStepper-root');
  return screen.getAllByRole('button', { name }).find((button) => !stepper.contains(button));
}

function stepNode(name) {
  return within(document.querySelector('.MuiStepper-root')).getByRole('button', { name });
}

/** Reach the Commit step, confirm, and wait for the commit request to be sent. */
async function openProgress(user) {
  await screen.findByText('nibras-dms-dry.csv');
  await user.click(stepNode('Commit'));
  await user.click(footerButton('Commit'));
  const confirm = await screen.findByRole('dialog');
  await user.click(within(confirm).getByRole('button', { name: 'Commit' }));
  await waitFor(() => expect(mocks.commitInboundBatch).toHaveBeenCalled());
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.progress.connected = true;
  mocks.progress.onFrame = null;
  mocks.fetchInboundBatch.mockResolvedValue(SMOKED_BATCH);
  mocks.fetchInboundTargets.mockResolvedValue([
    { key: 'people.employee_snapshot', label: 'Employee snapshot', fields: FIELDS },
  ]);
  mocks.fetchInboundTemplates.mockResolvedValue([]);
  mocks.fetchInboundRows.mockResolvedValue({
    results: [], headers: SMOKED_BATCH.headers, page: 1, page_size: 50, count: 0,
    max_page_size: 200, smoked: true,
  });
  mocks.fetchInboundTemplateExamples.mockResolvedValue([]);
  mocks.saveInboundMapping.mockResolvedValue(SMOKED_BATCH);
  mocks.fetchReferenceSets.mockResolvedValue([]);
  mocks.fetchInboundCommitRun.mockResolvedValue(DONE_RUN);
  mocks.fetchInboundCommitRuns.mockResolvedValue([]);
});

describe('People Import — ID2 commit progress', () => {
  it('closes the confirm dialog before the commit request is sent', async () => {
    const user = userEvent.setup();
    let resolveCommit;
    mocks.commitInboundBatch.mockImplementation(
      () => new Promise((resolve) => { resolveCommit = resolve; }),
    );
    renderStudio();
    await openProgress(user);

    // The request is in flight (never resolved): the confirm is gone and the
    // single progress surface is open.
    await waitFor(() => expect(screen.queryByText('Commit this batch?')).not.toBeInTheDocument());
    expect(screen.getByText('Committing batch')).toBeInTheDocument();
    await act(async () => { resolveCommit({ ...SMOKED_BATCH, status: 'committed', commit_run: DONE_RUN }); });
  });

  it('shows queued then running then done progress states', async () => {
    const user = userEvent.setup();
    let resolveCommit;
    mocks.commitInboundBatch.mockImplementation(
      () => new Promise((resolve) => { resolveCommit = resolve; }),
    );
    renderStudio();
    await openProgress(user);

    // queued
    expect(screen.getByText('Queued')).toBeInTheDocument();

    // running (determinate)
    act(() => {
      mocks.progress.onFrame({
        op_type: 'import', op_id: 55, status: 'running',
        message: 'Committing row 5 of 10…', percent: 40,
      });
    });
    expect(await screen.findByText('Committing the accepted rows')).toBeInTheDocument();
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '40');

    // done
    await act(async () => {
      resolveCommit({ ...SMOKED_BATCH, status: 'committed', commit_run: DONE_RUN });
    });
    expect(await screen.findByText('Commit complete')).toBeInTheDocument();
    expect(screen.getAllByText('100%').length).toBeGreaterThan(0);
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
  });

  it('appends batched log lines as progress arrives', async () => {
    const user = userEvent.setup();
    let resolveCommit;
    mocks.commitInboundBatch.mockImplementation(
      () => new Promise((resolve) => { resolveCommit = resolve; }),
    );
    renderStudio();
    await openProgress(user);

    act(() => {
      mocks.progress.onFrame({
        op_type: 'import', op_id: 55, status: 'running',
        message: 'Committing row 5 of 10…', percent: 40,
      });
      mocks.progress.onFrame({
        op_type: 'import', op_id: 55, status: 'running',
        message: 'Committing row 9 of 10…', percent: 90,
      });
    });

    expect(await screen.findByText('Progress log')).toBeInTheDocument();
    const log = within(screen.getByTestId('commit-log'));
    expect(log.getByText('Committing row 5 of 10…')).toBeInTheDocument();
    expect(log.getByText('Committing row 9 of 10…')).toBeInTheDocument();
    await act(async () => { resolveCommit({ ...SMOKED_BATCH, status: 'committed', commit_run: DONE_RUN }); });
  });

  it('shows an actionable error and an enabled Retry on failure; Retry re-calls the commit API', async () => {
    const user = userEvent.setup();
    const failedRun = { ...DONE_RUN, id: 56, status: 'failed', progress: 0, written: 0, reconcile: {}, error: 'host commit failed mid-loop' };
    const error = Object.assign(new Error('host commit failed mid-loop'), {
      data: { detail: 'host commit failed mid-loop', commit_run: failedRun },
    });
    mocks.commitInboundBatch
      .mockRejectedValueOnce(error)
      .mockResolvedValueOnce({ ...SMOKED_BATCH, status: 'committed', commit_run: DONE_RUN });

    renderStudio();
    await openProgress(user);

    expect((await screen.findAllByText('host commit failed mid-loop')).length).toBeGreaterThan(0);
    const retry = screen.getByRole('button', { name: 'Retry' });
    expect(retry).toBeEnabled();

    await user.click(retry);
    await waitFor(() => expect(mocks.commitInboundBatch).toHaveBeenCalledTimes(2));
    expect(await screen.findByText('Commit complete')).toBeInTheDocument();
  });

  it('renders exactly one dialog and the SoD line', async () => {
    const user = userEvent.setup();
    let resolveCommit;
    mocks.commitInboundBatch.mockImplementation(
      () => new Promise((resolve) => { resolveCommit = resolve; }),
    );
    renderStudio();
    await openProgress(user);

    // The confirm has closed; only the single progress surface remains.
    await waitFor(() => expect(document.querySelectorAll('.MuiDialog-root')).toHaveLength(1));
    expect(screen.getByText('Committing as emp_2400')).toBeInTheDocument();
    expect(screen.getByText(/Prepared by emp_2378 · committed by emp_2400/)).toBeInTheDocument();
    // No cancel control for an inline atomic commit.
    expect(screen.queryByRole('button', { name: 'Cancel' })).not.toBeInTheDocument();
    await act(async () => { resolveCommit({ ...SMOKED_BATCH, status: 'committed', commit_run: DONE_RUN }); });
  });
});
