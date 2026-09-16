# ADR-0033 — Pulse Identity Propagation (actor-chain attribution)

- **Status:** Accepted (ratified Pulse Master 2026-09-16)
- **Date:** 2026-09-16
- **Deciders:** Backend Worker (draft); Master Architect (ratify)
- **Area:** security | backend | cross-cutting
- **Phase:** PEC-ID-1

## Context

`engine_runtime` authenticates in-process host effects with a synthetic marker
`user_token=f"inproc:{instance_id}:{host_user_id}"`. That marker is truthy so
the plugin layer gates correctly, but it is **not** a credential: nothing is
exchanged, and PDP/audit rows historically stored only a free-text `principal`.

Enterprise bar (IBM-style): **propagate / exchange, never substitute**. Before
MCP egress expands, every boundary hop must attribute `user → engine → tool`
with stable identifiers so audit can answer "who caused this host effect?"
without changing CBAC allow/deny outcomes.

## Decision

### Phase 1 (this ADR / PEC-ID-1) — attribution only

1. **Keep** the in-process `inproc:{instance_id}:{host_user_id}` token as the
   host-executor marker. Do **not** invent a fake JWT or IdP exchange.
2. Persist an explicit **`actor_chain`** JSON list on every
   `PolicyDecisionRow` (PDP stage and grant-stage refusals):
   `[{role, id, …}, …]` ordered user → engine → tool (tool hop optional).
3. Persist stable attribution columns on the same row:
   - `host_user_id` (AppScopeMixin — acting Django user PK string)
   - `instance_id` (deployment instance, e.g. `carbon` / `nibras`)
   - `request_id` (per-effect correlation id; UUID when none supplied)
4. Attribution is **audit metadata only**. Policy matchers and Decision
   outcomes MUST ignore `actor_chain` / `request_id` / `instance_id` — CBAC
   deny/allow behaviour is unchanged.
5. Command boundary builds the chain from `Command.host_user_id`,
   `Command.instance_id`, `Command.tool`/`action`, and `Command.request_id`
   before calling PDP.

### Phase 2 (out of scope — do NOT implement here)

Short-lived scoped host credential and/or external IdP / OAuth token exchange
for MCP egress. Phase 1 rows and chain shape are the audit contract Phase 2
must extend, not replace.

## Alternatives Considered

- **Substitute a synthetic JWT for `user_token` now** — rejected: looks like
  auth but is not exchanged; invites false security assumptions.
- **Stuff attribution only into `process_state`** — rejected: pollutes PDP
  matcher input and is harder to query for audit.
- **Full OAuth exchange in Phase 1** — rejected: blocked until MCP egress
  design; ADR marks it Phase 2 only.

## Consequences

- **Positive:** Every host-effect PDP/grant row is attributable without
  changing authorization semantics.
- **Positive:** Ready for MCP egress audit (Phase 2 can mint/exchange without
  rewriting the ledger shape).
- **Negative / trade-off:** Extra JSON + columns on `PolicyDecisionRow`;
  callers should pass `instance_id` / `host_user_id` / `request_id` on
  `Command` (boundary generates `request_id` if missing).
- **Do NOT re-try:** Treating `inproc:…` as a real bearer credential; driving
  CBAC decisions from `actor_chain`.

## References

- TASKS.md Phase PEC-ID-1
- `backend/ai/engine_runtime.py` (`user_token=inproc:…`)
- `backend/ai/models/pdp.py` (`PolicyDecisionRow`)
- `backend/ai/command_boundary.py`, `backend/ai/pdp.py`, `backend/ai/grant.py`
- `.ai-toolkit/shared/security.md` §10 (AI audit trail)
