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

  it('says when no period is open', async () => {
    fetchOnboardingO1.mockResolvedValue({
      benchmark: 'O1',
      open_period_id: null,
      checks: [{ id: 'CR-PER-01', code: 'open_period_count', met: false, count: 0 }],
    });
    renderPage();
    expect(await screen.findByText('No reporting period is open')).toBeInTheDocument();
    expect(screen.queryByText(/is not in the declared source list/)).not.toBeInTheDocument();
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
        { id: 'CR-PULSE-01', code: 'summary_kg', met: true, scope: '2', kg: '1500' },
        { id: 'CR-PULSE-01', code: 'not_assured', met: false },
      ],
    });
    renderPage();
    expect(await screen.findByText(/1500 kg CO2e, scope 2/)).toBeInTheDocument();
    expect(screen.getByText(/not external assurance/)).toBeInTheDocument();
  });

  it('shows an alert and retry when the checklist load fails', async () => {
    fetchOnboardingO1.mockRejectedValue(new Error('checklist unavailable'));
    renderPage();
    expect(await screen.findByRole('alert')).toHaveTextContent('checklist unavailable');
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument();
  });
});
