# P0 — Backend Worker Prompt

**Role:** Backend Worker (Django + DRF, DQ domain)
**Phase:** DQ Core P0 Fixes
**Spec:** `TASK-DQ-CORE-P0-FIXES.md` (read it now if you haven't)
**Companion docs:** `plans/CARBON_DQ_CORE_PLAN.md`, `docs/CARBON_DQ_CORE_AUDIT.md`

## Your 5 deliverables (backend only)

### 1. Fix metrics endpoints HTTP 500 — `backend/dq/views.py`

**Problem:** `TableDQMetricsView` (~line 773) and `FieldDQMetricsView` (~line 858) filter on old `data_table=`/`data_field=` FKs removed in migration 0009.

**Fix:**
- `TableDQMetricsView.get()` line 773:
  - Replace: `DQRule.objects.filter(Q(data_table=table) | Q(data_field__data_table=table), is_active=True).distinct()`
  - With: `DQRule.objects.filter(Q(field_assignments__data_table=table) | Q(field_assignments__data_field__data_table=table), is_active=True).distinct()`
- `FieldDQMetricsView.get()` line 858:
  - Replace: `DQRule.objects.filter(data_field=field, is_active=True)`
  - With: `DQRule.objects.filter(field_assignments__data_field=field, is_active=True).distinct()`

**Tests (≥2):**
- Add to `backend/dq/tests/test_dq.py`: `test_table_metrics_returns_200_with_m2m_rules` — creates a DQRule with RuleFieldAssignment to a table, hits `GET /carbon-api/dq/metrics/table/<id>/`, asserts 200 and correct rule count.
- `test_field_metrics_returns_200_with_m2m_rules` — same for field-level assignment.

### 2. Fix `bulk_execute` double count — `backend/dq/views.py` ~line 305

**Problem:** `run_single_rule()` returns a **list** of DQResult dicts (one per RuleFieldAssignment). The view does `result['passed']` treating it as a single dict → `TypeError` → caught by generic `except` → every rule counted twice (once as raw list in results, once as error).

**Fix:** Iterate the returned list. A rule passes only if ALL results in the list have `passed=True`.

```python
# Replace the try/except block at ~line 320:
for rule in rules:
    _check_rule_access(request.user, rule)
    try:
        result_list = run_single_rule(rule.id, user=request.user)
        for result in result_list:
            results.append(result)
            if result['passed']:
                passed += 1
            else:
                failed += 1
    except Exception as exc:
        results.append({...})
        failed += 1
```

**Test (≥1):** `test_bulk_execute_two_passing_rules` — 2 passing rules, asserts `total=2, passed=2, failed=0, len(results)==2`.

### 3. Delete `backend/dq/executor.py` entirely

**Actions:**
- Delete `backend/dq/executor.py`
- `backend/dq/views.py` line 27: remove `from .executor import DQRuleExecutor`
- `backend/dq/views.py` execute action (line ~198): replace with `run_single_rule()` call:
  ```python
  @action(detail=True, methods=['post'])
  def execute(self, request, pk=None):
      rule = self.get_object()
      _check_rule_access(request.user, rule)
      results = run_single_rule(rule.id, user=request.user)
      return Response(results, status=status.HTTP_201_CREATED)
  ```
- **`backend/simulation/engine.py`** lines 641, 655-660: replace `DQRuleExecutor` usage:
  - Import: `from dq.services import run_single_rule` instead of `from dq.executor import DQRuleExecutor`
  - Also fix the old FK at line 657: `DQRule.objects.filter(data_table=table, ...)` → `DQRule.objects.filter(field_assignments__data_table=table, ...).distinct()`
  - Replace executor usage with `run_single_rule(rule.id)` and check result list for `passed`

**Gate:** `grep -ri "DQRuleExecutor\|dq\.executor" backend/` → **zero hits**.

### 4. `DQProfileConfig` cleanup — `backend/dq/models.py`

**Delete** from the model:
- `auto_profile_enabled` (line 163)
- `sample_size` (line 169)

**Deprecate** (do NOT delete; update help_text only):
- `volume_anomaly_pct` help_text → `"Row count change % that triggers a volume anomaly alert (wired in DQ Phase 4)."` 

**Document** (update help_text only):
- `FreshnessCheck.expected_max_age_hours` (line 184) help_text → `"Snapshot of the global threshold at check time; per-table thresholds not yet supported."`

**Also update:**
- `backend/dq/serializers.py` lines 24-25: remove `auto_profile_enabled` and `sample_size` from the DQProfileConfig serializer `fields` list. Update `volume_anomaly_pct` help_text.
- `backend/dq/admin.py` line 14: remove `auto_profile_enabled` and `sample_size` from the fieldsets tuple.
- Run `python manage.py makemigrations dq` → exactly ONE migration (2 field deletions).

**Tests:** Update `backend/dq/tests/test_phase1_7_profiling.py`:
- Remove assertions referencing `auto_profile_enabled` (lines 62, 69, 73, 81, 86, 88)
- Remove assertion referencing `sample_size` (line 65)
- Keep the DQProfileConfig creation/update test but only for `freshness_threshold_hours` and `volume_anomaly_pct`
- Do NOT touch `test_phase1_8_freshness_schema.py` — it only uses `freshness_threshold_hours`

### 5. Doc drift (text edits only)

**5a.** `backend/dq/models.py` DQRule docstring (lines 40-41):
```
Replace:
  - field_validation: checked at data entry time by validators.py
  - business_rule:    runs independently via Pulse scheduler / services.py
With:
  - field_validation: enforced at write time by the gate (Phase 2)
  - business_rule:    runs as jobs (Phase 3)
```

**5b.** Root `TASK-DQ-LEVEL2-PULSE.md`: header status → `DONE`, add `(commits: 0da0da5)`
**5c.** Root `TASK-DQ-LEVEL3-PULSE-SUGGEST.md`: header status → `DONE`, add `(commits: 5478368)`
**5d.** Root `TASK-DQ-PHASE4-CLEANUP.md`: header status → `DONE`, add `(commits: 5cff2ff)`
**5e.** `docs/PULSE_CONTRACT_SPEC.md`: header `"Spec — not yet implemented"` → `"v2.0 — dq.validate and dq.suggest implemented Carbon-side; other task types pending."`
**5f.** `docs/DESIGN_DATA_TRUST_CORE.md`: find the rule-type list and ensure it's exactly: `not_null, unique, allowed_values, range, regex, reference_integrity, threshold, nl_check`. Add note: `"Pulse direction: Carbon pushes tasks to Pulse (see PULSE_CONTRACT_SPEC v2.0)."`
**5g.** `plans/CARBON_DATA_TRUST_ARCHITECTURE.md`: `value_range` → `range`, `completeness` → `not_null` (example rule_type values referencing nonexistent types).

## Gates (run in order, all must pass)

1. `cd backend && python -m pytest -q` — full suite green
2. `cd backend && python -m pytest dq/ -q` — all DQ tests green including new regression tests (≥4 new)
3. `grep -ri "DQRuleExecutor" backend/` → zero hits
4. `grep -ri "dq\.executor" backend/` → zero hits
5. `python manage.py makemigrations dq` → exactly one migration; `python manage.py migrate` applies cleanly

## Explicit exclusions (HARD BOUNDARIES)

- Do NOT touch `dq/services.py::_evaluate_rule` logic
- Do NOT touch `pulse_gateway.py`
- Do NOT touch `dataschema/validators.py`
- Do NOT touch any model fields beyond item 4
- Do NOT create new endpoints or UI features
- Do NOT refactor code beyond what these 5 items require
- Do NOT run git commit

## Handoff

Report in this exact format when done:
```
PHASE 0 BACKEND: <DONE | BLOCKED>
- Deliverables: <5/5 or note deviations>
- Gates: <pass/fail per gate, with command output summary>
- Files changed: <list>
- Decisions needed: <list, or "none">
```
