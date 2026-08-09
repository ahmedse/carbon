# TASK-DQ-LEVEL1-VALIDATION.md — Phase 1: Unified Field Validation Layer

**Author**: Master Architect
**Date**: 2026-08-09
**Status**: Ready for Worker
**Depends on**: Nothing (standalone backend change)
**Produces**: TASK-RESULT-DQ-LEVEL1.md

---

## Goal

Replace 3 fragmented validation code paths with ONE unified function that reads `DataField` metadata (type, required, validation JSON, reference_set) and validates rows against it. This is **Level 1** (schema-bound field validation), NOT DQ rules.

## Problem Statement

Right now, 3 separate code paths do overlapping but incomplete validation:

| Path | File | What it checks | What it misses |
|---|---|---|---|
| DataRowSerializer.validate() | `dataschema/serializers.py:73-108` | type='number'→numeric, type='boolean', type='select', type='multiselect', required (fields missing from JSON dict) | `validation` JSON, `reference_set`, required (null values in existing fields) |
| SchemaValidationService | `dataschema/services.py:129-165` | type='number'→numeric, type='boolean', type='select', type='multiselect' | `required`, `validation`, `reference_set` |
| BulkImportService | `dataschema/services.py:14-100` | Calls DataRowSerializer (path 1) | Same gaps + no SchemaValidationService call |

`DataField.validation` JSON (defined in model at `dataschema/models.py:72`) is **never read by any code**. `DataField.reference_set` FK is **never validated**.

## Files to Change

### 1. `backend/dataschema/services.py` — CREATE unified `validate_row()` function

Add a new function (NOT a class method) below SchemaValidationService:

```python
def validate_row(values: dict, fields: list, *, strict: bool = False) -> list[dict]:
    """
    Validate a single row's values against DataField metadata.
    
    Returns list of dicts: [{'field': str, 'code': str, 'message': str}, ...]
    Empty list = valid. Never raises — always returns errors list.
    
    strict=True: return ALL errors. strict=False: return first error per field.
    """
```

**Checks to implement (in order):**

1. **`required`** — If `field.required` and (`field.name` not in `values` or value is `None`, `''`, `[]`):
   → `{'field': 'field_name', 'code': 'required', 'message': 'This field is required.'}`

2. **`type='number'`** — If value is not `int` or `float`:
   → `{'field': 'field_name', 'code': 'invalid_type', 'message': 'Must be a number.'}`
   Also: if value < 0:
   → `{'field': 'field_name', 'code': 'negative', 'message': 'Negative values are not allowed.'}`

3. **`type='boolean'`** — If value is not `bool`:
   → `{'field': 'field_name', 'code': 'invalid_type', 'message': 'Must be true or false.'}`

4. **`type='select'`** — If value not in `field.options[].value`:
   → `{'field': 'field_name', 'code': 'not_allowed', 'message': f"Value must be one of {allowed}."}`

5. **`type='multiselect'`** — If not a list or any item not in `field.options[].value`:
   → `{'field': 'field_name', 'code': 'not_allowed', 'message': f"All values must be in {allowed}."}`

6. **`validation.min`** (NEW — `field.validation` JSON dict) — If `field.type='number'` and value < validation.min:
   → `{'field': 'field_name', 'code': 'below_min', 'message': f"Value {value} is below minimum {validation.min}."}`

7. **`validation.max`** (NEW) — If `field.type='number'` and value > validation.max:
   → `{'field': 'field_name', 'code': 'above_max', 'message': f"Value {value} is above maximum {validation.max}."}`

8. **`validation.pattern`** (NEW) — If regex pattern, check value matches:
   → `{'field': 'field_name', 'code': 'pattern_mismatch', 'message': f"Value does not match pattern {validation.pattern}."}`

9. **`reference_set`** (NEW) — If field has `reference_set` FK, fetch ReferenceSet values and check:
   → `{'field': 'field_name', 'code': 'not_in_reference', 'message': f"Value '{value}' not found in reference set '{refset.name}'."}`

10. **`type='date'`** (NEW) — If value is not a valid date string (YYYY-MM-DD or ISO format):
    → `{'field': 'field_name', 'code': 'invalid_date', 'message': 'Must be a valid date (YYYY-MM-DD).'}`

**Performance**: `reference_set` lookup should cache per-call (one query per set, not per field). For `validation` JSON, use `.get()` with defaults.

### 2. `backend/dataschema/services.py` — UPDATE DataRowSerializer to call validate_row()

In `DataRowSerializer.validate()` (line ~73-108), replace the inline validation block with:

