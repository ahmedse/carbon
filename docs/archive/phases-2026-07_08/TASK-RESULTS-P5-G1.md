# TASK-RESULTS-P5-G1.md — Phase 5 · G1: seed_all.py Builder Pattern Refactor (COMPLETE)
# Master Architect ← Backend Worker | Date: 2026-07-31
# Result: ✅ SeedBuilder implemented, ALL 4 gates passed + verify.sh + scan.sh

---

## Summary

Refactored `backend/seed_all.py` from a procedural script (11 flat functions
threading state via parameters + a `global TARGET_YEARS`) into a chainable
**Builder pattern** orchestrator: `SeedBuilder().with_users().with_factors()
.with_targets().run()` — per `.ai-toolkit/shared/design-patterns.md` §Builder
(previously marked "❌ NOT YET USED", now **USED**).

**ZERO behavioral changes** — verified byte-identical seed data, identical
stdout format, identical CLI (`python seed_all.py`, `--reset`, `--years`).

| Before | After |
|---|---|
| 11 flat module-level functions | `SeedBuilder` class: 11 chainable `.with_*()` steps + terminal ops |
| State threaded via parameters (`org_units`, `tables`, `factors`) | Internal state on the builder (`self._org_units`, `self._tables`, `self._factors`, `self._periods`) |
| `global TARGET_YEARS` mutated by `main()` | `self.years` instance state (default `DEFAULT_YEARS = (2024, 2025, 2026)`) |
| Procedural `main()` orchestration | `main()` is a 3-line thin wrapper |

---

## What changed

`backend/seed_all.py`: **613 → 740 lines** (+502 / −375 net rewrite, single file).

### New class: `SeedBuilder`

```python
class SeedBuilder:
    def __init__(self, years=DEFAULT_YEARS, reset=False):
        self.years = tuple(years)
        self.reset = reset
        self._org_units = {}   # private internal state
        self._users = []
        self._tables = {}
        self._periods = {}
        self._factors = {}
        self._steps = []       # explicit chain accumulated via with_*()
        self._done = set()     # idempotency guard
```

### Step methods (all chainable, return `self`)

| Group | Methods |
|---|---|
| Foundation | `with_org_units()`, `with_users()`, `with_modules_and_tables()` |
| Reference data | `with_periods()`, `with_emission_factors()`, `with_gwp()` |
| Activity | `with_activity_data()` |
| Rules / targets / DQ | `with_calculation_rules()`, `with_sbti_targets()`, `with_calculations()`, `with_data_quality()` |
| Terminal | `run()`, `print_summary()`, `_reset()`, `_print_header()`, `_resolve_order()`, `@classmethod from_args()` |

### Behavior contracts implemented (per TASKS-P5.md G1)

- ✅ **No seed data changed** — all 11 module constants byte-identical
  (`ORG_UNIT_TREE`, `MODULE_SPEC`, `TABLE_SPECS`, `EMISSION_FACTOR_SPECS`,
  `GWP_SPECS`, `ELECTRICITY_KWH`, `WATER_M3`, `CHILLED_WATER_TR`,
  `FUEL_DIESEL_L`, `EMPLOYEES`, `SBTI_SPECS`) + method-local `USERS`,
  `rules_spec`, `creds` blocks verified identical.
- ✅ **No output changed** — same `banner()`, same print format, same summary
  table + credentials table (verified against pre-refactor output).
- ✅ **No CLI changed** — `python seed_all.py`, `--reset`, `--years` all
  identical, now via `SeedBuilder.from_args()` (argparse kept as-is).
- ✅ **`main()` is a thin wrapper**:
  ```python
  def main():
      builder = SeedBuilder.from_args()
      builder.run()
      builder.print_summary()
  ```
- ✅ **Every `with_*()` returns `self`** — chainable.
- ✅ **Internal state is private** (`_org_units`, `_tables`, `_factors`, ...).
- ✅ **Auto dependency resolution** — `_DEPENDENCIES` map + `_resolve_order()`
  topological sort; each step also self-resolves at call time
  (e.g. `with_users()` → `with_org_units()` first; `with_calculation_rules()`
  → `with_modules_and_tables()` + `with_emission_factors()` first).
- ✅ **Idempotent** — `_done` guard prevents double-execution; verified by
  calling `.run()` twice.
- ✅ **`run()` semantics** — stacked steps if any were chained, else full
  default pipeline (`_DEFAULT_STEPS`); `--reset` handled first, then header.

### What did NOT change

- All seed data values, credentials, org structure, factor codes, GWP numbers.
- The banner/print format and the summary/credentials table.
- The reset deletion order (`Calculation → … → User` non-superusers).
- The activity-data math (gasoline = 25% of diesel, natural gas = 15%, etc.).
- The `--years` comma-separated parsing.

---

## Gates (all run 2026-07-31)

| # | Gate | Command | Result |
|---|---|---|---|
| 1 | Full seed | `cd backend && python seed_all.py 2>/dev/null \| tail -30` | ✅ completes, same summary |
| 2 | Reset + reseed | `cd backend && python seed_all.py --reset 2>/dev/null \| tail -30` | ✅ clean counts, works |
| 3 | Single year | `cd backend && python seed_all.py --years 2025 2>/dev/null \| head -14 && … \| tail -8` | ✅ `CARBON MASTER SEED - 2025` |
| 4 | Test suite | `cd backend && python -m pytest --reuse-db -q 2>&1 \| tail -3` | ✅ **310 passed, 10 subtests passed** |
| 5 | Verify gate | `./.ai-toolkit/scripts/verify.sh backend` | ✅ **GATE PASSED** (django check, no missing migrations) |
| 6 | Antipattern scan | `bash ./.ai-toolkit/scripts/scan.sh all` | ✅ registry regenerated, no violations |
| 7 | Fluent API smoke test | `SeedBuilder(years=(2025,)).with_users().with_emission_factors().with_sbti_targets()` + `.run()` ×2 | ✅ auto-dep resolution, idempotent |
| 8 | Compile / diagnostics | `python -m py_compile seed_all.py` + editor diagnostics | ✅ no errors |

### Gate 1 — proof (tail)

```
  SEED COMPLETE
  Org Units:         7
  Users:             8
  Groups:            4
  ScopedRoles:       5
  Modules:           1
  DataTables:        6
  DataRows:          130
  ReportingPeriods:  3
  EmissionFactors:   12
  GWPValues:         9
  CalculationRules:  7
  Calculations:      189
  SBTiTargets:       4
LOGIN CREDENTIALS: … (5 rows identical)
```

*(Counts shown are post-`--reset` run — exact canonical values; the first
gate-1 run on the pre-populated DB showed the same cumulative totals as the
pre-refactor script because seeding logic is unchanged.)*

### Gate 3 — proof (head)

```
######################################################################
  CARBON MASTER SEED - 2025
######################################################################
```

### Gate 4 — proof (tail)

```
310 passed, 2 warnings, 10 subtests passed in 83.36s (0:01:23)
```

---

## Verification of zero data change

Automated diff of every seed-data block between `HEAD:backend/seed_all.py`
and the new file — **all 11 module constants + USERS + rules_spec + creds +
banner() + reset block report IDENTICAL**; no stale references to the removed
symbols (`TARGET_YEARS`, `seed_org_units`, …, `run_data_quality`) remain.

---

## Files touched

- `backend/seed_all.py` — the **only** file changed (613 → 740 lines).

No other files modified; nothing outside `backend/` touched.

## Rollback

`git checkout -- backend/seed_all.py` restores the pre-refactor procedural
script (verified it is the only modified tracked file).
