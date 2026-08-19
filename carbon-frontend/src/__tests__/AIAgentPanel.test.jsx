// src/__tests__/AIAgentPanel.test.jsx
// Sprint W2-A — Agent surface: 4-tab panel (Agents/MCP/Tools/Logs) + the
// clustered AIActionRunner timeline. Covers: RULE_17 tab persistence, agent
// run launch, tool args form + run, verbosity default expansion, the
// confirm gate for staged mutations (RULE_21), the stop path ("Stopped by
// you" inside the card — never a banner), "Finished · N tools" clustering,
// and the Logs tab.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import AIAgentPanel from '../shell/AIAgentPanel';
import AIActionRunner from '../shell/AIActionRunner';

// ── Mock hooks + API ──────────────────────────────────────────────────────
vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token', userCapabilities: [], isGlobalAdminFlag: false }),
}));

// Stable function identity per render — a fresh vi.fn() each render would
// re-create the useCallback deps and loop setState infinitely.
const { notify, notifyFromError } = vi.hoisted(() => ({
  notify: vi.fn(),
  notifyFromError: vi.fn(),
}));

vi.mock('../components/NotificationProvider', () => ({
  useNotification: () => ({ notify, notifyFromError, showFeedback: vi.fn() }),
}));

const runActionStream = vi.fn();
const stopGeneration = vi.fn();
const confirmToolExecution = vi.fn();
const declineToolExecution = vi.fn();
const createConversation = vi.fn();
const getSettings = vi.fn();
const getPulseData = vi.fn();

vi.mock('../api/aiWorkspace', () => ({
  runActionStream: (...args) => runActionStream(...args),
  stopGeneration: (...args) => stopGeneration(...args),
  confirmToolExecution: (...args) => confirmToolExecution(...args),
  declineToolExecution: (...args) => declineToolExecution(...args),
  createConversation: (...args) => createConversation(...args),
}));

vi.mock('../api/aiPulse', () => ({
  getSettings: (...args) => getSettings(...args),
  getPulseData: (...args) => getPulseData(...args),
}));

const AGENTS = [
  { id: 'agent-1', name: 'data_sweeper', role: 'Deduplicates and cleans datasets', tool_set: ['search_entity', 'create_dq_rule'], is_active: true },
];

const TOOLS = [
  {
    name: 'create_dq_rule',
    description: 'Creates a data-quality rule',
    kind: 'static',
    requires_confirmation: true,
    capability: 'dq:manage_rules',
    parameters: {
      type: 'object',
      properties: {
        name: { type: 'string', description: 'Rule name' },
        enabled: { type: 'boolean', default: true },
      },
      required: ['name'],
    },
  },
  {
    name: 'search_entity',
    description: 'Searches master-data entities',
    kind: 'tool',
    requires_confirmation: false,
    parameters: { type: 'object', properties: {} },
  },
];

const MCP_SERVERS = [{ name: 'brave', command: 'npx', args: ['-y', '@modelcontextprotocol/server-brave'] }];

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  getSettings.mockResolvedValue({ agents: AGENTS, mcp_servers: MCP_SERVERS, tools_catalog: TOOLS });
  getPulseData.mockImplementation((token, key) =>
    Promise.resolve(
      key === 'tools'
        ? { key: 'tools', label: 'Tools', results: [{ _type: 'ToolExecution', id: 'exec-1', tool: 'create_dq_rule', status: 'completed' }] }
        : { key: 'logs', label: 'AI Logs', results: [{ _type: 'LLMCallLog', id: 'call-1', model: 'deepseek' }] },
    ),
  );
  runActionStream.mockResolvedValue(undefined);
  stopGeneration.mockResolvedValue({ id: 'conv-1' });
  confirmToolExecution.mockResolvedValue({ status: 'confirmed' });
  declineToolExecution.mockResolvedValue({ status: 'declined' });
  createConversation.mockResolvedValue({ id: 'conv-new', conversation_type: 'chat', title: 'Agent run' });
});

