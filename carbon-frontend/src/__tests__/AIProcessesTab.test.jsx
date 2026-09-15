// src/__tests__/AIProcessesTab.test.jsx
// P6a — Shell Processes tab: list + detail rendering, submit action, and
// up-front CBAC capability gating (buttons disabled without the required
// capability) plus the 403 fallback that locks a denied action.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';

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
const getProcess = vi.fn();
const getAutonomy = vi.fn();
const submitProcess = vi.fn();
const publishProcess = vi.fn();
const deprecateProcess = vi.fn();
const setAutonomy = vi.fn();
const setKillSwitch = vi.fn();

vi.mock('../api/aiRegistry', () => ({
  listProcesses: (...a) => listProcesses(...a),
  getProcess: (...a) => getProcess(...a),
  getAutonomy: (...a) => getAutonomy(...a),
  submitProcess: (...a) => submitProcess(...a),
  publishProcess: (...a) => publishProcess(...a),
  deprecateProcess: (...a) => deprecateProcess(...a),
  setAutonomy: (...a) => setAutonomy(...a),
  setKillSwitch: (...a) => setKillSwitch(...a),
}));

import AIProcessesTab from '../shell/AIProcessesTab';

const ROWS = [
  {
    process_id: 'proc-1',
    version: 2,
    owner: 'alice',
    status: 'draft',
    kill_switch: false,
    definition: { objective: 'new objective', steps: [] },
  },
  {
    process_id: 'proc-2',
    version: 1,
    owner: 'bob',
    status: 'active',
    kill_switch: true,
    definition: { objective: '', steps: [] },
  },
];

const DETAIL = {
  process_id: 'proc-1',
  version: 2,
  owner: 'alice',
  status: 'draft',
  kill_switch: false,
  definition: {
    id: 'proc-1',
    version: 2,
    owner: 'alice',
    status: 'draft',
    objective: 'new objective',
    steps: [{ id: 'step-1', kind: 'command', autonomy: 'human_only' }],
  },
};

beforeEach(() => {
  vi.clearAllMocks();
  state.capabilities = [];
  listProcesses.mockResolvedValue(ROWS);
  getProcess.mockResolvedValue(DETAIL);
  getAutonomy.mockResolvedValue({ 'step-1': 'human_only' });
  submitProcess.mockResolvedValue(DETAIL);
  publishProcess.mockResolvedValue(DETAIL);
  deprecateProcess.mockResolvedValue(DETAIL);
  setKillSwitch.mockResolvedValue({ process_id: 'proc-1', kill_switch: true });
  setAutonomy.mockResolvedValue({ 'step-1': 'observe' });
});

describe('AIProcessesTab', () => {
  it('renders the governed process list and the selected detail', async () => {
    render(<AIProcessesTab />);

    // List shows the non-selected row's id; detail shows objective + steps.
    expect(await screen.findByText('proc-2')).toBeInTheDocument();
    expect(await screen.findByText('new objective')).toBeInTheDocument();
    expect(screen.getByText('step-1')).toBeInTheDocument();
  });

  it('submits a draft process when the user is a process owner', async () => {
    state.capabilities = ['ai:process_owner'];
    render(<AIProcessesTab />);
    await screen.findByText('new objective');

    fireEvent.click(screen.getByRole('button', { name: 'Submit for review' }));
    const dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Submit for review' }));

    await waitFor(() => {
      expect(submitProcess).toHaveBeenCalledWith('test-token', 'proc-1');
    });
  });

  it('disables write actions up front without the required capability', async () => {
    state.capabilities = ['ai:view_console']; // read-only, no governance caps
    render(<AIProcessesTab />);
    await screen.findByText('new objective');

    expect(screen.getByRole('button', { name: 'Submit for review' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Activate' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Retire' })).toBeDisabled();
  });

  it('locks a denied action after a 403 and warns the user', async () => {
    state.capabilities = ['ai:process_owner'];
    submitProcess.mockRejectedValue({ status: 403 });
    render(<AIProcessesTab />);
    await screen.findByText('new objective');

    fireEvent.click(screen.getByRole('button', { name: 'Submit for review' }));
    const dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Submit for review' }));

    await waitFor(() => {
      expect(notify).toHaveBeenCalledWith(
        expect.objectContaining({ type: 'warning' }),
      );
    });
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Submit for review' })).toBeDisabled();
    });
  });
});
