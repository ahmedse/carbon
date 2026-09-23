# Pulse v2 — Intelligence Contract & Phased Plan

- **Status:** Proposed (companion to ADR-0047)
- **Date:** 2026-09-22
- **Area:** cross-cutting — `backend/ai/engine/*`, `plans_service.py`, `engine_runtime.py`, `intelligence.py`, `ai/eval`, Pulse UI
- **Extends:** ADR-0014 (Chat/Agent split), ADR-0043 (Agent cockpit), ADR-0046 (Chat no host mutation), RULE_21, RULE_23, QA bank G2
- **Does not change:** the Chat/Agent trust contract. Chat stays advisory; all host writes stay on Agent Run consent or host UI.
- **Canvas:** `pulse-v2-intelligence-objectives.canvas.tsx` (Cursor canvases folder)

## 0. Executive summary

Pulse today is safe and grounded but not *coherent*. Users experience it as forgetful, inconsistent and slow because the engine is a pipeline of independent gates and prompts with no shared state — not a single agent with a memory. v2 keeps every safety property (G2, RULE_21, fabrication = 0, topic guard) and adds what makes Cursor-class agents feel intelligent: **one durable conversation state, one identity, one arbitrated decision per turn, full context (including tool results) in every LLM stage, continuity between Chat and Agent, and evals that measure exactly that.**

Seven phases (P0–P6), each independently shippable and gated by measurable acceptance criteria. P1–P3 remove most of the user-visible "out of context" behavior; P4–P6 make it stay fixed.

## 1. Findings this plan resolves

| # | Finding | Evidence | User symptom |
|---|---|---|---|
| F1 | History = last 8 messages, `role`+`content` only; tool results never re-enter context | `intelligence.py:416-423`, `context_assembler.py:173` | "It forgot what it just looked up" |
| F2 | `memory_manager` not passed to `TurnPipelineRunner` in chat → retrieval sees "No memories available." | `engine_runtime.py:181-188`, `retrieve.py:103,138` | Learned facts not used |
| F3 | No durable per-conversation working state (intent, slots, focus, open question, active plans). Redis focus stack (max 5) + pending-confirm only; `ConversationContextRecord` unused | `memory/working.py`, `models/core.py:219` | Re-asks questions; loses the thread |
| F4 | Agent Run gets its own prompt and no `conversation_history`; Chat has no view of running plans | `plans_service.py:3887, 3991` | "Plan ignores what we discussed" |
| F5 | ≥12 routers/classifiers (regex + LLM) applied in code order, no arbitration | `runner.py:1400-2051, 2987-3036`, `salience.py`, `intent.py`, `scope_route` | Same sentence → different behavior |
| F6 | ≥8 distinct system prompts; only draft gets persona + date + user | `critic.py:39`, `runner.py:1130`, `plans_service.py:2434`, `planner.py:138`, `loop.py:2312` | Tone drift, asks for known facts (date) |
| F7 | Chat prompt says "CALL THE TOOL" for writes; `chat_surface_hook` cancels them; runtime replaces the answer | `runner.py:2604-2610`, `guardrails.py:161-199`, `engine_runtime.py:205-230` | Wasted LLM call, reply ≠ reasoning |
| F8 | LLM invoked for fully bound `process_dial` steps; grounded slots not passed to LLM | `cognition/plan/loop.py` observe/draft path | ~10 s latency per plan, contradictory narration |
| F9 | Eval harness measures grounding/deny/fabrication only; nothing multi-turn | `ai/eval/run_harness.py`, CI | Coherence regressions unnoticed |
| F10 | Up to 6–10 LLM calls per turn (intent, rerank, draft, critic, escalate, synthesis, verify) | engine audit | "Not smooth" |

## 2. Intelligence maturity ladder

