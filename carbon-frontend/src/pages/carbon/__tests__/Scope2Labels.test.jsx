import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MarketBasedAbsentAlert, Scope2MethodChip } from '../Scope2Labels';

describe('Scope 2 labels', () => {
  it('names location-based on a Scope 2 chip', () => {
    render(<Scope2MethodChip method="location_based" scope={2} />);
    expect(screen.getByText('Location-based')).toBeTruthy();
  });

  it('says market-based is absent and not zero', () => {
    render(
      <MarketBasedAbsentAlert
        payload={{ by_scope2_method: { market_based: { present: false, reason: 'no_distinct_contractual_factor' } } }}
      />,
    );
    expect(screen.getByText(/Market-based Scope 2 is absent/)).toBeTruthy();
    expect(screen.queryByText(/0 kg/)).toBeNull();
  });

  it('hides the absent alert when a contractual total is present', () => {
    render(
      <MarketBasedAbsentAlert
        payload={{ by_scope2_method: { market_based: { present: true, total_co2e_kg: '12' } } }}
      />,
    );
    expect(screen.queryByText(/Market-based Scope 2 is absent/)).toBeNull();
  });
});
