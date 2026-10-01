import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import OnboardingPage from '../OnboardingPage';

vi.mock('../../../auth/AuthContext', () => ({ useAuth: () => ({ token: 't' }) }));

const fetchOnboardingO1 = vi.fn();
vi.mock('../../../api/emissions-extended', () => ({
  fetchOnboardingO1: (...args) => fetchOnboardingO1(...args),
}));

function renderPage() {
  return render(
    <MemoryRouter>
      <OnboardingPage />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  fetchOnboardingO1.mockReset();
});

describe('Inventory onboarding', () => {
  it('does not show a checklist row while the load is in flight', () => {
    fetchOnboardingO1.mockReturnValue(new Promise(() => {}));
    renderPage();
    expect(screen.queryByText(/is not in the declared source list/)).not.toBeInTheDocument();
    expect(document.querySelector('.MuiSkeleton-root')).toBeTruthy();
  });

  it('lists each open period with dates and no footprint figure', async () => {
    // O1-USE-TWO
    fetchOnboardingO1.mockResolvedValue({
      benchmark: 'O1',
      open_period_id: null,
      checks: [{
        id: 'CR-PER-01',
        code: 'open_period_count',
        met: false,
        count: 2,
        periods: [
          {
            id: 15,
            name: 'FY 2023-24',
            period_type: 'annual',
            start_date: '2023-07-01',
            end_date: '2024-06-30',
            status: 'open',
          },
          {
            id: 16,
            name: 'FY 2025-26',
            period_type: 'annual',
            start_date: '2025-07-01',
            end_date: '2026-06-30',
            status: 'open',
          },
        ],
      }],
    });
    renderPage();
    expect(await screen.findByText(/FY 2023-24/)).toBeInTheDocument();
    expect(screen.getByText(/FY 2025-26/)).toBeInTheDocument();
    expect(screen.getByText(/2023-07-01 to 2024-06-30/)).toBeInTheDocument();
    expect(screen.getByText(/2025-07-01 to 2026-06-30/)).toBeInTheDocument();
    expect(screen.queryByText(/kg CO2e/)).not.toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent(/does not lock it/);
    expect(screen.getByRole('alert')).toHaveTextContent(/Lock, not Close/);
    expect(screen.getByRole('button', { name: 'Open periods' })).toBeInTheDocument();
  });

  it('says when no period is open', async () => {
    fetchOnboardingO1.mockResolvedValue({
      benchmark: 'O1',
      open_period_id: null,
      checks: [{ id: 'CR-PER-01', code: 'open_period_count', met: false, count: 0 }],
    });
    renderPage();
    expect(await screen.findByText('No reporting period is open')).toBeInTheDocument();
    expect(screen.queryByText(/is not in the declared source list/)).not.toBeInTheDocument();
    expect(screen.queryByText(/does not lock it/)).not.toBeInTheDocument();
  });

  it('names both sources as missing and shows no kilogram figure', async () => {
    fetchOnboardingO1.mockResolvedValue({
      benchmark: 'O1',
      open_period_id: 7,
      checks: [
        { id: 'CR-PER-01', code: 'open_period_met', met: true, name: 'AY 2026', start: '2026-01-01', end: '2026-12-31', period_type: 'annual' },
        { id: 'CR-BND-01', code: 'boundary_missing', met: false },
        { id: 'CR-SRC-01', code: 'source_missing', met: false, name: 'Smart Village electricity', scope: 2 },
        { id: 'CR-SRC-01', code: 'source_missing', met: false, name: 'Smart Village diesel', scope: 1 },
        { id: 'CR-PULSE-01', code: 'no_calculation', met: false },
      ],
    });
    renderPage();
    expect(await screen.findByText('Smart Village electricity (scope 2) is not in the declared source list.')).toBeInTheDocument();
    expect(screen.getByText('Smart Village diesel (scope 1) is not in the declared source list.')).toBeInTheDocument();
    expect(screen.queryByText(/kg CO2e/)).not.toBeInTheDocument();
    expect(screen.getByText(/No calculation exists for this period/)).toBeInTheDocument();
  });

  it('shows kilograms from the summary and the assurance limit', async () => {
    fetchOnboardingO1.mockResolvedValue({
      benchmark: 'O1',
      open_period_id: 7,
      checks: [
        { id: 'CR-PULSE-01', code: 'summary_kg', met: true, scope: '2', kg: '1500', method: 'location-based' },
        { id: 'CR-PULSE-01', code: 'not_assured', met: false },
      ],
    });
    renderPage();
    expect(await screen.findByText(/1500 kg CO2e, scope 2 \(location-based\)/)).toBeInTheDocument();
    expect(screen.getByText(/not external assurance/)).toBeInTheDocument();
  });

  it('shows an alert and retry when the checklist load fails', async () => {
    // O1-REL-RETRY
    fetchOnboardingO1.mockRejectedValue(new Error('checklist unavailable'));
    renderPage();
    expect(await screen.findByRole('alert')).toHaveTextContent('checklist unavailable');
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument();
  });

  it('renders factor and coverage goal met lines without factor value or percent', async () => {
    fetchOnboardingO1.mockResolvedValue({
      benchmark: 'O1',
      open_period_id: 7,
      checks: [
        {
          code: 'factor_met',
          met: true,
          name: 'Grid Egypt',
          id: 'CR-FAC-01',
          record_id: 4,
          scope: 2,
          unit: 'kWh',
          country_code: 'EGY',
          factor_value: '0.42',
        },
        {
          code: 'coverage_goal_met',
          met: true,
          name: 'SV goal',
          id: 'CR-COV-01',
          record_id: 9,
          target_year: 2026,
          tier: 4,
          status: 'draft',
        },
      ],
    });
    renderPage();
    expect(await screen.findByText(/Grid Egypt/)).toBeInTheDocument();
    expect(screen.getByText(/2026/)).toBeInTheDocument();
    expect(screen.queryByText(/0\.42/)).not.toBeInTheDocument();
    expect(screen.queryByText(/CR-FAC-01/)).not.toBeInTheDocument();
    expect(screen.queryByText(/%/)).not.toBeInTheDocument();
  });

  it('names closed leaves and does not show a tonne', async () => {
    fetchOnboardingO1.mockResolvedValue({
      benchmark: 'O1',
      open_period_id: 1,
      checks: [],
    });
    renderPage();
    expect(await screen.findByText(/south_valley_inventory.csv is absent/)).toBeInTheDocument();
    expect(screen.getByText(/abu_qir_inventory.csv is absent/)).toBeInTheDocument();
    expect(screen.getByText(/new_alamein_inventory.csv is absent/)).toBeInTheDocument();
    expect(screen.getByText(/shape_only/)).toBeInTheDocument();
    expect(screen.getAllByText(/0 tCO2e/).length).toBeGreaterThan(0);
    expect(screen.queryByText(/kg CO2e/)).not.toBeInTheDocument();
  });
});
