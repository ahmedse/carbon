// src/__tests__/ProcessRegistry.test.jsx
// P3-05c — Process Registry screen spec: list rendering, status filter,
// structured diff (added/removed/changed + no-active-version), and CBAC
// capability gating (buttons disabled without the required capability).
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
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
const getProcess = vi.fn();
const getDiff = vi.fn();
const getAutonomy = vi.fn();
const createProcess = vi.fn();
const updateProcess = vi.fn();
const submitProcess = vi.fn();
const publishProcess = vi.fn();
const deprecateProcess = vi.fn();
const setAutonomy = vi.fn();
const setKillSwitch = vi.fn();

vi.mock('../api/aiRegistry', () => ({
  listProcesses: (...a) => listProcesses(...a),
  getProcess: (...a) => getProcess(...a),
  getDiff: (...a) => getDiff(...a),
  getAutonomy: (...a) => getAutonomy(...a),
  createProcess: (...a) => createProcess(...a),
  updateProcess: (...a) => updateProcess(...a),
  submitProcess: (...a) => submitProcess(...a),
  publishProcess: (...a) => publishProcess(...a),
  deprecateProcess: (...a) => deprecateProcess(...a),
  setAutonomy: (...a) => setAutonomy(...a),
  setKillSwitch: (...a) => setKillSwitch(...a),
}));

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

const DETAIL = {
  process_id: 'proc-1',
  version: '0.2.0',
  owner: 'alice',
  status: 'draft',
  kill_switch: false,
  definition: {
    id: 'proc-1',
    version: '0.2.0',
    owner: 'alice',
    status: 'draft',
    objective: 'new objective',
    steps: [
      { id: 'step-1', kind: 'command', capability: 'carbon:query', autonomy: 'human_only' },
    ],
    evidence: [],
    tests: [],
  },
};

const DIFF = {
  process_id: 'proc-1',
  from_version: '0.1.0',
  to_version: '0.2.0',
  added: { objects: [{}] },
  removed: { old_field: 'x' },
  changed: { objective: { from: 'old objective', to: 'new objective' } },
};

beforeEach(() => {
  vi.clearAllMocks();
  state.capabilities = [];
  listProcesses.mockResolvedValue(ROWS);
  getProcess.mockResolvedValue(DETAIL);
  getDiff.mockResolvedValue(DIFF);
  getAutonomy.mockResolvedValue({ 'step-1': 'human_only' });
  createProcess.mockResolvedValue(DETAIL);
  submitProcess.mockResolvedValue(DETAIL);
  publishProcess.mockResolvedValue(DETAIL);
  deprecateProcess.mockResolvedValue(DETAIL);
  setKillSwitch.mockResolvedValue({ process_id: 'proc-1', kill_switch: true });
  setAutonomy.mockResolvedValue({ 'step-1': 'observe' });
});

describe('ProcessRegistry', () => {
  it('renders the registry list', async () => {
    render(<ProcessRegistry />);

    expect(await screen.findByText('proc-1')).toBeInTheDocument();
    expect(screen.getByText('proc-2')).toBeInTheDocument();
    expect(screen.getByText('alice')).toBeInTheDocument();
    expect(screen.getByText('0.2.0')).toBeInTheDocument();
    expect(screen.getByText('draft')).toBeInTheDocument();
    expect(screen.getByText('active')).toBeInTheDocument();
  });

  it('drives the ?status= param from the status tabs', async () => {
    render(<ProcessRegistry />);
    await screen.findByText('proc-1');

    fireEvent.click(screen.getByRole('tab', { name: 'Review' }));

    await waitFor(() =>
      expect(listProcesses).toHaveBeenLastCalledWith('test-token', {
        status: 'review',
      })
    );
  });

  it('renders a structured diff (added / removed / changed)', async () => {
    render(<ProcessRegistry />);
    await screen.findByText('proc-1');

    fireEvent.click(screen.getByText('proc-1'));

    expect(await screen.findByText('Process Detail')).toBeInTheDocument();
    expect(screen.getByText(/old objective → new objective/)).toBeInTheDocument();
    expect(screen.getByText(/^\+ objects:/)).toBeInTheDocument();
    expect(screen.getByText(/^- old_field:/)).toBeInTheDocument();
  });

  it('shows the no-active-version message when the diff is null', async () => {
    getDiff.mockResolvedValue({ diff: null, reason: 'no_active_version' });
    render(<ProcessRegistry />);
    await screen.findByText('proc-1');

    fireEvent.click(screen.getByText('proc-1'));

    expect(
      await screen.findByText('No active version to diff against.')
    ).toBeInTheDocument();
  });

  it('disables write buttons when the caller lacks the capability', async () => {
    render(<ProcessRegistry />);
    await screen.findByText('proc-1');

    // New draft (requires ai:process_owner) is disabled + rendered.
    expect(screen.getByRole('button', { name: 'New draft' })).toBeDisabled();

    // Open a draft detail → Submit (requires ai:process_owner) disabled.
    fireEvent.click(screen.getByText('proc-1'));
    await screen.findByText('Process Detail');
    expect(screen.getByRole('button', { name: 'Submit' })).toBeDisabled();
  });

  it('enables owner actions when ai:process_owner is present', async () => {
    state.capabilities = ['ai:process_owner'];
    render(<ProcessRegistry />);
    await screen.findByText('proc-1');

    expect(screen.getByRole('button', { name: 'New draft' })).not.toBeDisabled();

    fireEvent.click(screen.getByText('proc-1'));
    await screen.findByText('Process Detail');
    expect(screen.getByRole('button', { name: 'Submit' })).not.toBeDisabled();
  });
});

describe('flattenDiff', () => {
  it('flattens added / removed / changed into a flat list', () => {
    const lines = flattenDiff(
      { objects: [{}] },
      { old_field: 'x' },
      { objective: { from: 'a', to: 'b' } }
    );
    expect(lines).toEqual([
      { kind: 'added', label: 'objects', value: [{}] },
      { kind: 'removed', label: 'old_field', value: 'x' },
      { kind: 'changed', label: 'objective', from: 'a', to: 'b' },
    ]);
  });
});
