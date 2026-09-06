# Pulse Answer Quality — Phased Plan (PAQ series)

**Version:** 1.0
**Date:** 2026-09-06
**Status:** Dispatch in progress
**Owner:** Master Architect
**Audience:** backend-worker / frontend-worker / qa-validator agents

---

## Why this exists (problem class, distilled)

Pulse answers are fragile along three axes that were root-caused and fixed in this session:

1. **Format** is produced by LLM free-form markdown, then patched with regex reflow
   (headings / lists / mermaid / GFM tables). Reflow is a *fallback*, not a guarantee —
   it cannot fix an LLM that emits a malformed table in the first place.
2. **Intelligence** is unreliable — the LLM does arithmetic over **truncated** tool
   results (wrong totals), labels charts with **raw PKs**, silently swaps intent
   (`gender → position`), and never discloses missing data (`gender` 98.9% blank).
3. **Trust** is unverifiable — there is no CI gate that asserts "the numbers match the
   DB", "labels are resolved", or "a dominant bucket is not drawn as a pie".

## North star (enterprise wisdom, non-negotiable)

- **Render from TYPED DATA, not prose.** The LLM emits a validated *Answer Envelope*
  (typed blocks); a deterministic renderer draws it. (OpenAI Structured Outputs,
  Vega-Lite spec.)
- **LLM PLANS, engine COMPUTES.** Never let the LLM aggregate rows. The server does
  `GROUP BY`, label resolution, normalization, and DQ disclosure. (LookML / Cube /
  ThoughtSpot / PowerBI Copilot.)
- **DQ disclosure is first-class.** Null%, cardinality, truncation are machine-computed
  and mandatory. (Great Expectations / Monte Carlo.)
- **Eval harness + golden sets gate every change.** Deterministic checks (numbers match
  DB, labels resolved, chart-type rule) run in CI; an LLM-judge narration harness is
  opt-in (`@pytest.mark.live`). (OpenAI Evals / Braintrust / LangSmith.)

## What is already done this session (baseline — do not redo)

| Layer | Change |
|-------|--------|
| Backend | `ai/host_executor.py` — `_people_analytics()` server-side aggregation: GROUP BY, FK label resolution (`position_id → title`), synonym normalization (`M → male`), top-N "Other" collapse, blank-data caveats, `suggested_chart_type` (bar for dominant bucket, pie only for balanced ≤8). List endpoints expose `total` + `truncated`. |
| Catalog | `instance.yaml` — `analyze_employees` entry instructs model to use it for any distribution/count-by. |
| Prompt | `prompts.py` — AGGREGATION RULES (use analyze endpoints, never aggregate rows, disclose truncation, quote caveats, obey `suggested_chart_type`). |
| Frontend | `MarkdownMessage.jsx` — `reflowCollapsedTable()` + `splitProseFromInlineTableHeader()`; Mermaid `<style>` extracted outside SVG (no CSS text leak); compact-ui table overrides. |
| Tests | `test_people_grounding.py` (20), `MarkdownMessage.rich.test.jsx` (31). |

---

## Phase dependency order (do NOT reorder)

```
PAQ-1A (eval harness)  ── gates ──►  PAQ-2A (envelope backend) ──► PAQ-2B (renderer) ──► PAQ-3A (provenance UI)
PAQ-4A (gender data hygiene)  ────────── independent, can run in parallel ──────────
```

---

## PAQ-1A — Backend: deterministic answer-quality eval harness (P5)

**Objective:** A CI-safe pytest gate that asserts Pulse's deterministic answer-quality
invariants on a golden dataset, so future prompt/model/renderer changes cannot silently
regress correctness. This is the gate that makes PAQ-2A/2B/3A safe to build.

**Worker Role:** backend-worker
**Domain:** backend only
**Deps:** none (builds on the already-merged `_people_analytics`)

### What to build

1. `backend/ai/eval/__init__.py` + `backend/ai/eval/golden.py`
   - `GOLDEN_QUERIES`: list of `{question, expected_tool, expected_dimension, invariants[]}`
     covering at least: gender distribution, position distribution, headcount,
     "how many employees are active", and one out-of-scope question.
   - `GOLDEN_DATASET`: a seed spec that creates a **known** employee population
     (e.g. 6 male, 2 female, 1 blank gender, mixed positions/orgs) so assertions
     are on exact counts, not "≥ 1".
2. `backend/ai/eval/checks.py` — deterministic check functions (pure, no LLM):
   - `assert_counts_match_db(breakdown, qs)` — each bucket `count` equals the DB COUNT.
   - `assert_no_raw_pk_labels(breakdown)` — no label is a bare integer PK.
   - `assert_caveat_fires_for_blank(breakdown, threshold=50.0)`.
   - `assert_chart_type_rule(breakdown, suggested)` — dominant >70% ⇒ "bar"; balanced ≤8 ⇒ "pie"; >8 buckets ⇒ "bar".
   - `assert_truncation_collapsed_to_other(breakdown, max_buckets=15)`.
   - `assert_synonym_merged(breakdown, canonical, raw_variant)`.
3. `backend/ai/tests/test_answer_quality_eval.py` — wires `GOLDEN_DATASET` → `_people_analytics`
   → `checks`. Deterministic, DB-backed, CI-safe (no network, no LLM).
