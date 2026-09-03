# Screen Spec — Code Sandbox Result Rendering (AIMessageBubble)
# Canonical per `.ai-toolkit/shared/frontend-ready.md` (RULE_29 — Frontend Definition of Ready).
# Consumed by TASKS.md Phase I2-F. A worker does NOT code this view before all 9 artifacts below are complete.

---

## Artifact 1 — User Story + Acceptance

**Story:** As an AI-workspace user, when the assistant runs `code.execute` to analyze/plot my
data, I want to see the computed table, generated chart image, and the code that produced it —
all inline in the answer bubble — so I can verify the analysis without leaving the conversation.

**Acceptance (Given/When/Then):**

- **Happy path (chart):** Given a message whose `code_result` has `image_b64`, when the bubble
  renders, then an inline `<img>` (base64 PNG) is shown inside the answer bubble.
- **Happy path (table):** Given `code_result.table_rows` is a non-empty list, then a compact
  data grid renders the rows (reuse the existing `nl_query_result` table branch).
- **Code transparency:** Given any `code_result`, then a collapsed "Code used" disclosure shows
  the executed code (and `stdout`) — collapsed by default, expandable, never inline-by-default.
- **Empty/absent:** Given a message with NO `code_result`, then the bubble renders exactly as
  today (zero regression to existing `metadata.type` branches).
- **Error:** Given `code_result.error` is non-empty, then a friendly inline error state is shown
  (the `error` string, not a stack trace) — no image/table is rendered.
- **Fallback scalar:** Given `code_result.result` is a scalar with no `image_b64`/`table_rows`,
  then the scalar is rendered as a short key/value line (never dropped silently).

---

## Artifact 2 — Journey Map

```
Conversation → user asks "plot emissions trend"
   └─ assistant runs code.execute → message carries metadata.code_result
        └─ AIMessageBubble renders structured content:
             ├─ (chart)   inline <img data:image/png;base64,…>  (alt text = code intent/step label)
             ├─ (table)   CarbonDataGrid (compact, ≤ first 10 rows + "Show all N")
             ├─ (scalar)  KeyValueOutput line
             ├─ (error)   friendly error Alert (no Retry — user re-asks)
             └─ "Code used" collapsed disclosure (PlanningHeader-style) → code + stdout
```
Friction points: (1) the base64 PNG can be large — lazy-load and never inline it into export
without gating; (2) the "Code used" section must default collapsed (transparency without clutter);
(3) the table must reuse the existing grid, never a raw `<table>`.

---

## Artifact 3 — IA Placement

- Live inside the existing `AIMessageBubble` structured-content dispatcher
  (`carbon-frontend/src/shell/AIMessageBubble.jsx` `renderStructuredContent()`), as a NEW
  `metadata.type === "code_result"` branch (or a sibling check on `message.code_result`) — **not**
  a new route, **not** the sidebar. No `App.jsx` route change.
- The chart/table/scalar render in the SAME `<Box>` slot that currently holds `CarbonDataGrid`
  (the `nl_query_result` branch) and the other structured cards.

---

## Artifact 4 — Composition Spec (reuse, never invent)

```
AIMessageBubble
 └─ renderStructuredContent()  ← add a code_result branch
     ├─ (chart)   <Box><img src={`data:image/png;base64,${image_b64}`} alt={…} loading="lazy" /></Box>
     ├─ (table)   CarbonDataGrid (lazy)  ← REUSE nl_query_result branch (toGridRows/toGridColumns)
     ├─ (scalar)  KeyValueOutput  ← src/components/ai/StepOutputRenderer.jsx
     ├─ (error)   Alert (severity="warning")  ← error string, no stack trace
     └─ CodeUsedDisclosure  ← mirrors PlanningHeader collapse (Paper + ExpandMore/ExpandLess + aria-expanded)
          └─ <pre dir="ltr">{code}</pre> + stdout (truncated)
```

**Reuse audit (mandatory):**
- [x] Table = lazy `CarbonDataGrid` (`import { lazy } … '../components/DataGrid/CarbonDataGrid'`), same `toGridRows`/`toGridColumns` helpers as `nl_query_result`.
- [x] Collapse pattern = `PlanningHeader` behavior (Button + ExpandMoreIcon/ExpandLessIcon, `aria-expanded`, Paper on expand) — copy its `localStorage`/`prefers-reduced-motion` handling.
- [x] Scalar/raw output = `KeyValueOutput` from `src/components/ai/StepOutputRenderer.jsx` (do NOT hand-roll a `<pre>`).
- [x] Feedback = none needed for read-only result; error state uses inline `Alert`, not a toast.
- [x] No raw `fontSize`/`height`/`bgcolor` literals — theme tokens only.
- [x] No raw `<table>` / `<table>` wrapper — `CarbonDataGrid` only.

---

## Artifact 5 — Complete State Matrix

