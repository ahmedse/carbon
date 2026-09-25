# ADR 0054 — Reasoning channel (pillar B, H2)

- **Status:** Proposed
- **Date:** 2026-09-25
- **Deciders:** Master Architect
- **Area:** backend

## Context

The thinking timeline shows stage labels ("Composing response…"). A draft can stream and then be replaced with no record of what was shown or why. Provider thinking is off for every call. Pillar B asks for four typed layers on the same panel, with employee text scrubbed and the ledger keeping the unshown pieces.

## Decision

1. **Rationale is the Decision reason.** The understand call already emits `reason`. That sentence is the turn rationale. It is scrubbed and shown. No second model call.
2. **A step says what it is waiting on.** An Agent step's narration is its intent plus the dependency ids that have not finished. It is built from the step record, not from a model call.
3. **Provider reasoning is state-gated, with a client opt-in.** Thinking is
   enabled on the understand call when conversation state already says so:
   intent confidence below 0.6, the previous turn recorded a degradation, or
   the open question kind is `correct_previous`. The Pulse status-bar
   **Think** switch (everyone, default off) sets `dense_thinking` on the
   request and widens that budget for the turn; scrub still drops fences,
   backticks, and `call_` tokens, but keeps more sentences. No keyword match.
4. **A replacement is a revision.** When the reply text differs from text already produced for the same turn, the reply carries `{shown, reason}`. The ledger row `reasoning` stores rationale, summary, draft, and revision reason. The draft row stores the draft text, not only its length.
5. **The rationale survives the turn.** Scrubbed lines and the revision are saved on the assistant message and restored into the thinking timeline on reload. `ai/eval/reasoning_bank.yaml` checks both: a tool answer with a reason keeps it, and only a real replacement produces a revision.
6. **Scrub is structural.** Fenced blocks, backtick spans, and `call_` tokens are removed. The scrub does not decide a route.
7. **The panel reads top-down.** A v21 turn narrates the rationale first, then one line per distinct host read, each naming its target. Identical reads are one read, so they are narrated once. The collapsed header states the cost of the turn — elapsed seconds and the number of lines — taken from the duration already persisted with the message. Narration is best-effort: a progress channel that raises never fails the turn.

## Alternatives Considered

- **A reasoning model call on every turn** — rejected. The rationale is already in the understand call.
- **Keyword triggers ("why", "wrong")** — rejected. The budget reads typed state.
- **Leave the silent overwrite** — rejected. It is incident I-2.

## Consequences

- **Positive:** Every v21 answer can show why. A replaced draft is auditable. Thinking cost is limited to turns the state already marked.
- **Negative / trade-off:** Turns under the budget are slower on providers that honour thinking. Corrections are budgeted only once `open_question.kind` is `correct_previous` (H1).
- **Do NOT re-try:** A phrase list that turns thinking on. A second model call whose only job is the rationale.

## References

- ADR-0049 · ADR-0053 · pillar B on the Pulse 2.1 canvas
- `backend/ai/engine/cognition/turn/reasoning.py`
- `backend/ai/tests/test_v21_turn_narration.py` · `carbon-frontend/src/shell/__tests__/AIWorkingIndicator.test.jsx`