// ── AIAgentPanel: tabs, persistence, launch, logs ─────────────────────────
describe('AIAgentPanel — four internal tabs (RULE_17)', () => {
  it('renders Agents/MCP/Tools/Logs tabs and defaults to Agents', async () => {
    render(<AIAgentPanel conversationId="conv-1" />);

    expect(screen.getByRole('tab', { name: 'Agents' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'MCP' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Tools' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Logs' })).toBeInTheDocument();

    expect(await screen.findByText('data_sweeper')).toBeInTheDocument();
    expect(screen.getByText('Deduplicates and cleans datasets')).toBeInTheDocument();
  });

  it('persists the selected tab to localStorage (RULE_17)', async () => {
    render(<AIAgentPanel conversationId="conv-1" />);

    fireEvent.click(screen.getByRole('tab', { name: 'Tools' }));

    expect(await screen.findByText('create_dq_rule')).toBeInTheDocument();
    expect(localStorage.getItem('carbon-ai-agent-tab')).toBe('tools');

    fireEvent.click(screen.getByRole('tab', { name: 'Logs' }));
    expect(localStorage.getItem('carbon-ai-agent-tab')).toBe('logs');
  });

  it('renders a fresh Agents tab when the stored tab is restored', async () => {
    localStorage.setItem('carbon-ai-agent-tab', 'mcp');
    render(<AIAgentPanel conversationId="conv-1" />);

    expect(await screen.findByText('MCP servers')).toBeInTheDocument();
    expect(screen.getByText('brave')).toBeInTheDocument();
    expect(screen.queryByText('data_sweeper')).not.toBeInTheDocument();
  });
});

describe('AIAgentPanel — running agents and tools', () => {
  it('launches an agent run with the selected verbosity', async () => {
    render(<AIAgentPanel conversationId="conv-1" />);

    fireEvent.click(await screen.findByRole('button', { name: 'Run' }));

    await waitFor(() => {
      expect(runActionStream).toHaveBeenCalledWith(
        'test-token',
        'conv-1',
        expect.objectContaining({ action_type: 'agent', agent: 'data_sweeper', args: {}, verbosity: 'concise' }),
        expect.any(Object),
      );
    });
  });

  it('renders the args form for a tool and runs it with the entered args', async () => {
    render(<AIAgentPanel conversationId="conv-1" />);

    fireEvent.click(screen.getByRole('tab', { name: 'Tools' }));
    fireEvent.click(await screen.findByText('create_dq_rule'));

    const nameInput = screen.getByLabelText('name');
    fireEvent.change(nameInput, { target: { value: 'My rule' } });

    fireEvent.click(screen.getByRole('button', { name: 'Run tool' }));

    await waitFor(() => {
      expect(runActionStream).toHaveBeenCalledWith(
        'test-token',
        'conv-1',
        expect.objectContaining({
          action_type: 'tool',
          tool: 'create_dq_rule',
          args: expect.objectContaining({ name: 'My rule', enabled: true }),
          verbosity: 'concise',
        }),
        expect.any(Object),
      );
    });
  });

  it('creates an anchor conversation when none is open yet', async () => {
    render(<AIAgentPanel conversationId={null} />);

    fireEvent.click(await screen.findByRole('button', { name: 'Run' }));

    await waitFor(() => {
      expect(createConversation).toHaveBeenCalledWith('test-token', {
        conversation_type: 'chat',
        title: 'Agent run',
      });
    });
    await waitFor(() => {
      expect(runActionStream).toHaveBeenCalledWith(
        'test-token',
        'conv-new',
        expect.objectContaining({ action_type: 'agent' }),
        expect.any(Object),
      );
    });
  });

  it('switches verbosity to Full for the next run', async () => {
    render(<AIAgentPanel conversationId="conv-1" />);

    // Single combobox on the Agents tab — the verbosity Select.
    fireEvent.mouseDown(screen.getByRole('combobox'));
    fireEvent.click(await screen.findByRole('option', { name: 'Full' }));

    fireEvent.click(screen.getByRole('button', { name: 'Run' }));

    await waitFor(() => {
      expect(runActionStream).toHaveBeenCalledWith(
        'test-token',
        'conv-1',
        expect.objectContaining({ action_type: 'agent', agent: 'data_sweeper', verbosity: 'full' }),
        expect.any(Object),
      );
    });
  });
});

describe('AIAgentPanel — Logs tab', () => {
  it('renders ToolExecution + LLMCallLog rows from the Pulse read API', async () => {
    render(<AIAgentPanel conversationId="conv-1" />);

    fireEvent.click(screen.getByRole('tab', { name: 'Logs' }));

    expect(await screen.findByText('Tool executions')).toBeInTheDocument();
    expect(await screen.findByText('create_dq_rule')).toBeInTheDocument();
    expect(screen.getByText('AI call logs')).toBeInTheDocument();

    expect(getPulseData).toHaveBeenCalledWith('test-token', 'tools');
    expect(getPulseData).toHaveBeenCalledWith('test-token', 'logs');
  });
});

// ── AIActionRunner: clustered timeline ────────────────────────────────────
function captureHandlers() {
  let handlers;
  runActionStream.mockImplementation(async (token, convId, spec, h) => {
    handlers = h;
    return undefined;
  });
  return () => handlers;
}

