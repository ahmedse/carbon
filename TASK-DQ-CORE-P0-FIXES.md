# TASK-DQ-CORE-P0-FIXES

**Status:** DONE — 2026-08-10
**Phase:** 0 of 5 — DQ Core next-gen plan (`plans/CARBON_DQ_CORE_PLAN.md`)
**Audit reference:** `docs/CARBON_DQ_CORE_AUDIT.md` §5
**Depends on:** nothing
**Executing agent:** read this file cold; everything needed is below.

## Goal

Fix all known DQ bugs and delete dead code. **Zero new features, zero redesign.** Every later phase builds on this.

## Repo facts

- Django + DRF backend in `backend/`, pytest for tests, repo gate: `./verify.sh backend` must pass.
- React 19 + Vite + MUI frontend in `carbon-frontend/` (`npm run build`, `npm run lint` must pass).
- DQ API mounted at `/carbon-api/dq/`.

## Deliverables

### 1. Fix metrics endpoints HTTP 500 — `backend/dq/views.py`

- `TableDQMetricsView` (~line 772) and `FieldDQMetricsView` (~line 838) filter `DQRule` on `data_table=` / `data_field=` FKs that were **removed in migration `dq/0009_decouple_rules_m2m.py`** → `FieldError` at runtime.
- Rewrite both queries through the through-model `RuleFieldAssignment` (`dq/models.py:64`). The FK `related_name` is **`field_assignments`** (verified; the same file already uses it at `views.py:290`). Table: `DQRule.objects.filter(field_assignments__data_table=table, is_active=True).distinct()`. Field: `DQRule.objects.filter(field_assignments__data_field=field, is_active=True).distinct()`. `.distinct()` is required — a rule can have several assignments.
- Add regression tests: `GET /dq/metrics/table/<id>/` and `/dq/metrics/field/<id>/` return 200 with correct rule counts for a rule bound to (a) one field, (b) a whole table (assignment with `data_field=null`).

### 2. Fix `bulk_execute` double count — `backend/dq/views.py` ~line 305

- `run_single_rule()` returns a **list** of `DQResult`; the view treats the return as a dict (`result['passed']`) → `TypeError` → generic `except` records every rule once as raw list and once as error/failure.
- Fix: iterate the returned list; a rule counts as failed only if any result has `passed=False`. Add a test: bulk-execute 2 passing rules → summary shows 2 passed, 0 failed, and exactly 2 result entries.

### 3. Delete `backend/dq/executor.py` entirely

- It is a stale duplicate evaluator: `execute()` with no data sample validates 0 rows and **always passes**; it accepts a `'custom'` type not in `RULE_TYPES`.
- `POST /dq/rules/{id}/execute/` (`dq/views.py` ~194-200) currently calls it with no sample. Re-point that action to `run_single_rule()` (the real path used by `run_dq()`).
- Remove all imports of `DQRuleExecutor`; update or delete tests that reference it.
- Gate: `grep -ri "DQRuleExecutor\|dq.executor" backend/` → zero hits.

### 4. `DQProfileConfig` cleanup — `backend/dq/models.py:161`

- **Delete** fields `auto_profile_enabled` and `sample_size` (never read by any code) — migration + remove from serializer/admin.
- **Freshness thresholds (corrected audit note):** there is **no per-table freshness setting** to wire. `expected_max_age_hours` lives on `FreshnessCheck` (`dq/models.py:184`) as a snapshot of the global threshold, written by `check_freshness.py:57` (`expected_max_age_hours=default_threshold`). P0 action: document this in the field's `help_text` ("snapshot of the global threshold at check time; per-table thresholds not yet supported"). Do NOT add a per-table field here — candidate for Phase 6.
- **Keep** `volume_anomaly_pct` but mark it deprecated in the serializer `help_text` ("wired in DQ Phase 4"). Do NOT implement anomaly logic here.
- Update the two existing tests that touch the deleted fields.

### 5. Doc drift (text edits only)

- `backend/dq/models.py` `DQRule` docstring: remove claims "checked at data entry time by validators.py" and "business rules run via Pulse scheduler" — both false. Replace with: "Field-level rules are enforced at write time by the gate (Phase 2). All other rules run as jobs (Phase 3)."
- Root `TASK-DQ-LEVEL2-PULSE.md`, `TASK-DQ-LEVEL3-PULSE-SUGGEST.md`, `TASK-DQ-PHASE4-CLEANUP.md`: header status → `DONE`, add commit refs `0da0da5`, `5478368`, `5cff2ff` respectively.
- `docs/PULSE_CONTRACT_SPEC.md`: header "Spec — not yet implemented" → "v2.0 — `dq.validate` and `dq.suggest` implemented Carbon-side; other task types pending."
- `docs/DESIGN_DATA_TRUST_CORE.md`: rule-type list → the actual 8: `not_null, unique, allowed_values, range, regex, reference_integrity, threshold, nl_check`. Add note: "Pulse direction: Carbon pushes tasks to Pulse (see PULSE_CONTRACT_SPEC v2.0); the 'Pulse pulls' statement in §6 is superseded."
- `plans/CARBON_DATA_TRUST_ARCHITECTURE.md`: fix example `rule_type` values `value_range`/`completeness` → `range`/`not_null` (they reference nonexistent types).

### 6. Frontend dead code — `carbon-frontend/src/`

- Delete `components/dq/DQMetricsDrawer.jsx` (unused; also has swapped args — do not fix, delete).
- `App.jsx` ~lines 57-58: remove lazy imports of legacy `pages/catalog/DQDashboardPage.jsx` and `DQRulesPage.jsx` (their routes already redirect to the hub). Delete the two page files if nothing imports them; verify with grep first.
- `api/dq.js`: delete `getFieldProfiles()` (calls nonexistent `dq/field-profiles/`) and unused `bulkExecuteRules()` (verify no importers via grep before deleting).
- `shell/StatusBar.jsx:61`: remove breadcrumb labels for nonexistent `/dataschema/quality` and `/carbon/data-entry/quality`.

## Explicit exclusions (do NOT touch)

- No changes to `dq/services.py::_evaluate_rule` logic, `pulse_gateway.py`, `dataschema/validators.py`, or any model fields beyond item 4.
- No new endpoints, no UI features, no refactoring beyond what the 6 items require.

## Gates

1. Backend green: `cd backend && python -m pytest -q` (or `./manage.sh test` from repo root). Note: there is **no `verify.sh`** in this repo — `manage.sh test` wraps pytest.
2. `cd backend && python -m pytest dq/ -q` — all green, including the new regression tests (≥4 new).
3. `grep -ri "DQRuleExecutor" backend/` → zero hits. `grep -ri "DQMetricsDrawer\|field-profiles" carbon-frontend/src/` → zero hits.
4. `cd carbon-frontend && npm run build && npm run lint` — clean.
5. Migrations: `python manage.py makemigrations dq` produces exactly one migration (field deletions); `migrate` applies cleanly.

## Done criteria

All 6 deliverables complete, all gates green, no unrelated diff noise.
