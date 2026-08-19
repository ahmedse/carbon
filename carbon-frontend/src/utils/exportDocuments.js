// src/utils/exportDocuments.js
// Phase 4C-B — message/conversation document export (Markdown / self-contained
// HTML / client-side .docx). Shared "transcript → rich document" builders so
// message-level and conversation-level exports look identical.
//
// Mermaid diagrams are rasterized to PNG before export (reuses the same render
// pipeline as the live chat). Raw HTML in markdown is intentionally ignored —
// consistent with MarkdownMessage's rendering.

import { unified } from 'unified';
import remarkParse from 'remark-parse';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import remarkRehype from 'remark-rehype';
import rehypeKatex from 'rehype-katex';
import rehypeHighlight from 'rehype-highlight';
import rehypeStringify from 'rehype-stringify';
import {
  AlignmentType,
  BorderStyle,
  Document,
  HeadingLevel,
  ImageRun,
  Packer,
  Paragraph,
  ShadingType,
  Table,
  TableCell,
  TableRow,
  WidthType,
  TextRun,
} from 'docx';
import { slugify, svgToPngBlob } from './exportUtils';

import katexCss from 'katex/dist/katex.min.css?raw';
import hljsGithubCss from 'highlight.js/styles/github.min.css?raw';

// ── Blob / image helpers ───────────────────────────────────────────────────

function blobToDataUri(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

function loadImageSize(dataUri) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve({ width: img.naturalWidth || img.width, height: img.naturalHeight || img.height });
    img.onerror = reject;
    img.src = dataUri;
  });
}

function resolveImageUrl(src) {
  if (!src || src.startsWith('data:') || /^https?:\/\//i.test(src)) return src;
  const base = import.meta.env.VITE_PUBLIC_BASE_URL || '';
  if (src.startsWith('/') && base) return `${base.replace(/\/$/, '')}${src}`;
  if (src.startsWith('/')) return `${window.location.origin}${src}`;
  return src;
}

async function imageToDataUri(src) {
  try {
    const url = resolveImageUrl(src);
    if (url.startsWith('data:')) return url;
    const res = await fetch(url);
    if (!res.ok) return null;
    return blobToDataUri(await res.blob());
  } catch {
    return null;
  }
}

async function renderMermaidPng(code) {
  const mermaid = (await import('mermaid')).default;
  mermaid.initialize({
    startOnLoad: false,
    securityLevel: 'loose',
    theme: 'default',
    fontFamily: 'inherit',
  });
  const id = `mmd-doc-${Date.now()}`;
  const { svg } = await mermaid.render(id, code);
  const doc = new DOMParser().parseFromString(svg, 'image/svg+xml');
  return svgToPngBlob(doc.documentElement, { scale: 2, backgroundColor: '#ffffff' });
}

// ── Markdown AST: parse + materialize (rasterize mermaid, inline images) ────

function parseMarkdown(content) {
  return unified().use(remarkParse).use(remarkGfm).use(remarkMath).parse(content);
}

async function materializeNode(node) {
  if (node.type === 'code' && (node.lang || '').toLowerCase() === 'mermaid') {
    try {
      const blob = await renderMermaidPng(node.value);
      return { type: 'image', url: await blobToDataUri(blob), alt: 'diagram', mermaid: true };
    } catch {
      return node;
    }
  }
  if (node.type === 'image') {
    const dataUri = await imageToDataUri(node.url);
    if (dataUri) return { ...node, url: dataUri };
    return node;
  }
  if (node.children) {
    const children = [];
    for (const child of node.children || []) {
      children.push(await materializeNode(child));
    }
    return { ...node, children };
  }
  return node;
}

// ── HTML document output ───────────────────────────────────────────────────

function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  })[c]);
}

async function astToHtmlFragment(ast) {
  const processor = unified()
    .use(remarkRehype)
    .use(rehypeKatex, { throwOnError: false })
    .use(rehypeHighlight, { ignoreMissing: true })
    .use(rehypeStringify);
  const hast = await processor.run(ast);
  return processor.stringify(hast);
}

