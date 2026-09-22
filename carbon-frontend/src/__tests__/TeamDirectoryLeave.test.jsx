// Team Directory + Who's Out smoke (manager-scoped reads).
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token' }),
}));

vi.mock('../api/team', () => ({
  fetchDirectReports: vi.fn(),
  fetchTeamLeave: vi.fn(),
}));

import { fetchDirectReports, fetchTeamLeave } from '../api/team';
import TeamDirectory from '../apps/team/TeamDirectory';
import TeamLeave from '../apps/team/TeamLeave';

beforeEach(() => {
  vi.clearAllMocks();
});

describe('TeamDirectory smoke', () => {
  it('renders title and empty state', async () => {
    fetchDirectReports.mockResolvedValue([]);

    render(
      <MemoryRouter>
        <TeamDirectory />
      </MemoryRouter>,
    );

    await waitFor(() => expect(fetchDirectReports).toHaveBeenCalled());
    expect(screen.getAllByText(/Team Directory/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/No direct reports assigned to you/i)).toBeInTheDocument();
  });

  it('renders a direct-report row', async () => {
    fetchDirectReports.mockResolvedValue([
      {
        id: 7,
        employee_no: 'TM-REP',
        full_name: 'Team Rep',
        job_title: 'Analyst',
        is_active: true,
        org_unit: { id: 1, name: 'Ops' },
      },
    ]);

    render(
      <MemoryRouter>
        <TeamDirectory />
      </MemoryRouter>,
    );

    expect(await screen.findByText('TM-REP')).toBeInTheDocument();
    expect(screen.getByText('Team Rep')).toBeInTheDocument();
    expect(screen.getByText('Ops')).toBeInTheDocument();
  });
});

describe("Who's Out smoke", () => {
  it('renders title and empty month', async () => {
    fetchTeamLeave.mockResolvedValue({ year: 2026, month: 9, items: [] });

    render(
      <MemoryRouter>
        <TeamLeave />
      </MemoryRouter>,
    );

    await waitFor(() => expect(fetchTeamLeave).toHaveBeenCalled());
    expect(screen.getAllByText(/Who's Out/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/No team leave overlapping this month/i)).toBeInTheDocument();
  });

  it('renders a leave row', async () => {
    fetchTeamLeave.mockResolvedValue({
      year: 2026,
      month: 9,
      items: [
        {
          id: 99,
          employee_no: 'TM-REP',
          employee_name: 'Team Rep',
          leave_type: 'annual',
          leave_type_label: 'Annual',
          start_date: '2026-09-10',
          end_date: '2026-09-12',
          days: '3.00',
          status: 'approved',
        },
      ],
    });

    render(
      <MemoryRouter>
        <TeamLeave />
      </MemoryRouter>,
    );

    expect(await screen.findByText('TM-REP')).toBeInTheDocument();
    expect(screen.getByText('Team Rep')).toBeInTheDocument();
    expect(screen.getByText(/Annual/i)).toBeInTheDocument();
  });
});
