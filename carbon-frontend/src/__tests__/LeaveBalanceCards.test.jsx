import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import LeaveBalanceCards from '../apps/my/components/LeaveBalanceCards';

describe('LeaveBalanceCards', () => {
  it('shows reserved-pending copy when a type has pending days', () => {
    render(
      <LeaveBalanceCards
        loading={false}
        balances={[
          {
            leave_type: 'annual',
            entitled: 20,
            carried_forward: 0,
            used: 0,
            pending: 3,
            remaining: 17,
            remaining_signed: 17,
            overdrawn: false,
          },
        ]}
      />,
    );
    expect(screen.getByText(/Pending is already reserved/i)).toBeInTheDocument();
    expect(screen.getByText('17')).toBeInTheDocument();
  });

  it('shows signed overdraw when used plus pending exceed opening', () => {
    render(
      <LeaveBalanceCards
        loading={false}
        balances={[
          {
            leave_type: 'annual',
            entitled: 20,
            carried_forward: 0,
            used: 15,
            pending: 10,
            remaining: 0,
            remaining_signed: -5,
            overdrawn: true,
          },
        ]}
      />,
    );
    expect(screen.getByText(/Used plus pending exceed/i)).toBeInTheDocument();
  });
});