| Level | Name | What the user experiences | Today |
|---|---|---|---|
| L0 | Safe | Never fabricates, never writes without consent, refuses off-limits | Reached |
| L1 | Grounded | Answers from data/knowledge with citations | Reached |
| L2 | Continuous | Remembers this conversation: entities, results, decisions, open questions | **Not reached — v2** |
| L3 | Coherent | One voice, one decision per turn, same behavior for same intent | **Not reached — v2** |
| L4 | Proactive | Anticipates the next step, tracks state across surfaces | Partial — v2 for ESS |
| L5 | Autonomous within consent | Bound multi-step processes with 0 unnecessary LLM calls; pauses only for real decisions | **Not reached — v2** |

v2 exit criterion: L2, L3, L5 fully reached; L4 for the ESS journeys (loan, leave, attendance).

## 3. Intelligence Contract — objectives Pulse MUST reach

Each objective has a definition, a metric and a CI gate. Nothing ships in v2 without moving a metric.

### 3.1 Chat (advisory surface — ADR-0046)

| ID | Objective | Pulse MUST | Measurable goal | Closes | Phase |
|---|---|---|---|---|---|
| C1 | Continuity | Resolve any entity/number/decision from turns 1..N-1 at turn N | Focus retention ≥ 95% on 10-turn scripts | F1, F3 | P1 |
| C2 | Grounded recall | Keep tool results available verbatim (compact digest) to later turns | "What was the X you found?" answered from digest 100% | F1 | P1 |
| C3 | Slot memory | Never re-ask a slot the user already gave (AR/EN) | Slot carry-over ≥ 95% | F3 | P1 |
| C4 | One decision per turn | Routers are signals; one Arbiter picks one logged `TurnDecision` | Decision log on 100% turns; router agreement ≥ 98% | F5 | P4 |
| C5 | Truthful surface | Be told its real capabilities (advise, draft, explain, hand off); answer never replaced post-hoc | 0 post-hoc text overrides on write-intent goldens | F7 | P3 |
| C6 | Identity constancy | Same persona, date, user, language in every LLM stage | 0 "what is today's date"-class failures | F6 | P2 |
| C7 | Language fidelity | Reply language = user language, incl. critic and synthesis | Language golden 100% | F6 | P2 |
| C8 | Latency | Simple turn ≤ 2 LLM calls; nav/FAQ/status 0 LLM calls | p50 ≤ 4 s; ledger histogram gated in CI | F10 | P3 |
| C9 | Plan awareness | Answer "status of my request?" from `active_plans` state | 100% from state, 0 LLM calls | F4 | P5 |
| C10 | Memory use | Apply a confirmed `learn_fact` in the same and later conversations | learn_fact turn-1 → applied turn-3 test green | F2 | P1 |

### 3.2 Agent (execution surface — RULE_21)

| ID | Objective | Pulse MUST | Measurable goal | Closes | Phase |
|---|---|---|---|---|---|
| A1 | Inherit context | Discovery and Run receive Chat `ConversationState` (slots, results, focus) | Brief enrichment 100% on Chat→Agent goldens | F4 | P5 |
| A2 | Deterministic-first | Bound `process_dial` step executes with no draft/observe LLM call | 0 LLM calls per bound step; ≤ 1 per bound plan | F8, F10 | P3 |
| A3 | Honest effect | Every Approve commits or fails visibly with a next action | 0 silent re-pauses (delivered; regression gate) | — | done |
| A4 | Right questions only | Discovery asks only for missing required slots | 0 redundant clarifications on ESS goldens | F3, F8 | P3 |
| A5 | Plan legibility | Each step states what it will do with which bound values, in the user's language, before consent | QA review 100% legible (G5) | F6, F8 | P2 |
| A6 | Progress reporting | Step transitions surfaced promptly; no dead time between pause and drawer | Visible ≤ 1 s; no polling gap > 2 s | F10 | P3 |
| A7 | Recovery | Dead staged execution → inline re-stage or visible failure with Decline/re-run/My | Recovery goldens 100% (delivered) | — | done |
| A8 | Cross-surface write-back | Plan lifecycle updates conversation state | `active_plans` reflects created/paused/completed/failed 100% | F4 | P5 |
| A9 | Latency | Discovery → approve → commit feels like one action | p50 ≤ 6 s excluding human approval | F8, F10 | P3 |
| A10 | Consistency | Same brief → same plan shape | pass^k = 3 identical plan fingerprints | F5 | P4 |

