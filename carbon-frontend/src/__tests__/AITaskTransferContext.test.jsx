// src/__tests__/AITaskTransferContext.test.jsx
// Phase 7C — enrichPayload normalization for entity-scoped task types
// (dq_validate / investigate / report_draft / chat).
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, act } from '@testing-library/react';

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token' }),
}));

vi.mock('../components/NotificationProvider', () => ({
  useNotification: () => ({ notifyFromError: vi.fn() }),
}));

vi.mock('../api/aiWorkspace', () => ({
  createConversation: vi.fn(),
  findOpenConversation: vi.fn(),
  sendMessage: vi.fn(),
}));

vi.mock('../api/aiPulse', () => ({
  listDomainManifests: vi.fn(),
}));

import { AITaskTransferProvider } from '../shell/AITaskTransferContext';
import { useAITaskTransfer } from '../shell/useAITaskTransfer';
import { createConversation, findOpenConversation, sendMessage } from '../api/aiWorkspace';
import { listDomainManifests } from '../api/aiPulse';
import { __resetAppIdentifierCache } from '../shell/aiTaskTransferUtils';

let transferTask;

function Capture() {
  transferTask = useAITaskTransfer().transferTask;
  return null;
}

beforeEach(() => {
  vi.clearAllMocks();
  __resetAppIdentifierCache();
  createConversation.mockResolvedValue({ id: 'conv-1' });
  findOpenConversation.mockResolvedValue(null);
  listDomainManifests.mockResolvedValue({
    apps: [{ app_identifier: 'emissions' }, { app_identifier: 'water' }],
  });
  transferTask = null;
});

async function dispatch(type, payload, metadata) {
  render(
    <AITaskTransferProvider>
      <Capture />
    </AITaskTransferProvider>,
  );
  await act(async () => {
    await transferTask(type, payload, metadata);
  });
  return createConversation.mock.calls[0][1];
}

