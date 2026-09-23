// src/shell/MarkdownMessage.jsx
// ────────────────────────────────────────────────────────────────────────────
// GENERIC RICH MARKDOWN RENDERER for AI assistant messages.
//
// Public import for apps / Agent surfaces: `components/RichContent.jsx`
// (same engine — GFM tables, code, mermaid, math, figures). Use RichContent
// for plan briefs, graph entity details, Run/Canvas/Output prose, and domain
// apps so formatting stays one stack.
//
//   * GFM tables            — MUI Table (striped, scrollable)
//   * syntax highlighting   — rehype-highlight (One Dark theme)
//   * code snippets         — dark fenced block + language badge + copy
//   * diagrams              — ```mermaid fenced blocks → rendered SVG
//   * math                  — $$...$$ / $...$ via KaTeX
//   * figures               — images with optional title → caption
//   * smart links           — internal safe routes → SPA <Link>; else new tab
//   * task lists, blockquotes, hr — GFM
//
// Dependencies: react-markdown, remark-gfm, remark-math, rehype-highlight,
// rehype-katex, katex, mermaid (dynamic import — not in the main bundle).
// ────────────────────────────────────────────────────────────────────────────
import React, { useCallback, useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeHighlight from 'rehype-highlight';
import rehypeKatex from 'rehype-katex';
import { Link as RouterLink } from 'react-router-dom';
import 'highlight.js/styles/atom-one-dark.css';
import 'katex/dist/katex.min.css';
import {
  Box,
  Button,
  Checkbox,
  Chip,
  Divider,
  IconButton,
  Link,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from '@mui/material';
import { useTheme } from '@mui/material/styles';
import CheckIcon from '@mui/icons-material/Check';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import { isSafeInternalRoute } from '../utils/navigation';
import EntityChip from './EntityChip';

// ── Helpers ──────────────────────────────────────────────────────────────

/** Flatten React children (incl. hljs span elements) to plain text. */
function flattenText(node) {
  if (node == null || typeof node === 'boolean') return '';
  if (typeof node === 'string' || typeof node === 'number') return String(node);
  if (Array.isArray(node)) return node.map(flattenText).join('');
  if (React.isValidElement(node)) return flattenText(node.props?.children);
  return '';
}

/**
 * Normalize mermaid fences the model sometimes emits inline (e.g.
 * "…factors: ```mermaid" on one line, or a closing ``` glued to trailing prose,
 * or several fences + prose collapsed onto one line). A fenced code block's
 * fence must start on its own line to be recognized by the CommonMark parser —
 * otherwise it renders as literal backticks and no diagram appears.
 */
function normalizeMermaidFences(content) {
  if (!content || typeof content !== 'string' || !content.includes('```')) {
    return content;
  }
  // Put every triple-backtick fence (with optional language) on its own line.
  // Splitting each line on fence tokens handles the case where the model glues
  // a closing ``` and the next opening ```mermaid (plus prose) onto one line,
  // while leaving already-well-formed lines untouched.
  return content
    .split('\n')
    .flatMap((line) => {
      if (!line.includes('```')) return [line];
      return line.split(/(```[a-zA-Z0-9_-]*)/g).filter((p) => p.length > 0);
    })
    .join('\n');
}

/**
 * Reflow a single-line mermaid body into the line-oriented form mermaid's
 * grammar requires. xychart-beta and pie are line-delimited; a single collapsed
 * line fails to parse, so split on their directive keywords. Already multi-line
 * (or non-chart) bodies pass through untouched.
 */
function reflowSingleLineMermaid(code) {
  if (!code || typeof code !== 'string') return code;
  const trimmed = code.trim();
  if (!trimmed || trimmed.includes('\n')) return code; // empty or already multi-line

  if (/^xychart-beta\b/.test(trimmed)) {
    const rest = trimmed.replace(/^xychart-beta\s*/, '');
    const dirs = ['title', 'x-axis', 'y-axis', 'bar', 'line'];
    const re = new RegExp(`\\s+(?=${dirs.map((d) => d.replace(/-/g, '\\-')).join('|')}\\b)`);
    const parts = rest.split(re).map((s) => s.trim()).filter(Boolean);
    return ['xychart-beta', ...parts].join('\n    ');
  }

  if (/^pie\b/.test(trimmed)) {
    let rest = trimmed.replace(/^pie\s*/, '');
    const lines = [];
    if (/^title\b/.test(rest)) {
      rest = rest.replace(/^title\s*/, '');
      const quote = rest.indexOf('"');
      if (quote === -1) {
        lines.push(`title ${rest.trim()}`);
        rest = '';
      } else {
        lines.push(`title ${rest.slice(0, quote).trim()}`);
        rest = rest.slice(quote);
      }
    }
    const sliceRe = /"([^"]*)"\s*:\s*([\d.]+)/g;
    let m;
    while ((m = sliceRe.exec(rest)) !== null) {
      lines.push(`"${m[1]}" : ${m[2]}`);
    }
    return ['pie', ...lines].join('\n    ');
  }

  return code;
}

/**
 * Repair invalid ``xychart-beta`` grammar the model sometimes emits. Three
 * forms the renderer rejects ("Diagram could not be rendered"):
 *
 * 1. ``axis x`` / ``axis y`` markers with per-point ``bar x: N y: V`` lines.
 * 2. pie-style slices glued onto a ``bar`` line: ``bar "A" : 1 "B" : 2 …``.
 *
 * Convert them to the line-oriented directives mermaid accepts: one
 * ``x-axis [...]``, one ``y-axis "title" 0 --> max``, one ``bar [...]``.
 */
function repairXychart(code) {
  if (!code || typeof code !== 'string') return code;
  if (!/^xychart-beta\b/m.test(code.trim())) return code;

  const lines = code.split('\n').map((l) => l.trim()).filter(Boolean);
  // Only repair when a known-bad bar form is present — an already-correct
  // body (bar [...]) or any other diagram passes through untouched.
  const hasPointBar = lines.some((l) => /^bar\s+x\s*:/i.test(l));
  const hasSliceBar = lines.some((l) => /^bar\s+"[^"]*"\s*:/i.test(l));
  if (!hasPointBar && !hasSliceBar) return code;

  const pointRe = /^bar\s+x\s*:\s*\S+\s+y\s*:\s*([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)/i;
  const sliceRe = /"([^"]*)"\s*:\s*([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)/g;
  const values = [];
  const sliceLabels = [];
  let xTitle = '';
  let yTitle = '';
  let xCategories = '';

  for (const line of lines) {
    const pm = line.match(pointRe);
    if (pm) {
      values.push(pm[1]);
      continue;
    }
    // pie-style slices on a bar line: "A" : 1  "B" : 2 …
    if (/^bar\s+"[^"]*"\s*:/i.test(line)) {
      let sm;
      while ((sm = sliceRe.exec(line)) !== null) {
        sliceLabels.push(sm[1]);
        values.push(sm[2]);
      }
      continue;
    }
    // "title \"Scope\" axis y" → the title belongs to the x-axis; "axis y" is a stray marker.
    let m = line.match(/^title\s+"([^"]+)"\s+axis\s+y\b/i);
    if (m) { xTitle = m[1]; continue; }
    m = line.match(/^title\s+"([^"]+)"\s+axis\s+x\b/i);
    if (m) { yTitle = m[1]; continue; }
    // Plain "title \"...\"" → first unused axis title (x then y).
    m = line.match(/^title\s+"([^"]+)"\s*$/i);
    if (m) {
      if (!xTitle) xTitle = m[1];
      else if (!yTitle) yTitle = m[1];
      continue;
    }
    // Already-correct axis lines (in case they're mixed with stray bars).
    m = line.match(/^x-axis\s+"([^"]+)"/i);
    if (m) { xTitle = m[1]; continue; }
    m = line.match(/^x-axis\s+\[(.*)\]$/i);
    if (m) { xCategories = m[1]; continue; }
    m = line.match(/^y-axis\s+"([^"]+)"/i);
    if (m) { yTitle = m[1]; continue; }
  }

  if (values.length === 0) return code;

  let xAxis;
  if (xCategories) {
    xAxis = `x-axis [${xCategories}]`;
  } else if (sliceLabels.length === values.length && sliceLabels.length > 0) {
    xAxis = `x-axis [${sliceLabels.map((lbl) => `"${lbl}"`).join(', ')}]`;
  } else if (xTitle) {
    const cats = values.map((_, i) => `"${xTitle} ${i + 1}"`).join(', ');
    xAxis = `x-axis [${cats}]`;
  } else {
    xAxis = `x-axis [${values.map((_, i) => i + 1).join(', ')}]`;
  }

  const maxVal = values.reduce((a, v) => Math.max(a, Number(v)), 0);
  const yMax = Math.ceil(maxVal * 1.1) || 1;
  const yLabel = yTitle ? ` "${yTitle}"` : '';

  return [
    'xychart-beta',
    xAxis,
    `y-axis${yLabel} 0 --> ${yMax}`,
    `bar [${values.join(', ')}]`,
  ].join('\n    ');
}

/**
 * Sanitize an xychart-beta block for mermaid compatibility. The parser rejects
 * an unquoted `title` containing parentheses, and chokes on em-dashes / angle
 * brackets / pipes in labels. We: (1) quote the `title` and strip parens,
 * (2) normalize subscript digits (CO₂e → CO2e) everywhere, (3) clean + quote +
 * truncate each x-axis category, (4) quote the y-axis label.
 */
const SUBSCRIPT_MAP = {
  '\u2080': '0', '\u2081': '1', '\u2082': '2', '\u2083': '3', '\u2084': '4',
  '\u2085': '5', '\u2086': '6', '\u2087': '7', '\u2088': '8', '\u2089': '9',
};

function normalizeSubscripts(text) {
  return text.replace(/[\u2080-\u2089]/g, (c) => SUBSCRIPT_MAP[c] || c);
}

function sanitizeXychartAxisLabels(code) {
  if (!code || !code.includes('xychart-beta')) return code;

  return code
    .split('\n')
    .map((line) => {
      const trimmed = line.trim();
      const indent = line.slice(0, line.length - line.trimStart().length);

      // title — quote it, strip parens (invalid unquoted), normalize subscripts.
      const titleMatch = trimmed.match(/^title\s+(.+)$/i);
      if (titleMatch) {
        const raw = normalizeSubscripts(titleMatch[1].trim().replace(/^"|"$/g, ''))
          .replace(/[()<>{}|]/g, '')
          .trim();
        return `${indent}title "${raw}"`;
      }

      // x-axis [a, b, c] — clean + quote + truncate each category.
      const xAxisMatch = trimmed.match(/^x-axis\s*\[([^\]]+)\]$/i);
      if (xAxisMatch) {
        const safe = xAxisMatch[1]
          .split(',')
          .map((lbl) => {
            const clean = normalizeSubscripts(lbl.trim().replace(/^"|"$/g, ''))
              .replace(/\u2014|\u2013/g, '-')
              .replace(/[<>{}|]/g, '')
              .trim();
            const truncated = clean.length > 20 ? `${clean.slice(0, 18)}\u2026` : clean;
            return `"${truncated}"`;
          })
          .join(', ');
        return `${indent}x-axis [${safe}]`;
      }

      // y-axis "label" 0 --> N — quote the label, normalize subscripts.
      const yAxisMatch = trimmed.match(/^y-axis\s+(?:"([^"]*)"|([^0-9-]+?))\s+([-\d.]+\s*-->\s*[-\d.]+)$/i);
      if (yAxisMatch) {
        const label = normalizeSubscripts((yAxisMatch[1] ?? yAxisMatch[2] ?? '').trim())
          .replace(/[()<>{}|]/g, '')
          .trim();
        return `${indent}y-axis "${label}" ${yAxisMatch[3].replace(/\s+/g, ' ')}`;
      }

      return line;
    })
    .join('\n');
}

/**
 * Repair a top-level ``bar`` diagram the model sometimes emits. Mermaid has NO
 * ``bar`` diagram type — bar charts are ``xychart-beta``. The model's output
 * uses a ``bar`` header with pie-style "Label" : value slices plus optional
 * ``title`` / ``x-axis`` / ``y-axis`` label lines:
 *
 *   bar
 *   title Employee Count by Position
 *   x-axis Label Position
 *   y-axis Label Count
 *   "Heavy Duty Driver" : 52
 *
 * Convert it to the xychart-beta directives mermaid accepts:
 *
 *   xychart-beta
 *       title "Employee Count by Position"
 *       x-axis ["Heavy Duty Driver", …]
 *       y-axis "Label Count" 0 --> 58
 *       bar [52, …]
 */
function repairTopLevelBar(code) {
  if (!code || typeof code !== 'string') return code;
  const trimmed = code.trim();
  // Only the top-level `bar` directive (NOT xychart-beta / pie / flowchart …).
  if (!/^bar(?=\s|$)/im.test(trimmed)) return code;
  if (/^xychart-beta\b/m.test(trimmed) || /^pie\b/m.test(trimmed)) return code;

  const lines = trimmed.split('\n').map((l) => l.trim()).filter(Boolean);

  let title = '';
  let xLabel = '';
  let yLabel = '';
  let categories = '';
  const labels = [];
  const values = [];

  const titleRe = /^title\s+(?:"([^"]+)"|(.+))$/i;
  const xAxisRe = /^x-axis\s+(?:"([^"]+)"|\[(.*)\]|(.+))$/i;
  const yAxisRe = /^y-axis\s+(?:"([^"]+)"|(.+))$/i;
  const sliceRe = /"([^"]*)"\s*:\s*([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)/g;

  for (const rawLine of lines) {
    // Strip a leading `bar` token so glued slices on the same line are parsed too.
    const line = rawLine.replace(/^bar(?=\s|$)/i, '').trim();
    if (!line) continue;

    let m = line.match(titleRe);
    if (m) { title = (m[1] ?? m[2] ?? '').trim(); continue; }
    m = line.match(xAxisRe);
    if (m) {
      if (m[2] !== undefined) categories = m[2].trim();
      else xLabel = (m[1] ?? m[3] ?? '').trim();
      continue;
    }
    m = line.match(yAxisRe);
    if (m) { yLabel = (m[1] ?? m[2] ?? '').trim(); continue; }

    let sm;
    while ((sm = sliceRe.exec(line)) !== null) {
      labels.push(sm[1]);
      values.push(sm[2]);
    }
  }

  if (values.length === 0) return code;

  const maxVal = values.reduce((a, v) => Math.max(a, Number(v)), 0);
  const yMax = Math.ceil(maxVal * 1.1) || 1;

  let xAxis;
  if (categories) {
    xAxis = `x-axis [${categories}]`;
  } else if (labels.length === values.length && labels.length > 0) {
    xAxis = `x-axis [${labels.map((lbl) => `"${lbl}"`).join(', ')}]`;
  } else if (xLabel) {
    xAxis = `x-axis [${values.map((_, i) => `"${xLabel} ${i + 1}"`).join(', ')}]`;
  } else {
    xAxis = `x-axis [${values.map((_, i) => i + 1).join(', ')}]`;
  }

  const parts = ['xychart-beta'];
  if (title) parts.push(`title "${title}"`);
  parts.push(xAxis);
  parts.push(`y-axis "${yLabel}" 0 --> ${yMax}`);
  parts.push(`bar [${values.join(', ')}]`);
  return parts.join('\n    ');
}

/**
 * Repair GFM table blocks the model breaks across lines. Two failure modes:
 *   1. An ATX heading glued to the table header row on one line:
 *      "###### Title | H1 | H2 |" → heading + blank + "| H1 | H2 |".
 *   2. A blank line between the header row and its delimiter row (GFM requires
 *      the delimiter to immediately follow the header) — the blank is dropped.
 * Runs before the line-oriented reflow so the header/delimiter/rows land as a
 * single contiguous table block the GFM parser recognizes.
 */
function repairTableBlocks(content) {
  if (!content || typeof content !== 'string' || !content.includes('|')) return content;

  const DELIM = /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$/;
  const isPipeRow = (l) => /^\s*\|.*\|\s*$/.test(l);

  // Pass 1: split a leading ATX heading glued to a table header row.
  const split = [];
  for (const raw of content.split('\n')) {
    const trimmed = raw.trim();
    const m = trimmed.match(/^(#{1,6}\s+.+?)\s+(\|.+\|)\s*$/);
    if (m && (m[2].match(/\|/g) || []).length >= 2) {
      split.push(m[1]);
      split.push('');
      split.push(m[2]);
    } else {
      split.push(raw);
    }
  }

  // Pass 2: drop a blank line sitting between a table header row and its delimiter.
  const out = [];
  for (let i = 0; i < split.length; i += 1) {
    const cur = split[i];
    const prev = out[out.length - 1];
    if (
      cur.trim() === '' &&
      prev !== undefined && isPipeRow(prev) && !DELIM.test(prev) &&
      i + 1 < split.length && DELIM.test(split[i + 1])
    ) {
      continue; // drop the blank so header and delimiter are adjacent
    }
    out.push(cur);
  }
  return out.join('\n');
}

/**
 * Reflow structural markdown the model sometimes collapses onto a single line.
 * gpt-4o frequently emits a whole section as one run-on line: ATX headings
 * glued to prose, ordered-list items concatenated, and bullets concatenated.
 * The parser then renders that as one giant paragraph. Splitting the markers
 * back onto their own lines restores proper headings and lists. Fenced code
 * blocks (```) are left verbatim.
 */
function reflowMarkdownStructure(content) {
  if (!content || typeof content !== 'string') return content;

  let inCode = false;
  const out = [];

  for (const rawLine of content.split('\n')) {
    const trimmed = rawLine.trim();

    // Enter/exit a fenced code block — never reflow inside it.
    if (/^```/.test(trimmed)) {
      inCode = !inCode;
      out.push(rawLine);
      continue;
    }
    if (inCode || !trimmed) {
      out.push(rawLine);
      continue;
    }

    // A GFM table the model collapsed onto one line (header+delimiter+rows glued
    // to trailing prose) never parses — reflow it to one row per line first.
    const tableLines = reflowCollapsedTable(trimmed);
    if (tableLines) {
      out.push(...tableLines);
      continue;
    }

    // Data rows collapsed on one line (header+delimiter already separate):
    // "| A | 1 || B | 2 ||" → split into individual rows.
    const dataRows = reflowCollapsedDataOnlyRows(trimmed);
    if (dataRows) {
      out.push(...dataRows);
      continue;
    }

    // A GFM table whose rows are already on separate lines but whose header row
    // is glued to trailing prose (e.g. "sentence. | Header | …") has no blank
    // separator — the parser won't start a table. Peel the prose off.
    const proseAndTable = splitProseFromInlineTableHeader(trimmed, out);
    if (proseAndTable) {
      out.push(...proseAndTable);
      continue;
    }

    // Last resort: a table fully collapsed onto one line with single-pipe
    // separators everywhere (no `| |` row seams for the reflows above to split
    // on). Re-chunk it using the delimiter run's inferred column count.
    const fullTable = reflowFullyCollapsedTable(trimmed);
    if (fullTable) {
      out.push(...fullTable);
      continue;
    }

    out.push(...reflowLine(trimmed));
  }

  return out.join('\n');
}

/**
 * Handle the case where the model emits: "Prose sentence. | Header | Col2 |"
 * followed by a delimiter row on the NEXT line (so the rows are already split
 * but there's no blank line separating the prose from the table). The GFM
 * parser won't recognise a table that starts mid-line — it needs the header on
 * its own line preceded by a blank line.
 *
 * We only trigger when: (a) the NEXT output line starts with `|---`, and
 * (b) the current line has a `|` that's preceded by non-pipe prose. We peel
 * the prose off, insert a blank line, and let the header row land alone.
 * Returns null when the heuristic doesn't apply so the caller falls through.
 */
function splitProseFromInlineTableHeader(line, _prevLines) {
  // A table header row sits here when: there's a | somewhere after prose content.
  const pipeIdx = line.indexOf('|');
  if (pipeIdx <= 0) return null; // line starts with | or has no | → not this case

  // The NEXT line in `prevLines` is not available yet (we're building it), so
  // we check whether the CURRENT line looks like "prose | col | col |" — the
  // delimiter row will arrive on the next iteration and the GFM parser handles
  // it from there if we just ensure a blank line precedes the header.
  // Heuristic: prose before the first pipe, AND multiple pipe-separated segments
  // after it (at least 2 `|`s total → a real table header, not an em-dash table).
  const afterFirstPipe = line.slice(pipeIdx);
  const pipeCount = (afterFirstPipe.match(/\|/g) || []).length;
  if (pipeCount < 2) return null;

  const prose = line.slice(0, pipeIdx).trim();
  const header = line.slice(pipeIdx).trim();
  if (!prose || !header) return null;

  // Avoid double-splitting a line that reflowCollapsedTable already handles
  // (that one has the delimiter on the same line; here it's on the next line).
  const DELIMITER_CELL = /\|\s*:?-{2,}:?\s*(?=\|)/;
  if (DELIMITER_CELL.test(line)) return null; // already handled by reflowCollapsedTable

  const result = [];
  result.push(prose);
  result.push(''); // blank line so the GFM parser starts a fresh block
  result.push(header);
  return result;
}


/**
 * Reflow a FULLY collapsed GFM table — one where the whole table (optional
 * caption + header + delimiter + every data row) is glued onto a single line
 * using single pipes as separators everywhere. ``reflowCollapsedTable`` cannot
 * handle this because there are no ``| |`` row seams to split on; instead we
 * use the delimiter run's column count (N) to re-chunk the cells:
 *
 *   Campus Coverage | Campus | Coverage | Covered |---|---|---| Abu Qir | 80% | 4 | …
 *   → caption "Campus Coverage", a 3-col header, then N-sized data rows.
 *
 * Returns null when no ``|---|---|`` delimiter run is present so the caller
 * falls through to the other table/prose reflows.
 */
function reflowFullyCollapsedTable(line) {
  const delimRe = /\|(?:\s*:?-{2,}:?\s*\|)+/;
  const m = line.match(delimRe);
  if (!m) return null;
  const delimN = (m[0].match(/:?-{2,}:?/g) || []).length;
  if (delimN < 2) return null;

  const before = line.slice(0, m.index);
  const after = line.slice(m.index + m[0].length);

  const beforeCells = before.split('|').map((c) => c.trim());
  while (beforeCells.length && beforeCells[beforeCells.length - 1] === '') beforeCells.pop();

  const afterCells = after.split('|').map((c) => c.trim());
  while (afterCells.length && afterCells[0] === '') afterCells.shift();
  while (afterCells.length && afterCells[afterCells.length - 1] === '') afterCells.pop();

  // The model's delimiter count is unreliable. Prefer a column count N that is
  // ≤ the header cell count AND divides the data cells evenly, taking the
  // largest such N; otherwise fall back to the delimiter count.
  let n = delimN;
  const maxN = beforeCells.length;
  if (afterCells.length > 0 && (delimN > maxN || afterCells.length % delimN !== 0)) {
    for (let cand = Math.min(maxN, afterCells.length); cand >= 2; cand -= 1) {
      if (afterCells.length % cand === 0) { n = cand; break; }
    }
  }
  if (n < 2 || beforeCells.length < n) return null;

  let prose = '';
  let headerCells = beforeCells;
  if (beforeCells.length > n) {
    headerCells = beforeCells.slice(beforeCells.length - n);
    prose = beforeCells.slice(0, beforeCells.length - n).join(' ').trim();
  }

  const out = [];
  if (prose) out.push(prose);
  out.push('');
  out.push(`| ${headerCells.join(' | ')} |`);
  out.push(`|${Array(n).fill('---').join('|')}|`);
  for (let i = 0; i < afterCells.length; i += n) {
    const row = afterCells.slice(i, i + n);
    while (row.length < n) row.push('');
    out.push(`| ${row.join(' | ')} |`);
  }
  out.push('');
  return out;
}

/**
 * Reflow a GFM table the model collapsed onto a single line back into the
 * line-oriented form the parser requires: leading prose on its own line, a
 * blank line, then one `|…|` row per line (header, delimiter, data rows).
 *
 * A collapsed table is detected by the co-occurrence of an inline delimiter
 * cell (`|---|`) and a row boundary (`|` + whitespace + `|`) — a correctly
 * formatted delimiter line on its own has neither. Returns `null` when the line
 * is not a collapsed table, so the caller falls through to the prose reflow.
 */
function reflowCollapsedTable(line) {
  const DELIMITER_CELL = /\|\s*:?-{2,}:?\s*(?=\|)/; // a |---| style delimiter cell
  const ROW_BOUNDARY = /\|[ \t]+\|/; // one row's closing pipe glued to the next row's opening pipe
  if (!DELIMITER_CELL.test(line) || !ROW_BOUNDARY.test(line)) return null;

  // Split on every "|<ws>|" row boundary (a real cell keeps content between its
  // pipes, so only true row seams — pipe directly followed by whitespace+pipe —
  // are cut here).
  const rows = line.replace(/\|[ \t]+\|/g, '|\u0001|').split('\u0001');
  if (rows.length < 2) return null;

  const out = [];
  const firstPipe = rows[0].indexOf('|');
  const prose = rows[0].slice(0, firstPipe).trim();
  const header = rows[0].slice(firstPipe).trim();
  if (prose) out.push(prose);
  out.push(''); // blank line so the table starts its own block
  out.push(header);
  for (let i = 1; i < rows.length; i += 1) out.push(rows[i].trim());
  out.push(''); // close the table block
  return out;
}

/**
 * Reflow collapsed data-only table rows onto separate lines.
 * Handles the case where the model emits all data rows on ONE line separated
 * by adjacent pipes with no spaces (``||``) — the header and delimiter are
 * already on their own lines, only the data is collapsed:
 *   | Abu Qir — X | 47 || Smart Village — Y | 84 || ...
 */
function reflowCollapsedDataOnlyRows(line) {
  if (!line.startsWith('|')) return null;
  if (/\|\s*:?-{2,}:?\s*\|/.test(line)) return null; // delimiter row — skip
  // Require at least one adjacent-pipe row boundary (0 spaces between rows).
  if (!/\|\s{0,1}\|/.test(line)) return null;
  const sentinel = '\u0001';
  const exploded = line.replace(/\|\s{0,1}\|/g, `|${sentinel}|`).split(sentinel);
  if (exploded.length < 2) return null;
  const rows = exploded.map((r) => r.trim()).filter(Boolean);
  // Each segment must have ≥2 pipes to be a real row (guards against empty cells).
  if (rows.some((r) => (r.match(/\|/g) || []).length < 2)) return null;
  return rows;
}

/** Split one prose line's collapsed headings / list items onto their own lines. */
function reflowLine(line) {
  let parts = [line];

  // ATX headings (### etc.) glued to prose → own line.
  parts = parts.flatMap((p) =>
    p.split(/(?<=\S)\s+(?=#{1,6}\s)/).map((s) => s.trim()).filter(Boolean),
  );

  // Ordered-list items "N. **Title**" or "N. text" → own line.
  parts = parts.flatMap((p) => splitOrderedListItems(p));

  // Unordered bullets "- item" / "* item" → own line.
  parts = parts.flatMap((p) => splitBullets(p));

  return parts;
}

/** Split collapsed ordered-list items ("1. A 2. B") onto their own lines. */
function splitOrderedListItems(line) {
  // A real list marker is either "N. " with 1-2 digits (so a 4-digit year like
  // "2050." is NOT mistaken for a marker), or any "N. **bold**" (unambiguous).
  // `(?<!\d)` prevents matching the tail of a year ("50." inside "2050.").
  const markerRe = /(?<!\d)\d{1,2}\.\s+\S|\d+\.\s+\*\*/g;
  const markers = line.match(markerRe) || [];
  const hasBold = /(?<=\s)\d+\.\s+\*\*/.test(line);
  // Only reflow when it is clearly a list: a bold item, or 2+ "N. " markers.
  // A lone "3. Next sentence" mid-prose is left alone.
  if (!hasBold && markers.length < 2) return [line];
  return line
    .split(/(?<=\S)\s+(?=(?<!\d)\d{1,2}\.\s+\S|\d+\.\s+\*\*)/)
    .map((s) => s.trim())
    .filter(Boolean);
}

/** Split collapsed bullets ("- a - b") onto their own lines. */
function splitBullets(line) {
  const markerCount = (line.match(/[-*]\s+\S/g) || []).length;
  // Multiple bullets ⇒ clearly a list: split on every bullet boundary. A single
  // bullet is only split when it follows sentence punctuation / a colon, so we
  // don't tear apart prose em-dashes like "word - word".
  const re =
    markerCount >= 2
      ? /\s+(?=[-*]\s+\S)/
      : /(?<=[.:;!?])\s+(?=[-*]\s+\S)/;
  return line.split(re).map((s) => s.trim()).filter(Boolean);
}

// ── Entity reference chips (Phase F1-F) ─────────────────────────────────────
//
// The assistant emits `[[kind:id:label]]` tokens for entities it can link to
// the Contextual Inspector (kind ∈ table | rule | module | org-unit). This
// remark plugin runs AFTER the reflow helpers (which operate on raw text) and
// BEFORE remark-rehype, splitting each matching text node into:
//
//   { type: 'entityRef', kind, id, label,
//     data: { hName: 'entityRef', hProperties: { kind, id, label } } }
//
// `data.hName` makes mdast-util-to-hast turn the unknown node into a hast
// element `<entityRef kind=… id=… label=…>` that the `components.entityRef`
// override renders as an <EntityChip/>. Fenced (```) and inline (`) code are
// never chipped: their payloads live in `node.value`, not as `text` children,
// so this walk only ever sees real prose `text` nodes.

const ENTITY_REF_RE = /\[\[(table|rule|module|org-unit):([^:\]]+):([^\]]+)\]\]/g;

/** Build the custom mdast node the remark-rehype `hName` mechanism carries over. */
function entityRefNode(kind, id, label) {
  return {
    type: 'entityRef',
    kind,
    id,
    label,
    data: {
      hName: 'entityRef',
      hProperties: { kind, id, label },
    },
  };
}

/** Split a text value into text/entityRef nodes (identity when no known refs). */
function splitEntityRefs(value) {
  if (typeof value !== 'string' || !value.includes('[[')) {
    return [{ type: 'text', value }];
  }

  const matches = [...value.matchAll(ENTITY_REF_RE)];
  if (matches.length === 0) {
    return [{ type: 'text', value }];
  }

  const parts = [];
  let cursor = 0;
  for (const match of matches) {
    const [full, kind, id, label] = match;
    if (match.index > cursor) {
      parts.push({ type: 'text', value: value.slice(cursor, match.index) });
    }
    parts.push(entityRefNode(kind, id, label));
    cursor = match.index + full.length;
  }
  if (cursor < value.length) {
    parts.push({ type: 'text', value: value.slice(cursor) });
  }
  return parts;
}

/** Recursively rewrite prose `text` nodes (code/inlineCode carry `.value`, skipped). */
function walkTextNodes(node) {
  if (!node || typeof node !== 'object') return;
  if (!Array.isArray(node.children)) return;

  for (let i = 0; i < node.children.length; i += 1) {
    const child = node.children[i];
    if (child && child.type === 'text') {
      const parts = splitEntityRefs(child.value);
      if (parts.length > 1) {
        node.children.splice(i, 1, ...parts);
        i += parts.length - 1; // advance past the nodes we just inserted
      }
    } else {
      walkTextNodes(child);
    }
  }
}

/** Remark plugin (attacher) — see module comment above. */
function remarkEntityChips() {
  return (tree) => {
    walkTextNodes(tree);
  };
}

// ── Mermaid diagram (```mermaid) — lazily imports the heavy lib ──────────

const mermaidIdRef = { current: 0 };

function MermaidBlock({ code }) {
  const theme = useTheme();
  // { html: svgWithoutStyle, css: extractedCSS } | null
  const [diagram, setDiagram] = useState(null);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  const effectiveCode = sanitizeXychartAxisLabels(repairTopLevelBar(repairXychart(reflowSingleLineMermaid(code))));
  const mermaidTheme = theme.palette.mode === 'dark' ? 'dark' : 'default';
  const fenceBg = 'grey.900';
  const fenceFg = 'grey.300';

  useEffect(() => {
    let cancelled = false;
    setDiagram(null);
    setError('');
    (async () => {
      try {
        const mermaid = (await import('mermaid')).default;
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: 'loose',
          theme: mermaidTheme,
          fontFamily: 'inherit',
          // Keep charts compact and responsive — never full-bleed square blocks.
          pie: { useMaxWidth: true },
          xyChart: { width: 560, height: 300 },
          flowchart: { useMaxWidth: true },
          sequence: { useMaxWidth: true },
        });
        mermaidIdRef.current += 1;
        const id = `mmd-${mermaidIdRef.current}-${Date.now()}`;
        const { svg: rendered } = await mermaid.render(id, effectiveCode);
        if (!cancelled) {
          // Hoist the mermaid <style> out of the SVG so it becomes a normal HTML
          // <style> element (UA stylesheet: display:none) — prevents the raw CSS
          // text from leaking as visible content inside the chat bubble.
          let css = '';
          const html = rendered.replace(/<style[^>]*>([\s\S]*?)<\/style>/gi, (_, c) => {
            css += c;
            return '';
          });
          setDiagram({ html, css });
        }
      } catch (err) {
        if (!cancelled) {
          setError(err?.message ? String(err.message) : 'Diagram render failed');
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [effectiveCode, attempt, mermaidTheme]);

  if (error) {
    return (
      <Box sx={{ my: 1.5, borderRadius: 0, border: 1, borderColor: 'warning.main', overflow: 'hidden' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1 }}>
          <Chip
            size="small"
            color="warning"
            variant="outlined"
            label="Diagram could not be rendered"
            sx={{ m: 0.75 }}
          />
          <Button
            size="small"
            color="warning"
            variant="text"
            onClick={() => setAttempt((n) => n + 1)}
            sx={{ m: 0.75, ml: 'auto', flexShrink: 0 }}
          >
            Retry
          </Button>
        </Box>
        <Box
          component="pre"
          dir="ltr"
          sx={{
            m: 0,
            p: 1.5,
            bgcolor: fenceBg,
            overflowX: 'auto',
            fontSize: '0.8125rem',
            color: fenceFg,
          }}
        >
          <code>{effectiveCode}</code>
        </Box>
      </Box>
    );
  }

  if (!diagram) {
    return (
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', my: 1 }}>
        Rendering diagram…
      </Typography>
    );
  }

  return (
    <>
      {/* Scoped mermaid CSS — outside SVG so it's treated as a real <style> (hidden by UA stylesheet) */}
      {diagram.css && <style>{diagram.css}</style>}
      <Box
        sx={{
          my: 1.5,
          display: 'flex',
          justifyContent: 'center',
          overflowX: 'auto',
          bgcolor: 'background.paper',
          borderRadius: 1,
          border: 1,
          borderColor: 'divider',
          p: 1.5,
          // Cap the rendered height so a square pie/flowchart never dominates the
          // thread; width scales down to fit, height follows the aspect ratio.
          '& svg': {
            maxWidth: '100%',
            maxHeight: 320,
            height: 'auto',
            width: 'auto',
            display: 'block',
          },
          '& a': { color: 'primary.main' },
        }}
        dangerouslySetInnerHTML={{ __html: diagram.html }}
      />
    </>
  );
}

// ── Fenced code block: dark bg + language badge + copy button ────────────

function CodeBlock({ children, className }) {
  const theme = useTheme();
  const [copied, setCopied] = useState(false);
  const match = /language-(\w+)/.exec(className || '');
  const code = flattenText(children).replace(/\n$/, '');
  const fenceBg = 'grey.900';
  const fenceFg = 'grey.300';
  const headerBg = theme.palette.mode === 'dark' ? 'grey.800' : 'grey.800';

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [code]);

  if (!match) {
    // inline code — always LTR so identifiers/emails never get mirrored
    return (
      <Typography
        component="code"
        variant="caption"
        dir="ltr"
        sx={{
          fontFamily: 'monospace',
          bgcolor: 'action.hover',
          px: 0.5,
          py: 0.125,
          borderRadius: 0.5,
          wordBreak: 'break-all',
        }}
      >
        {children}
      </Typography>
    );
  }

  // ```mermaid → live diagram (the generic renderer, not a bespoke card)
  if (match[1] === 'mermaid') {
    return <MermaidBlock code={code} />;
  }

  return (
    <Box sx={{ position: 'relative', my: 1.5, overflow: 'hidden', border: 1, borderColor: 'divider' }}>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          px: 1.5,
          py: 0.5,
          bgcolor: headerBg,
        }}
      >
        <Typography variant="caption" sx={{ color: fenceFg, fontFamily: 'monospace' }}>
          {match[1]}
        </Typography>
        <Tooltip title={copied ? 'Copied!' : 'Copy code'}>
          <IconButton size="small" onClick={handleCopy} aria-label="Copy code" sx={{ color: fenceFg, p: 0.25 }}>
            {copied ? <CheckIcon sx={{ fontSize: 13 }} /> : <ContentCopyIcon sx={{ fontSize: 13 }} />}
          </IconButton>
        </Tooltip>
      </Box>
      <Box
        component="pre"
        dir="ltr"
        sx={{
          m: 0,
          p: 1.5,
          bgcolor: fenceBg,
          overflowX: 'auto',
          fontFamily: 'monospace',
          fontSize: '0.75rem',
          lineHeight: 1.65,
          color: fenceFg,
          '& code': { fontFamily: 'inherit', fontSize: 'inherit', bgcolor: 'transparent', p: 0 },
        }}
      >
        <code className={className}>{children}</code>
      </Box>
    </Box>
  );
}

// ── Component overrides ───────────────────────────────────────────────────────

const components = {
  // code: handles both inline and fenced blocks
  code: CodeBlock,

  // strip the default <pre> wrapper — CodeBlock renders its own container
  pre: ({ children }) => <>{children}</>,

  // entity reference chip — [[kind:id:label]] → inline <EntityChip/>
  entityRef: ({ kind, id, label }) => <EntityChip kind={kind} id={id} label={label} />,

  // paragraphs — enterprise 15px / 1.7 (Copilot density)
  p: ({ children }) => (
    <Typography
      variant="body2"
      sx={{
        mb: 1,
        '&:last-child': { mb: 0 },
        fontSize: '0.9375rem',
        lineHeight: 1.7,
        letterSpacing: '0.005em',
      }}
    >
      {children}
    </Typography>
  ),

  // headings — H2 carries a 2px accent rule; no h5→caption jumps
  h1: ({ children }) => (
    <Typography
      component="h2"
      sx={{
        mt: 2,
        mb: 0.75,
        fontSize: '1.125rem',
        fontWeight: 650,
        letterSpacing: '-0.01em',
        lineHeight: 1.35,
        borderBottom: 2,
        borderColor: 'primary.main',
        pb: 0.5,
        display: 'inline-block',
        maxWidth: '100%',
      }}
    >
      {children}
    </Typography>
  ),
  h2: ({ children }) => (
    <Typography
      component="h3"
      sx={{
        mt: 1.75,
        mb: 0.5,
        fontSize: '1rem',
        fontWeight: 650,
        letterSpacing: '-0.01em',
        lineHeight: 1.35,
        borderBottom: 2,
        borderColor: 'primary.main',
        pb: 0.4,
        display: 'inline-block',
        maxWidth: '100%',
      }}
    >
      {children}
    </Typography>
  ),
  h3: ({ children }) => (
    <Typography
      component="h4"
      sx={{
        mt: 1.25,
        mb: 0.4,
        fontSize: '0.9375rem',
        fontWeight: 600,
        lineHeight: 1.4,
      }}
    >
      {children}
    </Typography>
  ),
  h4: ({ children }) => (
    <Typography
      component="h5"
      sx={{ mt: 1, mb: 0.25, fontSize: '0.875rem', fontWeight: 600 }}
    >
      {children}
    </Typography>
  ),
  h5: ({ children }) => (
    <Typography
      component="h6"
      sx={{ mt: 0.75, mb: 0.25, fontSize: '0.8125rem', fontWeight: 600 }}
    >
      {children}
    </Typography>
  ),
  h6: ({ children }) => (
    <Typography
      component="p"
      sx={{
        mt: 0.5,
        mb: 0.25,
        fontSize: '0.75rem',
        fontWeight: 600,
        color: 'text.secondary',
      }}
    >
      {children}
    </Typography>
  ),

  // lists
  ul: ({ children }) => (
    <Box
      component="ul"
      sx={{
        pl: 2.5,
        my: 0.75,
        mb: 1,
        fontSize: '0.9375rem',
        lineHeight: 1.7,
      }}
    >
      {children}
    </Box>
  ),
  ol: ({ children }) => (
    <Box
      component="ol"
      sx={{
        pl: 2.5,
        my: 0.75,
        mb: 1,
        fontSize: '0.9375rem',
        lineHeight: 1.7,
      }}
    >
      {children}
    </Box>
  ),
  li: ({ children, checked }) => {
    if (checked !== null && checked !== undefined) {
      return (
        <Box component="li" sx={{ display: 'flex', alignItems: 'flex-start', gap: 0.5, listStyle: 'none', ml: -2 }}>
          <Checkbox size="small" checked={!!checked} disabled sx={{ p: 0, mt: 0.125 }} />
          <Typography component="span" sx={{ fontSize: '0.9375rem', lineHeight: 1.7 }}>{children}</Typography>
        </Box>
      );
    }
    return (
      <Typography
        component="li"
        sx={{ mb: 0.35, fontSize: '0.9375rem', lineHeight: 1.7 }}
      >
        {children}
      </Typography>
    );
  },

  // tables — sticky head, tabular lining figures, caption-ready wrapper
  table: ({ children }) => (
    <Box
      sx={{
        overflowX: 'auto',
        my: 1.5,
        border: 1,
        borderColor: 'divider',
        borderRadius: 0,
      }}
    >
      <Table
        size="small"
        sx={{
          minWidth: 280,
          '& .MuiTableCell-root': {
            fontVariantNumeric: 'tabular-nums lining-nums',
          },
        }}
      >
        {children}
      </Table>
    </Box>
  ),
  thead: ({ children }) => (
    <TableHead
      sx={{
        bgcolor: 'action.hover',
        position: 'sticky',
        top: 0,
        zIndex: 1,
      }}
    >
      {children}
    </TableHead>
  ),
  tbody: ({ children }) => <TableBody>{children}</TableBody>,
  tr: ({ children }) => (
    <TableRow
      sx={{
        '&:nth-of-type(even)': { bgcolor: 'action.hover' },
        '&:last-child td': { borderBottom: 0 },
      }}
    >
      {children}
    </TableRow>
  ),
  th: ({ children }) => (
    <TableCell
      sx={{
        py: 0.75,
        px: 1,
        fontWeight: 600,
        fontSize: '0.6875rem',
        letterSpacing: '0.02em',
        whiteSpace: 'nowrap',
        color: 'text.secondary',
        borderBottom: 1,
        borderColor: 'divider',
        fontVariantNumeric: 'tabular-nums lining-nums',
      }}
    >
      {children}
    </TableCell>
  ),
  td: ({ children }) => (
    <TableCell
      sx={{
        py: 0.6,
        px: 1,
        fontSize: '0.8125rem',
        lineHeight: 1.5,
        fontVariantNumeric: 'tabular-nums lining-nums',
      }}
    >
      {children}
    </TableCell>
  ),

  // blockquote — borderRadius uses theme token (borderRadius:0.5 = 4px per shape.borderRadius:8)
  blockquote: ({ children }) => (
    <Box
      sx={{
        borderLeft: 3,
        borderColor: 'primary.main',
        pl: 2,
        py: 0.5,
        my: 1,
        bgcolor: 'action.hover',
        borderRadius: '0 4px 4px 0',
        color: 'text.secondary',
        fontSize: '0.6875rem',
      }}
    >
      {children}
    </Box>
  ),

  // inline formatting
  strong: ({ children }) => <Typography component="strong" variant="inherit" sx={{ fontWeight: 700 }}>{children}</Typography>,
  em: ({ children }) => <Typography component="em" variant="inherit" sx={{ fontStyle: 'italic' }}>{children}</Typography>,
  del: ({ children }) => <Typography component="del" variant="inherit" sx={{ textDecoration: 'line-through', color: 'text.secondary' }}>{children}</Typography>,

  // links — SPA <Link> for safe internal routes, new tab otherwise
  a: ({ href, children }) => {
    if (href && href.startsWith('/') && isSafeInternalRoute(href)) {
      return (
        <Link component={RouterLink} to={href} underline="hover" sx={{ fontWeight: 500 }}>
          {children}
        </Link>
      );
    }
    return (
      <Link href={href} target="_blank" rel="noopener noreferrer" underline="hover">
        {children}
      </Link>
    );
  },

  // figures — image with optional title → caption (theme tokens, flat)
  img: ({ src, alt, title }) => (
    <Box
      component="figure"
      sx={{
        my: 1.5,
        mx: 0,
        border: 1,
        borderColor: 'divider',
        bgcolor: 'background.paper',
      }}
    >
      <Box
        component="img"
        src={src}
        alt={alt || ''}
        title={title}
        sx={{ maxWidth: '100%', display: 'block' }}
      />
      {(title || alt) && (
        <Typography
          component="figcaption"
          variant="caption"
          color="text.secondary"
          sx={{
            display: 'block',
            px: 1,
            py: 0.75,
            textAlign: 'center',
            borderTop: 1,
            borderColor: 'divider',
            fontSize: '0.6875rem',
            letterSpacing: '0.01em',
          }}
        >
          {title || alt}
        </Typography>
      )}
    </Box>
  ),

  // horizontal rule
  hr: () => <Divider sx={{ my: 2 }} />,
};

// ── Public component ──────────────────────────────────────────────────────────

export {
  normalizeMermaidFences,
  reflowSingleLineMermaid,
  repairXychart,
  repairTopLevelBar,
  reflowMarkdownStructure,
  repairTableBlocks,
  sanitizeXychartAxisLabels,
  reflowCollapsedDataOnlyRows,
};

export default function MarkdownMessage({ content }) {
  const normalized = reflowMarkdownStructure(repairTableBlocks(normalizeMermaidFences(content)));
  return (
    <Box sx={{ '& > *:first-of-type': { mt: 0 }, '& > *:last-of-type': { mb: 0 } }}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath, remarkEntityChips]}
        rehypePlugins={[rehypeHighlight, rehypeKatex]}
        components={components}
      >
        {normalized}
      </ReactMarkdown>
    </Box>
  );
}
