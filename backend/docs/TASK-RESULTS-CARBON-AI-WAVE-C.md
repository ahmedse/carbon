# Carbon Wave C — Results

> **Date**: 2026-08-11
> **Status**: ✅ Complete
> **Tests**: 17 new (93 total with Waves A+B)

## What Was Built

`CarbonIntelligence` — the single entry point for all AI calls in Carbon. It wraps the
configured `AIProvider` (from `AI_PROVIDER_CLASS`), extracts RBAC scope from Django
users, and provides both sync (ABC) and async (job submission) methods.

### Files

| File | Action | Lines |
|---|---|---|
| `ai/intelligence.py` | Created | ~240 |
| `ai/tests/test_intelligence.py` | Created (17 tests) | ~270 |
| `dq/jobs.py` | Edited (7 PulseGateway → CarbonIntelligence call sites) | — |
| `dq/services.py` | Edited (1 PulseGateway → CarbonIntelligence call site) | — |

### Architecture

```
CarbonIntelligence
├── _get_provider()        # Factory: reads AI_PROVIDER_CLASS, imports, instantiates
├── build_scope(user)       # RBAC: ScopedRole → Scope(org_unit_ids, is_superuser, …)
├── Sync (ABC) methods:
│   ├── health_check()      → provider.health_check()
│   └── validate_dq_rule()  → provider.validate_dq(DqValidateRequest)
├── Async (job) methods:
│   ├── submit_dq_validate()  → _http.post_task("dq.validate", …)
│   ├── submit_dq_suggest()   → _http.post_task("dq.suggest", …)
│   ├── submit_anomaly_detect() → _http.post_task("anomaly.detect", …)
│   └── get_task_status()     → requests.get(/tasks/{id})
```

### Integration Points Changed

**dq/jobs.py** (7 call sites):
- `_submit_pulse_job()`: `PulseGateway()` → `CarbonIntelligence()`
- `_submit_anomaly_job()`: `PulseGateway()` → `CarbonIntelligence()`
- `refresh()`: `PulseGateway().get_task_status()` → `CarbonIntelligence().get_task_status()`

**dq/services.py** (1 call site):
- `suggest_rules_for_table()`: `PulseGateway().suggest_dq_rules()` → `CarbonIntelligence().submit_dq_suggest()`

### Design Decisions

1. **Single entry point** — All Carbon AI calls go through `CarbonIntelligence`. Swap backends by changing `AI_PROVIDER_CLASS`.
2. **Lazy provider** — Provider instantiated on first property access via `importlib.import_module`.
3. **Async/sync split** — `submit_*` methods use `_http.post_task()` for the DQ job system; sync methods delegate to `AIProvider` ABC.
4. **Backward compatible** — Response shapes unchanged; `dq/jobs.py` sees identical dict-based API.

### Gate Results

| Gate | Check | Result |
|---|---|---|
| G1 | Import works | ✅ OK |
| G2 | Zero `PulseGateway` references in dq/jobs.py code | ✅ OK |
| G3 | `suggest_rules_for_table` uses CarbonIntelligence | ✅ OK |
| G4 | Factory returns correct AIProvider | ✅ PulseProvider |
| G5 | Scope builder: None, superuser, staff, normal user | ✅ 4/4 |
| G6 | 93 tests pass (14+14+20+28+17) | ✅ 0 failures, 0.27s |

### Next: Wave D — Carbon Views Layer

Add NL query, suggest, and anomaly DRF endpoints that call `CarbonIntelligence` directly,
making AI capabilities accessible from the Carbon UI.