describe('AITaskTransferContext enrichPayload (Phase 7C)', () => {
  it('normalizes dq_validate with table + module fields', async () => {
    const body = await dispatch(
      'dq_validate',
      { table_id: 't1', table_name: 'Emissions Fuel', row_count: 100, module_id: 'm1', module_name: 'M' },
      { app_identifier: 'emissions' },
    );

    expect(body.task_payload).toEqual({
      type: 'dq_validate',
      table_id: 't1',
      table_name: 'Emissions Fuel',
      row_count: 100,
      module_id: 'm1',
      module_name: 'M',
    });
    expect(body.app_identifier).toBe('emissions');
  });

  it('defaults investigate fields to null when absent', async () => {
    const body = await dispatch(
      'investigate',
      {},
      { app_identifier: 'emissions' },
    );

    expect(body.task_payload).toEqual({
      type: 'investigate',
      table_id: null,
      table_name: null,
      row_count: null,
      module_id: null,
      module_name: null,
    });
  });

  it('normalizes report_draft with module + optional period', async () => {
    const body = await dispatch(
      'report_draft',
      { module_id: 'm1', module_name: 'Scope 2 Electricity' },
      { app_identifier: 'emissions' },
    );

    expect(body.task_payload).toEqual({
      type: 'report_draft',
      module_id: 'm1',
      module_name: 'Scope 2 Electricity',
      period_id: null,
    });
  });

  it('normalizes chat with table + module fields', async () => {
    const body = await dispatch(
      'chat',
      { table_id: 't1' },
      { app_identifier: 'emissions' },
    );

    expect(body.task_payload).toEqual({
      type: 'chat',
      table_id: 't1',
      table_name: null,
      module_id: null,
      module_name: null,
    });
  });

  // Phase 9-B — one-click investigate trigger.
  it('sends the investigate sentinel when transferring investigate with a table', async () => {
    const body = await dispatch(
      'investigate',
      { table_id: 't1', table_name: 'Emissions' },
      { app_identifier: 'emissions' },
    );

    expect(body.task_payload).toEqual({
      type: 'investigate',
      table_id: 't1',
      table_name: 'Emissions',
      row_count: null,
      module_id: null,
      module_name: null,
    });
    expect(sendMessage).toHaveBeenCalledWith(
      'test-token',
      'conv-1',
      'Investigate this table',
    );
  });

  it('does not send the sentinel when investigate has no table', async () => {
    await dispatch('investigate', {}, { app_identifier: 'emissions' });

    expect(sendMessage).not.toHaveBeenCalled();
  });

  // Phase 10-B — one-click report_draft trigger.
  it('sends the report sentinel when transferring report_draft with a module', async () => {
    const body = await dispatch(
      'report_draft',
      { module_id: 'm1', module_name: 'Scope 2 Electricity' },
      { app_identifier: 'emissions' },
    );

    expect(body.task_payload).toEqual({
      type: 'report_draft',
      module_id: 'm1',
      module_name: 'Scope 2 Electricity',
      period_id: null,
    });
    expect(sendMessage).toHaveBeenCalledWith(
      'test-token',
      'conv-1',
      'Draft this report',
    );
  });

  it('does not send the sentinel when report_draft has no module or period', async () => {
    await dispatch('report_draft', {}, { app_identifier: 'emissions' });

    expect(sendMessage).not.toHaveBeenCalled();
  });

  // Manifest-driven app resolution (replaces the hard-coded Set(['emissions'])).
  it('resolves a newly-installed app id from the manifest registry (water)', async () => {
    const body = await dispatch('chat', {}, { app_identifier: 'water' });

    expect(body.app_identifier).toBe('water');
  });

  it('drops an unknown app id to platform scope (null)', async () => {
    const body = await dispatch('chat', {}, { app_identifier: 'bogus-app' });

    expect(body.app_identifier).toBeNull();
  });

  it('derives app_identifier from a source_page slug naming a registered app', async () => {
    const body = await dispatch('chat', {}, { source_page: 'emissions-report-generator' });

    expect(body.app_identifier).toBe('emissions');
  });

  // Phase 16 — resume the most recent open thread of the same kind.
  it('resumes an existing open thread instead of creating a new one', async () => {
    findOpenConversation.mockResolvedValue({
      id: 'existing-1',
      conversation_type: 'investigate',
      app_identifier: 'emissions',
    });

    render(
      <AITaskTransferProvider>
        <Capture />
      </AITaskTransferProvider>,
    );
    await act(async () => {
      await transferTask(
        'investigate',
        { table_id: 't1', table_name: 'Emissions' },
        { app_identifier: 'emissions' },
      );
    });

    expect(createConversation).not.toHaveBeenCalled();
    expect(findOpenConversation).toHaveBeenCalledWith('test-token', {
      conversation_type: 'investigate',
      app_identifier: 'emissions',
      // Resume lookup is scoped to the transferred entity so a generic chat
      // never hijacks a thread that belongs to a different table/module.
      entityScope: { table_id: 't1' },
    });
    // Auto-send still fires into the resumed thread.
    expect(sendMessage).toHaveBeenCalledWith(
      'test-token',
      'existing-1',
      'Investigate this table',
    );
  });

  it('scopes the chat resume lookup to the module when transferring from a data product', async () => {
    findOpenConversation.mockResolvedValue({
      id: 'existing-2',
      conversation_type: 'chat',
    });

    render(
      <AITaskTransferProvider>
        <Capture />
      </AITaskTransferProvider>,
    );
    await act(async () => {
      await transferTask(
        'chat',
        { module_id: 'm7', module_name: 'Scope 2 Electricity' },
        { title: 'Ask about: Scope 2 Electricity' },
      );
    });

    expect(createConversation).not.toHaveBeenCalled();
    expect(findOpenConversation).toHaveBeenCalledWith('test-token', {
      conversation_type: 'chat',
      app_identifier: undefined,
      entityScope: { module_id: 'm7' },
    });
  });

  it('does not pass an entity scope for payloads with no entity identity', async () => {
    await dispatch('investigate', {}, { app_identifier: 'emissions' });

    expect(findOpenConversation).toHaveBeenCalledWith('test-token', {
      conversation_type: 'investigate',
      app_identifier: 'emissions',
    });
  });

  it('creates a new conversation when no open thread exists', async () => {
    findOpenConversation.mockResolvedValue(null);

    const body = await dispatch('investigate', {}, { app_identifier: 'emissions' });

    expect(createConversation).toHaveBeenCalledTimes(1);
    expect(body.conversation_type).toBe('investigate');
  });
});
