// src/__tests__/AIInputBar.entityResolve.test.jsx
// Phase 3B — two-stage mention resolver: kind → entity search → resolved mention object.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import AIInputBar from '../shell/AIInputBar';

// Mock auth so the component can call apiFetch.
vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token' }),
}));

// Mock apiFetch to return a predictable entity list.
vi.mock('../api/api', () => ({
  apiFetch: vi.fn(),
}));

import { apiFetch } from '../api/api';

const TABLES = [
  { id: 35, title: 'Electricity', name: 'electricity' },
  { id: 36, title: 'Fleet fuel log', name: 'fleet_fuel_log' },
];

function renderBar(props = {}) {
  return render(<AIInputBar onSend={vi.fn()} {...props} />);
}

beforeEach(() => {
  apiFetch.mockReset();
  apiFetch.mockResolvedValue({ results: TABLES });
});

describe('AIInputBar entity resolver', () => {
  it('shows kind list after #', () => {
    renderBar();
    fireEvent.change(screen.getByLabelText('Message input'), { target: { value: '#' } });
    expect(screen.getByRole('listbox', { name: /mention kinds/i })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: '#table' })).toBeInTheDocument();
  });

  it('moves to entity search after kind selected', async () => {
    renderBar();
    const input = screen.getByLabelText('Message input');
    fireEvent.change(input, { target: { value: '#' } });
    fireEvent.click(screen.getByRole('option', { name: '#table' }));

    // Input now contains '#table ' and the entity picker opens.
    expect(input.value).toBe('#table ');
    await waitFor(() =>
      expect(screen.getByRole('listbox', { name: /table search results/i })).toBeInTheDocument(),
    );
  });

  it('calls apiFetch with the right route and query', async () => {
    renderBar();
    const input = screen.getByLabelText('Message input');
    fireEvent.change(input, { target: { value: '#table Ele' } });

    await waitFor(() => expect(apiFetch).toHaveBeenCalled());
    const calledUrl = apiFetch.mock.calls[0][0];
    expect(calledUrl).toMatch(/dataschema\/tables\//);
    expect(calledUrl).toMatch(/q=Ele/);
  });

  it('inserts @EntityName and fires resolved mention on entity selection', async () => {
    const onSend = vi.fn();
    const onMentionsChange = vi.fn();
    renderBar({ onSend, onMentionsChange });

    const input = screen.getByLabelText('Message input');
    fireEvent.change(input, { target: { value: 'check #table ' } });

    await waitFor(() =>
      expect(screen.getByRole('listbox', { name: /table search results/i })).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole('option', { name: 'Electricity' }));

    expect(input.value).toBe('check @Electricity ');
    await waitFor(() =>
      expect(onMentionsChange).toHaveBeenCalledWith([
        expect.objectContaining({ kind: 'table', id: '35', name: 'Electricity' }),
      ]),
    );
  });

  it('sends resolved mention objects on submit', async () => {
    const onSend = vi.fn();
    renderBar({ onSend });

    const input = screen.getByLabelText('Message input');
    fireEvent.change(input, { target: { value: 'validate #table ' } });

    await waitFor(() => screen.getByRole('option', { name: 'Electricity' }));
    fireEvent.click(screen.getByRole('option', { name: 'Electricity' }));

    fireEvent.keyDown(input, { key: 'Enter' });

    expect(onSend).toHaveBeenCalledWith(
      'validate @Electricity',
      [expect.objectContaining({ kind: 'table', id: '35', name: 'Electricity' })],
    );
  });

  it('shows "No matches" when apiFetch returns empty', async () => {
    apiFetch.mockResolvedValue({ results: [] });
    renderBar();
    const input = screen.getByLabelText('Message input');
    fireEvent.change(input, { target: { value: '#table xyz' } });

    await waitFor(() =>
      expect(screen.getByText(/no matches/i)).toBeInTheDocument(),
    );
  });

  it('existing kind-only regression: kind list still appears on bare #', () => {
    renderBar();
    fireEvent.change(screen.getByLabelText('Message input'), { target: { value: 'text #r' } });
    expect(screen.getByRole('option', { name: '#rule' })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: '#table' })).not.toBeInTheDocument();
  });
});
