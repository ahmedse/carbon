// src/__tests__/ProcessRegistry.test.jsx
// Process Registry list: status filter, CBAC gating, navigate to object page.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ProcessRegistry, { flattenDiff } from '../pages/admin/ai/ProcessRegistry';

const state = vi.hoisted(() => ({ capabilities: [] }));

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token', userCapabilities: state.capabilities }),
}));

const { notify, notifyFromError } = vi.hoisted(() => ({
  notify: vi.fn(),
  notifyFromError: vi.fn(),
}));

vi.mock('../components/NotificationProvider', () => ({
  useNotification: () => ({ notify, notifyFromError, showFeedback: vi.fn() }),
}));

const listProcesses = vi.fn();
const createProcess = vi.fn();
const setKillSwitch = vi.fn();

vi.mock('../api/aiRegistry', () => ({
  listProcesses: (...a) => listProcesses(...a),
  createProcess: (...a) => createProcess(...a),
  setKillSwitch: (...a) => setKillSwitch(...a),
}));

const navigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => navigate,
  };
});

const ROWS = [
  {
    process_id: 'proc-1',
    version: '0.2.0',
    owner: 'alice',
    status: 'draft',
    kill_switch: false,
    updated_at: '2026-09-01T10:00:00Z',
  },
  {
    process_id: 'proc-2',
    version: '1.0.0',
    owner: 'bob',
    status: 'active',
    kill_switch: true,
    updated_at: '2026-09-02T10:00:00Z',
  },
];

beforeEach(() => {
  vi.clearAllMocks();
  state.capabilities = [];
  listProcesses.mockResolvedValue(ROWS);
  createProcess.mockResolvedValue({ process_id: 'proc-1' });
  setKillSwitch.mockResolvedValue({ process_id: 'proc-1', kill_switch: true });
});

function renderRegistry() {
  return render(
    <MemoryRouter>
      <ProcessRegistry />
    </MemoryRouter>,
  );
}

describe('ProcessRegistry', () => {
  it('renders the registry list', async () => {
    renderRegistry();

    expect(await screen.findByText('proc-1')).toBeInTheDocument();
    expect(screen.getByText('proc-2')).toBeInTheDocument();
    expect(screen.getByText('alice')).toBeInTheDocument();
    expect(screen.getByText('0.2.0')).toBeInTheDocument();
    expect(screen.getByText('draft')).toBeInTheDocument();
    expect(screen.getByText('active')).toBeInTheDocument();
  });

  it('drives the status filter from the status tabs', async () => {
    renderRegistry();
    await screen.findByText('proc-1');

    fireEvent.click(screen.getByRole('tab', { name: 'Review' }));

    await waitFor(() =>
      expect(listProcesses).toHaveBeenLastCalledWith('test-token', {
        status: 'review',
      }),
    );
  });

  it('navigates to the process object page on row click', async () => {
    renderRegistry();
    await screen.findByText('proc-1');

    fireEvent.click(screen.getByText('proc-1'));

    expect(navigate).toHaveBeenCalledWith('/admin/ai/domain/processes/proc-1');
  });

  it('disables New draft when the caller lacks the capability', async () => {
    renderRegistry();
    await screen.findByText('proc-1');
    expect(screen.getByRole('button', { name: 'New draft' })).toBeDisabled();
  });

  it('enables New draft when ai:process_owner is present', async () => {
    state.capabilities = ['ai:process_owner'];
    renderRegistry();
    await screen.findByText('proc-1');
    expect(screen.getByRole('button', { name: 'New draft' })).not.toBeDisabled();
  });
});

describe('flattenDiff', () => {
  it('flattens added / removed / changed into a flat list', () => {
    const lines = flattenDiff(
      { objects: [{}] },
      { old_field: 'x' },
      { objective: { from: 'a', to: 'b' } },
    );
    expect(lines).toEqual([
      { kind: 'added', label: 'objects', value: [{}] },
      { kind: 'removed', label: 'old_field', value: 'x' },
      { kind: 'changed', label: 'objective', from: 'a', to: 'b' },
    ]);
  });
});