function emit(handlers, frame) {
  act(() => {
    if (frame.type === 'turn_start') handlers.onTurnStart(frame);
    else if (frame.type === 'tool_start') handlers.onToolStart(frame);
    else if (frame.type === 'tool_arg') handlers.onToolArg(frame);
    else if (frame.type === 'tool_result') handlers.onToolResult(frame);
    else if (frame.type === 'tool_end') handlers.onToolEnd(frame);
    else if (frame.type === 'turn_end') handlers.onTurnEnd(frame);
    else if (frame.type === 'done') handlers.onDone(frame);
    else if (frame.type === 'stopped') handlers.onStopped(frame);
    else if (frame.type === 'error') handlers.onError(frame.error);
  });
}

const CONCISE_RUN = { runId: 1, action_type: 'agent', agent: 'data_sweeper', args: {}, verbosity: 'concise' };

describe('AIActionRunner — clustered timeline (design §2.5)', () => {
  it('collapses a 3-tool run to "Finished · 3 tools"', async () => {
    const getHandlers = captureHandlers();
    render(<AIActionRunner token="test-token" conversationId="conv-1" run={CONCISE_RUN} />);
    const handlers = getHandlers();

    emit(handlers, { type: 'turn_start', turn_id: 'turn-1', label: 'Run agent data_sweeper', verbosity: 'concise' });
    for (let step = 1; step <= 3; step += 1) {
      emit(handlers, { type: 'tool_start', turn_id: 'turn-1', step_id: step, tool: `tool_${step}`, category: 'agent' });
      emit(handlers, { type: 'tool_end', step_id: step, status: 'completed' });
    }
    emit(handlers, { type: 'turn_end', turn_id: 'turn-1', status: 'completed', summary: '3 step(s) completed' });

    expect(await screen.findByText('Finished · 3 tools')).toBeInTheDocument();
    expect(screen.getByText('Run agent data_sweeper')).toBeInTheDocument();
    expect(screen.getByText('tool_1')).toBeInTheDocument();
    expect(screen.getByText('tool_2')).toBeInTheDocument();
    expect(screen.getByText('tool_3')).toBeInTheDocument();
  });

  it('toggles each step card independently', async () => {
    const getHandlers = captureHandlers();
    render(<AIActionRunner token="test-token" conversationId="conv-1" run={{ ...CONCISE_RUN, verbosity: 'full' }} />);
    const handlers = getHandlers();

    emit(handlers, { type: 'turn_start', turn_id: 'turn-1', label: 'Run tool search_entity', verbosity: 'full' });
    emit(handlers, { type: 'tool_start', turn_id: 'turn-1', step_id: 1, tool: 'search_entity', category: 'tool' });
    emit(handlers, { type: 'tool_arg', step_id: 1, args: { q: 'carbon' } });
    emit(handlers, { type: 'tool_result', step_id: 1, result: { found: 2 } });
    emit(handlers, { type: 'tool_end', step_id: 1, status: 'completed' });

    expect(await screen.findByText('Input')).toBeInTheDocument();
    expect(screen.getByText('Output')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Toggle search_entity details' }));
    expect(screen.queryByText('Input')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Toggle search_entity details' }));
    expect(screen.getByText('Input')).toBeInTheDocument();
  });

  it('keeps step bodies collapsed by default in concise verbosity but expandable', async () => {
    const getHandlers = captureHandlers();
    render(<AIActionRunner token="test-token" conversationId="conv-1" run={CONCISE_RUN} />);
    const handlers = getHandlers();

    emit(handlers, { type: 'turn_start', turn_id: 'turn-1', label: 'Run tool search_entity', verbosity: 'concise' });
    emit(handlers, { type: 'tool_start', turn_id: 'turn-1', step_id: 1, tool: 'search_entity', category: 'tool' });
    emit(handlers, { type: 'tool_arg', step_id: 1, args: { q: 'carbon' } });
    emit(handlers, { type: 'tool_result', step_id: 1, result: { found: 2 } });
    emit(handlers, { type: 'tool_end', step_id: 1, status: 'completed' });

    expect(await screen.findByText('search_entity')).toBeInTheDocument();
    expect(screen.queryByText('Input')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Toggle search_entity details' }));
    expect(screen.getByText('Input')).toBeInTheDocument();
  });

  it('auto-expands step bodies in full verbosity', async () => {
    const getHandlers = captureHandlers();
    render(<AIActionRunner token="test-token" conversationId="conv-1" run={{ ...CONCISE_RUN, verbosity: 'full' }} />);
    const handlers = getHandlers();

    emit(handlers, { type: 'turn_start', turn_id: 'turn-1', label: 'Run tool search_entity', verbosity: 'full' });
    emit(handlers, { type: 'tool_start', turn_id: 'turn-1', step_id: 1, tool: 'search_entity', category: 'tool' });
    emit(handlers, { type: 'tool_arg', step_id: 1, args: { q: 'carbon' } });
    emit(handlers, { type: 'tool_end', step_id: 1, status: 'completed' });

    expect(await screen.findByText('Input')).toBeInTheDocument();
  });

  it('flips to "Stopped by you" on stop — inside the card, no red banner', async () => {
    const getHandlers = captureHandlers();
    render(<AIActionRunner token="test-token" conversationId="conv-1" run={CONCISE_RUN} />);
    const handlers = getHandlers();

    emit(handlers, { type: 'turn_start', turn_id: 'turn-1', label: 'Run agent data_sweeper', verbosity: 'concise' });
    emit(handlers, { type: 'tool_start', turn_id: 'turn-1', step_id: 1, tool: 'search_entity', category: 'agent' });
    expect(await screen.findByText('Working…')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Stop run' }));
    expect(stopGeneration).toHaveBeenCalledWith('test-token', 'conv-1');

    emit(handlers, { type: 'tool_end', step_id: 1, status: 'stopped' });
    emit(handlers, { type: 'turn_end', turn_id: 'turn-1', status: 'stopped', summary: 'Stopped by user' });
    emit(handlers, { type: 'stopped', conversation: { id: 'conv-1' } });

    expect(await screen.findByText('Stopped by you')).toBeInTheDocument();
    expect(screen.getAllByText(/Stopped by you/).length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByText('Run failed')).not.toBeInTheDocument();
  });

  it('surfaces a stream failure inline — never a full-width banner', async () => {
    const getHandlers = captureHandlers();
    render(<AIActionRunner token="test-token" conversationId="conv-1" run={CONCISE_RUN} />);
    const handlers = getHandlers();

    emit(handlers, { type: 'turn_start', turn_id: 'turn-1', label: 'Run agent data_sweeper', verbosity: 'concise' });
    emit(handlers, { type: 'tool_start', turn_id: 'turn-1', step_id: 1, tool: 'search_entity', category: 'agent' });
    emit(handlers, { type: 'error', error: 'Engine is warming up' });

    expect(await screen.findByText('Engine is warming up')).toBeInTheDocument();
    expect(screen.getByText('Run failed')).toBeInTheDocument();
  });
});

describe('AIActionRunner — confirm gate (RULE_21)', () => {
  it('renders Approve/Decline for a staged mutation and confirms via the API', async () => {
    const getHandlers = captureHandlers();
    render(<AIActionRunner token="test-token" conversationId="conv-1" run={CONCISE_RUN} />);
    const handlers = getHandlers();

    emit(handlers, { type: 'turn_start', turn_id: 'turn-1', label: 'Run tool create_dq_rule', verbosity: 'concise' });
    emit(handlers, { type: 'tool_start', turn_id: 'turn-1', step_id: 1, tool: 'create_dq_rule', category: 'tool' });
    emit(handlers, { type: 'tool_end', step_id: 1, status: 'needs_confirmation', execution_id: 'exec-1' });

    expect(await screen.findByText('Needs approval')).toBeInTheDocument();
    expect(screen.getByText(/This action writes to Carbon/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Approve' }));
    await waitFor(() => {
      expect(confirmToolExecution).toHaveBeenCalledWith('test-token', 'conv-1', 'exec-1');
    });
  });

  it('declines a staged mutation — nothing is written', async () => {
    const getHandlers = captureHandlers();
    render(<AIActionRunner token="test-token" conversationId="conv-1" run={CONCISE_RUN} />);
    const handlers = getHandlers();

    emit(handlers, { type: 'turn_start', turn_id: 'turn-1', label: 'Run tool create_dq_rule', verbosity: 'concise' });
    emit(handlers, { type: 'tool_start', turn_id: 'turn-1', step_id: 1, tool: 'create_dq_rule', category: 'tool' });
    emit(handlers, { type: 'tool_end', step_id: 1, status: 'needs_confirmation', execution_id: 'exec-1' });

    fireEvent.click(await screen.findByRole('button', { name: 'Decline' }));
    await waitFor(() => {
      expect(declineToolExecution).toHaveBeenCalledWith('test-token', 'conv-1', 'exec-1');
    });
  });
});
