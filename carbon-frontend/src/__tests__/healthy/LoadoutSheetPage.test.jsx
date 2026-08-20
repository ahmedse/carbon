// src/__tests__/healthy/LoadoutSheetPage.test.jsx
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import LoadoutSheetPage from '../../apps/healthy/LoadoutSheetPage';
import { fetchLoadoutSheets, fetchLoadoutWeek } from '../../api/healthy';

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token' }),
}));
vi.mock('../../api/healthy', () => ({
  fetchLoadoutSheets: vi.fn(),
  fetchLoadoutWeek: vi.fn(),
}));

// jsdom has no ResizeObserver — StandardDataGrid needs a stub.
class FakeResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

beforeEach(() => {
  global.ResizeObserver = FakeResizeObserver;
  fetchLoadoutSheets.mockReset();
  fetchLoadoutWeek.mockReset();
});

afterEach(() => {
  delete global.ResizeObserver;
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

    expect(await screen.findByText('Ana')).toBeInTheDocument();
    expect(screen.getByText('Ben')).toBeInTheDocument();
    expect(screen.getByText('Milk')).toBeInTheDocument();
    expect(screen.getByText('Export XLS')).toBeInTheDocument();
  });

  it('shows an empty state when there are no weeks', async () => {
    fetchLoadoutSheets.mockResolvedValue({ results: [] });
    render(
      <MemoryRouter>
        <LoadoutSheetPage />
      </MemoryRouter>,
    );
    expect(await screen.findByText('No loadout sheets yet')).toBeInTheDocument();
  });
});
