// src/__tests__/exportDocuments.test.js
// Phase 4C-B — document export builders (markdown / self-contained HTML / .docx).
import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  buildConversationDocx,
  buildConversationHtml,
  buildMessageDocx,
  buildMessageHtml,
  exportFilename,
  markdownToHtmlFragment,
} from '../utils/exportDocuments';

vi.mock('mermaid', () => ({
  default: {
    initialize: vi.fn(),
    render: vi.fn().mockResolvedValue({
      svg: '<svg id="mmd-doc-1" width="120" height="60" xmlns="http://www.w3.org/2000/svg"><rect width="120" height="60" fill="#ccc"></rect></svg>',
    }),
  },
}));

// Vitest stubs ?raw CSS imports to empty strings; mock them so the embedded
// vendor styles are exercised (real content is verified in the browser build).
vi.mock('katex/dist/katex.min.css?raw', () => ({
  default: '.katex{color:red}',
}));
vi.mock('highlight.js/styles/github.min.css?raw', () => ({
  default: '.github{border:0}',
}));

const MARKDOWN = `# Emissions Summary

| Metric | Value |
| ------ | ----- |
| tCO2e  | 1,234 |

\`\`\`mermaid
flowchart LR
A-->B
\`\`\`

Some **bold** and \`inline\` code.

- item one
- item two
`;

beforeEach(() => {
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

describe('exportFilename', () => {
  it('slugifies the stem and appends the extension', () => {
    expect(exportFilename('My Report!', 'docx')).toBe('my-report.docx');
    expect(exportFilename('!!!', 'html')).toBe('file.html');
  });
});

describe('markdownToHtmlFragment', () => {
  it('renders markdown to HTML with tables and code highlighted', async () => {
    const html = await markdownToHtmlFragment('| A | B |\n| - | - |\n| 1 | 2 |\n\n```js\nconst x = 1;\n```');
    expect(html).toContain('<table>');
    expect(html).toContain('<td>1</td>');
    expect(html).toContain('hljs'); // highlight.js classes applied
    // highlight.js wraps tokens in spans — assert across the markup.
    expect(html).toMatch(/const<\/span>\s*x =/);
  });

  it('rasterizes mermaid blocks to embedded PNG data URIs', async () => {
    const html = await markdownToHtmlFragment('```mermaid\nflowchart LR\nA-->B\n```');
    expect(html).toContain('<img src="data:image/png;base64,aW1nZGF0YQ=="');
    expect(html).not.toContain('flowchart LR');
  });

  it('inlines raster image URLs as data URIs', async () => {
    const html = await markdownToHtmlFragment('![chart](/mediafiles/report.png)');
    expect(html).toContain('data:image/png;base64,aW1nZGF0YQ==');
  });
});

describe('buildMessageHtml', () => {
  it('wraps content in a self-contained document with embedded styles', async () => {
    const html = await buildMessageHtml(MARKDOWN, { title: 'Emissions <Report>' });
    expect(html).toContain('<!DOCTYPE html>');
    expect(html).toContain('<title>Emissions &lt;Report&gt;</title>');
    expect(html).toContain('border-collapse: collapse');
    expect(html).toContain('.katex{color:red}'); // KaTeX CSS embedded
    expect(html).toContain('.github{border:0}'); // syntax theme embedded
    expect(html).toContain('data:image/png;base64'); // rasterized diagram
    expect(html).not.toContain('```mermaid');
  });
});

describe('buildConversationHtml', () => {
  it('builds a transcript with roles and timestamps', async () => {
    const messages = [
      { role: 'user', content: 'Hello', created_at: '2026-08-15T10:00:00Z' },
      { role: 'assistant', content: 'Hi **there**', created_at: '2026-08-15T10:00:01Z' },
    ];
    const html = await buildConversationHtml(messages, { title: 'My Thread' });
    expect(html).toContain('<title>My Thread</title>');
    expect(html).toContain('User · 2026-08-15T10:00:00Z');
    expect(html).toContain('Assistant · 2026-08-15T10:00:01Z');
    expect(html).toContain('<strong>there</strong>');
  });
});

describe('docx builders', () => {
  it('builds a real .docx blob for a message', async () => {
    const blob = await buildMessageDocx(MARKDOWN, { title: 'Emissions' });
    expect(blob).toBeInstanceOf(Blob);
    expect(blob.type).toBe('application/vnd.openxmlformats-officedocument.wordprocessingml.document');
    expect(blob.size).toBeGreaterThan(500); // a packed OOXML zip
  });

  it('builds a .docx transcript with per-message headings', async () => {
    const messages = [
      { role: 'user', content: 'Question?', created_at: '2026-08-15T10:00:00Z' },
      { role: 'assistant', content: 'Answer.', created_at: '2026-08-15T10:00:01Z' },
    ];
    const blob = await buildConversationDocx(messages, { title: 'Thread' });
    expect(blob).toBeInstanceOf(Blob);
    expect(blob.type).toContain('openxmlformats');
    expect(blob.size).toBeGreaterThan(500);
  });
});
