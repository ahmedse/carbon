# PEC-R7 — ECF tool surface advertises `leave_record`

**Date:** 2026-09-16  
**Seat:** Pulse  
**Worker:** backend-worker  
**ADR:** 0032 Entity Capability Framework

## Verdict

`resolve_entity` / `aggregate_entity` tool schemas now advertise **registered descriptor entity types** (including `leave_record`) when `instance_config` is passed to `get_tool_definitions`. `ECF_ENABLED` gate unchanged.

## Problem

Static ECF defs hardcoded `entity_type.enum: ["employee"]`, so the LLM could not discover Entity #2 (`leave_record`) from the tool surface even though ECF-8 goldens + host fetch_fn were green.

## Fix

| Item | Change |
|------|--------|
| Enrichment | `_enrich_ecf_tool_definitions()` deep-copies ECF defs and sets `entity_type` enum/description from `load_descriptors(instance_config)` |
| Metrics | `aggregate_entity.metric` enum also lists all descriptor metrics (e.g. `open_leave_count`) when config present |
| Fallback | Without descriptors: HRMS wording + `employee` / `leave_record` (no brand terms in engine) |
| Assembly | `get_tool_definitions(instance_config=None)` — ECF tools appended only when `ECF_ENABLED` |
| Call sites | `runner.py` (executor.instance_config), `plan/loop.py` (step tools) |

## Proof

```
$ ./manage.sh test ai/tests/test_ecf_aggregate.py -q
12 passed in 0.23s
```

New assertion: with nibras-like `instance.yaml` entities (employee + leave_record), both ECF tool schemas include `leave_record` in `entity_type.enum` and description; aggregate metrics include `open_leave_count`.

## Compliance

| Gate | Result |
|------|--------|
| ECF_ENABLED gate kept | ✅ |
| Engine generic (descriptor-driven names) | ✅ |
| No people app edits | ✅ |
| No `./manage.sh start\|stop` | ✅ |
