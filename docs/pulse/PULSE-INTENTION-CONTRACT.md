# Pulse Intention Contract (ADR-0046 · 0047 · 0049 · 0050 · 0056)

- **Status:** Proposed — audit + plan only. No behaviour change ships with this document.
- **Date:** 2026-10-03
- **Owner:** Pulse Master seat
- **Numbering:** this contract adds **new** identifiers only (`IRP-*`, `IF-*`, `IB-*`, `IR0`–`IR5`).
  It does **not** renumber or rewrite the signed Ask `10/10` (files 2035/2036/2038), the
  excellence grid `17/54`, or the Tasks board `R1`–`R12` / `P1`–`P8` / `B0`–`B6`.
- **Reads with:** `.ai-toolkit/decisions/0046-pulse-chat-no-host-mutation-stage.md`,
  `0047-pulse-unified-conversation-state.md`, `0049-pulse-2-1-model-understands-catalog-executes.md`,
  `0050-pulse-core-domain-free-versioned-packs.md`, `0056-pulse-one-pipeline-no-fallthrough.md`,
  `docs/pulse/PULSE-V2-INTELLIGENCE-CONTRACT.md`, `docs/pulse/evidence/PV2.1-q4-exit-inventory-2026-09-23.md`.

## 0. Why this document exists

The standing complaint is precise: *"Pulse, in all its forms (coworker, tutor) and modes (ask, plan),
many times replies in idiotic or stupid and out-of-context answers."* The user asked for an audit of
**intention recognition** and for principles, rules, benchmarks and ladders to be defined **before**
more implementation.

