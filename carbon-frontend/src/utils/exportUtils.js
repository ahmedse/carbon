// src/utils/exportUtils.js
// ────────────────────────────────────────────────────────────────────────────
// RICH COPY / EXPORT PRIMITIVES (Phase 4C).
//
// Everything here is pure, unit-testable, and browser-native — no server
// round-trip. The core idea: the user must get *what they see*, so we serialize
// the ALREADY-RENDERED DOM (computed styles inlined) instead of re-rendering
// markdown — zero double-rendering drift.
//
// Two copy paths:
//   1. Button copy (async)  — best Word fidelity: mermaid diagrams are
//      rasterized to PNG, exact computed styles inlined, table borders forced.
//   2. Ctrl+C selection (sync) — ClipboardEvent handler: tag-based defaults
//      (headings/lists/code mono/table borders) + inline SVG for diagrams;
//      syntax-highlight colors are a button-copy luxury (documented).
//
// Word compatibility rules (research): inline styles over classes; `table`
// needs explicit `border-collapse` + cell borders; `<!--StartFragment-->`
// markers; semantic tags (h1–h6, p, ul/ol/li, pre/code, img, blockquote).
// ────────────────────────────────────────────────────────────────────────────

// ── Small helpers ───────────────────────────────────────────────────────────

/** Slugify a string into a safe filename stem (no separators, no traversal). */
export function slugify(value) {
  const s = String(value ?? '')
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60);
  return s || 'file';
}

/** Trigger a browser download for a Blob. */
export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  // Revoke after the download has had a chance to start.
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}

function loadImage(src) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error('Could not load image'));
    img.src = src;
  });
}

function canvasToBlob(canvas, type = 'image/png') {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error('Canvas export failed'))), type);
  });
}

/** Read the natural (attribute) size of an SVG, falling back to layout size. */
function svgNaturalSize(svgEl) {
  const parsePx = (v) => {
    const n = parseFloat(v);
    return Number.isFinite(n) && n > 0 ? n : 0;
  };
  let width = parsePx(svgEl.getAttribute('width'));
  let height = parsePx(svgEl.getAttribute('height'));
  const vb = svgEl.getAttribute('viewBox');
  if (vb) {
    const parts = vb.split(/[\s,]+/).map(Number);
    if (parts.length === 4) {
      if (!width && parts[2] > 0) width = parts[2];
      if (!height && parts[3] > 0) height = parts[3];
    }
  }
  if (!width) width = svgEl.clientWidth || 800;
  if (!height) height = svgEl.clientHeight || 600;
  return { width, height };
}

/** Serialize an SVG element to a standalone SVG string. */
export function serializeSvg(svgEl) {
  const clone = svgEl.cloneNode(true);
  let source = new XMLSerializer().serializeToString(clone);
  if (!source.includes('xmlns=')) {
    source = source.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"');
  }
  return source;
}

// ── Rasterization ───────────────────────────────────────────────────────────

/**
 * Rasterize an SVG element to a PNG Blob (retina-friendly via `scale`).
 * Uses the SVG's natural (attribute) size so diagrams export at full
 * resolution even when CSS shrinks them on screen.
 */
export async function svgToPngBlob(svgEl, { scale = 2, backgroundColor = '#ffffff' } = {}) {
  const { width, height } = svgNaturalSize(svgEl);
  const w = Math.max(1, Math.round(width * scale));
  const h = Math.max(1, Math.round(height * scale));

  const source = serializeSvg(svgEl);
  // Re-parse so we can set explicit pixel dimensions on the clone.
  const doc = new DOMParser().parseFromString(source, 'image/svg+xml');
  const svg = doc.documentElement;
  svg.setAttribute('width', String(w));
  svg.setAttribute('height', String(h));

  const svgBlob = new Blob([new XMLSerializer().serializeToString(svg)], { type: 'image/svg+xml;charset=utf-8' });
  const url = URL.createObjectURL(svgBlob);
  try {
    const img = await loadImage(url);
    const canvas = document.createElement('canvas');
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext('2d');
    if (ctx) {
      ctx.fillStyle = backgroundColor;
      ctx.fillRect(0, 0, w, h);
      ctx.drawImage(img, 0, 0, w, h);
    }
    return canvasToBlob(canvas, 'image/png');
  } finally {
    URL.revokeObjectURL(url);
  }
}

