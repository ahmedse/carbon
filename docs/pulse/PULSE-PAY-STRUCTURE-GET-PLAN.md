# Pulse — Declared pay-structure GET (Wave B)

> **Status:** Offline executed (2026-09-25). Host GET + catalog + goldens. No live run. ADR-0059 Proposed.
> **Date:** 2026-09-25
> **Depends on:** Wave A (ADR-0057) + request write (ADR-0058) already in the tree
> **Probe:** same brief as runs `dbe99353` / `b040714a` / the live 9-step draft
> **Does not move:** L6 / L7 · soak night 2026-09-23 · ADR-0049 Proposed · no generic query API

This is the explicit feature that makes that workbook gettable. It is **not** an ad-hoc “bring me data” API. It is **not** a Pulse hop over `list_payslip_lines`.

## Why this GET, and why only this GET

The rows already exist: `PayslipLine` (amount, `line_type`, `payroll_run`, `employee`) joined to `Employee` (`org_unit`, `nationality`, `position`, `is_active`). Pulse must not join them. The host must name the metric family, the population, and the fields **before** the turn.

A generic analytics surface (caller picks metrics, group-bys, filters, line types) would:

- empty `returns` → I1 becomes name-exists again
- mix headcount, pay, and PII under one CBAC story
- leave “average of what” to the model
- turn the 9-step disaster into a product

`analyze_employees` is the warning. It is a bounded headcount GET. Its description said “any distribution.” The planner believed it. This GET must not inherit that sentence.

## What the brief actually asks

Latest **committed** pay cycle, then per group:

| Field | Meaning (fixed; not caller-defined) |
|---|---|
| `label` | Group label for the requested dimension |
| `headcount` | Employees in that group who have exactly one line of the chosen type |
| `average` | `total / headcount` |
| `median` | Middle of the sorted per-employee amounts |
| `min` / `max` | Range of those amounts |
| `total` | Sum of those amounts (payroll cost for that line type) |

Dimensions the brief names: org unit, nationality, position, employment status (`is_active`).

Unit of analysis is the **pay period**, not one `PayrollRun` row. A run is per org unit. A company-wide “by org / nationality” needs every **committed** run in scope for that `period_end`.

## The capability (one name, one path, one gate)

| | |
|---|---|
| Catalog name | `analyze_committed_pay` |
| Method / path | `GET /carbon-api/people/payslip-lines/summary/` |
| Kind | `read` |
| Confirmation | false (Chat may call it; ADR-0046 still forbids writes) |
| Capability | `people:view_compensation` (403 if missing; do not grant to `emp_1067`) |
| Org scope | RULE_12: lines whose employee org unit is visible **and** whose run is visible |
| Audit | one `view_compensation` governance event per GET (aggregate, not per employee) |

Do **not** hang this on `/people/analytics/` or add a `metric=` switch to `analyze_employees`. Separate path, separate name, separate gate.

### Query (closed; `additionalProperties: false`)

| Param | Required | Values |
|---|---|---|
| `period_end` | yes | Date. All scoped committed runs with this `period_end`. Bind from `list_payroll_runs`. |
| `dimension` | yes | `org_unit` \| `nationality` \| `position` \| `is_active` |
| `line_type` | no | `net` (default) \| `gross` |

No other dimensions. No `group_by` array. No metric list. No `p90`. No GOSI / loan as “salary.”

### Fail closed

| Input | Host answer |
|---|---|
| Unknown dimension / line_type | 400 |
| No `people:view_compensation` | 403 |
| No committed run in scope for that `period_end` | 200 + empty breakdown + `empty_render` (not a invented zero workbook) |
| Run exists but status ≠ committed (if a later `payroll_run` id is added) | 409 — do not aggregate draft / computed / validated / failed |
| Employee has 0 or 2+ lines of that type in the period | omit that employee; increment `omitted`; caveat |

### Population (write this in the view docstring and the catalog description)

1. Universe = `PayslipLine` whose `payroll_run.status = committed`, `payroll_run.period_end = period_end`, `line_type.code = line_type`, employee org in scope.
2. One amount per employee (that line type).
3. Group by the requested employee dimension (FK → label, same style as `analyze_employees`).
4. Compute `headcount`, `total`, `average`, `median`, `min`, `max` **on the host**.

`headcount` here is “employees with a pay line,” not roster headcount from `analyze_employees`. The catalog must say so.

### Envelope

```
{
  period_end, dimension, line_type, status: "committed",
  run_ids: [...],
  omitted: N,
  caveats: [...],
  breakdown: [{label, headcount, average, median, min, max, total}, ...]
}
```

Amounts as strings with the host decimal scale (3), same as payslip lines. Pulse restates; it does not re-average.

### Catalog `returns` (this is I1)

```
label, headcount, average, median, min, max, total,
period_end, dimension, line_type, status
```

Export `columns` must be a subset. If a later brief wants `p90` or `gosi`, that is a **new** catalog line (or a new `returns` row after the host grows). Until then: output-fit + request write.

### `not_for` / `empty_render`

- **not_for:** roster counts; gender / kuwaitization / rotation; draft or in-flight runs; one named person’s pay (`get_employee` / compensation); any metric not on `returns`.
- **empty_render:** `no_committed_pay` — “No committed pay lines for this period and dimension.”

## Catalog honesty (same change, not new APIs)

