// src/__tests__/healthy/LoadoutSheetPage.test.jsx
// W6-B5 — hardened per-test isolation. The page mounts StandardDataGrid
// (ResizeObserver) and fires two dependent effects (weeks → week rows), so
// every test resets mock state explicitly, installs a ResizeObserver stub,
// and restores document globals it touched — eliminating cross-test flakes
// regardless of pool/worker reuse.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import LoadoutSheetPage from '../../apps/healthy/LoadoutSheetPage';

// Stable mock identities (hoisted) so per-test resets never race with module
// state shared across the parallel runner.
const { fetchLoadoutSheets, fetchLoadoutWeek } = vi.hoisted(() => ({
  fetchLoadoutSheets: vi.fn(),
  fetchLoadoutWeek: vi.fn(),
}));

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token' }),
}));
vi.mock('../../api/healthy', () => ({
  fetchLoadoutSheets,
  fetchLoadoutWeek,
}));

// jsdom has no ResizeObserver — StandardDataGrid needs a stub.
class FakeResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

const originalDocumentTitle = typeof document !== 'undefined' ? document.title : '';

beforeEach(() => {
  // Fresh per-test isolation: no leaked mock calls/implementations.
  vi.clearAllMocks();
  fetchLoadoutSheets.mockReset();
  fetchLoadoutWeek.mockReset();
  global.ResizeObserver = FakeResizeObserver;
  document.title = originalDocumentTitle;
});

afterEach(() => {
  delete global.ResizeObserver;
  document.title = originalDocumentTitle;
});

describe('LoadoutSheetPage', () => {
  it('renders rep table, item rows and export action for the selected week', async () => {
    fetchLoadoutSheets.mockResolvedValue({
      results: [
        { id: 1, week_start: '2026-01-05', rep_code: 'R1' },
        { id: 2, week_start: '2026-01-05', rep_code: 'R2' },
      ],
    });
    fetchLoadoutWeek.mockResolvedValue({
      results: [
        {
          id: 1,
          week_start: '2026-01-05',
          rep_code: 'R1',
          rep_name: 'Ana',
          line_items: [{ item_code: 'A1', item_name: 'Milk', qty_forecast: 10, qty_actual: 9, return_rate_forecast: 0.1 }],
        },
        {
          id: 2,
          week_start: '2026-01-05',
          rep_code: 'R2',
          rep_name: 'Ben',
          line_items: [{ item_code: 'B1', item_name: 'Bread', qty_forecast: 5, qty_actual: 5, return_rate_forecast: 0.05 }],
        },
      ],
    });

    render(
      <MemoryRouter>
        <LoadoutSheetPage />
      </MemoryRouter>,
    );

    // Await the full effect chain (weeks → rows) before asserting anything.
    // Timeouts are explicit: MUI DataGrid first render is heavy and the
    // parallel suite shares CPU, so the default 1s waitFor window flakes.
    expect(await screen.findByText('Ana', {}, { timeout: 10000 })).toBeInTheDocument();
    expect(await screen.findByText('Ben')).toBeInTheDocument();
    // Default selection is the first rep (R1/Ana) — only her items render.
    expect(await screen.findByText('Milk')).toBeInTheDocument();
    // Item rows follow the selected rep: click Ben's row to load R2 items.
    fireEvent.click(screen.getByText('Ben'));
    expect(await screen.findByText('Bread')).toBeInTheDocument();
    expect(await screen.findByText('Export XLS')).toBeInTheDocument();
  });

  it('shows an empty state when there are no weeks', async () => {
    fetchLoadoutSheets.mockResolvedValue({ results: [] });
    render(
      <MemoryRouter>
        <LoadoutSheetPage />
      </MemoryRouter>,
    );
    expect(await screen.findByText('No loadout sheets yet')).toBeInTheDocument();
    // No week rows and no export action in the empty state.
    expect(screen.queryByText('Export XLS')).not.toBeInTheDocument();
  });
});
