import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import DiscoveryComposer from '../DiscoveryComposer';

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({ token: 't' }),
}));
vi.mock('../../components/NotificationProvider', () => ({
  useNotification: () => ({ notifyFromError: vi.fn() }),
}));

const startDiscoveryPlan = vi.fn();
const advanceDiscovery = vi.fn();
const finalizeDiscovery = vi.fn();
vi.mock('../../api/aiWorkspace', () => ({
  startDiscoveryPlan: (...a) => startDiscoveryPlan(...a),
  advanceDiscovery: (...a) => advanceDiscovery(...a),
  finalizeDiscovery: (...a) => finalizeDiscovery(...a),
}));

vi.mock('../AIMessageBubble', () => ({
  default: ({ message }) => <div data-testid="bubble">{message.content}</div>,
}));
vi.mock('../AIWorkingIndicator', () => ({ default: () => null }));
vi.mock('../AIInputBar', () => ({
  default: ({ onSend }) => (
    <button type="button" onClick={() => onSend('أريد عمل اجازه')}>
      send-brief
    </button>
  ),
}));

describe('DiscoveryComposer scope gate', () => {
  beforeEach(() => {
    startDiscoveryPlan.mockReset();
    advanceDiscovery.mockReset();
    finalizeDiscovery.mockReset();
  });

  it('shows recommended leave cards and does not enable Plan now', async () => {
    startDiscoveryPlan.mockResolvedValue({
      id: null,
      status: 'recommended',
      plannable: false,
      route: {
        class: 'TRANSACTION',
        message: 'That sounds like a personal leave request.',
        recommended: 'leave_request',
        plannable: false,
        cards: [
          { id: 'leave_request', label: 'Request personal leave', primary: true },
          { id: 'compliance_report', label: 'Plan a leave-compliance report', primary: false },
        ],
      },
      turns: [],
    });

    render(<DiscoveryComposer conversationId="c1" />);
    fireEvent.click(screen.getByRole('button', { name: 'send-brief' }));

    expect(await screen.findByTestId('scope-route-card')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Request personal leave/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Plan now' })).not.toBeInTheDocument();
  });
});