const DOC_STYLES = `
  body { font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
         margin: 2rem auto; max-width: 820px; padding: 0 1rem;
         color: #1f2328; line-height: 1.65; }
  h1 { border-bottom: 2px solid #e5e7eb; padding-bottom: .4rem; }
  h2, h3, h4 { margin-top: 1.4rem; }
  table { border-collapse: collapse; width: 100%; margin: 1rem 0; }
  th, td { border: 1px solid #c9ced4; padding: .45rem .65rem; text-align: left; }
  th { background: #f4f5f7; }
  pre { background: #f6f8fa; padding: .8rem; border-radius: 6px;
        overflow-x: auto; border: 1px solid #e1e4e8; }
  code { font-family: Consolas, Menlo, "Courier New", monospace; }
  p > code, li > code { background: #f0f1f3; padding: .1rem .3rem;
        border-radius: 4px; }
  img { max-width: 100%; height: auto; }
  blockquote { border-left: 4px solid #d0d7de; margin: 1rem 0;
        padding: 0 1rem; color: #57606a; }
  .message { margin-bottom: 1.75rem; padding-bottom: 1rem;
        border-bottom: 1px solid #eef0f2; }
  .message .meta { color: #8b949e; font-size: .82rem; margin: .15rem 0 .6rem; }
  hr { border: none; border-top: 1px solid #d0d7de; margin: 1.5rem 0; }
`;

