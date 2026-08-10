# P1 — Backend Worker Prompt

**Role:** Backend Worker (Django + DRF, DQ domain)
**Phase:** DQ Core P1 — Rule Core
**Spec:** `TASK-DQ-CORE-P1-RULE-CORE.md` (read it now)
**Companion docs:** `plans/CARBON_DQ_CORE_PLAN.md` §2-3, `docs/CARBON_DQ_CORE_AUDIT.md`

## Your 6 deliverables (backend only)

### 1. `backend/dq/rule_schema.py` (NEW FILE)

Pure Python validators. No `jsonschema` package. No raises — returns error list like `validate_row`.

**Constants:**
```python
DIMENSIONS = [
    ('completeness', 'Completeness'), ('validity', 'Validity'),
    ('accuracy', 'Accuracy'), ('consistency', 'Consistency'),
    ('timeliness', 'Timeliness'), ('uniqueness', 'Uniqueness'),
    ('integrity', 'Integrity'), ('reasonability', 'Reasonability'),
]

GATE_ELIGIBLE_TYPES = frozenset({
    'not_null', 'unique', 'allowed_values', 'range',
    'regex', 'reference_integrity', 'threshold',
})
```

**`validate_definition(d: dict) -> list[dict]`** — returns `[{'field': str, 'code': str, 'message': str}, ...]`. Empty = valid.

Checks (in order):
- `schema_version` must be `1` (int)
- `name` required, non-empty string
- `level` in `['field', 'business']`
- `dimension` in all 8 DIMENSIONS keys
- `type` in all 8 RULE_TYPES keys (reuse the `RULE_TYPES` list from `dq/models.py` — import it)
- `severity` in `['info', 'warn', 'error']`
- `active` must be boolean if present
- `bindings` non-empty list of `{table: str, field: str|null}`
- `params` validated per type:
  - `not_null`, `unique`: no params required
  - `range`: `min` and/or `max` must be numeric (int/float). At least one must exist.
  - `regex`: `pattern` string must `re.compile` without error
  - `allowed_values`: `values` non-empty list, or `reference_set` integer
  - `threshold`: `operator` in `{gte,gt,lte,lt,eq,neq}`, `value` numeric
  - `reference_integrity`: `reference_set_id` integer if present
  - `nl_check`: `prompt` non-empty string
- `enforcement.on_write` only allowed for gate-eligible types; if `nl_check` has it, return error

### 2. DQRule v2 — `backend/dq/models.py`

Add to DQRule model:
- `dimension = models.CharField(max_length=20, choices=DIMENSIONS, default='validity')`
- `definition = models.JSONField(default=dict, blank=True)`
- `version = models.IntegerField(default=1)`
- `archived = models.BooleanField(default=False)`

Add `save()` override:
```python
def save(self, *args, **kwargs):
    if self.definition:
        errors = validate_definition(self.definition)
        if errors:
            raise ValidationError({'definition': errors})
        # Sync denormalized columns
        self.name = self.definition.get('name', self.name)
        self.rule_level = self.definition.get('level', 'field_validation')
        self.rule_type = self.definition.get('type', self.rule_type)
        self.severity = self.definition.get('severity', self.severity)
        self.is_active = self.definition.get('active', True)
        self.dimension = self.definition.get('dimension', self.dimension)
    super().save(*args, **kwargs)
```

Run `makemigrations dq` → one migration for the 4 new fields.

**Data migration (separate migration):** `python manage.py makemigrations dq --empty --name migrate_rules_to_v1_json` then fill it manually. For each existing DQRule:
- Build `bindings` from its `RuleFieldAssignment` rows (resolve table name via `assn.data_table.name`, field name via `assn.data_field.name` if not null)
- Wrap into v1 JSON with:
  - `schema_version: 1`, `name: rule.name`, `description: rule.description or ""`
  - `level: "field" if rule.rule_level == "field_validation" else "business"`
  - `dimension: "accuracy" if rule.rule_type == "nl_check" else "validity"`
  - `type: rule.rule_type`, `severity: rule.severity`, `active: rule.is_active`
  - `bindings: [...]`, `params: rule.params or {}`
  - `enforcement: {"on_write": False, "on_import": "flag"}`
