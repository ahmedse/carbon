# ADR 0053 — No masking fallbacks; follow-ups answer from the last view

- **Status:** Proposed
- **Date:** 2026-09-25
- **Deciders:** Master Architect
- **Area:** backend

## Context

Conversation `c5801082` (2026-09-24 22:37): "summary report with pie charts", then "i told you pie", then "what ?". Every turn re-ran the same three reads and returned the same fixed text, "Live data summary". Three separate masks produced that:

- The v21 read path had no answer writer. When no restater covered the rows, a fixed template spoke for every message.
- The host sent "99.8% of employees have no 'gender' recorded". It was a string, the envelope kept only dict caveats, and the warning was dropped with no trace.
- When a stage failed, the turn fell back to another path that looked like a normal answer. The user could not tell Pulse had failed.

A fallback that looks like an answer hides the defect and makes Pulse look stupid. A visible, typed error is better.

## Decision

1. **Degradation is typed and visible.** A stage that fails records `Degradation(stage, cause)` on the turn and says so to the user in one sentence (English or Arabic), plus an envelope caveat. Data that is still exact (tables and charts computed from host rows) may be shown. Text that impersonates an answer may not.
2. **v21 does not fall through on failure.** Under `PULSE_UNDERSTAND=v21`, a malformed Decision or an act error returns a typed error reply. A failed model call (an exception) propagates, so the dispatcher's existing fail-visible status (`pulse_unavailable` / `failed`) reports the outage. The legacy spine stays reachable only through the explicit kill switch `PULSE_UNDERSTAND=legacy`, and for Decisions whose op the legacy spine owns (`answer`, `navigate`). Test stubs answer `emit_decision` the way a model does (`ai/tests/pv21_stub.py`) rather than relying on the fallthrough.
3. **The answer writer is strict.** `synthesize_envelope(strict=True)` raises `EnvelopeWriteError(cause)` (`model_error`, `empty_output`, `invalid_output`) instead of returning the template. A reply whose every sentence cites a number that is not in the payload fails with `ungrounded`.
4. **Host facts are never dropped for their shape.** A caveat reaches the envelope whether the host sent a string or `{level, text}`.
5. **Follow-ups answer from the last view.** The blocks of the last read turn (tables and charts, already aggregated and sanitized, capped in size) are typed state: `ConversationState.last_view`. The state block names it. A `continue` Decision renders from it and makes no host read. A new `call_tool` still reads the host.
6. **Cost is stated.** An unrestated read turn makes one `draft` call to write the reply. Restated (bound) reads make none.

Data gaps are reported, not filled. Pulse does not write inferred values (for example gender from a name) into master data. A name does not establish gender, and the value is a personal record under HR's authority. A host-side review list for HR is possible. Pulse writing the value is not.

## Alternatives Considered

- **Keep the template as a safety net** — rejected. It looks like an answer and hides the failure.
- **Phrase rules for "what", "again", "pie"** — rejected. The chart shape is a typed Decision field, and continuity is typed state.
- **Cache raw host payloads in state** — rejected. Raw rows can carry personal fields. The aggregated view is enough to re-render.

## Consequences

- **Positive:** A failure is visible the turn it happens. Follow-ups cost no host reads. The data-quality warning reaches the user.
- **Negative / trade-off:** A model outage shows an error instead of a plausible answer. One extra model call per unrestated read turn.
- **Do NOT re-try:** Returning a canned "summary" when the writer fails. Silently re-routing a failed v21 turn to the legacy spine.

## References

- ADR-0046 · ADR-0047 · ADR-0049 · ADR-0050
- `backend/ai/engine/cognition/turn/degradation.py`, `turn/pipeline_v21.py`, `cognition/state_store.py`, `ai/envelope_service.py`