function buildHtmlDocument(bodyHtml, { title = 'AI Message', meta = '' } = {}) {
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escapeHtml(title)}</title>
<style>${DOC_STYLES}</style>
<style>${katexCss}</style>
<style>${hljsGithubCss}</style>
</head>
<body>
<h1>${escapeHtml(title)}</h1>
${meta ? `<div class="meta">${escapeHtml(meta)}</div>` : ''}
${bodyHtml}
</body>
</html>`;
}

export async function markdownToHtmlFragment(content) {
  const ast = await materializeNode(parseMarkdown(content || ''));
  return astToHtmlFragment(ast);
}

export async function buildMessageHtml(content, { title, meta = '' } = {}) {
  const body = await markdownToHtmlFragment(content);
  const safeTitle =
    title || `${String(content || '').replace(/[#*`\n]/g, ' ').trim().slice(0, 60)}…` || 'AI Message';
  return buildHtmlDocument(body, { title: safeTitle, meta });
}

export async function buildConversationHtml(messages, { title = 'Conversation' } = {}) {
  const parts = [];
  for (const m of messages || []) {
    const role = m.role === 'user' ? 'User' : 'Assistant';
    const meta = m.created_at ? `${role} · ${m.created_at}` : role;
    const body = await markdownToHtmlFragment(m.content || '');
    parts.push(
      `<div class="message ${m.role || 'assistant'}"><div class="meta">${escapeHtml(meta)}</div><div class="body">${body}</div></div>`,
    );
  }
  return buildHtmlDocument(parts.join('\n'), { title });
}

// ── DOCX output ────────────────────────────────────────────────────────────

const NUMBERING = {
  config: [
    {
      reference: 'ordered',
      levels: [0, 1, 2].map((level) => ({
        level,
        format: 'decimal',
        text: ['%1.', '%2.', '%3.'][level],
        alignment: AlignmentType.START,
        style: {
          paragraph: { indent: { left: 720 * (level + 1) - 360, hanging: 360 } },
        },
      })),
    },
    {
      reference: 'bullets',
      levels: [0, 1, 2].map((level) => ({
        level,
        format: 'bullet',
        text: ['•', '◦', '▪'][level],
        alignment: AlignmentType.START,
        style: {
          paragraph: { indent: { left: 720 * (level + 1) - 360, hanging: 360 } },
        },
      })),
    },
  ],
};

const TABLE_BORDERS = {
  top: { style: BorderStyle.SINGLE, size: 4, color: 'C9CED4' },
  bottom: { style: BorderStyle.SINGLE, size: 4, color: 'C9CED4' },
  left: { style: BorderStyle.SINGLE, size: 4, color: 'C9CED4' },
  right: { style: BorderStyle.SINGLE, size: 4, color: 'C9CED4' },
  insideHorizontal: { style: BorderStyle.SINGLE, size: 4, color: 'C9CED4' },
  insideVertical: { style: BorderStyle.SINGLE, size: 4, color: 'C9CED4' },
};

function headingLevel(depth) {
  return [HeadingLevel.HEADING_1, HeadingLevel.HEADING_2, HeadingLevel.HEADING_3,
    HeadingLevel.HEADING_4, HeadingLevel.HEADING_5, HeadingLevel.HEADING_6][Math.min(Math.max(depth, 1), 6) - 1];
}

function imageTypeFromDataUri(dataUri) {
  if (/^data:image\/png/i.test(dataUri)) return 'png';
  if (/^data:image\/jpe?g/i.test(dataUri)) return 'jpg';
  if (/^data:image\/gif/i.test(dataUri)) return 'gif';
  if (/^data:image\/bmp/i.test(dataUri)) return 'bmp';
  return 'png';
}

async function imageRunFromDataUri(dataUri) {
  const size = await loadImageSize(dataUri);
  const maxWidth = 480;
  const scale = Math.min(1, maxWidth / (size.width || 1));
  return new ImageRun({
    type: imageTypeFromDataUri(dataUri),
    data: String(dataUri).split(',')[1] || '',
    transformation: {
      width: Math.round((size.width || 1) * scale),
      height: Math.round((size.height || 1) * scale),
    },
  });
}

async function collectRuns(node, fmt = {}) {
  const runs = [];
  for (const child of node.children || []) {
    switch (child.type) {
      case 'text':
        runs.push(new TextRun({ text: child.value, ...fmt }));
        break;
      case 'inlineCode':
        runs.push(
          new TextRun({
            text: child.value,
            font: 'Consolas',
            size: 18,
            shading: { type: ShadingType.CLEAR, fill: 'F2F2F2' },
            ...fmt,
          }),
        );
        break;
      case 'strong':
        runs.push(...(await collectRuns(child, { ...fmt, bold: true })));
        break;
      case 'emphasis':
        runs.push(...(await collectRuns(child, { ...fmt, italics: true })));
        break;
      case 'delete':
        runs.push(...(await collectRuns(child, { ...fmt, strike: true })));
        break;
      case 'link':
        runs.push(...(await collectRuns(child, { ...fmt, color: '0563C1', underline: {} })));
        break;
      case 'image':
        if (child.url && String(child.url).startsWith('data:')) {
          runs.push(await imageRunFromDataUri(child.url));
        }
        break;
      case 'math':
        runs.push(new TextRun({ text: child.value, italics: true, color: '555555' }));
        break;
      default:
        break;
    }
  }
  return runs;
}

function codeParagraph(code) {
  const lines = String(code || '').split('\n');
  const runs = lines.map(
    (line, i) => new TextRun({ text: line, font: 'Consolas', size: 18, break: i > 0 ? 1 : undefined }),
  );
  return new Paragraph({
    children: runs,
    shading: { type: ShadingType.CLEAR, fill: 'F6F8FA' },
    spacing: { before: 120, after: 120 },
    border: {
      left: { style: BorderStyle.SINGLE, size: 12, color: 'E1E4E8', space: 12 },
      top: { style: BorderStyle.SINGLE, size: 4, color: 'E1E4E8', space: 4 },
      bottom: { style: BorderStyle.SINGLE, size: 4, color: 'E1E4E8', space: 4 },
      right: { style: BorderStyle.SINGLE, size: 4, color: 'E1E4E8', space: 4 },
    },
  });
}

function tableFromMdast(node) {
  const rows = node.children || [];
  const docRows = rows.map((row, rowIndex) =>
    new TableRow({
      children: (row.children || []).map((cell) => {
        const header = rowIndex === 0;
        const cellRuns = collectInlineRunsSync(cell, { bold: header });
        return new TableCell({
          shading:
            rowIndex === 0 ? { type: ShadingType.CLEAR, fill: 'EEEEEE' } : undefined,
          width: { size: 100 / Math.max((row.children || []).length, 1), type: WidthType.PERCENTAGE },
          children: [
            new Paragraph({
              children: cellRuns,
              spacing: { before: 40, after: 40 },
            }),
          ],
        });
      }),
    }),
  );
  return new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    borders: TABLE_BORDERS,
    rows: docRows,
  });
}

