/**
 * Ask|Plan dial flips the conversation (separate sessions), not a flag on one thread.
 * Shell tests mock AIConversationView away — exercise the workspace handler here.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token', userCapabilities: [], isGlobalAdminFlag: false }),
}));

vi.mock('../components/NotificationProvider', () => ({
  useNotification: () => ({ notifyFromError: vi.fn(), notify: vi.fn(), showFeedback: vi.fn() }),
}));

vi.mock('../shell/useAITaskTransfer', () => ({
  useAITaskTransfer: () => ({ pendingTransferId: null, clearPendingTransfer: vi.fn() }),
}));

vi.mock('../shell/AIWorkspaceHeader', () => ({
  default: () => <div data-testid="header" />,
}));

vi.mock('../shell/AIConversationView', () => ({
  default: ({ process, processSwitching, onProcessChange }) => (
    <div
      data-testid="conversation-view"
      data-process={process}
      data-switching={String(Boolean(processSwitching))}
    >
      <button type="button" onClick={() => onProcessChange?.('plan')}>
        flip-to-plan
      </button>
      <button type="button" onClick={() => onProcessChange?.('ask')}>
        flip-to-ask
      </button>
    </div>
  ),
}));

vi.mock('../shell/AITaskPanel', () => ({
  default: () => <div data-testid="task-panel" />,
}));

vi.mock('../api/aiPulse', () => ({
  listDomainManifests: vi.fn().mockResolvedValue({ apps: [] }),
}));

vi.mock('../api/aiWorkspace', () => ({
  listConversations: vi.fn(),
  createConversation: vi.fn(),
  updateConversation: vi.fn(),
  deleteConversation: vi.fn(),
  sendMessage: vi.fn(),
  findOpenConversation: vi.fn(),
  listModels: vi.fn(() => Promise.resolve({ models: [] })),
}));

import { AIWorkspace } from '../shell/AIWorkspace';
import { createConversation, listConversations } from '../api/aiWorkspace';

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  listConversations.mockResolvedValue([
    {
      id: 'conv-ask',
      title: 'Ask thread',
      conversation_type: 'chat',
      status: 'completed',
      task_payload_json: { pulse_process: 'ask' },
    },
  ]);
  createConversation.mockResolvedValue({
    id: 'conv-plan',
    conversation_type: 'chat',
    title: 'Plan',
    task_payload_json: { pulse_process: 'plan' },
  });
});

describe('AIWorkspace Ask|Plan separate sessions', () => {
  it('Plan dial creates a Plan-tagged conversation instead of tagging the Ask thread', async () => {
    render(<AIWorkspace onClose={vi.fn()} />);
    expect(await screen.findByTestId('conversation-view')).toHaveAttribute(
      'data-process',
      'ask',
    );

    fireEvent.click(screen.getByRole('button', { name: 'flip-to-plan' }));

    await waitFor(() => {
      expect(createConversation).toHaveBeenCalledWith('test-token', {
        conversation_type: 'chat',
        title: 'Plan',
        task_payload: { pulse_process: 'plan' },
      });
    });
    await waitFor(() => {
      expect(screen.getByTestId('conversation-view')).toHaveAttribute(
        'data-process',
        'plan',
      );
    });
    expect(localStorage.getItem('carbon-ai-composer-process')).toBe('plan');
  });

  it('does not expose Plan on the Ask thread while the Plan thread is being created', async () => {
    let resolveCreate;
    createConversation.mockReturnValueOnce(new Promise((resolve) => {
      resolveCreate = resolve;
    }));
    render(<AIWorkspace onClose={vi.fn()} />);
    const view = await screen.findByTestId('conversation-view');
    expect(view).toHaveAttribute('data-process', 'ask');

    fireEvent.click(screen.getByRole('button', { name: 'flip-to-plan' }));

    await waitFor(() => {
      expect(screen.getByTestId('conversation-view')).toHaveAttribute(
        'data-switching',
        'true',
      );
    });
    // Critical invariant: Plan controls are never attached to conv-ask.
    expect(screen.getByTestId('conversation-view')).toHaveAttribute(
      'data-process',
      'ask',
    );

    resolveCreate({
      id: 'conv-plan',
      conversation_type: 'chat',
      title: 'Plan',
      task_payload_json: { pulse_process: 'plan' },
    });
    await waitFor(() => {
      expect(screen.getByTestId('conversation-view')).toHaveAttribute(
        'data-process',
        'plan',
      );
      expect(screen.getByTestId('conversation-view')).toHaveAttribute(
        'data-switching',
        'false',
      );
    });
  });
});
