// src/__tests__/healthy/SlowMoversPage.test.jsx
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import SlowMoversPage from '../../apps/healthy/SlowMoversPage';
import { fetchSlowMovers } from '../../api/healthy';

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token' }),
}));
vi.mock('../../api/healthy', () => ({
  fetchSlowMovers: vi.fn(),
}));

// jsdom has no ResizeObserver — StandardDataGrid needs a stub.
class FakeResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

beforeEach(() => {
  global.ResizeObserver = FakeResizeObserver;
  fetchSlowMovers.mockReset();
});

afterEach(() => {
  delete global.ResizeObserver;
});

describe('SlowMoversPage', () => {
  it('renders the heatmap and alert table with severity labels', async () => {
    fetchSlowMovers.mockResolvedValue({
      results: [
        { prediction_id: 1, item_code: 'SKU-001', demand_forecast_4w: 0 },
        { prediction_id: 2, item_code: 'SKU-002', demand_forecast_4w: 5 },
        { prediction_id: 3, item_code: 'SKU-003', demand_forecast_4w: 40 },
      ],
    });

    render(
      <MemoryRouter>
        <SlowMoversPage />
      </MemoryRouter>,
    );

    // item_code appears in both the heatmap and the alert table
    expect((await screen.findAllByText('SKU-001')).length).toBeGreaterThan(0);
    expect(screen.getByText('Dead stock')).toBeInTheDocument();
    expect(screen.getByText('Slow mover')).toBeInTheDocument();
    expect(screen.getByText('Moving')).toBeInTheDocument();
  });

  it('shows an empty state when there are no slow movers', async () => {
    fetchSlowMovers.mockResolvedValue({ results: [] });
    render(
      <MemoryRouter>
        <SlowMoversPage />
      </MemoryRouter>,
    );
    expect(await screen.findByText('No slow movers')).toBeInTheDocument();
  });
});
