# Pulse — Declared output is the only success

> **Status:** Wave A + Wave B landed offline (2026-09-25). Named GET `analyze_committed_pay` is in the catalog (ADR-0059). No live run.
> **Date:** 2026-09-25
> **Canvas:** Pulse 2.1 · P22 · H7 · incidents I-9 / I-10
> **Does not move:** L6 / L7 · soak night 2026-09-23 · ADR-0049 Proposed

## What this solves

Runs `dbe99353` (`ahmed`) and `b040714a` (`emp_2378`) proved the same hole:

- The brief asked for salary distribution (average, median, range, payroll cost by org / nationality / position / employment status, latest committed payroll).
- The catalog can list payslip lines and count heads. It cannot produce those columns.
- Observe and the critic **saw** the miss.
- The loop discarded both, stuffed a table so Excel could exist, marked compute **Finished**, and in `b040714a` shipped headcount as the report.

That is not a missing API problem first. It is Pulse claiming success on a plan that could never succeed.

Permission was not the issue. `emp_2378` is People lead (`people:manage` → `people:view` + `people:view_compensation`). Host calls returned 200.

## Better than “refuse, then add the GET”

The instinct is right: **do not add a salary-metrics GET until Pulse can tell the user this report is not gettable.**

The improvement: honesty is **catalog-generic**, and it is **not only a Chat sentence**.

If Wave A only teaches Pulse to say “not gettable” and Wave B adds the GET, the loop still:

1. Stuffs a `structured_synthesis` table into a tool-less step so `export_document` can fire (ADR-0053 mask).
2. Honours `{step, field, select}` on path `{id}` only — query filters (e.g. `payroll_run`) are ignored.
3. Marks `completed` after `no_effect` / veto — the chip says Finished.
4. Parses the critic verdict from the **observe rewrite**, not the critic draft.
5. Ships a second export from fiction.

Wave A must close that lie machinery. Wave B is then a clean experiment: one catalog line appears → Pulse proposes a short plan that calls it and exports **that** payload.

Do **not** write a salary-report special case in `engine/**` (no payslip / salary / GOSI / brand words). The salary-structure brief is a **probe in the bank**. The contract is: every declared field of the requested deliverable is produced by a catalog entry the actor can call, or the turn is a typed gap.

## Wave 0 — Goldens first (failing)

Write the failing goldens before any product change. Same brief, three surfaces:

| Surface | Probe | Expected now (fail) | Expected after Wave A |
|---|---|---|---|
| Chat | Salary-structure ask as `emp_2378` scope | Calls `analyze_employees` / answers as if the report exists | Honest gap / handoff. Names what exists (headcount) and what does not (avg / median / range / cost). No invented figures. |
| Plan propose | Same brief | Proposal with host reads + export, no output-fit block | `apply_plan_contract` at propose. Blocked / `step.gap`. No `export_document` until evidence exists. User sees why before Create task. |
| Plan loop (offline) | Replay `b040714a` shape | Stuffing, path-only bind, Finished after no_effect, critic parsed from observe | No stuffing. Query bind honoured. Critic verdict from critic `draft_text`. `completed` only without `failure_class`. No artifact. |

Bank / pack / instance YAML only. `python -m ai.eval.pack_contract --gate` and `domain_terms_in_core` stay 0.

## Wave A — Refuse (no People GET)

### A1. Contract at propose

`apply_plan_contract` runs at `propose_plan` the same way it runs at Approve / resume. The object the user reviews is the judged object (P21 completed).

### A2. I1 is output-fit, not name-exists

Deepen ADR-0052 I1 (or ADR-0057 if the cut is cleaner):

- A host step is capable only when a catalog entry **declares** the fields the step claims to produce.
- A plan / Chat turn that requests a deliverable whose fields no entry declares is `step.gap` / blocked, not a nearest-API walk.
- Finding codes stay typed (`gap`, missing capability, missing fields). Permission stays a host 403, not an engine guess.
- The **client** paints the sentence from `finding.detail`. The engine does not hard-code “this salary report is not gettable because…”.

### A3. No stuffing

Delete `_enforce_structured_export_source` injecting a table into a tool-less step. I3 already says: no evidence → no export. The loop currently violates that so a file can exist.

### A4. Bind for path and query

`{step, field, select}` is one dialect. `host_args` must not lift a dict-as-bind only for path keys. `resolve_bindings` must not return `status: none` when query keys are still unbound.

### A5. One deliverable write

