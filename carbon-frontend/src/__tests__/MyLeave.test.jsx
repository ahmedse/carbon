// NSR-9 — MyLeave smoke: request button + balance section render (QA B2/B3).
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token' }),
}));

vi.mock('../components/NotificationProvider', () => ({
  useNotification: () => ({ notify: vi.fn() }),
}));

vi.mock('../api/my', () => ({
  fetchMyProfile: vi.fn(),
  fetchLeaveBalance: vi.fn(),
  fetchMyLeave: vi.fn(),
  submitLeaveRequest: vi.fn(),
}));

import {
  fetchMyProfile,
  fetchLeaveBalance,
  fetchMyLeave,
} from '../api/my';
import MyLeave from '../apps/my/MyLeave';

beforeEach(() => {
  vi.clearAllMocks();
  fetchMyProfile.mockResolvedValue({
    id: 1,
    full_name: 'Alice',
    manager_name: 'Bob Manager',
  });
  fetchLeaveBalance.mockResolvedValue([
    {
      leave_type: 'annual',
      entitled: 30,
      carried: 0,
      used: 2,
      pending: 0,
      remaining: 28,
    },
  ]);
  fetchMyLeave.mockResolvedValue([]);
});

describe('MyLeave smoke (NSR-9)', () => {
  it('renders Request Leave and balance metrics', async () => {
    render(<MyLeave />);

    expect(await screen.findByRole('button', { name: /Request Leave/i })).toBeInTheDocument();

    await waitFor(() => {
      expect(fetchLeaveBalance).toHaveBeenCalled();
      expect(fetchMyLeave).toHaveBeenCalled();
    });

    expect(screen.getByText(/28/)).toBeInTheDocument();
  });

  it('shows empty leave history when no records', async () => {
    render(<MyLeave />);
    await waitFor(() => expect(fetchMyLeave).toHaveBeenCalled());
    // History table empty copy from my namespace (English mock).
    expect(screen.getByText(/No requests yet/i)).toBeInTheDocument();
  });
});