- Set `rule.definition = v1_json`, `rule.version = 1`, `registry.dimension = v1_json['dimension']`
- Save without triggering `save()` validation (use `update()` or `save(update_fields=[...])`)

### 3. `backend/dq/engine.py` (NEW FILE)

Move from `services.py` into `engine.py`:
- `_evaluate_rule()` → rename to `evaluate(rule_def: dict, rows: list, *, field: DataField = None) -> tuple`
- `_evaluate_nl_check()` → stays as `_evaluate_nl_check(rule_def: dict, rows: list, field=None)` 
- `_is_empty()` helper

The `evaluate` function works on the `rule_def` dict (the v1 JSON from `DQRule.definition`), not the model row. Read `rule_type` from `rule_def['type']`, `params` from `rule_def.get('params', {})`, `severity` from `rule_def.get('severity', 'error')`.

The `nl_check` branch calls `pulse_gateway.validate_dq_rules` **exactly as today** — no behavior change to fail-open.

`services.py` then delegates:
```python
from .engine import evaluate as engine_evaluate

def _evaluate_rule(rule, rows, field=None):
    return engine_evaluate(rule.definition, rows, field=field)
```

Keep `_evaluate_rule` in services.py as a thin wrapper so test imports don't break immediately (they can be updated to import from engine.py directly, but either works).

**Rule in spec:** `grep -rn "_evaluate_rule" backend/dq/services.py` → only delegation calls remain (the original logic body is gone).

### 4. Archive semantics — `backend/dq/views.py`

Replace the existing `destroy()` method (lines 173-184):
```python
def destroy(self, request, *args, **kwargs):
    rule = self.get_object()
    if rule.results.exists():
        rule.archived = True
        rule.is_active = False
        rule.save(update_fields=['archived', 'is_active'])
        return Response(
            {'detail': 'Rule archived because it has execution history.',
             'archived': True, 'results_count': rule.results.count()},
            status=status.HTTP_200_OK,
        )
    return super().destroy(request, *args, **kwargs)
```

In `get_queryset()`, exclude archived rules by default:
```python
def get_queryset(self):
    qs = DQRule.objects.filter(archived=False)
    if self.request.query_params.get('include_archived') == '1':
        qs = DQRule.objects.all()
    # ... existing RBAC filter continues
```

Also add `archived` to the default `filter_backends` / `filterset_fields` list in the viewset.

### 5. Per-dimension scores — `backend/dq/views.py` `DQMetricsView`

In the `get()` response, add `scores_by_dimension`:
```python
# After existing rule-level metrics block, add:
dimensions = {}
for rule in rules:
    dim = rule.dimension or 'validity'
    latest = DQResult.objects.filter(rule=rule).order_by('-run_at').first()
    dim_score = latest.score if latest else None
    if dim not in dimensions:
        dimensions[dim] = []
    if dim_score is not None:
        dimensions[dim].append(dim_score)

scores_by_dimension = {
    dim: round(sum(scores) / len(scores), 1)
    for dim, scores in dimensions.items()
    if scores
}
```

Return `scores_by_dimension` in the response dict.

### 6. De-hardcode the negative-value ban

**6a. `backend/dataschema/validators.py` lines 105-111:** Remove the entire "Negative check" block (the `if value < 0:` with the `code: 'negative'` error). Negative numbers become valid at the entry-validation level — they will be caught by `range` DQ rules instead.