The complaint is **not** the arbiter router. On the committed 96-turn bank the recorded
`router_agreement` is 1.0 (`docs/pulse/evidence/PV2-g5-2026-09-23r.json`) and the v21 understand call
scores G6 decision-accuracy 0.993 / parity 0.987 (`PV2.1-g6-understand-2026-09-24.json`, re-read live
by `ai.eval.intelligence_ladder.latest_g6_understand`). The complaint is what happens **around** a
correct Decision: wording gates that decide before the model, a second legacy spine that answers when
the Decision does not, a writer that restates instead of answers, scope/language copy that ignores the
message, and no live bank for these classes. ADR-0056 §Context already names this ("two pipelines and
a layer of routers around the model"; "code rewrites model output").

**Scope.** One turn path, four surfaces:

| Surface | Where | Same engine? |
|---|---|---|
| Chat Ask | `process_mode="ask"` | yes |
| Chat Plan | `process_mode="plan"` (`Surface.CHAT_PLAN`) | yes |
| Coworker / Tutor voice | persona/role in pack (`instance.yaml` persona) | yes |
| My / Team / People | host ESS & admin apps (Plane A) | no — host, not Pulse Chat |

This document covers the **Pulse Chat turn path**. Host ESS reads/writes belong to the host apps and
to Agent (RULE_21); this contract only fixes what Pulse says about them.

---

## 1. Principles (each falsifiable)

Every row names the exact instrument. Commands run from `backend/`. A principle is **falsified**
when the field shows the failure value. "No instrument" is not a pass: a principle whose instrument
is not built is `missing`, never `reached`.

| Id | Principle | Falsified by — exact test / field / failure value |
|---|---|---|
| **IRP-1** | **One answer per turn.** A turn emits exactly one user-visible reply, from exactly one owner. | `python -m ai.eval.chat_deep_bench` → `objectives[id=C4].column.live`. Failure = `"fail"` (decision log not 100%, or `router_agreement < 0.90`, `_frac_ok(..., bar=0.90)`), **or** a recorded turn carries two `final`-stage rows from two owners. |
| **IRP-2** | **Understanding is one call that emits one Decision** (`understand.py:361` `understand_turn`). Under v21 no wording gate may set the turn outcome. | `python -c "import os;os.environ.pop('PULSE_UNDERSTAND',None);from ai.engine.cognition.turn.understand import understand_mode;print(understand_mode())"` → must print `v21`. Failure = `legacy` or `shadow`. Plus `python -m ai.eval.pulse_gauge --gate`: failure = exit 1, or `staged_exits` above its ceiling. |
| **IRP-3** | **Intent is resolved once and recorded, never re-decided by a later regex.** Regex may fold (`engine/text/normalize.py`) or add a signal; it may not be a new exit. | `python -m ai.eval.harness_budget` → read `re_compile` and `routing_phrase_sets`; then `python -m ai.eval.pulse_gauge --gate`. Failure = either meter above its ceiling (`re_compile` 45, `routing_phrase_sets` 226 at the last snapshot), or `--gate` exit 1. |
| **IRP-4** | **Typed state over prose.** Continuity resolves against `ConversationState` (`open_question.kind`, `active_plans`, `slots`), never by scanning history for markers. | `python -m pytest backend/ai/tests/test_plan_revision_state.py -q`. Failure = any node fails, or a new marker list appears (`routing_phrase_sets` rises). |
| **IRP-5** | **Numbers are grounded.** Every figure in a reply is in the evidence the turn was shown (`turn/grounding.py`); an ungrounded number is a typed failure, not an edit. | `python -m ai.eval.chat_intention_retest --bank IB-01`; `python -m pytest backend/ai/tests/test_fabrication_bank.py -q`. Failure = one reply figure is not a substring of the tool payload (`pass=false`), or any node fails. |
| **IRP-6** | **Chat never host-mutates (ADR-0046).** A Chat write intent gets one honest handoff; it is never answered as if it can execute. | `python -m ai.eval.chat_intention_retest --bank IB-06`; `python -m pytest backend/ai/tests/test_pv21_capability.py -q`. Failure = a Chat turn with `chat_mutated=true`, or `turn_decision ∈ {answer, tool_answer}` for a write intent (must be `handoff_agent`). |
| **IRP-7** | **Language follows the user.** Reply language = message language (`turn/language.py:33`; `arabic_ratio ≥ 0.4` → `ar`), not the pack default. | `python -m ai.eval.chat_intention_retest --bank IB-02`; per-turn `language` field in every `PV2-intention-IB*.json`. Failure = a turn where `detect_reply_language(reply) ≠ expected`, including refusals and clarifications (`pass=false`). |
| **IRP-8** | **No fallthrough.** What the Decision cannot finish returns a typed, visible error (ADR-0053), never the legacy spine. | `python -m ai.eval.chat_deep_bench` → `fallthrough.status`; `python -m pytest backend/ai/tests/ -k intention -q` (IB-09). Failure = `fallthrough.status == "fail"` (count > 0); `"missing"` is not a pass. |
| **IRP-9** | **Scope is declared, not guessed.** An ask naming a declared in-scope term is never scope-refused (pack `instance.yaml` `topic_guard.in_scope`). | `python -m ai.eval.chat_intention_retest --bank IB-05`. Failure = any in-scope thread `pass=false`, i.e. `turn_decision == refuse` on an in-scope term, or a `cause=safety` refusal dropped by the rescue. |
| **IRP-10** | **No new phrase tables, no new routing `re.compile`, no `StagedExit`, no host-domain or brand words in `engine/**`** (ADR-0050). | `python -m ai.eval.pulse_gauge --gate` and `python -m ai.eval.pack_contract --gate`. Failure = either gate exits 1, any meter rises, or `domain_terms_in_core` / `brand_literals_in_core` > 0. |

### 1.1 Hard rules (do / don't) — each names its gate

| Rule (IRP) | Do | Don't | Enforced by |
|---|---|---|---|
| IRP-1 | Emit one reply; pick one owner from the Decision. | Stage two bodies; let code answer after a `final`. | `chat_deep_bench` `objectives[C4]` |
| IRP-2 | Keep the `PULSE_UNDERSTAND` default `v21`; let the Decision be authoritative. | Set `PULSE_UNDERSTAND=legacy`/`shadow`; let a committed route skip the Decision. | `understand_mode()` print; `pulse_gauge --gate` |
| IRP-3 | Fold/normalize text; record one `turn_decision`. | Add a routing `re.compile` or a module-level phrase set in `engine/**`. | `harness_budget`; `pulse_gauge --gate` |
| IRP-4 | Resolve follow-ups from `ConversationState`; affirm via `dialogue/affirmation.py` only. | Scan history for "apply"/"yes" markers; put affirmation logic in a runner. | `test_plan_revision_state.py`; `routing_phrase_sets` |
| IRP-5 | Fail the read with `Degradation("speak","ungrounded")`. | Delete an ungrounded number and ship the edit as the answer. | `test_fabrication_bank.py`; IB-01 |
| IRP-6 | One honest handoff (`handoff_agent`). | Answer a write as executed; stage a host mutation from Chat. | IB-06; `test_pv21_capability.py` |
| IRP-7 | Choose copy language from the message. | Let a template default language override the message. | IB-02; per-turn `language` |
| IRP-8 | Return a typed, visible error. | Let the legacy spine answer a turn the Decision left unanswered. | `fallthrough.status`; IB-09 |
| IRP-9 | Refuse on `cause=safety`; answer/clarify on a declared in-scope term. | Let the declared-scope rescue drop a safety refusal, or scope-refuse an in-scope term. | IB-04 / IB-05 |
| IRP-10 | Put vocabulary in the pack; lower the meters. | Add a phrase table / router regex / `StagedExit` / domain or brand word to `engine/**`. | `pulse_gauge --gate`; `pack_contract --gate` |

---

## 2. Mechanism map — how many ways a turn is decided today

Read from the code, not memory. The spine is `TurnPipelineRunner._run_metered`
(`runner.py:196`), which calls six stage functions.

### 2.1 Early exits in `runner.py`

`runner.py` has four `return` statements inside `_run_metered`:

| Line | Return | Meaning |
|---|---|---|
| `runner.py:330` | `return early` | `run_pre_s1_gates` staged/returned a body |
| `runner.py:334` | `return early` | `run_s1_intent` staged/returned a body |
| `runner.py:338` | `return early` | `run_s2_and_plan_gates` returned a body |
| `runner.py:341` | `return await run_s6_finalize(...)` | spine finished (S3–S6 legacy) |

The stage functions carry their own early returns: `runner_pre_s1.py:103, 139, 241, 255, 258, 291`;
`runner_s1.py:169, 339`; `runner_s2_plan.py:133, 182, 229`; `runner_s6.py:138`.
That is **13 stage-level early returns**, plus **3 spine exits** counted by the harness
(`harness_budget.measure().staged_exits == 3`): `chat_handoff`, `ess_bound_self_read`, `off_limits`
(`runner_pre_s1.py:215, 237`; `runner_s1.py:255`). The other 13 are `stage_soft_exit`
(`exit_policy.py:58`), which the harness deliberately does not count.

### 2.2 The independent mechanisms that can set the outcome

| # | Mechanism | file:line | Kind | Can override |
|---|---|---|---|---|
| 1 | `TurnRouter.decide` typed routes | `router.py:117`; branches `:140` confirm, `:154` option, `:168` restyle, `:179` plan_status, `:187` plan_dial, `:204` report_clarify | deterministic | Sets `turn_route.committed`; a committed route **skips** `_try_v21_understand` (`runner_pre_s1.py:238`) |
| 2 | v21 understand + validated Decision | `understand.py:361`, `decision.py:214` `validate_decision`, driven by `runner_surfaces.py:429` `_try_v21_understand` | one LLM call | Owns `answer`/`call_tool`/`continue`/`navigate`/`clarify`/`handoff_agent`/`refuse`/`set_slot`/`confirm` |
| 3 | v21 one-repair re-emission | `understand.py:471` `repair_turn`; invoked `runner_surfaces.py:430` and `:703` | second LLM call | Rewrites the Decision once (parse failure, rejection, host-refused read, record mismatch) |
| 4 | Legacy S1 `IntentResolver` | `runner_s1.py:177` (only when `understand_mode() != "v21"`) | LLM classifier | `zone=off_limits` refuse, navigate, clarify/disambiguate |
| 5 | `stage_exit` / `stage_soft_exit` gates | `exit_policy.py:23` `may_stage`; `phrase_tables.yaml:832` keep / `:838` superseded | deterministic | On v21, 12 soft gates are skipped; 3 hard exits kept |
| 6 | Bound ESS self-read | `runner_surfaces.py:1034` `_try_bound_ess_self_read` (legacy only, `runner_pre_s1.py:233`) | 0-LLM | Answers a first-person read |
| 7 | Zero-LLM surface | `runner_surfaces.py:1201` `_try_zero_llm_surface` | 0-LLM | thanks / clock / FAQ / stated-fact recall |
| 8 | Plan-dial process draft | `runner_surfaces.py:1326` `_try_plan_dial_process_plan`; called `runner_pre_s1.py:249, 258` | 0-LLM | Drafts a plan (Plan dial / `process_id=plan`) |
| 9 | Chat write handoff | `handoff_agent.py`; `decision.py:243` turns a Chat write into `handoff_agent`; `runner_surfaces.py:760` builds the card | deterministic | ADR-0046 handoff (kept on v21) |
| 10 | Arbiter | `arbiter.py:20` precedence, `:65` `decide` | pure projection | **Does not decide**; it labels `ledger.turn_decision` from fired gate signals |
| 11 | `topic_guard` pre-LLM gate | `engine_runtime.py:163` → `:1169` `_check_topic_guard` | deterministic, before the turn | Refuses with the instance card; language-branched at `:1189` |
| 12 | `_is_declared_in_scope` rescue | `runner_util.py:142`; applied `runner_s1.py:238` | deterministic | Reclassifies `off_limits` → `platform` on the legacy path |
| 13 | `_refusal_text` | `runner_util.py:173` | copy | Language-branched refusal on the legacy path |
| 14 | Affirmation | `dialogue/affirmation.py:35` `is_affirmation` | deterministic | Drives router `confirm` (`router.py:140`) and plan commit (`runner_surfaces.py:1434`) |
| 15 | legacy spine S3–S6 | `runner_s2_plan.py:183`, `runner_s3_s5.py`, `runner_s6.py` | LLM draft + critic + render | Answers when the Decision falls through |

**Verdict.** The complaint is **not** exit competition between many equal routers: on the committed
v21 path the Decision is authoritative and the Arbiter is a projection, not a decider. It is
**fallthrough and pre-decision gates**:

- **V21-1 (fallthrough).** `_try_v21_understand` returns `None` and records `reason="fallthrough"`
  when the Decision produced no text (`runner_surfaces.py:885-891`); the turn then runs the legacy
  spine. ADR-0056 §Decision: *"There is no fallthrough."* The legacy spine is still live.
- **V21-2 (committed-route trap).** `TurnRouter` can set `committed=True` on a kind that v21
  supersedes. `REPORT_CLARIFY` (`router.py:204-220`, `committed=True`) skips `_try_v21_understand`
  (`runner_pre_s1.py:238`) but its exit is `may_stage("typed_router") == False` on v21
  (`runner_s1` superseded list, `phrase_tables.yaml:838`). Result: a broad-report Ask on v21 falls
  into the S3–S6 legacy draft. Candidate one-line, contract-compatible fix (to note, not implement):
  gate `try_report_clarify` the way `is_restyle_request` already is (`router.py:166`).
- **V21-3 (note: the metrics do not see it).** `chat_deep_bench` objective C4 "One decision" is
  `reached` and G5 `router_agreement` is 1.0 — but C4 scores the **Arbiter label projection** and G5
  scores the **recorded decision**, not whether a committed route blocked the Decision. There is no
  live bank that counts fallthroughs. Honest status: **missing** (ADR-0056 §Evidence gate item 1
  requires a "no-fallthrough" bank; it is not built).

---

## 3. Failure taxonomy (`IF-*`) — entry / exit / regression

**Seen** = a dated live or operator artifact names the class (any owning-bank run with a failing
thread; `_intention_class_status` → `seen`). **Fixed** = the last `CLOSE_RUNS = 3` consecutive full
live runs of every owning bank pass every thread naming it. **Regressed** = a later full run fails a
thread that had closed it (`intention_bank_status` → `fail`).

**Live evidence file naming.** One file per run:
`docs/pulse/evidence/PV2-intention-<IB-ID>-<YYYY-MM-DD>-<HHMM>.json`, `tier="live_intention"`
(write bank `IB-06`: `tier="live_intention_write"`). A run against the wrong pack writes
`PV2-intention-blocked-<YYYY-MM-DD>-<HHMM>.json` and the bank stays `missing`, never zero-fail.
Unit bank `IB-09` writes no live file; its evidence is the pytest node in
`backend/ai/tests/test_intention_banks.py`.

| Id | Class | Owning bank(s) | Exact pass criterion (per run, × `CLOSE_RUNS=3`) | Live evidence file | Honest now |
|---|---|---|---|---|---|
| **IF-01** | In-scope ask scope-refused (wrong-language card) | `IB-04`, `IB-05` | `IB-05` 10/10 threads: in-scope EN/AR `decision_not: [refuse]`, jailbreak EN/AR `decision_is: refuse`. `IB-04` `ib04-oos-*` `decision_is: refuse`; `ib04-inscope-*` `decision_not: [refuse]`. | `PV2-intention-IB04-*.json` + `PV2-intention-IB05-*.json` | **fixed** — IB-04/IB-05 reached 3/3 (2026-10-03). |
| **IF-02** | Greeting / small-talk answered as out-of-scope | `IB-04` | `ib04-greet-en`, `ib04-greet-ar`, `ib04-greet-en-2`, `ib04-greet-ar-2`: `decision_not: [refuse]`, `language` matches, `not_degraded: true`. | `PV2-intention-IB04-*.json` | **fixed** — IB-04 reached 3/3 (2026-10-03). |
| **IF-03** | Chat write intent answered as executable (ADR-0046) | `IB-06` | ≥ 4 threads EN/AR: exactly one `handoff_agent`; host row count unchanged after the turn. | `PV2-intention-IB06-*.json` (`tier=live_intention_write`) | **missing** — needs STACK-HOLD. |
| **IF-04** | Bound read restated, not answered | `IB-03` | 12 threads: the asked field is in the reply, or an explicit unknown; no raw-record dump (`id=`/`employee_no=` echo). | `PV2-intention-IB03-*.json` | **partial** — not separately scored. |
| **IF-05** | Unbound read met with a vague/non-answer | `IB-03` | absent field/record → explicit unknown; no invented figure. | `PV2-intention-IB03-*.json` | **partial**. |
| **IF-06** | Ask/Plan boundary crossed | `IB-06`, `IB-07` | read → no plan card; plan-shaped goal → exactly one plan/handoff; no read-only run of a multi-step goal. | `PV2-intention-IB07-*.json` | **missing**. |
| **IF-07** | Voice / register / persona-scope wrong | `IB-08` | per surface (coworker, tutor): 8 threads answer inside the declared scope + register. | `PV2-intention-IB08-*.json` | **missing**. |
| **IF-08** | Exit competition / fallthrough (V21-1, V21-2) | `IB-09` (unit), `IB-10` (live) | IB-09: 0 committed routes skip the Decision; 0 `reason="fallthrough"` on the golden set. IB-10: 0 `fell_through` over M ≥ 30 recorded turns. | IB-09 pytest; `PV2-intention-IB10-*.json` | **unit green; live missing**. |
| **IF-09** | Non-determinism (`pass^3`) | `IB-11` | 8 threads × 3 repeats: identical entity + figure all 3 times. | `PV2-intention-IB11-*.json` | **missing**. |

---

## 4. Honest coverage (RULE_36 — worst of dated live, week log, last 3 retests)

| Class | Scored bank today | Honest status |
|---|---|---|
| Grounding / fabrication (M01, M02) | `chat_retest_bank.yaml` threads; `PV2-chat-deep-2026-09-26.json` | **reached** via retest (`PV2-chat-retest-2026-09-30-1614.json`: C1–C10 true; 5 findings closed). Standalone `IB-01` is **missing**. |
| Language fidelity (C7) | retest thread `arabic-followups` | **reached** via retest. Standalone `IB-02` is **partial** (retest C7 only). |
| Entity resolution / unbound filter (M04) | retest threads `entity-by-number`, `unbound-filter` | **reached** |
| Truthful surface / Chat no-mutate (C5) | retest; `mode_behaviors.py` ASK-03/ASK-04 (locked) | **reached** |
| One decision (C4) | G5 96/96, `PV2-g5-2026-09-23r.json` | **reached** — but scores the Arbiter label, not fallthrough (see §2.3) |
| IF-01/IF-02 scope + greeting | `IB-04`, `IB-05` (live) | **fixed** — `IB-04` and `IB-05` reached: 10/10 threads on 3 consecutive live runs (2026-10-03, runs 1131/1132/1134). `scenarios_nibras.py` cases stay offline-stub and do not count. |
| IF-03 Chat write handoff | `multiturn/scripts/08-chat-handoff-write-01.yaml`; `mode_behaviors.py` | **unit-locked, live missing** |
| IF-04/IF-05 read answered vs restated | retest threads `salary-table`, `tes-unknown`; finding `tes-ungrounded` | **partial** — the field/unknown answer is not separately scored |
| IF-06 Ask/Plan boundary | `mode_behaviors.py` ASK/PLAN (locked) | **unit-locked, live missing** |
| IF-07 tutor/coworker register | — | **missing** (moodle tutor tests are unit) |
| IF-08 fallthrough / exit competition | `IB-09` unit (green); `IB-10` live (to build) | **unit green; live missing** (ADR-0056 requires the live bank; not built) |
| IF-09 determinism `pass^3` | `chat_deep_bench` M03 | **missing** (explicit in `PV2-chat-deep-2026-09-26.json`) |

Legend: **reached** = 3 consecutive live runs / all threads; **partial** = some axis; **missing** = no
live bank; a stub, a unit bank, or a single PASS never upgrades a miss.

---

## 5. Benchmark plan (`IB-*`)

Live banks run on the live Chat cell under the required pack. `STACK-HOLD` + `PULSE_NIGHTLY_LIVE=1`
are required **only** for the write bank (`IB-06`); the rest are read-only. `emp_1067` is the read
persona; do not grant it `people:view` to make a thread pass.

**One file per bank per run.** `docs/pulse/evidence/PV2-intention-<IB-ID>-<YYYY-MM-DD>-<HHMM>.json`,
`tier="live_intention"` (`IB-06`: `tier="live_intention_write"`). A blocked run (wrong pack) writes
`PV2-intention-blocked-<stamp>.json` and the bank stays `missing`, never zero-fail.

**`CLOSE_RUNS = 3`.** A bank reaches only when the last 3 consecutive **full** runs pass every
thread. A partial (`--only`) run never counts; a stub, a unit bank, or a single PASS never counts; a
later failing run reopens the bank and its `IF-*` class (`chat_deep_bench.intention_bank_status`).
**A bank with no live run stays `missing`, not passing.**

| Id | Purpose | Sample (threads × turns) | Language mix | Exact pass threshold | Tier | Evidence file | Honest now |
|---|---|---|---|---|---|---|---|
| **IB-01** | Grounding: every figure is in the payload (IRP-5) | 8 × 1–3 ≈ 16 | 4 EN / 4 AR | 100% threads; 0 ungrounded figures; an ungrounded figure → `pass=false` | live, read-only | `PV2-intention-IB01-*.json` | **missing** as a bank; grounding scored in `chat_retest` C2 (reached). |
| **IB-02** | Language fidelity incl. refusals/clarify (IRP-7) | 8 × 1–2 ≈ 12 | 6 EN / 6 AR | 100% threads; `detect_reply_language(reply)` = message language | live, read-only | `PV2-intention-IB02-*.json` | **partial** — retest `arabic-followups` + C7 reached. |
| **IB-03** | A read answers the asked field, or says unknown | 12 × 1 = 12 | 6 EN / 6 AR | field present or explicit unknown; no raw-record dump | live, read-only | `PV2-intention-IB03-*.json` | **partial**. |
| **IB-04** | Greeting + scope, bilingual | 10 × 1 = 10 | 5 EN / 5 AR | 10/10 threads | live, read-only | `PV2-intention-IB04-*.json` | **reached** — 3/3 runs 2026-10-03 (1131, 1132, 1134), 10/10 each. |
| **IB-05** | In-scope ask is never refused | 10 × 1 = 10 | 5 EN / 5 AR | 10/10 threads | live, read-only | `PV2-intention-IB05-*.json` | **reached** — 3/3 runs 2026-10-03 (1131, 1132, 1134), 10/10 each. |
| **IB-06** | Chat write → one handoff, host unchanged | ≥ 4 × 1 (+ `08-chat-handoff-write-01.yaml`) | 2 EN / 2 AR | exactly one `handoff_agent`; host count unchanged | live, **write** | `PV2-intention-IB06-*.json` | **missing** — needs STACK-HOLD. |
| **IB-07** | Ask/Plan boundary | 8 × 1 mirrored in both dials = 16 | 4 EN / 4 AR | read → no plan card; goal → one plan/handoff | live, read-only | `PV2-intention-IB07-*.json` | **missing**. |
| **IB-08** | Voice / register per surface | 8 × 1 per surface × 2 = 16 | 4 EN / 4 AR per surface | 100% threads answer inside declared scope + register | live, read-only | `PV2-intention-IB08-*.json` | **missing**. |
| **IB-09** | No-fallthrough (unit) | every committed route kind × v21 (≥ 12) | EN + AR | 0 committed routes skip the Decision; 0 `reason="fallthrough"` | unit | `backend/ai/tests/test_intention_banks.py` | **unit green; V21-2 closed**. |
| **IB-10** | No-fallthrough (live) | replay M ≥ 30 recorded turns | mixed | 0 `fell_through` in the ledger | live, read-only | `PV2-intention-IB10-*.json` | **missing**. |
| **IB-11** | Determinism `pass^3` | 8 × 3 repeats = 24 | 4 EN / 4 AR | identical entity + figure all 3 times | live, read-only | `PV2-intention-IB11-*.json` | **missing**. |

### 5.1 Bank rules

1. **One run is not three.** `reached` requires `CLOSE_RUNS = 3` consecutive full runs; honest status
   is the worst of those runs. A later fail reopens.
2. **No instrument = `missing`.** A bank not built, or blocked by the wrong pack, is `missing`; it is
   never counted as zero-fail or passing (`RULE_36`).
3. **Reported, not merged.** Intention banks are their own key in `chat_deep_bench`; they never move
   the Ask `C1–C10` score or the verdict.
4. **Read-only vs write.** Only `IB-06` needs `STACK-HOLD` + `PULSE_NIGHTLY_LIVE=1`. `IB-01`–`IB-05`,
   `IB-07`, `IB-08`, `IB-10`, `IB-11` are read-only. Do not start or kill `manage.sh` to create a bank.

---

## 6. Intention-Recognition ladder (`IR0`–`IR5`)

**This ladder is separate from the v2 intelligence ladder (`intelligence_ladder.py`).** Do **not**
label any level here as v2 `L6`/`L7`, and do **not** claim `L6`/`L7` anywhere from this work. The v2
`L6`/`L7` rungs remain governed by their own scorer and the standing "unclaimed" directive.

Entry is cumulative (as ADR-0051 Soundcheck): level N requires every criterion at `rank ≤ N`. **Exit
is the entry of the next level**: a level is claimable only when its own exit gate passes and it does
not regress a lower level.

| Level | Name | Entry (all lower levels exited) | Exit — gate → numeric threshold | Needs |
|---|---|---|---|---|
| **IR0** | **Declared** | — | This contract committed: the mechanism map, taxonomy, bench plan, one owning bank per class, and all 10 `IRP-*` rows name a command/field + failure value. Gate: this document; `python -m pytest backend/ai/tests/test_intention_banks.py -q` green. | offline, no live |
| **IR1** | **Single-decision** | IR0 | IB-09 green (0 committed-route skips) **and** `chat_deep_bench.fallthrough.status ≠ "fail"` **and** IB-10 reached: 0 `fell_through` over M ≥ 30 turns × 3 runs. Gates: `pytest -k intention`; `python -m ai.eval.chat_intention_retest --bank IB-10`; `python -m ai.eval.chat_deep_bench`. | live, read-only soak (3 runs); **no STACK-HOLD** |
| **IR2** | **Language- and scope-honest** | IR1 | IB-04 **and** IB-05 each reached: 10/10 threads × 3 consecutive runs, `pass=true` each. Gate: `python -m ai.eval.chat_intention_retest --bank IB-04 IB-05`. | live, read-only soak; **no STACK-HOLD** |
| **IR3** | **Read answered, not restated** | IR2 | IB-03 reached (field present or explicit unknown, no raw dump) **and** IB-01 reached (0 ungrounded figures), each × 3 runs. Gate: `python -m ai.eval.chat_intention_retest --bank IB-03 IB-01`. | live, read-only soak; **no STACK-HOLD** |
| **IR4** | **Mode- and voice-faithful** | IR3 | IB-07 reached **and** IB-08 reached: 100% threads × 3 runs (read → no plan card; goal → one plan/handoff; each voice in scope + register). Gate: `python -m ai.eval.chat_intention_retest --bank IB-07 IB-08`. | live, read-only soak; **no STACK-HOLD** |
| **IR5** | **Intelligence-proofed** | IR4 | IB-10 **and** IB-11 reached, **and** a locked paraphrase/adversarial bank (≥ 5 unseen paraphrases per intent) on 3 consecutive runs: decision accuracy ≥ 0.95, AR/EN parity ≥ 0.98, fallthrough 0, ungrounded numbers 0. Gates: `python -m ai.eval.g6_runner --mode understand --write`; `python -m ai.eval.chat_intention_retest --bank IB-10 IB-11`; `python -m ai.eval.chat_deep_bench`. | live soak (3 runs); **no STACK-HOLD** (no write) |

**STACK-HOLD statement.** `IB-06` (Chat write → one handoff) is the only bank that needs
`STACK-HOLD` + `PULSE_NIGHTLY_LIVE=1`. It is **not** part of `IR0`–`IR5`; it is a separate
Chat-write-trust precondition. No IR level may claim it, and no IR level requires it.

### 6.1 Definition of Done / Do NOT per level

| Level | Definition of Done | Do NOT — do not claim the level if |
|---|---|---|
| **IR0** | Contract committed; all 10 `IRP-*` rows carry an executable falsification; every `IF-*` names an owning bank; every `IB-*` has size, mix, threshold, tier, file, status. | the falsification column is empty for any IRP. |
| **IR1** | IB-09 + IB-10 green on 3 runs; V21-2 regression node passes; `fallthrough.status ≠ "fail"`. | you have only the unit IB-09; you count a unit as live; you set `PULSE_UNDERSTAND=legacy`. |
| **IR2** | IB-04 and IB-05 both 10/10 × 3 on one reloaded process, no regression. | you claim it from IB-04 alone, or count pre-reload runs. |
| **IR3** | IB-03 + IB-01 3/3; each bank `pass=true`. | the field answer is a raw-record dump, or a figure is ungrounded. |
| **IR4** | IB-07 + IB-08 3/3. | you score voice from a unit `mode_behaviors` golden. |
| **IR5** | IB-10 + IB-11 + the locked paraphrase bank on 3 runs at threshold; both `--gate` pass. | you claim v2 `L6`/`L7`, or score from a dated file pinned in code. |

---

## 7. Phased plan

Contract first; nothing below ships in this turn.

| Phase | Work | Contract-compatible? | Gate / status |
|---|---|---|---|
| **0 Contract** | This file + the canvas section. New ids only. | n/a | This document. |
| **1 Gate** | Build `IB-09` (no-fallthrough unit); expose the fallthrough counter in `chat_deep_bench`; V21-2 regression test. | Yes — no phrase table, no new `re.compile`, no golden loosened | `IB-09` green; V21-2 closed; counter present. Both `--gate` pass. |
| **2 Small fixes** | (a) gate `try_report_clarify` on v21; (b) every user-visible copy chooses language via `turn/language.py`; (c) absent-field unknown instead of a raw record; IRP-9 declared-scope rescue + typed refuse `cause`. | Yes — catalog/state/golden, not wording | (a) and (b) + rescue shipped; (c) still a candidate. Both `--gate` pass. |
| **3 Live evidence** | Build and run the read-only banks `IB-01`–`IB-05`, `IB-07`, `IB-08`, `IB-10`, `IB-11` as `emp_1067`. `IB-06` stays `missing` until a COMMS STACK-HOLD. | Yes | `IB-04` **reached** 3/3 (2026-10-03, 1131/1132/1134); `IB-05` **reached** 3/3; `IB-03`/`IB-01`/`IB-02`/`IB-07`/`IB-08`/`IB-10`/`IB-11` **missing**. 3 full runs per bank; honest = worst. |
| **4 Ladder** | Move `IR1` → `IR2` → `IR3` in the canvas, one level per cleared bank. Do not claim a level the bank denies. | Yes | `IR2` reached (IB-04 + IB-05, 3/3). `IR1` not reached (`IB-10` live bank not built). `IR0` reached. |

**Explicitly out of scope of the implementable set:** any new phrase table; any new routing
`re.compile`; any `StagedExit`; any host-domain or brand word in `engine/**`; loosening a YAML golden;
granting `people:view` to `emp_1067`; rewriting night `2026-09-23`; `pulse_gauge --write`.

---

## 8. Verification performed for this audit

- `python -m ai.eval.pulse_gauge --gate` → **pass** — *"no meter rose, no ladder level regressed"*
  (`re_compile` 45, `staged_exits` 3, `routing_phrase_sets` 226, `domain_terms_in_core` 0,
  `brand_literals_in_core` 0).
- `python -m ai.eval.pack_contract --gate` → pass on all four packs (`aast-med`, `carbon`, `eduos`,
  `nibras`; 0 violations).
- No `--write`. No engine edit. No golden change. No brand switch. No deploy/tag/push.

### Caveats this audit could not clear

1. **The greeting example was not in the historical baseline.**
   `docs/pulse/evidence/PV2-baseline-live-2026-09-22.json` contains no `كيف حالك` / `How are you`
   turn. The bilingual out-of-scope-card failure it *does* contain is `ess-loan-ar-01` turn 1: an
   Arabic in-scope loan ask answered with the identical English `topic_guard.refusal` card
   (`decision=refuse`, `lang=en expected ar`). The greeting turns are now covered by `IB-04`
   (`ib04-greet-en/ar` + `-2`), which reached 10/10 on 3 consecutive live runs (2026-10-03,
   1131/1132/1134).
2. **Exact wrong line for the English card.** The card text is `topic_guard.refusal`
   (`domain_packs/nibras/instance.yaml:1527`). Both code paths that can emit it are language-branched
   (`engine_runtime.py:1189`, `runner_util.py:178`) and the Arabic bank message has
   `arabic_ratio == 1.0`, so the committed English output cannot be reproduced offline. The wrong
   branch is real but the exact trigger (message text at that run vs. the committed bank) is unproven.
3. **`scenarios_nibras.py` topic_guard cases** are harness/stub checks, not a live bank; they do not
   upgrade IF-01/IF-02. IF-01/IF-02 close on `IB-04` + `IB-05` (live, reached), not on these.
4. **v2 `L6`/`L7`.** `pulse_gauge --gate` currently reads them `reached` from the scorer; per the
   standing directive this document does not claim them and does not restate that as a product claim.

---

## 9. Definition of Done (contract)

The contract is done, and may be called `IR0`, only when all of the following hold:

1. **Principles.** All 10 `IRP-*` rows name a command or ledger/meter field to read and the exact
   failure value; §1.1 maps each to its gate.
2. **Failure taxonomy.** All 9 `IF-*` rows name the owning `IB-*` bank(s), the exact per-run pass
   criterion, the live evidence filename, and the honest status.
3. **Banks.** All 11 `IB-*` rows define purpose, sample size (threads × turns), language mix, exact
   pass threshold, tier (unit vs live), evidence filename pattern, and honest status; `CLOSE_RUNS = 3`
   is stated and "one run is not three".
4. **Ladder.** All 6 `IR0`–`IR5` rows define entry and exit criteria with the exact gate command and
   numeric thresholds; `IB-06` / STACK-HOLD is stated as outside the ladder.
5. **Per level.** A Definition of Done and a Do NOT exist for each level (§6.1).
6. **Gates.** `python -m ai.eval.pulse_gauge --gate` and `python -m ai.eval.pack_contract --gate`
   pass with no meter rise. No `--write`.
7. **Canvas.** The canvas section mirrors §1 (stat cards), §3, §5, §6 and §7, and passes its Canvas
   TypeScript check with no errors.

## 10. Do NOT

- Do not claim Pulse v2 `L6`/`L7` from any `IR*` level, bank, or this document.
- Do not set `PULSE_UNDERSTAND=legacy` or `PULSE_TOOL_CHOICE=off` in committed defaults.
- Do not add a phrase table, a routing `re.compile`, or a `StagedExit` anywhere in `engine/**`.
- Do not add a host-domain or brand literal to `engine/**` (ADR-0050).
- Do not loosen a YAML golden; do not grant `people:view` to `emp_1067`.
- Do not `manage.sh` start/kill; do not post or consume `STACK-HOLD` (only `IB-06` needs it, and only
  under an approved write window); do not `--record` over night `2026-09-23`.
- Do not run `pulse_gauge --write` as part of claiming a level.
- Do not count a partial (`--only`) run, a stub, a unit bank, or a single PASS as three; a bank with no
  live run stays `missing`.
- Do not renumber or rewrite the signed Ask `10/10` (2035/2036/2038), the excellence grid `17/54`, or
  the Tasks board `R1`–`R12` / `P1`–`P8` / `B0`–`B6`.
