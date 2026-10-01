import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
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
      scope_breakdown: [
        { scope: 2, scope_name: 'Scope 2', co2e_tonnes: 12, percentage: 100, scope2_method: 'location-based' },
      ],
      actions: [],
    });
    renderPage();
    const alerts = await screen.findAllByRole('alert');
    expect(alerts[0]).toHaveTextContent(/are not the O1/);
    expect(alerts.some((el) => /Market-based Scope 2 is absent/.test(el.textContent))).toBe(true);
    expect(screen.getByRole('button', { name: 'Inventory onboarding' })).toBeInTheDocument();
    expect(screen.getByText(/Scope 2 method: Location-based/)).toBeInTheDocument();
    expect(screen.queryByText(/Goal: 100/)).toBeNull();
  });

  it('does not set page-local fontSize on chairman, console, or onboarding', () => {
    const dir = dirname(fileURLToPath(import.meta.url));
    for (const name of ['ChairmanDashboard.jsx', 'CarbonConsolePage.jsx', 'OnboardingPage.jsx']) {
      const src = readFileSync(resolve(dir, '..', name), 'utf8');
      expect(src, name).not.toMatch(/fontSize\s*:/);
      expect(src, name).not.toMatch(/\bFONT\b/);
    }
  });
});
