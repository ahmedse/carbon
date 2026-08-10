# TASK-DQ-CORE-P1-RULE-CORE

**Status:** NOT STARTED
**Phase:** 1 of 5 — DQ Core next-gen plan (`plans/CARBON_DQ_CORE_PLAN.md` §2, §3-Phase-1)
**Depends on:** TASK-DQ-CORE-P0-FIXES
**Executing agent:** read this file cold; everything needed is below.

## Goal

One rule = one versioned JSON document, tagged with a DAMA dimension, evaluated by a single engine. This is the foundation every later phase (gate, jobs, workspace JSON editor) builds on.

## Design decisions (do NOT debate)

1. **JSON is the source of truth.** `DQRule.definition` holds the full v1 document. Existing columns `name`, `rule_type`, `severity`, `is_active` remain as **denormalized, synced from `definition` on save** (querying/filtering stays cheap). `rule_level` stays and is also synced.
2. **One engine.** After P0 deleted `dq/executor.py`, move the surviving evaluator out of `services.py` into `dq/engine.py` as a public pure function. `services.py` delegates to it. No third evaluator may appear.
3. **Dimensions** are DAMA DMBOK2: `completeness, validity, accuracy, consistency, timeliness, uniqueness, integrity, reasonability`. Required on every rule; default `validity` for the 7 deterministic types, `accuracy` for `nl_check`.
4. **Archive, never hard-delete** rules that have results.
5. No new dependencies (hand-rolled validators, no `jsonschema` package).

## Rule JSON v1 (canonical example)

```json
{
  "schema_version": 1,
  "name": "electricity_kwh_non_negative",
  "description": "kWh can never be negative",
  "level": "field",
  "dimension": "validity",
  "type": "range",
  "severity": "error",
  "active": true,
  "bindings": [{"table": "utility_bills", "field": "kwh"}],
  "params": {"min": 0},
  "enforcement": {"on_write": true, "on_import": "block"}
}
```

`level`: `field | business`. `enforcement.on_write` is only meaningful for gate-eligible types (`not_null, unique, allowed_values, range, regex, reference_integrity, threshold`); reject it in validation for `nl_check`.

## Deliverables

### 1. `backend/dq/rule_schema.py` (new)

- `DIMENSIONS` enum; `GATE_ELIGIBLE_TYPES` frozenset; `validate_definition(d: dict) -> list[error-dicts]` (never raises, mirrors `validate_row` convention).
- Per-type `params` validators: `range`→min/max numeric; `regex`→pattern compiles; `allowed_values`→non-empty list; `threshold`→operator ∈ {gte,gt,lte,lt,eq,neq} + numeric value; `reference_integrity`→reference_set id or fallback allowed; `not_null`/`unique`→no params; `nl_check`→non-empty `prompt` string.
- Cross-field checks: name required; `enforcement.on_write` only for gate-eligible types; `bindings` non-empty; unknown `type`/`dimension`/`level` rejected.

### 2. `DQRule` v2 — `backend/dq/models.py`

- Add: `dimension` (CharField, choices=DIMENSIONS), `definition` (JSONField), `version` (IntegerField, default 1), `archived` (BooleanField, default False).
- `save()`: validate `definition` via `rule_schema.validate_definition` (raise `ValidationError` on errors), then sync denormalized columns from it.
- Data migration: wrap every existing rule into v1 JSON (bindings from its `RuleFieldAssignment` rows, resolving table/field slugs; `enforcement` default `{"on_write": false, "on_import": "flag"}`); set `dimension` by the §3 defaults.

### 3. `backend/dq/engine.py` (new)

- Move `_evaluate_rule` (and its `nl_check` branch) from `services.py` into `engine.py` as `evaluate(rule_def: dict, rows: list, *, field=None) -> dict`. No logic change beyond operating on the JSON definition instead of the model row. `services.run_dq()` / `run_single_rule()` delegate.
- The `nl_check` branch stays calling `pulse_gateway.validate_dq_rules` exactly as today (fail-open behavior is changed in Phase 4, NOT here).

### 4. Archive semantics — `backend/dq/views.py`

- Replace the 409 `rule_locked` delete path: if results exist → set `archived=True`, return 200 with `{"archived": true}`; hard delete only when zero results.
- Default rule list excludes archived (`?include_archived=1` to show).

### 5. Per-dimension scores — `dq/views.py` metrics

- `GET /dq/metrics/` response gains `scores_by_dimension: {validity: 92.5, completeness: ...}` computed from latest result per rule grouped by dimension. Table/field metrics endpoints unchanged in shape (already fixed in P0).

### 6. De-hardcode the negative-value ban

- `backend/dataschema/validators.py:106-111`: remove the hardcoded "no negative numbers" check (it is a carbon-domain opinion inside the generic platform).
- Add it as a seeded rule instead: in the carbon seed path (`alamein-campus/` seed scripts or `emissions` seeds — find where fields are seeded), create a `range` rule `{"min": 0}` bound to the numeric emission-activity fields, `severity=error`. If no seed location fits, document the rule JSON in the seed file's README section instead — do NOT invent a new seed framework.
- Update tests that asserted the hardcoded ban: they now assert the seeded rule exists / or test the ban via a `range` rule fixture.

## Explicit exclusions

- No gate/write-path enforcement (Phase 2). No jobs (Phase 3). No `anomaly_detect` type (Phase 4). No frontend work.
- Do not change `RuleFieldAssignment` structure.

## Gates

1. Backend green: `cd backend && python -m pytest -q` (or `./manage.sh test` from repo root). Note: there is **no `verify.sh`** in this repo — `manage.sh test` wraps pytest.
2. `python -m pytest dq/ dataschema/ -q` — all green; new tests ≥ 12 covering: schema validation per type (valid + invalid), migration fidelity (existing rules produce valid v1 definitions), denormalized sync on save, archive-vs-delete, `scores_by_dimension` math, negatives now allowed by `validate_row`.
3. `python manage.py makemigrations dq dataschema` → exactly one migration each at most; `migrate` clean on a copy of the production backup (`backups/carbon_backup_20260809_181139.sql.gz`) if feasible, else on a fresh sqlite.
4. `curl GET /carbon-api/dq/rules/` returns `dimension` and `definition` for each rule; `POST` with an invalid definition → 400 with precise error list.
5. `grep -rn "_evaluate_rule" backend/dq/services.py` → only the delegation call remains.

## Done criteria

Any rule fully described by its JSON doc; one evaluator; dimensions flowing to metrics; old UI rule dialog still functional against the denormalized fields (temporary compatibility, replaced in Phase 5).
