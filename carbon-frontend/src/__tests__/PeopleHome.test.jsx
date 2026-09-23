// src/__tests__/PeopleHome.test.jsx
// NSR-6A Path H — PeopleHome ops landing: go-live modules only (no Attendance).

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import userEvent from '@testing-library/user-event';

const navigateMock = vi.fn();

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => navigateMock,
  };
});

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token' }),
}));

vi.mock('../api/people', () => ({
  fetchEmployees: vi.fn().mockResolvedValue({ count: 12, results: [] }),
  fetchLeaveRecords: vi.fn().mockResolvedValue({ count: 3, results: [] }),
  fetchPayrollRuns: vi.fn().mockResolvedValue({ count: 2, results: [] }),
  fetchLeavePolicies: vi.fn().mockResolvedValue({ count: 4, results: [] }),
  fetchLoans: vi.fn().mockResolvedValue({ count: 1, results: [] }),
}));

import PeopleHome, { PEOPLE_HOME_MODULES } from '../apps/people/PeopleHome';

describe('PeopleHome (NSR-6A Path H)', () => {
  beforeEach(() => {
    navigateMock.mockClear();
  });

  it('exports the go-live module paths (no attendance/rotation)', () => {
    expect(PEOPLE_HOME_MODULES.map((m) => m.path)).toEqual([
      '/people/employees',
      '/people/requests',
      '/people/leave',
      '/people/payroll',
      '/people/policies',
      '/people/loans',
    ]);
    expect(PEOPLE_HOME_MODULES.map((m) => m.path)).not.toContain('/people/attendance');
    expect(PEOPLE_HOME_MODULES.map((m) => m.path)).not.toContain('/people/rotation');
  });

  it('renders module links for Employees, Leave, Payroll, Policies, Loans', () => {
    render(
      <MemoryRouter>
        <PeopleHome />
      </MemoryRouter>,
    );

    for (const module of PEOPLE_HOME_MODULES) {
      expect(screen.getByTestId(`people-home-${module.id}`)).toBeInTheDocument();
    }

    expect(screen.getByText('Employees')).toBeInTheDocument();
    expect(screen.getByText('Requests')).toBeInTheDocument();
    expect(screen.getByText('Leave')).toBeInTheDocument();
    expect(screen.getByText('Payroll Runs')).toBeInTheDocument();
    expect(screen.getByText('Policies')).toBeInTheDocument();
    expect(screen.getByText('Loans')).toBeInTheDocument();
    expect(screen.queryByTestId('people-home-attendance')).not.toBeInTheDocument();
    expect(screen.queryByText('Attendance')).not.toBeInTheDocument();
  });

  it('navigates to the module path when a card is activated', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <PeopleHome />
      </MemoryRouter>,
    );

    await user.click(screen.getByTestId('people-home-employees'));
    expect(navigateMock).toHaveBeenCalledWith('/people/employees');
  });

  it('soft-loads optional counts without blocking the landing', async () => {
    render(
      <MemoryRouter>
        <PeopleHome />
      </MemoryRouter>,
    );

    expect(screen.getByTestId('people-home-employees')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('12')).toBeInTheDocument();
    });
  });
});
