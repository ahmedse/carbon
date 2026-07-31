import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import PlatformHome from '../pages/PlatformHome';

// Mock dependencies
vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ user: { username: 'testuser' }, permissions: [] }),
}));
vi.mock('../hooks/useEnabledApps', () => ({
  useEnabledApps: () => ({ apps: [], loading: false, error: null, isAppEnabled: () => true }),
}));

describe('PlatformHome', () => {
  it('renders the page title', () => {
    render(<MemoryRouter><PlatformHome /></MemoryRouter>);
    expect(screen.getByRole('heading', { name: /platform/i })).toBeInTheDocument();
  });

  it('renders without crashing when apps list is empty', () => {
    const { container } = render(<MemoryRouter><PlatformHome /></MemoryRouter>);
    expect(container).toBeTruthy();
  });
});
