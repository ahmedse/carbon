import { describe, it, expect, vi, beforeEach } from 'vitest';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import CampusIntakePage from '../CampusIntakePage';

vi.mock('../../../auth/AuthContext', () => ({ useAuth: () => ({ token: 't' }) }));

const fetchCampusIntake = vi.fn();
vi.mock('../../../api/emissions-extended', () => ({
  fetchCampusIntake: (...args) => fetchCampusIntake(...args),
  uploadCampusIntake: vi.fn(),
  enterCampusStream: vi.fn(),
  recordDiscoveredActivity: vi.fn(),
}));

const LEAVES = {
  leaves: [
    {
      id: 'O2',
      title: 'South Valley electricity and diesel',
      outcome: 'b',
      kilograms: null,
      tonnes_co2e: '0',
      waiting: {
        file: 'south_valley_inventory.csv',
        exists: false,
        columns: ['campus', 'source_name', 'scope', 'activity_unit', 'quantity', 'stream', 'period_start', 'period_end'],
      },
      template_columns: ['campus', 'source_name'],
      discovered_files: ['south_valley_scope12_fy2526.csv'],
      activity_rows: [
        { label: 'Purchased electricity Electricity', quantity: '700000', unit: 'kWh', source_file: 'south_valley_scope12_fy2526.csv' },
      ],
      exclusions: [{ code: 'diesel_stream_both', generators_l: '25000', mobile_l: '125500' }],
    },
    {
      id: 'S2MB',
      title: 'Market-based Scope 2',
      method: 'absent',
      kilograms: null,
      tonnes_co2e: null,
      waiting: { file: 'ContractualScope2Factor', columns: ['factor_code'] },
      template_columns: [],
      activity_rows: [],
      exclusions: [{ code: 'market_absent' }],
    },
  ],
  coverage_complete: false,
  entry_period: { id: 1, name: 'FY 2023-24', start_date: '2023-07-01', end_date: '2024-06-30' },
  streams: [
    {
      id: 'O1:Smart Village electricity',
      leaf_id: 'O1',
      campus: 'Smart Village',
      source_name: 'Smart Village electricity',
      scope: 2,
      activity_type: 'electricity',
      activity_unit: 'kWh',
      method: 'location_based',
      status: 'entered',
      inventory_kg: null,
      later_year_files: [],
    },
    {
      id: 'O2:South Valley electricity',
      leaf_id: 'O2',
      campus: 'South Valley',
      source_name: 'South Valley electricity',
      scope: 2,
      activity_type: 'electricity',
      activity_unit: 'kWh',
      method: 'location_based',
      status: 'missing',
      inventory_kg: null,
      later_year_files: ['south_valley_scope12_fy2526.csv'],
    },
  ],
};

function renderPage() {
  return render(
    <MemoryRouter>
      <CampusIntakePage />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  fetchCampusIntake.mockReset();
});

describe('Campus intake', () => {
  it('quotes the discovered file and shows zero tonnes', async () => {
    fetchCampusIntake.mockResolvedValue(LEAVES);
    renderPage();
    expect(await screen.findByText(/700000/)).toBeInTheDocument();
    expect(screen.getByText(/south_valley_inventory.csv/)).toBeInTheDocument();
    expect(screen.getByText(/Inventory kilograms are absent/)).toBeInTheDocument();
    expect(screen.getByText(/25000/)).toBeInTheDocument();
    expect(screen.queryByText(/kg CO2e/)).not.toBeInTheDocument();
    expect(screen.queryByText(/^0 kg$/)).not.toBeInTheDocument();
    expect(screen.getByText(/not coverage complete/i)).toBeInTheDocument();
    expect(screen.getAllByText('South Valley electricity').length).toBeGreaterThan(0);
    expect(screen.getByText('Missing')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Save activity' })).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: /quantity/i })).toBeInTheDocument();
    expect(screen.getAllByText('south_valley_scope12_fy2526.csv').length).toBeGreaterThan(0);
  });

  it('shows a retry alert when the catalogue fails', async () => {
    fetchCampusIntake.mockRejectedValue(new Error('intake unavailable'));
    renderPage();
    expect(await screen.findByText(/intake unavailable/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
  });

  it('does not set page-local fontSize or hex', () => {
    const dir = dirname(fileURLToPath(import.meta.url));
    const src = readFileSync(resolve(dir, '..', 'CampusIntakePage.jsx'), 'utf8');
    expect(src).not.toMatch(/fontSize\s*:/);
    expect(src).not.toMatch(/#[0-9A-Fa-f]{3,8}\b/);
  });
});
