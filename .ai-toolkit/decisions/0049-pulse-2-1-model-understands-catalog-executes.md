# ADR 0049 — Pulse 2.1: model understands, catalog executes

- **Status:** Proposed
- **Date:** 2026-09-23
- **Deciders:** Pulse Master
- **Area:** backend

## Context

Pulse v2 (ADR-0047) reached L0–L5 by stacking deterministic gates in front of the draft model. The engine now has 13 staged exits, 227 compiled regexes (53 containing Arabic), and `runner.py` at ~5908 lines. `tool_choice` is unused: Intent confidence is passed as prose, Draft may return `tool_calls=0`, and synthesis invents figures (conv `fc9eb86b`, "0 يوم"). Industry systems that feel coherent (Rasa CALM, Copilot, Cursor, Agentforce, Copilot Studio) put language understanding in the model and business logic in code. Arabic is the stress test, not the cause.

ADR-0046 (Chat never mutates) and ADR-0047 (one state, one pack, measure only what the scorer grants, night 2026-09-23 FAIL stays) remain in force.

## Decision

1. **Understanding is one LLM call** that emits a strict `Decision`: 1–3 commands in `{call_tool, navigate, clarify, set_slot, answer, handoff_agent, refuse}`, plus `language` and `confidence`. The transcript plus ConversationState is the context. Regex may normalize text or add an Arbiter signal. Regex must not end the turn.
2. **The catalog is the router.** Tools carry `description`, `not_for`, `domain`, `kind`, `empty_render`, and examples. Twins are disambiguated there, not by `topic_re` tables.
3. **Determinism uses the API.** `route_chat` accepts `tool_choice` (`auto` | `required` | named) and optional strict schemas. Bound self-reads use named `tool_choice` when intent already names one tool at confidence ≥ 0.9. `PULSE_TOOL_CHOICE` defaults on (P3, 2026-09-24). `off` is the kill switch.
4. **The Arbiter validates; it does not re-route.** `Arbiter.decide` stays the v2 path. `validate_decision` checks RBAC, surface, and ADR-0046. Chat never receives write tools.
5. **Flags, not a big bang.** `PULSE_UNDERSTAND=v21|shadow|legacy` (default `v21` as of P1, 2026-09-24; `legacy` is the kill switch) and `PULSE_TOOL_CHOICE=off|on` (default `off`). G6 ≥ 0.95 and the hours-scale bank agreement (121/122 baseline) are the evidence. Superseded soft gates do not stage under v21.
6. **Harness budget is a metric.** `ai.eval.harness_budget` counts exits, routing regexes, Arabic-literal regexes, runner lines, and `tool_choice` uses. Ceilings ratchet down. A phase must not increase them.
7. **L6 Understands and L7 Lean** are scorer predicates. The canvas must not claim them while evidence is missing.
8. **Fixes are goldens plus descriptions.** No new `StagedExit` and no new routing `re.compile` on the v21 path.

## Alternatives Considered

- **More phrase gates per transcript** — rejected. That is how the harness reached 13 exits and 227 regexes.
- **Model swap as the fix** — rejected. ADR-0047: improve metrics at constant model.
- **Delete every gate in one change** — rejected. Shadow + kill switch first; G5 must stay 96/96.

## Consequences

- **Positive:** a forced tool call cannot be declined in prose; empty host data has a renderer; Arabic leaves the router.
- **Negative / trade-off:** two paths until the flip. Understanding adds a call on turns that regex used to short-circuit; bound reads stay 0-LLM.
- **Do NOT re-try:** per-utterance Arabic/English regex to choose an API; passing "please call the tool" as the only force; claiming L6/L7 without `intelligence_ladder` evidence; building a stage's tool list anywhere but `capability_surface`; turning a validation failure into user text; naming a tool in persona / guidance prose.

## Rollout (2026-09-24) — goldens first, flip by env only

Trigger: Nibras Chat transcript as `emp_1067` (payslip → "what is GOSI?!" → "I noticed I have a loan, give me more details" → "get it"). Three failures, one class: an ordered lexical gate decided read-vs-write before understanding, and a fallback keyed on *draft empty* replaced a grounded render. No phrase was added to any table.