**6b. Seed the no-negative rule:** In `backend/core/management/commands/seed_aastmt_showcase.py`, add a method `_seed_dq_rules(self)` called after `_seed_data_rows()`. For each table that has `number` type fields, create a DQRule:
```python
def _seed_dq_rules(self):
    self.stdout.write("\n[9/14] Seeding DQ no-negative rules...")
    created = 0
    numeric_field_tables = {
        'monthly_electricity': ['consumption_kwh', 'cost_egp'],
        'monthly_chilled_water': ['consumption_tr'],
        'monthly_water': ['consumption_m3'],
        'fleet_fuel_log': ['vehicle_count', 'gasoline_liters', 'diesel_liters', 'total_cost_egp'],
        'generator_fuel_log': ['diesel_liters', 'runtime_hours'],
        'paper_consumption': ['paper_reams', 'cost_egp'],
        'vessel_fuel_log': ['diesel_liters', 'voyage_hours'],
    }
    for table_name, fields in numeric_field_tables.items():
        table = self._table_cache.get(table_name)
        if not table:
            continue
        for fname in fields:
            field = self._get_field(table, fname)
            if not field:
                continue
            definition = {
                'schema_version': 1,
                'name': f'{fname}_non_negative',
                'description': f'{fname} must be >= 0',
                'level': 'field',
                'dimension': 'validity',
                'type': 'range',
                'severity': 'error',
                'active': True,
                'bindings': [{'table': table_name, 'field': fname}],
                'params': {'min': 0},
                'enforcement': {'on_write': True, 'on_import': 'block'},
            }
            rule = DQRule.objects.create(
                name=definition['name'],
                rule_level='field_validation',
                rule_type='range',
                params=definition['params'],
                severity='error',
                is_active=True,
                description=definition['description'],
                dimension='validity',
                definition=definition,
                version=1,
            )
            RuleFieldAssignment.objects.get_or_create(
                rule=rule, data_table=table, data_field=field,
            )
            created += 1
    self.stdout.write(f"  {created} no-negative range rules seeded.")
```

Update the `handle()` method numbering and add method calls. The seed's `_clean_previous()` already deletes all DQRules so idempotency is preserved.

**6c. Update tests:** In `backend/dataschema/tests/test_validate_row.py`:
- `test_number_negative` (line 112): change to assert **no errors** (negative values now pass entry validation)
- The mixed-error tests (lines 343-359): remove assertions about `negative` code — only `below_min` and `not_allowed` remain for those cases

## Test minimums (≥12 new)

Add to `backend/dq/tests/test_dq.py` or a new `backend/dq/tests/test_rule_schema.py`:

| Test | What |
|------|------|
| `test_validate_valid_range` | valid range definition → empty errors |
| `test_validate_valid_nl_check` | valid nl_check definition → empty errors |
| `test_validate_invalid_missing_name` | missing name → error |
| `test_validate_invalid_unknown_type` | unknown type → error |
| `test_validate_invalid_enforcement_on_nl_check` | nl_check with on_write → error |
| `test_validate_invalid_range_no_params` | range without min/max → error |
| `test_validate_invalid_threshold_bad_op` | threshold with bad operator → error |
| `test_rule_save_syncs_denormalized` | save with definition → denormalized fields match |
| `test_rule_save_invalid_definition_raises` | save with bad definition → ValidationError |
| `test_migration_wraps_existing_rules` | existing rule after migration → valid definition JSON |
| `test_archive_rule_with_results` | DELETE rule with results → archived=True, 200 |
| `test_hard_delete_rule_no_results` | DELETE rule no results → 204 |
| `test_scores_by_dimension_in_metrics` | GET /dq/metrics/ → scores_by_dimension present |
| `test_negative_values_allowed_no_error` | validate_row with negative number → empty errors (validators.py change) |

## Gates (run in order)

1. `cd backend && python -m pytest -q` — full suite green
2. `cd backend && python -m pytest dq/ dataschema/ -q` — all green, ≥12 new tests
3. `python manage.py makemigrations dq` → exactly 2 migrations (fields + data); `migrate` clean
4. `grep -rn "_evaluate_rule" backend/dq/services.py` → only the delegation wrapper remains
5. `curl GET /carbon-api/dq/rules/` returns `dimension` and `definition` for each rule; `POST` invalid definition → 400 with error list
6. `curl GET /carbon-api/dq/metrics/` returns `scores_by_dimension`

## Explicit exclusions (HARD BOUNDARIES)

- No gate/write-path enforcement (Phase 2)
- No jobs model or runner (Phase 3)
- No `anomaly_detect` type (Phase 4)
- No frontend changes
- No changes to `RuleFieldAssignment` structure
- No `jsonschema` package install
- Do NOT change Pulse fail-open behavior
- Do NOT run git commit

## Handoff

```
PHASE 1 BACKEND: <DONE | BLOCKED>
- Deliverables: <6/6 or deviations>
- Gates: <pass/fail each, with command output summary>
- Files changed: <list>
- Decisions needed: <list or none>
```
