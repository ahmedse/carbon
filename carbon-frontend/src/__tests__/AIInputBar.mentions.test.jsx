// src/__tests__/AIInputBar.mentions.test.jsx
// Sprint 17 — #-mentions: trigger shows the fixed entity-kind list; selecting a
// kind inserts "#kind " into the text and mentions are passed up on send.
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import AIInputBar from '../shell/AIInputBar';

function renderBar(props = {}) {
  return render(<AIInputBar onSend={vi.fn()} {...props} />);
}

describe('AIInputBar #-mentions', () => {
  it('shows the entity-kind list when a leading # trigger is typed', () => {
    renderBar();
    const input = screen.getByLabelText('Message input');
    fireEvent.change(input, { target: { value: 'summarize #' } });

    expect(screen.getByRole('listbox', { name: /mention kinds/i })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: '#table' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: '#rule' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: '#field' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: '#module' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: '#org-unit' })).toBeInTheDocument();
  });

  it('inserts the selected kind into the text and closes the list', () => {
    renderBar();
    const input = screen.getByLabelText('Message input');
    fireEvent.change(input, { target: { value: 'summarize #' } });
    fireEvent.click(screen.getByRole('option', { name: '#table' }));

    expect(input.value).toBe('summarize #table ');
    expect(screen.queryByRole('listbox', { name: /mention kinds/i })).not.toBeInTheDocument();
  });

  it('filters the kind list by the partial text after #', () => {
    renderBar();
    const input = screen.getByLabelText('Message input');
    fireEvent.change(input, { target: { value: 'check #ta' } });

    expect(screen.getByRole('option', { name: '#table' })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: '#rule' })).not.toBeInTheDocument();
  });

  it('passes mentions up on send and notifies mentions changes', () => {
    const onSend = vi.fn();
    const onMentionsChange = vi.fn();
    renderBar({ onSend, onMentionsChange });
    const input = screen.getByLabelText('Message input');
    fireEvent.change(input, { target: { value: 'summarize #' } });
    fireEvent.click(screen.getByRole('option', { name: '#table' }));

    // After kind selection the input reads '#table ' and no entity was selected;
    // the mentions change callback is called with an empty resolved array.
    expect(onMentionsChange).toHaveBeenLastCalledWith([]);

    // Close the entity picker, then send.
    fireEvent.keyDown(input, { key: 'Escape' });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onSend).toHaveBeenCalledWith('summarize #table', []);
  });
});