These descriptions caused the 9-step draft. Fix them in the same Wave B commit.

| Entry | Change |
|---|---|
| `analyze_employees` | Add `not_for`: pay amounts, average, median, range, payroll cost, “salary distribution.” It is headcount. |
| `get_payroll_run` | Delete “summary totals.” Add `returns`: `id`, `org_unit`, `period_start`, `period_end`, `status`, `committed_at`. Serializer already has those; it has no totals. |
| `list_payslip_lines` | Add `not_for`: group metrics / distribution workbooks. It is a (truncated) line list. |
| `list_payroll_runs` | Declare optional query `status` (`draft` \| `computed` \| `validated` \| `committed`) and implement that filter on DRF **and** in-process. `latest_by: period_end` then means “latest among that filter.” |

Without `status=committed` on the list, bind can point `period_end` at a draft run; the new GET would then empty-render. The filter is a declared field, not a generic query language.

## Honest plan after Wave B (same brief)

1. `list_payroll_runs` `status=committed` → bind `period_end` latest.
2. `analyze_committed_pay` × 4 (`dimension` = org_unit / nationality / position / is_active). Same entry. `line_type` defaults to `net`.
3. One `export_document` whose `columns` ⊆ `returns`.

No synthesize hop. No critic GET. No unnamed xlsx. If the planner still invents those, Wave A is incomplete — fix Wave A, do not add a second GET.

Chat: one or more calls to `analyze_committed_pay`, grounded answer, no invented figures. 403 stays 403.

## Implementation order (when Master says go)

```
B0  Goldens first (failing) — same brief, three surfaces
B1  Host GET + status filter + people tests (RBAC, committed-only, omit, empty)
B2  In-process route (same view as HTTP; no second implementation)
B3  Catalog honesty (not_for / returns / status) + one new catalog line + pack tools ⊆ instance
B4  Bank / contract goldens green (columns ⊆ returns; no hop; no stuffing)
B5  Live emp_2378 under STACK-HOLD — propose + Chat + one export
```

B0 expected **before** B1:

| Surface | Now | After B4 |
|---|---|---|
| Plan propose | output_fit on hops + unnamed export; request write if catalog loaded | 1 list + 4 `analyze_committed_pay` + 1 named export; Create on |
| Plan loop | must not stuff if someone still Runs the old 9-step | export fires only after the GET payload exists |
| Chat | must not invent averages | answers from the GET; 403-honest for `emp_1067` |

## Files (when executed)

**People (host of record)**

- `backend/people/views.py` — new summary view; `PayslipLineListView` unchanged
- `backend/people/urls.py` — `payslip-lines/summary/`
- `backend/people/tests/` — compensation 403, committed-only, omit, empty period, org scope
- `backend/people/views.py` / `host_executor.py` — `list_payroll_runs?status=`

**Pulse catalog only (no engine salary code)**

- `backend/ai/engine/instances/nibras/instance.yaml` — new entry + honesty edits
- `domain_packs/nibras/api_catalog.yaml` + `pack.yaml` version bump
- `backend/ai/eval/plan_contract_bank.yaml` — covered case: columns ⊆ new `returns`
- `backend/ai/host_executor.py` — route the new path to the **same** view (APIRequestFactory or shared function). Do not re-implement aggregation in the executor.

**Do not touch**

- `backend/ai/engine/**` phrase tables, `topic_re`, salary words
- soak `PV2-6B-nights.json`
- `emp_1067` capabilities
- `analyze_employees` implementation (headcount stays headcount)

## Tests that must exist before live

1. `emp_2378` + committed period → breakdown fields == `returns`; sums reconstruct.
2. `emp_1067` → 403, no amounts in body.
3. Draft-only period → empty breakdown, no numbers invented.
4. Duplicate net lines for one employee → omitted + caveat; not double-counted.
5. Contract golden: export `columns: [average, median]` is covered; `columns: [p90]` is still `output_fit` + request write.
6. `pack_contract --gate`. `domain_terms_in_core` stays 0.

## Live (STACK-HOLD only)

- Actor: `emp_2378` / `mozafNibrasPa_132`.
- Same salary-structure brief.
- Propose: no blocked synthesize; Create on because the GET is on the plan, not because of a request.
- Run: one xlsx; columns ⊆ payload; figures appear in the tool result.
- Chat: same figures, no extras.
- No `manage.sh` start/kill from the agent. Night 2026-09-23 FAIL stays.

## ADR

Write **ADR-0059** with the host code, not before: *A pay-structure read is a named, closed GET; `returns` are the only columns; analytics stays headcount.* Proposed until B4 is green. Do not flip 0049 / 0057 / 0058.

## Never

- `metric=`, open `group_by`, or “fields=” on any People GET
- Pulse-side group-by of `list_payslip_lines` (that list is also truncated)
- Extending `analyze_employees` to return amounts
- Teaching Chat to POST
- Granting `people:view` or `people:view_compensation` to `emp_1067`
- Adding the GET to make a Wave A refuse golden pass
- A second GET when the first plan still stuffs

## Exit

The same brief, as `emp_2378`, produces a short plan whose only reads are `list_payroll_runs` + `analyze_committed_pay`, whose only write is a named export, and whose file contains only fields the GET declared. Anything else is a Wave A defect or a new catalog line — not a wider API.
