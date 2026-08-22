// src/__tests__/AIInputBar.mode.test.jsx
// Phase 21-C — persistent context chips (restore context across turns).
// W5-A (ADR-0014) — the Ask/Agent composer selector MOVED to the workspace
// header; the composer itself is now mode-agnostic and must not render the
// pill or any mode hint/steering copy.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import AIInputBar from '../shell/AIInputBar';

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token' }),
}));

vi.mock('../api/api', () => ({
  apiFetch: vi.fn(),
}));

import { apiFetch } from '../api/api';

const TABLES = [{ id: 35, title: 'Electricity', name: 'electricity' }];

// Mirrors AIInputBar's PLACEHOLDER_MAP.working — the composer no longer swaps
// in mode-specific steering copy while working (W5-A).
const PLACEHOLDER_WORKING = 'AI is thinking… (Enter to queue)';

function renderBar(props = {}) {
  return render(<AIInputBar onSend={vi.fn()} {...props} />);
}

beforeEach(() => {
  apiFetch.mockReset();
  apiFetch.mockResolvedValue({ results: TABLES });
});

describe('AIInputBar composer (W5-A — mode lives in the workspace header)', () => {
  it('no longer renders the Ask/Agent composer-mode selector', () => {
    renderBar();
    expect(screen.queryByRole('group', { name: 'Composer mode' })).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /answers and advice only, nothing executed/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /plan and execute actions in a workflow/i }),
    ).not.toBeInTheDocument();
  });

  it('no longer shows the dynamic mode hint text', () => {
    renderBar();
    expect(screen.queryByText(/no rules created, no data changed/i)).not.toBeInTheDocument();
    expect(
      screen.queryByText(/Agents execute actions — you confirm before they run/i),
    ).not.toBeInTheDocument();
  });

  it('uses the default working placeholder (no agent steering copy)', () => {
    renderBar({ working: true });
    expect(screen.getByLabelText('Message input')).toHaveAttribute(
      'placeholder',
      PLACEHOLDER_WORKING,
    );
    expect(screen.getByLabelText('Message input').getAttribute('placeholder')).not.toContain(
      'interrupt',
    );
  });

  it('shows a context chip for a resolved mention and keeps it after sending', async () => {
    const onSend = vi.fn();
    renderBar({ onSend });
    const input = screen.getByLabelText('Message input');
    fireEvent.change(input, { target: { value: 'check #table ' } });
    await waitFor(() => screen.getByRole('option', { name: 'Electricity' }));
    fireEvent.click(screen.getByRole('option', { name: 'Electricity' }));

    expect(screen.getByRole('button', { name: /remove context table electricity/i })).toBeInTheDocument();

    // Send — the context chip persists for the next turn (restore context).
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onSend).toHaveBeenCalledWith(
      'check @Electricity',
      [expect.objectContaining({ kind: 'table', id: '35', name: 'Electricity' })],
    );
    expect(screen.getByRole('button', { name: /remove context table electricity/i })).toBeInTheDocument();
  });

  it('removes a single context chip via its delete affordance', async () => {
    renderBar();
    const input = screen.getByLabelText('Message input');
    fireEvent.change(input, { target: { value: 'check #table ' } });
    await waitFor(() => screen.getByRole('option', { name: 'Electricity' }));
    fireEvent.click(screen.getByRole('option', { name: 'Electricity' }));

    // MUI attaches onDelete to the chip's trailing delete icon.
    fireEvent.click(screen.getByTestId('CancelIcon'));
    expect(screen.queryByRole('button', { name: /remove context table electricity/i })).not.toBeInTheDocument();
  });

  it('clears all context with the Clear action', async () => {
    renderBar();
    const input = screen.getByLabelText('Message input');
    fireEvent.change(input, { target: { value: 'check #table ' } });
    await waitFor(() => screen.getByRole('option', { name: 'Electricity' }));
    fireEvent.click(screen.getByRole('option', { name: 'Electricity' }));

    fireEvent.click(screen.getByRole('button', { name: 'Clear all context' }));
    expect(screen.queryByRole('button', { name: /remove context table electricity/i })).not.toBeInTheDocument();
  });

  it('sends without context when nothing was attached', () => {
    const onSend = vi.fn();
    renderBar({ onSend });
    const input = screen.getByLabelText('Message input');
    fireEvent.change(input, { target: { value: 'hello' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onSend).toHaveBeenCalledWith('hello', []);
  });
});
