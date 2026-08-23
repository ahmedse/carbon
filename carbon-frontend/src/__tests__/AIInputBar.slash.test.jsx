// src/__tests__/AIInputBar.slash.test.jsx
// Phase W8-A — slash-command menu: '/' opens the command list, directives insert
// prompt text, actions dispatch onCommand, and '/' + '#' stay mutually exclusive.
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import AIInputBar from '../shell/AIInputBar';

function renderBar(props = {}) {
  return render(<AIInputBar onSend={vi.fn()} {...props} />);
}

describe('AIInputBar slash-commands', () => {
  it('opens the command menu when a leading / is typed', () => {
    renderBar();
    const input = screen.getByLabelText('Message input');
    fireEvent.change(input, { target: { value: '/' } });

    expect(screen.getByRole('listbox', { name: 'Commands' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Summarize this conversation so far' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Clear working context' })).toBeInTheDocument();
  });

  it('filters commands by the partial text after /', () => {
    renderBar();
    const input = screen.getByLabelText('Message input');
    fireEvent.change(input, { target: { value: '/c' } });

    expect(screen.getByRole('option', { name: 'Clear working context' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Save a checkpoint' })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: 'Summarize this conversation so far' })).not.toBeInTheDocument();
  });

  it('directive selection inserts the label + trailing space', () => {
    renderBar();
    const input = screen.getByLabelText('Message input');
    fireEvent.change(input, { target: { value: '/sum' } });
    fireEvent.click(screen.getByRole('option', { name: 'Summarize this conversation so far' }));

    expect(input.value).toBe('Summarize this conversation so far ');
    expect(screen.queryByRole('listbox', { name: 'Commands' })).not.toBeInTheDocument();
  });

  it('action selection calls onCommand and clears the input', () => {
    const onCommand = vi.fn();
    renderBar({ onCommand });
    const input = screen.getByLabelText('Message input');
    fireEvent.change(input, { target: { value: '/clear' } });
    fireEvent.click(screen.getByRole('option', { name: 'Clear working context' }));

    expect(onCommand).toHaveBeenCalledWith('clear');
    expect(input.value).toBe('');
    expect(screen.queryByRole('listbox', { name: 'Commands' })).not.toBeInTheDocument();
  });

  it('action selection is a graceful no-op when onCommand is absent', () => {
    renderBar();
    const input = screen.getByLabelText('Message input');
    fireEvent.change(input, { target: { value: '/clear' } });
    fireEvent.click(screen.getByRole('option', { name: 'Clear working context' }));

    expect(input.value).toBe('');
    expect(screen.queryByRole('listbox', { name: 'Commands' })).not.toBeInTheDocument();
  });

  it('Escape closes the command menu', () => {
    renderBar();
    const input = screen.getByLabelText('Message input');
    fireEvent.change(input, { target: { value: '/' } });
    expect(screen.getByRole('listbox', { name: 'Commands' })).toBeInTheDocument();

    fireEvent.keyDown(input, { key: 'Escape' });
    expect(screen.queryByRole('listbox', { name: 'Commands' })).not.toBeInTheDocument();
  });

  it('/ and # are independent — # does not open the command menu and vice versa', () => {
    renderBar();
    const input = screen.getByLabelText('Message input');

    fireEvent.change(input, { target: { value: '#' } });
    expect(screen.queryByRole('listbox', { name: 'Commands' })).not.toBeInTheDocument();
    expect(screen.getByRole('listbox', { name: /mention kinds/i })).toBeInTheDocument();

    fireEvent.change(input, { target: { value: '/' } });
    expect(screen.getByRole('listbox', { name: 'Commands' })).toBeInTheDocument();
    expect(screen.queryByRole('listbox', { name: /mention kinds/i })).not.toBeInTheDocument();
  });

  it('ArrowUp/Down move the highlight and Enter selects the highlighted command', () => {
    renderBar();
    const input = screen.getByLabelText('Message input');
    fireEvent.change(input, { target: { value: '/' } });

    // Down once highlights the 2nd item (/plan, a directive)…
    fireEvent.keyDown(input, { key: 'ArrowDown' });
    expect(screen.getByRole('option', { name: 'Plan a task to' })).toHaveAttribute('aria-selected', 'true');

    // …Enter inserts its label + trailing space and closes the menu.
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(input.value).toBe('Plan a task to ');
    expect(screen.queryByRole('listbox', { name: 'Commands' })).not.toBeInTheDocument();
  });
});
