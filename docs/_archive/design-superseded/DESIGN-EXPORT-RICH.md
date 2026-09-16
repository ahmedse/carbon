# Rich Copy & Export — Design (Phase 4C)

**Status:** Approved — full scope A+B+C + long-content UX (scroll + expand/collapse)
**Scope:** Chat/Agent workspace (Pulse) — message-level copy & export with full
formatting (tables, code, mermaid diagrams, math, figures), Word-ready rich-text
clipboard, image/figure asset export, long-content handling (vertical/horizontal
scroll + expand/collapse), and server-side document export with audit.
**Companion:** `DESIGN-PLATFORM.md` (platform), `.ai-toolkit/shared/ux-patterns.md`
(conversational surfaces), `.ai-toolkit/shared/design-principles.md` (10 principles).
**Rendered content source of truth:** `carbon-frontend/src/shell/MarkdownMessage.jsx`
(Phase 4 generic rich renderer — GFM tables, hljs code, live mermaid SVG, KaTeX, captions).

---

## 1. Job to be done (user stories)

| # | User story | Value |
|---|-----------|-------|
| U1 | "I want to copy **this whole message** and paste it **into Word with its tables, code styling, and diagrams**." | Report-grade deliverables from chat |
| U2 | "I want to select **part of a message** and copy just that — formatted." | Precise extraction, no re-typing |
| U3 | "I want to **save this flowchart/sequence diagram as an image** (PNG/SVG)." | Diagrams leave the UI as assets |
| U4 | "I want to copy a message as **plain text** (markdown source or stripped)." | Slack/email/notes |
| U5 | "I want to export **the whole conversation** as a Word document / HTML / Markdown with images embedded." | Shareable knowledge documents |
| U6 | "Long replies shouldn't blow up my screen — I want to **scroll and collapse/expand** them." | Readability at scale (added by user) |

Acceptance is per-phase in §11.

---

## 2. Research — what top systems do (and where they fail)

### 2.1 Industry state of the art

| System | Copy | Export | Gap we can beat |
|--------|------|--------|-----------------|
| ChatGPT | Copy = markdown source text only | Conversation export = HTML transcript (full fidelity) | No rich-text **clipboard** (pasting into Word loses formatting); no per-diagram image export |
| Claude.ai | Copy = markdown | API-only export | Same |
| MS Copilot Chat | Copy = markdown | — | Same |
| **Notion** | Rich-text clipboard (`text/plain` + `text/html`), pastes into Word with tables/formatting intact | — | The benchmark for **U1**; we adopt its approach (inline-styled HTML serialization) |
| Obsidian | Copy = markdown; export HTML | — | No rich clipboard |
| Mermaid Live Editor / Mermaid CLI | — | PNG/SVG/PDF export per diagram (headless Chromium) | Server-side diagram rasterization is the enterprise answer (Phase C) |

### 2.2 Standards & papers

- **W3C Clipboard API / ClipboardEvent** (MDN, 2026): `ClipboardItem` supports
  multiple MIME types in one write — `text/plain` + `text/html` (Chrome 86+,
  FF 127+, Safari 13.1+). The OS paste target (Word) chooses the richest format
  it understands. **This is the sanctioned mechanism for U1.** Also:
  - `clipboard-write` permission or transient user activation required (we always
    call from a click / copy event → satisfied).
  - Event-based `copy` handler with `event.clipboardData.setData('text/html', …)`
    is the classic synchronous path — no async permission needed, works in every
    browser, and gives us **selection-aware** copy (U2) for free.
- **HTML Living Standard — clipboard fragment convention**: rich HTML written to
  the clipboard should be a self-contained fragment; Word additionally prefers
  `<!--StartFragment-->`…`<!--EndFragment-->` markers and **inline styles** over
  classes (Word drops unknown CSS classes; `mso-*` styles are Word-specific but
  plain inline `style=` is reliably honored).
- **Word HTML paste requirements** (Microsoft support): Word will render standard
  semantic HTML (`h1`–`h6`, `p`, `ul/ol/li`, `table/th/td`, `pre/code`, `img`,
  `blockquote`) with inline styles. Tables must carry `border`, `border-collapse`,
  cell padding inline to survive. This shapes our serializer (§5.2).
- **Pandoc** (universal document converter, basis of Quarto): the canonical
  markdown→docx/html/pdf pipeline for enterprise doc generation. Not installed in
  this environment (verified) → server-side .docx via pandoc is a Phase C
  deployment decision, not a dev dependency.
- **Kroki** (self-hostable diagram-as-image HTTP service): enterprise pattern for
  server-side mermaid/plantuml rendering. Alternative to bundling headless
  Chromium (Phase C).

### 2.3 What we will NOT do (anti-patterns from research)

