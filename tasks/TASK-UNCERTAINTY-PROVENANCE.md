# TASK: Uncertainty Provenance — Kill Silent Absence→Answer Coercion (Platform-Wide)

**Dispatcher:** Master Architect
**Workers:** backend-worker (Phases 1–5), qa-validator (Phase 6)
**Priority:** High — this is the hallucination root cause (UP-0011), not a weather fix
**Contract:** `.ai-toolkit/shared/uncertainty-provenance.md`
**Rule:** `.ai-toolkit/universal/rules/ai-uncertainty-provenance.md`
**Pattern:** `patterns/index.md` UP-0011

---

## Motivation (abstract, not weather)

The observed weather failure ("north coast egypt" → Wikipedia city-history presented as a
weather answer) is one instance of a **universal defect**:

> A value whose epistemic status is **absent / not-understood** is silently re-typed as
> **known**, and a downstream stage narrates it with full confidence.

This is the single root cause of agent hallucination on this platform. The model is not
lying — it faithfully renders a value whose uncertainty was **erased at a boundary**. We do
NOT fix this by adding tools or alias maps (object-level, scales with an infinite world).
We fix it by enforcing **confidence conservation + tri-state results + mandatory
escalation** at every seam (meta-level, constant cost).

### The law we are enforcing
1. **Conservation of confidence** — no stage emits confidence higher than `min(inputs)`.
2. **Absence is a value** — `no_match` ≠ `empty` ≠ `error` ≠ `timeout`; never one falsy branch.
3. **Unknown routes up, known routes down** — open vocab → LLM/human; closed vocab → code.
4. **On no-match, decide — never act** — LLM normalizes/asks; never fabricates to fill a gap.

---

## Design: the tri-state result

Every deterministic resolver/primitive returns one of three, and the distinction survives
to the caller:

```python
# Canonical shape (dict-based, RULE_20 stdlib-only — no new deps)
{"status": "resolved", "data": {...}, "confidence": 0.0-1.0, "source": "..."}
{"status": "no_match", "reason": "unresolved_location", "hint": "north coast egypt",
 "candidates": [...optional...]}                     # → escalate UP to the LLM
{"status": "error",    "cause": "forecast_http_500", "detail": "..."}   # → report, no substitute
```

`no_match` MUST NOT be coercible into `resolved` by a truthiness check. Callers branch on
`status`, never on `if result:`.

---

## Scope — Phases

### Phase 1 — Audit the boundaries (backend-worker, read-only)
Produce an inventory of every seam that currently collapses absence into falsy. Grep + read,
no edits. Deliverable: table in `TASK-RESULTS-UNCERTAINTY-PROVENANCE.md`.

**Files to read first:**
- `backend/ai/plugins/web_research.py` — `_weather` returns `None` for no-match (the exemplar).
- `backend/ai/engine/cognition/turn/runner.py` — the fall-through that presents fallback as answer.
- `backend/ai/engine/cognition/turn/intent.py` — `IntentResolver.resolve` returns `None` on failure.
- `backend/ai/engine/agent/tools.py`, `backend/ai/subagent_service.py` — tool dispatch seams.
- Retrieval/memory reads: `backend/ai/engine/knowledge/semantic_layer.py`,
  `backend/ai/engine/memory/episodic.py`, `backend/ai/engine/knowledge_graph/context.py`.

