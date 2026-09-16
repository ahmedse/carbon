# CHAT P0 — Chart vs prose mismatch (empty series)

**Date:** 2026-09-16  
**Seat:** Frontend+Backend Worker (Pulse)  
**Symptom (LIVE-QA):** Prose says correct headcount (e.g. **530**) but envelope chart titled **Active Employee Count** shows **“No data”**.

## Root cause

1. Headcount answers come from `aggregate_entity` as a **scalar**  
   `{metric: "headcount", value: 530, description: "Total active employees", …}` — not a breakdown with chartable buckets.
2. Envelope LLM often emitted `{title: "Active Employee Count", series: []}` (title only, empty series).
3. `EnvelopeChart` treated empty `flattenSeries` as a visible **“No data”** shell → trust defect even when prose matched DB.

## Fix

| Layer | Change |
|-------|--------|
| Backend | `enrich_envelope_charts` in `backend/ai/envelope_service.py` fills empty series from scalar tool results (`aggregate_entity.value` / analyze `total` with empty breakdown); synthesises one bar chart when LLM omitted charts; **drops** charts that remain empty. Prompt updated in `envelope_prompt.py` (never emit empty `series`). |
| Frontend | `EnvelopeMessage.jsx` — empty series → **omit chart** (no title + “No data” shell). |

## Tests

- Backend: `backend/ai/tests/test_answer_envelope.py` — enrich fill / drop / synthesise + synthesize_envelope enrich path.
- Frontend: `EnvelopeMessage.test.jsx` — omits empty-series charts.

**Counts (targeted):**
- pytest `ai/tests/test_answer_envelope.py -k "not build_ai_message"` → **19 passed**
- vitest `src/shell/EnvelopeMessage.test.jsx` → **11 passed**

## Live UI retest (2026-09-16 · IDE browser)

Prompt: *How many active employees do we have? Answer briefly with the exact number from People data.*

| Check | Result |
|-------|--------|
| Prose | **530** (“We have 530 active employees…”) |
| Visual | Status table Active / **530** / 100% — **not** empty chart shell |
| “No data” | **Absent** |
| Presence | Ready |

**A10 → PASS** · M17 closed for this defect.