// Tables need sync run collection — text/inlineCode enough for cells.
function collectInlineRunsSync(node, fmt = {}) {
  const runs = [];
  for (const child of node.children || []) {
    if (child.type === 'text') runs.push(new TextRun({ text: child.value, ...fmt }));
    else if (child.type === 'inlineCode') {
      runs.push(
        new TextRun({
          text: child.value,
          font: 'Consolas',
          size: 18,
          shading: { type: ShadingType.CLEAR, fill: 'F2F2F2' },
          ...fmt,
        }),
      );
    } else if (child.type === 'strong' || child.type === 'emphasis' || child.type === 'link' || child.type === 'delete') {
      runs.push(...collectInlineRunsSync(child, fmt));
    }
  }
  return runs;
}

async function mdastToDocxBlocks(node, depth = 0) {
  const blocks = [];
  for (const child of node.children || []) {
    switch (child.type) {
      case 'heading':
        blocks.push(
          new Paragraph({
            heading: headingLevel(child.depth),
            spacing: { before: 280, after: 140 },
            children: await collectRuns(child),
          }),
        );
        break;
      case 'paragraph':
        blocks.push(
          new Paragraph({ spacing: { after: 120 }, children: await collectRuns(child) }),
        );
        break;
      case 'blockquote':
        blocks.push(
          new Paragraph({
            indent: { left: 480 },
            border: { left: { style: BorderStyle.SINGLE, size: 18, color: '999999', space: 12 } },
            shading: { type: ShadingType.CLEAR, fill: 'FAFAFA' },
            children: await collectRuns(child),
          }),
        );
        break;
      case 'code':
        blocks.push(codeParagraph(child.value));
        break;
      case 'list': {
        const reference = child.ordered ? 'ordered' : 'bullets';
        for (const item of child.children || []) {
          const listParagraphs = await listItemToParagraphs(item, reference, depth);
          blocks.push(...listParagraphs);
        }
        break;
      }
      case 'table':
        blocks.push(tableFromMdast(child));
        break;
      case 'thematicBreak':
        blocks.push(
          new Paragraph({
            children: [new TextRun({ text: '' })],
            border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: 'CCCCCC', space: 1 } },
            spacing: { before: 120, after: 120 },
          }),
        );
        break;
      default:
        break;
    }
  }
  return blocks;
}

async function listItemToParagraphs(item, reference, depth) {
  const blocks = [
    new Paragraph({
      numbering: { reference, level: Math.min(depth, 2) },
      spacing: { after: 60 },
      children: await collectRuns(item),
    }),
  ];
  // Nested lists inside a list item.
  for (const sub of item.children || []) {
    if (sub.type === 'list') {
      for (const subItem of sub.children || []) {
        blocks.push(
          ...(await listItemToParagraphs(subItem, sub.ordered ? 'ordered' : 'bullets', depth + 1)),
        );
      }
    }
  }
  return blocks;
}

async function markdownToDocxBlocks(content) {
  const ast = await materializeNode(parseMarkdown(content || ''));
  return mdastToDocxBlocks(ast);
}

async function packToBlob(children, { title = 'AI Export' } = {}) {
  const doc = new Document({
    title,
    styles: {
      default: {
        document: { run: { font: 'Calibri', size: 22 } },
      },
    },
    numbering: NUMBERING,
    sections: [{ properties: {}, children }],
  });
  return Packer.toBlob(doc);
}

export async function buildMessageDocx(content, { title = 'AI Message', meta = '' } = {}) {
  const children = [];
  if (meta) {
    children.push(new Paragraph({ children: [new TextRun({ text: meta, size: 18, color: '888888' })] }));
  }
  children.push(...(await markdownToDocxBlocks(content)));
  return packToBlob(children, { title });
}

export async function buildConversationDocx(messages, { title = 'Conversation' } = {}) {
  const children = [];
  for (const m of messages || []) {
    const role = m.role === 'user' ? 'User' : 'Assistant';
    children.push(
      new Paragraph({
        heading: HeadingLevel.HEADING_2,
        spacing: { before: 320, after: 60 },
        children: [new TextRun({ text: role })],
      }),
    );
    if (m.created_at) {
      children.push(
        new Paragraph({ children: [new TextRun({ text: `— ${m.created_at}`, size: 18, color: '888888' })] }),
      );
    }
    children.push(...(await markdownToDocxBlocks(m.content || '')));
  }
  return packToBlob(children, { title });
}

// ── Filename helper ────────────────────────────────────────────────────────

export function exportFilename(stem, ext) {
  const safe = slugify(stem) || 'export';
  return `${safe}.${ext}`;
}