**Grep signatures (from the contract's "Detectable" section):**
```bash
grep -rn "return None" backend/ai/plugins backend/ai/engine/cognition/turn
grep -rniE "fall.?back|still gets something|fall through" backend/ai
grep -rnE "if not (results|matches|hits|data|rows)\b" backend/ai
```
Classify each hit: does it conflate `no_match` with `empty`/`error`? (Y/N + which).

**Gate:** inventory table with ≥ the known 4 seams, each tagged `conflates|clean`.

---

### Phase 2 — Introduce the tri-state helper (backend-worker)
One tiny stdlib-only module the whole engine reuses — do NOT scatter dict literals.

- **CREATE** `backend/ai/engine/core/resolution.py`:
  - `resolved(data, *, confidence=1.0, source="") -> dict`
  - `no_match(reason, *, hint="", candidates=None) -> dict`
  - `error(cause, *, detail="") -> dict`
  - `is_resolved(r) / is_no_match(r) / is_error(r) -> bool`
  - `min_confidence(*rs) -> float` — the conservation helper.
- Pure functions, no imports beyond stdlib (RULE_20). Unit-tested in isolation.

**Gate:** `pytest ai/tests/test_resolution.py -q` green (new file, ~8 tests).

---

### Phase 3 — Convert the exemplar seam: `web_research` weather (backend-worker)
Make the weather path the reference implementation of the contract.

- **MODIFY** `backend/ai/plugins/web_research.py`:
  - `_weather` returns `no_match("unresolved_location", hint=location)` instead of `None`
    when geocoding is empty; `error(...)` on forecast HTTP failure (already close); `resolved`
    with `confidence` derived from geocoder match quality on success.
  - `execute` branches on `status`: `resolved` → return; `no_match` → return the structured
    no_match to the caller (do NOT silently fall through to `_search`); `error` → return error.
  - The generic `_search` fall-through is REMOVED for weather no-match. A weather question
    with an unresolvable location must surface `no_match`, not city trivia.
- **DO NOT** add a region→city alias map. Resolution of an open vocabulary is the LLM's job
  (Phase 4), not a hardcoded dictionary.

**Gate:** new tests — `test_weather_region_returns_no_match` (asserts `status=no_match`,
`hint` present, NO Wikipedia fallback), existing weather-happy-path tests still green.

---

### Phase 4 — Escalation seam: no_match routes UP to the LLM (backend-worker)
Wire the pipeline so a tool `no_match` re-enters the semantic layer instead of being
narrated. This is where "unknown routes up" is enforced.

- **MODIFY** `backend/ai/engine/cognition/turn/runner.py` (+ tool-dispatch in
  `backend/ai/engine/agent/tools.py` as needed):
  - When a tool result is `no_match`, the drafting witness receives an explicit directive:
    *"The tool could not resolve `<hint>`. Do NOT fabricate. Either (a) normalize it to a
    concrete entity and re-call the tool, or (b) ask the user one disambiguating question."*
  - The LLM may re-call the tool with a normalized entity (open→closed), OR emit a
    clarification. It may NEVER be handed a fabricated value.
  - `IntentResolver.resolve` returning `None` is audited: distinguish "no signal, behave as
    before" (legitimate) from "didn't understand" (should escalate) — align with tri-state
    where it changes behavior; leave the legitimate no-signal path intact (minimal-fix).

**Gate:** integration test — a region weather question yields either a re-call with a
normalized city OR a clarification; it NEVER yields city-history-as-weather. Live
`qa_zone_verify.py` extended with the region case.

---

### Phase 5 — Confidence conservation surfacing (backend-worker)
Stop dropping the score. Carry input confidence to the emitted answer's provenance.

- **MODIFY** the answer/provenance assembly (`ledger` / `intent_zone` metadata path in
  `runner.py` + `engine_runtime.py`):
  - The emitted turn carries `min_confidence(inputs)` in metadata; a low value flips the
    surface into a hedge/clarify posture rather than a confident assertion.
  - Assert (in code, cheaply) `answer_confidence <= min_confidence(inputs)` — log a WARNING
    on violation (the confidence-amplifying-junction detector from the contract).

**Gate:** unit test proving a low-confidence input caps the emitted confidence; WARNING
fires on an injected violation.

---

### Phase 6 — Validation + regression net (qa-validator)
- Re-run the full `ai` suite: `pytest ai -q --ignore=ai/tests/test_store_execute.py
  --ignore=ai/tests/test_intelligence_live.py` ≥ baseline + new tests.
- Live matrix via `qa_zone_verify.py`: (a) resolvable city → live reading; (b) unresolvable
  region → clarify/normalize, never trivia; (c) genuinely-empty platform query → honest
  "nothing found" (NOT no_match); (d) tool error → reported, not substituted.
- Audit against the contract's "Detectable" grep signatures → zero conflating seams remain
  in the converted files.

**Gate (4-layer evidence):** unit + integration green; live matrix screenshots/JSON in
TASK-RESULTS; grep audit clean; confidence-conservation assertion active.

---

## DO NOT (guardrails)
- Do NOT add per-question tools or region→city alias maps (object-level; UP-0010/UP-0011).
- Do NOT let the LLM fabricate coordinates/rows/readings to cover a `no_match`.
- Do NOT collapse `empty` (genuinely zero results — must answer honestly) into `no_match`
  (didn't understand — must escalate). They are opposite signals.
- Do NOT break the legitimate `IntentResolver → None` "no signal" path (minimal-fix).
- RULE_20 (no upward imports) and RULE_21 (read-only tools) stay intact.

## Success definition
Every converted seam returns tri-state; no silent absence→answer coercion remains in the
audited files; an unresolvable entity escalates (normalize or ask) instead of hallucinating;
emitted confidence never exceeds `min(inputs)`. The weather case passes as a *side effect*
of the general fix, not as a special case.
