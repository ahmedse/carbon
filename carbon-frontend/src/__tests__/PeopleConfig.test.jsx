// src/__tests__/PeopleConfig.test.jsx
// NSR-5B — People Config thick: tabs, compliance CRUD helpers, compensation create helpers.

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token', isGlobalAdminFlag: true }),
}));

vi.mock('../api/people', () => ({
  fetchComplianceRules: vi.fn().mockResolvedValue({
    count: 1,
    results: [{
      id: 1,
      rule_id: 'kw-gosi',
      version: '2026.1',
      name: 'GOSI KW',
      jurisdiction: 'KW',
      category: 'gosi',
      effective_date: '2026-01-01',
      is_authoritative: true,
      inputs_schema: {},
    }],
  }),
  createComplianceRule: vi.fn().mockResolvedValue({ id: 2 }),
  updateComplianceRule: vi.fn().mockResolvedValue({ id: 1 }),
  deleteComplianceRule: vi.fn().mockResolvedValue(undefined),
  fetchCompensationComponents: vi.fn().mockResolvedValue([
    { id: 10, code: 'basic', name: 'Basic Salary', direction: 'earning', category: 'base', is_eosi_base: true, is_gosi_base: true, sort_order: 10 },
  ]),
  createCompensationComponent: vi.fn().mockResolvedValue({ id: 11 }),
  fetchCompensationPlan: vi.fn().mockResolvedValue([
    {
      id: 20,
      pay_grade_code: 'G5',
      job_family_code: 'ops',
      component: 10,
      component_code: 'basic',
      amount: '500.000',
      currency: 'KWD',
      frequency: 'monthly',
      effective_start: '2026-01-01',
      effective_end: null,
    },
  ]),
  createCompensationPlan: vi.fn().mockResolvedValue({ id: 21 }),
  fetchBenefitTypes: vi.fn().mockResolvedValue([]),
  createBenefitType: vi.fn(),
  updateBenefitType: vi.fn(),
  deleteBenefitType: vi.fn(),
}));

import * as peopleApi from '../api/people';
import PeopleConfigPage from '../apps/people/PeopleConfigPage';

describe('PeopleConfig (NSR-5B)', () => {
  beforeEach(() => {
    localStorage.removeItem('carbon-people-config-tab');
    vi.clearAllMocks();
  });

  it('exports compliance and compensation write helpers', () => {
    for (const name of [
      'fetchComplianceRules',
      'createComplianceRule',
      'updateComplianceRule',
      'deleteComplianceRule',
      'fetchCompensationComponents',
      'createCompensationComponent',
      'fetchCompensationPlan',
      'createCompensationPlan',
    ]) {
      expect(typeof peopleApi[name]).toBe('function');
    }
  });

  it('renders Overview, Reference, Compliance, and Compensation tabs', () => {
    render(<PeopleConfigPage />);
    expect(screen.getByRole('tab', { name: 'Overview' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Reference Data' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Compliance Rules' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Compensation' })).toBeInTheDocument();
  });

  it('loads compliance rules when Compliance tab is selected', async () => {
    const user = userEvent.setup();
    render(<PeopleConfigPage />);

    await user.click(screen.getByRole('tab', { name: 'Compliance Rules' }));

    await waitFor(() => {
      expect(peopleApi.fetchComplianceRules).toHaveBeenCalledWith('test-token');
    });
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Add rule' })).toBeInTheDocument();
    });
  });

  it('opens create dialog and posts a compliance rule', async () => {
    const user = userEvent.setup();
    render(<PeopleConfigPage />);
    await user.click(screen.getByRole('tab', { name: 'Compliance Rules' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Add rule' })).toBeInTheDocument());

    await user.click(screen.getByRole('button', { name: 'Add rule' }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText('Add Compliance Rule')).toBeInTheDocument();

    await user.type(within(dialog).getByRole('textbox', { name: /Rule ID/i }), 'kw-test');
    await user.type(within(dialog).getByRole('textbox', { name: /Version/i }), '2026.1');
    await user.type(within(dialog).getByRole('textbox', { name: /^Name/i }), 'Test Rule');
    const dateField = within(dialog).getByLabelText(/Effective Date/i);
    await user.clear(dateField);
    await user.type(dateField, '2026-01-01');

    await user.click(within(dialog).getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      expect(peopleApi.createComplianceRule).toHaveBeenCalled();
    });
    const payload = peopleApi.createComplianceRule.mock.calls[0][0];
    expect(payload.rule_id).toBe('kw-test');
    expect(payload.version).toBe('2026.1');
    expect(payload.name).toBe('Test Rule');
    expect(payload.effective_date).toBe('2026-01-01');
  });

  it('loads compensation components and plans on Compensation tab', async () => {
    const user = userEvent.setup();
    render(<PeopleConfigPage />);
    await user.click(screen.getByRole('tab', { name: 'Compensation' }));

    await waitFor(() => {
      expect(peopleApi.fetchCompensationComponents).toHaveBeenCalledWith('test-token');
      expect(peopleApi.fetchCompensationPlan).toHaveBeenCalledWith('test-token');
    });
    await waitFor(() => {
      expect(screen.getByText('Compensation Components')).toBeInTheDocument();
      expect(screen.getByText('Compensation Plan')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Add component' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Add plan row' })).toBeInTheDocument();
    });
  });

  it('creates a compensation component via SystemDialog', async () => {
    const user = userEvent.setup();
    render(<PeopleConfigPage />);
    await user.click(screen.getByRole('tab', { name: 'Compensation' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Add component' })).toBeInTheDocument());

    await user.click(screen.getByRole('button', { name: 'Add component' }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText('Add Compensation Component')).toBeInTheDocument();

    await user.type(within(dialog).getByRole('textbox', { name: /Code/i }), 'housing');
    await user.type(within(dialog).getByRole('textbox', { name: /^Name/i }), 'Housing');
    await user.click(within(dialog).getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      expect(peopleApi.createCompensationComponent).toHaveBeenCalled();
    });
    const payload = peopleApi.createCompensationComponent.mock.calls[0][0];
    expect(payload.code).toBe('housing');
    expect(payload.name).toBe('Housing');
    expect(payload.direction).toBe('earning');
  });
});
