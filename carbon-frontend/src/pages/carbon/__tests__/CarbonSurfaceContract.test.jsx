import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import CarbonConsolePage from '../CarbonConsolePage';
import { Scope2MethodChip } from '../Scope2Labels';

const fetchConsoleData = vi.fn();
vi.mock('../../../api/emissions', () => ({
  fetchConsoleData: (...args) => fetchConsoleData(...args),
}));

const dir = dirname(fileURLToPath(import.meta.url));

function source(relativePath) {
  return readFileSync(resolve(dir, relativePath), 'utf8');
}

describe('Carbon surface contract', () => {
  it('does not invent a location-based label when the method is blank', () => {
    render(<Scope2MethodChip method="" scope={2} />);
    expect(screen.getByText('Scope 2 method missing')).toBeTruthy();
    expect(screen.queryByText('Location-based')).toBeNull();
  });

  it('keeps dashboard, analytics, and the print report on theme tokens', () => {
    const files = [
      '../../EmissionsDashboard.jsx',
      '../../dashboards/AnalyticsDashboard.jsx',
      '../../EmissionsReport.jsx',
      '../CarbonConsolePage.jsx',
    ];
    for (const name of files) {
      const src = source(name);
      expect(src, name).not.toMatch(/fontSize\s*:/);
      expect(src, name).not.toMatch(/\bFONT\b/);
      expect(src, name).not.toMatch(/linear-gradient/);
      expect(src, name).not.toMatch(/#[0-9A-Fa-f]{3,8}\b/);
    }
    expect(source('../CarbonConsolePage.jsx')).toMatch(/import \{ useTheme \}/);
    expect(source('../../dashboards/AnalyticsDashboard.jsx')).not.toMatch(/method="location_based"/);
    expect(source('../../dashboards/AnalyticsDashboard.jsx')).toMatch(/setScopeFilter/);
  });

  it('renders the console status cards', async () => {
    fetchConsoleData.mockResolvedValue({
      active_period: {
        name: 'FY 2023-24',
        status: 'open',
        start_date: '2023-09-01',
        end_date: '2024-08-31',
        days_remaining: 40,
      },
      stats: {
        total_emissions_tonnes: 1247.639,
        total_calculations: 2,
        total_tables: 2,
        avg_quality_score: 90,
        total_modules: 1,
        by_scope2_method: { market_based: { present: false, reason: 'no_distinct_contractual_factor' } },
      },
      alerts: [],
      recent_activity: [],
    });
    render(
      <MemoryRouter>
        <CarbonConsolePage />
      </MemoryRouter>,
    );
    expect(await screen.findByText('FY 2023-24')).toBeTruthy();
    expect(screen.getByText('Location-based')).toBeTruthy();
    expect(screen.getByText(/Market-based Scope 2 is absent/)).toBeTruthy();
    expect(screen.queryByText(/0 kg/)).toBeNull();
  });
});

beforeEach(() => {
  fetchConsoleData.mockReset();
});
