# ADR 0058 — Catalog request write is the remaining effect

- **Status:** Proposed
- **Date:** 2026-09-25
- **Deciders:** Master Architect
- **Area:** backend

## Context

ADR-0057 blocks Create when a plan claims fields no catalog entry declares. The honest leftover was a Chat sentence ("contact admin"). That is not a product path: Chat cannot host-mutate (ADR-0046), and the host already has Correspondence for a typed request.

## Decision

A catalog entry with `kind: request` is the remaining effect when `output_fit` blocks. The contract appends that write (findings + brief in the body). Create is allowed because the stored plan's effect is the request, not the missing file.

Chat proposes. Agent Approve + Run + RULE_21 confirm, or the Correspondence UI, submits. The host defaults `org_unit` from the actor's employee profile so the write does not invent a unit.

No engine "contact admin" sentence. No People salary GET in this change.

## Alternatives Considered

- **A Chat refusal that names an admin** — rejected. It is prose, not a host write, and Chat cannot submit.
- **Add the aggregate GET first** — rejected. Honesty is still the proof; the GET stays Wave B.

## Consequences

- **Positive:** The user can store a plan whose only write is a request the catalog declared.
- **Negative / trade-off:** A pack without a `kind: request` entry still blocks Create (ADR-0057 unchanged).
- **Do NOT re-try:** Teaching Chat to POST, or a phrase list that detects one report.

## References

- `backend/ai/engine/cognition/plan/contract.py` `offer_request_write`
- ADR-0046 · ADR-0050 · ADR-0057 · ADR-0030
