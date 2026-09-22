# PV2 P0 baseline — 2026-09-22/23

**Track:** PV2 — Pulse v2 Intelligence Contract (ADR-0047) · **Phase:** PV2-0C · **Author:** Pulse Master (workers PV2-0A rev2b opus, PV2-0B rev3 opus; both died mid-gate 20:47 on a shared test-DB collision — Master re-ran every gate and the live tier itself).

Purpose: freeze the *before* numbers for every Intelligence Contract objective so P1–P6 are measured, not felt. No code in this phase changes behaviour; the only edits are the runner flags `--live / --host-user / --no-isolated-db` (≈40 lines).

## 1. Instrumentation truthfulness (PV2-0A)

| Check | Result |
|---|---|
| `CallMeter` counts every `route_chat` call (success + exception path) | ✔ 8/8 tests |
| Per-stage attribution, no `unattributed` on a plain chat turn | ✔ — the hidden call was `AutoMemoryExtractor` (fire-and-forget, now stage `auto_memory`) |
| Nested scopes: step meter rolls up into turn meter under `pulse_loop`, outer restored | ✔ |
| Durable: `RunStep.critic_flags_json["llm_meter"]` + `llm_meter` in `_ADVANCE_EVENT_BY_STATE` StepJournal payloads | ✔ |
| Legacy hand count `total_llm_calls` vs meter | **undercounts by 1** (skips the intent call) — deterministic, 6/6 runs |
| Regression | 85 passed / 1 pre-existing failure (`test_chat_wiring::test_dispatch_chat_returns_completed`, nav fast-path; reproduced at HEAD) |
| Import boundary | 9 violations, byte-identical to HEAD |

## 2. Offline tier — 12 scripts × 8 turns, stub LLM, isolated test DB (PV2-0B rev3)

Dev-DB isolation proof: `LLMCallLog` 3364 → 3364 across the full run.

```
scripts_run 12   total_turns 96   turns_passed 4
focus_retention 0.082   slot_carry_over 1.0   language_fidelity 0.865
router_agreement 0.781  llm_calls_p50 4  llm_calls_max 4  turns_over_budget 83/96
per_objective_pass  C8 0.167 · A2 0.5 · all other C1–C10/A1 0.0
```

Engine-attributable in this tier: `router_agreement`, `llm_calls_*`, `turns_over_budget`. Text metrics are stub-dominated (see `caveats` in the JSON). Known harness defect carried forward: the stub advances one canned reply per *LLM call*, not per turn (fix in PV2-1x QA).

Script 12 (`nav-zero-llm`) verbose view — the router is right 5/8 and every non-nav turn costs 4 calls:

```
t1 navigate    llm=0 pass
t2 tool_answer llm=4 FAIL  expected answer|navigate, budget 0
t3 navigate    llm=0 FAIL  expected answer  (nav over-fires on a follow-up question)
t4 navigate    llm=0 pass
t5 navigate    llm=0 pass
t6 answer      llm=4 FAIL  expected navigate
t7 navigate    llm=0 pass
t8 answer      llm=4 FAIL  budget 0
```

## 3. Live tier — real LLM, dev DB, as `emp_1067` (PV2-0C)

3 scripts, 24 turns, Chat mode. `--live --host-user emp_1067 --no-isolated-db`. Reports: `/tmp/pv2-0c-live.json`, `/tmp/pv2-0c-live-payroll.json` (copied below).

```
                         turns_passed  router_agr  lang_fid  focus  llm_p50  llm_max  over_budget
ess-loan-ar-01 (AR)          0/8         0.50       0.81     0.50     3        5        6
chat-handoff-write-01 (EN)   0/8         0.50       1.00     0.50     3        5        7
payroll-followup-en-01 (EN)  0/8         0.625      1.00     0.40     3        5        6
```

### LLM cost per decision (from `[turn-decision]` logs, 24 live turns)

| decision | calls | stages |
|---|---|---|
| answer (×16) | 3 | intent · **fanout** · draft |
| tool_answer (×3) | 5 | intent · fanout · multi_step_plan ×3 |
| tool_answer (×1) | 5 | intent · fanout · draft · synthesis · verify |
| clarify (×2) | 1 | intent |
| refuse (×1) | 1 | intent |
| navigate (×2) | 0 | — |

`fanout` spends one LLM call on **every** answer turn even though `AGENT_ORCHESTRATOR_ENABLED=false` — pure waste (F-LIVE-5).

### Findings (verbatim replies)

