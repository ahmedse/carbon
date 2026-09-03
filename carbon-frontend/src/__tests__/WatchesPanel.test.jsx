// src/__tests__/WatchesPanel.test.jsx — H3-F Anomaly Watches admin panel.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

let authMock = { token: 't', userCapabilities: ['ai:manage_console'] };

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => authMock,
}));

const { notify, notifyFromError } = vi.hoisted(() => ({
  notify: vi.fn(),
  notifyFromError: vi.fn(),
}));

vi.mock('../components/NotificationProvider', () => ({
  useNotification: () => ({ notify, notifyFromError, showFeedback: vi.fn() }),
}));

vi.mock('../hooks/useDocumentTitle', () => ({
  default: () => {},
}));

const listWatches = vi.fn();
const createWatch = vi.fn();
const updateWatch = vi.fn();
const deleteWatch = vi.fn();

vi.mock('../api/aiPulse', () => ({
  listWatches: (...a) => listWatches(...a),
  createWatch: (...a) => createWatch(...a),
  updateWatch: (...a) => updateWatch(...a),
  deleteWatch: (...a) => deleteWatch(...a),
}));

const fetchUsers = vi.fn();

vi.mock('../api/users', () => ({
  fetchUsers: (...a) => fetchUsers(...a),
}));

import WatchesPanel from '../pages/admin/ai/WatchesPanel';

const ROW = {
  id: 7,
  name: 'CPU spike',
  kpi_expression: 'CPU usage above 90%',
  condition: { table: 'host_metrics', column: 'cpu_pct', operator: '>', aggregation: 'latest' },
  threshold: 90,
  comparison_window_days: 7,
  enabled: true,
  last_fired_at: '2026-09-02T10:00:00Z',
  fire_count: 3,
  recipients: [1, 2],
  instance_id: 'carbon',
};

beforeEach(() => {
  vi.clearAllMocks();
  authMock = { token: 't', userCapabilities: ['ai:manage_console'] };
  listWatches.mockResolvedValue({ count: 1, next: null, previous: null, results: [ROW] });
  fetchUsers.mockResolvedValue([{ id: 1, username: 'alice' }, { id: 2, username: 'bob' }]);
  createWatch.mockResolvedValue({ id: 8 });
  updateWatch.mockResolvedValue({ id: 7 });
  deleteWatch.mockResolvedValue(undefined);
});

function renderPanel() {
  return render(
    <MemoryRouter>
      <WatchesPanel />
    </MemoryRouter>
  );
}

describe('WatchesPanel — anomaly watches', () => {
  it('renders list rows from listWatches', async () => {
    renderPanel();
    expect(await screen.findByText('CPU spike')).toBeInTheDocument();
    expect(screen.getByText('CPU usage above 90%')).toBeInTheDocument();
  });

  it('shows the honest empty state with a primary action', async () => {
    listWatches.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    renderPanel();
    expect(await screen.findByText(/No anomaly watches yet/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Create your first watch' })).toBeInTheDocument();
  });

  it('opens the dialog and submits a create (calls createWatch)', async () => {
    renderPanel();
    await screen.findByText('CPU spike');

    fireEvent.click(screen.getByRole('button', { name: 'New watch' }));
    const dialog = await screen.findByRole('dialog');

    fireEvent.change(within(dialog).getByLabelText(/Name/), { target: { value: 'Disk full' } });
    fireEvent.change(within(dialog).getByLabelText('Threshold'), { target: { value: '95' } });
    fireEvent.change(within(dialog).getByLabelText('Comparison window (days)'), { target: { value: '3' } });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      expect(createWatch).toHaveBeenCalledWith('t', expect.objectContaining({
        name: 'Disk full',
        threshold: 95,
        comparison_window_days: 3,
      }));
    });
  });

  it('hides write affordances and shows forbidden copy without ai:manage_console', async () => {
    authMock.userCapabilities = ['ai:view_console'];
    renderPanel();

    expect(await screen.findByText('CPU spike')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'New watch' })).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Delete CPU spike')).not.toBeInTheDocument();
    expect(screen.getByText(/requires the AI manage console capability/i)).toBeInTheDocument();
  });

  it('shows the full forbidden copy and skips the fetch without ai:view_console', async () => {
    authMock.userCapabilities = [];
    renderPanel();

    expect(await screen.findByText(/requires the AI view console capability/i)).toBeInTheDocument();
    expect(listWatches).not.toHaveBeenCalled();
  });

  it('delete opens ConfirmDialog and calls deleteWatch', async () => {
    renderPanel();
    await screen.findByText('CPU spike');

    fireEvent.click(screen.getByLabelText('Delete CPU spike'));
    const dialog = await screen.findByRole('dialog');

    fireEvent.click(within(dialog).getByRole('button', { name: 'Delete' }));

    await waitFor(() => {
      expect(deleteWatch).toHaveBeenCalledWith('t', 7);
    });
  });
});
