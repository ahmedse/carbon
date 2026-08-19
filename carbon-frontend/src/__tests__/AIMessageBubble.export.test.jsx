// src/__tests__/AIMessageBubble.export.test.jsx
// Phase 4C — rich copy, selection copy, image export, long-content collapse.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import AIMessageBubble from '../shell/AIMessageBubble';

// Mermaid is lazy-loaded by MarkdownMessage — stub it so diagrams render in jsdom.
vi.mock('mermaid', () => ({
  default: {
    initialize: vi.fn(),
    render: vi.fn().mockResolvedValue({
      svg: '<svg id="mmd-mock-1" width="120" height="60" xmlns="http://www.w3.org/2000/svg"><rect width="120" height="60" fill="#ccc"></rect></svg>',
    }),
  },
}));

// Keep real serialization helpers, spy the heavy/external ones.
vi.mock('../utils/exportUtils', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    copyRich: vi.fn().mockResolvedValue('rich'),
    downloadMediaItem: vi.fn().mockResolvedValue(undefined),
    downloadZip: vi.fn().mockResolvedValue(undefined),
    downloadBlob: vi.fn(),
  };
});
import { copyRich, downloadBlob, downloadMediaItem } from '../utils/exportUtils';

const assistantMessage = {
  id: 'msg-1',
  role: 'assistant',
  content: 'Here is the answer with **bold** and a table.',
  created_at: '2026-08-15T10:00:00Z',
  outcome: null,
};

const diagramMessage = {
  id: 'msg-2',
  role: 'assistant',
  content: '```mermaid\nflowchart LR\nA-->B\n```',
  created_at: '2026-08-15T10:00:00Z',
  outcome: null,
};

function renderBubble(message, props = {}) {
  return render(
    <MemoryRouter>
      <AIMessageBubble message={message} {...props} />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  Object.assign(navigator, {
    clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
  });
});

describe('AIMessageBubble rich copy (Phase 4C)', () => {
  it('copies the whole message with formatting on the copy button', async () => {
    renderBubble(assistantMessage);

    fireEvent.click(screen.getByRole('button', { name: 'Copy message' }));

    await waitFor(() => expect(copyRich).toHaveBeenCalledTimes(1));
    const [node, options] = copyRich.mock.calls[0];
    expect(node.getAttribute('data-testid')).toBe('message-content');
    expect(options.plainText).toContain('Here is the answer');
  });

  it('offers plain-text and markdown copy from the overflow menu', async () => {
    renderBubble(assistantMessage, { onRetry: vi.fn() });

    fireEvent.click(screen.getByRole('button', { name: 'More message actions' }));

    expect(await screen.findByRole('menuitem', { name: 'Copy plain text' })).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: 'Copy markdown' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('menuitem', { name: 'Copy markdown' }));
    await waitFor(() =>
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith(assistantMessage.content),
    );
  });

  it('intercepts Ctrl+C with a selection and writes rich HTML + plain text', () => {
    const { container } = renderBubble(assistantMessage);
    const bubbleRoot = container.firstChild;
    const contentNode = bubbleRoot.querySelector('[data-testid="message-content"]');

    const range = document.createRange();
    range.selectNodeContents(contentNode);
    window.getSelection = vi.fn(() => ({
      rangeCount: 1,
      isCollapsed: false,
      anchorNode: contentNode,
      getRangeAt: () => range,
      toString: () => 'selected part',
    }));

    const setData = vi.fn();
    fireEvent.copy(bubbleRoot, { clipboardData: { setData } });

    expect(setData).toHaveBeenCalledWith('text/html', expect.stringContaining('<!--StartFragment-->'));
    expect(setData).toHaveBeenCalledWith('text/plain', 'selected part');
  });

  it('does not intercept Ctrl+C when nothing is selected', () => {
    const { container } = renderBubble(assistantMessage);
    window.getSelection = vi.fn(() => ({ rangeCount: 0 }));

    const setData = vi.fn();
    fireEvent.copy(container.firstChild, { clipboardData: { setData } });
    expect(setData).not.toHaveBeenCalled();
  });
});

describe('AIMessageBubble image export (Phase 4C)', () => {
  it('shows a Save-images menu with per-diagram PNG/SVG actions once a diagram renders', async () => {
    renderBubble(diagramMessage);

    const saveButton = await screen.findByRole('button', { name: 'Save images' });
    fireEvent.click(saveButton);

    const pngItem = await screen.findByRole('menuitem', { name: 'Diagram 1 — PNG' });
    expect(screen.getByRole('menuitem', { name: 'Diagram 1 — SVG' })).toBeInTheDocument();

    fireEvent.click(pngItem);
    await waitFor(() => expect(downloadMediaItem).toHaveBeenCalledTimes(1));
    expect(downloadMediaItem.mock.calls[0][0]).toMatchObject({ kind: 'diagram', label: 'Diagram 1' });
    expect(downloadMediaItem.mock.calls[0][1]).toBe('png');
  });

  it('does not show a Save-images button for messages without media', () => {
    renderBubble(assistantMessage);
    expect(screen.queryByRole('button', { name: 'Save images' })).not.toBeInTheDocument();
  });
});

describe('AIMessageBubble message export (Phase 4C-B)', () => {
  it('exposes an Export message submenu with all three formats', async () => {
    renderBubble(assistantMessage, { onRetry: vi.fn() });

    fireEvent.click(screen.getByRole('button', { name: 'More message actions' }));
    fireEvent.click(await screen.findByRole('menuitem', { name: 'Export message' }));

    expect(await screen.findByRole('menuitem', { name: 'Markdown (.md)' })).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: 'HTML (.html)' })).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: 'Word (.docx)' })).toBeInTheDocument();
  });

  it('downloads a .md file when Markdown is chosen', async () => {
    const onNotify = vi.fn();
    renderBubble(assistantMessage, { onRetry: vi.fn(), onNotify });

    fireEvent.click(screen.getByRole('button', { name: 'More message actions' }));
    fireEvent.click(await screen.findByRole('menuitem', { name: 'Export message' }));
    fireEvent.click(await screen.findByRole('menuitem', { name: 'Markdown (.md)' }));

    await waitFor(() => expect(downloadBlob).toHaveBeenCalledTimes(1));
    expect(downloadBlob.mock.calls[0][0]).toBeInstanceOf(Blob);
    expect(downloadBlob.mock.calls[0][1]).toMatch(/\.md$/);
    await waitFor(() =>
      expect(onNotify).toHaveBeenCalledWith(expect.objectContaining({ type: 'success' })),
    );
  });
});