/** Serialize an SVG element to an SVG Blob. */
export function svgToSvgBlob(svgEl) {
  return new Blob([serializeSvg(svgEl)], { type: 'image/svg+xml;charset=utf-8' });
}

/**
 * Fetch a raster image as a Blob (same-origin mediafiles are fetched directly).
 * Returns null when the image cannot be fetched (cross-origin without CORS).
 */
export async function imgToBlob(imgEl) {
  const src = imgEl?.currentSrc || imgEl?.src;
  if (!src) return null;
  try {
    const res = await fetch(src);
    if (!res.ok) return null;
    return res.blob();
  } catch {
    return null;
  }
}

function dataUrlFromBlob(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(new Error('Could not read image'));
    reader.readAsDataURL(blob);
  });
}

// ── DOM serialization ────────────────────────────────────────────────────────

// Computed styles worth carrying into Word/external apps (curated — keeps the
// exported HTML small and Word-friendly, avoids MUI noise).
const STYLE_PROPS = [
  'color',
  'background-color',
  'font-family',
  'font-size',
  'font-weight',
  'font-style',
  'text-align',
  'text-decoration',
  'border',
  'padding',
  'margin',
  'white-space',
  'line-height',
];

/**
 * Walk `srcRoot` (live DOM) and `dstRoot` (its clone) in lockstep, copying the
 * relevant computed styles from each live element onto the clone's `style`
 * attribute. Positional pairing is safe because `dstRoot` is a deep clone of
 * `srcRoot` made before any structural edits.
 */
export function applyComputedStyles(srcRoot, dstRoot) {
  if (!srcRoot || !dstRoot) return;
  const walk = (src, dst) => {
    if (!src || !dst) return;
    if (src.nodeType === 1 && dst.nodeType === 1) {
      const cs = window.getComputedStyle(src);
      const styles = [];
      for (const prop of STYLE_PROPS) {
        const value = cs.getPropertyValue(prop);
        if (value && value !== 'none') styles.push(`${prop}:${value}`);
      }
      if (styles.length) {
        const existing = dst.getAttribute('style') || '';
        dst.setAttribute('style', existing ? `${existing};${styles.join(';')}` : styles.join(';'));
      }
    }
    const srcChildren = src.children;
    const dstChildren = dst.children;
    const n = Math.max(srcChildren.length, dstChildren.length);
    for (let i = 0; i < n; i += 1) walk(srcChildren[i], dstChildren[i]);
  };
  walk(srcRoot, dstRoot);
}

/** Strip interactive/UI chrome from a clone so exports carry content only. */
export function stripInteractive(root) {
  if (!root) return;
  root
    .querySelectorAll('button, [role="tooltip"], [aria-hidden="true"], .MuiTooltip-popper, .MuiSvgIcon-root')
    .forEach((el) => el.remove());
  // Any leftover non-mermaid svg (icons) is removed; mermaid diagrams (mmd-)
  // are handled by the caller (inlined to PNG or kept as SVG markup).
}

/** Force borders on tables so Word renders them as real tables. */
export function enforceTableBorders(root) {
  if (!root) return;
  root.querySelectorAll('table').forEach((table) => {
    table.style.borderCollapse = 'collapse';
    table.style.width = '100%';
    table.querySelectorAll('th, td').forEach((cell) => {
      cell.style.border = '1px solid #c9ced4';
      cell.style.padding = '4px 8px';
    });
  });
}

/** Rewrite internal SPA links: absolute when a public base is configured. */
export function rewriteLinks(root) {
  if (!root) return;
  const base = (import.meta.env.VITE_PUBLIC_BASE_URL || '').replace(/\/+$/, '');
  root.querySelectorAll('a[href]').forEach((a) => {
    const href = a.getAttribute('href');
    if (href && href.startsWith('/') && base) {
      a.setAttribute('href', `${base}${href}`);
      a.setAttribute('target', '_blank');
    } else if (href && href.startsWith('/')) {
      // Keep relative text link — no internal host leakage without a base URL.
      a.removeAttribute('href');
    }
  });
}

