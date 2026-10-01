// Host screens for the payroll policy. Evidence is this component test, not a browser session.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token', user: { username: 'reviewer' } }),
}));

vi.mock('../hooks/useReferenceOptions', () => ({
  useReferenceOptions: () => ({
    options: [{ value: 'other', label: 'Other' }],
    loading: false,
    error: null,
    refetch: vi.fn(),
  }),
}));

vi.mock('../api/orgUnits', () => ({
  fetchOrgUnits: vi.fn(async () => []),
  orgUnitDepth: () => 0,
  orgUnitOptionLabel: (unit) => unit?.name || '',
  prepareOrgUnitsForPicker: (rows) => rows || [],
}));

const rules = [
  { id: 1, rule_id: 'tenant-draft', version: '2026.9', name: 'Draft rule', category: 'other', effective_date: '2026-08-01', lifecycle: 'draft' },
  { id: 2, rule_id: 'tenant-review', version: '2026.9', name: 'Review rule', category: 'other', effective_date: '2026-08-01', lifecycle: 'in_review' },
  { id: 3, rule_id: 'tenant-live', version: '2026.9', name: 'Live rule', category: 'other', effective_date: '2026-08-01', lifecycle: 'authoritative' },
  { id: 4, rule_id: 'tenant-old', version: '2026.8', name: 'Old rule', category: 'other', effective_date: '2026-01-01', lifecycle: 'superseded' },
];

vi.mock('../api/people', () => ({
  fetchComplianceRules: vi.fn(async () => ({ results: rules })),
  createComplianceRule: vi.fn(),
  updateComplianceRule: vi.fn(),
  deleteComplianceRule: vi.fn(),
  copyForwardComplianceRule: vi.fn(),
  submitComplianceRule: vi.fn(async () => ({})),
  previewComplianceRule: vi.fn(async () => ({
    examples: { passed: true },
    floors: { passed: true },
    citation: true,
    active_employees: 0,
  })),
  fetchPayrollRuns: vi.fn(async () => ({ results: [] })),
  fetchPayrollRunValidations: vi.fn(async () => ({ results: [] })),
  createPayrollRun: vi.fn(),
  updatePayrollRun: vi.fn(),
  deletePayrollRun: vi.fn(),
  computePayrollRun: vi.fn(),
  validatePayrollRun: vi.fn(),
  commitPayrollRun: vi.fn(),
  exportWpsPayrollRun: vi.fn(),
  openRetroPayrollRun: vi.fn(),
  fetchPayslipLines: vi.fn(async () => ({ results: [] })),
}));

import * as peopleApi from '../api/people';
import ComplianceRulesPanel from '../apps/people/ComplianceRulesPanel';
import PayrollRunsPage from '../apps/people/PayrollRunsPage';
import PayslipPage from '../apps/people/PayslipPage';

function renderRules() {
  return render(
    <MemoryRouter>
      <ComplianceRulesPanel />
    </MemoryRouter>,
  );
}

describe('payroll policy host surfaces', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    peopleApi.fetchComplianceRules.mockResolvedValue({ results: rules });
  });

  it('shows the four lifecycle states and submits a draft', async () => {
    const user = userEvent.setup();
    renderRules();
    expect(document.querySelector('.MuiSkeleton-root')).toBeTruthy();
    await screen.findByText('tenant-draft');
    expect(screen.getByText('Draft')).toBeInTheDocument();
    expect(screen.getByText('In review')).toBeInTheDocument();
    expect(screen.getByText('Authoritative')).toBeInTheDocument();
    expect(screen.getByText('Superseded')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Submit' }));
    await waitFor(() => {
      expect(peopleApi.submitComplianceRule).toHaveBeenCalledWith(1, 'test-token');
    });
  });

  it('has no publish button and points in-review rows at the policy desk', async () => {
    renderRules();
    await screen.findByText('tenant-review');
    expect(screen.queryByRole('button', { name: 'Publish' })).not.toBeInTheDocument();
    expect(screen.getByText('Publish is on the policy desk.')).toBeInTheDocument();
    const link = screen.getByRole('link', { name: 'Open the policy desk' });
    expect(link).toHaveAttribute('href', '/catalog/policy-versions?focus=2');
  });

  it('highlights a compliance row without opening a dialog', async () => {
    const user = userEvent.setup();
    renderRules();
    const label = await screen.findByText('tenant-live');
    await user.click(label);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(label.closest('.MuiDataGrid-row')).toHaveClass('highlighted-row');
  });

  it('renders an empty compliance list and a load error', async () => {
    peopleApi.fetchComplianceRules.mockResolvedValue({ results: [] });
    const { unmount } = renderRules();
    expect(await screen.findByText('No compliance rules')).toBeInTheDocument();
    unmount();
    peopleApi.fetchComplianceRules.mockRejectedValue(new Error('Could not load app configuration'));
    renderRules();
    expect(await screen.findByText('Could not load app configuration')).toBeInTheDocument();
  });

  it('shows a payslip regulation version and highlights the row only', async () => {
    const user = userEvent.setup();
    peopleApi.fetchPayrollRuns.mockResolvedValue({
      results: [{ id: 9, period_start: '2026-08-01', period_end: '2026-08-31', status: 'committed' }],
    });
    peopleApi.fetchPayslipLines.mockResolvedValue({
      results: [{
        id: 41,
        employee_no: 'E-DIRECT',
        employee_name: 'Direct',
        line_type: { code: 'leave_pay', label: 'Leave pay' },
        amount: '115.385',
        rule_id: 'sheet-leave',
        rule_version: '2026.2',
        inputs: { regulation_version: '2010.1', regulation_pack: 'kw' },
      }],
    });
    render(<PayslipPage />);
    expect(await screen.findByText('Regulation version')).toBeInTheDocument();
    expect(screen.getByText('2010.1')).toBeInTheDocument();
    expect(screen.getByText('115.385')).toBeInTheDocument();
    const label = screen.getByText(/E-DIRECT/);
    await user.click(label);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(label.closest('.MuiDataGrid-row')).toHaveClass('highlighted-row');
  });

  it('opens a retro dialog from a committed payroll run', async () => {
    const user = userEvent.setup();
    peopleApi.fetchPayrollRuns.mockResolvedValue({
      results: [{
        id: 9,
        org_unit: 1,
        period_start: '2026-08-01',
        period_end: '2026-08-31',
        status: 'committed',
        kind: 'regular',
        preparer_username: 'maker',
      }],
    });
    render(<PayrollRunsPage />);
    await user.click(await screen.findByRole('button', { name: 'Open retro' }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText('Open a retro run')).toBeInTheDocument();
    expect(screen.getByText('Committed')).toBeInTheDocument();
  });
});