| ID | Turn | What happened | Contract objective |
|---|---|---|---|
| F-LIVE-1 | loan-ar t1 «أريد قرض طارئ ٥٠٠٠ دينار» | `refuse` in **English**: *"that topic is outside my scope. I can help with payroll runs, payslips, GOSI/WPS, leave, loans…"* — refuses a loan request while listing loans as in scope; wrong language | IC-3 language fidelity · IC-1 intent grounding |
| F-LIVE-2 | loan-ar t8 «ما نوع القرض الذي طلبته؟» · handoff t1 "I want to apply for a loan" · t2 "An emergency loan" | `tool_answer` → *"I need your approval before I can proceed."* — Chat mode staged a host write and asked for consent (ADR-0046 violation), 5 LLM calls, and the *question* (what type of loan?) was never answered | IC-5 Chat/Agent boundary · IC-2 answer the question asked |
| F-LIVE-3 | loan-ar t6 «هل ستتم الموافقة عليه؟» · payroll t7 "When will next month's payroll be processed?" | `navigate` — *"هل تريد فتح People & Payroll؟"* / *"Would you like to open Payroll?"* — nav resolver hijacks a question because it contains a module noun | IC-1 · IC-6 deterministic-first must not over-fire |
| F-LIVE-4 | handoff t3 "I need 3000 SAR" | Expected `handoff_agent`; got `answer` asking for start date — there is no handoff decision in the runtime today; Chat keeps collecting slots it can never submit | IC-5 |
| F-LIVE-5 | all 16 `answer` turns | 3 calls each: `fanout` planning call fires with orchestrator disabled | IC-7 cost ≤ 1–2 calls for a plain answer |
| F-LIVE-6 | payroll t1–t6 as `emp_1067` | *"unable to access your pay information … permission issue"* on the employee's **own** payslip; then t5 `clarify` *"Which loan are you asking about"* after 4 turns about the same payslip. **Root cause (Master triage 2026-09-23):** the draft called `list_payslip_lines` (HR API → host 403) because the Nibras persona prompt says *"You have full read access … fetch … using list_payslip_lines"* — text written for an HR admin, shown unchanged to an employee. `list_my_payslips` exists in the catalog and `PayslipSelfCollectionView` works. The tool catalog is not filtered by the user's role and the prompt has no audience. → P2 `IdentityBlock` (role) + role-scoped catalog (PV2-2C). | IC-4 grounded self-service reads · IC-6 identity · IC-2 focus retention |
| F-LIVE-7 | handoff t5–t7 | Honest and correct: *"No information has been sent to an agent yet. We're still in Chat mode…"* — the model knows the boundary; the runtime doesn't act on it | (positive control for IC-5 wording) |
| F-LIVE-8 | loan-ar t2–t5 | Good: Arabic maintained, amount (5000) and type (emergency) carried across turns, term re-asked once | (positive control for IC-2/IC-3) |

### Reading the baseline

- **Cost:** p50 = 3 LLM calls for a plain answer; 5 for anything touching a tool. Target after P3/P4: ≤ 1 for deterministic paths, ≤ 2 for drafted answers.
- **Routing:** router agrees with the script author 50–62 % of the time live; the two systematic misfires are nav-over-fire (F-LIVE-3) and Chat staging writes (F-LIVE-2).
- **Language:** 0.81 on the Arabic script — the failures are the *deterministic* templates (refuse, nav), not the LLM. Same root cause as ADR-0047 §"stage-local prompts".
- **Boundary:** Chat has no `handoff_agent` decision; it either stages a write (wrong) or keeps collecting slots (dead end). P5 owns this.

## 4. Baseline numbers to beat (per IC objective)

| IC | Metric | Offline | Live | P-target |
|---|---|---|---|---|
| IC-1 intent/route | router_agreement | 0.781 | 0.50–0.625 | ≥ 0.90 (P4) |
| IC-2 focus/slots | focus_retention / slot_carry_over | 0.082* / 1.0 | 0.40–0.50 / 1.0 | ≥ 0.85 / 1.0 (P1) |
| IC-3 language | language_fidelity | 0.865* | 0.81 (AR) · 1.0 (EN) | ≥ 0.98 (P3) |
| IC-5 boundary | handoff decisions present | n/a | 0 of 2 expected | 2/2 (P5) |
| IC-7 cost | llm_calls_p50 / over_budget | 4 / 83 of 96 | 3 / 19 of 24 | ≤ 2 / ≤ 10 % (P3–P4) |

\* stub-dominated; use live column for text metrics.

## 5. Artifacts

- Runner: `backend/ai/eval/multiturn/runner.py` (`--report`, `--scripts`, `--verbose`, `--keepdb`, `--live`, `--host-user`, `--no-isolated-db`; exit 0/2/3)
- Bank: `backend/ai/eval/multiturn/scripts/*.yaml` (12) · tests `backend/ai/eval/test_multiturn_bank.py` (23 pass, 12 xfail coherence)
- Meter: `backend/ai/engine/llm/call_meter.py` · tests `backend/ai/tests/test_pv2_instrumentation.py` (8 pass)
- Reports: `docs/pulse/evidence/PV2-baseline-offline-2026-09-22.json`, `docs/pulse/evidence/PV2-baseline-live-2026-09-22.json`