- ✗ `document.execCommand('copy')` — deprecated.
- ✗ Clipboard via a hidden textarea only — loses HTML.
- ✗ Server round-trip for copy — copy must be instant, offline-safe, no DB.
- ✗ `html-docx-js` — unmaintained; prefer the maintained `docx` npm lib or HTML.
- ✗ Fake `.docx` extension on HTML content — hacky; if we ship Word export, ship
  a real `.docx` (client `docx` lib) or honest `.html` (Word opens it natively).

---

## 3. Toolkit principles applied

- **design-principles.md** P1 (user goal first), P3 (progressive disclosure —
  defaults = plain copy; rich options one click deeper), P6 (consistency — reuse
  the existing hover action bar, `notify()` snackbar, `isSafeInternalRoute`),
  P7 (sensible defaults), P8 (instant local response — no server for copy).
- **ux-patterns.md** conversational surfaces: actions live in the **hover toolbar**,
  never always-on rows; status exceptional; latency/cost never as inline chips.
- **RULE_8** design tokens only (exported HTML is user content, not app UI — but
  the export menu/buttons use tokens).
- **RULE_10** apiFetch for any network call (only needed if we add backend export).
- **RULE_21** no auto-mutation — export is read-only by construction.
- **RULE_23** outcome-oriented copy: "Copy with formatting", "Saved diagram as
  PNG" — never "serialized DOM to clipboard".
- **RULE_22** no dangling routes — export uses blob downloads, no routes.
- **Security**: exports contain only what the user can already see (existing
  scope enforcement); mermaid SVG serialization happens in the user's own session
  (same trust domain as rendering — `securityLevel:'loose'` already in use);
  internal SPA links in exports render as relative links in `.md` and as
  absolute links **only** when a public base URL is configured (no internal host
  leakage otherwise).

---

## 4. Architecture overview

**Layered, frontend-first.** Everything in Phase A+B is pure client-side
(instant, offline, no DB, no new backend surface). A backend export service is
an optional Phase C for enterprise consistency (server-rendered PNGs, audit trail).

```
┌─ UI (AIMessageBubble / AIConversationView) ───────────────────────────┐
│  hover action bar ── Copy ▾ / Save image ▾ / Export message ▾         │
│  + selection-aware onCopy on the message container (native Ctrl+C)    │
└───────────────┬───────────────────────────────────────────────────────┘
                ▼
┌─ exportUtils.js (pure, unit-testable) ────────────────────────────────┐
│  copyRichHTML(node|selection)   → ClipboardItem {text/plain, text/html}│
│  htmlToWordFragment(html)       → inline-styled, fragment-marked HTML  │
│  svgToPng(svgNode, scale)       → canvas → Blob (retina 2x/3x)        │
│  svgToSvgBlob(svgNode)          → XML Blob                             │
│  imgToPngBlob(imgEl)            → fetch → canvas (CORS-safe fallback) │
│  markdownToAst / astToDocx      → client `docx` lib (Phase B)         │
│  downloadBlob(blob, filename), downloadAll(files)                     │
└───────────────┬───────────────────────────────────────────────────────┘
                ▼
   Clipboard (OS)          Downloads (OS)         Artifacts (existing)
   Word/Google Docs        .png/.svg/.md/.html/.docx
```

**Design decision — serialize the rendered DOM, don't re-render markdown.**
The user must get **what they see**. `MarkdownMessage` already produced the
styled DOM (tables, hljs `<span>`s, mermaid `<svg>`, KaTeX). Exporting a
clone-with-inline-styles of that DOM guarantees fidelity with zero double-
rendering drift. Markdown AST → `.docx` (Phase B) is the exception: docx needs
paragraph/image objects, so we walk the markdown AST and rasterize mermaid
blocks to PNG first (same `mermaid.render` already used).

---

## 5. Phase A — Clipboard + message actions (v1, pure frontend)

### 5.1 New UI — hover action bar (AIMessageBubble)

Existing bar: `Copy` (plain), `More ⋮`. New:

```
[Copy ▾]  [Save image ▾]           …existing usage/time meta…
  ├─ Copy                      ├─ Diagram 1 (flowchart) → PNG 2x
  ├─ Copy with formatting      ├─ Diagram 1 → SVG
  ├─ Copy markdown             ├─ Figure: chart.png → Save
  └─ (rich copy is the default └─ Save all images (.zip)
       when you Ctrl+C a        (n items ⇒ "Save all (n)")
       selection in the msg)
```

- Keep `Copy` = current behavior (plain text) — **zero regression**.
- `Copy with formatting` → `copyRichHTML(contentNode)` (§5.2).
- `Copy markdown` → raw `message.content` (same as today, relabeled).
- Diagram items come from querying the message DOM for `svg[id^="mmd-"]`
  (+ caption from sibling). Regular `<img>` elements get "Save".
- `Save all images (.zip)` → `jszip` (new dep, small/stable) bundling each
  PNG/SVG; single-item case downloads directly (no zip needed).
