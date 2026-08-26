// src/__tests__/DQScorecardTab.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const mockGetTableScorecard = vi.fn();

vi.mock('../api/profiling', () => ({
  getTableScorecard: (...args) => mockGetTableScorecard(...args),
  getTableProfile: vi.fn(),
  runTableProfile: vi.fn(),
  getTableFreshness: vi.fn(),
  saveFreshnessPolicy: vi.fn(),
}));

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token' }),
}));

const mockNotify = vi.fn();

vi.mock('../components/NotificationProvider', () => ({
  useNotification: () => ({ notify: mockNotify }),
}));

import DQScorecardTab from '../pages/catalog/tabs/DQScorecardTab';

const SCORECARD = {
  quality_score: 0.92,
  dimensions: {
    completeness: { passed: 10, failed: 0, score: 1.0 },
    validity: { passed: 8, failed: 2, score: 0.8 },
    accuracy: { passed: 5, failed: 5, score: 0.5 },
    uniqueness: { passed: 7, failed: 3, score: 0.7 },
    consistency: { passed: 6, failed: 4, score: 0.6 },
    timeliness: { passed: 9, failed: 1, score: 0.9 },
  },
  total_rules: 2,
  last_run_at: '2026-08-26T10:00:00Z',
  profile_summary: {
    row_count: 100,
    completeness_pct: 95.0,
    profiled_at: '2026-08-26T10:00:00Z',
  },
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe('DQScorecardTab', () => {
  it('renders the overall score and six dimension bars', async () => {
    mockGetTableScorecard.mockResolvedValue(SCORECARD);

    render(
      <MemoryRouter>
        <DQScorecardTab tableId="42" />
      </MemoryRouter>,
    );

    expect(await screen.findByText('Quality Score')).toBeInTheDocument();
    expect(screen.getByText('Completeness')).toBeInTheDocument();
    expect(screen.getByText('Validity')).toBeInTheDocument();
    expect(screen.getByText('Accuracy')).toBeInTheDocument();
    expect(screen.getByText('Uniqueness')).toBeInTheDocument();
    expect(screen.getByText('Consistency')).toBeInTheDocument();
    expect(screen.getByText('Timeliness')).toBeInTheDocument();
    expect(screen.getByText('92')).toBeInTheDocument();
  });

  it('shows an empty state when total_rules is 0', async () => {
    mockGetTableScorecard.mockResolvedValue({
      quality_score: 0,
      dimensions: {},
      total_rules: 0,
      last_run_at: null,
      profile_summary: { row_count: 0, completeness_pct: 0, profiled_at: null },
    });

    render(
      <MemoryRouter>
        <DQScorecardTab tableId="42" />
      </MemoryRouter>,
    );

    expect(
      await screen.findByText('No DQ rules assigned to this table'),
    ).toBeInTheDocument();
  });
});
