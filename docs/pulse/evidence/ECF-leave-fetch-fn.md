# ECF leave fetch_fn — Host live LeaveRecord ORM path

**Date:** 2026-09-16  
**Seat:** Pulse  
**Worker:** backend-worker  
**ADR:** 0032 Entity Capability Framework  
**Residual after:** ECF-8 (descriptor-only; in-memory harness)

## Verdict

**DONE.** Live host `entity_fetch` / `entity_count` for `people.models.LeaveRecord` uses RULE_12 scoping via `employee__org_unit_id__in` (descriptor `scope_lookup`), matching the employee pattern (`org_unit_id__in`). Engine cognition/entity untouched.

## How leave_record is fetched

1. `execute_resolve_entity` / `aggregate_entity` call `executor.entity_fetch` / `entity_count` (host seam).
2. `CarbonHostExecutor.entity_fetch`:
   - Resolves model from dotted path (`people.models.LeaveRecord`).
   - Looks up org scope key via `_people_entity_scope_lookup` — prefers instance.yaml `entities[].scope_lookup`, else host map (`LeaveRecord` → `employee__org_unit_id__in`).
   - Applies `_people_scope(user, qs, org_lookup)` (same helper as list leave API).
   - Filters / limits as requested by the resolver.
   - Returns `values(...)` rows normalized so FK keys are `employee` / `leave_type` (not only `*_id`) and dates/Decimals are strings for search scoring.
3. Label fetches for `label_map` (Employee.full_name, ReferenceValue.label) reuse the same `entity_fetch`.

## What shipped

| Item | Path |
|------|------|
| Host bridge | `backend/ai/host_executor.py` — `_PEOPLE_ENTITY_SCOPE_LOOKUP`, `_people_entity_scope_lookup`, `_normalize_entity_row`; `entity_fetch` / `entity_count` model-aware scope |
| Tests | `backend/ai/tests/test_ecf_leave_fetch_fn.py` |
| Descriptor (unchanged) | `nibras/instance.yaml` `leave_record.scope_lookup: employee__org_unit_id__in` |

## Quality gates

```
$ ./manage.sh test ai/tests/test_ecf_leave_fetch_fn.py -q --tb=short --maxfail=8
7 passed in 2.77s
```

| Gate | Result |
|------|--------|
| Scope lookup map LeaveRecord | `employee__org_unit_id__in` |
| Descriptor fields in row | status, dates, employee, leave_type |
| Org isolation (scoped viewer) | org B leave excluded |
| `resolve()` + live fetch | match by id + start_date |
| `execute_resolve_entity` | found + employee label |
| cognition/entity algorithm | **untouched** |
| people models / frontend | **untouched** |

## Residual risk

- Other employee-linked models (Loan, Attendance, …) are mapped in the host table for future descriptors; only `leave_record` is covered by goldens here.
- Non-superuser scope still depends on `get_visible_org_units` + viewers_group (same as People list).
