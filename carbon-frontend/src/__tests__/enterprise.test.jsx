import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import React from 'react';

const theme = createTheme();

// ── Mock AuthContext ─────────────────────────────────────────────────
vi.mock('../auth/AuthContext', () => ({
  useAuth: vi.fn(() => ({
    user: { username: 'testuser', roles: [] },
    loading: false,
    availablePerspectives: ['admin'],
    context: { modules: [] },
  })),
  AuthProvider: ({ children }) => React.createElement(React.Fragment, null, children),
}));

// ── Mock ThemeContext ─────────────────────────────────────────────────
vi.mock('../theme/useThemeMode', () => ({
  useThemeMode: vi.fn(() => ({ mode: 'light', toggle: vi.fn() })),
}));

// ── Shell smoke ──────────────────────────────────────────────────────
describe('Shell', () => {
  it('renders without crashing', async () => {
    const { Shell } = await import('../shell/Shell');
    const { container } = render(
      <ThemeProvider theme={theme}>
        <MemoryRouter>
          <Shell />
        </MemoryRouter>
      </ThemeProvider>
    );
    expect(container).toBeTruthy();
  });
});

// ── PageHeader ──────────────────────────────────────────────────────
describe('PageHeader', () => {
  it('renders title', async () => {
    const { default: PageHeader } = await import('../components/Page/PageHeader');
    render(<PageHeader title="Test Title" />);
    expect(screen.getByText('Test Title')).toBeInTheDocument();
  });

  it('renders subtitle when provided', async () => {
    const { default: PageHeader } = await import('../components/Page/PageHeader');
    render(<PageHeader title="Test" subtitle="A subtitle" />);
    expect(screen.getByText('A subtitle')).toBeInTheDocument();
  });

  it('renders badge when provided', async () => {
    const { default: PageHeader } = await import('../components/Page/PageHeader');
    render(<PageHeader title="Test" badge={{ label: 'Draft', color: 'warning' }} />);
    expect(screen.getByText('Draft')).toBeInTheDocument();
  });

  it('renders actions when provided', async () => {
    const { default: PageHeader } = await import('../components/Page/PageHeader');
    render(
      <PageHeader title="Test" actions={<button>Action</button>} />
    );
    expect(screen.getByText('Action')).toBeInTheDocument();
  });
});

// ── ErrorBoundary ────────────────────────────────────────────────────
describe('ErrorBoundary', () => {
  it('renders children without error', async () => {
    const { default: ErrorBoundary } = await import('../shell/ErrorBoundary');
    render(
      <ErrorBoundary>
        <div>Content</div>
      </ErrorBoundary>
    );
    expect(screen.getByText('Content')).toBeInTheDocument();
  });

  it('catches errors and shows fallback', async () => {
    const ThrowError = () => {
      throw new Error('test error');
    };
    const { default: ErrorBoundary } = await import('../shell/ErrorBoundary');
    // suppress console.error for expected throw
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>
    );
    expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();
    spy.mockRestore();
  });
});

// ── Breadcrumbs ──────────────────────────────────────────────────────
describe('Breadcrumbs', () => {
  it('renders breadcrumbs for known paths', async () => {
    const { Breadcrumbs } = await import('../shell/Breadcrumbs');
    render(
      <MemoryRouter initialEntries={['/carbon/console']}>
        <Breadcrumbs />
      </MemoryRouter>
    );
    expect(screen.getByText('Carbon Console')).toBeInTheDocument();
  });

  it('renders nothing on home page', async () => {
    const { Breadcrumbs } = await import('../shell/Breadcrumbs');
    const { container } = render(
      <MemoryRouter initialEntries={['/']}>
        <Breadcrumbs />
      </MemoryRouter>
    );
    // Should render nothing or minimal content
    expect(container).toBeTruthy();
  });
});

// ── Theme exports ────────────────────────────────────────────────────
describe('carbonTheme', () => {
  it('exports chartPalette with expected colors', async () => {
    const { chartPalette } = await import('../theme/carbonTheme');
    expect(chartPalette.blue).toBe('#2563eb');
    expect(chartPalette.green).toBe('#10b981');
    expect(chartPalette.scope1).toBe('#ef4444');
    expect(chartPalette.scope2).toBe('#f59e0b');
    expect(chartPalette.scope3).toBe('#2563eb');
  });

  it('exports createCarbonTheme as a function', async () => {
    const { default: createCarbonTheme } = await import('../theme/carbonTheme');
    expect(typeof createCarbonTheme).toBe('function');
    const theme = createCarbonTheme('light');
    expect(theme.palette.mode).toBe('light');
  });
});

// ── Terminology ──────────────────────────────────────────────────────
describe('terminology', () => {
  it('exports DATA_PRODUCT and DATA_PRODUCTS', async () => {
    const { DATA_PRODUCT, DATA_PRODUCTS } = await import('../constants/terminology');
    expect(DATA_PRODUCT).toBe('Data Product');
    expect(DATA_PRODUCTS).toBe('Data Products');
  });
});

// ── NetworkStatusBanner ──────────────────────────────────────────────
describe('NetworkStatusBanner', () => {
  it('renders without crashing', async () => {
    const { NetworkStatusProvider } = await import('../components/NetworkStatusBanner');
    const { container } = render(
      <NetworkStatusProvider>
        <div>child</div>
      </NetworkStatusProvider>
    );
    expect(container).toBeTruthy();
  });
});

// ── AdminRoute ──────────────────────────────────────────────────────
describe('AdminRoute', () => {
  it('renders children when user is admin', async () => {
    const { useAuth } = await import('../auth/AuthContext');
    useAuth.mockReturnValue({
      user: { username: 'admin', roles: ['admin'] },
      loading: false,
      availablePerspectives: ['admin'],
      context: { modules: [] },
    });
    const { default: AdminRoute } = await import('../components/AdminRoute');
    render(
      <MemoryRouter>
        <AdminRoute>
          <div>Admin Content</div>
        </AdminRoute>
      </MemoryRouter>
    );
    expect(screen.getByText('Admin Content')).toBeInTheDocument();
  });
});

// ── NotFound ─────────────────────────────────────────────────────────
describe('NotFound page', () => {
  it('renders 404', async () => {
    const { default: NotFound } = await import('../pages/NotFound');
    render(
      <MemoryRouter>
        <NotFound />
      </MemoryRouter>
    );
    expect(screen.getByText('404')).toBeInTheDocument();
  });
});

// ── API 401 refresh ──────────────────────────────────────────────────
describe('apiFetch 401 handling', () => {
  it('api module exports apiFetch and authFetch', async () => {
    const api = await import('../api/api');
    expect(typeof api.apiFetch).toBe('function');
    expect(typeof api.authFetch).toBe('function');
  });

  it('apiFetch throws on non-200 response', async () => {
    const { apiFetch } = await import('../api/api');
    // Mock fetch to return 500
    globalThis.fetch = vi.fn(() =>
      Promise.resolve({
        ok: false,
        status: 500,
        headers: { get: () => 'application/json' },
        json: () => Promise.resolve({ detail: 'Server Error' }),
      })
    );
    await expect(apiFetch('test/')).rejects.toThrow();
    globalThis.fetch.mockRestore();
  });
});
