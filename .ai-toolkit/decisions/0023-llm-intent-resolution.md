# ADR-0023 — LLM-Driven Intent Resolution (S1.5)

- **Status:** Accepted
- **Date:** 2026-08-28
- **Deciders:** Master Architect

## Context

ADR-0022 fixed *grounding* (answer from real data, synthesise insight) but the
recognition of *which* endpoint the user is after was still a prompt-level hint
plus the S3 planner's best guess. The remaining failure modes:

- **Regex isn't intent.** `salience.py` is a lexical cost-gate and
  `trajectory._INTENT_RULES` is a post-hoc label — neither can tell that
  "emission factors?", "what emission factors do we have here?" and "our EF
  list" all mean `list_emission_factors`, or that "what are *they* on the
  system?" refers back to the previous turn.
- **One-to-one keyword maps don't scale.** Hardcoding phrase→endpoint pairs is
  exactly the per-instance coupling ADR-0017 was created to remove.

User directive: **no local models — use LLMs.**

## Decision

Add an **S1.5 Intent Resolution** stage: an LLM-as-classifier that maps the
user's message onto the instance's **closed label set** — the read-only (GET)
endpoints declared in `instance.yaml` `api_catalog` — and returns structured
JSON, then a deterministic **confidence ladder** turns that into behaviour.

1. **LLM-as-classifier.** `IntentResolver` (in
   `ai/engine/cognition/turn/intent.py`) calls `route_chat(task="introspect",
   response_format={"type":"json_object"}, temperature=0)`. This uses the
   existing JSON-mode seam and the cheap `introspect` task lane — **no local
   models, no new provider, no new dependencies**. Only GET endpoints are in
   the label set, so intent resolution can never select a mutating tool.

2. **Catalog-derived label set.** The prompt enumerates each GET endpoint's
   name + human phrase (`list_emission_factors` → "emission factors") +
   description, derived from `api_catalog` (ADR-0017). A new instance gains
   intent resolution with zero code changes.

3. **Confidence ladder** (enforced deterministically *after* parsing, so a
   weak/garbage answer is never trusted):
   - `answer` — one endpoint clears both thresholds (`min_confidence`,
     `ambiguity_gap`) → the runner **injects the matched tool into S3** so the
     planner *confirms* the call instead of lecturing.
   - `disambiguate` — 2+ endpoints within the gap → the runner returns a short
     human options list (not endpoint names).
   - `clarify` — top confidence below threshold → the runner asks one question.
   - greeting / general knowledge → `answer` with no candidate, no host call.

4. **Graceful degradation.** Empty catalog, unparseable JSON, or an LLM error
   all return `None` and the pipeline continues exactly as before — intent
   resolution can never break a turn.

## Consequences

- One extra `introspect` LLM call per turn (bounded by the cheap lane). Gated by
  `INTENT_RESOLVER_ENABLED`; model overridable via `INTENT_RESOLVER_MODEL`.
- Candidate names are validated against the closed set, so a hallucinated tool
  name is stripped rather than executed.
- The ladder is the "ask / guess-with-options / answer" mechanism the user asked
  for, but grounded in confidence rather than ad-hoc heuristics. Its outcomes
  are written to `turn_ledger` (stage `intent`) so the P4.2 consolidation sweep
  can later learn "these phrasings → this endpoint" from real traffic instead of
  from rules.

## Files changed

- `backend/ai/engine/cognition/turn/intent.py` — `IntentResolver`,
  `IntentResolution`, `_apply_ladder`.
- `backend/ai/engine/cognition/turn/runner.py` — S1.5 stage, short-circuit
  returns, S3 tool injection.
- `backend/ai/engine/core/config.py` — `INTENT_RESOLVER_*` settings.
- `backend/ai/tests/test_intent_resolver.py` — 18 regression tests.