- Buttons/menu follow the existing MUI `Menu` pattern already in the file.

### 5.2 `copyRichHTML(node)` — Word-grade rich copy

1. **Clone** `node` (deep), strip interactive wrappers (buttons, tooltips,
   provenance icons) — keep only content: `h1–h6, p, ul/ol/li(input checkbox),
   table/th/td, pre>code, blockquote, img, a, strong/em/del, hr`.
2. **Inline styles** — walk the clone; for each element copy the **computed
   styles** relevant to print/paste (`color, background-color, font-family,
   font-size, font-weight, font-style, text-align, border, padding, margin,
   white-space` for `pre/code`). Tables additionally get inline `border,
   border-collapse, cellpadding` (Word requirement).
3. **Images** — mermaid SVGs: serialize → inline `<img src="data:image/png;base64,…">`
   (rasterized via `svgToPng`, white background — Word has no dark mode);
   `<img>`s: fetch → data URI (CORS-safe fallback: keep original `src`).
   LaTeX/Katex: keep rendered spans with inline styles (Word renders them as text).
4. **Links** — internal routes: absolute only if `VITE_PUBLIC_BASE_URL` set,
   else relative text; external: keep `href` + `target`.
5. Wrap: `<!--StartFragment-->` + `<div style="font-family:…; color:…">…` +
   `<!--EndFragment-->`.
6. **Write** `ClipboardItem({ 'text/plain': plainText, 'text/html': html })`
   (fallback: legacy event-based `copy` with `clipboardData.setData`).

### 5.3 Selection-aware copy (U2) — native Ctrl+C on messages

Attach `onCopy` to the message container. On copy event:
- If there is a non-collapsed `window.getSelection()` **inside** this message →
  serialize the selected range (clone + inline styles, same serializer), and
  `e.clipboardData.setData('text/html', …)` + `setData('text/plain', …)`,
  `e.preventDefault()`.
- Else → default behavior (whole-message plain copy already exists via button).

This delivers "select part of the message → Ctrl+C → paste into Word with
formatting" — the Notion-style power move. Zero new visible UI.

### 5.4 Files

| File | Change |
|------|--------|
| `carbon-frontend/src/utils/exportUtils.js` | **NEW** — serializer, clipboard, svg→png, img→png, download helpers |
| `carbon-frontend/src/shell/AIMessageBubble.jsx` | action-bar submenus + `onCopy` on container + ref to content node |
| `carbon-frontend/package.json` | add `jszip` |
| `carbon-frontend/src/__tests__/exportUtils.test.js` | **NEW** — unit tests |
| `carbon-frontend/src/__tests__/AIMessageBubble.export.test.jsx` | **NEW** — action/menu/copy-behavior tests |

### 5.5 Long-content UX (U6) — scroll + expand/collapse

Vertical bloat in a conversation is a top readability killer. Rules:

- **Horizontal scroll (already per-block):** tables (`overflowX:auto`),
  code blocks, and mermaid containers already scroll horizontally. Verified in
  `MarkdownMessage.jsx` (Phase 4) — kept as-is.
- **Vertical collapse (new):** `LongContent` wrapper around the AI message
  body. Deterministic heuristic: `content.length > 1600` → collapsed by default.
  - Collapsed: `maxHeight: 320px` + `overflowY: auto` (inner scroll) + soft
    bottom fade.
  - **"Show more"** expands fully (browser scroll takes over — no nested
    scrollbar) and **"Show less"** re-collapses (toggle, per message, `useState`).
  - Collapse is **purely visual** (max-height/overflow) — the DOM stays intact,
    so rich copy / export / Ctrl+C selection serialize the FULL content
    regardless of collapse state. No special-casing in the serializer.
- Interactive cards (`structuredContent`: DataGrid, NLRuleTestCard, drafts)
  stay **outside** the collapse — never clipped, always actionable.

---

## 6. Phase B — Document export (v2)

### 6.1 Message-level "Export message ▾"
- **Markdown (.md)** — `message.content` (already have).
- **Rich HTML (.html)** — self-contained document (inline styles + embedded
  base64 images) → opens in Word & browsers offline.