/** Wrap content in the Word clipboard-fragment convention. */
export function wordFragment(innerHtml) {
  return (
    '<!--StartFragment--><div style="font-family:Segoe UI, Arial, sans-serif;' +
    'font-size:11pt;color:#1f2937;line-height:1.5;word-wrap:break-word;">' +
    `${innerHtml}</div><!--EndFragment-->`
  );
}

/** Clean textContent for clipboard plain-text payloads. */
export function cleanPlainText(text) {
  return String(text ?? '')
    .replace(/\u00a0/g, ' ')
    .split('\n')
    .map((line) => line.replace(/\s+$/g, ''))
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

/**
 * Build the rich clipboard payload ({ html, text }) from a rendered content
 * node. Async: mermaid SVGs are rasterized to PNG and <img> sources are
 * embedded as data URIs (best Word fidelity).
 */
export async function buildRichClipboardPayload(node, { plainText } = {}) {
  const clone = node.cloneNode(true);

  // 1. Inline mermaid diagrams as PNG data URIs.
  const svgs = Array.from(clone.querySelectorAll('svg[id^="mmd-"]'));
  await Promise.all(
    svgs.map(async (svg) => {
      try {
        const png = await svgToPngBlob(svg, { scale: 2 });
        const dataUri = await dataUrlFromBlob(png);
        const img = document.createElement('img');
        img.src = dataUri;
        img.style.maxWidth = '100%';
        img.style.display = 'block';
        svg.replaceWith(img);
      } catch {
        // Keep the SVG markup as-is (Word 2016+ can render inline SVG).
      }
    }),
  );

  // 2. Inline raster images as data URIs.
  const imgs = Array.from(clone.querySelectorAll('img'));
  await Promise.all(
    imgs.map(async (img) => {
      try {
        const blob = await imgToBlob(img);
        if (blob) img.src = await dataUrlFromBlob(blob);
      } catch {
        // Keep the original src.
      }
    }),
  );

  // 3. Strip chrome, copy computed styles, force table borders, fix links.
  stripInteractive(clone);
  applyComputedStyles(node, clone);
  enforceTableBorders(clone);
  rewriteLinks(clone);

  const html = wordFragment(clone.outerHTML);
  const text = cleanPlainText(plainText ?? clone.textContent);
  return { html, text };
}

// ── Clipboard writes ─────────────────────────────────────────────────────────

/** Write both MIME types via the modern ClipboardItem API. */
export async function writeClipboard(html, text) {
  if (typeof ClipboardItem !== 'undefined' && navigator.clipboard?.write) {
    await navigator.clipboard.write([
      new ClipboardItem({
        'text/plain': new Blob([text], { type: 'text/plain' }),
        'text/html': new Blob([html], { type: 'text/html' }),
      }),
    ]);
    return;
  }
  // Legacy fallback (HTTP contexts, older engines).
  legacyCopy(html, text);
}

/** Synchronous execCommand fallback — still honored by every browser. */
export function legacyCopy(html, _text) {
  // `_text` is intentionally unused: the container below carries the rich HTML
  // (which includes the readable text), and execCommand copies its contents.
  const container = document.createElement('div');
  container.innerHTML = html;
  container.style.position = 'fixed';
  container.style.left = '-9999px';
  container.style.top = '0';
  container.style.opacity = '0';
  container.setAttribute('contenteditable', 'true');
  document.body.appendChild(container);
  const range = document.createRange();
  range.selectNodeContents(container);
  const selection = window.getSelection();
  if (selection) {
    selection.removeAllRanges();
    selection.addRange(range);
  }
  let ok = false;
  try {
    ok = document.execCommand('copy');
  } catch {
    ok = false;
  }
  if (selection) selection.removeAllRanges();
  document.body.removeChild(container);
  return ok;
}

/**
 * Copy a rendered content node with formatting. Returns 'rich' when the
 * dual-MIME payload was written, 'plain' when it fell back to plain text.
 */
export async function copyRich(node, { plainText } = {}) {
  const { html, text } = await buildRichClipboardPayload(node, { plainText });
  try {
    await writeClipboard(html, text);
    return 'rich';
  } catch {
    try {
      await navigator.clipboard.writeText(text);
      return 'plain';
    } catch {
      legacyCopy(html, text);
      return 'plain';
    }
  }
}

/**
 * Synchronous handler for the container `copy` event — makes native Ctrl+C on
 * a selection inside the message write RICH HTML (formatting survives in Word).
 * Returns false when the event was handled (caller must preventDefault).
 */
export function handleRichCopyEvent(event, { contentNode } = {}) {
  const selection = window.getSelection();
  if (!selection || selection.rangeCount === 0 || selection.isCollapsed) return true;
  const anchor = selection.anchorNode;
  if (contentNode && anchor && !contentNode.contains(anchor)) return true;
  if (!event.clipboardData) return true;

  const range = selection.getRangeAt(0);
  const fragment = range.cloneContents();
  const wrapper = document.createElement('div');
  wrapper.appendChild(fragment);

  // Tag-based defaults — sync-safe (no computed-style pairing needed for a
  // selection fragment; syntax colors are the async button-copy's job).
  stripInteractive(wrapper);
  enforceTableBorders(wrapper);
  rewriteLinks(wrapper);
  wrapper.querySelectorAll('pre').forEach((pre) => {
    pre.style.backgroundColor = '#282c34';
    pre.style.color = '#abb2bf';
    pre.style.padding = '8px 12px';
    pre.style.fontFamily = 'Consolas, monospace';
    pre.style.whiteSpace = 'pre-wrap';
    pre.style.borderRadius = '4px';
  });

  const html = wordFragment(wrapper.innerHTML);
  const text = cleanPlainText(selection.toString());
  event.clipboardData.setData('text/html', html);
  event.clipboardData.setData('text/plain', text);
  return false;
}

// ── Media asset collection (Save-image / Save-all) ───────────────────────────

/**
 * Collect the media assets rendered inside a message content node:
 * mermaid diagrams (PNG+SVG) and raster figures (PNG). Returns a list of
 * `{ kind, label, nameBase, png(), svg() }` items.
 */
export function collectMediaItems(node) {
  const items = [];
  if (!node) return items;
  node.querySelectorAll('svg[id^="mmd-"]').forEach((svg, i) => {
    const nameBase = `diagram-${i + 1}`;
    items.push({
      kind: 'diagram',
      label: `Diagram ${i + 1}`,
      nameBase,
      png: () => svgToPngBlob(svg, { scale: 2 }),
      svg: () => svgToSvgBlob(svg),
    });
  });
  node.querySelectorAll('img').forEach((img, i) => {
    const alt = img.getAttribute('alt') || '';
    const nameBase = slugify(alt || `figure-${i + 1}`);
    items.push({
      kind: 'figure',
      label: alt || `Figure ${i + 1}`,
      nameBase,
      png: async () => {
        const blob = await imgToBlob(img);
        if (!blob) throw new Error('Image could not be fetched');
        return blob;
      },
      svg: null,
    });
  });
  return items;
}

/** Download a single media item as its chosen format. */
export async function downloadMediaItem(item, format = 'png') {
  const factory = format === 'svg' ? item.svg : item.png;
  if (!factory) throw new Error('Format not available');
  const blob = await factory();
  downloadBlob(blob, `${item.nameBase}.${format}`);
}

/** Bundle media items into a ZIP (jszip — lazy-loaded, kept out of main bundle). */
export async function downloadZip(items, zipName = 'images.zip') {
  const JSZip = (await import('jszip')).default;
  const zip = new JSZip();
  await Promise.all(
    items.map(async (item) => {
      try {
        zip.file(`${item.nameBase}.png`, await item.png());
      } catch {
        // Skip items that could not be fetched.
      }
    }),
  );
  const blob = await zip.generateAsync({ type: 'blob' });
  downloadBlob(blob, zipName);
}
