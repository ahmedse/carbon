// src/__tests__/AgentsPanel.test.jsx
// W3-G — AI Admin agent catalog spec: staff-gated CRUD (create / edit /
// remove), RULE_21 confirm gate for delete (API NOT called until confirmed),
// and the update payload never carries `name` (backend update serializer
// omits it — rename is delete + create). Non-staff admins get read-only.
//
// CarbonDataGrid only mounts once its container has width > 0, so we stub
// getBoundingClientRect + ResizeObserver (jsdom has neither by default).
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import AgentsPanel from '../pages/admin/ai/AgentsPanel';

let mockAuth = {
  token: 'test-token',
  userCapabilities: [],
  canSchemaAdmin: () => false,
  isGlobalAdminFlag: false,
};

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => mockAuth,
}));

const { notify, notifyFromError } = vi.hoisted(() => ({
  notify: vi.fn(),
  notifyFromError: vi.fn(),
}));

vi.mock('../components/NotificationProvider', () => ({
  useNotification: () => ({ notify, notifyFromError, showFeedback: vi.fn() }),
}));

const listAgents = vi.fn();
const createAgent = vi.fn();
const updateAgent = vi.fn();
const deleteAgent = vi.fn();
const getTopology = vi.fn();

vi.mock('../api/aiCatalog', () => ({
  listAgents: (...args) => listAgents(...args),
  createAgent: (...args) => createAgent(...args),
  updateAgent: (...args) => updateAgent(...args),
  deleteAgent: (...args) => deleteAgent(...args),
  getTopology: (...args) => getTopology(...args),
}));

const AGENTS = [
  {
    id: 'a1',
    name: 'Fetcher',
    role: 'researcher',
    tool_set: ['web_search'],
    playbook_blocks: [],
    model_override: null,
    max_turns: 3,
    is_active: true,
    outgoing_handoffs: [{ to_agent_id: 'a2', description: 'findings' }],
    incoming_handoffs: [{ from_agent_id: 'a1', description: 'delegate' }],
    skills: [{ id: 's1', name: 'search' }],
  },
];

class FakeResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

const originalGetBoundingClientRect = Element.prototype.getBoundingClientRect;

beforeEach(() => {
  vi.clearAllMocks();
  mockAuth = {
    token: 'test-token',
    userCapabilities: [],
    canSchemaAdmin: () => false,
    isGlobalAdminFlag: false,
  };
  listAgents.mockResolvedValue(AGENTS);
  createAgent.mockResolvedValue({ id: 'a-new' });
  updateAgent.mockResolvedValue({ id: 'a1' });
  deleteAgent.mockResolvedValue({ id: 'a1', deleted: true });
  getTopology.mockResolvedValue({ nodes: [], edges: [] });
  global.ResizeObserver = FakeResizeObserver;
  Element.prototype.getBoundingClientRect = () => ({
    width: 960,
    height: 600,
    top: 0,
    left: 0,
    right: 960,
    bottom: 600,
    x: 0,
    y: 0,
    toJSON: () => ({}),
  });
});

afterEach(() => {
  delete global.ResizeObserver;
  Element.prototype.getBoundingClientRect = originalGetBoundingClientRect;
});

describe('AgentsPanel — staff gate', () => {
  it('hides write controls for non-staff admins (read-only catalog)', async () => {
    render(<AgentsPanel />);
    await screen.findByText('Fetcher');

    expect(screen.queryByRole('button', { name: 'Register agent' })).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Edit Fetcher')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Remove Fetcher')).not.toBeInTheDocument();
  });

  it('shows write controls for staff (isGlobalAdminFlag)', async () => {
    mockAuth = {
      token: 'test-token',
      userCapabilities: [],
      canSchemaAdmin: () => false,
      isGlobalAdminFlag: true,
    };
    render(<AgentsPanel />);
    await screen.findByText('Fetcher');

    expect(screen.getByRole('button', { name: 'Register agent' })).toBeInTheDocument();
    expect(screen.getByLabelText('Edit Fetcher')).toBeInTheDocument();
    expect(screen.getByLabelText('Remove Fetcher')).toBeInTheDocument();
  });
});

describe('AgentsPanel — CRUD (staff)', () => {
  beforeEach(() => {
    mockAuth = {
      token: 'test-token',
      userCapabilities: [],
      canSchemaAdmin: () => true,
      isGlobalAdminFlag: false,
    };
  });

  it('creates an agent through the register dialog', async () => {
    render(<AgentsPanel />);
    await screen.findByText('Fetcher');

    fireEvent.click(screen.getByRole('button', { name: 'Register agent' }));
    expect(screen.getByRole('heading', { name: 'Register agent' })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Name (unique — engine upsert key)'), {
      target: { value: 'CriticBot' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Register' }));

    await waitFor(() =>
      expect(createAgent).toHaveBeenCalledWith(
        'test-token',
        expect.objectContaining({ name: 'CriticBot', role: 'orchestrator', max_turns: 3 }),
      ),
    );
    expect(notify).toHaveBeenCalledWith(expect.objectContaining({ type: 'success' }));
  });

  it('updates an agent WITHOUT sending name (update serializer omits it)', async () => {
    render(<AgentsPanel />);
    await screen.findByText('Fetcher');

    fireEvent.click(screen.getByLabelText('Edit Fetcher'));
    expect(screen.getByText('Edit Fetcher')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }));

    await waitFor(() => expect(updateAgent).toHaveBeenCalledTimes(1));
    const [, id, payload] = updateAgent.mock.calls[0];
    expect(id).toBe('a1');
    expect(payload).not.toHaveProperty('name');
    expect(payload).toEqual(
      expect.objectContaining({ role: 'researcher', max_turns: 3 }),
    );
  });

  it('delete is confirm-gated: API is NOT called until the dialog confirms (RULE_21)', async () => {
    render(<AgentsPanel />);
    await screen.findByText('Fetcher');

    fireEvent.click(screen.getByLabelText('Remove Fetcher'));
    expect(screen.getByText('Remove agent?')).toBeInTheDocument();
    expect(deleteAgent).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'Remove agent' }));
    await waitFor(() => expect(deleteAgent).toHaveBeenCalledWith('test-token', 'a1'));
    expect(notify).toHaveBeenCalledWith(expect.objectContaining({ type: 'success' }));
  });

  it('notifies from error when a mutation fails', async () => {
    createAgent.mockRejectedValue(new Error('admin_required'));
    render(<AgentsPanel />);
    await screen.findByText('Fetcher');

    fireEvent.click(screen.getByRole('button', { name: 'Register agent' }));
    fireEvent.change(screen.getByLabelText('Name (unique — engine upsert key)'), {
      target: { value: 'Nope' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Register' }));

    await waitFor(() => expect(notifyFromError).toHaveBeenCalled());
  });
});
