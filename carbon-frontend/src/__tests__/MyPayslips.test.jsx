// MyPayslips smoke — month grouping + page render (read-only).
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import MyPayslips, { groupPayslipsByMonth } from '../apps/my/MyPayslips';

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token' }),
}));

const fetchMyPayslips = vi.fn();
vi.mock('../api/my', () => ({
  fetchMyPayslips: (...args) => fetchMyPayslips(...args),
}));

describe('groupPayslipsByMonth', () => {
  it('groups by period month newest first', () => {
    const groups = groupPayslipsByMonth([
      { id: 1, payroll_run: 10, period_start: '2026-08-01', period_end: '2026-08-31', line_type: { code: 'gross' }, amount: 100 },
      { id: 2, payroll_run: 30, period_start: '2026-09-01', period_end: '2026-09-30', line_type: { code: 'gross' }, amount: 6500 },
      { id: 3, payroll_run: 30, period_start: '2026-09-01', period_end: '2026-09-30', line_type: { code: 'net' }, amount: 4500 },
    ]);
    expect(groups).toHaveLength(2);
    expect(groups[0].runId).toBe(30);
    expect(groups[0].lines).toHaveLength(2);
    expect(groups[1].runId).toBe(10);
  });
});

describe('MyPayslips page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchMyPayslips.mockResolvedValue([
      {
        id: 1,
        payroll_run: 30,
        period_start: '2026-09-01',
        period_end: '2026-09-30',
        run_status: 'committed',
        line_type: { code: 'gross', label: 'Gross' },
        amount: 6500,
        rule_id: 'kw-gross-pay',
        rule_version: 1,
      },
      {
        id: 2,
        payroll_run: 30,
        period_start: '2026-09-01',
        period_end: '2026-09-30',
        run_status: 'committed',
        line_type: { code: 'gosi', label: 'GOSI' },
        amount: 1200,
        rule_id: 'kw-gosi',
        rule_version: 1,
      },
      {
        id: 3,
        payroll_run: 30,
        period_start: '2026-09-01',
        period_end: '2026-09-30',
        run_status: 'committed',
        line_type: { code: 'net', label: 'Net' },
        amount: 4500,
        rule_id: 'kw-net-pay',
        rule_version: 1,
      },
    ]);
  });

  it('renders month nav and line labels (not [object Object])', async () => {
    render(<MyPayslips />);
    expect(await screen.findByTestId('my-payslips')).toBeInTheDocument();
    await waitFor(() => expect(fetchMyPayslips).toHaveBeenCalled());
    expect(screen.getByTestId('payslip-month-nav')).toBeInTheDocument();
    expect(screen.getAllByText('Gross').length).toBeGreaterThan(0);
    expect(screen.getAllByText('GOSI').length).toBeGreaterThan(0);
    expect(screen.queryByText('[object Object]')).not.toBeInTheDocument();
    expect(screen.getByTestId('payslip-lines-table')).toBeInTheDocument();
  });

  it('disables next when on newest month', async () => {
    render(<MyPayslips />);
    await waitFor(() => expect(fetchMyPayslips).toHaveBeenCalled());
    expect(screen.getByTestId('payslip-month-next')).toBeDisabled();
  });
});
