// NSR-3B — My loans: list helper + card smoke render (QA B6).
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token' }),
}));

import { normalizeMyLoans } from '../api/my';
import MyLoansCard from '../apps/my/components/MyLoansCard';

describe('normalizeMyLoans (list helper)', () => {
  it('returns a plain array as-is', () => {
    const rows = [{ id: 1, loan_type: 'personal', status: 'active' }];
    expect(normalizeMyLoans(rows)).toEqual(rows);
  });

  it('unwraps a paginated { results } envelope', () => {
    const rows = [{ id: 2, loan_type: 'housing', status: 'draft' }];
    expect(normalizeMyLoans({ count: 1, results: rows })).toEqual(rows);
  });

  it('returns [] for null / unexpected shapes', () => {
    expect(normalizeMyLoans(null)).toEqual([]);
    expect(normalizeMyLoans(undefined)).toEqual([]);
    expect(normalizeMyLoans({})).toEqual([]);
  });
});

describe('MyLoansCard smoke', () => {
  it('renders empty state', () => {
    render(<MyLoansCard loans={[]} loading={false} error={null} />);
    expect(screen.getByTestId('my-loans-card')).toBeInTheDocument();
    expect(screen.getByText(/You have no loans yet/i)).toBeInTheDocument();
  });

  it('renders loan type and status label', () => {
    render(
      <MyLoansCard
        loans={[
          {
            id: 9,
            loan_type: { id: 1, code: 'personal', label: 'Personal' },
            principal: '500.000',
            term_months: 12,
            start_date: '2026-01-01',
            status: 'active',
          },
        ]}
        loading={false}
        error={null}
      />,
    );
    expect(screen.getByText('Personal')).toBeInTheDocument();
    expect(screen.getByText(/Active/i)).toBeInTheDocument();
    expect(screen.getByText(/500/)).toBeInTheDocument();
  });

  it('renders plain-string loan_type during transition', () => {
    render(
      <MyLoansCard
        loans={[
          {
            id: 10,
            loan_type: 'housing',
            principal: '100',
            term_months: 6,
            start_date: '2026-02-01',
            status: 'draft',
          },
        ]}
        loading={false}
        error={null}
      />,
    );
    expect(screen.getByText('housing')).toBeInTheDocument();
  });

  it('renders error with retry affordance', () => {
    const onRetry = vi.fn();
    render(
      <MyLoansCard loans={[]} loading={false} error="Could not load data" onRetry={onRetry} />,
    );
    expect(screen.getByText(/Could not load data/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Retry/i })).toBeInTheDocument();
  });
});
