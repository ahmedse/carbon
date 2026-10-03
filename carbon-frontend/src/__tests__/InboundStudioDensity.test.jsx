// Item 1 (Import audit): the embedded Studio grids — Upload sample, Map, and
// Reconcile — must render with compact density. We assert the MUI DataGrid root
// class so the check is end-to-end through FilteredDataGrid → StandardDataGrid
// → DataGrid, not a prop that could be dropped in between.
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
    userCapabilities: ['inbound:commit'],
  }),
}));

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

vi.mock('../api/catalog', () => ({ fetchReferenceSets: mocks.fetchReferenceSets }));

vi.mock('../components/inbound/InboundExampleTemplates', () => ({ default: () => null }));

import ImportStudioPage from '../apps/people/ImportStudioPage';

const FIELDS = [
  { name: 'employee_no', label: 'Employee number', required: true },
  { name: 'full_name', label: 'Full name', required: true },
  { name: 'org_unit', label: 'Org unit code', required: true },
  { name: 'basic_salary', label: 'Basic salary', required: true },
];

const HEADERS = ['employee_no', 'full_name', 'org_unit', 'basic_salary'];

const COMMITTED_BATCH = {
  id: 7,
  kind: 'typed_object',
  target_key: 'people.employee_snapshot',
  target_label: 'Employee snapshot',
  status: 'committed',
  original_filename: 'nibras-dms-dry.csv',
  encoding: 'utf-8',
  headers: HEADERS,
  sample: [{ employee_no: 'DMSDEV9001', full_name: 'DMS Dev Dry Run', org_unit: 'coiled-tubing', basic_salary: '100.000' }],
  row_count: 1,
  mapping: { columns: {}, crosswalks: {} },
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

// Every DataGrid currently mounted must be compact.
function everyGridIsCompact() {
  const grids = Array.from(document.querySelectorAll('.MuiDataGrid-root'));
  return grids.length > 0
    && grids.every((node) => node.classList.contains('MuiDataGrid-root--densityCompact'));
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.fetchInboundTargets.mockResolvedValue([
    { key: 'people.employee_snapshot', label: 'Employee snapshot', fields: FIELDS },
  ]);
  mocks.fetchInboundTemplates.mockResolvedValue([]);
  mocks.fetchInboundRows.mockResolvedValue({
    results: [],
    headers: HEADERS,
    page: 1,
    page_size: 50,
    count: 0,
    max_page_size: 200,
    smoked: true,
  });
  mocks.fetchInboundTemplateExamples.mockResolvedValue([]);
  mocks.saveInboundMapping.mockResolvedValue(COMMITTED_BATCH);
  mocks.fetchReferenceSets.mockResolvedValue([]);
});

describe('People Import studio — embedded grids use compact density', () => {
  it('renders the Upload sample grid and the Map grid with compact density', async () => {
    mocks.fetchInboundBatch.mockResolvedValue({
      ...COMMITTED_BATCH, id: 9, status: 'draft', mapping: {}, smoke: {},
    });
    const user = userEvent.setup();
    renderStudio();

    // Upload step: the ≤20 sample grid renders compact.
    await waitFor(() => expect(everyGridIsCompact()).toBe(true));

    // Advance to Map: the header→field mapping grid is compact too.
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await waitFor(() => expect(everyGridIsCompact()).toBe(true));
  });

  it('renders the Reconcile grid on the Commit step with compact density', async () => {
    mocks.fetchInboundBatch.mockResolvedValue(COMMITTED_BATCH);
    const user = userEvent.setup();
    renderStudio();

    await screen.findByText('nibras-dms-dry.csv');
    // Committed batches start on Smoke (step 2); advancing reaches Commit.
    await user.click(screen.getByRole('button', { name: 'Next' }));

    await waitFor(() => {
      expect(screen.getByText(/Employee snapshot: 1 insert, 0 update, 0 reject/i)).toBeInTheDocument();
    });
    expect(everyGridIsCompact()).toBe(true);
  });
});
