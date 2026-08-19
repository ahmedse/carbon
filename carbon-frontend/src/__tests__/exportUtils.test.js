// src/__tests__/exportUtils.test.js
// Phase 4C — rich copy/export primitives.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  applyComputedStyles,
  buildRichClipboardPayload,
  cleanPlainText,
  collectMediaItems,
  handleRichCopyEvent,
  rewriteLinks,
  slugify,
  svgToPngBlob,
  writeClipboard,
} from '../utils/exportUtils';

// ── Fixtures ────────────────────────────────────────────────────────────────

const RICH_HTML_FIXTURE = `
<div id="msg">
  <table>
    <thead><tr><th>Metric</th><th>Value</th></tr></thead>
    <tbody><tr><td>tCO2e</td><td>1,234</td></tr></tbody>
  </table>
  <pre><code class="language-js">const x = 1;</code></pre>
  <svg id="mmd-1-1700000000000" width="100" height="50">
    <rect width="100" height="50" fill="red"></rect>
  </svg>
  <img src="/mediafiles/report.png" alt="Figure A">
  <button>strip me</button>
  <span aria-hidden="true">icon</span>
</div>`;

function mountFixture() {
  document.body.innerHTML = RICH_HTML_FIXTURE;
  return document.getElementById('msg');
}

beforeEach(() => {
  // Browser APIs jsdom does not implement.
  URL.createObjectURL = vi.fn(() => 'blob:mock');
  URL.revokeObjectURL = vi.fn();
  vi.stubGlobal(
    'Image',
    class {
      set src(_value) {
        queueMicrotask(() => this.onload?.());
      }
    },
  );
  HTMLCanvasElement.prototype.getContext = vi.fn(() => ({ fillRect: vi.fn(), drawImage: vi.fn() }));
  HTMLCanvasElement.prototype.toBlob = vi.fn(function toBlob(cb) {
    cb(new Blob(['png'], { type: 'image/png' }));
  });
  vi.stubGlobal(
    'FileReader',
    class {
      constructor() {
        this.result = null;
        this.onload = null;
      }
      readAsDataURL() {
        this.result = 'data:image/png;base64,aW1nZGF0YQ==';
        if (typeof this.onload === 'function') this.onload();
      }
    },
  );
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    blob: () => Promise.resolve(new Blob(['img'], { type: 'image/png' })),
  });
});

// ── slugify / cleanPlainText ────────────────────────────────────────────────

describe('slugify', () => {
  it('slugifies text into a safe filename stem', () => {
    expect(slugify('My Diagram 1!')).toBe('my-diagram-1');
    expect(slugify('a/b\\c')).toBe('a-b-c');
    expect(slugify('Charts & Graphs')).toBe('charts-graphs');
  });

  it('falls back for empty/junk input', () => {
    expect(slugify('')).toBe('file');
    expect(slugify('!!!')).toBe('file');
  });
});

describe('cleanPlainText', () => {
  it('trims and collapses runs of blank lines (keeps code indentation)', () => {
    expect(cleanPlainText('  a  \n\n\n\n  b  ')).toBe('a\n\n  b');
  });

  it('normalizes non-breaking spaces', () => {
    expect(cleanPlainText('a\u00a0b')).toBe('a b');
  });
});

// ── applyComputedStyles ─────────────────────────────────────────────────────

describe('applyComputedStyles', () => {
  it('copies relevant computed styles onto the clone in lockstep', () => {
    document.body.innerHTML = '<div id="src"><p>hi</p><span>there</span></div>';
    const src = document.getElementById('src');
    const dst = src.cloneNode(true);
    const getPropertyValue = vi.fn((prop) => {
      if (prop === 'color') return 'rgb(1, 2, 3)';
      if (prop === 'font-weight') return '700';
      return '';
    });
    window.getComputedStyle = vi.fn(() => ({ getPropertyValue }));

    applyComputedStyles(src, dst);

    expect(dst.querySelector('p').getAttribute('style')).toContain('color:rgb(1, 2, 3)');
    expect(dst.querySelector('p').getAttribute('style')).toContain('font-weight:700');
  });

  it('tolerates null roots', () => {
    expect(() => applyComputedStyles(null, null)).not.toThrow();
  });
});

// ── rewriteLinks ────────────────────────────────────────────────────────────

describe('rewriteLinks', () => {
  it('keeps internal links relative when no public base is configured', () => {
    document.body.innerHTML = '<div><a href="/app/charts">Charts</a><a href="https://x.dev">X</a></div>';
    const root = document.body.firstChild;
    rewriteLinks(root);
    const internal = root.querySelector('a[href="/app/charts"]');
    // No VITE_PUBLIC_BASE_URL in tests → href removed, no host leakage.
    expect(internal).toBeNull();
    expect(root.querySelectorAll('a[href]')).toHaveLength(1);
  });
});

// ── buildRichClipboardPayload ───────────────────────────────────────────────

describe('buildRichClipboardPayload', () => {
  it('produces a Word-ready fragment with inlined images and stripped chrome', async () => {
    const node = mountFixture();
    const { html, text } = await buildRichClipboardPayload(node);

    expect(html).toContain('<!--StartFragment-->');
    expect(html).toContain('<!--EndFragment-->');

    // Table borders forced for Word.
    expect(html).toContain('border-collapse: collapse');
    expect(html).toContain('border: 1px solid');

    // Mermaid diagram rasterized to an inline PNG data URI.
    expect(html).toContain('data:image/png;base64,aW1nZGF0YQ==');
    expect(html).not.toContain('mmd-1-1700000000000');

    // Raster figure inlined as data URI.
    expect(html.match(/data:image\/png;base64/g).length).toBeGreaterThanOrEqual(2);

    // Interactive chrome stripped.
    expect(html).not.toContain('strip me');
    expect(html).not.toContain('aria-hidden');

    // Plain text payload keeps readable content.
    expect(text).toContain('Metric');
    expect(text).toContain('const x = 1');
  });
});

