// src/__tests__/ReviewQueue.test.jsx
// P3-05c — Review Queue screen spec: the seven review dimensions render from
// real data (diff, rationale, evidence, derived missing evidence, derived
// permissions delta, tests, affected runs), and Publish is gated by
// ai:publisher.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import ReviewQueue, {
  computePermissionDelta,
  deriveMissingEvidence,
} from '../pages/admin/ai/ReviewQueue';

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
const publishProcess = vi.fn();

vi.mock('../api/aiRegistry', () => ({
  listProcesses: (...a) => listProcesses(...a),
  getProcess: (...a) => getProcess(...a),
  getDiff: (...a) => getDiff(...a),
  publishProcess: (...a) => publishProcess(...a),
}));

const listPlans = vi.fn();
vi.mock('../api/aiWorkspace', () => ({
  listPlans: (...a) => listPlans(...a),
}));

const REVIEW_ROW = {
  process_id: 'proc-1',
  version: '0.2.0',
  owner: 'alice',
  status: 'review',
  kill_switch: false,
  updated_at: '2026-09-01T10:00:00Z',
};

const DEFINITION = {
  id: 'proc-1',
  version: '0.2.0',
  owner: 'alice',
  status: 'review',
  objective: 'Reconcile monthly emissions',
  steps: [
    { id: 'step-1', kind: 'command', capability: 'carbon:query', autonomy: 'human_only' },
    { id: 'step-2', kind: 'human_task', capability: 'carbon:approve', consent: true },
  ],
  evidence: [{ step: 'step-1', title: 'Query log' }],
  tests: [{ name: 'smoke' }],
};

const DIFF = {
  process_id: 'proc-1',
  from_version: '0.1.0',
  to_version: '0.2.0',
  added: { scope: { source: 'scope-2' } },
  removed: { old_policy: 'x' },
  changed: {
    objective: { from: 'old objective', to: 'Reconcile monthly emissions' },
    steps: {
      from: [{ id: 'step-1', capability: 'carbon:query' }],
      to: [{ id: 'step-1', capability: 'carbon:write' }],
    },
  },
};

const PLANS = {
  plans: [
    {
      id: 'run-1',
      status: 'pending_approval',
      brief: 'Reconcile the emissions',
      created_at: '2026-09-03T10:00:00Z',
      definition_id: 'proc-1',
    },
    {
      id: 'run-2',
      status: 'completed',
      brief: 'Unrelated run',
      created_at: '2026-09-04T10:00:00Z',
      definition_id: 'proc-other',
    },
  ],
  count: 2,
};

beforeEach(() => {
  vi.clearAllMocks();
  state.capabilities = [];
  listProcesses.mockResolvedValue([REVIEW_ROW]);
  getProcess.mockResolvedValue({ ...REVIEW_ROW, definition: DEFINITION, kill_switch: false });
  getDiff.mockResolvedValue(DIFF);
  listPlans.mockResolvedValue(PLANS);
  publishProcess.mockResolvedValue({ ...REVIEW_ROW, status: 'active' });
});

describe('ReviewQueue', () => {
  it('requests only review-status processes and renders the seven dimensions', async () => {
    render(<ReviewQueue />);

    await waitFor(() =>
      expect(listProcesses).toHaveBeenCalledWith('test-token', { status: 'review' })
    );

    expect(await screen.findByText('proc-1')).toBeInTheDocument();
    for (const heading of [
      'Diff',
      'Rationale',
      'Evidence',
      'Missing evidence',
      'Permissions delta',
      'Tests',
      'Affected runs',
    ]) {
      expect(screen.getByText(heading)).toBeInTheDocument();
    }
  });

  it('renders rationale, evidence, tests and affected runs from real data', async () => {
    render(<ReviewQueue />);

    expect(await screen.findByText('Reconcile monthly emissions')).toBeInTheDocument();
    expect(screen.getByText(/Query log/)).toBeInTheDocument();
    expect(screen.getByText(/smoke/)).toBeInTheDocument();
    expect(screen.getByText(/run-1/)).toBeInTheDocument();
    // run-2 references a different process → filtered out.
    expect(screen.queryByText(/run-2/)).not.toBeInTheDocument();
  });

  it('derives missing evidence for human_task/consent steps without evidence', async () => {
    render(<ReviewQueue />);

    expect(await screen.findByText('proc-1')).toBeInTheDocument();
    // step-2 is a consent-gated human_task with no evidence reference.
    expect(screen.getByText('step-2')).toBeInTheDocument();
  });

  it('derives the permissions delta from changed.steps', async () => {
    render(<ReviewQueue />);

    expect(await screen.findByText('proc-1')).toBeInTheDocument();
    expect(
      screen.getByText(/step-1\.capability: carbon:query → carbon:write/)
    ).toBeInTheDocument();
  });

  it('disables Publish without ai:publisher', async () => {
    render(<ReviewQueue />);

    expect(await screen.findByText('proc-1')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Publish' })).toBeDisabled();
  });

  it('enables Publish with ai:publisher', async () => {
    state.capabilities = ['ai:publisher'];
    render(<ReviewQueue />);

    expect(await screen.findByText('proc-1')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Publish' })).not.toBeDisabled();
  });
});

describe('deriveMissingEvidence', () => {
  it('flags human_task / consent steps with no evidence reference', () => {
    const missing = deriveMissingEvidence(DEFINITION);
    expect(missing).toEqual(['step-2']);
  });
});

describe('computePermissionDelta', () => {
  it('surfaces capability changes matched by step id', () => {
    const deltas = computePermissionDelta(DIFF);
    expect(deltas).toEqual([
      { step: 'step-1', field: 'capability', from: 'carbon:query', to: 'carbon:write' },
    ]);
  });
});
