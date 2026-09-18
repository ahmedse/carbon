# Chat QA — B1 leave employee filter + label honesty (2026-09-17)

**Seat:** Pulse · **Brand:** nibras · **User:** `ahmed`  
**Fixture:** `employee_no=1416` (Eslam Mohamed Elsayed Mohamed Ramadan)

## Goal

After focusing 1416, leave follow-up must not over-fetch org-wide entitlements
(truncated 100 rows) or mislabel the table as **Employee 333**.

## Fix

| Layer | Change |
|-------|--------|
| Host | `leave-entitlements` / `leave-records` / `loans` honour `employee` / `employee_no` |
| Host | Annotate rows with `employee_no` + `employee_name` (no bare FK labels) |
| Tools | Inject WM focus `employee_no` into person-scoped leave/loan lists when omitted |
| Resolve | Persist focus with `entity_id=employee_no` after match |
| Catalog | `instance.yaml` requires employee filter for single-person leave follow-ups |

## Unit tests

`ai/tests/test_b1_leave_employee_filter.py` → **13 related suite PASS** (with C1/C7: 23)

## Live prove (`CarbonIntelligence`, `ahmed`)

| Step | Verdict | Observed |
|------|---------|----------|
| Find 1416 | **PASS** | Resolve → Eslam; WM focus `entity_id=1416` |
| Leave entitlements follow-up | **PASS** | Named **Eslam Mohamed…**; five leave types for 2026; **no Employee 333**; `list_leave_entitlements` |

## Result

**B1 PASS**
