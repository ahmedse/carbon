# Pulse Plan Contract (ADR-0046 · 0047 · 0049 · 0050 · 0052 · 0055 · 0056)

- **Status:** Proposed — audit + benchmark surface. No behaviour change ships with this document.
- **Date:** 2026-10-03
- **Owner:** Pulse Master seat (Plan benchmarking surface)
- **Numbering:** this contract adds **new** identifiers only (`PLP-*`, `PF-*`, `PB-*`, `PL0`–`PL5`).
  It does **not** renumber the Intention contract (`IRP-*`, `IF-*`, `IB-*`, `IR0`–`IR5`), the
  signed Ask `10/10` (files 2035/2036/2038), the excellence grid `17/54`, or the Tasks board
  `R1`–`R12` / `P1`–`P8` / `B0`–`B6`.
- **Reads with:** `docs/pulse/PULSE-INTENTION-CONTRACT.md`,
  `docs/pulse/PULSE-V2-INTELLIGENCE-CONTRACT.md`,
  `.cursor/rules/pulse-2-1-contract.mdc`, `pulse-chat-agent-mode-contract.mdc`,
  `pulse-measurement-contract.mdc`, ADR-0046, 0047, 0049, 0050, 0052, 0055, 0056.

## 0. Why this document exists

The Intention contract scores what a turn **understands**. It does not score what a turn
**proposes**: the **Plan** dial, the Agent plan proposal, plan revision, await-user, and the
read-vs-goal boundary are measured today only by an offline 12-case bank
(`agent_plan_bank.yaml`) plus unit tests. The canvas has a Tasks ladder and an Intention ladder,
but **no Plan ladder**, and no bank states its own honest status. That is the gap this closes.

**Scope.** The Plan surface, three neighbours:

| Surface | Where | This contract |
|---|---|---|
| **Chat Plan** | `process_mode="plan"`, `Surface.CHAT_PLAN` | owns it |
| **Chat Ask** | `process_mode="ask"` | only the read-vs-goal **boundary** |
| **Agent / Tasks** | `plan_task` / `edit_plan` / `approve_plan`, `ReActLoop` run | only the **propose → Approve → Run** handoff and consent boundary |

A **read** ("what is my leave balance?") is a question. A **goal** ("apply for 3 days leave",
"build the salary distribution report") is a plan. The **planner decides**, not the wording
(`plan_proposal.is_task_plan`, `MIN_TASK_STEPS = 2`). This contract fixes that boundary, the typed
continuity that holds a plan across turns, and how the Plan benchmarks are reported.

**Plan is not Tasks.** Plan proposes and reviews; it stores nothing until consent
(ADR-0055) and never host-mutates from Chat (ADR-0046). Execution is Agent
(Plan → Approve → Run → RULE_21). The Tasks ladder (`R1`–`R12`) scores execution; this ladder
scores the proposal boundary. They are reported separately and never merged (RULE_36).

---

## 1. Principles (each falsifiable)

Commands run from `backend/` with `/home/ahmed/ws/carbon/.venv/bin/python`. A principle is
**falsified** when the field shows the failure value. "No instrument" is not a pass: a principle
whose instrument is not built is `missing`, never `reached`.

