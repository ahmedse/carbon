import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within, fireEvent } from '@testing-library/react';
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

// The shared grid virtualizes by viewport, which jsdom measures as 0. Stand in
// for it and still call each column's valueGetter/renderCell so the Map pickers
// and the reconcile/sample cells render and expose their disabled state.
vi.mock('../components/FilteredDataGrid', () => ({
  default: ({ rows = [], columns = [], emptyMessage, dataGridProps }) => (
    <div data-testid="grid" data-density={dataGridProps?.density || ''}>
      {rows.length === 0
        ? <div data-testid="grid-empty">{emptyMessage}</div>
        : rows.map((row, index) => (
          <div key={String(row.id ?? row.__i ?? row.__row ?? index)} data-testid="grid-row">
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
        issues: [],
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
      smoked: true,
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

describe('People Import studio — a view open must not write (Defect 11)', () => {
  const DRAFT_NO_MAPPING = {
    ...COMMITTED_BATCH,
    id: 9,
    status: 'draft',
    mapping: {},
    smoke: {},
    prepared_by_username: 'emp_2378',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mocks.fetchInboundTargets.mockResolvedValue([
      { key: 'people.employee_snapshot', label: 'Employee snapshot', fields: FIELDS },
    ]);
    mocks.fetchInboundTemplates.mockResolvedValue([]);
    mocks.fetchInboundRows.mockResolvedValue({
      results: [], headers: COMMITTED_BATCH.headers, page: 1, page_size: 50, count: 0,
    });
    mocks.fetchInboundTemplateExamples.mockResolvedValue([]);
    mocks.saveInboundMapping.mockResolvedValue(COMMITTED_BATCH);
    mocks.fetchReferenceSets.mockResolvedValue([]);
  });

  it('does not PUT a mapping when a non-owner opens an un-mapped draft', async () => {
    // Auth user is emp_2400; the batch was prepared by emp_2378.
    mocks.fetchInboundBatch.mockResolvedValue(DRAFT_NO_MAPPING);
    renderStudio();

    // Templates fetch is the last step of load(); if no PUT happened by then,
    // opening the batch wrote nothing.
    await waitFor(() => expect(mocks.fetchInboundTemplates).toHaveBeenCalled());
    expect(mocks.saveInboundMapping).not.toHaveBeenCalled();
  });

  it('persists the suggested mapping only for the preparer who owns the batch', async () => {
    mocks.fetchInboundBatch.mockResolvedValue({
      ...DRAFT_NO_MAPPING, id: 10, prepared_by_username: 'emp_2400',
    });
    renderStudio();

    await waitFor(() => expect(mocks.saveInboundMapping).toHaveBeenCalledTimes(1));
    expect(mocks.saveInboundMapping).toHaveBeenCalledWith('t', 10, expect.objectContaining({
      columns: expect.objectContaining({ employee_no: 'employee_no' }),
    }));
  });
});

describe('People Import studio — clickable step nodes', () => {
  function smokedBatch(overrides = {}) {
    return {
      ...COMMITTED_BATCH,
      id: 21,
      status: 'smoked',
      smoke: {
        insert: 5, update: 2, skip: 0, reject: 3,
        sample: [], reject_rows: [], commit: {},
      },
      reject_count: 3,
      committed_by_username: null,
      ...overrides,
    };
  }

  // The Stepper node ("Map") and the footer finish button can share a label
  // ("Commit"), so scope node lookups to the Stepper.
  function stepNode(name) {
    return within(document.querySelector('.MuiStepper-root')).getByRole('button', { name });
  }
  function footerButton(name) {
    const stepper = document.querySelector('.MuiStepper-root');
    return screen.getAllByRole('button', { name }).find((b) => !stepper.contains(b));
  }
  function firstMappingPicker() {
    return within(screen.getAllByTestId('cell-target')[0]).getByRole('combobox');
  }
  function statValue(label) {
    return screen.getByText(label).parentElement.textContent.replace(label, '');
  }

  beforeEach(() => {
    vi.clearAllMocks();
    mocks.fetchInboundTargets.mockResolvedValue([
      { key: 'people.employee_snapshot', label: 'Employee snapshot', fields: FIELDS },
    ]);
    mocks.fetchInboundTemplates.mockResolvedValue([]);
    mocks.fetchInboundRows.mockResolvedValue({
      results: [], headers: COMMITTED_BATCH.headers, page: 1, page_size: 50, count: 0,
      max_page_size: 200, smoked: true,
    });
    mocks.fetchInboundTemplateExamples.mockResolvedValue([]);
    mocks.saveInboundMapping.mockResolvedValue(COMMITTED_BATCH);
    mocks.fetchReferenceSets.mockResolvedValue([]);
  });

  it('clicking the Upload node on a smoked batch shows Upload with an enabled file control', async () => {
    const user = userEvent.setup();
    mocks.fetchInboundBatch.mockResolvedValue(smokedBatch());
    renderStudio();

    // Starts on Smoke (startStep 2).
    expect(await screen.findByText('nibras-dms-dry.csv')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Choose CSV' })).not.toBeInTheDocument();

    const uploadNode = stepNode('Upload');
    expect(uploadNode).toBeEnabled();
    await user.click(uploadNode);

    // The Upload step is shown and the file change control is live again.
    expect(screen.getByRole('button', { name: 'Choose CSV' })).toBeEnabled();
  });

  it('clicking the Map node on a smoked batch re-enables the mapping pickers', async () => {
    const user = userEvent.setup();
    mocks.fetchInboundBatch.mockResolvedValue(smokedBatch());
    renderStudio();
    await screen.findByText('nibras-dms-dry.csv');

    await user.click(stepNode('Map'));

    // One picker per CSV header, editable because the batch is not committed.
    const pickers = screen.getAllByTestId('cell-target').map(
      (cell) => within(cell).getByRole('combobox'),
    );
    expect(pickers).toHaveLength(FIELDS.length);
    pickers.forEach((picker) => expect(picker).toBeEnabled());
    expect(firstMappingPicker()).toBeEnabled();
  });

  it('disables the Commit node on a mapped batch and does not jump to the summary', async () => {
    mocks.fetchInboundBatch.mockResolvedValue({ ...smokedBatch(), status: 'mapped', smoke: {} });
    renderStudio();
    await screen.findByText('nibras-dms-dry.csv');

    const commitNode = stepNode('Commit');
    expect(commitNode).toBeDisabled();
    // A disabled node cannot be activated; fireEvent bypasses pointer-events so
    // we can prove the click is swallowed rather than relying on a throw.
    fireEvent.click(commitNode);

    // No forward jump past the smoke guard: the commit summary never renders.
    expect(screen.queryByText(/Employee snapshot: .* insert/i)).not.toBeInTheDocument();
  });

  it('keeps a committed batch view-only across node clicks', async () => {
    const user = userEvent.setup();
    mocks.fetchInboundBatch.mockResolvedValue(COMMITTED_BATCH);
    renderStudio();

    // Committed note on the Smoke step; no Run-smoke button.
    expect(await screen.findByText(/this batch is committed/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Run smoke' })).not.toBeInTheDocument();

    await user.click(stepNode('Upload'));
    expect(screen.getByRole('button', { name: 'Choose CSV' })).toBeDisabled();

    await user.click(stepNode('Map'));
    expect(firstMappingPicker()).toBeDisabled();

    // Back on Smoke the committed note is still shown; Finish stays disabled.
    await user.click(stepNode('Smoke'));
    expect(screen.getByText(/this batch is committed/i)).toBeInTheDocument();

    await user.click(stepNode('Commit'));
    expect(footerButton('Commit')).toBeDisabled();
  });

  it('changing the mapping on a smoked batch resets the smoke stats and the allow-partial consent', async () => {
    const user = userEvent.setup();
    mocks.fetchInboundBatch.mockResolvedValue(smokedBatch());
    // A re-map clears smoke and drops the status back to mapped on the server.
    mocks.saveInboundMapping.mockResolvedValue({
      ...smokedBatch(), status: 'mapped', smoke: {}, reject_count: 0,
    });
    renderStudio();
    await screen.findByText('nibras-dms-dry.csv');

    // Give commit consent first, on the commit step.
    await user.click(stepNode('Commit'));
    const consent = await screen.findByRole('checkbox', { name: /commit accepted rows/i });
    await user.click(consent);
    expect(consent).toBeChecked();

    // Edit the mapping: the server returns a mapped batch with smoke cleared.
    await user.click(stepNode('Map'));
    await user.click(firstMappingPicker());
    await user.click(await screen.findByRole('option', { name: 'Skip' }));

    await waitFor(() => expect(mocks.saveInboundMapping).toHaveBeenCalledTimes(1));

    // The smoke stat row is reset from the fresh (smoke-less) batch.
    await user.click(stepNode('Smoke'));
    expect(statValue('Insert')).toBe('0');
    expect(statValue('Reject')).toBe('0');

    // Consent was dropped, not merely hidden: re-smoke and re-open Commit.
    mocks.smokeInboundBatch.mockResolvedValue(smokedBatch());
    await user.click(screen.getByRole('button', { name: 'Run smoke' }));
    await user.click(stepNode('Commit'));
    expect(await screen.findByRole('checkbox', { name: /commit accepted rows/i })).not.toBeChecked();
  });

  it('re-uploading on a smoked batch resets the smoke stats and the allow-partial consent', async () => {
    const user = userEvent.setup();
    mocks.fetchInboundBatch.mockResolvedValue(smokedBatch());
    // New file -> draft with smoke cleared, then the suggested map persists -> mapped.
    mocks.uploadInboundFile.mockResolvedValue({
      ...smokedBatch(), status: 'draft', smoke: {}, reject_count: 0,
    });
    mocks.saveInboundMapping.mockResolvedValue({
      ...smokedBatch(), status: 'mapped', smoke: {}, reject_count: 0,
    });
    renderStudio();
    await screen.findByText('nibras-dms-dry.csv');

    await user.click(stepNode('Commit'));
    const consent = await screen.findByRole('checkbox', { name: /commit accepted rows/i });
    await user.click(consent);
    expect(consent).toBeChecked();

    await user.click(stepNode('Upload'));
    const input = document.querySelector('input[type="file"]');
    await user.upload(input, new File(['employee_no\nE1'], 'next.csv', { type: 'text/csv' }));
    await waitFor(() => expect(mocks.uploadInboundFile).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(mocks.saveInboundMapping).toHaveBeenCalledTimes(1));

    await user.click(stepNode('Smoke'));
    expect(statValue('Insert')).toBe('0');
    expect(statValue('Reject')).toBe('0');

    mocks.smokeInboundBatch.mockResolvedValue(smokedBatch());
    await user.click(screen.getByRole('button', { name: 'Run smoke' }));
    await user.click(stepNode('Commit'));
    expect(await screen.findByRole('checkbox', { name: /commit accepted rows/i })).not.toBeChecked();
  });

  it('activates a reachable step node with Enter and Space (StepButton a11y)', async () => {
    const user = userEvent.setup();
    mocks.fetchInboundBatch.mockResolvedValue(smokedBatch());
    renderStudio();
    await screen.findByText('nibras-dms-dry.csv');

    const mapNode = stepNode('Map');
    expect(mapNode.tagName).toBe('BUTTON');
    mapNode.focus();
    await user.keyboard('{Enter}');
    // The Map step is now rendered (its mapping grid is present).
    expect(await screen.findAllByTestId('cell-target')).not.toHaveLength(0);

    const smokeNode = stepNode('Smoke');
    smokeNode.focus();
    await user.keyboard(' ');
    // The Smoke step is now rendered (its Run-smoke action is present).
    expect(await screen.findByRole('button', { name: 'Run smoke' })).toBeInTheDocument();
  });
});
