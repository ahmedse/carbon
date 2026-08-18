// src/__tests__/AIUsageTab.test.jsx
// Phase 21-B — Usage & cost panel: quota bar, period totals, tier/model
// breakdown, per-conversation table, and refetch on period change / refresh.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

vi.mock('../api/aiWorkspace', () => ({
  getUsageSummary: vi.fn(),
  getUsageByConversation: vi.fn(),
}));

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token' }),
}));

const { notifyFromError } = vi.hoisted(() => ({
  notifyFromError: vi.fn(),
}));

vi.mock('../components/NotificationProvider', () => ({
  useNotification: () => ({ notifyFromError, notify: vi.fn() }),
}));

import AIUsageTab, { formatTokens, formatCost } from '../shell/AIUsageTab';
import { getUsageSummary, getUsageByConversation } from '../api/aiWorkspace';

const summary = {
  period_days: 30,
  total_tokens: 1234500,
  prompt_tokens: 400000,
  completion_tokens: 834500,
  total_cost: '12.345678',
  total_generations: 42,
  by_tier: {
    analysis: { tokens: 700000, cost: '7.000000', generations: 20 },
    drafting: { tokens: 534500, cost: '5.345678', generations: 22 },
  },
  by_model: {
    'deepseek-v4-flash': { tokens: 900000, cost: '8.000000', generations: 30 },
    'gpt-4o-mini': { tokens: 334500, cost: '4.345678', generations: 12 },
  },
  quota: {
    limit: 2000000,
    used: 1234500,
    remaining: 765500,
    reset_at: '2026-09-01T00:00:00Z',
    window_start: '2026-08-01T00:00:00Z',
    pct: 61.725,
    soft_warning: false,
    hard_exceeded: false,
  },
};

const conversations = [
  {
    conversation_id: 'conv-1',
    title: 'Carbon budget analysis',
    total_tokens: 600000,
    total_cost: '6.000000',
    generation_count: 10,
    message_count: 24,
  },
  {
    conversation_id: 'conv-2',
    title: 'DQ rule drafting',
    total_tokens: 400000,
    total_cost: '4.000000',
    generation_count: 8,
    message_count: 15,
  },
];

beforeEach(() => {
  vi.clearAllMocks();
  getUsageSummary.mockResolvedValue(summary);
  getUsageByConversation.mockResolvedValue({ period_days: 30, conversations });
});

describe('AIUsageTab (Phase 21-B)', () => {
  it('renders the quota bar with used/limit, remaining, and reset date', async () => {
    render(<AIUsageTab />);

    expect(await screen.findByText(/1\.2M of 2\.0M used/)).toBeInTheDocument();
    expect(screen.getByText(/765\.5K remaining/)).toBeInTheDocument();
    expect(screen.getByText(/resets Sep 1, 2026/)).toBeInTheDocument();
    expect(screen.getByText('On track')).toBeInTheDocument();
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '62');
  });

  it('renders period totals for tokens, cost, and generations', async () => {
    render(<AIUsageTab />);

    expect(await screen.findByText('1.2M')).toBeInTheDocument();
    expect(screen.getByText('$12.35')).toBeInTheDocument();
    expect(screen.getByText('42')).toBeInTheDocument();
  });

  it('renders the tier and model breakdowns', async () => {
    render(<AIUsageTab />);

    expect(await screen.findByText('By tier')).toBeInTheDocument();
    expect(screen.getByText('By model')).toBeInTheDocument();
    expect(screen.getByText('analysis')).toBeInTheDocument();
    expect(screen.getByText('deepseek-v4-flash')).toBeInTheDocument();
    expect(screen.getByText(/700\.0K tok · \$7\.00/)).toBeInTheDocument();
    expect(screen.getByText(/900\.0K tok · \$8\.00/)).toBeInTheDocument();
  });

  it('renders the per-conversation table', async () => {
    render(<AIUsageTab />);

    expect(await screen.findByText('Carbon budget analysis')).toBeInTheDocument();
    expect(screen.getByText('DQ rule drafting')).toBeInTheDocument();
    expect(screen.getByText('600.0K')).toBeInTheDocument();
    expect(screen.getByText('$6.00')).toBeInTheDocument();
    expect(screen.getByRole('table')).toBeInTheDocument();
  });

  it('refetches with the new period when the period selector changes', async () => {
    render(<AIUsageTab />);

    await screen.findByText('1.2M');

    fireEvent.mouseDown(screen.getByLabelText('Period'));
    fireEvent.click(await screen.findByRole('option', { name: 'Last 7 days' }));

    await waitFor(() => {
      expect(getUsageSummary).toHaveBeenLastCalledWith('test-token', { period: '7d' });
      expect(getUsageByConversation).toHaveBeenLastCalledWith('test-token', { period: '7d' });
    });
  });

  it('refetches on Refresh and shows the updated cost', async () => {
    render(<AIUsageTab />);

    await screen.findByText('$12.35');

    getUsageSummary.mockResolvedValue({ ...summary, total_cost: '9.990000' });
    fireEvent.click(screen.getByRole('button', { name: 'Refresh' }));

    expect(await screen.findByText('$9.99')).toBeInTheDocument();
    expect(getUsageSummary).toHaveBeenCalledTimes(2);
  });

  it('shows an error state with Retry when the request fails', async () => {
    getUsageSummary.mockRejectedValue(new Error('boom'));
    getUsageByConversation.mockRejectedValue(new Error('boom'));

    render(<AIUsageTab />);

    expect(await screen.findByText('boom')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument();
  });

  it('shows an empty state when there is no usage in the period', async () => {
    getUsageSummary.mockResolvedValue({
      period_days: 7,
      total_tokens: 0,
      prompt_tokens: 0,
      completion_tokens: 0,
      total_cost: '0.000000',
      total_generations: 0,
      by_tier: {},
      by_model: {},
      quota: null,
    });
    getUsageByConversation.mockResolvedValue({ period_days: 7, conversations: [] });

    render(<AIUsageTab />);

    expect(await screen.findByText('No usage recorded in this period.')).toBeInTheDocument();
  });
});

describe('AIUsageTab formatting helpers', () => {
  it('humanizes token counts', () => {
    expect(formatTokens(1234500)).toBe('1.2M');
    expect(formatTokens(765500)).toBe('765.5K');
    expect(formatTokens(900)).toBe('900');
    expect(formatTokens(0)).toBe('0');
    expect(formatTokens('400000')).toBe('400.0K');
  });

  it('formats cost strings as dollars', () => {
    expect(formatCost('12.345678')).toBe('$12.35');
    expect(formatCost('0.000000')).toBe('$0.00');
    expect(formatCost('9.99')).toBe('$9.99');
  });
});
