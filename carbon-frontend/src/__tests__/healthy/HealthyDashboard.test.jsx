// src/__tests__/healthy/HealthyDashboard.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import HealthyDashboard from '../../apps/healthy/HealthyDashboard';
import { fetchHealthySummary } from '../../api/healthy';

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token', user: { username: 'testuser' } }),
}));
vi.mock('../../api/healthy', () => ({
  fetchHealthySummary: vi.fn(),
}));

describe('HealthyDashboard', () => {
  beforeEach(() => {
    fetchHealthySummary.mockReset();
  });

  it('renders KPI cards and pipeline rows after load', async () => {
    fetchHealthySummary.mockResolvedValue({
      pipelines: { returns: 2, churn: 1, 'sales-lines': 0, 'ar-aging': 3, 'transaction-classifier': 1 },
      snapshots_done: 7,
      predictions: 120,
      loadout_sheets: 4,
      rep_health_cards: 6,
      dataset_versions: 2,
    });

    render(
      <MemoryRouter>
        <HealthyDashboard />
      </MemoryRouter>,
    );

    expect(await screen.findByText('Forecasts ready')).toBeInTheDocument();
    expect(screen.getByText('Data pipelines')).toBeInTheDocument();
    expect(screen.getByText('Returns / load-out demand')).toBeInTheDocument();
    // Outcome copy (RULE_23) — never internal pipeline language
    expect(screen.getAllByText('Forecast ready').length).toBeGreaterThan(0);
  });

  it('shows an error alert on failure', async () => {
    fetchHealthySummary.mockRejectedValue(new Error('boom'));
    render(
      <MemoryRouter>
        <HealthyDashboard />
      </MemoryRouter>,
    );
    expect(await screen.findByText('boom')).toBeInTheDocument();
  });

  it('shows an empty state when there is no summary', async () => {
    fetchHealthySummary.mockResolvedValue(null);
    render(
      <MemoryRouter>
        <HealthyDashboard />
      </MemoryRouter>,
    );
    expect(await screen.findByText('No dashboard data yet')).toBeInTheDocument();
  });
});
