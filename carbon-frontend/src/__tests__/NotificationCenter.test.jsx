import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token' }),
}));

vi.mock('../api/notifications', () => ({
  getNotifications: vi.fn(),
  getUnreadCount: vi.fn(),
  markRead: vi.fn(),
  markAllRead: vi.fn(),
}));

import { getNotifications, getUnreadCount, markRead, markAllRead } from '../api/notifications';
import HeaderEnhanced from '../components/HeaderEnhanced';

function renderHeaderEnhanced() {
  return render(
    <MemoryRouter>
      <HeaderEnhanced />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  getNotifications.mockResolvedValue({
    count: 2,
    next: null,
    previous: null,
    results: [
      {
        id: 1,
        title: 'Security alert',
        body: 'Login from new device',
        category: 'security',
        is_read: false,
        link: '/admin',
        created_at: new Date().toISOString(),
      },
      {
        id: 2,
        title: 'Backup done',
        body: '',
        category: 'backup',
        is_read: true,
        link: '',
        created_at: new Date().toISOString(),
      },
    ],
  });
  getUnreadCount.mockResolvedValue({ unread_count: 1 });
  markRead.mockResolvedValue({ detail: 'ok', id: 1 });
  markAllRead.mockResolvedValue({ detail: 'ok', count: 1 });
});

describe('NotificationCenter', () => {
  async function openNotifications() {
    renderHeaderEnhanced();
    const bellButton = await screen.findByRole('button', { name: /notifications/i });
    bellButton.click();
    return bellButton;
  }

  it('fetches notifications and unread count on mount', async () => {
    renderHeaderEnhanced();

    await waitFor(() => {
      expect(getNotifications).toHaveBeenCalledWith('test-token', 1);
      expect(getUnreadCount).toHaveBeenCalledWith('test-token');
    });
  });

  it('renders the notification rows with title and category', async () => {
    await openNotifications();

    expect(await screen.findByText('Security alert')).toBeInTheDocument();
    expect(screen.getByText('Backup done')).toBeInTheDocument();
  });

  it('renders the empty state when there are no notifications', async () => {
    getNotifications.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    await openNotifications();

    expect(await screen.findByText('No notifications')).toBeInTheDocument();
  });

  it('calls markRead when a notification row is clicked', async () => {
    await openNotifications();

    const row = await screen.findByText('Security alert');
    row.click();

    await waitFor(() => {
      expect(markRead).toHaveBeenCalledWith('test-token', 1);
    });
  });

  it('calls markAllRead when the mark all read button is clicked', async () => {
    await openNotifications();

    const button = await screen.findByText('Mark all read');
    button.click();

    await waitFor(() => {
      expect(markAllRead).toHaveBeenCalledWith('test-token');
    });
  });

  it('shows the unread badge count on mount', async () => {
    renderHeaderEnhanced();

    expect(await screen.findByText('1')).toBeInTheDocument();
  });
});
