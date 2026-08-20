// src/__tests__/healthy/RepHealthPage.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import RepHealthPage from '../../apps/healthy/RepHealthPage';
import { fetchRepHealth } from '../../api/healthy';

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token' }),
}));
vi.mock('../../api/healthy', () => ({
  fetchRepHealth: vi.fn(),
}));

describe('RepHealthPage', () => {
  beforeEach(() => {
    fetchRepHealth.mockReset();
  });

  it('renders rep cards with churn risk badges and metrics', async () => {
    fetchRepHealth.mockResolvedValue({
      results: [
        {
          id: 1,
          week_start: '2026-01-05',
          rep_code: 'R1',
          churn_probability: 0.75,
          active_customer_count: 40,
          visit_coverage: 0.9,
          avg_order_value: 250,
          ar_overdue_amount: 1200,
        },
        {
          id: 2,
          week_start: '2026-01-05',
          rep_code: 'R2',
          churn_probability: 0.15,
          active_customer_count: 55,
          visit_coverage: 0.8,
          avg_order_value: 300,
          ar_overdue_amount: 0,
        },
      ],
    });

    render(
      <MemoryRouter>
        <RepHealthPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText('R1')).toBeInTheDocument();
    expect(screen.getByText('R2')).toBeInTheDocument();
    expect(screen.getByText('75% churn · High risk')).toBeInTheDocument();
    expect(screen.getByText('15% churn · Low risk')).toBeInTheDocument();
    expect(screen.getByText('$250')).toBeInTheDocument();
  });

  it('shows an empty state when there are no cards', async () => {
    fetchRepHealth.mockResolvedValue({ results: [] });
    render(
      <MemoryRouter>
        <RepHealthPage />
      </MemoryRouter>,
    );
    expect(await screen.findByText('No rep health cards yet')).toBeInTheDocument();
  });
});
