// src/shell/AgentCanvasSurface.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import AgentCanvasSurface from './AgentCanvasSurface';

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ token: 't' }),
}));

vi.mock('../components/NotificationProvider', () => ({
  useNotification: () => ({ notifyFromError: vi.fn() }),
}));

vi.mock('../api/aiWorkspace', () => ({
  listArtifacts: vi.fn(),
}));

vi.mock('./OpsCanvasHost', () => ({
  default: function MockHost({ artifact }) {
    return <div data-testid="ops-canvas-host-mock">{artifact?.id}</div>;
  },
}));

import { listArtifacts } from '../api/aiWorkspace';

describe('AgentCanvasSurface', () => {
  beforeEach(() => {
    listArtifacts.mockReset();
  });

  it('shows empty state when no Job Map exists', async () => {
    listArtifacts.mockResolvedValue([]);
    render(<AgentCanvasSurface planId="plan-1" conversationId="c1" />);
    await waitFor(() => {
      expect(screen.getByTestId('agent-canvas-empty')).toBeInTheDocument();
    });
    expect(screen.queryByTestId('ops-canvas-host-mock')).toBeNull();
  });

  it('renders OpsCanvasHost for an Agent Job Map', async () => {
    listArtifacts.mockResolvedValue([
      {
        id: 'jm-1',
        artifact_type: 'job_map',
        content_json: { kind: 'job_map', mode: 'agent', layers: { job_map: { steps: [] } } },
      },
    ]);
    render(<AgentCanvasSurface planId="plan-1" />);
    await waitFor(() => {
      expect(screen.getByTestId('agent-canvas-board')).toBeInTheDocument();
    });
    expect(screen.getByTestId('ops-canvas-host-mock')).toHaveTextContent('jm-1');
    expect(listArtifacts).toHaveBeenCalledWith('t', expect.objectContaining({
      artifact_type: 'job_map',
      plan_id: 'plan-1',
    }));
  });

  it('falls back to conversation_id when plan_id Job Map is empty', async () => {
    listArtifacts.mockImplementation(async (_token, opts) => {
      if (opts?.conversation_id) {
        return [
          {
            id: 'jm-conv',
            artifact_type: 'job_map',
            content_json: {
              kind: 'job_map',
              mode: 'agent',
              plan_id: 'plan-1',
              layers: { job_map: { steps: [] } },
            },
          },
        ];
      }
      return [];
    });
    render(<AgentCanvasSurface planId="plan-1" conversationId="c1" />);
    await waitFor(() => {
      expect(screen.getByTestId('ops-canvas-host-mock')).toHaveTextContent('jm-conv');
    });
    expect(listArtifacts).toHaveBeenCalledWith('t', expect.objectContaining({
      conversation_id: 'c1',
    }));
  });

  it('retries after load failure', async () => {
    listArtifacts
      .mockRejectedValueOnce(new Error('boom'))
      .mockResolvedValueOnce([]);
    render(<AgentCanvasSurface planId="plan-1" />);
    await waitFor(() => {
      expect(screen.getByTestId('agent-canvas-error')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    await waitFor(() => {
      expect(screen.getByTestId('agent-canvas-empty')).toBeInTheDocument();
    });
  });
});
