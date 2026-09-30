import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ChairmanDashboard from '../ChairmanDashboard';

vi.mock('react-chartjs-2', () => ({
  Line: () => null,
  Doughnut: () => null,
}));

const fetchChairmanData = vi.fn();
vi.mock('../../../api/emissions-extended', () => ({
  fetchChairmanData: (...args) => fetchChairmanData(...args),
}));

function renderPage() {
  return render(
    <MemoryRouter>
      <ChairmanDashboard />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  fetchChairmanData.mockReset();
  window.localStorage.setItem('access', 'test-token');
});

describe('Chairman dashboard O1 quote honesty', () => {
  it('warns that figures are not O1 and links to onboarding (O1-QUOTE)', async () => {
    fetchChairmanData.mockResolvedValue({
      headline: { footprint_tonnes: 12, coverage_covered: 1, coverage_total: 2, coverage_pct: 50 },
      period: { name: 'FY 2025', status: 'open' },
      sbti: {},
      coverage: {},
      scope_breakdown: [],
      actions: [],
    });
    renderPage();
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(/are not the O1/);
    expect(screen.getByRole('button', { name: 'Inventory onboarding' })).toBeInTheDocument();
    expect(screen.queryByText(/Goal: 100/)).toBeNull();
  });
});
