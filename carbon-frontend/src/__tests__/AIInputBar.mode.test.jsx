// src/__tests__/AIInputBar.mode.test.jsx
// Phase 21-C — VS Code Copilot-style composer: Ask/Agent mode selector and
// persistent context chips (restore context across turns).
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

function renderBar(props = {}) {
  return render(<AIInputBar onSend={vi.fn()} {...props} />);
}

beforeEach(() => {
  apiFetch.mockReset();
  apiFetch.mockResolvedValue({ results: TABLES });
});

describe('AIInputBar composer mode (Ask = answers only / Agent = executes)', () => {
  it('renders Ask/Agent mode selector with Ask selected by default', () => {
    renderBar();
    expect(screen.getByRole('group', { name: 'Composer mode' })).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /answers and advice only, nothing executed/i }),
    ).toHaveAttribute('aria-pressed', 'true');
    expect(
      screen.getByRole('button', { name: /plan and execute actions in a workflow/i }),
    ).toHaveAttribute('aria-pressed', 'false');
  });

  it('notifies the parent when the mode switches to Agent', () => {
    const onModeChange = vi.fn();
    renderBar({ onModeChange });
    fireEvent.click(screen.getByRole('button', { name: /plan and execute actions in a workflow/i }));
    expect(onModeChange).toHaveBeenCalledWith('agent');
  });

  it('uses the steering placeholder in Agent mode while working', () => {
    renderBar({ mode: 'agent', working: true });
    expect(screen.getByLabelText('Message input')).toHaveAttribute(
      'placeholder',
      expect.stringContaining('interrupt'),
    );
  });

  it('shows a dynamic mode hint that switches with the selected mode', () => {
    renderBar();
    // Default Ask mode → answers-only hint (nothing is executed).
    expect(screen.getByText(/no rules created, no data changed/i)).toBeInTheDocument();
    // Agent mode → execution hint (agents run actions, user confirms first).
    renderBar({ mode: 'agent' });
    expect(screen.getByText(/Agents execute actions — you confirm before they run/i)).toBeInTheDocument();
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
