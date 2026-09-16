# ECF-7 Evidence — Cutover (`ECF_ENABLED=True`)

**Date:** 2026-09-16  
**Seat:** Pulse  
**Worker:** backend-worker  
**Human sign-off:** received (Master Architect)  
**ADR:** 0032 Entity Capability Framework

## Verdict

ECF-7 cutover is **DONE**. `Settings.ECF_ENABLED` defaults to **True**.  
`resolve_entity` / `aggregate_entity` are in the tool catalog when the flag is on.  
Legacy `list_employees` / `get_employee` / `slug_resolution` remain as a **30-day fallback** (not deleted). Shadow parity stays wired.

## Flag

| Item | Value |
|------|--------|
| Default | `ECF_ENABLED = True` in `backend/ai/engine/core/config.py` |
| Override | env `ECF_ENABLED=false` (pydantic-settings) — emergency rollback |
| Scope | Instances **with** `entities:` expose ECF tools; instances without are unaffected |

## Quality gates

```
$ ./manage.sh test ai/tests/test_ecf_golden.py ai/tests/test_ecf_shadow.py \
    ai/tests/test_ecf_contracts.py ai/tests/test_ecf_aggregate.py -q
52 passed in 0.84s
  (goldens 17/17 included)

$ rg -n "django|from people|rest_framework" backend/ai/engine/cognition/entity/
# zero hits
```

| Gate | Result |
|------|--------|
| Goldens | 17/17 passed |
| Quality-gate suite (golden+shadow+contracts+aggregate) | **52 passed** |
| Shadow suite | green |
| Contracts suite | green |
| Aggregate suite | green |
| Import-boundary (`cognition/entity/`) | clean |
| MutationGuard / no auto-mutation | unchanged — cutover enables resolve/aggregate only |
| Legacy slug_resolution deleted? | **No** — superseded comments only |

## Rollback (one-liner)

```bash
ECF_ENABLED=false  # env override; restart backend
```

## Residual risk

- First 30 days: dual path (ECF primary + slug_resolution fallback). Monitor `pulse.ecf.shadow` diffs.
- Instances without `entities:` unchanged — no accidental tool exposure.
- ECF-8 LeaveRecord generalize proof **DONE** (`docs/pulse/evidence/ECF-8-leave-record.md`).