One `export_document` after evidence. Kill `_coerce_export_steps` / `_ensure_export_deliverable` (Excel-from-wording) in the same change as H4 already listed. No intermediate xlsx from a compute hop.

### A6. Critic is not an export hop

`REVIEW_INSTRUCTION` verdict is parsed from the critic `draft_text` (last JSON object, existing helper). Observe rewrite is not the verdict. Observe failure stays in `step_contexts` so later steps can see it — today contexts are filled from `draft_text` only, and bound GETs skip draft/observe.

### A7. Finished means it produced the effect

`completed_ids.add` only when the step completed and has no `failure_class` / is not `no_effect`. UI label Finished = that set. A run that is all-terminal with failed writes is failed; compute chips must not say Finished.

### Wave A exit

**Offline**

- Wave 0 goldens green.
- Targeted tests only (contract, loop, bind, propose, task-status). No full backend suite.
- `python -m ai.eval.pulse_gauge --gate`
- `python -m ai.eval.pack_contract --gate`
- No new `re.compile`, phrase table, or brand / domain word in `engine/**`.

**Live (only after STACK-HOLD)**

- Actor: `emp_2378` / `mozafNibrasPa_132`.
- Chat: the report is not gettable; says why from the finding; does not invent averages.
- Plan propose: blocked / gap; user sees it before Create task.
- If someone still Runs a pre-H7 plan: no new xlsx from stuffing; no Finished on no_effect.
- No `manage.sh` start/kill. Night 2026-09-23 FAIL stays. No `people:view` for `emp_1067`.

## Wave A+ — Request write (not a Chat sentence)

When output-fit blocks, the remaining effect is a catalog entry with `kind: request`. Body is the typed findings plus the brief. Chat proposes; Agent or the Correspondence UI submits (ADR-0046). The host defaults `org_unit` from the employee's profile. Create is on only because that write is on the plan.

Do **not** teach Chat to POST. Do **not** add a People salary GET here.

## Wave B — Then add the API (offline executed)

Detailed plan: [`PULSE-PAY-STRUCTURE-GET-PLAN.md`](PULSE-PAY-STRUCTURE-GET-PLAN.md). ADR-0059 Proposed.

One named GET (`analyze_committed_pay`) → `GET /carbon-api/people/payslip-lines/summary/`. Closed query, declared `returns`. Not a generic analytics API. Not a Pulse hop. B0–B4 green. B5 live still needs STACK-HOLD.

## Execution order when Master says go

```
Wave 0 goldens (failing)
    → A1 + A2   contract at propose + I1 output-fit     ← user's honesty test
    → A3 + A7   no stuffing + Finished honesty          ← same week; else B still lies
    → A4 + A5 + A6  bind, one export, critic
    → live emp_2378 under STACK-HOLD
    → Wave B    People GET + catalog line
```

A1+A2 first is the test you asked for. A3–A7 should ship before Wave B even if they land in the same week. Shipping A1+A2 alone is enough to **see** the refuse; it is not enough to **trust** the loop once the GET exists.

## ADR

Write ADR-0057 (or deepen 0052 I1) **with the Wave A code**, not before. Proposed until goldens are green. Do not flip Accepted, do not touch ADR-0049, do not claim ladder movement.

## Never

- A salary-specific regex or “if the brief contains average/median”.
- Chat host mutation (ADR-0046).
- `people:view` for `emp_1067`.
- `--record` over soak 2026-09-23.
- Adding the GET to make a Wave A golden pass.
- Domain or brand literals in `engine/**`.

## Files the Wave A change will touch (when executed)

- `backend/ai/engine/cognition/plan/contract.py` — I1 output-fit; call at propose.
- `backend/ai/engine/cognition/plan/loop.py` — stuffing, completed_ids, critic parse, step_contexts.
- `backend/ai/engine/cognition/turn/capability.py` · `plan/bindings.py` — bind dialect.
- `backend/ai/engine/cognition/plan/planner.py` — stop Excel-from-wording coerce (already on H4 kill list).
- `carbon-frontend/src/shell/aiTaskStatus.js` — Finished honesty.
- Banks under pack / eval — probes, not engine phrases.

## References

- Runs `dbe99353`, `b040714a`
- ADR-0052 I1 / I3 / I5 · ADR-0053 no-mask · ADR-0055 propose-is-the-plan · ADR-0046 · ADR-0050
- Canvas P22 · H7 · I-9 · I-10 · RC8
