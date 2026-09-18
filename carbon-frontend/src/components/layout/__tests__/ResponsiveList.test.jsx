// ResponsiveList — mobile cards vs desktop table (ADR-0035 / MOB-C)
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

const useIsMobileMock = vi.fn();

vi.mock('../../../hooks/useIsMobile', () => ({
  useIsMobile: () => useIsMobileMock(),
  default: () => useIsMobileMock(),
}));

import ResponsiveList from '../ResponsiveList';

const ITEMS = [
  { id: 1, name: 'Alpha' },
  { id: 2, name: 'Beta' },
];

beforeEach(() => {
  useIsMobileMock.mockReset();
});

describe('ResponsiveList', () => {
  it('renders the table prop when not mobile', () => {
    useIsMobileMock.mockReturnValue(false);

    render(
      <ResponsiveList
        items={ITEMS}
        getKey={(item) => item.id}
        renderCard={(item) => ({ title: item.name })}
        table={<div data-testid="desktop-table">Desktop table</div>}
      />,
    );

    expect(screen.getByTestId('desktop-table')).toBeInTheDocument();
    expect(screen.queryByText('Alpha')).not.toBeInTheDocument();
  });

  it('renders stacked cards when mobile', () => {
    useIsMobileMock.mockReturnValue(true);
    const onClick = vi.fn();

    render(
      <ResponsiveList
        items={ITEMS}
        getKey={(item) => item.id}
        renderCard={(item) => ({
          title: item.name,
          status: 'Open',
          statusColor: 'info',
          meta: '2026-09-17',
          onClick: item.id === 1 ? onClick : undefined,
        })}
        table={<div data-testid="desktop-table">Desktop table</div>}
      />,
    );

    expect(screen.queryByTestId('desktop-table')).not.toBeInTheDocument();
    expect(screen.getByText('Alpha')).toBeInTheDocument();
    expect(screen.getByText('Beta')).toBeInTheDocument();
    expect(screen.getAllByText('Open')).toHaveLength(2);
    expect(screen.getAllByText('2026-09-17')).toHaveLength(2);

    fireEvent.click(screen.getByText('Alpha'));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it('renders emptyLabel when mobile and items is empty', () => {
    useIsMobileMock.mockReturnValue(true);

    render(
      <ResponsiveList
        items={[]}
        getKey={(item) => item.id}
        renderCard={(item) => ({ title: item.name })}
        table={<div data-testid="desktop-table">Desktop table</div>}
        emptyLabel="Nothing here"
      />,
    );

    expect(screen.getByText('Nothing here')).toBeInTheDocument();
    expect(screen.queryByTestId('desktop-table')).not.toBeInTheDocument();
  });
});
