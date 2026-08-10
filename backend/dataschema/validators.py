"""
Level 1 field-metadata validation for dataschema rows.

Pure functions that read DataField metadata (type, required, validation JSON,
reference_set) and validate row values against it. Returns error dicts — NEVER
raises exceptions. Callers decide how to surface errors (DRF ValidationError,
bulk-import accumulation, etc.).
"""

from datetime import date, datetime
import re


def validate_row(values: dict, fields: list, *, strict: bool = False) -> list[dict]:
    """
    Validate a single row's values against DataField metadata.

    Args:
        values: dict of {field_name: value}
        fields: list of DataField model instances
        strict: if True, return ALL errors; if False, return first error per field

    Returns:
        list of error dicts: [{'field': str, 'code': str, 'message': str}, ...]
        Empty list = valid. Never raises.
    """
    # Pre-load reference set valid codes (one query per set — cached per call)
    ref_cache = _build_reference_cache(fields)

    errors = []
    for field in fields:
        field_errors = _validate_one_field(field, values.get(field.name), values, ref_cache)
        if field_errors:
            if strict:
                errors.extend(field_errors)
            else:
                errors.append(field_errors[0])
    return errors


def _build_reference_cache(fields: list) -> dict:
    """Build a dict of {reference_set_id: set(codes)} for all fields with reference_set FK."""
    ref_set_ids = set()
    for field in fields:
        if getattr(field, 'reference_set_id', None):
            ref_set_ids.add(field.reference_set_id)

    if not ref_set_ids:
        return {}

    # Lazy import to avoid circular dependency at module level
    from mdm.models import ReferenceSet

    cache = {}
    for ref_set in (
        ReferenceSet.objects
        .filter(id__in=ref_set_ids)
        .prefetch_related('values')
    ):
        cache[ref_set.id] = set(
            ref_set.values.filter(is_active=True).values_list('code', flat=True)
        )
    return cache


def _validate_one_field(field, value, values: dict, ref_cache: dict) -> list[dict]:
    """
    Validate a single value against one DataField's metadata.
    Returns list of error dicts (empty if valid). Does NOT raise.
    """
    errors = []
    field_name = field.name

    # ── 1. required ──────────────────────────────────────────────────
    if field.required:
        is_missing = (
            field_name not in values
            or value is None
            or value == ''
            or value == []
        )
        if is_missing:
            errors.append({
                'field': field_name,
                'code': 'required',
                'message': 'This field is required.',
            })
            return errors  # no point checking further constraints for missing field

    # If value is None/empty and not required, skip all other checks
    if value is None or value == '' or value == []:
        return errors

    # ── 2. type='number' ────────────────────────────────────────────
    if field.type == 'number':
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            # bool is a subclass of int, so reject it explicitly
            errors.append({
                'field': field_name,
                'code': 'invalid_type',
                'message': 'Must be a number.',
            })
            return errors  # can't check min/max on non-numeric values

        # Negative values are no longer banned at the platform level.
        # Use DQ range rules (min: 0) seeded per domain to enforce domain-specific bans.

        # 6-7. validation.min / validation.max (new — was never read before)
        validation = field.validation or {}
        min_val = validation.get('min')
        max_val = validation.get('max')
        if min_val is not None and value < min_val:
            errors.append({
                'field': field_name,
                'code': 'below_min',
                'message': f"Value {value} is below minimum {min_val}.",
            })
        if max_val is not None and value > max_val:
            errors.append({
                'field': field_name,
                'code': 'above_max',
                'message': f"Value {value} is above maximum {max_val}.",
            })

    # ── 3. type='boolean' ───────────────────────────────────────────
    if field.type == 'boolean' and not isinstance(value, bool):
        errors.append({
            'field': field_name,
            'code': 'invalid_type',
            'message': 'Must be true or false.',
        })

    # ── 4. type='select' ────────────────────────────────────────────
    if field.type == 'select':
        allowed = [opt['value'] for opt in (field.options or [])]
        if value not in allowed:
            errors.append({
                'field': field_name,
                'code': 'not_allowed',
                'message': f"Value must be one of {allowed}.",
            })

    # ── 5. type='multiselect' ───────────────────────────────────────
    if field.type == 'multiselect':
        allowed = [opt['value'] for opt in (field.options or [])]
        if not isinstance(value, list) or not all(v in allowed for v in value):
            errors.append({
                'field': field_name,
                'code': 'not_allowed',
                'message': f"All values must be in {allowed}.",
            })

    # ── 8. validation.pattern ──────────────────────────────────────
    validation = field.validation or {}
    pattern = validation.get('pattern')
    if pattern and isinstance(value, str):
        try:
            if not re.match(pattern, value):
                errors.append({
                    'field': field_name,
                    'code': 'pattern_mismatch',
                    'message': f"Value does not match pattern {pattern}.",
                })
        except re.error:
            pass  # skip invalid regex patterns silently

    # ── 9. reference_set ───────────────────────────────────────────
    ref_set_id = getattr(field, 'reference_set_id', None)
    if ref_set_id and ref_set_id in ref_cache and isinstance(value, str):
        if value not in ref_cache[ref_set_id]:
            # Get the reference set name for a better message — use the field's
            # reference_set attribute if it was loaded, otherwise just show ID
            ref_name = getattr(field, 'reference_set', None)
            ref_name = ref_name.name if ref_name else f'reference set {ref_set_id}'
            errors.append({
                'field': field_name,
                'code': 'not_in_reference',
                'message': f"Value '{value}' not found in {ref_name}.",
            })

    # ── 10. type='date' ────────────────────────────────────────────
    if field.type == 'date':
        if isinstance(value, date):
            pass  # Python date objects are always valid
        elif isinstance(value, str):
            try:
                datetime.strptime(value, '%Y-%m-%d')
            except ValueError:
                # Also try ISO format with time component
                try:
                    datetime.fromisoformat(value)
                except (ValueError, TypeError):
                    errors.append({
                        'field': field_name,
                        'code': 'invalid_date',
                        'message': 'Must be a valid date (YYYY-MM-DD).',
                    })
        elif not isinstance(value, datetime):
            errors.append({
                'field': field_name,
                'code': 'invalid_date',
                'message': 'Must be a valid date (YYYY-MM-DD).',
            })

    return errors
