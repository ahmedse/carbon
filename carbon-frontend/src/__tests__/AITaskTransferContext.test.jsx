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
  sendMessage: vi.fn(),
}));

import { AITaskTransferProvider } from '../shell/AITaskTransferContext';
import { useAITaskTransfer } from '../shell/useAITaskTransfer';
import { createConversation, sendMessage } from '../api/aiWorkspace';

let transferTask;

function Capture() {
  transferTask = useAITaskTransfer().transferTask;
  return null;
}

beforeEach(() => {
  vi.clearAllMocks();
  createConversation.mockResolvedValue({ id: 'conv-1' });
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
});