4. A **live** judge harness (opt-in, excluded from CI):
   - `backend/ai/tests/test_answer_quality_live.py` with `@pytest.mark.live` — runs the
     full pipeline over `GOLDEN_QUERIES` and applies `checks` to the synthesized output.
   - Register `live` marker in `backend/pytest.ini` (if not already present) so
     `pytest -m "not live"` is the CI default.

### Files to read first
- `backend/ai/host_executor.py` (`_people_analytics`, `_suggest_chart_type`, `_ANALYTICS_MAX_BUCKETS`)
- `backend/ai/tests/test_people_grounding.py` (existing helpers `_make_org`, `_make_employee`)
- `backend/pytest.ini` (existing markers; do not add xdist)

### DO NOT TOUCH
- Frontend (`carbon-frontend/**`)
- `_people_analytics` behavior (only *test* it — if a check reveals a real bug, STOP and report, don't silently fix here)
- No docker, no full-suite pytest, no `-n auto`

### Verification gate (Master runs)
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests/test_answer_quality_eval.py -q --maxfail=5 --disable-warnings -p no:cacheprovider
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests/test_people_grounding.py -q --maxfail=5 --disable-warnings -p no:cacheprovider
```
Report: both suites green; `pytest --collect-only -q` shows `live` tests exist but are excluded by default.

---

## PAQ-2A — Backend: Answer Envelope contract + Structured Outputs (P1)

**Objective:** Pulse emits a typed **AnswerEnvelope** — `{headline, prose[], tables[], charts[], caveats[], sources[]}` — instead of free-form markdown. Markdown survives only inside `prose[]`/`headline`. The renderer (PAQ-2B) draws `tables[]`/`charts[]` deterministically.

**Worker Role:** backend-worker
**Deps:** PAQ-1A complete (envelope is built *behind* the eval gate)

### What to build (contract-first)
1. `backend/ai/envelope.py` (or `backend/ai/engine/cognition/envelope.py`) —
   pydantic models: `TableBlock`, `ChartBlock` (typed Vega-Lite-ish spec), `CaveatBlock`,
   `SourceBlock` (tool name, rows returned, truncated flag, timestamp), `AnswerEnvelope`.
   Validation rules: no raw markdown in `tables[]`/`charts[]`; `sources[]` mandatory when
   any `tables[]`/`charts[]` present.
2. Structured-output path: prompt the model with a JSON schema (OpenAI `response_format`
   `json_schema`, or Pydantic-based parsing) so synthesis returns the envelope, not prose.
   Keep the existing markdown path as fallback until PAQ-2B lands.
3. Persist the envelope on the message artifact (`AIMessage`/`AIArtifact`) alongside the
   rendered text, so the frontend can render from data.
4. Unit tests: envelope validation (reject bare-PK table labels, missing sources,
   unknown chart types).

### Files to read first
- `backend/ai/engine/cognition/synthesis.py` (`_synthesize_tool_results`)
- `backend/ai/engine/llm/prompts.py` (current RENDERING_CAPABILITIES + AGGREGATION RULES)
- `backend/ai/models/workspace.py` (`AIMessage`, `AIArtifact`)

### DO NOT TOUCH
- Frontend; `guards.py`; mutation flow; no docker.

---

## PAQ-2B — Frontend: deterministic envelope renderer (P1)

**Objective:** `MarkdownMessage` renders envelope blocks from typed data (tables from
`rows[]`, charts from a spec, caveats as a disclosure banner, sources as chips), not
from reflowed markdown. Markdown fallback stays for non-envelope messages.

**Worker Role:** frontend-worker
**Deps:** PAQ-2A (needs the persisted envelope shape)

**Compact-ui compliance (non-negotiable):** `th` 0.625rem uppercase 600 0.05em letterSpacing,
`td` 0.6875rem, `thead` background.dark `#f4f4f5`, caption 0.625rem, body2 0.6875rem,
no raw inline `fontSize`/hex. All tokens from `carbonTheme.js`.

**Verification:** targeted `vitest` + `npm run lint` + `npm run build`.

---

## PAQ-3A — Frontend: Provenance UI (Sources chip)

**Objective:** Every data-bearing block renders a **Sources** chip: tool name, rows
returned, truncation status, resolved-at timestamp. Provenance is first-class — the
user can see *why* an answer is trustworthy.

**Worker Role:** frontend-worker
**Deps:** PAQ-2B (envelope renderer carries `sources[]`)

---

## PAQ-4A — Backend/Data: normalize Nibras gender seed data (optional, independent)

**Objective:** Standardize source data so `gender` is not 98.9% blank and `M`/`F` are
canonicalized to `male`/`female`. The engine already defends against this (synonym
merge + caveat); this removes the noise at the source.

**Worker Role:** backend-worker (data)
**Deps:** none — runs in parallel with PAQ-1A..3A.

### What to build
- A management command `normalize_employee_genders` that backfills canonical gender
  from raw `M`/`F` values (idempotent), OR a data migration. Report counts before/after.
- Do **not** invent genders for blank rows — blanks stay blank and remain disclosed.

---

## Cross-cutting (deferred, tracked separately)
- Streaming UX while envelope is computed.
- Model choice per surface (already `GPT-4o` for Pulse UI).
- LLM-judge narration scoring for the `live` harness (beyond deterministic checks).
