// NSR-2B — ledger-first Pay tab: reflected basic is read-only; payroll SoT copy.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';

vi.mock('../api/people', () => ({
  fetchCompensationLedger: vi.fn(),
  fetchCompensationComponents: vi.fn(),
  createCompensationLine: vi.fn(),
  fetchPayrollRuns: vi.fn(),
  fetchPayslipLines: vi.fn(),
}));

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({
    isGlobalAdminFlag: true,
    userCapabilities: ['people:manage', 'people:view_compensation'],
  }),
}));

vi.mock('../components/NotificationProvider', () => ({
  useNotification: () => ({
    notify: vi.fn(),
    notifyFromError: vi.fn(),
    showFeedback: vi.fn(),
  }),
}));

import {
  fetchCompensationLedger,
  fetchPayrollRuns,
  fetchPayslipLines,
} from '../api/people';
import EmployeePayTab from '../apps/people/tabs/EmployeePayTab';

beforeEach(() => {
  vi.clearAllMocks();
  fetchPayrollRuns.mockResolvedValue({ results: [] });
  fetchPayslipLines.mockResolvedValue({ results: [] });
});

describe('EmployeePayTab (NSR-2B ledger SoT)', () => {
  it('shows disabled reflected-basic field and ledger-first messaging', async () => {
    fetchCompensationLedger.mockResolvedValue({
      employee_id: 42,
      as_of: '2026-09-16',
      basic_salary: '850.000',
      totals: {
        monthly_earnings: '850.000',
        monthly_deductions: '0',
        net_monthly: '850.000',
      },
      current: [
        {
          id: 1,
          component_name: 'Basic',
          component_code: 'basic',
          component_direction: 'earning',
          amount: '850.000',
          currency: 'KWD',
          frequency: 'monthly',
          effective_start: '2026-01-01',
          effective_end: null,
          is_verified: true,
        },
      ],
      history: [],
    });

    render(
      <EmployeePayTab
        entityData={{ id: 42, empId: 42 }}
        additionalProps={{ token: 'test-token' }}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId('comp-reflected-basic')).toBeInTheDocument();
    });

    const reflected = screen.getByLabelText(/Reflected basic \(ledger\)/i);
    expect(reflected).toBeDisabled();
    expect(reflected).toHaveAttribute('readonly');
    expect(screen.getByText(/Payroll uses verified compensation ledger lines only/i)).toBeInTheDocument();
    expect(screen.getByText(/Change pay via Add Component/i)).toBeInTheDocument();
  });

  it('shows empty-basic copy when ledger has no reflected basic', async () => {
    fetchCompensationLedger.mockResolvedValue({
      employee_id: 7,
      as_of: '2026-09-16',
      basic_salary: null,
      totals: { monthly_earnings: '0', monthly_deductions: '0', net_monthly: '0' },
      current: [],
      history: [],
    });

    render(
      <EmployeePayTab
        entityData={{ id: 7 }}
        additionalProps={{ token: 'test-token' }}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId('comp-reflected-basic')).toBeInTheDocument();
    });

    expect(screen.getByDisplayValue(/No verified basic line yet/i)).toBeInTheDocument();
    expect(screen.getByText(/Payroll uses verified compensation ledger lines only/i)).toBeInTheDocument();
  });
});