| Step | Artefact | Result |
|---|---|---|
| 1. Failing goldens | `ai/eval/g6_bank.yaml` `tier: v21` g6-062…067 (loan reads phrased as statements, "get it" on an offered read, contrast "I want to take a new loan" → `handoff_agent`); `ai/eval/multiturn/scripts_v21/14-payslip-loan-followup-en-01.yaml` | Legacy ladder: 0/6 G6 cases (`v21_pending` in `PV2.1-g6-baseline-2026-09-24.json`); legacy runtime turn 4 = `clarify` "What type of loan" (`PV2.1-multiturn-v21-legacy-2026-09-24.json`). G5 bank `scripts/*.yaml` untouched (96/96 stands). |
| 2. Catalog is the router | `nibras/instance.yaml`: `list_my_loans` description/examples cover existing-loan statements; `submit_my_loan.not_for` names the read twin and forbids "what type of loan" unless a new loan is asked; `list_my_payslips` says explaining GOSI is an answer from state | `catalog_prompt_lines` (`turn/understand.py`) now describes write twins as **Agent-only** so their `not_for` can route; `validate_decision` gets `write_tools` and downgrades a write `call_tool` to `handoff_agent` (was: "I can't use submit_my_loan from here" clarify). |
| 3. Measure | `python -m ai.eval.g6_runner --mode understand [--tier v21|all] --write` — one `emit_decision` call per utterance through the same prompt/catalog/validation as the runtime | See `docs/pulse/evidence/PV2.1-g6-understand-<date>.json`. Gate = `decision_accuracy ≥ 0.95`, no errors. |
| 4. Stage invariant | `should_honest_fallback(final_text, completed_tools)` in `turn/catalog_render.py`; `runner_s3_s5` uses it | Fallback fires only when tools ran **and nothing rendered**. A forced call blanking the draft no longer erases catalog / empty-host renders. Applies to v2 as well (contract repair, not a phrase patch). |
| 5. Budget | `ai.eval.harness_budget --gate` | No new `StagedExit`, no new routing `re.compile`. |
| 6. Chart = render of the decided read | `Command.render` ∈ {text,chart,table}; `pipeline_v21.render_envelope` / `rows_envelope` chart **only** executed rows; envelope `_gross_per_person` requires ≥2 identities before "Employees" bands | Goldens: g6-068…070 + `scripts_v21/15-leave-charts-subject-en-01.yaml` (leave thread → "where are the charts?" must not show Gross Pay). Conv 5719114d class. |
| 7. Plan handoff + prompt fit | Multi-step / conditional / escalate → `handoff_agent` `process_id=plan`. Malformed `emit_decision` → `None` (legacy speaks; never "Which of these?"). Rules **above** catalog; non-top-k tools are name-only so HR catalogs fit under TASK 8k (was clipping the plan rule). Non-GET catalog entries marked write. | Goldens: g6-071…074 (board-pack variance → plan; ESS composite → plan; single PDF export → answer; "which October runs?" → `list_payroll_runs`). |
| 8. Close G6 gap (catalog + audience) | ESS sees `list_leave_entitlements` (403-honest); NAV routes `attendance`/`payroll`/`leave`/`loans` audience ess+hr; understand prompt includes NAV lines; empty_host goldens carry prior empty state; decision rules for multi-domain clarify, bare leave vs bare attendance, coworker leave, empty_render, clock-now vs past attendance | Evidence `PV2.1-g6-understand-2026-09-24.json`: full-bank **0.973**, `gate_pass: true` (was 0.567 → 0.811 → 0.919). v21 tier 0.962. Four residual utterance flakes (g6-038 AR, g6-045/047 EN clarify, g6-070 EN). |

| 9. Discuss→apply is typed state (2026-09-24, plan `e20c2937`) | User refined a plan in Chat, typed "apply" then "accept"; Pulse replanned from the prompt, then "I wasn't able to generate a response". Four layers, one class: an apply **phrase allowlist** decided the turn (invisible to the `re.compile` meter), discuss context was scanned from transcript markers, the plan id was regex-searched from history, and the APPLY prompt ordered `edit_plan` in Chat — which the ADR-0046 guard cancels on every Chat surface (dead end even when the words matched). | `turn/plan_revision.py`: the discuss reply becomes a typed `open_question{kind: plan_revision, plan_id, revision, confirm}` on ConversationState; the shared affirmation module (`is_commit_affirmation`) resolves the next turn via the existing I2 confirm route; a confirmed revision is a **0-LLM handoff** to Agent (`open_panel` → Tasks with the revision; existing replan + diff review applies it). Deleted: `_AGENT_DISCUSS_APPLY_SHORT/_PHRASES`, `_is_discuss_apply_turn`, `_history_has_discuss_markers`, `_is_agent_discuss_context`, the plan-id regex, the APPLY prompt. Golden: `ai/tests/test_plan_revision_state.py` (incl. the guard-contradiction test). New meters `routing_phrase_sets` / `domain_terms_in_core` / `brand_literals_in_core` + `pulse_gauge --gate` ratchet — see ADR-0050. |

