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

  it('has a search input for page search', () => {
    render(<MemoryRouter><NotFound /></MemoryRouter>);
    const searchInput = screen.getByPlaceholderText(/search for a page/i);
    expect(searchInput).toBeInTheDocument();
  });

  it('has suggested page links including Dashboard', () => {
    render(<MemoryRouter><NotFound /></MemoryRouter>);
    const dashboardLink = screen.getByRole('link', { name: /dashboard/i });
    expect(dashboardLink).toBeInTheDocument();
  });
});
