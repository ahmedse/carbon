import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import NotFound from '../pages/NotFound';

describe('NotFound', () => {
  it('renders 404 heading', () => {
    render(<MemoryRouter><NotFound /></MemoryRouter>);
    expect(screen.getByText('404')).toBeInTheDocument();
  });

  it('renders "Page Not Found" message', () => {
    render(<MemoryRouter><NotFound /></MemoryRouter>);
    expect(screen.getByText('Page Not Found')).toBeInTheDocument();
  });

  it('has a "Go to Dashboard" link pointing to the dashboard', () => {
    render(<MemoryRouter><NotFound /></MemoryRouter>);
    const link = screen.getByRole('link', { name: /go to dashboard/i });
    expect(link).toHaveAttribute('href', '/carbon/dashboard');
  });
});
