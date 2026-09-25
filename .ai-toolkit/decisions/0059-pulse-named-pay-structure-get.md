# ADR 0059 — A pay-structure read is a named, closed GET

- **Status:** Proposed
- **Date:** 2026-09-25
- **Deciders:** Master Architect
- **Area:** backend

## Context

Wave A (ADR-0057) proved Pulse must not ship a file for fields no catalog entry declares. The salary-structure brief needs average / median / min / max / total / headcount by org, nationality, position, and employment status on the latest committed pay cycle. Those rows exist (`PayslipLine` × `Employee`). No entry produced them. A generic “bring me data” API would empty `returns` and restore name-exists.

## Decision

People adds **one** GET: `analyze_committed_pay` → `/carbon-api/people/payslip-lines/summary/`.

Closed query: `period_end` + `dimension` ∈ {org_unit, nationality, position, is_active} + optional `line_type` (`net`|`gross`). Unions every **committed** run in scope for that period. Host computes the declared fields. `returns` are the only export columns.

`analyze_employees` stays headcount. `get_payroll_run` does not claim totals it does not have. `list_payroll_runs` may filter `status`. Pulse adds one catalog line. No engine salary code.

## Alternatives Considered

- **Extend `/people/analytics/` with `metric=`** — rejected. That is an ad-hoc API.
- **Pulse group-by of `list_payslip_lines`** — rejected. The list is truncated; I1 would lie.
- **One `payroll_run` id only** — rejected for this brief. A run is per org; the brief is period-wide.

## Consequences

- **Positive:** The same brief becomes a short plan: list committed runs, call this GET, export ⊆ `returns`.
- **Negative / trade-off:** A later metric (p90, GOSI) is a new catalog line, not a wider query.
- **Do NOT re-try:** Open `group_by`, `fields=`, or stuffing a compute hop.

## References

- `backend/people/pay_structure.py`
- ADR-0050 · ADR-0057 · ADR-0058 · `docs/pulse/PULSE-PAY-STRUCTURE-GET-PLAN.md`
