# ADR-0022 — Live-Data Grounding Directive + Insight Synthesis

- **Status:** Accepted
- **Date:** 2026-08-28
- **Deciders:** Master Architect

## Context

Eval and live QA surfaced two "non-intelligence" failure modes:

1. **Intent miss → parametric lecture.** "tell me more about emissions factor
   *here*?" was answered with a generic textbook definition of emission factors
   instead of the platform's live records. The S3 planner even recognised the
   system existed ("would you like me to list the active emission factors in
   your system?") but treated the host API as an optional follow-up rather than
   the answer.
2. **Retrieval → raw dump.** "what they are on the system?" correctly retrieved
   the 8 factors but presented them as a verbatim table dump including the raw
   `Source` formula text — data retrieval plus pretty-print, not reasoning.

Root cause: grounding was gated at the *wrong stage*. The synthesis stage only
fires when the draft is empty/short (`>= 300 chars → skip`), so a long-but-
ungrounded answer ships uncorrected. The grounding decision must happen at
**S3** (the tool-use decision), and the S6 synthesis must produce *insight*,
not a dump.

## Decision

1. **Live-data grounding directive (S3).** `build_chat_prompt` now appends a
   `## Live data grounding (non-negotiable)` section **derived from the
   `api_catalog`** (`_build_grounding_directive`). For every read-only (GET)
   endpoint it maps a human domain phrase to its endpoint name
   (`emission factors → list_emission_factors`), and instructs the planner that
   questions about these domains — especially with deictic cues ("here", "in the
   system", "our", "my", "what we have") — MUST be answered via `call_host_api`
   from returned data, never from parametric/texbook knowledge.

2. **Insight synthesis (S6).** `_synthesize_tool_results` system prompt rewritten:
   lead with a 1–3 sentence summary of what the data shows, compare/group/rank
   when it adds insight, omit verbose metadata (raw source strings, ids, tags),
   and use a table only when the user asked for the full list or a table
   genuinely clarifies — otherwise summarise in prose.

## Consequences

- Grounding is a property of the **catalog seam** (ADR-0017): any instance
  gains the directive from its `instance.yaml` with zero code changes.
- Live answers now read as domain insight (grouped by scope, ranked, provenance
  noted) rather than table dumps.
- Regression tests lock both behaviours in
  `ai/tests/test_prompt_rendering.py` and `ai/tests/test_tool_result_synthesis.py`.

## Files changed

- `backend/ai/engine/llm/prompts.py` — `_endpoint_to_domain_phrase`,
  `_build_grounding_directive`, injected in `build_chat_prompt`.
- `backend/ai/engine/cognition/turn/runner.py` — synthesis system prompt.
- `backend/ai/tests/test_prompt_rendering.py` — directive + phrase tests.