| Id | Principle | Falsified by — exact test / field / failure value |
|---|---|---|
| **PLP-1** | **A read is a question; a goal is a plan.** One bound read on the Ask dial is never a plan card; a goal decomposes. | `python -m ai.eval.agent_plan_runner --gate` → cases `ap-020`…`ap-024`. Failure = `is_task=True` for the single-read Ask case, or `payload != false`. |
| **PLP-2** | **Continuity is typed state, not prose.** A follow-up resolves against `ConversationState.open_question` (`kind="plan_revision"`), never a transcript marker scan. | `python -m pytest ai/tests/test_plan_revision_state.py -q`; runner cases `ap-005`/`ap-015`/`ap-016`. Failure = `pending_revision(state) is None` after the discuss reply, or a `DISCUSSION ONLY`-marker list reappears (measured as `routing_phrase_sets` rising). |
| **PLP-3** | **Affirmation is one module.** `apply` / `accept` / `اعتمدها` commit through `dialogue/affirmation.py` only; there is no apply allowlist in a planner/runner. | Runner cases `ap-037`…`ap-040`; `python -m pytest ai/tests/test_plan_revision_state.py -q`. Failure = `is_commit_affirmation` disagrees, or a marker/list name returns to `planner.py` / `runner_*.py`. |
| **PLP-4** | **Chat proposes; Agent applies (ADR-0046).** `edit_plan` / `approve_plan` are cancelled on every Chat surface, including the Plan dial. | Runner cases `ap-012`/`ap-019`; `python -m pytest ai/tests/test_plan_proposal_consent.py ai/tests/test_plan_lifecycle.py -q`. Failure = `chat_surface_hook(...).action != "cancel"`, or `"chat_no_host_mutation"` absent from flags. |
| **PLP-5** | **A confirmed revision is a 0-LLM handoff carrying the exact revision.** | Runner cases `ap-006`…`ap-008`; live bank `PB-02`. Failure = `response.llm_calls != 0`, or `action["revision"]` missing/≠ the confirmed text. |
| **PLP-6** | **await-user pauses.** A step that collects an answer pauses the run; later steps do not run. | Runner cases `ap-027`…`ap-030`; `python -m pytest ai/tests/test_plan_await_user.py -q`. Failure = `pause_for_user_answer(ask_clarification step)` returns `None`, or `paused is False`. |
| **PLP-7** | **Guards are typed.** A guarded branch resolves to `run` / `skip` / `pause`; two effects without an exclusive guard is a `branch` finding (ADR-0052 I4). | Runner cases `ap-031`…`ap-034`; `plan_contract_bank.yaml`; `python -m pytest ai/tests/test_plan_contract.py -q`. Failure = `guard_outcome` outside `{run,skip,pause}`, or a blocked-code mismatch vs the golden. |
| **PLP-8** | **Output-fit.** A file may contain only fields a catalog entry declares. An unnamed export binds to closed-aggregate `returns`, or is a gap. | `plan_contract_bank.yaml` cases with `blocking: [output_fit]`; runner case `ap-024`. Failure = blocked-code mismatch. |
| **PLP-9** | **No phantom success.** An invented host API degrades to a `gap`, never reaches Approve as a call. | Runner case `ap-041`; `python -m pytest ai/tests/test_plan_contract_db.py -q`. Failure = `step.tool_name` still set, or `confirm_step` does not raise `gap:`. |
| **PLP-10** | **A proposal stores nothing until consent (ADR-0055).** Drafting writes no `Run` / `RunStep`. | `python -m pytest ai/tests/test_plan_proposal_consent.py -q` (`test_drafting_stores_nothing`). Failure = `Run.objects.count()` rises on draft. |
| **PLP-11** | **No new phrase tables, no routing `re.compile`, no `StagedExit`, no host-domain or brand words in `engine/**`** (ADR-0050). | `python -m ai.eval.pulse_gauge --gate`; `python -m ai.eval.pack_contract --gate`. Failure = either gate exits 1, any meter rises, or `domain_terms_in_core` / `brand_literals_in_core` > 0. |
| **PLP-12** | **Report honesty (RULE_36).** An offline pass never closes a live rung; no live evidence is `missing`, never zero-fail. | `python -m ai.eval.plan_bench`. Failure = a `PL-*` bank shows `reached` with `< CLOSE_RUNS` full runs, or the Plan report moves a Chat/Tasks/ladder score. |

### 1.1 Hard rules (do / don't) — each names its gate

