import { describe, it, expect, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import SearchPage from '../pages/catalog/SearchPage';

const searchCatalog = vi.fn();

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token' }),
}));

const notify = vi.fn();
const notifyFromError = vi.fn();

vi.mock('../components/NotificationProvider', () => ({
  useNotification: () => ({ notify, notifyFromError, showFeedback: vi.fn() }),
}));

vi.mock('../api/catalogSearch', () => ({
  searchCatalog: (...args) => searchCatalog(...args),
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe('SearchPage', () => {
  it('renders search input and type chips', () => {
    searchCatalog.mockResolvedValue({ total: 0, results: [] });
    render(
      <MemoryRouter initialEntries={['/catalog/search']}>
        <SearchPage />
      </MemoryRouter>,
    );

    expect(screen.getByPlaceholderText('Search catalog by name or description...')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'All' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Tables' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Fields' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Domains' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Glossary' })).toBeInTheDocument();
  });

  it('calls searchCatalog after debounce when input changes', async () => {
    searchCatalog.mockResolvedValue({ total: 0, results: [] });
    render(
      <MemoryRouter initialEntries={['/catalog/search']}>
        <SearchPage />
      </MemoryRouter>,
    );

    const input = screen.getByPlaceholderText('Search catalog by name or description...');
    fireEvent.change(input, { target: { value: 'ta' } });

    await waitFor(() => {
      expect(searchCatalog).toHaveBeenCalledWith('test-token', 'ta', [], 1);
    });
  });

  it('renders results with type chips and links', async () => {
    searchCatalog.mockResolvedValue({
      total: 2,
      results: [
        { type: 'table', id: 12, name: 'Customers', description: 'Customer table', url_hint: 'ignore' },
        { type: 'domain', id: 7, name: 'Finance', description: 'Finance domain', url_hint: 'ignore' },
      ],
    });

    render(
      <MemoryRouter initialEntries={['/catalog/search?q=cu']}>
        <SearchPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText('Customers')).toBeInTheDocument();
    expect(screen.getByText('Finance')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Customers' })).toHaveAttribute('href', '/catalog/tables/12');
    expect(screen.getByRole('link', { name: 'Finance' })).toHaveAttribute('href', '/catalog/domains/7');
    expect(screen.getByText('Customer table')).toBeInTheDocument();
  });

  it('updates API types when a filter chip is selected', async () => {
    searchCatalog.mockResolvedValue({ total: 0, results: [] });
    render(
      <MemoryRouter initialEntries={['/catalog/search']}>
        <SearchPage />
      </MemoryRouter>,
    );

    const input = screen.getByPlaceholderText('Search catalog by name or description...');
    fireEvent.change(input, { target: { value: 'field' } });

    await waitFor(() => {
      expect(searchCatalog).toHaveBeenCalledWith('test-token', 'field', [], 1);
    });

    const fieldsChip = screen.getByRole('button', { name: 'Fields' });
    fireEvent.click(fieldsChip);

    await waitFor(() => {
      expect(searchCatalog).toHaveBeenLastCalledWith('test-token', 'field', ['field'], 1);
    });
  });

  it('shows the empty state when no results are returned', async () => {
    searchCatalog.mockResolvedValue({ total: 0, results: [] });
    render(
      <MemoryRouter initialEntries={['/catalog/search']}>
        <SearchPage />
      </MemoryRouter>,
    );

    const input = screen.getByPlaceholderText('Search catalog by name or description...');
    fireEvent.change(input, { target: { value: 'zz' } });

    expect(await screen.findByText('No matching results found.')).toBeInTheDocument();
  });

  it('reads q and types from URL on mount', async () => {
    searchCatalog.mockResolvedValue({ total: 0, results: [] });
    render(
      <MemoryRouter initialEntries={['/catalog/search?q=alpha&types=table']}>
        <SearchPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(searchCatalog).toHaveBeenCalledWith('test-token', 'alpha', ['table'], 1);
    });
    expect(screen.getByDisplayValue('alpha')).toBeInTheDocument();
  });
});
