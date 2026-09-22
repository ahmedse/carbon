// NSR-9 — TeamInbox smoke: inbox chrome + empty / row render + eye opens detail.
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
  fetchInbox: vi.fn(),
}));

import { fetchInbox } from '../api/team';
import TeamInbox from '../apps/team/TeamInbox';

beforeEach(() => {
  vi.clearAllMocks();
  navigateMock.mockClear();
});

describe('TeamInbox smoke (NSR-9)', () => {
  it('renders Approvals Inbox title and empty state', async () => {
    fetchInbox.mockResolvedValue({ items: [] });

    render(
      <MemoryRouter>
        <TeamInbox />
      </MemoryRouter>,
    );

    await waitFor(() => expect(fetchInbox).toHaveBeenCalled());
    expect(screen.getAllByText(/Approvals Inbox/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/No requests awaiting your approval/i)).toBeInTheDocument();
  });

  it('renders an inbox row with reference and type', async () => {
    fetchInbox.mockResolvedValue({
      items: [
        {
          id: 42,
          reference_no: 'LR-2026-0001',
          title: 'Annual leave',
          requester_name: 'Alice',
          corr_type_label: 'Leave Request',
          corr_type_code: 'leave_request',
          status: 'submitted',
          created_at: '2026-09-16T10:00:00Z',
        },
      ],
    });

    render(
      <MemoryRouter>
        <TeamInbox />
      </MemoryRouter>,
    );

    expect(await screen.findByText('LR-2026-0001')).toBeInTheDocument();
    expect(screen.getByText('Alice')).toBeInTheDocument();
    expect(screen.getByText(/Leave Request/i)).toBeInTheDocument();
  });

  it('opens detail via eye icon, not row click', async () => {
    const user = userEvent.setup();
    fetchInbox.mockResolvedValue({
      items: [
        {
          id: 42,
          reference_no: 'CRS-2026-0077',
          title: 'Leave request',
          requester_name: 'emp_1067',
          corr_type_label: 'Leave Request',
          corr_type_code: 'leave_request',
          status: 'submitted',
          created_at: '2026-09-21T18:38:00Z',
        },
      ],
    });

    render(
      <MemoryRouter>
        <TeamInbox />
      </MemoryRouter>,
    );

    expect(await screen.findByText('CRS-2026-0077')).toBeInTheDocument();

    await user.click(screen.getByText('CRS-2026-0077'));
    expect(navigateMock).not.toHaveBeenCalled();

    await user.click(screen.getByRole('button', { name: /Open request CRS-2026-0077/i }));
    expect(navigateMock).toHaveBeenCalledWith('/team/42');
  });
});