// ── writeClipboard ──────────────────────────────────────────────────────────

describe('writeClipboard', () => {
  it('writes both MIME types via ClipboardItem', async () => {
    vi.stubGlobal(
      'ClipboardItem',
      class ClipboardItemMock {
        constructor(items) {
          this.items = items;
        }
      },
    );
    Object.assign(navigator, { clipboard: { write: vi.fn().mockResolvedValue(undefined) } });

    await writeClipboard('<p>hi</p>', 'hi');

    const payload = navigator.clipboard.write.mock.calls[0][0][0].items;
    expect(payload['text/html']).toBeInstanceOf(Blob);
    expect(payload['text/plain']).toBeInstanceOf(Blob);
  });
});

// ── collectMediaItems ───────────────────────────────────────────────────────

describe('collectMediaItems', () => {
  it('lists mermaid diagrams and raster figures with safe names', () => {
    document.body.innerHTML = `
      <div id="m">
        <svg id="mmd-1-1" width="10" height="10"></svg>
        <svg id="mmd-2-2" width="10" height="10"></svg>
        <img alt="Fig B" src="/x.png">
      </div>`;
    const items = collectMediaItems(document.getElementById('m'));

    expect(items).toHaveLength(3);
    expect(items[0]).toMatchObject({ kind: 'diagram', label: 'Diagram 1', nameBase: 'diagram-1' });
    expect(items[0].svg).toBeTypeOf('function');
    expect(items[2]).toMatchObject({ kind: 'figure', label: 'Fig B', nameBase: 'fig-b' });
    expect(items[2].svg).toBeNull();
  });

  it('returns an empty list for an empty node', () => {
    document.body.innerHTML = '<div id="e"></div>';
    expect(collectMediaItems(document.getElementById('e'))).toEqual([]);
    expect(collectMediaItems(null)).toEqual([]);
  });
});

// ── handleRichCopyEvent ─────────────────────────────────────────────────────

describe('handleRichCopyEvent', () => {
  it('lets the default behavior run when there is no selection', () => {
    window.getSelection = vi.fn(() => ({ rangeCount: 0 }));
    const handled = handleRichCopyEvent({ clipboardData: { setData: vi.fn() } }, { contentNode: null });
    expect(handled).toBe(true);
  });

  it('lets the default behavior run for a collapsed selection', () => {
    window.getSelection = vi.fn(() => ({ rangeCount: 1, isCollapsed: true }));
    const handled = handleRichCopyEvent({ clipboardData: { setData: vi.fn() } }, { contentNode: null });
    expect(handled).toBe(true);
  });

  it('writes rich HTML + plain text for a selection inside the content node', () => {
    document.body.innerHTML = '<div id="msg"><p>Hello <strong>world</strong></p></div>';
    const contentNode = document.getElementById('msg');
    const range = document.createRange();
    range.selectNodeContents(contentNode);
    window.getSelection = vi.fn(() => ({
      rangeCount: 1,
      isCollapsed: false,
      anchorNode: contentNode,
      getRangeAt: () => range,
      toString: () => 'Hello world',
    }));

    const setData = vi.fn();
    const handled = handleRichCopyEvent({ clipboardData: { setData } }, { contentNode });

    expect(handled).toBe(false);
    expect(setData).toHaveBeenCalledWith('text/html', expect.stringContaining('<!--StartFragment-->'));
    expect(setData).toHaveBeenCalledWith('text/plain', 'Hello world');
  });

  it('ignores selections anchored outside the content node', () => {
    document.body.innerHTML = '<div id="msg"><p>inside</p></div><div id="out">outside</div>';
    const contentNode = document.getElementById('msg');
    window.getSelection = vi.fn(() => ({
      rangeCount: 1,
      isCollapsed: false,
      anchorNode: document.getElementById('out'),
    }));
    const handled = handleRichCopyEvent({ clipboardData: { setData: vi.fn() } }, { contentNode });
    expect(handled).toBe(true);
  });
});

// ── svgToPngBlob ────────────────────────────────────────────────────────────

describe('svgToPngBlob', () => {
  it('rasterizes at scale using the SVG natural size', async () => {
    document.body.innerHTML = `
      <svg id="s" width="100" height="50" xmlns="http://www.w3.org/2000/svg">
        <rect width="100" height="50" fill="red"></rect>
      </svg>`;
    const canvasDims = [];
    HTMLCanvasElement.prototype.toBlob = vi.fn(function toBlob(cb) {
      canvasDims.push({ w: this.width, h: this.height });
      cb(new Blob(['png'], { type: 'image/png' }));
    });

    const blob = await svgToPngBlob(document.getElementById('s'), { scale: 2 });

    expect(blob).toBeInstanceOf(Blob);
    expect(canvasDims).toEqual([{ w: 200, h: 100 }]);
    expect(URL.createObjectURL).toHaveBeenCalled();
    expect(URL.revokeObjectURL).toHaveBeenCalled();
  });
});
