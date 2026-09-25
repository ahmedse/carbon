# ADR 0052 — One Plan Contract, with authority to reject

- **Status:** Proposed
- **Date:** 2026-09-25
- **Deciders:** Master Architect
- **Area:** backend

## Context

Run `aec8f39a` exported a board pack on a failed read, saved a list payload as a validation, and offered Approve on an invented API. Six planner passes each patch one past incident by rewriting the plan, and they contradict each other: one pass dropped the export and the next put it back. A seventh pass would be another patch.

## Decision

`plan/contract.py` `apply_plan_contract` is the only plan-save authority. It returns typed findings `(code, step_id, detail, blocks)`. A repair is a non-blocking finding. Anything it cannot repair blocks the plan, and the finding is what Approve and resume show. The six passes are not called on their own anymore; the contract calls the repairs it still needs, once, in one order.

Invariants:

- **I1 Capability.** A host step names an exact catalog entry in the canonical argument shape, schema-valid or bound. Otherwise it is a declared gap, not a host call.
- **I2 Mutation.** `is_mutation` comes from the catalog method or `requires_confirmation`, or from the export tool. The model's flag is ignored.
- **I3 Evidence.** A write or export runs only when every dependency completed with an effect. Failed, skipped, and `no_effect` block it. The consent card lists that status. No evidence means no card.
- **I4 Branches.** Two effects that neither depends on the other run in one plan only when each carries a guard on the same step with a different value. Otherwise the plan is blocked. An unresolved guard pauses. It never runs both and never guesses.
- **I5 Gaps.** An intent with no capability is `step.gap`. It is not an invented `api_name`, and it is not marked finished.
- **I6 Declared = executed.** The executed tool and `api_name` must equal the declaration. A mismatch is a rejected call.
- **I7 Coverage.** `contract_gate` findings block approval. They used to be recorded and ignored.

The same check runs at plan save, Approve, and every resume, including plans saved before this contract. Approve and resume check existence against the unscoped catalog; permission stays with the host.

The auditor at each stage:

- **Plan:** the contract and `contract_gate`. A category noun (report, export, table, rule, field, binding) is covered by what a step does, not only by its words. A quoted name is a hint and does not block.
- **Before a step:** gap, guard (run, skip, or a typed guard choice the operator answers for the source step), and evidence.
- **Step output:** an error status inside a returned call fails with a typed class. A review step (`agent_role: critic`) takes no tool, needs a step to review, and must end with a typed verdict. No verdict is `no_effect`; `fail` blocks its dependents.
- **Final:** a missed acceptance turns `completed` into `completed_with_gaps`, and the summary leads with what was not met. List and get keep that status.

## Alternatives Considered

- **A seventh repair pass** — rejected. The passes already undo each other.
- **Phrase rules for "if / else" and "escalate"** — rejected. The fork is structural: two effects, neither depending on the other, and no guard.

## Consequences

- **Positive:** A plan that cannot be executed is refused before consent, with a code the operator can read.
- **Negative / trade-off:** A conditional brief the model does not guard is rejected instead of run. The operator replans.
- **Do NOT re-try:** Silently rewriting a step to hide a missing capability, or treating a model's `is_mutation: false` as a fact.

## References

- `backend/ai/engine/cognition/plan/contract.py`
- ADR-0034 workflow choice nodes · ADR-0046 Chat does not host-mutate · RULE_21
- Runs `aec8f39a` (this brief) and `0bd5072d` (workforce briefing)
