// src/__tests__/EmissionsDashboard.notes.test.jsx
// Phase 3 — Emissions dashboard registers a notes entity context so the
// Notes composer is enabled:
//   - with a reporting_period in the payload → anchors to reporting_period
//   - without one (dashboard queries by year) → anchors to reporting_year
//   - on unmount → clears context back to the global view
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, act, fireEvent } from '@testing-library/react';
import { useEffect, useRef, useState } from 'react';

vi.mock('../api/api', () => ({
  apiFetch: vi.fn(),
}));

vi.mock('../api/emissions', () => ({
  fetchEmissionsDashboard: vi.fn(),
  triggerCalculations: vi.fn(),
}));

// The dashboard now attaches the Carbon Footprint domain app as a second
// anchor via useEnabledApps — mock the hook so no API call is made.
// The apps array is hoisted at module scope so its reference is stable
// across renders (the dashboard memoizes carbonApp off it).
vi.mock('../hooks/useEnabledApps', () => {
  const apps = [{ id: 1, app_id: 'carbon', name: 'Carbon Footprint', is_enabled: true }];
  return {
    useEnabledApps: () => ({ apps, loading: false, error: null }),
  };
});

// react-chartjs-2 needs a canvas 2D context — not available in jsdom.
vi.mock('react-chartjs-2', () => ({
  Line: () => null,
  Bar: () => null,
  Doughnut: () => null,
  Pie: () => null,
}));

import EmissionsDashboard from '../pages/EmissionsDashboard';
import { NotesProvider, useNotes } from '../notes/NotesContext';
import { fetchEmissionsDashboard } from '../api/emissions';

function ContextProbe({ onContext }) {
  const { context, contexts } = useNotes();
  const last = useRef(contexts);
  useEffect(() => {
    last.current = contexts;
    onContext?.(contexts);
  }, [contexts, onContext]);
  return <div data-testid="context-probe">{JSON.stringify(contexts)}</div>;
}

const PERIOD_PAYLOAD = {
  reporting_period: { id: 7, name: 'FY2026', start_date: '2026-01-01', end_date: '2026-12-31' },
  total_co2e_tonnes: 850.28,
  scope_breakdown: [],
  category_breakdown: [],
  monthly_trend: [],
  data_quality_score: 49,
  calculation_count: 18,
  last_updated: '2026-08-27T10:00:00Z',
};

const YEAR_PAYLOAD = {
  ...PERIOD_PAYLOAD,
  reporting_period: null, // dashboard API queried by year → no period object
};

// Renders the dashboard + probe inside a provider that OUTLIVES the
// dashboard, so unmounting the dashboard alone lets the provider process
// the `setContext(null)` cleanup and re-render the probe with null.
function Harness({ showDashboard, onContext }) {
  return (
    <NotesProvider>
      {showDashboard && <EmissionsDashboard />}
      <ContextProbe onContext={onContext} />
    </NotesProvider>
  );
}

function renderDashboard(payload) {
  let captured = 'UNSET';
  const result = render(<Harness showDashboard onContext={(c) => { captured = c; }} />);
  const unmountDashboard = () => {
    act(() => {
      result.rerender(<Harness showDashboard={false} onContext={(c) => { captured = c; }} />);
    });
  };
  return { result, unmountDashboard, getContext: () => captured };
}

// The Carbon Footprint app anchor (PlatformAppConfig id=1, from useEnabledApps).
const APP_ANCHOR = { entityType: 'app', entityId: 1, label: 'Carbon Footprint' };

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('EmissionsDashboard — notes entity context', () => {
  it('anchors to reporting_period + domain app when the payload includes a period', async () => {
    fetchEmissionsDashboard.mockResolvedValue(PERIOD_PAYLOAD);
    const { getContext } = renderDashboard(PERIOD_PAYLOAD);

    await waitFor(() => expect(fetchEmissionsDashboard).toHaveBeenCalled());
    // Let the setContexts effect run.
    await act(async () => {});

    const ctx = getContext();
    expect(ctx).toEqual([
      { entityType: 'reporting_period', entityId: 7, label: 'FY2026' },
      APP_ANCHOR,
    ]);
  });

  it('anchors to reporting_year + domain app when no period object is present', async () => {
    fetchEmissionsDashboard.mockResolvedValue(YEAR_PAYLOAD);
    const { getContext } = renderDashboard(YEAR_PAYLOAD);

    await waitFor(() => expect(fetchEmissionsDashboard).toHaveBeenCalled());
    await act(async () => {});

    const ctx = getContext();
    expect(ctx).toEqual([
      { entityType: 'reporting_year', entityId: 2026, label: 'Year 2026' },
      APP_ANCHOR,
    ]);
  });

  it('clears the contexts on unmount (back to global notes view)', async () => {
    fetchEmissionsDashboard.mockResolvedValue(PERIOD_PAYLOAD);
    const { unmountDashboard, getContext } = renderDashboard(PERIOD_PAYLOAD);

    await waitFor(() => expect(fetchEmissionsDashboard).toHaveBeenCalled());
    await act(async () => {});
    expect(getContext()).not.toEqual([]);

    unmountDashboard(); // provider stays mounted; only the dashboard leaves
    // Cleanup registers an empty anchor set → composer disabled, global feed.
    expect(getContext()).toEqual([]);
  });
});
