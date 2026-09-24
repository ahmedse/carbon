// MyAttendance smoke — month attendance + permission CTA.
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
  fetchMyAttendance: vi.fn(),
  fetchMyAttendancePermissions: vi.fn(),
  submitAttendancePermission: vi.fn(),
}));

import {
  fetchMyProfile,
  fetchMyAttendance,
  fetchMyAttendancePermissions,
} from '../api/my';
import MyAttendance from '../apps/my/MyAttendance';

beforeEach(() => {
  fetchMyProfile.mockResolvedValue({ full_name: 'Test Emp' });
  fetchMyAttendance.mockResolvedValue([
    {
      id: 1,
      date: '2026-09-30',
      hours_worked: '8.00',
      overtime_hours: '0.00',
      status: 'present',
    },
  ]);
  fetchMyAttendancePermissions.mockResolvedValue([]);
});

describe('MyAttendance smoke', () => {
  it('renders title, month nav, and request button', async () => {
    render(
      <MemoryRouter>
        <MyAttendance />
      </MemoryRouter>,
    );
    await waitFor(() => expect(fetchMyAttendance).toHaveBeenCalled());
    expect(screen.getByTestId('my-attendance')).toBeInTheDocument();
    expect(screen.getByTestId('attendance-month-nav')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /request permission/i })).toBeInTheDocument();
    expect(screen.getByTestId('attendance-records-table')).toBeInTheDocument();
    expect(screen.getAllByText(/Present/i).length).toBeGreaterThan(0);
  });

  it('shows empty permissions section when none', async () => {
    render(
      <MemoryRouter>
        <MyAttendance />
      </MemoryRouter>,
    );
    await waitFor(() => expect(fetchMyAttendancePermissions).toHaveBeenCalled());
    expect(screen.getByText(/no attendance permissions yet/i)).toBeInTheDocument();
  });
});