## 4. Target architecture

### 4.1 One turn owner

```
TurnCoordinator (new)
  ├─ load ConversationState (durable) + IdentityBlock
  ├─ Arbiter → TurnDecision (answer | clarify | navigate | handoff_agent |
  │            process_brief | memory_confirm | plan_status | refuse)
  │            ← every existing gate becomes a signal producer
  ├─ ContextPack builder → same pack for every LLM stage
  ├─ execute decision (draft / critic / tools as advisors, not exits)
  ├─ persist ConversationState delta + TurnDecision log
  └─ emit response + ledger
```

Gates (topic guard, deixis, nav, process_brief, salience, intent, weather, skill router, chat surface) stop being early `return`s and become **signal producers** consumed by one deterministic `Arbiter` (ranked rules + confidence tie-break), fully logged and unit-tested per conflict pair.

### 4.2 ConversationState (durable)

Stored in `ConversationContextRecord.session_json` (exists, per-conversation PK), mirrored to Redis. Schema v1:

```json
{
  "version": 1,
  "focus": [{"type": "employee", "id": "1067", "label": "…", "turn": 7}],
  "intent": {"zone": "ess", "action": "loan.request", "confidence": 0.92, "since_turn": 5},
  "slots": {"loan_type": "emergency", "amount": 5000, "reason": null},
  "open_question": {"slot": "reason", "asked_turn": 8, "text": "…"},
  "last_results": [
    {"turn": 6, "tool": "call_host_api", "api": "get_my_loan_eligibility",
     "digest": "eligible=true, max=8000 SAR, active_loans=0", "ref": "trace:…"}
  ],
  "active_plans": [{"plan_id": "…", "status": "paused", "title": "Emergency loan"}],
  "decisions": [{"turn": 7, "decision": "clarify", "why": "slot reason missing"}],
  "language": "ar",
  "surface_last": "chat"
}
```

Rules: bounded lists; redacted per RBAC scope on load; cleared on explicit clear/new-topic (existing `_snapshot_with_clear_break` semantics); versioned.

### 4.3 ContextPack

Single builder producing the same structure for **every** LLM call in a turn or plan step:

1. `IdentityBlock` — persona (instance.yaml), today's date + timezone, user (name, role, employee_no), language, surface (`chat` | `agent_plan` | `agent_discovery`), autonomy rules for that surface (Chat = advise + handoff; Agent = stage with consent).
2. `StateBlock` — rendered `ConversationState`.
3. `HistoryBlock` — last 8 messages + compaction summary, **plus** per-message tool digests.
4. `KnowledgeBlock` / `MemoryBlock` — T3/T4 as today, with `memory_manager` wired.
5. `TaskBlock` — stage-specific instruction (draft / critic / observe / synthesise / plan).

Stage prompts become `TaskBlock` only; no stage may define its own identity.

### 4.4 Deterministic-first process steps

When `write_slots` are complete: bind → stage → consent → commit with **no** draft/observe LLM call. LLM only for (a) missing-slot clarification wording, (b) optional final polish — both receive `StateBlock`.

### 4.5 Cross-surface continuity

- Discovery and `_execute_plan_once` receive `ContextPack(surface="agent_*")` from the **same** `ConversationState`; brief enriched with slots + last_results before planning.
- Plan lifecycle writes `active_plans` back; Chat Arbiter's `plan_status` decision answers from state, 0 LLM.

### 4.6 Truthful Chat prompt

Replace the "CALL THE TOOL" grounding block with a surface-aware block: on Chat the model is told writes happen via Agent/My and produces the handoff itself (structured `handoff` field), so `engine_runtime` no longer overwrites text. On Agent the block stays. ADR-0046 remains the contract; this removes the contradiction, not the rule.

## 5. Phased plan

### P0 — Instrumentation & baseline (1 week, low risk)