| Rule | Do | Don't | Enforced by |
|---|---|---|---|
| PLP-1 | Let `is_task_plan` decide; show one read as a draft only on Plan (`single_read=True`). | Coerce a read into a task; gate on the word "plan". | `agent_plan_runner` `proposal` cases |
| PLP-2 | Resolve follow-ups from `state.open_question`. | Scan history for `DISCUSSION ONLY`; regex-search the transcript for a plan id after turn 1. | `test_plan_revision_state.py`; `routing_phrase_sets` |
| PLP-3 | Commit via `dialogue/affirmation.py`. | Add an `apply`/`accept` allowlist in `planner.py` / `runner_*.py`. | runner `affirmation` cases |
| PLP-4 | One honest handoff (`open_panel` → Tasks); Agent applies. | Ask Chat to call `edit_plan` / `approve_plan`. | `ap-012`/`ap-019`; `test_plan_proposal_consent.py` |
| PLP-5 | Carry the reviewed revision verbatim with `llm_calls=0`. | Re-decompose on apply; drop `revision`. | runner `commit` cases; `PB-02` |
| PLP-6 | Pause at `ask_clarification`; resume when answered. | Run later steps past an unanswered question. | `test_plan_await_user.py`; `ap-027`…`ap-030` |
| PLP-7 | Give two effects exclusive guards or a dependency. | Ship two effectful steps neither of which depends on the other. | `plan_contract_bank.yaml`; PLP-8 |
| PLP-8 | Name only declared `returns`; bind an unnamed export to closed aggregates. | Let a row-list fill a distribution workbook. | `plan_contract_bank.yaml` |
| PLP-9 | Degrade an unknown API to `gap`. | Let a hallucinated `api_name` reach Approve. | `ap-041`; `test_plan_contract_db.py` |
| PLP-10 | Draft in memory; store on consent. | Persist a `Run` on propose. | `test_plan_proposal_consent.py` |
| PLP-11 | Put vocabulary in the pack. | Add a phrase table / router regex / `StagedExit` / domain or brand word to `engine/**`. | `pulse_gauge --gate`; `pack_contract --gate` |
| PLP-12 | Report `missing` when there is no live run. | Promote a unit bank or a single PASS to a live rung. | `plan_bench`; RULE_36 |

---

## 2. Mechanism map — where a plan is decided today

Read from the code, not memory. Two dials, one planner:

| # | Mechanism | file | Kind | Role |
|---|---|---|---|---|
| 1 | Plan-dial process draft | `runner_surfaces.py::_try_plan_dial_process_plan`; called `runner_pre_s1.py` (Plan dial / `process_id=plan`) | 0-LLM | Drafts from a governed process dial; owns the turn via `plan_dial_process` |
| 2 | `SkillAwarePlanner.decompose` | `plan/planner.py:968` | skill-first, LLM-fallback | Produces a `Plan`; `force_decompose` for explicit tasks; single-step fallback |
| 3 | Catalog compile | `plan/compile.py::compile_catalog_plan`, `planner._catalog_compile` | 0-LLM | Authors the DAG from catalog `returns` when it covers the brief |
| 4 | Procedural composite | `plan/process_dial.py::materialize_*_plan` | 0-LLM | Loan / attendance / leave composite with guards and parallel reads |
| 5 | Plan contract | `plan/contract.py::apply_plan_contract` (ADR-0052) | pure | One save-time authority: repairs what is mechanical, blocks what is not |
| 6 | Proposal | `turn/plan_proposal.py::proposal_payload` | pure | Read-vs-goal boundary (`is_task_plan`, `MIN_TASK_STEPS=2`); the client paints it |
| 7 | Revision state | `turn/plan_revision.py` | pure | Typed `plan_revision` question on `ConversationState`; 0-LLM handoff on confirm |
| 8 | Affirmation | `dialogue/affirmation.py` | pure | Sole resolver for commit words (EN + AR) |
| 9 | Await-user / guard | `plan/loop.py::pause_for_user_answer`, `resume_answered_clarification`; `contract.py::guard_outcome` / `guard_choice` | pure | Pauses a run; types an unresolved guard |
| 10 | Consent guard | `agent/guardrails.py::chat_surface_hook` | pure | Cancels `edit_plan` / `approve_plan` on Chat (ADR-0046) |
| 11 | Persisted lifecycle | `plans_service.PlansService` (`create_plan`, `commit_proposal`, `confirm_step`, `_run_plan_frames_sync`) | Django | Stores on consent; Approve then Run (RULE_21) |
| 12 | Plan-status recall | `turn/plan_status.py` | 0-LLM | `active_plans` status, no new write |