| 10. §9 One capability surface + bounded self-repair (2026-09-24, conv `fc9eb86b` 14:34) | HR manager: "summary report with charts about gofsco employees" → Pulse: "I can't use aggregate_entity from here." Replay: the model decided well (headcount + two breakdowns), then four layers broke it. (a) The persona and two catalog entries offered `aggregate_entity`, but the understand allow-set was built from the host catalog only, so validation refused it. (b) Validation authored that refusal as user text; the output gate passed it. (c) `act_on_decision` ran only `commands[0]`, so the two valid reads were dropped. (d) `execute_tool` did `del args`, so a read with a required arg could never succeed. One class: v21 rebuilt narrower private copies of the tool surface, arg contract, and recovery instead of using the engine's. Same class seen at 00:15 ("I can't use export_document from here") and in legacy "**call_host_api**: Retrieved 6 row(s)". | **Surface:** `turn/capability.py` `capability_surface` = audience-scoped catalog + registry capabilities `call_host_api` executes by name (`tools.host_api_capabilities`, flag-gated). Understand prompt, `validate_decision`, executor (`host_call` binds path/query params from the entry), the v21 Draft task body, synthesis (was unscoped), and the G6 scorer all read it. Catalog lines render declared `Args:` from the entry schema. **Rejection is typed:** `Decision.rejections` (`not_on_surface` / `invalid_args` / `missing_name`); a rejected command is dropped, never spoken. **Self-repair:** `turn/repair.py`. The rejection (or a host 400 on a decided read) goes back to the model once, as the tool result of its own `emit_decision`; budget one per turn; an empty Decision falls through to legacy (`unrepairable`). **Execution:** every validated read runs with its args (dedup), a handoff/refuse anywhere wins, and rows no restater covers render as the envelope instead of "Could not read". **Egress invariant:** `engine_runtime._scrub_internal_names` relabels any exact registry/catalog identifier in final Chat text (flag `internal_identifier_corrected`); the tool-only summary names the capability, not the executor. **Pack contract:** `pack_contract.tool_reference_violations`. Identity prose names no tool (it is shared by every stage and audience); catalog text names only entries every reader can see, never a flag-gated engine tool. 15 violations fixed across nibras/eduos/carbon. **Observability + learning:** one `understand` ledger row per v21 turn (raw ops, ops, rejections, repaired, executed, host_refused) + `[understand]` log; every turn with a rejection is queued to `ai/eval/pending_understand_nominations.json` for G6 review. Golden g6-075 (`expect_api_any`, `expect_render: chart`). Tests `ai/tests/test_pv21_capability.py` (16). The v21 `turn_decision` is now the Arbiter's (v21 fires the existing gate it acted as: `tools_executed` / `chat_clarify` / `chat_handoff` / `off_limits`), where it used to be a raw op the Arbiter relabelled `answer`. Evidence `PV2.1-g6-understand-2026-09-24.json`: n=75, **0.987**, `gate_pass: true`, v21 tier 14/14 (residual flakes g6-038 AR, g6-049). Budget meters unchanged (routing_phrase_sets 260, re_compile 59, staged_exits 3, runner_lines 367). |

P1 is in force: `PULSE_UNDERSTAND` defaults to `v21` in committed code. `legacy` remains the kill switch. `PULSE_TOOL_CHOICE` stays off. Any v21-tier golden the ladder cannot pass is fixed by description or golden, never by regex.

## References

- Canvas: Pulse 2.1 plan + principles registry; ladder canvas L6/L7.
- ADR-0046, ADR-0047.
- `backend/ai/engine/llm/router.py` `route_chat`, `backend/ai/engine/cognition/turn/decision.py`.
