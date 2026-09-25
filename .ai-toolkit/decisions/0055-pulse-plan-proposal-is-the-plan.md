# ADR-0055 — A proposed plan is the plan

- **Status:** Proposed
- **Date:** 2026-09-25
- **Relates to:** ADR-0046 (Chat never host-mutates) · ADR-0052 (One plan contract, I6 declared = executed) · ADR-0053 (No masking fallbacks) · ADR-0049 (Pulse 2.1) · RULE_21 · RULE_23

## Context

On the Chat Plan dial a brief produced a *prose* plan and then, on an accept
word, a *different* plan. The two were never the same object:

1. `ensure_plan_review_text` substituted a five-step template whenever the
   draft returned fewer than two numbered lines. The template named no tool,
   no argument, and no deliverable — it pasted the user's sentence into step 2.
2. "Did the assistant show a plan?" was answered by a regex for `\d+[.)]`
   over the rendered prose.
3. "Did the user accept?" was answered by a word list (`_PLAN_ACCEPT` plus an
   inline `looks good / go ahead / create it` tuple) — a second affirmation
   path outside `dialogue/affirmation.py`.
4. On acceptance, `plan_task` received only `brief` and `PlansService.create_plan`
   decomposed from scratch. **The steps the user reviewed were discarded.**

A deterministic path that did this correctly already existed
(`_try_plan_dial_process_plan` → `create_plan` → `render_plan_dial_answer`:
real plan id, zero LLM calls, bound arguments, honest missing slots), but it
was gated to personal leave / loan / attendance writes. Every other brief fell
to the prose path.

## Decision

**The object the user reviews is the object that runs.**

- The Plan dial decomposes every substantive brief through the planner
  (`PlansService.decompose_for_review`) before anything is stored.
- **The planner decides what a task is.** `is_task_plan` returns false for a
  decomposition of one non-effect step: that is a question, so the turn falls
  through and answers it. This replaces the wording gate
  (`is_ess_write_utterance` + three personal-brief predicates).
- **Nothing is stored until the user consents.** The draft lives in
  `ConversationState.open_question` (`kind: plan_proposal`, with `plan_json`);
  the client form never receives `plan_json`. **Create task** calls
  `POST /ai/plans/proposal/commit/`, which reads the draft from the caller's
  own conversation state (owner-checked) and persists it *as reviewed* via
  `create_plan(user, brief, plan=rebuilt)` — no second decomposition. I6 holds
  across the proposal seam, and a client cannot commit a plan it was not shown.
- **Change** sends the user's words; with a draft open, the planner re-drafts
  from `revised_brief(prior, change)`. That is the clarifying conversation:
  typed state, not a wording match.
- The turn returns a typed `plan_proposal` (`turn/plan_proposal.py`): plan id,
  status, per-step intent, tool, bound argument preview, `gap`, `blocked`, and
  `blocked_count`. The client paints it; the text only restates it.
- **Capability preview moves before the commitment.** A step with no catalog
  capability shows as blocked while the user is still reading the plan,
  instead of 403-ing after approval.
- Approve and Run stay in Tasks / Agent. Chat proposes (ADR-0046).

### Deleted, not improved

`ensure_plan_review_text`, `_looks_like_accept`, `_assistant_showed_plan`,
`_user_accepted_shown_plan`, `plan_accept_brief`, the `_PLAN_ACCEPT` phrase
table, and the accept-injection block in `runner_s3_s5.py`. `plan_task` is no
longer reachable from either Chat surface. `routing_phrase_sets` 260 → 259; no
meter rose.

### Honest failure

When the planner cannot produce a task, the draft says so and asks one
question. `_plan_grounding_rules_block` now forbids the model from writing a
plan of its own or listing steps it did not get from a tool result
(ADR-0053).

## Consequences

- One typed question surface: `ChatResponse.form` carries whatever the turn
  asks (`kind: choice | plan_proposal | …`); `metadata.form` is the single
  client contract. The earlier `choice` field folded into it.
- A read brief on the Plan dial costs one planner call and then falls through.
  That replaces a draft call, so the turn budget is unchanged.
- Nothing is written for a brief the planner rejects.

## Enforcement

- `ai/tests/test_plan_dial.py` — `is_task_plan` on a one-read decomposition,
  `proposal_payload` shape, bound-argument preview, blocked step.
- `ai/tests/test_pv2_handoff_agent.py` — no reply word re-opens `plan_task`;
  the Plan grounding block forbids invented steps.
- `carbon-frontend/src/shell/__tests__/PlanProposalForm.test.jsx` — steps,
  bound args, blocked marking, and no approve control in Chat.
- `python -m ai.eval.pulse_gauge --gate` and `ai.eval.harness_budget`.
