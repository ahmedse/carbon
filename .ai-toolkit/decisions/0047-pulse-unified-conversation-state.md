# ADR-0047 — Pulse v2: unified ConversationState, ContextPack and one decision per turn

- **Status:** Proposed
- **Date:** 2026-09-22
- **Deciders:** Master Architect (Pulse seat) + Nibras QA
- **Area:** cross-cutting (Pulse engine · Chat/Agent continuity · eval gates)
- **Extends:** ADR-0014 (Chat/Agent split), ADR-0043 (Agent cockpit), ADR-0046 (Chat never stages host writes),
  RULE_21, RULE_23, QA bank **G2**
- **Plan:** `docs/pulse/PULSE-V2-INTELLIGENCE-CONTRACT.md`

## Context

Live Nibras QA (`emp_1067`) reports Pulse as "not intelligent, not smooth, out of context". An audit of
`backend/ai` on 2026-09-22 traced this to architecture, not to the model:

1. Chat history is the last **8** messages, `role`+`content` only; tool results never re-enter context
   (`intelligence.py:416-423`, `context_assembler.py:173`).
2. `memory_manager` is not passed to `TurnPipelineRunner` in `_run_chat`; retrieval defaults to
   "No memories available." (`engine_runtime.py:181-188`, `retrieve.py:103,138`).
3. No durable working state — Redis focus stack + pending-confirm only; `ConversationContextRecord` unused.
4. Agent Run builds its own prompt with no `conversation_history` (`plans_service.py:3887, 3991`);
   Chat has no view of running plans.
5. ≥12 routers/classifiers applied in code order with no arbitration; ≥8 stage prompts with no shared identity.
6. Chat grounding prompt says "CALL THE TOOL" for writes while `chat_surface_hook` cancels them and the
   runtime replaces the answer (`runner.py:2604-2610`, `guardrails.py:161-199`, `engine_runtime.py:205-230`).
7. LLM draft/observe runs for fully bound `process_dial` steps; up to 6–10 LLM calls per Chat turn.
8. CI evals measure grounding/deny/fabrication only; nothing multi-turn.

## Decision

Pulse v2 adopts an explicit **Intelligence Contract** with measurable objectives per surface
(Chat C1–C10, Agent A1–A10) and the following architectural commitments:

| Commitment | Rule |
|---|---|
| **ConversationState** | One durable, RBAC-scoped, versioned state per conversation (focus, intent, slots, open question, last tool digests, active plans, decisions, language) in `ConversationContextRecord.session_json`, mirrored to Redis. Loaded on every Chat turn and every Agent discovery/run. |
| **ContextPack + IdentityBlock** | Every LLM call in Chat or Agent receives the same pack: identity (persona, date, user, language, surface, autonomy rules), state, history **with tool digests**, knowledge/memory, and a stage-specific task block. No stage may define its own identity. |
| **Arbiter → TurnDecision** | Existing gates (topic guard, nav, process brief, salience, deixis, intent, weather, skills, chat surface) become signal producers. One deterministic, logged `TurnDecision` per turn. Early `return`s from gates are forbidden. |
| **Deterministic-first** | A `process_dial` step with complete `write_slots` executes bind → stage → consent → commit with **zero** draft/observe LLM calls. |
| **Surface-truthful prompts** | Chat prompts describe Chat's real capabilities (advise, draft, explain, hand off). The model produces the handoff; the runtime never replaces model text post-hoc except as a logged fallback. |
| **Cross-surface continuity** | Agent discovery/run inherit `ConversationState`; plan lifecycle writes `active_plans` back; Chat answers plan status from state. |
| **Coherence eval gate** | A multi-turn golden bank (continuity, slot carry-over, router agreement, latency, LLM-call budget) runs in CI as a blocking gate — QA bank **G5 — Coherence**. |

## What this ADR does NOT change

- ADR-0046 / G2: Chat still never stages or executes host mutations. Continuity does not create a new write path.
- RULE_21: Agent host effects still require staged consent.
- No model swap is accepted as the remedy for any objective.

## Consequences

**Positive:** Pulse remembers the conversation, speaks with one voice, decides once per turn, executes bound
processes without narration latency, and Chat/Agent behave as one coworker. Regressions become measurable.

**Negative / cost:** Larger refactor of `turn/runner.py` (Arbiter); prompt refactor across ≥8 stages; new
state store and eval runner; ~7–10 weeks across P0–P6.

**Risks:** Arbiter behavior change (mitigated by shadow mode + `PULSE_ARBITER=legacy` kill switch);
PII in state/digests (mitigated by RBAC-scoped construction and tenancy tests); context growth
(mitigated by hard budgets).

## Compliance checks

- Static test: every `route_chat(...)` system prompt originates from `build_context_pack`.
- `llm_calls == 0` tests for bound loan/leave/attendance steps.
- Decision log present on 100% of turns.
- Multi-turn bank thresholds (see plan §3) enforced in CI at pass^k = 3.

## Agent rules (for AI coworkers editing Pulse)

1. Do not add a new early-exit gate in `turn/runner.py`; add a signal to the Arbiter.
2. Do not add a stage-local system prompt; add a `TaskBlock` to `context_pack.py`.
3. Do not call the LLM for a `process_dial` step whose slots are complete.
4. Do not "fix" Chat by enabling Confirm for `call_host_api` (ADR-0046).
5. Any change touching history, state, or routing must add or update a multi-turn golden.
