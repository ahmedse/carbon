// Team History smoke — list + eye opens detail with from=history state.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

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

vi.mock('../api/team', () => ({
  fetchHistory: vi.fn(),
}));

import { fetchHistory } from '../api/team';
import TeamHistory from '../apps/team/TeamHistory';

beforeEach(() => {
  vi.clearAllMocks();
  navigateMock.mockClear();
});

describe('TeamHistory smoke', () => {
  it('renders empty history state', async () => {
    fetchHistory.mockResolvedValue({ items: [] });

    render(
      <MemoryRouter>
        <TeamHistory />
      </MemoryRouter>,
    );

    await waitFor(() => expect(fetchHistory).toHaveBeenCalled());
    expect(screen.getAllByText(/^History$/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/No decisions recorded yet/i)).toBeInTheDocument();
  });

  it('opens detail via eye with history state', async () => {
    const user = userEvent.setup();
    fetchHistory.mockResolvedValue({
      items: [
        {
          id: 77,
          reference_no: 'CRS-2026-0077',
          title: 'Leave request',
          requester_name: 'emp_1067',
          corr_type_label: 'Leave Request',
          corr_type_code: 'leave_request',
          status: 'approved',
          updated_at: '2026-09-22T08:00:00Z',
        },
      ],
    });

    render(
      <MemoryRouter>
        <TeamHistory />
      </MemoryRouter>,
    );

    expect(await screen.findByText('CRS-2026-0077')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /Open request CRS-2026-0077/i }));
    expect(navigateMock).toHaveBeenCalledWith('/team/77', { state: { from: 'history' } });
  });
});
