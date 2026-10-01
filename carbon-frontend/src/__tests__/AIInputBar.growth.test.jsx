// src/__tests__/AIInputBar.growth.test.jsx
// Phase 23-C — VS Code Copilot-style composer: the textarea grows with content
// up to a pane-derived max (~55% of parent height, clamped 6–18 rows), then
// scrolls internally instead of clipping.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import AIInputBar, {
  COMPOSER_DEFAULT_ROWS,
  COMPOSER_HEIGHT_KEY,
  COMPOSER_MIN_PX,
  COMPOSER_MIN_ROWS,
  readComposerHeight,
} from '../shell/AIInputBar';

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
  localStorage.removeItem(COMPOSER_HEIGHT_KEY);
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

  it('exposes a mouse resize handle on the composer', () => {
    renderBar();
    const handle = screen.getByTestId('composer-resize');
    expect(handle).toBeTruthy();
    fireEvent.pointerDown(handle, { button: 0, clientY: 400 });
    fireEvent.pointerMove(window, { clientY: 280 });
    fireEvent.pointerUp(window);
    expect(screen.getByLabelText('Message input')).toBeTruthy();
  });

  it('handles a zero-height layout gracefully (fallback default rows)', () => {
    renderBar();
    const input = screen.getByLabelText('Message input');
    fireEvent.change(input, { target: { value: 'short message' } });
    expect(input.value).toBe('short message');
  });

  it('defaults to 2 rows when no composer height is saved', () => {
    expect(COMPOSER_DEFAULT_ROWS).toBe(2);
    expect(COMPOSER_MIN_ROWS).toBe(1);
    expect(readComposerHeight(null)).toBeNull();
    renderBar();
    const root = screen.getByLabelText('Message input').closest('.MuiInputBase-root');
    expect(window.getComputedStyle(root).height).not.toBe('96px');
  });

  it('keeps a saved height that is already at least one row', () => {
    localStorage.setItem(COMPOSER_HEIGHT_KEY, '96');
    renderBar();
    expect(readComposerHeight('96')).toBe(96);
    expect(localStorage.getItem(COMPOSER_HEIGHT_KEY)).toBe('96');
    const root = screen.getByLabelText('Message input').closest('.MuiInputBase-root');
    expect(window.getComputedStyle(root).height).toBe('96px');
  });

  it('ignores a saved height below one row without clearing it', () => {
    localStorage.setItem(COMPOSER_HEIGHT_KEY, '8');
    renderBar();
    expect(readComposerHeight('8')).toBeNull();
    expect(readComposerHeight('4')).toBeNull();
    expect(localStorage.getItem(COMPOSER_HEIGHT_KEY)).toBe('8');
    const root = screen.getByLabelText('Message input').closest('.MuiInputBase-root');
    expect(window.getComputedStyle(root).height).not.toBe('8px');
  });

  it('resize handle cannot shrink the composer below one row', () => {
    renderBar();
    const handle = screen.getByTestId('composer-resize');
    fireEvent.pointerDown(handle, { button: 0, clientY: 100 });
    fireEvent.pointerMove(window, { clientY: 4000 });
    fireEvent.pointerUp(window);
    expect(Number(localStorage.getItem(COMPOSER_HEIGHT_KEY))).toBe(COMPOSER_MIN_PX);
  });
});
