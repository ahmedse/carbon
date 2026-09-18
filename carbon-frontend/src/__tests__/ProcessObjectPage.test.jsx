// Process object page — scope editor + autonomy + lifecycle actions.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import ProcessObjectPage from '../pages/admin/ai/control/ProcessObjectPage';

const state = vi.hoisted(() => ({ capabilities: ['ai:process_owner', 'ai:publisher'] }));

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

const getProcess = vi.fn();
const getDiff = vi.fn();
const getAutonomy = vi.fn();
const updateProcess = vi.fn();
const setAutonomy = vi.fn();
const setKillSwitch = vi.fn();
const submitProcess = vi.fn();
const publishProcess = vi.fn();
const deprecateProcess = vi.fn();

vi.mock('../api/aiRegistry', () => ({
  getProcess: (...a) => getProcess(...a),
  getDiff: (...a) => getDiff(...a),
  getAutonomy: (...a) => getAutonomy(...a),
  updateProcess: (...a) => updateProcess(...a),
  setAutonomy: (...a) => setAutonomy(...a),
  setKillSwitch: (...a) => setKillSwitch(...a),
  submitProcess: (...a) => submitProcess(...a),
  publishProcess: (...a) => publishProcess(...a),
  deprecateProcess: (...a) => deprecateProcess(...a),
}));

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
    objective: { predicate: 'Ship invoices safely' },
    scope: {
      source: 'authenticated_host_context',
      org_unit: 'finance',
      roles: ['approver'],
    },
    steps: [
      {
        id: 'step-1',
        kind: 'command',
        capability: 'carbon:query',
        autonomy: 'human_only',
      },
    ],
    evidence: [],
    tests: [],
  },
};

beforeEach(() => {
  vi.clearAllMocks();
  state.capabilities = ['ai:process_owner', 'ai:publisher'];
  getProcess.mockResolvedValue(DETAIL);
  getDiff.mockResolvedValue({
    process_id: 'proc-1',
    from_version: '0.1.0',
    to_version: '0.2.0',
    added: { objects: [{}] },
    removed: {},
    changed: {},
  });
  getAutonomy.mockResolvedValue({ 'step-1': 'human_only' });
  updateProcess.mockResolvedValue(DETAIL);
  setAutonomy.mockResolvedValue({ 'step-1': 'observe' });
});

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/admin/ai/domain/processes/proc-1']}>
      <Routes>
        <Route
          path="/admin/ai/domain/processes/:processId"
          element={<ProcessObjectPage />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe('ProcessObjectPage', () => {
  it('loads overview with process id and objective', async () => {
    renderPage();
    expect(await screen.findByText('proc-1')).toBeInTheDocument();
    expect(screen.getByText('Ship invoices safely')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Submit for review' })).toBeEnabled();
  });

  it('edits and saves structured scope on draft', async () => {
    renderPage();
    await screen.findByText('proc-1');

    fireEvent.click(screen.getByRole('tab', { name: 'Scope' }));
    const org = screen.getByLabelText('Org unit');
    fireEvent.change(org, { target: { value: 'ops' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save scope & objective' }));

    await waitFor(() => expect(updateProcess).toHaveBeenCalled());
    const body = updateProcess.mock.calls[0][2];
    expect(body.scope.org_unit).toBe('ops');
    expect(body.scope.source).toBe('authenticated_host_context');
    expect(notify).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'success' }),
    );
  });

  it('shows diff tab content', async () => {
    renderPage();
    await screen.findByText('proc-1');
    fireEvent.click(screen.getByRole('tab', { name: 'Diff' }));
    expect(await screen.findByText(/0\.1\.0 → 0\.2\.0/)).toBeInTheDocument();
    expect(screen.getByText('objects')).toBeInTheDocument();
  });
});
