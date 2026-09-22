// MyAttendance smoke — request button + history section render.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token', user: { username: 'emp' } }),
}));

vi.mock('../components/NotificationProvider', () => ({
  useNotification: () => ({ notify: vi.fn() }),
}));

vi.mock('../api/my', () => ({
  fetchMyProfile: vi.fn(),
  fetchMyAttendancePermissions: vi.fn(),
  submitAttendancePermission: vi.fn(),
}));

import {
  fetchMyProfile,
  fetchMyAttendancePermissions,
} from '../api/my';
import MyAttendance from '../apps/my/MyAttendance';

beforeEach(() => {
  fetchMyProfile.mockResolvedValue({ full_name: 'Test Emp' });
  fetchMyAttendancePermissions.mockResolvedValue([]);
});

describe('MyAttendance smoke', () => {
  it('renders title and request button', async () => {
    render(
      <MemoryRouter>
        <MyAttendance />
      </MemoryRouter>,
    );
    await waitFor(() => expect(fetchMyAttendancePermissions).toHaveBeenCalled());
    expect(screen.getByRole('button', { name: /request permission/i })).toBeInTheDocument();
  });

  it('shows empty history', async () => {
    render(
      <MemoryRouter>
        <MyAttendance />
      </MemoryRouter>,
    );
    await waitFor(() => expect(fetchMyAttendancePermissions).toHaveBeenCalled());
    expect(screen.getByText(/no attendance permissions yet/i)).toBeInTheDocument();
  });
});