- **Word (.docx)** — client-side via `docx` npm lib: walk markdown AST
  (reuse `remark-parse` — already in the dependency tree via `react-markdown`),
  emit `Paragraph/Table/Heading/Image`; mermaid blocks rasterized to PNG first
  (reuse `MermaidBlock`'s `mermaid.render`). Adds `docx` dependency.

### 6.2 Conversation-level export (AIConversationView export menu)
Existing `Markdown (.md)` / `JSON (.json)` stay. Add:
- **Rich HTML (.html)** — same serializer over the whole transcript (roles,
  timestamps, images embedded).
- **Word (.docx)** — same AST walker, per-message.

Both reuse one shared "transcript → rich document" builder so message-level and
conversation-level stay identical in look.

---

## 7. Phase C — Backend export service (enterprise, optional)

Only if server-side consistency is required later:
- `export_conversation(…, fmt="docx"|"html")` server-side: python-docx +
  markdown parser; mermaid → PNG via **Kroki** (self-hosted service) or bundled
  headless Chromium (deploy decision, documented — never in dev per user rule).
- `POST …/export/` endpoint → returns blob with `Content-Disposition`; wired
  through `apiFetch` (RULE_10); export **audited** via existing
  `audit_trail`/ops observability (who exported what, when).
- Templates: optional cover page, org branding, watermark for read-only users.
- **Justification gate:** only build when users need identical exports across
  devices / audit compliance. Phase A+B cover 95% of the ask with zero backend.

---

## 8. UX details (per toolkit)

- Hover-only reveal (matches existing `showActions` pattern); submenus are
  standard MUI `Menu`.
- Feedback: `notify({message:'Copied with formatting'})` /
  `'Saved diagram as PNG'` — outcome language (RULE_23), auto-dismiss (ux-patterns).
- Copy button icon swaps to `Check` momentarily (existing `copied` state reused).
- No modal-on-modal; menus close before action (existing pattern).
- Keyboard: standard `Ctrl+C` works for selections (native); actions are
  icon buttons already focusable (design-principles P9).
- Perceived performance: copy is synchronous-fast; PNG rasterization is async
  with the existing spinner-on-element convention for >1s.

---

## 9. Security & compliance

- Exports are read-only, scope-enforced (only the user's own accessible content —
  no new backend surface in A/B).
- Clipboard write requires user gesture (click or copy event) → satisfies
  browser permission rules.
- Mermaid SVG serialization: same trust domain as on-screen rendering
  (`securityLevel:'loose'` is already the app's choice; no new code executes).
- Internal route leakage: relative links in `.md`; absolute links in rich
  exports **only** when `VITE_PUBLIC_BASE_URL` is configured; never internal host.
- Zip contents sanitized filenames (`slugify`, no path separators).
- No data exfil: all work happens in the browser; nothing is uploaded.

---

## 10. Testing & gates

- **Frontend unit (vitest):** `exportUtils` — inline-styler (table borders,
  pre/code colors), fragment markers, svg→png canvas mock, clipboard write
  (`ClipboardItem`/fallback), selection serializer, link rewriting.
- **Component (vitest + jsdom):** AIMessageBubble — menu opens, `Copy with
  formatting` calls serializer and clipboard with both MIME types; `onCopy`
  handler intercepts selections; diagram menu lists one item per mermaid SVG;
  `Save all` zips (jszip mock) or single-downloads.
- **Conversation view:** export menu gains HTML/DOCX items; download invoked
  (blob mock); existing md/json export tests still green.
- **Regression:** full vitest suite — must stay at **561 passed / 9 pre-existing
  failures** baseline (AIMessageBubble.feedback 5, AIArtifacts 2, AISharedThreads 2 —
  documented, do not fix).
- **Backend:** unchanged in A/B → gate = existing `pytest ai appregistry
  --ignore=ai/tests/test_store_execute.py` (510 passed) stays green.
- **ESLint** clean on all touched files; `npm run build` clean.

---

## 11. Acceptance criteria (per phase)

**Phase A**
- [ ] Copy with formatting → paste into Word: tables have borders, code keeps
      dark-bg styling, mermaid appears as image, links work — verified manually
      + by component tests asserting both MIME types.
- [ ] Select part of a message → Ctrl+C → Word paste = only that part, formatted.
- [ ] Each diagram in a message has "Save as PNG/SVG"; Save all → zip.
- [ ] Existing "Copy" unchanged; all pre-existing tests still pass.
- [ ] Long replies collapse with inner vertical scroll; "Show more/less" toggles;
      horizontal scroll present for tables/code/diagrams.

**Phase B**
- [ ] Message & conversation export offer .md/.html/.docx; .docx opens in Word
      with headings, tables, embedded diagram images.
- [ ] HTML export is self-contained (works offline, images inline).

**Phase C** (if approved)
- [ ] Server exports match client fidelity; export events appear in audit trail.

---

## 12. Rollout order (approved — full scope)

1. **Phase A** — rich clipboard + selection copy + diagram image export +
   long-content scroll/expand-collapse. One new util file, one component change,
   `jszip`.
2. **Phase B** — .docx/.html document exports (message + conversation).
3. **Phase C** — backend export endpoints (html/docx) + audit trail; diagram
   rasterization server-side documented as a deploy-gate (no docker in dev).

Estimated footprint: A ≈ 450–600 LOC + tests; B ≈ 250–400 LOC + tests; C backend
≈ 300–500 LOC + tests + deploy config.
