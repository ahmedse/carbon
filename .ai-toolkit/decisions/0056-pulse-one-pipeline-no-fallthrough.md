# ADR-0056 — One pipeline: the model decides, code blocks or verifies, nothing falls through

- **Status:** Proposed
- **Date:** 2026-09-25
- **Relates to:** ADR-0046 (Chat never host-mutates) · ADR-0047 (intelligence contract) · ADR-0049 (Pulse 2.1) · ADR-0050 (domain-free core) · ADR-0053 (no masking fallbacks) · ADR-0054 (reasoning channel) · ADR-0055 (proposed plan is the plan) · RULE_21

## Context

A Chat turn has two pipelines and a layer of routers around the model.

1. **Seven deterministic gates run before the understand call** (`runner_pre_s1.py`): plan-revision confirm, memory confirm, navigation fast path, plan status, Chat write handoff, next-step offer, bound self-service read. Two answer a typed open question. Five decide the turn from the user's wording.
2. **v21 cannot finish three of its own ops.** `answer`, `navigate` and `set_slot` return `None` from `act_on_decision` / `_reply_for`, so the turn drops into a second router (zero-LLM surface, restyle, typed report clarify, process brief) and then the legacy spine (S1 intent · S2 plan gates · S3 draft · S4 critic · FallbackHandler · S5 render · S6 finalize). Every plain conversational answer today is written by the legacy draft.
3. **Code rewrites model output.** The FallbackHandler and the envelope template replaced correct answers (incident c5801082, "Live data summary" on every message; I-2 silent draft swap). `_execute_bound_read` deletes ungrounded numbers from the text instead of failing.

The model already understands: G6 accuracy 0.993, parity 0.987. The intelligence is lost in the layers around it.

4. **The model cannot reach most of Pulse's tools.** The v21 capability surface is the host catalog plus `resolve_entity` / `aggregate_entity`. Memory (`learn_fact`, `forget_fact`), `search_knowledge`, `get_entity_details`, `export_document`, `web_research`, work objectives, `list_my_capabilities`, `code_execute`, `unit_converter`, `cross_synthesize` and `create_dq_rule` exist only in the legacy draft's tool list. Today those turns work because v21 falls through. Deleting legacy first would remove them.
5. **The understand call is also overridden.** `_apply_catalog_choice` replaces the model's lead command when the utterance lexically matches catalog examples.

## Decision

**Rule.** On a Chat turn the model decides. Code may *block* (RBAC, ADR-0046, RULE_21 consent) or *verify* (schema validation, grounding, scrub). Code may not decide the turn from wording, answer in the model's place, or rewrite what the model said. A turn that cannot be answered returns a typed, visible error (ADR-0053). There is no fallthrough.

0. **One capability surface.** Every chat-visible tool becomes a catalog entry: name, description, parameter schema, and `kind` from its own metadata (`requires_confirmation` → write; memory tools → memory, the ADR-0046 Chat exception; otherwise read). The executor runs a tool entry as that tool and a host entry as `call_host_api`. No name list decides which is which.
1. **v21 finishes every op it can emit.**
   - `answer` → one writer call (`speak_answer`) with the same ContextPack plus the retrieved knowledge and memory the draft uses today, no tools. It is grounded like every other reply.
   - `navigate` → the navigation reply built from the Decision's target, validated against the scoped route list.
   - `set_slot` → state write plus the next clarify/confirm from state.
   - `handoff_agent process_id=plan` on the Plan dial → the planner (ADR-0055) is called *by the Decision*, not reached by fallthrough.
2. **The five deciding gates move behind the understand call.**
   - Navigation fast path → `navigate` op (already in `COMMAND_OPS`).
   - Plan status and next-step offer → the understand prompt's StateBlock already lists `active_plans`; the Decision answers from state (`answer` with a state source, 0 host reads).
   - Chat write handoff → deleted; `validate_decision` already turns a Chat write into `handoff_agent`.
   - Bound self-service read → the `call_tool` Decision with bound args. A fully bound read still runs with 0 draft/observe LLM (ADR-0047 deterministic-first); only the choice moves to the model.
   The two typed confirms (plan revision, memory) stay: they answer an `open_question` the user was already shown, which is state, not wording.
