# ECF-8 Evidence — LeaveRecord generalize proof

**Date:** 2026-09-16  
**Seat:** Pulse  
**Worker:** backend-worker  
**ADR:** 0032 Entity Capability Framework

## Verdict

ECF-8 is **DONE**. Entity #2 (`leave_record` → `people.models.LeaveRecord`) onboarded by **descriptor + goldens only**. **Zero new algorithm code** under `backend/ai/engine/cognition/entity/`.

## What shipped

| Item | Path |
|------|------|
| Descriptor | `backend/ai/engine/instances/nibras/instance.yaml` → `entities:` entry `leave_record` |
| Goldens | `backend/ai/tests/test_ecf_leave_golden.py` (≥2 resolve cases + grounded-none) |

### Descriptor (thick)

- `identifiers: [id]`
- `search_fields`: status, start_date, end_date
- `label_map`: employee → `full_name`; leave_type → ReferenceValue `label`
- `metrics`: `open_leave_count` (status=submitted), `approved_leave_count` (status=approved)
- `scope_lookup: employee__org_unit_id__in` (RULE_12)

### Golden cases

| id | query | expect |
|----|-------|--------|
| leave_lookup_by_id_42 | `42` | match leave_id=42 |
| leave_lookup_by_start_date | `2026-03-01` | match leave_id=42 |
| leave_grounded_none_unknown_id | `99999` | grounded-none + searched N of N |
| leave_grounded_none_unknown_date | `2099-01-01` | grounded-none + searched N of N |

Harness uses in-memory population (no Django / no people edits).

## Quality gates

```
$ ./manage.sh test ai/tests/test_ecf_golden.py ai/tests/test_ecf_leave_golden.py \
    ai/tests/test_ecf_shadow.py ai/tests/test_ecf_contracts.py \
    ai/tests/test_ecf_aggregate.py -q
59 passed in 0.84s
  (prior ECF-7 gate was 52; +7 leave golden/structural)

$ rg -n "django|from people|rest_framework" backend/ai/engine/cognition/entity/
# zero hits

$ # No ECF-8 edits under cognition/entity/ (resolver/contracts/aggregate/heal/registry untouched this phase)
```

| Gate | Result |
|------|--------|
| Employee goldens | still green |
| LeaveRecord goldens | green |
| Shadow / contracts / aggregate | green |
| Import-boundary (`cognition/entity/`) | clean |
| New `.py` under cognition/entity/ for ECF-8 | **none** |
| people app / NSR frontend | untouched |

## Proof: framework generalizes

`get_descriptor(cfg, "leave_record")` loads from instance.yaml.  
`resolve(desc, query, fetch_fn=...)` matches LeaveRecord without any LeaveRecord-specific algorithm module.

## Residual risk

- Host `fetch_fn` wiring for live LeaveRecord ORM path not exercised here (in-memory harness preferred per ECF-8 scope).
- LeaveRecord has no bilingual name fields on the model — search is status/date only (thick where fields exist).
- Production `resolve_entity` tool must pass `entity_type=leave_record` when callers request leave (tool wiring out of scope for this phase).