```python
from .services import validate_row

# ... inside validate():
if data_table:
    values = data.get('values', {})
    # ... merge partial logic as before (lines 79-84, keep them) ...
    
    # REPLACE the for-loop on lines 87-108 with:
    fields = list(data_table.fields.filter(is_active=True))
    errors = validate_row(values, fields)
    if errors:
        raise serializers.ValidationError(
            {e['field']: e['message'] for e in errors}
        )
```

Do NOT delete the required-fields check — `validate_row()` covers it now (check #1).

### 3. `backend/dataschema/services.py` — UPDATE SchemaValidationService

Replace `SchemaValidationService.validate_field()` body with a call to `validate_row()`:

```python
@staticmethod
def validate_field(field, value):
    errors = validate_row({field.name: value}, [field])
    if errors:
        raise ValueError(errors[0])  # preserve existing contract: {field_name: message} dict
    return None
```

This preserves backward compatibility — existing callers of `SchemaValidationService.validate_field()` stay working.

### 4. `backend/dataschema/services.py` — ADD pre-validate to BulkImportService

In `BulkImportService.import_rows()`, BEFORE the `DataRowSerializer(data={...})` call (line ~83), add a pre-check:

```python
# Pre-validate against field metadata (fast, no DB write)
fields = list(data_table.fields.filter(is_active=True, is_archived=False))
field_errors = validate_row(row_data, fields)
if field_errors:
    results['failed'] += 1
    results['errors'].append({
        'row': idx + 2,
        'data': row_data,
        'error': '; '.join(f"{e['field']}: {e['message']}" for e in field_errors)
    })
    continue  # skip serializer entirely for invalid rows
```

### 5. `backend/dataschema/tests/` — ADD tests

Create `test_validate_row.py` with these test cases:

```python
class ValidateRowTests(TestCase):
    def setUp(self):
        self.table = DataTable.objects.create(...)
        self.num_field = DataField.objects.create(
            data_table=self.table, name='kwh', type='number', required=True,
            validation={'min': 0, 'max': 200000}
        )
        self.select_field = DataField.objects.create(
            data_table=self.table, name='building', type='select',
            options=[{'value': 'B401'}, {'value': 'B2401'}]
        )
        self.date_field = DataField.objects.create(
            data_table=self.table, name='month', type='date', required=True
        )
        # ... etc
    
    def test_valid_row_no_errors(self): ...
    def test_required_missing(self): ...
    def test_required_null_value(self): ...
    def test_number_type_reject_string(self): ...
    def test_number_negative(self): ...
    def test_number_below_min(self): ...
    def test_number_above_max(self): ...
    def test_select_not_in_options(self): ...
    def test_multiselect_not_allowed(self): ...
    def test_regex_pattern_match(self): ...
    def test_reference_set_lookup(self): ...
    def test_date_invalid(self): ...
    def test_date_valid_iso(self): ...
    def test_strict_returns_all_errors(self): ...
    def test_non_strict_returns_first_only(self): ...
```

### 6. DO NOT TOUCH (explicitly exclude)
- `backend/dq/` — any file (Level 2 is separate phase)
- `backend/emissions/` — any file
- `backend/dq/models.py` — DQRule model stays as-is for now
- `setup_carbon_dq.py` — cleanup is Phase 4
- `seed_aastmt_showcase.py` — cleanup is Phase 4

## Acceptance Gates

```bash
# 1. Syntax + no import errors
cd backend && python -c "from dataschema.services import validate_row; print('OK')"

# 2. Django check
python manage.py check

# 3. No new migrations (no model changes)
python manage.py makemigrations --check

# 4. All existing tests pass (50+ tests)
python -m pytest dataschema/ -x -v

# 5. New tests pass
python -m pytest dataschema/tests/test_validate_row.py -x -v

# 6. Verify.sh backend gate
bash .ai-toolkit/scripts/verify.sh backend

# 7. Manual smoke: create a table with validation rules, import a row, verify error messages
```

## Key Design Decisions (do NOT debate)

1. `validate_row()` returns list of errors dicts — NEVER raises. Callers decide: raise ValidationError (DRF) or accumulate (bulk import).
2. `strict=False` by default — returns one error per field. `strict=True` for debugging (all errors).
3. `reference_set` values are cached per-call to avoid N+1 queries.
4. `SchemaValidationService.validate_field()` wraps `validate_row()` — preserves backward compat. Existing callers (if any) don't break.
5. No model changes. No migrations. Pure code refactor.
6. Date validation: accept `YYYY-MM-DD` strings AND Python `date` objects. Reject everything else.

## Completion

Worker must produce `TASK-RESULT-DQ-LEVEL1.md` listing:
- Files changed
- Test results (count pass/fail)
- Gate results
- Any deviations from spec (with reason)