3. **Rewrites become failures.** `_execute_bound_read` fails the read visibly on ungrounded numbers (`Degradation("speak", "ungrounded")`) instead of deleting them. FallbackHandler is not reachable from Chat. `_apply_catalog_choice` stops replacing the model's command; a catalog/model disagreement is logged as a G6 signal and fixed in the catalog description, not at runtime.
4. **The fallthrough and the legacy Chat spine are deleted** once the evidence gate (below) passes: `runner_s1.py`, the Chat parts of `runner_s2_plan.py`, `runner_s3_s5.py`, `runner_s6.py`, the soft surfaces in `runner_surfaces.py` (`_try_zero_llm_surface`, `_try_restyle_previous_answer`, `_try_plan_status_answer`, `_try_next_step_offer`, `_try_chat_write_handoff`, `_try_bound_ess_self_read`), `zero_llm.py`, the deterministic `resolve_navigation` fast path, early `process_brief`, `TurnRouter` RESTYLE / REPORT_CLARIFY kinds, `exit_policy.py` and `StagedExit`, `intent.py` (legacy S1), `force_tool.py`, the Chat-only parts of `runner_render.py` (`_wants_visual`, `_is_distribution_ask`, draft synthesis), and the `PULSE_UNDERSTAND=legacy|shadow` modes.
   **Kept:** `DraftWitness`, `CriticWitness` and the planner. The Agent run (`plans_service.py`, `plan/loop.py`) uses them. They are called by an approved plan step, never by a Chat fallthrough.
5. **Rollback replaces the kill switch.** With one pipeline there is no `legacy` mode to flip. Rollback is the release tag (prod stays `nibras-v0.1.44` until you deploy) or a revert of the deletion commit. `PULSE_TOOL_CHOICE=off` stays.

## Evidence gate before deletion (step 4)

- G6 ≥ 0.95 accuracy and parity ≥ 0.98 with fallthrough counted as a miss (today it is counted as neutral).
- G5 multi-turn 96/96 with no fallthrough outcome in the ledger.
- A replay of recorded real conversations from `nibras_dev` through the new path: zero fallthroughs, zero ungrounded numbers, no reply identical across different user messages (the c5801082 class).
- The live shadow window the contract names (ADR-0049 Q3), on STACK-HOLD, as `emp_1067`, with `PULSE_NIGHTLY_LIVE=1`. This needs a restart of :8009 that only you can allow.
- `pulse_gauge --gate` and `pack_contract --gate` pass. Meters `staged_exits`, `re_compile`, `routing_phrase_sets` and `runner_lines` must fall, and nothing may rise.

## Order

| Step | What | Needs live | Gate |
|---|---|---|---|
| 0 | One capability surface: plugin and platform tools are catalog entries v21 can decide and execute | No | tool-reach test: every chat-visible tool is on the surface and runs |
| 1 | `answer` / `navigate` / `set_slot` / plan-handoff finished inside v21; every remaining fallthrough is recorded with its reason, then becomes a typed error | No | G6, G5, new "no-fallthrough" bank |
| 2 | The five deciding gates move behind understand | No | G6, G5, gate-parity bank (each old gate's goldens now pass through a Decision) |
| 3 | Rewrites become failures (`_execute_bound_read`, FallbackHandler off Chat) | No | fabrication bank, reasoning bank |
| 4 | Offline replay of real conversations | No | the replay criteria above |
| 5 | Live shadow window | **Yes: restart + STACK-HOLD** | contract Q3 |
| 6 | Delete the legacy Chat spine, the soft surfaces and `legacy`/`shadow` modes | No | all gates; meters fall |
| 7 | Update `.cursor/rules/pulse-2-1-contract.mdc` and the canvas: kill switch section, L7 lean-harness numbers | No | — |

## Alternatives considered

- **Keep legacy behind the kill switch indefinitely.** Rejected. Two pipelines is why the model's answer gets overridden, and every fix has to be made twice.
- **Delete now, skip the shadow window.** Rejected by the contract (ADR-0049). The offline replay shortens the risk; it does not replace the live window.
- **Delete draft and critic too.** Rejected. The Agent run executes approved steps with them.

## Consequences

- **Positive:** One pipeline. Every Chat reply is traceable to one Decision. No code path can say "Live data summary" or swap a draft. The routing meters fall toward zero.
- **Negative:** An understand-model outage is a visible failure, not a degraded answer (ADR-0053 already chose this). `answer` turns keep two model calls (understand + writer), the same as today's understand + draft.
- **Do NOT re-try:** A wording gate before understand. A fallthrough to "some other path that might answer". A post-hoc rewrite of model text.
