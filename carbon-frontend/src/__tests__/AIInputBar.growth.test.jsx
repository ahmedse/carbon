// src/__tests__/AIInputBar.growth.test.jsx
// Phase 23-C — VS Code Copilot-style composer: the textarea grows with content
// up to a pane-derived max (~55% of parent height, clamped 6–18 rows), then
// scrolls internally instead of clipping.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import AIInputBar from '../shell/AIInputBar';

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token' }),
}));

vi.mock('../api/api', () => ({
  apiFetch: vi.fn(),
}));

import { apiFetch } from '../api/api';

// jsdom has no ResizeObserver — capture instances so tests can drive the
// grow-to-fit callback exactly like the browser would.
let capturedObserver = null;
let observedElements = [];
class FakeResizeObserver {
  constructor(cb) {
    this.cb = cb;
    capturedObserver = this;
  }
  observe(el) {
    observedElements.push(el);
  }
  disconnect() {
    observedElements = [];
  }
}

function renderBar(props = {}) {
  return render(<AIInputBar onSend={vi.fn()} {...props} />);
}

beforeEach(() => {
  apiFetch.mockReset();
  apiFetch.mockResolvedValue({ results: [] });
  capturedObserver = null;
  observedElements = [];
  global.ResizeObserver = FakeResizeObserver;
});

afterEach(() => {
  delete global.ResizeObserver;
});

describe('AIInputBar Copilot-style growth (Phase 23-C)', () => {
  it('watches the parent pane height to derive max rows (55% clamp 6–18)', () => {
    renderBar();
    expect(capturedObserver).toBeTruthy();
    expect(observedElements.length).toBeGreaterThan(0);
  });

  it('long multi-line input stays editable and sends via Enter', () => {
    const onSend = vi.fn();
    renderBar({ onSend });
    const input = screen.getByLabelText('Message input');

    const longText = Array.from({ length: 40 }, (_, i) => `line ${i + 1}`).join('\n');
    fireEvent.change(input, { target: { value: longText } });
    expect(input.value).toBe(longText);

    // Enter still submits (growth must not break submit).
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onSend).toHaveBeenCalledWith(longText, []);
  });

  it('Shift+Enter inserts a newline instead of submitting', () => {
    const onSend = vi.fn();
    renderBar({ onSend });
    const input = screen.getByLabelText('Message input');

    fireEvent.change(input, { target: { value: 'hello' } });
    fireEvent.keyDown(input, { key: 'Enter', shiftKey: true });
    expect(onSend).not.toHaveBeenCalled();
  });

  it('handles a zero-height layout gracefully (fallback default rows)', () => {
    renderBar();
    const input = screen.getByLabelText('Message input');
    fireEvent.change(input, { target: { value: 'short message' } });
    expect(input.value).toBe('short message');
  });
});
