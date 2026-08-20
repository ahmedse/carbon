// src/__tests__/healthy/ARQueuePage.test.jsx
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ARQueuePage from '../../apps/healthy/ARQueuePage';
import { fetchARQueue } from '../../api/healthy';

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token' }),
}));
vi.mock('../../api/healthy', () => ({
  fetchARQueue: vi.fn(),
}));

// jsdom has no ResizeObserver — StandardDataGrid needs a stub.
class FakeResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

beforeEach(() => {
  global.ResizeObserver = FakeResizeObserver;
  fetchARQueue.mockReset();
});

afterEach(() => {
  delete global.ResizeObserver;
});

describe('ARQueuePage', () => {
  it('renders the priority table with risk chips and currency', async () => {
    fetchARQueue.mockResolvedValue({
      results: [
        { prediction_id: 1, customer_code: 'ACME-01', risk_score: 0.92, days_overdue: 45, amount_overdue: 12000 },
        { prediction_id: 2, customer_code: 'ACME-02', risk_score: 0.3, days_overdue: 10, amount_overdue: 500 },
      ],
    });

    render(
      <MemoryRouter>
        <ARQueuePage />
      </MemoryRouter>,
    );

    expect(await screen.findByText('ACME-01')).toBeInTheDocument();
    expect(screen.getByText('ACME-02')).toBeInTheDocument();
    expect(screen.getByText('High · 92%')).toBeInTheDocument();
    expect(screen.getByText('Low · 30%')).toBeInTheDocument();
    expect(screen.getByText('$12,000')).toBeInTheDocument();
  });

  it('shows an empty state when the queue is empty', async () => {
    fetchARQueue.mockResolvedValue({ results: [] });
    render(
      <MemoryRouter>
        <ARQueuePage />
      </MemoryRouter>,
    );
    expect(await screen.findByText('No overdue accounts')).toBeInTheDocument();
  });
});