**Verdict.** Plan is already a typed chain, not a phrase forest: the planner decides read-vs-goal
(#2/#6), continuity is state (#7), consent is a guard (#10), and the contract is one authority
(#5). What was missing was **measurement**: one offline bank, no live bank, no honest status, no
ladder. This contract adds them; it does not change the chain.

---

## 3. Failure taxonomy (`PF-*`) — entry / exit / regression

**Seen** = a dated live or unit artifact names the class (any owning-bank run with a failing case;
`plan_bench` → `seen`). **Fixed** = the last `CLOSE_RUNS = 3` consecutive full runs of every
owning **live** bank pass every row naming it. **Regressed** = a later full run fails a row that
had closed it. Offline-only classes (no live bank) can be `offline_green` but never `fixed`;
a class whose only bank is offline is `partial`.

**Live evidence file naming.** One file per run:
`docs/pulse/evidence/PV2-plan-<PB-ID>-<YYYY-MM-DD>-<HHMM>.json`, `tier="live_plan"`. A run against
the wrong pack / no cell writes `PV2-plan-blocked-<YYYY-MM-DD>-<HHMM>.json` and the bank stays
`missing`, never zero-fail. Offline banks write `PV2-plan-offline-<YYYY-MM-DD>.json`
(`tier="plan_offline"`); their evidence is the pytest node in `backend/ai/tests/test_plan_bench.py`.

| Id | Class | Owning bank(s) | Exact pass criterion (per run, × `CLOSE_RUNS=3` for live) | Live evidence | Honest now |
|---|---|---|---|---|---|
| **PF-01** | Read yields a plan card | `PB-01` (live), `OB-01` (`ap-020`/`ap-021`) | 16/16 live rows: `no_plan_card=true` for reads; `OB-01` single-read Ask `is_task=false`, `payload=false`. | `PV2-plan-PL01-*.json` | **offline_green; live missing** |
| **PF-02** | Goal yields no plan | `PB-01` (live), `OB-01` (`ap-022`/`ap-023`) | 16/16 live rows: `plan_or_handoff=true` for goals; offline two-read goal `is_task=true`. | `PV2-plan-PL01-*.json` | **offline_green; live missing** |
| **PF-03** | Plan revision loses typed state | `PB-02` (live), `OB-01` (`ap-005`/`ap-015`/`ap-016`) | 8/8 live rows; offline `pending_revision` present and follow-ups resolve. | `PV2-plan-PL02-*.json` | **offline_green; live missing** |
| **PF-04** | Chat Plan mutates host / calls `edit_plan` | `PB-01` (`no_host_write`), `OB-01` (`ap-012`/`ap-019`), `test_plan_proposal_consent.py` | offline: guard `cancel` + `chat_no_host_mutation`; live: `host_write=false`. | `PV2-plan-PL01-*.json` | **offline_green; live missing** |
| **PF-05** | await-user unresolved (run continues) | `PB-03` (live), `OB-01` (`ap-027`…`ap-030`) | offline: `paused=true` / `resumed=true`; live: a missing fact → a question, no host write. | `PV2-plan-PL03-*.json` | **offline_green; live missing** |
| **PF-06** | Approve/Run boundary crossed (stored before consent) | `OB-01` (`ap-006`…`ap-010`), `test_plan_proposal_consent.py`, `test_plan_lifecycle.py` | `ap-009`/`ap-010` do not commit; `test_drafting_stores_nothing` (`Run` count unchanged); `plan_task` → `pending_approval`. | pytest node | **offline_green** |
| **PF-07** | Invented host API reaches Approve (phantom success) | `OB-01` (`ap-041`), `OB-02`, `test_plan_contract_db.py` | unknown `api_name` → step `tool_name=None` + `gap`; `confirm_step` raises `gap:`. | pytest node | **offline_green** |
| **PF-08** | File claims undeclared fields | `OB-02` (`output_fit` cases), `test_plan_contract.py` | blocked codes match the golden; export dropped with `gap="declared output"`. | pytest node | **offline_green** |
| **PF-09** | Two effects with no exclusive guard | `OB-02` (`branch` cases), `test_plan_contract.py` | `branch` finding present unless exclusive guards / dependency exist. | pytest node | **offline_green** |
| **PF-10** | Handoff language/register wrong | `OB-01` (`ap-008`), `test_plan_revision_state.py::test_arabic_reply_gets_arabic_handoff_copy`; live `PB-02` AR rows | AR message → AR handoff copy (`تطبيق في الوكيل`). | pytest node; `PV2-plan-PL02-*.json` | **offline_green; live missing** |
| **PF-11** | Affirmation over-matches | `OB-01` (`ap-009`/`ap-010`/`ap-018`/`ap-040`), `test_plan_revision_state.py` | a long sentence containing "apply" does not commit; `is_commit_affirmation` gates. | pytest node | **offline_green** |

Legend: **offline_green** = the owning offline bank/tests pass; **live missing** = no `PV2-plan-*`
run; **fixed** = 3 consecutive full live runs (none yet for Plan).

---

## 4. Honest coverage (RULE_36 — worst of dated live, week log, last 3 retests)

| Class | Scored today | Honest status |
|---|---|---|
| Read-vs-goal boundary (PF-01/PF-02) | `OB-01` offline (`ap-020`…`ap-024`); `IB-07` scores only the live *intention* boundary | **offline_green; live missing** — no `PV2-plan-PL01-*` run |
| Typed revision continuity (PF-03) | `OB-01` offline + `test_plan_revision_state.py` | **offline_green; live missing** |
| Consent / no-mutate (PLP-4/PF-04) | guard cases + `test_plan_proposal_consent.py` | **offline_green; live missing** |
| await-user / guards (PF-05/PF-09) | `ap-027`…`ap-036` + `test_plan_await_user.py` + `test_plan_contract.py` | **offline_green** |
| Output-fit / phantom success (PF-07/PF-08) | `OB-02` + `test_plan_contract*.py` | **offline_green** |
| Approve/Run boundary (PF-06) | `test_plan_proposal_consent.py` + `test_plan_lifecycle.py` | **offline_green** |
| Language fidelity (PF-10) | `ap-008` + AR unit tests | **offline_green; live missing** |
| Affirmation typing (PF-11) | `ap-009`/`ap-010`/`ap-018`/`ap-040` + shared module | **offline_green** |
| Live Chat Plan surface | — | **missing** — local cell is `aastmt/carbon`; the `nibras` cell is down |

Legend: **offline_green** = offline bank + unit tests pass; **missing** = no live bank; a stub, a
unit bank, or a single PASS never upgrades a miss.

---

## 5. Benchmark plan (`OB-*` offline, `PB-*` live)

Offline banks are **0-LLM, deterministic, no Django required**. Live banks run on the live Chat
cell under the required pack. **Plan never host-mutates**, so **no `PB-*` bank needs
STACK-HOLD**; they are read-only. `emp_1067` is the read persona; do not grant it `people:view`.

**Evidence files.** Offline `docs/pulse/evidence/PV2-plan-offline-<YYYY-MM-DD>.json`
(`tier="plan_offline"`). Live `docs/pulse/evidence/PV2-plan-<PB-ID>-<YYYY-MM-DD>-<HHMM>.json`
(`tier="live_plan"`). Blocked live run → `PV2-plan-blocked-<stamp>.json`, bank stays `missing`.

**`CLOSE_RUNS = 3`.** A live bank reaches only when the last 3 consecutive **full** runs pass every
row. A partial (`--only`) run never counts; a stub, a unit bank, or a single PASS never counts; a
later failing run reopens the bank and its `PF-*` class (`plan_bench.live_status`).
**A bank with no live run stays `missing`, not passing.**

| Id | Purpose | Sample | Language mix | Exact pass threshold | Tier | Evidence file | Honest now |
|---|---|---|---|---|---|---|---|
| **OB-01** | Plan path bank: seed, continuity, commit, guard, proposal, await-user, affirmation | 41 cases | EN + AR | 100% cases; 0 misses | offline unit, 0-LLM | `PV2-plan-offline-<date>.json` | **reached** (41/41) |
| **OB-02** | ADR-0052 contract goldens: shapes, guards, output-fit, branch | 32 cases | EN | 100% cases; blocked codes match the golden | offline unit, 0-LLM | `PV2-plan-offline-<date>.json` | **reached** (32/32) |
| **PB-01** | Ask/Plan boundary: read → no plan card; goal → one plan/handoff; no host write | 8 threads × 2 dials = 16 rows | 4 EN / 4 AR | 100% rows | live, read-only | `PV2-plan-PL01-*.json` | **missing** (needs a nibras cell) |
| **PB-02** | Plan-revision continuity: discuss seed stays a revision; `apply` → 0-LLM handoff | 4 threads × 2 turns = 8 rows | 2 EN / 2 AR | 100% rows; apply `llm_calls=0`; no host write | live, read-only | `PV2-plan-PL02-*.json` | **missing** (needs a nibras cell + a seeded plan) |
| **PB-03** | await-user honesty: a goal missing a fact asks one question | 4 threads × 1 = 4 rows | 2 EN / 2 AR | 100% rows; asks a question; not degraded; no host write | live, read-only | `PV2-plan-PL03-*.json` | **missing** (needs a nibras cell) |

### 5.1 Bank rules

1. **One run is not three.** A live `reached` requires `CLOSE_RUNS = 3` consecutive full runs;
   honest status is the worst of those runs. A later fail reopens.
2. **No instrument = `missing`.** A bank not built, or blocked by the wrong pack, is `missing`;
   never zero-fail or passing (`RULE_36`).
3. **Reported, never merged.** Plan is its own key in `plan_bench`; it never moves the Chat Ask
   `C1–C10` score, the Tasks board, or the v2 ladder.
4. **Read-only.** Every `PB-*` bank is read-only (Plan proposes; Agent applies). No STACK-HOLD.
5. **Offline never closes a live rung.** `OB-01`/`OB-02` green is `PL0`–`PL2`, not `PL3`.

---

## 6. Plan ladder (`PL0`–`PL5`)

**This ladder is separate from the v2 intelligence ladder (`intelligence_ladder.py`) and from the
Intention ladder (`IR0`–`IR5`).** Do **not** label any level here as v2 `L6`/`L7`, and do **not**
claim `L6`/`L7` anywhere from this work. Entry is cumulative: level N requires every criterion at
`rank ≤ N`. **Exit is the entry of the next level.**

| Level | Name | Entry (all lower levels exited) | Exit — gate → numeric threshold | Needs |
|---|---|---|---|---|
| **PL0** | **Declared** | — | This contract committed; `python -m ai.eval.agent_plan_runner --gate` → 100% (73/73 today: 41 path + 32 contract); `python -m pytest ai/tests/test_plan_bench.py -q` green. | offline, no live |
| **PL1** | **Typed-state** | PL0 | `test_plan_revision_state.py`, `test_plan_await_user.py`, `test_plan_contract.py` all green; runner `continuity`/`commit`/`await_user`/`guard`/`affirmation` cases 100%; no new phrase table / router regex (`pulse_gauge --gate`). | offline, no live |
| **PL2** | **Consent boundary** | PL1 | `test_plan_proposal_consent.py` + `test_plan_lifecycle.py` green; runner `ap-006`…`ap-012`/`ap-019` 100% (Chat proposes; Agent applies; draft stores nothing). | offline, no live |
| **PL3** | **Live boundary** | PL2 | `PB-01` reached: 16/16 rows × 3 consecutive full runs, `no_host_write`. Gate: `python -m ai.eval.chat_plan_retest --bank PL-01`; `python -m ai.eval.plan_bench`. | live, read-only soak (3 runs); **no STACK-HOLD** |
| **PL4** | **Live revision** | PL3 | `PB-02` reached: 8/8 rows × 3 runs, apply `llm_calls=0`, no host write, and `PB-01` not regressed. Gate: `python -m ai.eval.chat_plan_retest --bank PL-02`. | live, read-only soak (3 runs); **no STACK-HOLD** |
| **PL5** | **Live await-user + honesty** | PL4 | `PB-03` reached: 4/4 rows × 3 runs (asks a question, not degraded, no host write), and `PB-01` + `PB-02` not regressed. Gates: `python -m ai.eval.chat_plan_retest --bank PL-03`; `python -m ai.eval.plan_bench --write`. | live, read-only soak (3 runs); **no STACK-HOLD** |

**STACK-HOLD statement.** **No Plan level requires STACK-HOLD.** Plan never host-mutates from Chat
(ADR-0046); every live bank is read-only. `PL3`–`PL5` require a **live nibras cell**, not a write
window. There is no Plan write bank.

### 6.1 Definition of Done / Do NOT per level

| Level | Definition of Done | Do NOT — do not claim the level if |
|---|---|---|
| **PL0** | Contract committed; every `PLP-*` names a command/field + failure value; every `PF-*` names an owning bank; every bank has size, mix, threshold, tier, file, status. | any `PLP-*` falsification column is empty. |
| **PL1** | Typed-state tests green and runner continuity/guard/await-user/affirmation cases 100%. | you count a live rung; or a marker list was added to pass a case. |
| **PL2** | Proposal stores nothing; `edit_plan`/`approve_plan` cancel on Chat. | you score consent from a UI flip or a unit stub alone. |
| **PL3** | `PB-01` 16/16 × 3 on one reloaded process, `no_host_write`. | you claim it from `IB-07` (a different contract), a partial run, or a stub. |
| **PL4** | `PB-02` 8/8 × 3, apply 0-LLM; `PB-01` not regressed. | the plan precondition was not seeded, or a single PASS is counted. |
| **PL5** | `PB-03` 4/4 × 3; `PB-01` + `PB-02` not regressed; both `--gate` pass. | you claim v2 `L6`/`L7`, or pin a dated evidence file in code. |

### 6.2 Current honest standing

- **PL0 reached** — contract committed; both offline banks green.
- **PL1 reached** — typed-state offline tests green.
- **PL2 reached** — consent-boundary offline tests green.
- **PL3–PL5 missing** — no live `PV2-plan-*` evidence. The local cell is `aastmt/carbon`; the
  `nibras` cell is down, and the runner refuses to score off the wrong pack (it writes a blocked
  note and the bank stays `missing`). No brand switch, no fabricated run.

---

## 7. Phased plan

Contract + benchmarks only; nothing below changes product behaviour.

| Phase | Work | Contract-compatible? | Gate / status |
|---|---|---|---|
| **0 Contract** | This file. New ids only. | n/a | This document |
| **1 Offline gate** | Deepen `agent_plan_bank.yaml` + `plan_contract_bank.yaml`; extend `agent_plan_runner` with `proposal` / `await_user` / `guard` / `affirmation` / `contract` and aggregate scoring; `--gate` fails on any miss. | Yes — no phrase table, no `re.compile`, no golden relaxed | `agent_plan_runner --gate` → 73/73 |
| **2 Live banks** | `chat_plan_bank_pl0{1,2,3}.yaml` + `chat_plan_retest.py` (discovered registry, nibras pack boundary, blocked note). | Yes | `chat_plan_retest --list` green; runs blocked (no nibras cell) |
| **3 Report** | `plan_bench.py` — offline score + live honest status; `--write` → `PV2-plan-report-<date>.json`. | Yes | `plan_bench` → offline pass, live `missing` |
| **4 Ladder** | Move `PL0` → `PL1` → `PL2` in the canvas from the offline gates; `PL3`–`PL5` stay missing until a nibras cell and 3 runs. Do not claim a level a bank denies. | Yes | `PL0`–`PL2` reached; `PL3`–`PL5` missing |

---

## 8. Verification performed for this audit

- `python -m ai.eval.agent_plan_runner --gate` → **pass**, **73/73** (path 41/41, contract 32/32).
- `python -m ai.eval.plan_bench` → offline **73/73** gate pass; **PL-01/PL-02/PL-03 missing**
  (0/3 runs) — honest, no fabricated live run.
- `python -m pytest ai/tests/test_plan_bench.py` → **14 passed**.
- `python -m pytest` on all 15 owned plan test files + `test_plan_bench.py` → **208 passed**
  (includes the pre-existing `test_pv2_plan_status.py::test_create_plan_writes_active_plans`
  fake signature, repaired to accept `model=`).
- `python -m ai.eval.pulse_gauge --gate` → **pass** (no meter rose).
- `python -m ai.eval.pack_contract --gate` → pass on all four packs.

### Caveats this audit could not clear

1. **No live Plan run.** The nibras cell is down; `chat_plan_retest` writes a `plan_blocked` note
   and the banks stay `missing`. Since it is a live-only instrument, it was not run here.
2. **`PB-02` needs a seeded plan.** The FE discuss handoff links via `state.active_plans`; a live
   API run must first create the plan. The bank states this as a `precondition`.
3. **`plan_bench.py` duplicates contract-catalog shapes.** `agent_plan_runner` carries the ADR-0052
   catalog so it can score `plan_contract_bank.yaml` without importing a test module. The golden
   test (`test_plan_contract.py`) and the runner must agree; both are green today.
4. **v2 `L6`/`L7`.** `pulse_gauge --gate` reads them `reached` from its own scorer; per the standing
   directive this document does not claim them and does not restate that as a product claim.

---

## 9. Definition of Done (contract)

The contract is done, and may be called `PL0`, only when all of the following hold:

1. **Principles.** All 12 `PLP-*` rows name a command/field to read and the exact failure value;
   §1.1 maps each to its gate.
2. **Failure taxonomy.** All 11 `PF-*` rows name the owning bank(s), the per-run pass criterion,
   the live evidence filename, and the honest status.
3. **Banks.** All 5 `OB-*`/`PB-*` rows define purpose, sample, language mix, exact threshold, tier,
   evidence filename, and honest status; `CLOSE_RUNS = 3` is stated and "one run is not three".
4. **Ladder.** `PL0`–`PL5` define entry and exit with the exact gate command and numeric
   thresholds; the STACK-HOLD-free statement is explicit and no Plan level needs a write window.
5. **Per level.** A Definition of Done and a Do NOT exist per level (§6.1).
6. **Gates.** `agent_plan_runner --gate`, `pulse_gauge --gate`, `pack_contract --gate` pass; the
   owned Plan test files pass. No `pulse_gauge --write`.
7. **Report.** `plan_bench` reports the offline score and each live bank's honest status; a live
   bank with no run is `missing`.

## 10. Do NOT

- Do not claim Pulse v2 `L6`/`L7` from any `PL*` level, bank, or this document.
- Do not claim `PL3`–`PL5` from an offline bank, a stub, a partial (`--only`) run, or a single PASS.
- Do not set `PULSE_UNDERSTAND=legacy` or `PULSE_TOOL_CHOICE=off` in committed defaults.
- Do not add a phrase table, a routing `re.compile`, or a `StagedExit` anywhere in `engine/**`.
- Do not add a host-domain or brand literal to `engine/**` (ADR-0050).
- Do not loosen a YAML golden or a budget; do not grant `people:view` to `emp_1067`.
- Do not teach Chat to call `edit_plan` / `approve_plan`; Agent applies (ADR-0046).
- Do not count a unit bank as live, or merge the Plan report into the Chat Ask / Tasks / ladder scores.
- Do not `manage.sh` start/kill; do not post or consume `STACK-HOLD` (no Plan bank needs it); do not
  `--record` over night `2026-09-23`; do not run `pulse_gauge --write`.
- Do not switch brands to make a live bank run; a wrong pack writes a blocked note and stays `missing`.
