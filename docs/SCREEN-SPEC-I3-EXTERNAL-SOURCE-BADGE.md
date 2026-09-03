# Screen Spec — External Source Badge (ReasoningTrace "Why this answer")
# Canonical per `.ai-toolkit/shared/frontend-ready.md` (RULE_29 — Frontend Definition of Ready).
# Consumed by TASKS.md Phase I3-F. A worker does NOT code this view before all 9 artifacts below are complete.

---

## Artifact 1 — User Story + Acceptance

**Story:** As an AI-workspace user, when the assistant's answer draws on the open web
(`web_research`), I want a clear "External" badge on each cited source so I always know which
claims came from outside my data — never silently blended in.

**Acceptance (Given/When/Then):**

- **Happy path:** Given a message with `external_sources` (non-empty), when the user opens
  "Why this answer", then each external source renders an `ExternalSourceBadge` labelled
  `External · {provider} · {retrieved_at}`.
- **Source link:** Given a source with a `url`, then the title is a clickable link (opens in a
  new tab, `rel="noopener noreferrer"`).
- **No external sources:** Given a message with no `external_sources`, then the Sources section
  renders exactly as today (zero regression).
- **Malformed item:** Given a source item missing `url`/`title`, then it is skipped (never crash,
  never render a blank badge).

---

## Artifact 2 — Journey Map

```
Conversation → assistant answer with web citations
   └─ user clicks "Why this answer" (ReasoningTrace InfoOutlinedIcon)
        └─ expanded Paper
             ├─ "Sources" section
             │    └─ internal outcome lines (as today)
             │    └─ + external sources → ExternalSourceBadge (title → link + badge)
             └─ "Tools used" section (as today)
```
Friction points: (1) external sources must be visually distinct from internal data lines —
"External · not from your data" semantics (RULE_23 inverse); (2) the `retrieved_at` must be
formatted, not a raw ISO string; (3) links must not leak referrer.

---

## Artifact 3 — IA Placement

- Live inside the existing `ReasoningTrace` drawer (`carbon-frontend/src/shell/ReasoningTrace.jsx`)
  "Sources" section — **not** a new route, **not** the sidebar.
- `ReasoningTrace` is already fed by `AIMessageBubble` (`provenanceLines` at lines ~431–456);
  I3-F threads `external_sources` into that same wiring (a new `externalSources` prop or a merged
  `sources` list). No `App.jsx` change.

---

## Artifact 4 — Composition Spec (reuse, never invent)

```
ReasoningTrace
 ├─ "Sources" section
 │    ├─ internal lines (as today — isOutcomeLine filter)
 │    └─ ExternalSourceBadge  ← NEW, per external_sources item
 │         ├─ <Link href={url} target="_blank" rel="noopener noreferrer">{title}</Link>
 │         └─ <Chip size="small" variant="outlined" icon={<…/>} label={`External · {provider}`} />
 └─ "Tools used" section (as today)
```

**Reuse audit (mandatory):**
- [x] Badge = the existing `AIGeneratedBadge` pattern (`src/shell/AIGeneratedBadge.jsx` — Chip +
      icon + `aria-label`), generalized or extended for `source` labels. Do NOT invent a new chip.
- [x] Link = MUI `Link` (or theme-styled anchor), `target="_blank"` + `rel="noopener noreferrer"`.
- [x] Date formatting = existing `formatDate`/intl helper (do NOT render raw ISO).
- [x] RTL positioning = existing `useLanguage().isRtl` flip already in `ReasoningTrace` (line 58).
- [x] `LEAK_PATTERN` (RULE_23) filter is NOT bypassed by external sources.

---

## Artifact 5 — Complete State Matrix

### Page (message-level, data already present — no fetch)
| State | Rendering |
|-------|-----------|
| `idle` | No `external_sources` → Sources section renders as today |
| `loaded` | Each external source → `ExternalSourceBadge` + title link |
| `partial` | Malformed item (no url) skipped; others still render |
| `error` | *(not applicable — no fetch)* |

### Component (interaction)
| State | Where |
|-------|-------|
| `default/hover/focus/focus-visible` | badge chip + source link |
| `expanded/collapsed` | ReasoningTrace Paper (as today) |
| `open` | link opens new tab |

---

## Artifact 6 — Data Contract

No new fetch. Sources are already on the serialized message at **two** places (both `|| []`):
- top-level `message.external_sources`
- nested `message.provenance.external_sources`

Item shape (produced by `_build_external_sources`, `backend/ai/engine_runtime.py` lines 698–720):
```jsonc
{ "title": str, "url": str, "source": "wikipedia"|"duckduckgo"|"external_web", "retrieved_at": ISO-8601 }
```

Provider label map (source → label):
- `wikipedia` → "Wikipedia"
- `duckduckgo` → "DuckDuckGo"
- `external_web` → "Web search" (fallback)
Badge label = `External · {label} · {formatted retrieved_at}`.

Frontend reads `message.external_sources || message.provenance?.external_sources || []` —
always defensive, always a list.

---

## Artifact 7 — Accessibility (WCAG AA)

- [x] Badge = icon + text label (`aria-label`), never color-alone.
- [x] Source links have descriptive text (the title) + `aria-label` where needed.
- [x] Keyboard reachable + `focus-visible` on links.
- [x] `rel="noopener noreferrer"` on all external links.
- [x] Dates/URLs `dir="ltr"`.

---

## Artifact 8 — Performance Envelope

- [x] No fetch, no virtualization (external sources are typically < 10 items).
- [x] `useMemo` for the source-list derivation (stable across re-renders).
- [x] No new bundle weight (reuses `AIGeneratedBadge`/`Chip`).

---

## Artifact 9 — i18n / RTL

- [x] New strings via `t()` (`useTranslation('ai')`): "External", provider labels
      ("Wikipedia"/"DuckDuckGo"/"Web search"), "External · not from your data". Keys in BOTH
      `en` and `ar` `ai.json`.
- [x] `dir="ltr"` on URLs + dates.
- [x] `node scripts/check-i18n-keys.js` → 0 missing keys.
- [x] Badge positioning already RTL-aware via `useLanguage().isRtl`.

---

## Anti-patterns (instant reject — do NOT ship these)

- Inventing a new chip component instead of extending `AIGeneratedBadge`.
- Rendering raw ISO `retrieved_at` (must be formatted).
- External link without `target="_blank"` + `rel="noopener noreferrer"`.
- Silently dropping external sources when the message has them (RULE_23 inverse).
- Hardcoded English strings not `t()`-wrapped.

*Source: `docs/SCREEN-SPEC-I3-EXTERNAL-SOURCE-BADGE.md` — authored by Master Architect under RULE_29.*
