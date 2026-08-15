# TASK-DQ-PHASE4-CLEANUP

**Task ID:** DQ-PHASE4-CLEANUP  
**Status:** DONE (commits: 5cff2ff)  
**Assigned to:** Worker (backend)  
**Depends on:** DQ-LEVEL1-VALIDATION (✅), DQ-LEVEL2-PULSE (✅), DQ-LEVEL3-SUGGEST (✅)  
**Estimated effort:** 30 minutes  
**Created:** 2026-08-09  

---

## 0. Context

All DQ rule creation and execution now goes through the proper API path:
- `POST /carbon-api/dq/rules/` → CRUD
- `POST /carbon-api/dq/run/` → `run_dq()` in services.py
- `POST /carbon-api/dq/profile/` → `profile_table()` in services.py

Two legacy artifacts remain that were bootstraps before the API existed.

---

## 1. What To Delete

### 1.1 `backend/emissions/management/commands/setup_carbon_dq.py` — DELETE entire file

An ad-hoc management command that profiled tables, created hardcoded rules, and ran them. Superseded by:
- `profile_table()` in `dq/services.py`
- `run_dq()` in `dq/services.py`
- `DQRuleViewSet` API

No other code imports or calls it. Safe to delete.

### 1.2 `backend/core/management/commands/seed_aastmt_showcase.py` — REMOVE DQ_RULE_SPECS

Two changes in this file:

**A) Delete the `DQ_RULE_SPECS` list** (lines ~393-413):
```python
DQ_RULE_SPECS = [
    ('monthly_electricity', 'field', 'Consumption kWh Not Null', 'not_null', {}, 'error', 'consumption_kwh'),
    ... 9 entries total ...
]
```

**B) Remove the `_seed_dq_rules()` call from `handle()`** (line ~917):
```python
# ── Phase 11: DQ Rules & Results ──
self._seed_dq_rules()
```
Replace the two lines with:
```python
# ── Phase 11: Profile tables for DQ ──
self._profile_tables()
```

**C) Replace `_seed_dq_rules()` method with `_profile_tables()`:**

```python
def _profile_tables(self):
    """Profile all seed tables for data quality (no hardcoded rules)."""
    self.stdout.write("\n[11/13] Profiling tables for DQ...")
    from dq.services import profile_table
    count = 0
    for tbl in self._table_cache.values():
        try:
            profile_table(tbl.id)
            count += 1
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"  Profile failed for {tbl.name}: {e}"))
    self.stdout.write(f"  {count} tables profiled. Create DQ rules via API at /carbon-api/dq/rules/")
```

**D) Remove the `import random` line** inside the old `_seed_dq_rules()` — it won't exist anymore.

### 1.3 `.ai-toolkit/roles/researcher.md` — REMOVE mention of setup_carbon_dq.py

Line 64: `- setup_carbon_app.py, setup_carbon_dq.py (emissions/)`  
Change to: `- setup_carbon_app.py (emissions/)`

---

## 3. Acceptance Gates

- [ ] **G1**: `setup_carbon_dq.py` no longer exists
- [ ] **G2**: `seed_aastmt_showcase.py` has no `DQ_RULE_SPECS` variable
- [ ] **G3**: `seed_aastmt_showcase.py` profiles tables instead of seeding hardcoded rules
- [ ] **G4**: `python manage.py check` passes with 0 issues
- [ ] **G5**: `grep -r "setup_carbon_dq" backend/` returns 0 results
- [ ] **G6**: `grep -r "DQ_RULE_SPECS" backend/` returns 0 results
- [ ] **G7**: All existing 153 DQ tests pass (no regression)
- [ ] **G8**: `verify.sh backend` passes
