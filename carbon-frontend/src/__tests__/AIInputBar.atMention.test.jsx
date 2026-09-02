// src/__tests__/AIInputBar.atMention.test.jsx
// Phase F2-F — '@'-mention trigger: a fresh trailing '@query' opens a single-stage
// cross-kind typeahead (table/rule/module/org-unit) with a per-kind badge. Selecting
// pins a {kind,id,name} mention and inserts the '@displayName ' token. A resolved
// inline '@South Valley ' (trailing space) must NOT re-trigger the picker.
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

function renderBar(props = {}) {
  return render(<AIInputBar onSend={vi.fn()} {...props} />);
}

beforeEach(() => {
  apiFetch.mockReset();
});

describe('AIInputBar @-mention trigger', () => {
  it('opens a cross-kind picker with org-unit + table matches for @sou', async () => {
    apiFetch.mockImplementation((url) => {
      if (url.includes('mdm/org-units/')) {
        return Promise.resolve([{ id: 7, name: 'South Valley', org_type: 'campus' }]);
      }
      if (url.includes('dataschema/tables/')) {
        return Promise.resolve([{ id: 35, title: 'Electricity', name: 'electricity' }]);
      }
      return Promise.resolve([]);
    });

    renderBar();
    const input = screen.getByLabelText('Message input');
    fireEvent.change(input, { target: { value: '@sou' } });

    await waitFor(() =>
      expect(screen.getByRole('option', { name: /South Valley/i })).toBeInTheDocument(),
    );
    expect(screen.getByRole('option', { name: /Electricity/i })).toBeInTheDocument();

    // Both org-unit and table routes were searched (parallel cross-kind apiFetch).
    expect(apiFetch.mock.calls.some(([url]) => url.includes('mdm/org-units/'))).toBe(true);
    expect(apiFetch.mock.calls.some(([url]) => url.includes('dataschema/tables/'))).toBe(true);
  });

  it('selecting an org-unit pins a {kind,id,name} mention and notifies onMentionsChange', async () => {
    const onMentionsChange = vi.fn();
    apiFetch.mockImplementation((url) => {
      if (url.includes('mdm/org-units/')) {
        return Promise.resolve([{ id: 7, name: 'South Valley', org_type: 'campus' }]);
      }
      return Promise.resolve([]);
    });

    renderBar({ onMentionsChange });
    const input = screen.getByLabelText('Message input');
    fireEvent.change(input, { target: { value: 'meet @sou' } });

    await waitFor(() => screen.getByRole('option', { name: /South Valley/i }));
    fireEvent.click(screen.getByRole('option', { name: /South Valley/i }));

    expect(input.value).toBe('meet @South Valley ');
    await waitFor(() =>
      expect(onMentionsChange).toHaveBeenCalledWith([
        expect.objectContaining({ kind: 'org-unit', id: '7', name: 'South Valley' }),
      ]),
    );
  });

  it('does NOT re-trigger on a resolved inline @displayName with trailing space', () => {
    apiFetch.mockResolvedValue([]);
    renderBar();
    const input = screen.getByLabelText('Message input');
    fireEvent.change(input, { target: { value: 'check @South Valley ' } });

    expect(screen.queryByRole('listbox', { name: /mentions/i })).not.toBeInTheDocument();
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it('Escape closes the @ picker without blocking the textarea', async () => {
    apiFetch.mockResolvedValue([]);
    renderBar();
    const input = screen.getByLabelText('Message input');
    fireEvent.change(input, { target: { value: '@sou' } });

    await waitFor(() =>
      expect(screen.getByRole('listbox', { name: /mentions/i })).toBeInTheDocument(),
    );

    fireEvent.keyDown(input, { key: 'Escape' });
    expect(screen.queryByRole('listbox', { name: /mentions/i })).not.toBeInTheDocument();
  });
});