- `llm_calls`, `llm_ms`, `stage` in turn `ledger` and plan `StepJournal`; exposed in `/ai/telemetry`.
- `TurnDecisionLog` (log-only) recording which gates fired and which won.
- First multi-turn golden bank `ai/eval/goldens/multiturn/*.yaml`: 12 scripts × 8–12 turns (ESS loan/leave/attendance, payroll follow-ups, focus switching, AR/EN mixing, Chat→Agent handoff, "what did you find earlier", "status of my request").
- Baseline report committed; CI runs the bank report-only.

**Touchpoints:** `turn/runner.py` (ledger), `plan/loop.py`, `ai/eval/run_harness.py`, new `ai/eval/multiturn_runner.py`.

### P1 — Durable ConversationState + tool recall (2 weeks, medium risk) → C1, C2, C3, C10

- `ConversationState` dataclass + `ConversationStateStore` (Django `ConversationContextRecord` + Redis mirror) with load/save/redact/clear and v1 migration.
- Populate from existing signals: focus (`WorkingMemory`), intent (IntentResolver), slots (`process_brief`/`write_slots`), `last_results` digests (`tool_trace`), `open_question` (clarify policy).
- `assemble_context` appends per-message tool digests (≤ 200 chars, RBAC-scoped).
- `memory_manager=MemoryManager(db)` wired into `TurnPipelineRunner` in `_run_chat`; regression test for `learn_fact` recall.
- `StateBlock` rendered into the draft prompt.

**Touchpoints:** new `engine/cognition/state_store.py`, `context_assembler.py`, `intelligence.py:416-430`, `engine_runtime.py:181-203`, `turn/draft.py`, `memory/working.py`.
**Acceptance:** C1 ≥ 90%, C2 100%; `learn_fact` test green; no fabrication regression.
**Mitigation:** hard context budgets; digests built through retrieval RBAC scope.

### P2 — IdentityBlock + ContextPack for every stage (1.5 weeks, medium risk) → C6, C7, A5

- `engine/cognition/context_pack.py`: `IdentityBlock`, `build_context_pack(state, surface, stage)`.
- Refactor `build_chat_prompt`, `CRITIC_SYSTEM_PROMPT`, tool-synthesis, IntentResolver, discovery, planner decompose, observe, plan synthesise to consume the pack.
- Static test: every `route_chat` system prompt originates from `build_context_pack`.

**Touchpoints:** `prompts.py`, `turn/critic.py`, `turn/intent.py`, `turn/runner.py:1130-1162, 2534-2698`, `plans_service.py:2434-2457, 3887`, `plan/planner.py`, `plan/loop.py:2312-2337, 2957-2988`.
**Acceptance:** static test green; C7 100%; date-class goldens 0 failures; existing harness pass^k = 3.

### P3 — Deterministic-first steps + truthful Chat prompt (1.5 weeks, medium risk) → C5, C8, A2, A4, A6, A9

- `ReActLoop`: bound `process_dial` steps skip draft/observe; summary from deterministic inline-commit templates (AR/EN, QA-reviewed).
- `llm_calls == 0` tests for bound loan/leave/attendance steps.
- Surface-aware grounding block; model emits structured `handoff`; `_should_force_action` becomes a logged fallback (target 0 on goldens).
- Discovery: no LLM on `scope_route` short-circuit; `StateBlock` otherwise so it never re-asks known slots.

**Touchpoints:** `plan/loop.py`, `plan/export_bind.py`, `turn/runner.py:2596-2615`, `engine_runtime.py:205-230`, `plans_service.start_discovery`.
**Acceptance:** A2 0 LLM calls; A9 p50 ≤ 6 s; C8 ≤ 2 LLM calls; C5 0 overrides; G2 bank + `test_plans.py` green.

### P4 — Arbiter: one decision per turn (2 weeks, high risk) → C4, A10

- `TurnDecision` enum + `Arbiter.decide(signals)` with documented precedence (safety refusals > pending memory confirm > explicit process brief > navigation > deixis/clarify > intent zone > default answer).
- Convert early-exit gates in `runner.py:1400-2051` into signal producers; runner executes only the Arbiter's decision.
- Decisions persisted in `ConversationState.decisions` and ledger; conflict-pair unit tests.
- Shadow mode for one week (log legacy vs Arbiter disagreement) before flipping; `PULSE_ARBITER=legacy` kill switch for one release.