### Page (message-level, data already present — no fetch)
| State | Rendering |
|-------|-----------|
| `idle` | No `code_result` → bubble renders as today (no change) |
| `loaded` (chart) | inline `<img>` |
| `loaded` (table) | `CarbonDataGrid` (compact) |
| `loaded` (scalar) | `KeyValueOutput` |
| `error` | `Alert` with the `error` string (no image/table) |
| `empty` | `code_result` present but all of `image_b64`/`table_rows`/`result` are null/empty → render nothing extra (or a minimal "no output" note) |

### Component (interaction)
| State | Where |
|-------|-------|
| `collapsed` / `expanded` | "Code used" disclosure (default collapsed) |
| `focus-visible` | the disclosure toggle button |
| `loading` | `CarbonDataGrid` lazy-load (route already lazy; grid shows its own loading) |
| `error` | inline `Alert` |

**The three "empty" states are DISTINCT:** this view has no filters, so "no results" does not
apply; "no data" = `code_result` absent (render as today); "loading empty" = not applicable
(data is embedded in the message, never fetched).

---

## Artifact 6 — Data Contract

No new fetch. The message payload (already returned by the workspace message serializer) gains one
field, threaded by the I2-F **backend seam** (mirror of I3-B's `external_sources`):

`message.code_result` (object | absent) — shape produced by `CodeSandbox.execute`:
```jsonc
{
  "stdout": str,           // captured subprocess stdout (may be "")
  "error": str | null,     // subprocess error string (null on success)
  "image_b64": str | null, // base64 PNG (matplotlib)
  "table_rows": list[dict] | null,  // DataFrame.to_dict(orient="records") or list[dict]
  "result": any | null     // scalar fallback (e.g. a number/string)
}
```

**Backend threading seam (I2-F prerequisite — do BEFORE the frontend):**
1. `backend/ai/engine_runtime.py`: add `_build_code_result(completed_tools)` — iterate
   `completed_tools`, find the tool whose `tool_name == "code.execute"` (skip items with `error`,
   skip `requires_confirmation`), parse `item["result"]` (JSON-string or dict) and return that
   dict verbatim (it IS the sandbox shape). Return `None` if no code.execute result.
2. Add `"code_result": _build_code_result(completed_tools)` to the turn `result` dict
   (alongside `tool_trace`/`external_sources`, ~line 208).
3. `backend/ai/intelligence.py` `_build_ai_message`: add `code_result: dict | None = None` param;
   `if code_result: metadata["code_result"] = code_result` (mirror `external_sources` at 3895–3896).
4. Pass `code_result=res.get("code_result")` at the 3 call sites (654, 2426, 3608).
5. `_serialize_message`: add `"code_result": metadata.get("code_result")` (mirror line 4062).

Frontend reads `message.code_result || message.metadata_json?.code_result`. Always defensive:
`code_result` may be absent → render nothing.

---

## Artifact 7 — Accessibility (WCAG AA)

- [x] Chart `<img>` has `alt` text describing the chart (use the code's step label/intent when
      available, else "Generated chart").
- [x] "Code used" toggle is keyboard-reachable with visible `focus-visible` + `aria-expanded`.
- [x] `<pre dir="ltr">` for code/stdout (code must not mirror in RTL).
- [x] Error state = `Alert` with `role="alert"` (not color-alone).
- [x] Table cells/numbers `dir="ltr"`.
- [x] Contrast via theme tokens (no raw hex).

---

## Artifact 8 — Performance Envelope

- [x] `loading="lazy"` on the chart `<img>`; no eager decode of large base64.
- [x] Table capped to first ~10 rows with a "Show all N rows" affordance (mirror
      `StepOutputRenderer.TableOutput` `MAX_TABLE_ROWS = 10`), never render hundreds of rows.
- [x] `CarbonDataGrid` already lazy-loaded at route level — no new bundle weight.
- [x] `useMemo` for the grid rows/columns derivation (reuse the `nl_query_result` memo pattern).
- [x] No fetch, no debounce, no N+1 — data is embedded in the message.
- [x] No `if (!code_result) return null` (blank frame) — absent state renders as today.

---

## Artifact 9 — i18n / RTL

- [x] New strings via `t()` (`useTranslation('ai')`): "Code used", "Show all {n} rows",
      "No output", "Generated chart", "Analysis failed". Keys in BOTH `en` and `ar` `ai.json`.
- [x] `dir="ltr"` on the code `<pre>`, the table, and the chart container (code/numbers do not mirror).
- [x] `node scripts/check-i18n-keys.js` → 0 missing keys.
- [x] Directional icons (expand chevron) mirrored in RTL via `useLanguage().isRtl`.

---

## Anti-patterns (instant reject — do NOT ship these)

- Raw `<table>` instead of `CarbonDataGrid`; raw `<pre>` without `dir="ltr"`.
- Chart `<img>` without `alt` / `loading="lazy"`.
- "Code used" expanded by default (must default collapsed).
- `if (!code_result) return null` (blank bubble regression).
- Hardcoded English strings not `t()`-wrapped.
- Rendering `error` as a stack trace / raw exception text.

*Source: `docs/SCREEN-SPEC-I2-CODE-SANDBOX-RESULT.md` — authored by Master Architect under RULE_29.*
