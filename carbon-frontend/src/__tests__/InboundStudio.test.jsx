import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
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
  downloadInboundRejects: vi.fn(),
  smokeInboundBatch: vi.fn(),
  uploadInboundFile: vi.fn(),
  fetchReferenceSets: vi.fn(),
}));

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({
    token: 't',
    isGlobalAdminFlag: false,
    user: { username: 'emp_2400' },
    // inbound:commit expands to inbound:prepare (capabilities.js).
    userCapabilities: ['inbound:commit'],
  }),
}));

// Stable notify/notifyFromError: an inline `vi.fn()` here changes identity
// every render, re-firing the studio's `load` useCallback in an infinite loop.
vi.mock('../components/NotificationProvider', () => ({
  useNotification: () => ({ notify: mocks.notify, notifyFromError: mocks.notifyFromError }),
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
  downloadInboundRejects: mocks.downloadInboundRejects,
  smokeInboundBatch: mocks.smokeInboundBatch,
  uploadInboundFile: mocks.uploadInboundFile,
}));

vi.mock('../api/catalog', () => ({
  fetchReferenceSets: mocks.fetchReferenceSets,
}));

import ImportStudioPage from '../apps/people/ImportStudioPage';

const FIELDS = [
  { name: 'employee_no', label: 'Employee number', required: true },
  { name: 'full_name', label: 'Full name', required: true },
  { name: 'org_unit', label: 'Org unit code', required: true },
  { name: 'basic_salary', label: 'Basic salary', required: true },
];

const COMMITTED_BATCH = {
  id: 7,
  kind: 'typed_object',
  target_key: 'people.employee_snapshot',
  target_label: 'Employee snapshot',
  status: 'committed',
  original_filename: 'nibras-dms-dry.csv',
  encoding: 'utf-8',
  headers: ['employee_no', 'full_name', 'org_unit', 'basic_salary'],
  sample: [{
    employee_no: 'DMSDEV9001',
    full_name: 'DMS Dev Dry Run',
    org_unit: 'coiled-tubing',
    basic_salary: '100.000',
  }],
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
  smoke: {
    insert: 1,
    update: 0,
    skip: 0,
    reject: 0,
    sample: [{ row: 1, key: 'DMSDEV9001', verdict: 'insert', reason: '' }],
    reject_rows: [],
    commit: { written: 1, reconcile: { employees: 1 } },
  },
  reject_count: 0,
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

describe('People Import studio — committed batch', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.fetchInboundBatch.mockResolvedValue(COMMITTED_BATCH);
    mocks.fetchInboundTargets.mockResolvedValue([
      { key: 'people.employee_snapshot', label: 'Employee snapshot', fields: FIELDS },
    ]);
    mocks.fetchInboundTemplates.mockResolvedValue([]);
    mocks.fetchInboundRows.mockResolvedValue({
      results: [{
        row: 1,
        key: 'DMSDEV9001',
        verdict: 'insert',
        reason: '',
        values: {
          employee_no: 'DMSDEV9001',
          full_name: 'DMS Dev Dry Run',
          org_unit: 'coiled-tubing',
          basic_salary: '100.000',
        },
      }],
      headers: ['employee_no', 'full_name', 'org_unit', 'basic_salary'],
      page: 1,
      page_size: 50,
      count: 1,
      max_page_size: 200,
    });
    mocks.fetchInboundTemplateExamples.mockResolvedValue([]);
    mocks.saveInboundMapping.mockResolvedValue(COMMITTED_BATCH);
    mocks.fetchReferenceSets.mockResolvedValue([]);
  });

  it('does not block a committed batch on the Smoke step with a false smoke error', async () => {
    const user = userEvent.setup();
    renderStudio();

    // The read-only viewer receives the committed batch's rows from the endpoint.
    expect(await screen.findByText('1 rows in this file')).toBeInTheDocument();
    // Committed batches reopen read-only with an explicit note.
    expect(screen.getByText(/this batch is committed/i)).toBeInTheDocument();

    // Smoke step is current (startStep 2). Advancing must not show the false error.
    await user.click(screen.getByRole('button', { name: 'Next' }));

    expect(screen.queryByText('Run smoke before continuing')).not.toBeInTheDocument();
    // The wizard reached the Commit step summary.
    await waitFor(() => {
      expect(screen.getByText(/Employee snapshot: 1 insert, 0 update, 0 reject/i)).toBeInTheDocument();
    });
  });

  it('still blocks a mapped-but-unsmoked batch on the Smoke step', async () => {
    const user = userEvent.setup();
    mocks.fetchInboundBatch.mockResolvedValue({
      ...COMMITTED_BATCH, id: 8, status: 'mapped', smoke: {},
    });
    renderStudio();

    await screen.findByText('nibras-dms-dry.csv');
    // startStep is Map (1) for a mapped batch: advance to Smoke, then try Next.
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(screen.getByRole('button', { name: 'Next' }));

    expect(await screen.findByText('Run smoke before continuing')).toBeInTheDocument();
  });
});