**Touchpoints:** new `turn/arbiter.py`, `runner.py`, `salience.py`, `intent.py`, `navigation.py`, `process_brief.py`, `chat_surface.py`.
**Acceptance:** decision log on 100% turns; router agreement ≥ 98%; zero regressions at pass^k = 3.

### P5 — Chat ↔ Agent continuity (1.5 weeks, medium risk) → C9, A1, A8

- `start_discovery` and `_execute_plan_once` build `ContextPack(surface="agent_*")` from `ConversationState`; brief enriched with slots and result digests.
- Plan lifecycle events update `active_plans`.
- Chat `plan_status` decision answered from state + `RunStep` rows.
- UI: Active-plans chip in Chat; inherited-context panel in Run drawer (RULE_23 wording).

**Touchpoints:** `plans_service.py`, `state_store.py`, Pulse frontend chat/agent components.
**Acceptance:** A1 100%; PC-090/091/350 and PA-* still green; tenancy test for state isolation.

### P6 — Evaluation as a gate + hardening (1 week, low risk)

- Multi-turn bank blocking in CI with §3 thresholds; `latency_budget` and `llm_calls` regression gates.
- Nightly live smoke on Nibras dev (`emp_1067`) for the three ESS journeys Chat→Agent→Approve, asserting host rows + IC metrics.
- ADR-0047 accepted; QA bank gate **G5 — Coherence**; `.cursor/rules/pulse-intelligence-contract.mdc`.

### QA bank G5 — Coherence (PV2-6A)

Offline CI step: `python -m ai.eval.multiturn.runner --gate`. Fails the build when any threshold misses. Stub advances **per script turn**, not per LLM call.

| Metric | Gate | Contract |
|---|---|---|
| `router_agreement` | ≥ 0.90 | C4 (shadow); 0.98 target is P4 flip) |
| `slot_carry_over` | = 1.0 | C3 |
| `llm_calls_p50` | ≤ 2 | C8 after P3 |
| `turns_over_budget` / simple turns (`max_llm_calls ≥ 1`) | ≤ 10% | C8 simple-turn ≤ 2. 0-LLM (nav/status) misses stay visible in the raw count, not this ratio. |

## 6. Sequencing

```
P0 ──► P1 ──► P2 ──► P3 ──► P4 ──► P5 ──► P6
        │      │      └─ P3 needs IdentityBlock for clarification wording
        │      └─ P2 needs ConversationState to render StateBlock
        └─ P1 needs P0 ledger to prove C1/C2
P4 may start in shadow mode after P1 (signals only); flip after P3.
```

≈ 10 weeks single-track; ≈ 7 weeks with P1/P2 and P3/P4-shadow in parallel.

## 7. Non-goals

- No Chat host mutations, no Chat Confirm for `call_host_api` (ADR-0046 stays).
- No model change as the fix — every phase must improve at constant model.
- No Agent cockpit rewrite beyond the two transparency widgets in P5.
- No new memory type; existing LTM/episodic are wired, not replaced.

## 8. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Context growth → cost/latency | Hard budgets in `assemble_context`; digests ≤ 200 chars; bounded state lists |
| PII in state/digests | Built through retrieval RBAC scope; redact on load; tenancy tests |
| Arbiter regressions | Shadow mode + `PULSE_ARBITER=legacy`; conflict-pair tests; pass^k = 3 |
| Deterministic summaries feel terse | Per-API bilingual templates reviewed by QA; optional 1-call LLM polish |
| Prompt refactor drift | Static test that every LLM stage uses `build_context_pack`; fabrication harness unchanged |

## 9. Definition of done

All C1–C10 and A1–A10 green in CI at pass^k = 3; nightly live Nibras ESS smoke green 5 consecutive days; QA bank G5 accepted by Nibras QA; ADR-0047 status Accepted.
