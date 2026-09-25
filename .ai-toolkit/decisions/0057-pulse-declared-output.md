# ADR 0057 — Declared output is the only success

- **Status:** Proposed
- **Date:** 2026-09-25
- **Deciders:** Master Architect
- **Area:** backend

## Context

Runs `dbe99353` and `b040714a` shipped a file for a report no catalog entry can produce. ADR-0052 I1 treated a catalog name as a capability. The loop then invented a `structured_synthesis` result so export could fire, ignored a bind spec sitting on a query key, and counted a failed step as done.

## Decision

I1 is output-fit. A step that claims `columns` or `produces` is capable only when those names are in `returns` on a catalog entry that step or its dependencies call. Otherwise the finding is `output_fit`, the step is a gap, and an export is not a call.

The same contract already runs inside planning. The proposal the user reviews carries those findings.

The loop does not invent a tool result for a tool-less step. The contract does not add or retarget an export because the brief said Excel. An export that names no columns is a gap when no dependency declares `returns`. A `{step, field}` object is a bind on a query key the same way it is on a path key. A review step keeps its draft; observe does not replace the verdict. `completed_ids` grows only when the step has no error, veto, or failure class.

No new host GET in this change. A later catalog line with `returns` covering the claimed fields is what makes the same brief succeed. When output-fit blocks, a catalog `kind: request` write (ADR-0058) is the remaining effect — not a "contact admin" sentence.

## Alternatives Considered

- **A salary-report sentence in the engine** — rejected. The finding names the missing fields. The client paints it.
- **Add the aggregate GET first** — rejected. That hides the lie. Honesty is the proof; the GET comes after.

## Consequences

- **Positive:** A plan that claims fields the catalog does not declare is blocked before Create task, with no file.
- **Negative / trade-off:** An export that names columns must have those columns on `returns`. An export that names no columns is unchanged.
- **Do NOT re-try:** Stuffing a table so a file exists, or a phrase list that detects one report.

## References

- `backend/ai/engine/cognition/plan/contract.py` `output_fit_findings`
- ADR-0052 · ADR-0053 · ADR-0055
- `docs/pulse/PULSE-DECLARED-OUTPUT-PLAN.md`
